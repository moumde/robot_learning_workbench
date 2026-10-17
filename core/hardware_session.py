"""Cross-process ownership of a robot endpoint, independent of vendor SDKs."""

from __future__ import annotations

import fcntl
import os
import threading
from pathlib import Path
from urllib.parse import quote


class RobotSessionBusyError(RuntimeError):
    """Another application still owns the requested robot endpoint."""


class RobotSessionLock:
    def __init__(
        self,
        robot_ip: str,
        command_port: int = 6001,
        servo_port: int = 7000,
        lock_root: str | Path | None = None,
    ) -> None:
        ip = str(robot_ip).strip()
        if not ip:
            raise ValueError("robot_ip cannot be empty")
        ports = (int(command_port), int(servo_port))
        if any(not 1 <= port <= 65535 for port in ports):
            raise ValueError("Robot ports must be in 1..65535")
        root = Path(lock_root) if lock_root is not None else (
            Path(__file__).resolve().parents[1] / "logs/robot_sessions"
        )
        self.path = root.expanduser().resolve() / f"{quote(ip, safe='')}_{ports[0]}_{ports[1]}.lock"
        self.endpoint = f"{ip}:{ports[0]}/{ports[1]}"
        self._file = None
        self._mutex = threading.RLock()

    def acquire(self) -> None:
        with self._mutex:
            if self._file is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+", encoding="utf-8")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                handle.close()
                raise RobotSessionBusyError(
                    f"Robot session {self.endpoint} is already owned by another application; "
                    "disconnect it before connecting here."
                ) from exc
            except BaseException:
                handle.close()
                raise
            try:
                handle.seek(0)
                handle.truncate()
                handle.write(f"pid={os.getpid()} endpoint={self.endpoint}\n")
                handle.flush()
            except BaseException:
                handle.close()
                raise
            self._file = handle

    def release(self) -> None:
        with self._mutex:
            handle = self._file
            if handle is not None:
                # Keep the pathname: deleting it could let a contender lock a
                # different inode while another process still owns the old one.
                handle.close()
                self._file = None
