"""RoArm feedback and serial device controller."""

from __future__ import annotations

import json
import logging
import math
import os
import queue
import select
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RoArmFeedback:
    timestamp: float
    x: float
    y: float
    z: float
    b: float
    s: float
    e: float
    t: float
    torques: tuple[float, float, float, float]

    @property
    def xyz(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def joints(self) -> tuple[float, float, float, float]:
        return (self.b, self.s, self.e, self.t)

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> RoArmFeedback:
        required = ("x", "y", "z", "b", "s", "e", "t")
        if any(key not in value for key in required):
            raise ValueError("RoArm T=1051 反馈字段不完整")
        numbers = [float(value[key]) for key in required]
        if any(not math.isfinite(number) for number in numbers):
            raise ValueError("RoArm 反馈包含非有限数")
        return cls(
            timestamp=time.monotonic(),
            x=numbers[0],
            y=numbers[1],
            z=numbers[2],
            b=numbers[3],
            s=numbers[4],
            e=numbers[5],
            t=numbers[6],
            torques=(
                float(value.get("torB", 0.0)),
                float(value.get("torS", 0.0)),
                float(value.get("torE", 0.0)),
                float(value.get("torH", 0.0)),
            ),
        )


class RoArmSerialController:
    """Long-lived RoArm JSON/UART connection that never toggles DTR/RTS."""

    master_type = "roarm"
    passive = False

    def __init__(self, port: str, baudrate: int = 115200, feedback_hz: float = 20.0):
        self.port = port
        self.baudrate = int(baudrate)
        self.feedback_hz = max(2.0, float(feedback_hz))
        self._fd: int | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._feedback_ready = threading.Event()
        self._commands: queue.Queue[tuple[dict[str, Any], threading.Event | None, list[Any]]] = (
            queue.Queue()
        )
        self._lock = threading.RLock()
        self._latest: RoArmFeedback | None = None
        self._error = ""
        self._boot_detected = False

    @property
    def io_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def connected(self) -> bool:
        return self.io_alive and not self._error

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def latest(self) -> RoArmFeedback | None:
        with self._lock:
            return self._latest

    def connect(self, timeout: float = 4.0) -> RoArmFeedback:
        if self.connected:
            latest = self.latest()
            if latest is None:
                raise RuntimeError("RoArm 已连接但没有反馈")
            return latest
        if self._thread is not None:
            self.close(hold=False)
        if not Path(self.port).exists():
            raise FileNotFoundError(f"RoArm 串口不存在: {self.port}")

        # stty opens the port without manipulating modem-control lines, then
        # persists -hupcl so subsequent low-level opens/closes do not reset ESP32.
        subprocess.run(
            [
                "stty",
                "-F",
                self.port,
                str(self.baudrate),
                "raw",
                "-echo",
                "-hupcl",
                "-crtscts",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self._fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self._stop.clear()
        self._feedback_ready.clear()
        with self._lock:
            self._latest = None
            self._error = ""
            self._boot_detected = False
        self._thread = threading.Thread(target=self._run, name="RoArm-UART", daemon=True)
        self._thread.start()
        if not self._feedback_ready.wait(timeout):
            error = self.error or "RoArm 状态查询超时"
            self.close(hold=False)
            raise TimeoutError(error)
        latest = self.latest()
        if latest is None:
            raise RuntimeError(self.error or "RoArm 没有有效反馈")
        return latest

    def command(self, value: dict[str, Any], wait: bool = False, timeout: float = 1.0) -> None:
        if self._thread is None or not self._thread.is_alive():
            raise RuntimeError("RoArm 尚未连接")
        done = threading.Event() if wait else None
        result: list[Any] = []
        self._commands.put((value, done, result))
        if done is not None:
            if not done.wait(timeout):
                raise TimeoutError("RoArm 命令发送超时")
            if result and isinstance(result[0], BaseException):
                raise RuntimeError(f"RoArm 命令发送失败: {result[0]}")

    def release_torque(self) -> None:
        self.command({"T": 210, "cmd": 0}, wait=True)

    def lock_torque(self) -> None:
        self.command({"T": 210, "cmd": 1}, wait=True)

    def move_joints(self, joints: Sequence[float], duration_s: float = 3.0) -> None:
        if len(joints) != 4:
            raise ValueError("RoArm 目标必须包含 b/s/e/t 四个关节")
        target = [float(value) for value in joints]
        if any(not math.isfinite(value) for value in target):
            raise ValueError("RoArm 目标关节包含非有限数")
        current = self.latest()
        max_delta = max(
            abs(target[index] - current.joints[index]) if current else 0.5 for index in range(4)
        )
        steps_per_second = int(
            math.ceil(max_delta * 4096.0 / (2.0 * math.pi) / max(0.5, duration_s))
        )
        steps_per_second = max(10, min(800, steps_per_second))
        self.command(
            {
                "T": 102,
                "base": target[0],
                "shoulder": target[1],
                "elbow": target[2],
                "hand": target[3],
                "spd": steps_per_second,
                "acc": 10,
            },
            wait=True,
        )

    def hold_current(self) -> None:
        latest = self.latest()
        if latest is not None:
            self.move_joints(latest.joints, duration_s=1.0)
            time.sleep(0.1)
        self.lock_torque()

    def wait_until_joints(
        self,
        target: Sequence[float],
        tolerance_rad: float = 0.04,
        timeout: float = 15.0,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            latest = self.latest()
            if (
                latest
                and max(abs(a - b) for a, b in zip(latest.joints, target, strict=True))
                <= tolerance_rad
            ):
                return True
            if self.error:
                return False
            time.sleep(0.05)
        return False

    def close(self, hold: bool = True) -> None:
        if hold and self._thread is not None and self._thread.is_alive():
            try:
                self.hold_current()
            except Exception:
                logging.getLogger("workbench.hardware").exception("RoArm hold before close failed")
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise TimeoutError("RoArm feedback thread did not stop")
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
        self._fd = None
        self._thread = None

    def _write_json(self, value: dict[str, Any]) -> None:
        if self._fd is None:
            raise RuntimeError("RoArm 串口已关闭")
        payload = (json.dumps(value, separators=(",", ":")) + "\n").encode("ascii")
        offset = 0
        while offset < len(payload):
            offset += os.write(self._fd, payload[offset:])

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._error = message
        self._feedback_ready.set()

    def _run(self) -> None:
        pending = b""
        next_query = time.monotonic()
        period = 1.0 / self.feedback_hz
        try:
            while not self._stop.is_set():
                for _ in range(20):
                    try:
                        value, done, result = self._commands.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        self._write_json(value)
                    except Exception as exc:
                        result.append(exc)
                        self._set_error(str(exc))
                    finally:
                        if done is not None:
                            done.set()

                now = time.monotonic()
                if now >= next_query:
                    self._write_json({"T": 105})
                    next_query = now + period

                readable, _, _ = select.select(
                    [self._fd], [], [], min(0.02, max(0.0, next_query - now))
                )
                if not readable:
                    continue
                try:
                    chunk = os.read(self._fd, 4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    continue
                pending += chunk
                while b"\n" in pending:
                    raw, pending = pending.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if any(
                        marker in line
                        for marker in (
                            "ServoCtrl init",
                            "Bus servos status check",
                            "Moving BASE_JOINT",
                            "Moving SHOULDER_JOINT",
                        )
                    ):
                        self._boot_detected = True
                        self._set_error("检测到 RoArm ESP32 重启/初始化，已禁止跟随")
                        continue
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if value.get("T") != 1051:
                        continue
                    feedback = RoArmFeedback.from_json(value)
                    with self._lock:
                        self._latest = feedback
                    self._feedback_ready.set()
        except Exception as exc:
            self._set_error(f"RoArm 串口线程异常: {type(exc).__name__}: {exc}")
