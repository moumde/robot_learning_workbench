"""LinkerHand O6 device adapter.

The O6 SDK is blocking and must have exactly one owner thread.  This adapter
contains that ownership boundary and exposes thread-safe snapshots/commands to
the rest of the application.

The implementation intentionally preserves the proven legacy behavior:
- position polling every 0.2 s by default;
- fault polling every 0.8 s by default;
- profile writes are serialized on the O6 worker thread;
- target writes are de-duplicated;
- single-motor recovery refuses fault codes other than 0/1 and overwrites the
  old target before restoring speed/torque.
"""

from __future__ import annotations

import importlib.util
import math
import os
import queue
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teleop.gello_cr.core.contracts import HandSnapshot
from teleop.gello_cr.support.paths import workbench_root

HandFactory = Callable[..., Any]

O6_MOTOR_NAMES = (
    "大拇指弯曲",
    "大拇指侧摆",
    "食指弯曲",
    "中指弯曲",
    "无名指弯曲",
    "小拇指弯曲",
)

O6_FAULT_NAMES = {
    0: "正常",
    1: "电流过载",
    2: "温度过高",
    3: "编码器错误",
    4: "过压/欠压",
}


def _six_uint8(values: Sequence[Any], name: str) -> tuple[int, int, int, int, int, int]:
    if len(values) != 6:
        raise ValueError(f"{name} 必须包含 6 个数值")
    converted = tuple(int(round(float(value))) for value in values)
    if any(value < 0 or value > 255 for value in converted):
        raise ValueError(f"{name} 必须在 0..255 范围内")
    return converted  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class O6Config:
    port: str
    sdk_root: str | None
    hand_id: int = 0x27
    baudrate: int = 115200
    position_poll_s: float = 0.2
    fault_poll_s: float = 0.8
    loop_sleep_s: float = 0.01

    def __post_init__(self) -> None:
        if not self.port.strip():
            raise ValueError("O6 port cannot be empty")
        if not 0 <= int(self.hand_id) <= 255:
            raise ValueError("O6 hand_id must be in 0..255")
        if int(self.baudrate) <= 0:
            raise ValueError("O6 baudrate must be positive")
        for name, value in (
            ("position_poll_s", self.position_poll_s),
            ("fault_poll_s", self.fault_poll_s),
            ("loop_sleep_s", self.loop_sleep_s),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"O6 {name} must be a positive finite value")


@dataclass(slots=True)
class _RecoveryRequest:
    motor_index: int
    speed: int
    torque: int
    done: threading.Event
    cancelled: threading.Event
    result: dict[str, Any] | None = None
    error: str = ""


class O6Device:
    """Single-owner background adapter for LinkerHand O6 RS485."""

    def __init__(
        self,
        config: O6Config,
        *,
        hand_factory: HandFactory | None = None,
    ) -> None:
        self.config = config
        self._hand_factory = hand_factory
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self._latest: HandSnapshot | None = None
        self._position_timestamp = 0.0
        self._desired_target: tuple[int, ...] | None = None
        self._last_sent_target: tuple[int, ...] | None = None
        self._pending_profile: tuple[tuple[int, ...], tuple[int, ...]] | None = None
        self._recovery_requests: queue.Queue[_RecoveryRequest] = queue.Queue()
        self._error = ""
        self._phase = "未启动"

    @property
    def connected(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and not self.error

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    @property
    def phase(self) -> str:
        with self._lock:
            return self._phase

    @property
    def last_sent_target(self) -> tuple[int, ...] | None:
        with self._lock:
            return self._last_sent_target

    @property
    def latest_position_timestamp(self) -> float:
        """Timestamp of the last position read, preserving legacy semantics."""
        with self._lock:
            return self._position_timestamp

    def latest(self) -> HandSnapshot | None:
        with self._lock:
            return self._latest

    def connect(self, timeout: float = 10.0) -> HandSnapshot:
        if timeout <= 0:
            raise ValueError("O6 connect timeout must be positive")

        if self.connected:
            latest = self.latest()
            if latest is None:
                raise RuntimeError("O6 已连接但没有反馈")
            return latest

        if self._thread is not None:
            self.close()
            if self._thread is not None:
                raise RuntimeError(
                    f"O6 上一次通信线程仍未退出（阶段={self.phase}），"
                    "请断开 O6 USB 后重插并重启程序"
                )

        port = Path(self.config.port)
        if not port.exists():
            raise FileNotFoundError(f"O6 串口不存在: {self.config.port}")
        if not os.access(port, os.R_OK | os.W_OK):
            raise PermissionError(f"O6 串口无读写权限: {self.config.port}")

        self._stop.clear()
        self._ready.clear()
        with self._lock:
            self._latest = None
            self._position_timestamp = 0.0
            self._desired_target = None
            self._last_sent_target = None
            self._pending_profile = None
            self._recovery_requests = queue.Queue()
            self._error = ""
            self._phase = "启动通信线程"

        self._thread = threading.Thread(
            target=self._run,
            name="O6-RS485",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(float(timeout)):
            phase = self.phase
            error = self.error or f"O6 初始化超时 {timeout:.0f}s（阶段={phase}）"
            self.close()
            raise TimeoutError(error)

        if self.error:
            error = self.error
            self.close()
            raise RuntimeError(error)

        latest = self.latest()
        if latest is None:
            self.close()
            raise RuntimeError("O6 没有有效反馈")
        return latest

    def set_profile(self, speed: Sequence[Any], torque: Sequence[Any]) -> None:
        profile = (
            _six_uint8(speed, "O6 速度"),
            _six_uint8(torque, "O6 力矩"),
        )
        with self._lock:
            self._pending_profile = profile

    def set_target(self, target: Sequence[Any]) -> None:
        converted = _six_uint8(target, "O6 目标")
        with self._lock:
            self._desired_target = converted

    def set_positions(self, positions: tuple[int, ...]) -> None:
        """HandDevice contract alias."""
        self.set_target(positions)

    def hold_current(self) -> None:
        latest = self.latest()
        if latest is not None:
            self.set_target(latest.positions)

    def wait_until_position(
        self,
        target: Sequence[Any],
        tolerance: int = 6,
        timeout: float = 15.0,
        stop_event: threading.Event | None = None,
    ) -> bool:
        converted = _six_uint8(target, "O6 目标")
        started = time.monotonic()
        deadline = started + float(timeout)
        while time.monotonic() < deadline:
            if self.error or (stop_event is not None and stop_event.is_set()):
                return False
            with self._lock:
                latest = self._latest
                position_at = self._position_timestamp
            if latest is not None:
                if any(latest.faults):
                    return False
                # Completion requires a position read during this wait. A
                # cached matching target must not hide a blocked/dead I/O worker.
                if position_at >= started and max(
                    abs(a - b) for a, b in zip(latest.positions, converted, strict=True)
                ) <= int(tolerance):
                    return not self.error and not (stop_event is not None and stop_event.is_set())
            time.sleep(0.05)
        return False

    def recover_motor(
        self,
        motor_number: int,
        speed: Any,
        torque: Any,
        timeout: float = 4.0,
        stop_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        number = int(motor_number)
        if number < 1 or number > len(O6_MOTOR_NAMES):
            raise ValueError("O6 电机编号必须为 1～6")
        speed_value = int(speed)
        torque_value = int(torque)
        if not 1 <= speed_value <= 255:
            raise ValueError("O6 恢复速度必须为 1～255")
        if not 1 <= torque_value <= 255:
            raise ValueError("O6 恢复力矩必须为 1～255")
        if not self.connected:
            raise RuntimeError("O6 未连接")

        request = _RecoveryRequest(
            motor_index=number - 1,
            speed=speed_value,
            torque=torque_value,
            done=threading.Event(),
            cancelled=threading.Event(),
        )
        self._recovery_requests.put(request)

        deadline = time.monotonic() + float(timeout)
        while not request.done.wait(0.05):
            if stop_event is not None and stop_event.is_set():
                request.cancelled.set()
                raise RuntimeError(f"O6 {number} 号电机恢复已被软件紧急停止")
            if time.monotonic() >= deadline:
                request.cancelled.set()
                raise TimeoutError(f"O6 {number} 号电机恢复命令超时（阶段={self.phase}）")

        if request.error:
            raise RuntimeError(request.error)
        if request.result is None:
            raise RuntimeError("O6 电机恢复没有返回结果")
        return request.result

    def close(self) -> None:
        self._stop.set()
        self._fail_pending_recoveries("O6 正在关闭，恢复操作已取消")

        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        if thread is not None and thread.is_alive():
            with self._lock:
                if not self._error:
                    self._error = f"O6 通信线程无法退出（阶段={self._phase}）"
            raise TimeoutError(self._error)

        self._thread = None

    def _load_hand_factory(self) -> HandFactory:
        root = Path(self.config.sdk_root).expanduser().resolve() if self.config.sdk_root else (
            workbench_root() / "vendor/actuator/linkerhand-python-sdk/LinkerHand"
        )
        path = root / "core/rs485/linker_hand_o6_rs485.py"
        if not path.is_file():
            raise FileNotFoundError(f"O6 SDK 文件不存在: {path}")
        # The workbench owns top-level `core`; import this self-contained driver
        # by file so the SDK cannot replace or extend that package.
        try:
            spec = importlib.util.spec_from_file_location("_gello_cr_linkerhand_o6_rs485", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:
            raise RuntimeError(
                "无法导入 LinkerHandO6RS485；请安装 LinkerHand SDK 或配置 o6.sdk_root"
            ) from exc
        return module.LinkerHandO6RS485

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._error = message
        self._ready.set()

    def _set_snapshot(
        self,
        *,
        positions: tuple[int, ...] | None = None,
        faults: tuple[int, ...] | None = None,
        position_read: bool = False,
    ) -> None:
        now = time.monotonic()
        with self._lock:
            current = self._latest
            if positions is None:
                positions = current.positions if current is not None else None
            if faults is None:
                faults = current.faults if current is not None else None
            if positions is None or faults is None:
                return
            if len(positions) != 6 or len(faults) != 6:
                raise RuntimeError("O6 反馈必须包含 6 个位置值和 6 个故障码")
            self._latest = HandSnapshot(
                timestamp=now,
                positions=tuple(int(value) for value in positions),
                faults=tuple(int(value) for value in faults),
            )
            if position_read:
                self._position_timestamp = now

    def _fail_pending_recoveries(self, message: str) -> None:
        while True:
            try:
                request = self._recovery_requests.get_nowait()
            except queue.Empty:
                return
            request.error = message
            request.done.set()

    def _process_recovery(self, hand: Any, request: _RecoveryRequest) -> None:
        index = request.motor_index
        number = index + 1
        try:
            with self._lock:
                self._phase = f"恢复 O6 {number} 号电机"

            before_position = tuple(int(value) for value in hand.get_state())
            before_fault = tuple(int(value) for value in hand.get_fault())
            if len(before_position) != 6 or len(before_fault) != 6:
                raise RuntimeError("O6 恢复前反馈维度错误")

            fault_code = before_fault[index]
            if fault_code not in (0, 1):
                fault_name = O6_FAULT_NAMES.get(fault_code, "未知故障")
                raise RuntimeError(
                    f"O6 {number} 号电机为 {fault_name}（故障码 {fault_code}），禁止软件重新上力"
                )

            position_setters = (
                hand.set_thumb_pitch,
                hand.set_thumb_yaw,
                hand.set_index_pitch,
                hand.set_middle_pitch,
                hand.set_ring_pitch,
                hand.set_little_pitch,
            )
            speed_setters = (
                hand.set_thumb_speed,
                hand.set_thumb_yaw_speed,
                hand.set_index_speed,
                hand.set_middle_speed,
                hand.set_ring_speed,
                hand.set_little_speed,
            )
            torque_setters = (
                hand.set_thumb_torque,
                hand.set_thumb_yaw_torque,
                hand.set_index_torque,
                hand.set_middle_torque,
                hand.set_ring_torque,
                hand.set_little_torque,
            )

            if request.cancelled.is_set():
                raise RuntimeError("恢复请求已取消")
            position_setters[index](before_position[index])

            if request.cancelled.is_set():
                raise RuntimeError("恢复请求已取消")
            speed_setters[index](request.speed)

            if request.cancelled.is_set():
                raise RuntimeError("恢复请求已取消")
            torque_setters[index](request.torque)

            time.sleep(0.2)

            if request.cancelled.is_set():
                raise RuntimeError("恢复请求已取消")

            after_position = tuple(int(value) for value in hand.get_state())
            after_fault = tuple(int(value) for value in hand.get_fault())
            self._set_snapshot(
                positions=after_position,
                faults=after_fault,
                position_read=True,
            )

            with self._lock:
                self._desired_target = after_position
                self._last_sent_target = after_position

            request.result = {
                "motor_number": number,
                "motor_name": O6_MOTOR_NAMES[index],
                "position_before": before_position[index],
                "position_after": after_position[index],
                "fault_before": before_fault,
                "fault_after": after_fault,
            }
        except Exception as exc:
            request.error = f"O6 {number} 号电机恢复失败: {type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                if self._phase != "异常":
                    self._phase = "运行中"
            request.done.set()

    def _run(self) -> None:
        hand: Any = None
        try:
            with self._lock:
                self._phase = "加载 O6 SDK"
            factory = self._hand_factory or self._load_hand_factory()

            with self._lock:
                self._phase = "打开 RS485 串口"
            hand = factory(
                hand_id=int(self.config.hand_id),
                modbus_port=self.config.port,
                baudrate=int(self.config.baudrate),
            )

            with self._lock:
                self._phase = "读取 O6 位置"
            position = tuple(int(value) for value in hand.get_state())

            with self._lock:
                self._phase = "读取 O6 故障码"
            fault = tuple(int(value) for value in hand.get_fault())

            self._set_snapshot(
                positions=position,
                faults=fault,
                position_read=True,
            )
            with self._lock:
                self._phase = "运行中"
            self._ready.set()

            next_position = time.monotonic() + self.config.position_poll_s
            next_fault = time.monotonic() + self.config.fault_poll_s

            while not self._stop.is_set():
                try:
                    recovery = self._recovery_requests.get_nowait()
                except queue.Empty:
                    recovery = None
                if recovery is not None:
                    self._process_recovery(hand, recovery)

                with self._lock:
                    profile = self._pending_profile
                    self._pending_profile = None
                    target = self._desired_target

                if profile is not None:
                    hand.set_speed(list(profile[0]))
                    hand.set_torque(list(profile[1]))

                if target is not None:
                    with self._lock:
                        last_target = self._last_sent_target
                    if target != last_target:
                        hand.set_joint_positions(list(target))
                        with self._lock:
                            self._last_sent_target = target

                now = time.monotonic()
                if now >= next_position:
                    position = tuple(int(value) for value in hand.get_state())
                    self._set_snapshot(positions=position, position_read=True)
                    next_position = time.monotonic() + self.config.position_poll_s

                if now >= next_fault:
                    fault = tuple(int(value) for value in hand.get_fault())
                    self._set_snapshot(faults=fault)
                    next_fault = time.monotonic() + self.config.fault_poll_s

                time.sleep(self.config.loop_sleep_s)

        except Exception as exc:
            with self._lock:
                self._phase = "异常"
            self._set_error(f"O6 通信线程异常: {type(exc).__name__}: {exc}")
        finally:
            self._fail_pending_recoveries(self.error or "O6 通信线程已退出")
            if hand is not None:
                try:
                    hand.close()
                except Exception as exc:
                    self._set_error(f"O6 关闭失败: {exc}")
            with self._lock:
                if self._phase != "异常":
                    self._phase = "已关闭"


class O6Controller:
    """Expose O6 feedback and commands to motion orchestration."""

    def __init__(
        self,
        port: str,
        sdk_root: Path | str,
        hand_id: int = 0x27,
        baudrate: int = 115200,
    ):
        self.port = str(port)
        self.sdk_root = str(sdk_root)
        self.hand_id = int(hand_id)
        self.baudrate = int(baudrate)

        self._device = O6Device(
            O6Config(
                port=self.port,
                sdk_root=self.sdk_root,
                hand_id=self.hand_id,
                baudrate=self.baudrate,
            )
        )

    @property
    def connected(self) -> bool:
        return self._device.connected

    @property
    def error(self) -> str:
        return self._device.error

    @property
    def phase(self) -> str:
        return self._device.phase

    def latest(
        self,
    ) -> tuple[
        tuple[int, ...] | None,
        tuple[int, ...] | None,
        float,
    ]:
        snapshot = self._device.latest()
        if snapshot is None:
            return None, None, self._device.latest_position_timestamp
        return (
            tuple(int(value) for value in snapshot.positions),
            tuple(int(value) for value in snapshot.faults),
            float(self._device.latest_position_timestamp),
        )

    @property
    def last_sent_target(self) -> tuple[int, ...] | None:
        return self._device.last_sent_target

    def connect(self, timeout: float = 10.0) -> tuple[int, ...]:
        snapshot = self._device.connect(timeout=float(timeout))
        return tuple(int(value) for value in snapshot.positions)

    def set_profile(self, speed: Sequence[Any], torque: Sequence[Any]) -> None:
        self._device.set_profile(speed, torque)

    def set_target(self, target: Sequence[Any]) -> None:
        self._device.set_target(target)

    def hold_current(self) -> None:
        self._device.hold_current()

    def recover_motor(
        self,
        motor_number: int,
        speed: Any,
        torque: Any,
        timeout: float = 4.0,
        stop_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        return self._device.recover_motor(
            motor_number,
            speed,
            torque,
            timeout=float(timeout),
            stop_event=stop_event,
        )

    def wait_until_position(
        self,
        target: Sequence[Any],
        tolerance: int = 6,
        timeout: float = 15.0,
        stop_event: threading.Event | None = None,
    ) -> bool:
        return self._device.wait_until_position(
            target,
            tolerance=int(tolerance),
            timeout=float(timeout),
            stop_event=stop_event,
        )

    def close(self) -> None:
        self._device.close()
