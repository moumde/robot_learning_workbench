from __future__ import annotations

import json
import os
import signal

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from hmi.trainui.models import TrainSpec
from hmi.trainui.paths import RUN_OPENPI, WORKSPACE_ROOT


class OpenPIService(QObject):
    # Persistent config inspector: only names first, one selected config on demand.
    config_names_ready = Signal(list)
    config_ready = Signal(dict)
    config_inspect_failed = Signal(str, str)  # config name, error

    helper_output = Signal(str)
    helper_failed = Signal(str)
    norm_finished = Signal(bool, str)

    training_started = Signal()
    training_output = Signal(str)
    training_finished = Signal(int)
    training_error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        # Long-lived process.  It imports openpi.training.config once and then
        # waits for inspect requests on stdin.  It never serializes all configs.
        self._inspector: QProcess | None = None
        self._inspector_stdout_buffer = ""
        self._inspector_stderr_buffer = ""
        self._pending_inspect_names: list[str] = []

        # One-shot helper is reserved for norm-stat computation.
        self._helper: QProcess | None = None
        self._helper_stdout = ""
        self._helper_stderr = ""
        self._helper_kind = ""

        self._training: QProcess | None = None

    @property
    def training_running(self) -> bool:
        return (
            self._training is not None
            and self._training.state() != QProcess.ProcessState.NotRunning
        )

    @property
    def inspector_running(self) -> bool:
        return (
            self._inspector is not None
            and self._inspector.state() != QProcess.ProcessState.NotRunning
        )

    def _new_openpi_process(self) -> QProcess:
        process = QProcess(self)
        process.setProgram("bash")
        process.setWorkingDirectory(str(WORKSPACE_ROOT))
        environment = QProcessEnvironment.systemEnvironment()
        # The Qt process deliberately prepends PySide6's Qt libraries. Never
        # leak those GUI loader paths into JAX/OpenPI child processes.
        for key in (
            "VIRTUAL_ENV",
            "LD_LIBRARY_PATH",
            "LD_PRELOAD",
            "QT_PLUGIN_PATH",
            "QT_QPA_PLATFORM_PLUGIN_PATH",
            "QML2_IMPORT_PATH",
            "QML_IMPORT_PATH",
        ):
            environment.remove(key)
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        return process

    @staticmethod
    def _openpi_args(module: str, extra: list[str] | None = None) -> list[str]:
        args = [str(RUN_OPENPI), "python", "-m", module]
        if extra:
            args.extend(extra)
        return args

    # ------------------------------------------------------------------
    # Persistent config inspector
    # ------------------------------------------------------------------
    def start_config_inspector(self) -> None:
        if self.inspector_running:
            return

        process = self._new_openpi_process()
        process.setArguments(
            self._openpi_args("hmi.trainui.bridge.inspect_openpi", ["--server"])
        )
        process.readyReadStandardOutput.connect(
            lambda p=process: self._read_inspector_stdout(p)
        )
        process.readyReadStandardError.connect(
            lambda p=process: self._read_inspector_stderr(p)
        )
        process.finished.connect(
            lambda code, _status, p=process: self._inspector_finished(p, code)
        )
        process.errorOccurred.connect(
            lambda error, p=process: self._inspector_error(p, error)
        )

        self._inspector = process
        self._inspector_stdout_buffer = ""
        self._inspector_stderr_buffer = ""
        process.start()

    # Backward-compatible name used by older controller code.
    def inspect_configs(self) -> None:
        self.start_config_inspector()

    def inspect_config(self, config_name: str) -> None:
        config_name = str(config_name).strip()
        if not config_name:
            return

        if not self.inspector_running:
            # Queue exactly the latest/current request.  Starting the inspector
            # will emit the name list first; then the queued inspect is sent.
            self._pending_inspect_names[:] = [config_name]
            self.start_config_inspector()
            return

        self._send_inspector_request({"cmd": "inspect", "name": config_name})

    def _send_inspector_request(self, payload: dict) -> None:
        process = self._inspector
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        process.write(line.encode("utf-8"))

    def _read_inspector_stdout(self, process: QProcess) -> None:
        if process is not self._inspector:
            return
        raw = process.readAllStandardOutput()
        self._inspector_stdout_buffer += bytes(raw).decode("utf-8", errors="replace")

        while "\n" in self._inspector_stdout_buffer:
            line, self._inspector_stdout_buffer = self._inspector_stdout_buffer.split("\n", 1)
            self._handle_inspector_line(line.strip())

    def _handle_inspector_line(self, line: str) -> None:
        if not line:
            return

        if line.startswith("TRAINUI_NAMES="):
            try:
                payload = json.loads(line[len("TRAINUI_NAMES="):])
            except json.JSONDecodeError as exc:
                self.config_inspect_failed.emit("", f"配置名称列表解析失败：{exc}")
                return
            if not isinstance(payload, list) or not all(isinstance(x, str) for x in payload):
                self.config_inspect_failed.emit("", "OpenPI 配置名称输出格式无效")
                return
            self.config_names_ready.emit(payload)
            if self._pending_inspect_names:
                name = self._pending_inspect_names[-1]
                self._pending_inspect_names.clear()
                self._send_inspector_request({"cmd": "inspect", "name": name})
            return

        if line.startswith("TRAINUI_CONFIG="):
            try:
                payload = json.loads(line[len("TRAINUI_CONFIG="):])
            except json.JSONDecodeError as exc:
                self.config_inspect_failed.emit("", f"当前配置解析失败：{exc}")
                return
            if not isinstance(payload, dict):
                self.config_inspect_failed.emit("", "OpenPI 当前配置输出格式无效")
                return
            self.config_ready.emit(payload)
            return

        if line.startswith("TRAINUI_ERROR="):
            try:
                payload = json.loads(line[len("TRAINUI_ERROR="):])
            except json.JSONDecodeError:
                self.config_inspect_failed.emit("", line)
                return
            if isinstance(payload, dict):
                self.config_inspect_failed.emit(
                    str(payload.get("name", "")),
                    str(payload.get("message", "OpenPI 配置检查失败")),
                )
            else:
                self.config_inspect_failed.emit("", str(payload))
            return

        # Preserve useful OpenPI diagnostics without treating them as protocol.
        self.helper_output.emit(line + "\n")

    def _read_inspector_stderr(self, process: QProcess) -> None:
        if process is not self._inspector:
            return
        raw = process.readAllStandardError()
        text = bytes(raw).decode("utf-8", errors="replace")
        self._inspector_stderr_buffer += text
        if text.strip():
            self.helper_output.emit(text)

    def _inspector_error(self, process: QProcess, error: QProcess.ProcessError) -> None:
        if process is not self._inspector:
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._inspector = None
            process.deleteLater()
            self.config_inspect_failed.emit("", "无法启动 OpenPI 配置检查进程")

    def _inspector_finished(self, process: QProcess, code: int) -> None:
        if process is not self._inspector:
            process.deleteLater()
            return
        stderr = self._inspector_stderr_buffer.strip()
        self._inspector = None
        self._inspector_stdout_buffer = ""
        self._inspector_stderr_buffer = ""
        process.deleteLater()
        if code != 0:
            self.config_inspect_failed.emit(
                "", stderr or f"OpenPI 配置检查进程异常退出，code={code}"
            )

    def shutdown_inspector(self) -> None:
        process = self._inspector
        if process is None:
            return
        if process.state() != QProcess.ProcessState.NotRunning:
            self._send_inspector_request({"cmd": "quit"})
            if not process.waitForFinished(800):
                process.terminate()
                if not process.waitForFinished(500):
                    process.kill()
        self._inspector = None

    # ------------------------------------------------------------------
    # One-shot helper: norm stats
    # ------------------------------------------------------------------
    def compute_norm_stats(self, config_name: str, dataset_id: str) -> None:
        if self._helper is not None:
            self.helper_failed.emit("已有 OpenPI 辅助任务正在运行")
            return
        process = self._new_openpi_process()
        process.setArguments(self._openpi_args(
            "hmi.trainui.bridge.compute_norm_stats",
            ["--config-name", config_name, "--dataset-id", dataset_id],
        ))
        self._start_helper(process, "norm")

    def _start_helper(self, process: QProcess, kind: str) -> None:
        self._helper = process
        self._helper_kind = kind
        self._helper_stdout = ""
        self._helper_stderr = ""
        process.readyReadStandardOutput.connect(lambda p=process: self._read_helper(p, False))
        process.readyReadStandardError.connect(lambda p=process: self._read_helper(p, True))
        process.finished.connect(lambda code, _status, p=process: self._helper_finished(p, code))
        process.errorOccurred.connect(lambda error, p=process: self._helper_error(p, error))
        process.start()

    def _helper_error(self, process: QProcess, error: QProcess.ProcessError) -> None:
        if process is not self._helper:
            return
        if error == QProcess.ProcessError.FailedToStart:
            kind = self._helper_kind
            self._helper = None
            self._helper_kind = ""
            process.deleteLater()
            message = f"无法启动 OpenPI {kind or 'helper'} 进程"
            if kind == "norm":
                self.norm_finished.emit(False, message)
            else:
                self.helper_failed.emit(message)

    def _read_helper(self, process: QProcess, stderr: bool) -> None:
        raw = process.readAllStandardError() if stderr else process.readAllStandardOutput()
        text = bytes(raw).decode("utf-8", errors="replace")
        if stderr:
            self._helper_stderr += text
        else:
            self._helper_stdout += text
        if text.strip():
            self.helper_output.emit(text)

    def _helper_finished(self, process: QProcess, code: int) -> None:
        if process is not self._helper:
            process.deleteLater()
            return
        kind = self._helper_kind
        stdout = self._helper_stdout
        stderr = self._helper_stderr
        self._helper = None
        self._helper_kind = ""
        process.deleteLater()

        if kind == "norm":
            message = (stderr.strip() or stdout.strip()).splitlines()[-1:] or [""]
            self.norm_finished.emit(code == 0, message[0])

    # ------------------------------------------------------------------
    # Training process
    # ------------------------------------------------------------------
    def start_training(self, spec: TrainSpec) -> None:
        if self.training_running:
            self.training_error.emit("训练进程已经在运行")
            return
        process = self._new_openpi_process()
        payload = json.dumps(spec.to_dict(), ensure_ascii=False, separators=(",", ":"))
        process.setArguments(self._openpi_args(
            "hmi.trainui.bridge.run_training",
            ["--spec-json", payload],
        ))
        process.readyReadStandardOutput.connect(lambda p=process: self._read_training(p, False))
        process.readyReadStandardError.connect(lambda p=process: self._read_training(p, True))
        process.started.connect(self.training_started)
        process.finished.connect(lambda code, _status, p=process: self._training_finished(p, code))
        process.errorOccurred.connect(lambda error, p=process: self._training_process_error(p, error))
        self._training = process
        process.start()

    def _training_process_error(self, process: QProcess, error: QProcess.ProcessError) -> None:
        if process is not self._training:
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._training = None
            process.deleteLater()
            self.training_error.emit("无法启动训练子进程")

    def _read_training(self, process: QProcess, stderr: bool) -> None:
        raw = process.readAllStandardError() if stderr else process.readAllStandardOutput()
        text = bytes(raw).decode("utf-8", errors="replace")
        if text:
            self.training_output.emit(text)

    def _training_finished(self, process: QProcess, code: int) -> None:
        if process is not self._training:
            process.deleteLater()
            return
        self._training = None
        process.deleteLater()
        self.training_finished.emit(code)

    def request_stop_training(self) -> None:
        if not self.training_running or self._training is None:
            return
        pid = int(self._training.processId())
        if pid <= 0:
            return
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass

    def force_kill_training(self) -> None:
        if self.training_running and self._training is not None:
            self._training.kill()
