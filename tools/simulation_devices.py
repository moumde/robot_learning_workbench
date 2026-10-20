"""In-memory devices for exercising the real teleoperation application.

No constructor opens hardware or starts a worker.  Start ``SimulationRig`` and
then use the application's normal connection and enable operations.  One worker
samples master/hand feedback at 100 Hz and RGB frames at 30 Hz using actual
``time.monotonic()`` timestamps.  ``motion_enabled`` is initially false so HOME
and idle checks receive a stationary master; enabling it adds slow, small joint
and gripper movement.  Disabling it freezes the current master pose.

Taking an endpoint offline latches its connection closed.  Bringing it online
does not reconnect it or resume a command stream.  Old snapshots remain old.
The NRC implementation uses degrees and a seventh placeholder axis, just like
the vendor SDK.  Its simple reversible Cartesian mapping is a simulation only;
these devices provide no evidence about physical kinematics or robot dynamics.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Sequence
from typing import Any

import numpy as np

from core.hardware.realsense import RealSenseRgbConfig
from core.workbench.core.contracts import CameraSnapshot, HandSnapshot
from teleop.gello_cr.device import GelloFeedback


def _six_bytes(values: Sequence[Any]) -> tuple[int, ...]:
    converted = tuple(int(round(float(value))) for value in values)
    if len(converted) != 6 or any(value < 0 or value > 255 for value in converted):
        raise ValueError("O6 values must contain six numbers in 0..255")
    return converted


class _MoveCmd:
    pass


class SimulatedNrcApi:
    """The SDK subset consumed by Cr3aDevice/NrcRobotSession, without sockets."""

    PosType_data = 99
    MoveCmd = _MoveCmd

    def __init__(self, rig: SimulationRig) -> None:
        self._rig = rig
        self._next_fd = 10
        self._endpoints: dict[int, dict[str, Any]] = {}
        self.state = 1
        self.mode = 0
        self.callback: Any = None
        self.connect_count = 0
        self.disconnect_count = 0
        self.send_count = 0
        self.movej_count = 0
        self.stop_count = 0
        self.power_on_count = 0
        self.last_send_timestamp: float | None = None
        self.last_target_deg: tuple[float, ...] | None = None
        self._joints = [0.0, -45.0, 90.0, 0.0, 45.0, 0.0, 0.0]
        self._target = self._joints.copy()
        self._servo_open = False
        self._moving = False
        self._anchor_joints = self._joints.copy()
        self._anchor_tcp = [320.0, 0.0, 350.0, 0.0, 0.0, 0.0, 0.0]

    @staticmethod
    def VectorDouble(size: int | None = None) -> list[float]:
        return [] if size is None else [0.0] * int(size)

    @property
    def joint_position(self) -> list[float]:
        with self._rig._lock:
            return self._joints.copy()

    @property
    def connection_status(self) -> dict[int, int]:
        with self._rig._lock:
            return {fd: 0 if item["connected"] else -2 for fd, item in self._endpoints.items()}

    @property
    def endpoints(self) -> dict[int, dict[str, Any]]:
        with self._rig._lock:
            return {fd: dict(item) for fd, item in self._endpoints.items()}

    def _require_connection(self, fd: int) -> None:
        if self.get_connection_status(fd) != 0:
            raise ConnectionError(f"Simulated NRC endpoint {fd} is disconnected")

    def connect_robot(self, ip: str, port: str) -> int:
        with self._rig._lock:
            if not self._rig._running or not self._rig._robot_online:
                raise ConnectionError("Simulated NRC is offline")
            self._next_fd += 1
            fd = self._next_fd
            self._endpoints[fd] = {"ip": str(ip), "port": str(port), "connected": True}
            self.connect_count += 1
            return fd

    def disconnect_robot(self, fd: int) -> int:
        with self._rig._lock:
            endpoint = self._endpoints.get(int(fd))
            if endpoint is not None:
                endpoint["connected"] = False
            self.disconnect_count += 1
            self._halt()
            return 0

    def get_connection_status(self, fd: int) -> int:
        with self._rig._lock:
            endpoint = self._endpoints.get(int(fd))
            return 0 if (
                self._rig._running and self._rig._robot_online
                and endpoint is not None and endpoint["connected"]
            ) else -2

    def set_receive_error_or_warnning_message_callback(self, fd: int, callback: Any) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            self.callback = callback
            return 0

    def get_servo_state_robot(self, fd: int, robot_num: int, status: int) -> tuple[int, int]:
        del robot_num, status
        with self._rig._lock:
            self._require_connection(fd)
            return 0, self.state

    def get_current_mode_robot(self, fd: int, robot_num: int, mode: int) -> tuple[int, int]:
        del robot_num, mode
        with self._rig._lock:
            self._require_connection(fd)
            return 0, self.mode

    def set_current_mode_robot(self, fd: int, robot_num: int, mode: int) -> int:
        del robot_num
        with self._rig._lock:
            self._require_connection(fd)
            self.mode = int(mode)
            return 0

    def get_robot_running_state_robot(self, fd: int, robot_num: int, state: int) -> tuple[int, int]:
        del robot_num, state
        with self._rig._lock:
            self._require_connection(fd)
            return 0, 2 if self._moving else 0

    def get_current_position(self, fd: int, coord: int, output: list[float]) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            output.extend(self._joints if int(coord) == 0 else self._forward(self._joints))
            return 0

    def clear_error_robot(self, fd: int, robot_num: int) -> int:
        return self.set_servo_state_robot(fd, robot_num, 1)

    def set_servo_state_robot(self, fd: int, robot_num: int, state: int) -> int:
        del robot_num
        with self._rig._lock:
            self._require_connection(fd)
            self.state = int(state)
            if self.state != 3:
                self._halt()
            return 0

    def set_servo_poweron_robot(self, fd: int, robot_num: int) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            self.power_on_count += 1
            return self.set_servo_state_robot(fd, robot_num, 3)

    def set_servo_poweroff_robot(self, fd: int, robot_num: int) -> int:
        return self.set_servo_state_robot(fd, robot_num, 1)

    def enable_servo_position_motion_control(self, fd: int, enabled: bool) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            if not enabled:
                self._halt()
            return 0

    def open_servoJ(self, fd: int, vmax: Any, amax: Any, jmax: Any) -> int:
        del vmax, amax, jmax
        with self._rig._lock:
            self._require_connection(fd)
            if self.state != 3:
                raise RuntimeError("Simulated NRC servo is not powered on")
            self._servo_open = True
            return 0

    def _set_target(self, joints: Sequence[float]) -> None:
        target = [float(value) for value in joints]
        if len(target) != 7 or any(not math.isfinite(value) for value in target):
            raise ValueError("NRC target must contain seven finite degree values")
        self._target = target
        self._moving = True
        self.send_count += 1
        self.last_send_timestamp = time.monotonic()
        self.last_target_deg = tuple(target)

    def set_servoJ_pos(self, fd: int, joints: Sequence[float]) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            if self.state != 3 or not self._servo_open:
                raise RuntimeError("Simulated NRC servoJ is not open and enabled")
            self._set_target(joints)
            return 0

    def robot_movej(self, fd: int, command: Any) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            if self.state != 3:
                raise RuntimeError("Simulated NRC MoveJ requires power on")
            self._set_target(command.targetPosValue)
            self.movej_count += 1
            return 0

    def _halt(self) -> None:
        self._servo_open = False
        self._moving = False
        self._target = self._joints.copy()

    def stop_servoJ(self, fd: int) -> int:
        # The local model can always stop, including after simulated link loss.
        del fd
        with self._rig._lock:
            self.stop_count += 1
            self._halt()
            return 0

    def queue_motion_stop_not_power_off(self, fd: int) -> int:
        return self.stop_servoJ(fd)

    def _forward(self, joints: Sequence[float]) -> list[float]:
        delta = [
            math.radians(float(a) - b)
            for a, b in zip(joints, self._anchor_joints, strict=True)
        ]
        return [
            self._anchor_tcp[index] + delta[index] * (100.0 if index < 3 else 1.0)
            for index in range(6)
        ] + [0.0]

    def get_origin_coord_to_target_coord(
        self, fd: int, origin: int, target: Sequence[float], coord: int, output: list[float]
    ) -> int:
        with self._rig._lock:
            self._require_connection(fd)
            if int(origin) == 0 and int(coord) == 1:
                values = self._forward(target)
            elif int(origin) == 1 and int(coord) == 0:
                values = [
                    self._anchor_joints[index] + math.degrees(
                        (float(target[index]) - self._anchor_tcp[index])
                        / (100.0 if index < 3 else 1.0)
                    )
                    for index in range(6)
                ] + [0.0]
            else:
                raise ValueError("Simulation supports joint/TCP conversions only")
            output[:] = values
            return 0

    def _sample(self, dt: float) -> None:
        if not self._moving or self.state != 3 or not self._rig._robot_online:
            return
        limit = 60.0 * dt
        self._joints = [
            value + max(-limit, min(limit, target - value))
            for value, target in zip(self._joints, self._target, strict=True)
        ]
        self._moving = any(
            abs(a - b) > 1e-8 for a, b in zip(self._joints, self._target, strict=True)
        )


class _SampledDevice:
    def __init__(self, rig: SimulationRig, channel: str) -> None:
        self._rig = rig
        self._channel = channel
        self._connected = False
        self._error = ""
        self._latest: Any = None
        self.connect_count = 0
        self.close_count = 0

    @property
    def connected(self) -> bool:
        with self._rig._lock:
            return self._connected and self._rig._running

    @property
    def error(self) -> str:
        with self._rig._lock:
            return self._error

    def _connect(self, timeout: float) -> Any:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Connect timeout must be positive and finite")
        with self._rig._condition:
            if not self._rig._running or not getattr(self._rig, f"_{self._channel}_online"):
                raise ConnectionError(f"Simulated {self._channel} is offline")
            if self._connected and self._latest is not None:
                return self._latest
            connected_at = time.monotonic()
            deadline = connected_at + timeout
            self._connected = True
            self._error = ""
            self.connect_count += 1
            while self._latest is None or self._latest.timestamp < connected_at:
                if not self._connected or not self._rig._running:
                    raise ConnectionError(f"Simulated {self._channel} disconnected during connect")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._connected = False
                    raise TimeoutError(f"Simulated {self._channel} produced no sample")
                self._rig._condition.wait(remaining)
            return self._latest

    def close(self) -> None:
        with self._rig._condition:
            self._connected = False
            self.close_count += 1
            self._rig._condition.notify_all()

    def _offline(self) -> None:
        if self._connected:
            self._connected = False
            self._error = f"Simulated {self._channel} link lost"


class SimulatedMaster(_SampledDevice):
    master_type = "gello"
    passive = True

    def __init__(self, rig: SimulationRig, **kwargs: Any) -> None:
        super().__init__(rig, "master")
        self.config = dict(kwargs)
        self.port = str(kwargs.get("port", "simulation://gello"))

    @property
    def io_alive(self) -> bool:
        return self.connected

    def latest(self) -> GelloFeedback | None:
        with self._rig._lock:
            return self._latest

    def connect(self, timeout: float = 5.0) -> GelloFeedback:
        return self._connect(float(timeout))

    def close(self, hold: bool = False) -> None:
        del hold
        super().close()

    def _sample(self, now: float) -> None:
        self._latest = GelloFeedback(now, self._rig._master_values())


class SimulatedHand(_SampledDevice):
    def __init__(
        self, rig: SimulationRig, port: str, sdk_root: Any, hand_id: int, baudrate: int
    ) -> None:
        super().__init__(rig, "hand")
        self.port, self.sdk_root = str(port), str(sdk_root)
        self.hand_id, self.baudrate = int(hand_id), int(baudrate)
        self._position = [157.0, 95.0, 175.0, 0.0, 0.0, 0.0]
        self._target = tuple(int(value) for value in self._position)
        self.last_sent_target: tuple[int, ...] | None = None
        self.target_count = 0
        self.hold_count = 0
        self.profile: tuple[tuple[int, ...], tuple[int, ...]] | None = None

    @property
    def phase(self) -> str:
        return "运行" if self.connected else "已关闭"

    def latest(self) -> tuple[tuple[int, ...] | None, tuple[int, ...] | None, float]:
        with self._rig._lock:
            if self._latest is None:
                return None, None, 0.0
            return self._latest.positions, self._latest.faults, self._latest.timestamp

    def connect(self, timeout: float = 10.0) -> tuple[int, ...]:
        return self._connect(float(timeout)).positions

    def set_profile(self, speed: Sequence[Any], torque: Sequence[Any]) -> None:
        with self._rig._lock:
            if not self.connected:
                raise ConnectionError("Simulated O6 is disconnected")
            self.profile = _six_bytes(speed), _six_bytes(torque)

    def set_target(self, target: Sequence[Any]) -> None:
        with self._rig._lock:
            if not self.connected:
                raise ConnectionError("Simulated O6 is disconnected")
            self._target = _six_bytes(target)
            self.last_sent_target = self._target
            self.target_count += 1

    def hold_current(self) -> None:
        with self._rig._lock:
            self._target = tuple(int(round(value)) for value in self._position)
            self.last_sent_target = self._target
            self.hold_count += 1

    def wait_until_position(
        self, target: Sequence[Any], tolerance: int = 6, timeout: float = 15.0,
        stop_event: threading.Event | None = None,
    ) -> bool:
        expected = _six_bytes(target)
        deadline = time.monotonic() + float(timeout)
        with self._rig._condition:
            while time.monotonic() < deadline:
                if stop_event is not None and stop_event.is_set():
                    return False
                if not self.connected or self.error:
                    raise ConnectionError(self.error or "Simulated O6 is disconnected")
                if self._latest is not None and max(
                    abs(a - b) for a, b in zip(self._latest.positions, expected, strict=True)
                ) <= int(tolerance):
                    return True
                self._rig._condition.wait(min(0.02, max(0.0, deadline - time.monotonic())))
            return False

    def _offline(self) -> None:
        self.hold_current()
        super()._offline()

    def close(self) -> None:
        self.hold_current()
        super().close()

    def _sample(self, now: float, dt: float) -> None:
        self._position = [
            value + max(-200.0 * dt, min(200.0 * dt, target - value))
            for value, target in zip(self._position, self._target, strict=True)
        ]
        self._latest = HandSnapshot(
            now, tuple(int(round(value)) for value in self._position), (0,) * 6
        )


class SimulatedCamera(_SampledDevice):
    def __init__(self, rig: SimulationRig, config: RealSenseRgbConfig) -> None:
        super().__init__(rig, "cameras")
        self.config = config
        self.frame_count = 0
        self._next_frame = 0.0
        y, x = np.indices((config.height, config.width))
        self._pattern = np.stack((x % 256, y % 256, (x + y) % 256), axis=-1).astype(np.uint8)

    def connect(self, timeout: float = 5.0) -> CameraSnapshot:
        self._connect(float(timeout))
        snapshot = self.latest()
        assert snapshot is not None
        return snapshot

    def latest(self) -> CameraSnapshot | None:
        with self._rig._lock:
            sample = self._latest
            if sample is None:
                return None
            return CameraSnapshot(
                sample.timestamp, sample.serial, sample.image_rgb.copy(),
                sample.width, sample.height,
            )

    def _sample(self, now: float) -> None:
        if now < self._next_frame:
            return
        image = np.add(self._pattern, np.uint8(self.frame_count % 256), dtype=np.uint8)
        self._latest = CameraSnapshot(
            now, self.config.serial, image, self.config.width, self.config.height
        )
        self.frame_count += 1
        # Advance the schedule without producing synthetic catch-up samples.
        self._next_frame += 1.0 / self.config.fps
        if self._next_frame <= now:
            self._next_frame = now + 1.0 / self.config.fps


class SimulationRig:
    """Explicit lifecycle and fault switches for all simulated endpoints."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._robot_online = self._master_online = self._hand_online = self._cameras_online = True
        self._motion_enabled = False
        self._motion_time = 0.0
        self.sample_count = 0
        self.last_sample_timestamp: float | None = None
        self.api = SimulatedNrcApi(self)
        self.masters: list[SimulatedMaster] = []
        self.hands: list[SimulatedHand] = []
        self.cameras: list[SimulatedCamera] = []

    def master_constructor(self, **kwargs: Any) -> SimulatedMaster:
        with self._lock:
            master = SimulatedMaster(self, **kwargs)
            self.masters.append(master)
            return master

    def hand_constructor(
        self, port: str, sdk_root: Any, hand_id: int = 0x27, baudrate: int = 115200
    ) -> SimulatedHand:
        with self._lock:
            hand = SimulatedHand(self, port, sdk_root, hand_id, baudrate)
            self.hands.append(hand)
            return hand

    def camera_constructor(self, config: RealSenseRgbConfig) -> SimulatedCamera:
        with self._lock:
            camera = SimulatedCamera(self, config)
            self.cameras.append(camera)
            return camera

    def _get_online(self, channel: str) -> bool:
        with self._lock:
            return bool(getattr(self, f"_{channel}_online"))

    def _set_online(self, channel: str, value: bool) -> None:
        with self._condition:
            setattr(self, f"_{channel}_online", bool(value))
            if not value:
                if channel == "robot":
                    for endpoint in self.api._endpoints.values():
                        endpoint["connected"] = False
                    self.api._halt()
                else:
                    devices = {"master": self.masters, "hand": self.hands, "cameras": self.cameras}
                    for device in devices[channel]:
                        device._offline()
            self._condition.notify_all()

    robot_online = property(
        lambda self: self._get_online("robot"), lambda self, v: self._set_online("robot", v)
    )
    master_online = property(
        lambda self: self._get_online("master"), lambda self, v: self._set_online("master", v)
    )
    hand_online = property(
        lambda self: self._get_online("hand"), lambda self, v: self._set_online("hand", v)
    )
    cameras_online = property(
        lambda self: self._get_online("cameras"), lambda self, v: self._set_online("cameras", v)
    )

    @property
    def motion_enabled(self) -> bool:
        with self._lock:
            return self._motion_enabled

    @motion_enabled.setter
    def motion_enabled(self, value: bool) -> None:
        with self._lock:
            self._motion_enabled = bool(value)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _master_values(self) -> tuple[float, ...]:
        phase = self._motion_time * 2.0 * math.pi * 0.08
        base = (0.0, -0.4, 0.8, 0.0, 0.4, 0.0)
        arm = tuple(
            value + 0.025 * (math.sin(phase + index * 0.4) - math.sin(index * 0.4))
            for index, value in enumerate(base)
        )
        return (*arm, 0.5 + 0.3 * math.sin(phase * 0.75))

    def start(self) -> None:
        with self._condition:
            if self._running:
                return
            self._stop.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._run, name="Teleop-Simulation-100Hz", daemon=True
            )
            self._thread.start()

    def _run(self) -> None:
        previous = time.monotonic()
        next_cycle = previous
        while not self._stop.is_set():
            now = time.monotonic()
            dt = now - previous
            previous = now
            with self._condition:
                if (
                    self._motion_enabled and self._master_online
                    and any(m._connected for m in self.masters)
                ):
                    self._motion_time += dt
                self.api._sample(dt)
                for master in self.masters:
                    if master._connected and self._master_online:
                        master._sample(now)
                for hand in self.hands:
                    if hand._connected and self._hand_online:
                        hand._sample(now, dt)
                for camera in self.cameras:
                    if camera._connected and self._cameras_online:
                        camera._sample(now)
                self.sample_count += 1
                self.last_sample_timestamp = now
                self._condition.notify_all()
            next_cycle += 0.01
            delay = next_cycle - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            else:
                next_cycle = time.monotonic()

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(2.0)
            if thread.is_alive():
                raise TimeoutError("Teleop simulation worker did not exit")
        with self._condition:
            self._running = False
            self._motion_enabled = False
            self._thread = None
            self.api._halt()
            for endpoint in self.api._endpoints.values():
                endpoint["connected"] = False
            for device in (*self.masters, *self.hands, *self.cameras):
                device._connected = False
            self._condition.notify_all()

    def __enter__(self) -> SimulationRig:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
