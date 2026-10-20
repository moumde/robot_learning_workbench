"""Legacy degree/seven-axis view of the parent's single NRC connection owner."""
from __future__ import annotations

import math
import time
from collections.abc import Sequence
from typing import Any

from core.hardware.servo_state import ServoTransition as NrcServoTransition
from core.workbench.core.servo_limits import ServoLimit, servo_limit_vector
from core.workbench.errors import HardwareError
from vendor.nrc_interface.interface import (
    NRC_RESULT_NAMES as NRC_RESULT_NAMES,
)
from vendor.nrc_interface.interface import (
    NRC_SERVO_STATE_NAMES as NRC_SERVO_STATE_NAMES,
)
from vendor.nrc_interface.interface import (
    CR3Interface,
    NRCError,
)

__all__ = ["NrcRobotSession", "NrcServoTransition", "NRC_RESULT_NAMES", "NRC_SERVO_STATE_NAMES"]


class NrcRobotSession:
    """Compatibility units and MoveJ scheduling; the parent owns every SDK operation."""

    def __init__(self, api: Any = None, command_fd: int = -1, servo_fd: int = -1,
                 robot_num: int = 1, motion_mode: str = "movej", movej_velocity: float = 10.0,
                 movej_acc: float = 20.0, movej_dec: float = 20.0,
                 movej_period_s: float = 0.1, movej_low_latency: bool = False,
                 *, backend: CR3Interface | None = None) -> None:
        if not 1 <= int(robot_num) <= 4:
            raise ValueError("NRC robot_num 必须是 1～4 的整数")
        if motion_mode not in ("servoj", "movej"):
            raise ValueError("motion_mode 必须是 servoj 或 movej")
        if float(movej_period_s) <= 0:
            raise ValueError("movej_period_s 必须大于 0")
        self.backend = backend if backend is not None else CR3Interface.from_connected(
            api, command_fd, servo_fd, robot_num=robot_num)
        self.motion_mode = motion_mode
        self.movej_velocity, self.movej_acc, self.movej_dec = (
            float(movej_velocity), float(movej_acc), float(movej_dec))
        self.movej_period_s = float(movej_period_s)
        self.movej_low_latency = bool(movej_low_latency)
        self._last_movej_send_time: float | None = None
        self._controller_job_warning = ""

    @property
    def api(self):
        return self.backend.api

    @property
    def command_fd(self):
        return self.backend.command_fd

    @property
    def servo_fd(self):
        return self.backend.servo_fd

    @property
    def robot_num(self):
        return self.backend.robot_num

    @property
    def lock(self):
        return self.backend._lock

    @property
    def servoj_open(self):
        return self.backend.servo_active

    @property
    def controller_job_warning(self):
        with self.lock:
            return self._controller_job_warning

    def record_controller_message(self, message_type, message, code):
        del message_type
        if int(code) == 4098:
            with self.lock:
                self._controller_job_warning = f"code=4098: {message}"

    _result_ok = staticmethod(CR3Interface._result_ok)
    _result_description = staticmethod(CR3Interface._result_description)
    servo_state_name = staticmethod(CR3Interface.servo_state_name)

    @staticmethod
    def _invoke(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NRCError as exc:
            raise HardwareError(str(exc)) from exc

    def wait_connections_ready(self, timeout=10.0):
        return self._invoke(self.backend.wait_connections_ready, timeout)

    def connection_statuses(self):
        return self.backend.connection_statuses()

    def connections_ready(self):
        return all(value == 0 for value in self.connection_statuses().values())

    def servo_state(self):
        return self._invoke(self.backend.get_servo_state)

    def current_mode(self):
        return self._invoke(self.backend.get_current_mode)

    def power_on(self, timeout=10.0):
        return self._invoke(self.backend.power_on_verified, timeout)

    def power_off(self, timeout=10.0):
        return self._invoke(self.backend.power_off_verified, timeout)

    def clear_servo_error(self, timeout=10.0):
        return self.power_on(timeout)

    def running_state(self):
        return self._invoke(self.backend.running_state)

    def wait_until_motion_stopped(self, timeout, stop_event=None, stable_samples=3):
        return self._invoke(self.backend.wait_until_motion_stopped, timeout, stop_event, stable_samples)

    def joint_position(self):
        values = self._invoke(self.backend.get_joint_positions, include_external_axis=True)
        joints = [math.degrees(v) for v in values[:6]]
        for index, value in enumerate(joints):
            wrapped = value - 360.0 * round(value / 360.0)
            if abs(wrapped) < 1.0:
                joints[index] = wrapped
        return joints + [values[6]]

    def tcp_position(self):
        return self._invoke(self.backend.get_tcp_pose)

    def position(self, coord):
        return self.joint_position() if int(coord) == 0 else self.tcp_position()

    def open_servoj(self, vmax: ServoLimit, amax: ServoLimit, jmax: ServoLimit):
        if self.motion_mode == "movej":
            return
        limits = [servo_limit_vector(value, name) for value, name in (
            (vmax, "vmax"), (amax, "amax"), (jmax, "jmax"))]
        self._invoke(self.backend.open_servoj, vmax=limits[0], amax=limits[1], jmax=limits[2],
                     enable_position_control=True)

    def stop_servoj(self):
        if self.motion_mode != "movej":
            self._invoke(self.backend.close_servoj)

    def inverse_kinematics(self, tcp: Sequence[float]):
        if len(tcp) != 7:
            raise ValueError("CR5 TCP 目标必须包含 7 个值")
        values = self._invoke(self.backend.convert_pose_to_joints, tcp, include_external_axis=True)
        return [math.degrees(v) for v in values[:6]] + [values[6]]

    def forward_kinematics(self, joints: Sequence[float]):
        if len(joints) != 7:
            raise ValueError("CR5 正运动学输入必须包含 7 个关节值")
        return self._invoke(self.backend.forward_kinematics,
                            [math.radians(v) for v in joints[:6]], external_axis=joints[6])

    def clear_movej_busy_if_stopped(self):
        with self.lock:
            if self._controller_job_warning:
                if self.running_state() != 0:
                    return False
                if self.servo_state() != 3:
                    raise HardwareError("CR5 等待 MoveJ 空闲时退出运行状态")
                self._controller_job_warning = ""
            return True

    def send_servoj(self, joints: Sequence[float]) -> bool:
        if len(joints) != 7:
            raise ValueError("CR5 servoJ 目标必须包含 7 个值")
        if self.motion_mode == "movej":
            now = time.monotonic()
            if self._last_movej_send_time is not None and now - self._last_movej_send_time < self.movej_period_s:
                return False
            with self.lock:
                if self._controller_job_warning:
                    if not self.movej_low_latency:
                        self.clear_movej_busy_if_stopped()
                    return False
            self._invoke(self.backend.move_joint_positions,
                         [math.radians(v) for v in joints[:6]], external_axis=joints[6],
                         velocity=self.movej_velocity, acc=self.movej_acc, dec=self.movej_dec,
                         stop_servoj=False)
            self._last_movej_send_time = now
        else:
            self._invoke(self.backend.send_joint_positions,
                         [math.radians(v) for v in joints[:6]], external_axis=joints[6])
        return True

    def movej(self, joints, velocity, acc, dec):
        if len(joints) != 7:
            raise ValueError("CR5 MoveJ 目标必须包含 7 个值")
        self._invoke(self.backend.move_joint_positions,
                     [math.radians(v) for v in joints[:6]], external_axis=joints[6],
                     velocity=velocity, acc=acc, dec=dec)

    def movel(self, tcp, velocity, acc, dec):
        self._invoke(self.backend.move_cartesian_pose, tcp, velocity=velocity, acc=acc, dec=dec)

    def wait_until_joints(self, target, tolerance_deg, timeout):
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            current = self.joint_position()
            if max(abs(a - b) for a, b in zip(current[:6], target[:6], strict=True)) <= tolerance_deg:
                return True
            time.sleep(0.1)
        return False

    def stop_motion(self):
        try:
            self._invoke(self.backend.stop_motion)
        finally:
            self._last_movej_send_time = None
