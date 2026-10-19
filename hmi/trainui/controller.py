from __future__ import annotations

from datetime import datetime
import re

from PySide6.QtCore import QObject, QTimer

from hmi.trainui.models import ConfigInfo, DatasetInfo, RunMode, TrainSpec, TrainState
from hmi.trainui.paths import LOG_ROOT
from hmi.trainui.services.checkpoint_service import CheckpointService
from hmi.trainui.services.dataset_service import DatasetService
from hmi.trainui.services.gpu_monitor import GpuMonitor
from hmi.trainui.services.log_parser import LogParser
from hmi.trainui.services.openpi_service import OpenPIService
from hmi.trainui.views.main_window import MainWindow


_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class TrainController(QObject):
    def __init__(self, window: MainWindow):
        super().__init__(window)
        self.window = window
        self.openpi = OpenPIService(self)
        self.gpu = GpuMonitor(self)
        self.parser = LogParser()

        self.config_names: list[str] = []
        self.datasets: dict[str, DatasetInfo] = {}
        self.current_config: ConfigInfo | None = None
        self.current_dataset: DatasetInfo | None = None
        self.current_spec: TrainSpec | None = None
        self.log_file = None
        self.state = TrainState.IDLE
        self._last_progress_completed = 0
        self._log_interval_adjustment: tuple[int, int] | None = None

        window.close_handler = self.request_close
        window.refresh_datasets_requested.connect(self.refresh_datasets)
        window.config_changed.connect(self.select_config)
        window.dataset_changed.connect(self.select_dataset)
        window.experiment_changed.connect(lambda _text: self._update_checkpoint_status())
        window.compute_norm_requested.connect(self.compute_norm_stats)
        window.start_requested.connect(self.start_training)
        window.stop_requested.connect(self.stop_training)
        window.force_stop_requested.connect(self.force_stop)

        self.openpi.config_names_ready.connect(self._config_names_ready)
        self.openpi.config_ready.connect(self._config_ready)
        self.openpi.config_inspect_failed.connect(self._config_inspect_failed)
        self.openpi.helper_output.connect(self._helper_output)
        self.openpi.helper_failed.connect(self._helper_failed)
        self.openpi.norm_finished.connect(self._norm_finished)
        self.openpi.training_started.connect(self._training_started)
        self.openpi.training_output.connect(self._training_output)
        self.openpi.training_finished.connect(self._training_finished)
        self.openpi.training_error.connect(self._training_error)

        self.gpu.updated.connect(window.update_gpu)
        self.gpu.unavailable.connect(lambda message: window.gpu_name.setText(message))

    def start(self) -> None:
        self._set_state(TrainState.VALIDATING)
        self.window.append_log(
            "正在读取 OpenPI 配置名称…详细内容只加载当前选择的配置。"
        )
        self.openpi.start_config_inspector()
        self.gpu.start()

    # ------------------------------------------------------------------
    # Config registry / on-demand inspection
    # ------------------------------------------------------------------
    def _config_names_ready(self, names: list) -> None:
        clean = [str(name) for name in names if str(name)]
        if not clean:
            self._config_inspect_failed("", "OpenPI 配置注册表为空")
            return

        previous = str(self.window.config_combo.currentData() or "")
        self.config_names = clean
        self.window.populate_config_names(clean, preferred=previous or None)

        selected = str(self.window.config_combo.currentData() or "")
        self.window.append_log(
            f"已读取 {len(clean)} 个配置名称；尚未解析任何详细配置。"
        )
        if selected:
            self.select_config(selected)
        else:
            self.window.show_config_unselected()
            self._set_state(TrainState.IDLE)

    def select_config(self, name: str) -> None:
        name = str(name or "").strip()
        if not name or name not in self.config_names:
            return
        if self.openpi.training_running:
            return
        if self.current_config is not None and self.current_config.name == name:
            return

        self.current_config = None
        self.current_dataset = None
        self.datasets = {}
        self.window.show_config_loading(name)
        self._set_state(TrainState.VALIDATING)
        self.window.append_log(f"正在加载当前训练配置：{name}")
        self.openpi.inspect_config(name)

    def _config_ready(self, payload: dict) -> None:
        try:
            config = ConfigInfo.from_payload(payload)
        except (KeyError, TypeError, ValueError) as exc:
            self._config_inspect_failed(str(payload.get("name", "")), str(exc))
            return

        # If the user changed the combo while the previous config was being
        # inspected, never apply stale details to the newly selected name.
        selected = str(self.window.config_combo.currentData() or "")
        if selected and config.name != selected:
            return

        self.current_config = config
        self.window.apply_config(config)

        if config.inspect_warnings:
            for warning in config.inspect_warnings:
                self.window.append_log(f"配置检查警告 [{config.name}]：{warning}")

        self.refresh_datasets()
        self._update_checkpoint_status()
        self._set_state(TrainState.IDLE)
        self.window.append_log(f"当前配置已加载：{config.name}")

    def _config_inspect_failed(self, name: str, message: str) -> None:
        selected = str(self.window.config_combo.currentData() or "")
        if name and selected and name != selected:
            return
        self.current_config = None
        self.current_dataset = None
        self.datasets = {}
        self.window.show_config_error(name or selected, message)
        self._set_state(TrainState.FAILED)
        self.window.warn("OpenPI 配置读取失败", message)

    # ------------------------------------------------------------------
    # Dataset / normalization
    # ------------------------------------------------------------------
    def refresh_datasets(self) -> None:
        config = self.current_config
        if config is None:
            return

        service = DatasetService()
        if not config.dataset_override_supported:
            self.datasets = {}
            self.current_dataset = None
            label = config.default_repo_id or f"由 {config.data_factory} 决定"
            self.window.set_dataset_selector_mode(False, label)
            self.window.show_dataset(None)
            self._update_norm_status()
            return

        self.window.set_dataset_selector_mode(True)
        preferred = self.current_dataset.repo_id if self.current_dataset else config.default_repo_id
        discovered = service.discover(config)

        # Keep the config-declared repo visible even if it is not in the local
        # workbench cache.  It may be a Hugging Face repo that OpenPI can resolve.
        if config.default_repo_id and all(d.repo_id != config.default_repo_id for d in discovered):
            configured = service.configured_source(config)
            if configured is not None:
                discovered.insert(0, configured)

        self.datasets = {dataset.repo_id: dataset for dataset in discovered}
        self.window.populate_datasets(discovered, preferred=preferred)

        selected = (
            preferred
            if preferred and preferred in self.datasets
            else (discovered[0].repo_id if discovered else "")
        )
        self.select_dataset(selected)
        index = self.window.dataset_combo.findData(selected)
        if index >= 0:
            self.window.dataset_combo.setCurrentIndex(index)

    def select_dataset(self, repo_id: str) -> None:
        self.current_dataset = self.datasets.get(repo_id)
        self.window.show_dataset(self.current_dataset)
        self._update_norm_status()
        self._update_checkpoint_status()

    def _selected_dataset_id(self) -> str | None:
        if self.current_dataset is not None:
            return self.current_dataset.repo_id
        if self.current_config is not None:
            return self.current_config.default_repo_id
        return None

    def _update_norm_status(self) -> None:
        config = self.current_config
        if config is None:
            self.window.show_norm("—", False, supported=False)
            return

        if not config.norm_stats_supported:
            self.window.show_norm(
                "该配置的数据管线不支持 TrainUI 本地归一化统计切换；请查看完整配置。",
                False,
                supported=False,
            )
            return

        if self.current_dataset is not None and not self.current_dataset.valid:
            self.window.show_norm(
                "当前数据集不可用，不能计算归一化统计。请先选择存在且兼容的数据集。",
                False,
                supported=True,
                blocked=True,
            )
            return

        path = config.norm_stats_path(self._selected_dataset_id())
        if path is None:
            self.window.show_norm("无法从当前配置推导 norm_stats.json 路径", False, supported=False)
            return
        self.window.show_norm(str(path), path.is_file(), supported=True)

    def compute_norm_stats(self) -> None:
        config = self.current_config
        dataset_id = self._selected_dataset_id()
        if config is None or not config.norm_stats_supported:
            self.window.warn("无法计算", "当前训练配置不支持 TrainUI 的本地归一化统计计算。")
            return
        if not dataset_id:
            self.window.warn("无法计算", "当前配置尚未指定数据集，请先选择一个本地数据集。")
            return
        if self.current_dataset is not None and not self.current_dataset.valid:
            self.window.warn(
                "数据集不可用",
                "\n".join(self.current_dataset.errors)
                + "\n\n归一化统计未启动，因此不会再让 OpenPI 回退到一个不存在的远程仓库。",
            )
            return

        target = config.norm_stats_path(dataset_id)
        if target is not None and target.exists() and not self.window.confirm(
            "重新计算归一化统计",
            f"统计文件已经存在：\n{target}\n\n是否重新计算并覆盖？",
        ):
            return

        self.window.compute_norm_button.setEnabled(False)
        self.window.append_log(f"开始计算归一化统计：config={config.name}, dataset={dataset_id}")
        self.openpi.compute_norm_stats(config.name, dataset_id)

    def _norm_finished(self, success: bool, message: str) -> None:
        if self.current_config and self.current_config.norm_stats_supported:
            self.window.compute_norm_button.setEnabled(True)
        self._update_norm_status()
        if success:
            self.window.append_log("归一化统计计算完成。")
        else:
            self.window.warn("归一化统计失败", message or "请查看日志。")

    # ------------------------------------------------------------------
    # Helpers / form -> TrainSpec
    # ------------------------------------------------------------------
    def _helper_output(self, text: str) -> None:
        for line in text.replace("\r", "\n").splitlines():
            line = line.strip()
            if line and not line.startswith("TRAINUI_JSON="):
                self.window.append_log(line)

    def _helper_failed(self, message: str) -> None:
        self.window.compute_norm_button.setEnabled(True)
        self.window.framework_status.setText("OpenPI · 错误")
        self._set_state(TrainState.FAILED)
        self.window.warn("OpenPI 错误", message)

    @staticmethod
    def _parse_optional_positive_float(value, name: str) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} 不是有效数字") from exc
        if number <= 0:
            raise ValueError(f"{name} 必须大于 0")
        return number

    def _build_spec(self) -> TrainSpec:
        config = self.current_config
        if config is None:
            raise ValueError("OpenPI 配置尚未加载")
        if not config.runnable:
            raise ValueError(config.runnable_reason or "当前配置不可由 OpenPI 训练入口执行")

        dataset_id: str | None = None
        if config.dataset_override_supported:
            dataset_id = self._selected_dataset_id()
            if not dataset_id:
                raise ValueError("该配置需要 repo_id，请先选择训练数据集")
            if self.current_dataset is not None and not self.current_dataset.valid:
                raise ValueError(
                    "数据集结构不符合当前配置能够静态推导的要求：\n"
                    + "\n".join(self.current_dataset.errors)
                )

        values = self.window.form_values()
        exp_name = str(values["exp_name"])
        if not _SAFE_NAME.fullmatch(exp_name):
            raise ValueError("实验名称仅允许字母、数字、点、下划线和连字符")

        try:
            mode = RunMode(values["run_mode"])
        except ValueError as exc:
            raise ValueError("无效启动方式") from exc

        num_train_steps = int(values["num_train_steps"])
        requested_log_interval = int(values["log_interval"])
        effective_log_interval = requested_log_interval
        self._log_interval_adjustment = None
        if num_train_steps <= requested_log_interval:
            effective_log_interval = 1
            if requested_log_interval != 1:
                self._log_interval_adjustment = (requested_log_interval, 1)
                self.window.log_interval.setValue(1)

        warmup = values.get("warmup_steps")
        decay_steps = values.get("decay_steps")
        warmup = None if warmup is None else int(warmup)
        decay_steps = None if decay_steps is None else int(decay_steps)
        if warmup is not None and decay_steps is not None and decay_steps <= warmup:
            raise ValueError("学习率衰减步数必须大于预热步数")

        return TrainSpec(
            config_name=config.name,
            dataset_id=dataset_id,
            exp_name=exp_name,
            num_train_steps=num_train_steps,
            batch_size=int(values["batch_size"]),
            save_interval=int(values["save_interval"]),
            log_interval=effective_log_interval,
            keep_period=None if int(values["keep_period"]) == 0 else int(values["keep_period"]),
            num_workers=int(values["num_workers"]),
            peak_lr=self._parse_optional_positive_float(values.get("peak_lr"), "峰值学习率"),
            warmup_steps=warmup,
            decay_steps=decay_steps,
            decay_lr=self._parse_optional_positive_float(values.get("decay_lr"), "衰减后学习率"),
            clip_gradient_norm=self._parse_optional_positive_float(
                values.get("clip_gradient_norm"), "梯度裁剪阈值"
            ),
            seed=int(values["seed"]),
            fsdp_devices=int(values["fsdp_devices"]),
            wandb_enabled=bool(values["wandb_enabled"]),
            run_mode=mode,
        )

    # ------------------------------------------------------------------
    # Training lifecycle
    # ------------------------------------------------------------------
    def start_training(self) -> None:
        if self.openpi.training_running:
            return

        self._set_state(TrainState.VALIDATING)
        try:
            spec = self._build_spec()
        except ValueError as exc:
            self._set_state(TrainState.IDLE)
            self.window.warn("训练配置无效", str(exc))
            return

        assert self.current_config is not None
        config = self.current_config

        # Config-driven behavior: missing norm stats are not globally assumed to
        # be fatal.  Warn for local LeRobot configs, then let OpenPI be the final
        # authority if the user chooses to continue.
        norm_path = config.norm_stats_path(spec.dataset_id)
        if config.norm_stats_supported and norm_path is not None and not norm_path.is_file():
            if not self.window.confirm(
                "归一化统计缺失",
                f"当前没有找到：\n{norm_path}\n\n"
                "大多数机器人微调配置需要对应的归一化统计。"
                "如果这个 TrainConfig 明确允许无归一化训练，可以继续；否则建议先计算。\n\n"
                "仍然继续启动 OpenPI 训练吗？",
            ):
                self._set_state(TrainState.IDLE)
                return

        experiment_dir, latest = CheckpointService.status(config, spec.exp_name)
        if spec.run_mode == RunMode.NEW and experiment_dir.exists():
            self._set_state(TrainState.IDLE)
            self.window.warn(
                "实验目录已存在",
                f"{experiment_dir}\n\n请选择“从最新检查点继续”、“覆盖同名实验”，或修改实验名称。",
            )
            return
        if spec.run_mode == RunMode.RESUME and latest is None:
            self._set_state(TrainState.IDLE)
            self.window.warn("无法继续训练", f"没有找到可恢复的检查点：\n{experiment_dir}")
            return
        if spec.run_mode == RunMode.RESUME and latest is not None and spec.num_train_steps <= latest:
            self._set_state(TrainState.IDLE)
            self.window.warn(
                "继续训练的目标步数无效",
                f"最新检查点为第 {latest} 步，训练步数必须大于该值。",
            )
            return
        if spec.run_mode == RunMode.OVERWRITE and experiment_dir.exists():
            if not self.window.confirm(
                "确认覆盖",
                f"将覆盖已有实验目录：\n{experiment_dir}\n\n现有检查点可能被删除，是否继续？",
            ):
                self._set_state(TrainState.IDLE)
                return

        self.current_spec = spec
        self._last_progress_completed = 0
        self.parser.reset()
        self.window.reset_metrics(spec.num_train_steps)
        self.window.enable_force_stop(False)
        self._open_log_file(spec)
        self._write_log(
            f"START config={spec.config_name} dataset={spec.dataset_id} "
            f"exp={spec.exp_name} mode={spec.run_mode.value}"
        )

        if self._log_interval_adjustment is not None:
            old_value, new_value = self._log_interval_adjustment
            self.window.append_log(
                f"当前为短训练：指标记录间隔已从 {old_value} 自动调整为 {new_value}，"
                "以保证损失曲线持续更新。"
            )

        self._set_state(TrainState.STARTING)
        self.window.set_running(True)
        self.openpi.start_training(spec)

    def _open_log_file(self, spec: TrainSpec) -> None:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = LOG_ROOT / f"{spec.exp_name}_{stamp}.log"
        self.log_file = path.open("a", encoding="utf-8")
        self.window.append_log(f"日志文件：{path}")

    def _write_log(self, line: str) -> None:
        if self.log_file is not None:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def _training_started(self) -> None:
        self._set_state(TrainState.RUNNING)
        self.window.append_log("训练进程已启动。")

    def _training_output(self, chunk: str) -> None:
        if self.log_file is not None:
            self.log_file.write(chunk)
            self.log_file.flush()

        configured_total = self.current_spec.num_train_steps if self.current_spec else 1
        for record in self.parser.feed(chunk):
            if self.parser.should_show(record.line):
                self.window.append_log(record.line)

            if record.progress is not None:
                self._last_progress_completed = max(
                    self._last_progress_completed,
                    record.progress.completed,
                )
                total = record.progress.total or configured_total
                self.window.update_progress(self._last_progress_completed, total)
                self._update_checkpoint_status()

            if record.metrics is not None:
                self.window.update_metrics(record.metrics)

            if record.event is not None and record.event.get("type") == "training_failed":
                self.window.append_log(f"训练异常：{record.event.get('message', '')}")

    def stop_training(self) -> None:
        if not self.openpi.training_running:
            return
        self._set_state(TrainState.STOPPING)
        self.window.stop_button.setEnabled(False)
        self.window.append_log(
            "已发送 SIGINT。OpenPI 将停止；当前未完成的训练步不会作为新检查点保存，"
            "后续可从最近一次已完成的检查点继续。"
        )
        self.openpi.request_stop_training()
        QTimer.singleShot(15_000, self._enable_force_if_needed)

    def _enable_force_if_needed(self) -> None:
        if self.openpi.training_running:
            self.window.enable_force_stop(True)
            self.window.append_log("训练进程 15 秒后仍未退出，如确认需要，可使用“强制结束”。")

    def force_stop(self) -> None:
        if not self.openpi.training_running:
            return
        if not self.window.confirm(
            "强制结束训练",
            "强制结束可能中断正在进行的检查点写入。\n"
            "只有在普通停止无法退出时才应使用。是否继续？",
        ):
            return
        self.openpi.force_kill_training()

    def _training_finished(self, code: int) -> None:
        self.window.set_running(False)
        self.window.enable_force_stop(False)
        self._update_checkpoint_status()

        if code == 0:
            if self.current_spec is not None:
                self.window.mark_training_complete(self.current_spec.num_train_steps)
            self._set_state(TrainState.FINISHED)
            self.window.append_log("训练正常结束。")
        elif code in (130, 2):
            self._set_state(TrainState.IDLE)
            self.window.append_log(f"训练已停止（退出码 {code}）。")
        else:
            self._set_state(TrainState.FAILED)
            self.window.append_log(f"训练异常退出（退出码 {code}）。")

        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None
        self.current_spec = None
        self._log_interval_adjustment = None

    def _training_error(self, message: str) -> None:
        self.window.set_running(False)
        self.window.enable_force_stop(False)
        self._set_state(TrainState.FAILED)
        self.window.warn("训练进程错误", message)
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None

    def _update_checkpoint_status(self) -> None:
        if self.current_config is None:
            return
        exp_name = self.window.exp_name.text().strip()
        if not exp_name:
            return
        directory, latest = CheckpointService.status(self.current_config, exp_name)
        self.window.update_checkpoint(str(directory), latest)

    def _set_state(self, state: TrainState) -> None:
        self.state = state
        self.window.set_state(state)

    def request_close(self) -> bool:
        if self.openpi.training_running:
            self.window.warn(
                "训练仍在运行",
                "请先使用“停止训练”等待进程退出，再关闭训练界面。\n"
                "这样可以避免留下无法管理的训练子进程。",
            )
            return False

        self.gpu.stop()
        self.openpi.shutdown_inspector()
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None
        return True
