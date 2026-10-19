from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class GpuMonitor(QObject):
    updated = Signal(list)
    unavailable = Signal(str)

    def __init__(self, parent: QObject | None = None, interval_ms: int = 2000):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.refresh)

    def start(self) -> None:
        self.refresh()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        if self._process is not None:
            self._process.kill()
            self._process = None

    def refresh(self) -> None:
        if self._process is not None:
            return
        process = QProcess(self)
        process.setProgram("nvidia-smi")
        process.setArguments([
            "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        process.finished.connect(lambda code, _status, p=process: self._finished(p, code))
        process.errorOccurred.connect(lambda _error, p=process: self._failed(p))
        self._process = process
        process.start()

    def _failed(self, process: QProcess) -> None:
        if process is not self._process:
            return
        self._process = None
        self.unavailable.emit("nvidia-smi 不可用")
        process.deleteLater()

    def _finished(self, process: QProcess, code: int) -> None:
        if process is not self._process:
            process.deleteLater()
            return
        self._process = None
        raw = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        err = bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        process.deleteLater()
        if code != 0:
            self.unavailable.emit(err or f"nvidia-smi exited with code {code}")
            return

        gpus = []
        for line in raw.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 6:
                continue
            try:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "memory_total_mb": int(parts[2]),
                    "memory_used_mb": int(parts[3]),
                    "utilization": int(parts[4]),
                    "temperature_c": int(parts[5]),
                })
            except ValueError:
                continue
        self.updated.emit(gpus)
