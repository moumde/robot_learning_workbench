"""Read-only Inverse3 and VerseGrip feedback device controller."""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from typing import Any

from gello_cr.control.geometry import (
    _normalize_quaternion,
    _quaternion_to_nrc_abc,
)


@dataclass(frozen=True)
class Inverse3Feedback:
    timestamp: float
    x: float
    y: float
    z: float
    orientation_wxyz: tuple[float, float, float, float] | None
    inverse3_device_id: str
    grip_device_id: str
    grip_type: str
    buttons: tuple[bool, bool, bool]

    @property
    def xyz(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def rpy_rad(self) -> tuple[float, float, float] | None:
        if self.orientation_wxyz is None:
            return None
        return _quaternion_to_nrc_abc(self.orientation_wxyz)


class Inverse3Controller:
    """Read-only Haply Inverse Service client for Inverse3 + VerseGrip."""

    master_type = "inverse3"
    passive = True

    def __init__(
        self,
        uri: str,
        device_id: str = "",
        grip_device_id: str = "",
        feedback_hz: float = 20.0,
        basis: str = "XYZ",
        websocket_factory: Any | None = None,
    ):
        self.uri = str(uri)
        self.device_id = str(device_id)
        self.grip_device_id = str(grip_device_id)
        self.feedback_hz = float(feedback_hz)
        self.basis = str(basis)
        self._websocket_factory = websocket_factory
        self._socket: Any | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._stream_ready = threading.Event()
        self._lock = threading.RLock()
        self._latest: Inverse3Feedback | None = None
        self._error = ""
        self._selected_inverse3_id = ""
        self._selected_grip_id = ""
        self._selected_grip_type = ""

    @property
    def io_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def connected(self) -> bool:
        return self.io_alive and not self.error

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def latest(self) -> Inverse3Feedback | None:
        with self._lock:
            return self._latest

    def connect(self, timeout: float = 4.0) -> Inverse3Feedback:
        if self.connected:
            latest = self.latest()
            if latest is None:
                raise RuntimeError("Inverse3 已连接但没有反馈")
            if latest.orientation_wxyz is not None:
                return latest
            self.close()
        if self._thread is not None:
            self.close()

        self._stop.clear()
        self._stream_ready.clear()
        with self._lock:
            self._latest = None
            self._error = ""
        factory = self._websocket_factory
        if factory is None:
            import websocket

            def factory(uri, connect_timeout):
                return websocket.create_connection(
                    uri,
                    timeout=connect_timeout,
                    enable_multithread=True,
                )

        self._socket = factory(self.uri, float(timeout))
        try:
            first_frame = json.loads(self._socket.recv())
            self._select_devices(first_frame)
            self._update_feedback(first_frame)
        except Exception:
            self._socket.close()
            self._socket = None
            raise
        self._thread = threading.Thread(
            target=self._run,
            name="Inverse3-ReadOnly",
            daemon=True,
        )
        self._thread.start()
        if not self._stream_ready.wait(timeout):
            error = self.error or "Inverse3 只读状态流启动超时"
            self.close()
            raise TimeoutError(error)
        if self.error:
            error = self.error
            self.close()
            raise RuntimeError(error)
        latest = self.latest()
        if latest is None:
            raise RuntimeError("Inverse3 没有有效反馈")
        return latest

    def close(self, hold: bool = False) -> None:
        del hold
        self._stop.set()
        socket = self._socket
        if socket is not None:
            socket.close()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            raise TimeoutError("Inverse3 只读状态线程未能退出")
        self._socket = None
        self._thread = None

    @staticmethod
    def _find_device(frame: dict[str, Any], group: str, device_id: str) -> dict[str, Any] | None:
        devices = frame.get(group, [])
        if device_id:
            return next(
                (device for device in devices if device.get("device_id") == device_id),
                None,
            )
        return devices[0] if devices else None

    @staticmethod
    def _validate_inverse3_status(device: dict[str, Any]) -> None:
        status = device.get("status", {})
        missing = [name for name in ("calibrated", "ready", "started") if not status.get(name)]
        if missing:
            raise RuntimeError("Inverse3 状态未就绪: " + ", ".join(missing))
        if status.get("in_use"):
            raise RuntimeError(
                "Inverse3 正被其他 Haply 控制会话占用；请先退出 GEL/其他力或位置控制演示"
            )
        control_mode = str(
            device.get("state", {}).get("control_mode", device.get("state", {}).get("mode", "idle"))
        )
        if control_mode not in ("", "idle"):
            raise RuntimeError(f"Inverse3 当前 control_mode={control_mode}，只读遥操作要求 idle")

    @staticmethod
    def _validate_grip_status(group: str, device: dict[str, Any]) -> None:
        status = device.get("status", {})
        if not status.get("ready"):
            raise RuntimeError("VerseGrip 状态未就绪: ready")
        if group == "wireless_verse_grip":
            missing = [name for name in ("connected", "awake") if not status.get(name)]
            if missing:
                raise RuntimeError("Wireless VerseGrip 状态未就绪: " + ", ".join(missing))
        elif int(status.get("error", 0)) != 0:
            raise RuntimeError(f"VerseGrip 报错: {status['error']}")

    def _select_devices(self, frame: dict[str, Any]) -> None:
        inverse3 = self._find_device(frame, "inverse3", self.device_id)
        if inverse3 is None:
            target = f" {self.device_id}" if self.device_id else ""
            raise RuntimeError(f"Inverse Service 未发现 Inverse3{target}")
        self._validate_inverse3_status(inverse3)
        self._selected_inverse3_id = str(inverse3["device_id"])
        actual_basis = str(inverse3.get("config", {}).get("basis", {}).get("permutation", ""))
        if actual_basis != self.basis:
            raise RuntimeError(
                f"Inverse3 会话 basis={actual_basis or '--'}，"
                f"配置要求 {self.basis}；禁止在未知坐标映射下跟随"
            )

        candidates: list[tuple[str, dict[str, Any]]] = []
        for group in ("wireless_verse_grip", "verse_grip"):
            candidates.extend(
                (group, grip)
                for grip in frame.get(group, [])
                if not self.grip_device_id or grip.get("device_id") == self.grip_device_id
            )
        if len(candidates) > 1:
            raise RuntimeError("检测到多个 VerseGrip，请在配置中填写唯一 grip_device_id")
        if candidates:
            self._selected_grip_type, grip = candidates[0]
            self._selected_grip_id = str(grip["device_id"])
            self._validate_grip_status(self._selected_grip_type, grip)
            grip_basis = str(grip.get("config", {}).get("basis", {}).get("permutation", ""))
            if grip_basis != self.basis:
                raise RuntimeError(
                    f"VerseGrip 会话 basis={grip_basis or '--'}，"
                    f"配置要求 {self.basis}；禁止混用位置/姿态坐标系"
                )
        else:
            self._selected_grip_type = ""
            self._selected_grip_id = ""

    def _update_feedback(self, frame: dict[str, Any]) -> None:
        inverse3 = self._find_device(frame, "inverse3", self._selected_inverse3_id)
        if inverse3 is None:
            raise RuntimeError("Inverse3 状态流中目标设备消失")
        self._validate_inverse3_status(inverse3)
        position = inverse3["state"]["cursor_position"]
        xyz_m = tuple(float(position[axis]) for axis in "xyz")
        if any(not math.isfinite(value) for value in xyz_m):
            raise RuntimeError("Inverse3 cursor_position 包含非有限数")

        orientation: tuple[float, float, float, float] | None = None
        buttons = (False, False, False)
        if self._selected_grip_type:
            grip = self._find_device(frame, self._selected_grip_type, self._selected_grip_id)
            if grip is None:
                raise RuntimeError("VerseGrip 状态流中目标设备消失")
            self._validate_grip_status(self._selected_grip_type, grip)
            raw_orientation = grip["state"]["orientation"]
            orientation = _normalize_quaternion(tuple(raw_orientation[name] for name in "wxyz"))
            state = grip["state"]
            if self._selected_grip_type == "wireless_verse_grip":
                raw_buttons = state.get("buttons", {})
                buttons = tuple(bool(raw_buttons.get(name, False)) for name in "abc")
            else:
                buttons = (bool(state.get("button", False)), False, False)

        feedback = Inverse3Feedback(
            timestamp=time.monotonic(),
            x=xyz_m[0] * 1000.0,
            y=xyz_m[1] * 1000.0,
            z=xyz_m[2] * 1000.0,
            orientation_wxyz=orientation,
            inverse3_device_id=self._selected_inverse3_id,
            grip_device_id=self._selected_grip_id,
            grip_type=self._selected_grip_type,
            buttons=buttons,
        )
        with self._lock:
            self._latest = feedback

    def _probe_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {
            "inverse3": [
                {
                    "device_id": self._selected_inverse3_id,
                    "commands": {"probe_position": {}},
                }
            ]
        }
        if self._selected_grip_type:
            message[self._selected_grip_type] = [
                {
                    "device_id": self._selected_grip_id,
                    "commands": {"probe_orientation": {}},
                }
            ]
        return message

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._error = message
        self._stream_ready.set()

    def _run(self) -> None:
        period = 1.0 / self.feedback_hz
        next_cycle = time.monotonic()
        try:
            while not self._stop.is_set():
                self._socket.send(
                    json.dumps(
                        self._probe_message(),
                        separators=(",", ":"),
                    )
                )
                frame = json.loads(self._socket.recv())
                self._update_feedback(frame)
                self._stream_ready.set()
                next_cycle += period
                wait_time = next_cycle - time.monotonic()
                if wait_time > 0:
                    self._stop.wait(wait_time)
                else:
                    next_cycle = time.monotonic()
        except Exception as exc:
            if not self._stop.is_set():
                self._set_error(f"Inverse3 只读状态线程异常: {type(exc).__name__}: {exc}")
        finally:
            self._stream_ready.set()
