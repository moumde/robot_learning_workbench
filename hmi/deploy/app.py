"""Qt control panel for CR3/O6 OpenPI deployment workflows."""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
import math
import os
from pathlib import Path
import signal
import sys
from typing import Any

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtNetwork import QTcpSocket
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[2]
HARDWARE_DIR = ROOT / "config" / "hardware"
CHECKPOINTS_DIR = ROOT / "checkpoints"
DEFAULT_DATASET = ROOT / "dataset" / "replay" / "teleop_once"
TASKS_DIR = ROOT / "tasks"
WORKFLOW_VERSION = 1


def _episode_files(dataset_dir: Path) -> list[tuple[int, Path]]:
    episodes = []
    for path in (dataset_dir / "data").glob("chunk-*/episode_*.parquet"):
        try:
            episode_index = int(path.stem.removeprefix("episode_"))
        except ValueError:
            continue
        episodes.append((episode_index, path))
    return sorted(episodes, key=lambda item: (item[0], str(item[1])))


def _discover_policy_checkpoints(checkpoints_dir: Path = CHECKPOINTS_DIR) -> dict[str, Path]:
    """Map each checkpoint/config directory name to its newest params checkpoint."""

    policies: dict[str, Path] = {}
    if not checkpoints_dir.is_dir():
        return policies

    for policy_dir in sorted(path for path in checkpoints_dir.iterdir() if path.is_dir()):
        candidates = {params_dir.parent.resolve() for params_dir in policy_dir.rglob("params")
                      if params_dir.is_dir()}
        if not candidates:
            continue

        def checkpoint_key(path: Path) -> tuple[tuple[int, ...], str]:
            relative = path.relative_to(policy_dir.resolve())
            steps = tuple(int(part) for part in relative.parts if part.isdigit())
            return steps, relative.as_posix()

        policies[policy_dir.name] = max(candidates, key=checkpoint_key)
    return policies


def _serialize_task(task: Task) -> dict[str, Any]:
    if task.kind == "policy":
        return {
            "type": "policy",
            "description": task.description,
            "prompt": task.prompt,
            "duration_s": task.duration_s,
        }
    if task.kind == "replay" and task.dataset_dir is not None:
        dataset_dir = task.dataset_dir.expanduser().resolve()
        try:
            stored_path = dataset_dir.relative_to(ROOT).as_posix()
        except ValueError:
            stored_path = str(dataset_dir)
        return {
            "type": "replay",
            "description": task.description,
            "dataset_dir": stored_path,
            "repeat_count": task.repeat_count,
            "time_scale": task.time_scale,
        }
    raise ValueError(f"无法保存未知或不完整的任务类型：{task.kind}")


def _deserialize_workflow(data: Any) -> list[Task]:
    if not isinstance(data, dict) or data.get("version") != WORKFLOW_VERSION:
        raise ValueError(f"工作流文件格式不受支持（需要 version={WORKFLOW_VERSION}）")
    raw_tasks = data.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("工作流必须包含至少一个任务")

    tasks: list[Task] = []
    for index, raw in enumerate(raw_tasks, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"任务 {index} 配置必须是对象")
        kind = raw.get("type")
        description = raw.get("description")
        if not isinstance(description, str):
            description = f"任务 {index}"

        if kind == "policy":
            prompt = raw.get("prompt")
            duration = raw.get("duration_s")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"任务 {index} 的推理指令不能为空")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration)
                or not 0.5 <= duration <= 3600.0
            ):
                raise ValueError(f"任务 {index} 的推理时长必须在 0.5 到 3600 秒之间")
            tasks.append(Task("policy", description, float(duration), prompt.strip()))
            continue

        if kind == "replay":
            raw_path = raw.get("dataset_dir")
            repeat = raw.get("repeat_count")
            time_scale = raw.get("time_scale")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(f"任务 {index} 缺少数据集路径")
            if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 10_000:
                raise ValueError(f"任务 {index} 的播放次数必须在 1 到 10000 之间")
            if (
                isinstance(time_scale, bool)
                or not isinstance(time_scale, (int, float))
                or not math.isfinite(time_scale)
                or not 0.1 <= time_scale <= 10.0
            ):
                raise ValueError(f"任务 {index} 的速度倍率必须在 0.1 到 10 之间")
            dataset_dir = Path(raw_path).expanduser()
            if not dataset_dir.is_absolute():
                dataset_dir = ROOT / dataset_dir
            dataset_dir = dataset_dir.resolve()
            if not description or description == f"任务 {index}":
                description = f"重播 · {dataset_dir.name} · {repeat} 遍"
            tasks.append(
                Task(
                    "replay",
                    description,
                    dataset_dir=dataset_dir,
                    repeat_count=repeat,
                    time_scale=float(time_scale),
                )
            )
            continue

        raise ValueError(f"任务 {index} 类型不支持：{kind!r}")
    return tasks


@dataclass(frozen=True)
class Task:
    kind: str
    description: str
    duration_s: float = 0.0
    prompt: str = ""
    dataset_dir: Path | None = None
    repeat_count: int = 1
    time_scale: float = 1.0


class TaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("添加执行任务")
        self.setMinimumWidth(480)
        form = QFormLayout(self)
        self.kind = QComboBox()
        self.kind.addItem("PI05 模型推理", "policy")
        self.kind.addItem("重播数据集轨迹", "replay")
        form.addRow("任务类型", self.kind)

        self.prompt = QLineEdit("Pick up the motor and place it on the right side with the protruding side facing left.")
        form.addRow("推理指令", self.prompt)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.5, 3600.0)
        self.duration.setSingleStep(1.0)
        self.duration.setValue(25.0)
        self.duration.setSuffix(" 秒")
        form.addRow("最长运行时间", self.duration)

        dataset_row = QWidget()
        dataset_layout = QHBoxLayout(dataset_row)
        dataset_layout.setContentsMargins(0, 0, 0, 0)
        self.dataset = QLineEdit(str(DEFAULT_DATASET))
        browse = QPushButton("选择…")
        browse.clicked.connect(self._browse_dataset)
        dataset_layout.addWidget(self.dataset)
        dataset_layout.addWidget(browse)
        form.addRow("数据集目录", dataset_row)

        self.repeat_count = QSpinBox()
        self.repeat_count.setRange(1, 10_000)
        self.repeat_count.setValue(1)
        form.addRow("完整数据集播放次数", self.repeat_count)
        self.time_scale = QDoubleSpinBox()
        self.time_scale.setRange(0.1, 10.0)
        self.time_scale.setSingleStep(0.1)
        self.time_scale.setValue(1.0)
        form.addRow("重播速度倍率", self.time_scale)

        self.kind.currentIndexChanged.connect(self._update_fields)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._update_fields()

    def _browse_dataset(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 LeRobot 数据集", self.dataset.text())
        if directory:
            self.dataset.setText(directory)

    def _update_fields(self) -> None:
        is_policy = self.kind.currentData() == "policy"
        self.prompt.setEnabled(is_policy)
        self.duration.setEnabled(is_policy)
        self.dataset.setEnabled(not is_policy)
        self.repeat_count.setEnabled(not is_policy)
        self.time_scale.setEnabled(not is_policy)

    def task(self) -> Task:
        if self.kind.currentData() == "policy":
            prompt = self.prompt.text().strip()
            if not prompt:
                raise ValueError("推理指令不能为空")
            return Task("policy", f"PI05 推理 · {self.duration.value():g}s", self.duration.value(), prompt)
        dataset = Path(self.dataset.text()).expanduser()
        if not dataset.is_absolute():
            dataset = ROOT / dataset
        if not dataset.is_dir():
            raise ValueError(f"数据集目录不存在：{dataset}")
        episodes = _episode_files(dataset)
        if not episodes:
            raise ValueError(
                f"该目录中没有找到轨迹文件。请选择包含 "
                f"data/chunk-*/episode_*.parquet 的数据集目录：{dataset}"
            )
        repeat_count = self.repeat_count.value()
        return Task(
            "replay",
            f"重播 · {dataset.name} · {len(episodes)} 条轨迹 × {repeat_count} 遍",
            dataset_dir=dataset,
            repeat_count=repeat_count,
            time_scale=self.time_scale.value(),
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Learning Workbench · CR3/O6 控制台")
        self.resize(1000, 760)
        self.tasks: list[Task] = []
        self.server_process: QProcess | None = None
        self.task_process: QProcess | None = None
        self.server_ready = False
        self.stop_sequence_requested = False
        self.close_after_stop = False

        central = QWidget()
        root_layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        selection = QGroupBox("机器人与模型")
        selection_layout = QFormLayout(selection)
        self.hardware = QComboBox()
        profiles = sorted(HARDWARE_DIR.glob("*.toml"))
        for profile in profiles:
            self.hardware.addItem(profile.stem, profile)
        selection_layout.addRow("机器人系统", self.hardware)

        self.policy_config = QComboBox()
        self.policy_checkpoints = _discover_policy_checkpoints()
        if self.policy_checkpoints:
            for policy_name in self.policy_checkpoints:
                self.policy_config.addItem(policy_name, policy_name)
        else:
            self.policy_config.addItem("未在 checkpoints/ 中找到有效模型", "")
        selection_layout.addRow("策略模型", self.policy_config)

        checkpoint_row = QWidget()
        checkpoint_layout = QHBoxLayout(checkpoint_row)
        checkpoint_layout.setContentsMargins(0, 0, 0, 0)
        default_policy = self.policy_config.currentData()
        default_checkpoint = self.policy_checkpoints.get(default_policy, CHECKPOINTS_DIR)
        self.checkpoint = QLineEdit(str(default_checkpoint))
        self.checkpoint_browse_button = QPushButton("选择…")
        self.checkpoint_browse_button.clicked.connect(self._browse_checkpoint)
        self.policy_config.currentIndexChanged.connect(self._policy_changed)
        checkpoint_layout.addWidget(self.checkpoint)
        checkpoint_layout.addWidget(self.checkpoint_browse_button)
        selection_layout.addRow("Checkpoint", checkpoint_row)

        server_row = QWidget()
        server_layout = QHBoxLayout(server_row)
        server_layout.setContentsMargins(0, 0, 0, 0)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(8000)
        self.start_server_button = QPushButton("启动模型服务")
        self.stop_server_button = QPushButton("停止服务")
        self.stop_server_button.setEnabled(False)
        self.server_status = QLabel("未启动")
        self.server_status.setMinimumWidth(100)
        self.start_server_button.clicked.connect(self._start_server)
        self.stop_server_button.clicked.connect(self._stop_server)
        server_layout.addWidget(QLabel("端口"))
        server_layout.addWidget(self.port)
        server_layout.addWidget(self.start_server_button)
        server_layout.addWidget(self.stop_server_button)
        server_layout.addWidget(self.server_status)
        server_layout.addStretch(1)
        selection_layout.addRow("模型服务", server_row)
        root_layout.addWidget(selection)

        sequence_box = QGroupBox("执行序列（按列表顺序运行）")
        sequence_layout = QVBoxLayout(sequence_box)
        self.task_list = QListWidget()
        self.task_list.setAlternatingRowColors(True)
        sequence_layout.addWidget(self.task_list)
        task_buttons = QHBoxLayout()
        add_task = QPushButton("＋ 添加任务")
        remove_task = QPushButton("删除")
        move_up = QPushButton("上移")
        move_down = QPushButton("下移")
        save_workflow = QPushButton("保存工作流")
        load_workflow = QPushButton("读取工作流")
        add_task.clicked.connect(self._add_task)
        remove_task.clicked.connect(self._remove_task)
        move_up.clicked.connect(lambda: self._move_task(-1))
        move_down.clicked.connect(lambda: self._move_task(1))
        save_workflow.clicked.connect(self._save_workflow)
        load_workflow.clicked.connect(self._load_workflow)
        for button in (add_task, remove_task, move_up, move_down, save_workflow, load_workflow):
            task_buttons.addWidget(button)
        task_buttons.addStretch(1)
        sequence_layout.addLayout(task_buttons)
        root_layout.addWidget(sequence_box, 1)

        control_row = QHBoxLayout()
        self.arm_confirm = QCheckBox("我已确认机器人周围安全，并允许真实运动")
        preview_button = QPushButton("预览计划")
        self.run_button = QPushButton("确认并执行")
        self.stop_task_button = QPushButton("停止当前任务")
        self.stop_task_button.setEnabled(False)
        preview_button.clicked.connect(self._preview_plan)
        self.run_button.clicked.connect(self._run_plan)
        self.stop_task_button.clicked.connect(self._stop_task)
        control_row.addWidget(self.arm_confirm)
        control_row.addStretch(1)
        control_row.addWidget(preview_button)
        control_row.addWidget(self.run_button)
        control_row.addWidget(self.stop_task_button)
        root_layout.addLayout(control_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("模型服务与执行日志")
        self.log.setMaximumHeight(170)
        root_layout.addWidget(self.log)

    def _log(self, message: str) -> None:
        self.log.append(message)

    def _browse_checkpoint(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择模型 checkpoint", self.checkpoint.text())
        if directory:
            self.checkpoint.setText(directory)

    def _policy_changed(self, _index: int) -> None:
        checkpoint = self.policy_checkpoints.get(self.policy_config.currentData())
        if checkpoint is not None:
            self.checkpoint.setText(str(checkpoint))

    def _add_task(self) -> None:
        dialog = TaskDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            task = dialog.task()
        except ValueError as exc:
            QMessageBox.warning(self, "任务配置无效", str(exc))
            return
        self.tasks.append(task)
        self._refresh_tasks()

    def _remove_task(self) -> None:
        index = self.task_list.currentRow()
        if 0 <= index < len(self.tasks):
            del self.tasks[index]
            self._refresh_tasks()

    def _move_task(self, offset: int) -> None:
        index = self.task_list.currentRow()
        target = index + offset
        if not (0 <= index < len(self.tasks) and 0 <= target < len(self.tasks)):
            return
        self.tasks[index], self.tasks[target] = self.tasks[target], self.tasks[index]
        self._refresh_tasks()
        self.task_list.setCurrentRow(target)

    def _refresh_tasks(self) -> None:
        self.task_list.clear()
        for number, task in enumerate(self.tasks, start=1):
            item = QListWidgetItem(f"{number}. {task.description}")
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.task_list.addItem(item)

    def _save_workflow(self) -> None:
        if not self.tasks:
            QMessageBox.information(self, "保存工作流", "请先添加至少一个任务。")
            return
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存工作流配置",
            str(TASKS_DIR / "workflow.json"),
            "工作流配置 (*.json)",
        )
        if not file_path:
            return
        target = Path(file_path).expanduser()
        if not target.is_absolute():
            target = ROOT / target
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        target = target.resolve()
        if not target.is_relative_to(TASKS_DIR.resolve()):
            QMessageBox.warning(self, "保存失败", f"工作流只能保存到 {TASKS_DIR} 目录内。")
            return
        document = {
            "version": WORKFLOW_VERSION,
            "tasks": [_serialize_task(task) for task in self.tasks],
        }
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "保存失败", f"无法保存工作流：{exc}")
            return
        self._log(f"已保存工作流：{target}")

    def _load_workflow(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "读取工作流配置",
            str(TASKS_DIR),
            "工作流配置 (*.json)",
        )
        if not file_path:
            return
        source = Path(file_path)
        try:
            document = json.loads(source.read_text())
            loaded_tasks = _deserialize_workflow(document)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "读取失败", f"工作流配置无效：{exc}")
            return

        if self.tasks and QMessageBox.question(
            self,
            "替换当前任务流",
            f"将用 {source.name} 替换当前的 {len(self.tasks)} 个任务，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.tasks = loaded_tasks
        self._refresh_tasks()
        self._log(f"已读取工作流：{source}（{len(loaded_tasks)} 个任务）")

    def _selected_hardware(self) -> Path:
        profile = self.hardware.currentData()
        if not profile or not Path(profile).is_file():
            raise ValueError("没有可用的硬件配置文件")
        return Path(profile)

    def _server_args(self) -> list[str]:
        policy_name = self.policy_config.currentData()
        if not policy_name:
            raise ValueError(f"在 {CHECKPOINTS_DIR} 下没有发现可用模型 checkpoint")
        checkpoint = Path(self.checkpoint.text()).expanduser()
        if not checkpoint.is_absolute():
            checkpoint = ROOT / checkpoint
        checkpoint = checkpoint.resolve()
        if not checkpoint.is_dir():
            raise ValueError(f"Checkpoint 目录不存在：{checkpoint}")
        return [
            "scripts/serve_policy.py",
            "--port",
            str(self.port.value()),
            "policy:checkpoint",
            f"--policy.config={policy_name}",
            f"--policy.dir={checkpoint}",
        ]

    def _start_server(self) -> None:
        if self.server_process is not None:
            return
        try:
            args = ["run_openpi.sh", "python", *self._server_args()]
        except ValueError as exc:
            QMessageBox.warning(self, "无法启动模型服务", str(exc))
            return
        process = QProcess(self)
        process.setProgram("bash")
        process.setArguments([str(ROOT / "scripts" / args[0]), *args[1:]])
        process.setWorkingDirectory(str(ROOT))
        environment = QProcessEnvironment.systemEnvironment()
        # The HMI runs in the NRC environment, while run_openpi.sh selects
        # module/openpi/.venv. Avoid uv's misleading inherited-env warning.
        environment.remove("VIRTUAL_ENV")
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(lambda p=process: self._read_process(p, False))
        process.readyReadStandardError.connect(lambda p=process: self._read_process(p, True))
        process.finished.connect(self._server_finished)
        process.errorOccurred.connect(lambda error: self._log(f"模型服务进程错误：{error}"))
        self.server_process = process
        self.server_ready = False
        self.server_status.setText("启动中…")
        self.start_server_button.setEnabled(False)
        self.stop_server_button.setEnabled(True)
        self._log("启动模型服务：" + " ".join(args[1:]))
        self._set_model_selection_enabled(False)
        process.start()
        self._probe_server()

    def _set_model_selection_enabled(self, enabled: bool) -> None:
        self.policy_config.setEnabled(enabled)
        self.checkpoint.setEnabled(enabled)
        self.checkpoint_browse_button.setEnabled(enabled)
        self.port.setEnabled(enabled)

    def _probe_server(self) -> None:
        if self.server_process is None or self.server_ready:
            return
        if self.server_process.state() == QProcess.ProcessState.NotRunning:
            return
        socket = QTcpSocket(self)
        timer = QTimer(self)
        timer.setSingleShot(True)
        finished = False
        response = bytearray()

        def complete(healthy: bool) -> None:
            nonlocal finished
            if finished:
                return
            finished = True
            timer.stop()
            socket.abort()
            socket.deleteLater()
            timer.deleteLater()
            if healthy and self.server_process is not None:
                self.server_ready = True
                self.server_status.setText("就绪")
                self._log(f"模型服务已在 127.0.0.1:{self.port.value()} 就绪")
            elif self.server_process is not None and not self.server_ready:
                QTimer.singleShot(700, self._probe_server)

        def read_health_response() -> None:
            response.extend(bytes(socket.readAll()))
            if b"\r\n\r\n" not in response:
                return
            status_line = bytes(response).split(b"\r\n", 1)[0].split()
            complete(len(status_line) >= 2 and status_line[1] == b"200")

        socket.connectToHost("127.0.0.1", self.port.value())
        socket.connected.connect(
            lambda: socket.write(
                f"GET /healthz HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.port.value()}\r\n"
                "Connection: close\r\n\r\n".encode()
            )
        )
        socket.readyRead.connect(read_health_response)
        socket.errorOccurred.connect(lambda _error: complete(False))
        timer.timeout.connect(lambda: complete(False))
        timer.start(500)

    def _server_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._log(f"模型服务已退出（code={code}, status={status.name}）")
        self.server_process = None
        self.server_ready = False
        self.server_status.setText("未启动")
        self.start_server_button.setEnabled(True)
        self.stop_server_button.setEnabled(False)
        self._set_model_selection_enabled(True)
        self._close_if_stopped()

    def _stop_server(self) -> None:
        if self.server_process is not None:
            self.server_status.setText("停止中…")
            self._send_interrupt(self.server_process)
            QTimer.singleShot(5000, self._kill_server_if_needed)

    @staticmethod
    def _send_interrupt(process: QProcess) -> None:
        pid = int(process.processId())
        if pid <= 0:
            return
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass

    def _kill_server_if_needed(self) -> None:
        if self.server_process is not None and self.server_process.state() != QProcess.ProcessState.NotRunning:
            self.server_process.kill()

    def _read_process(self, process: QProcess, is_stderr: bool) -> None:
        data = process.readAllStandardError() if is_stderr else process.readAllStandardOutput()
        text = bytes(data).decode(errors="replace").rstrip()
        if text:
            self._log(html.escape(text).replace("\n", "<br>"))

    def _preview_plan(self) -> None:
        if not self.tasks:
            QMessageBox.information(self, "执行计划", "请先添加至少一个任务。")
            return
        try:
            profile = self._selected_hardware()
            lines = [f"硬件：{profile.stem}", f"策略：{self.policy_config.currentText()}"]
            for index, task in enumerate(self.tasks, start=1):
                if task.kind == "replay":
                    data_dir = task.dataset_dir
                    episodes = _episode_files(data_dir)
                    if not episodes:
                        raise ValueError(
                            f"数据集中已没有可重播轨迹：{data_dir}"
                        )
                    episode_indices = [episode_index for episode_index, _path in episodes]
                    lines.append(
                        f"{index}. {task.description} · episode 顺序：{episode_indices} "
                        f"· 整套序列重复 {task.repeat_count} 遍"
                    )
                else:
                    lines.append(f"{index}. {task.description} · {task.prompt}")
            lines.append("\n提示：计划预览只检查配置和轨迹文件，不连接机器人，也不触发模型推理。")
            QMessageBox.information(self, "执行计划预览", "\n".join(lines))
        except ValueError as exc:
            QMessageBox.warning(self, "计划检查失败", str(exc))

    def _run_plan(self) -> None:
        if self.task_process is not None or not self.tasks:
            return
        if not self.arm_confirm.isChecked():
            QMessageBox.warning(self, "需要确认", "请先勾选真实运动安全确认。")
            return
        if any(task.kind == "policy" for task in self.tasks) and not self.server_ready:
            QMessageBox.warning(self, "模型服务未就绪", "请先启动模型服务并等待状态变为“就绪”。")
            return
        try:
            self._selected_hardware()
            if any(task.kind == "policy" for task in self.tasks):
                self._server_args()
        except ValueError as exc:
            QMessageBox.warning(self, "配置无效", str(exc))
            return

        plan_tasks: list[dict[str, Any]] = []
        for task in self.tasks:
            if task.kind == "policy":
                plan_tasks.append({
                    "type": "policy",
                    "name": task.description,
                    "prompt": task.prompt,
                    "duration_s": task.duration_s,
                })
            else:
                dataset_dir = task.dataset_dir
                if not _episode_files(dataset_dir):
                    QMessageBox.warning(
                        self,
                        "数据集无轨迹",
                        f"数据集中没有可重播轨迹：{dataset_dir}",
                    )
                    return
                plan_tasks.append({
                    "type": "replay",
                    "name": task.description,
                    "data_dir": str(dataset_dir),
                    "repeat": task.repeat_count,
                    "time_scale": task.time_scale,
                })

        note = (
            "将连接并控制真实机器人。整套序列开始时会移动到初始位姿；任务之间保持上电和 ServoJ，"
            "每一遍数据集重播前先回初始位姿，再平滑过渡到轨迹首帧；全部任务结束后才统一清理。"
            "如果控制器进入错误态，后续任务会停止。请确认初始位姿和现场环境安全。"
        )
        if QMessageBox.warning(
            self,
            "确认机器人运动",
            note,
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.run_button.setEnabled(False)
        self.stop_task_button.setEnabled(True)
        self._start_workflow(plan_tasks)

    def _start_workflow(self, plan_tasks: list[dict[str, Any]]) -> None:
        config = str(self._selected_hardware())
        plan_json = json.dumps({"tasks": plan_tasks}, ensure_ascii=False)
        process = QProcess(self)
        process.setProgram("bash")
        process.setArguments([
            str(ROOT / "scripts" / "run_nrc.sh"),
            "python",
            str(ROOT / "core" / "openpi" / "cr3_o6" / "run_workflow.py"),
            "--config", config,
            "--host", "127.0.0.1",
            "--port", str(self.port.value()),
            "--plan-json", plan_json,
            "--confirm-motion",
        ])
        process.setWorkingDirectory(str(ROOT))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(lambda p=process: self._read_process(p, False))
        process.readyReadStandardError.connect(lambda p=process: self._read_process(p, True))
        process.finished.connect(self._workflow_finished)
        process.errorOccurred.connect(lambda error: self._log(f"工作流进程错误：{error}"))
        self.task_process = process
        self._log(f"启动单会话工作流，包含 {len(self.tasks)} 个任务。")
        process.start()

    def _workflow_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._log(f"工作流进程退出（code={code}, status={status.name}）")
        self.task_process = None
        if self.stop_sequence_requested:
            self._log("工作流已停止。")
            self.stop_sequence_requested = False
            self._finish_task_run()
            self._close_if_stopped()
            return
        if code != 0:
            self._log("工作流失败；未继续任何后续任务。请检查控制器状态和日志。")
            self._finish_task_run()
            self._close_if_stopped()
            return
        self._log("执行序列完成。")
        self._finish_task_run()
        self._close_if_stopped()

    def _stop_task(self) -> None:
        if self.task_process is not None:
            self._log("请求停止当前任务。")
            self.stop_sequence_requested = True
            self._send_interrupt(self.task_process)
            QTimer.singleShot(15000, self._kill_task_if_needed)

    def _kill_task_if_needed(self) -> None:
        if self.task_process is not None and self.task_process.state() != QProcess.ProcessState.NotRunning:
            self._log("任务尚未响应停止信号；未强制杀进程，以保留脚本清理硬件的机会。")
            QMessageBox.warning(
                self,
                "任务尚未停止",
                "任务进程未能在 15 秒内安全退出。请检查机器人状态；如存在风险，立即使用实体急停。",
            )

    def _finish_task_run(self) -> None:
        self.task_process = None
        self.run_button.setEnabled(True)
        self.stop_task_button.setEnabled(False)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        running = any(
            process is not None and process.state() != QProcess.ProcessState.NotRunning
            for process in (self.task_process, self.server_process)
        )
        if running:
            answer = QMessageBox.question(
                self,
                "退出工作台",
                "仍有任务或模型服务在运行。退出将发送中断信号，并等待清理完成。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.close_after_stop = True
            if self.task_process is not None:
                self.stop_sequence_requested = True
                self._send_interrupt(self.task_process)
            if self.server_process is not None:
                self._send_interrupt(self.server_process)
            event.ignore()
            return
        event.accept()

    def _close_if_stopped(self) -> None:
        if self.close_after_stop and self.task_process is None and self.server_process is None:
            self.close_after_stop = False
            QTimer.singleShot(0, self.close)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Robot Learning Workbench HMI")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
