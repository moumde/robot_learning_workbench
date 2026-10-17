"""The sole bridge from validated motion targets to native robot commands."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from .types import JointTarget, MotionError, TcpTarget


class MotionExecutor:
    def __init__(self, robot_provider: Callable[[], Any]) -> None:
        self._robot_provider = robot_provider

    def _robot(self) -> Any:
        robot = self._robot_provider()
        if robot is None:
            raise MotionError("Robot is not connected")
        return robot

    @staticmethod
    def _joint_native(target: JointTarget) -> list[float]:
        return [math.degrees(value) for value in target.positions_rad] + [target.auxiliary_axis_deg]

    def servo_joint(self, target: JointTarget) -> bool:
        return self._robot().send_servoj(self._joint_native(target))

    def move_joint(
        self,
        target: JointTarget,
        velocity: float,
        acceleration: float,
        deceleration: float | None = None,
    ) -> None:
        self._robot().movej(
            self._joint_native(target),
            velocity,
            acceleration,
            acceleration if deceleration is None else deceleration,
        )

    def move_tcp(
        self,
        target: TcpTarget,
        velocity: float,
        acceleration: float,
        deceleration: float | None = None,
    ) -> None:
        native = [value * 1000.0 for value in target.xyz_m]
        native.extend(target.rpy_rad)
        native.append(target.auxiliary_axis)
        self._robot().movel(
            native,
            velocity,
            acceleration,
            acceleration if deceleration is None else deceleration,
        )

    def open_servo(self, vmax: float, amax: float, jmax: float) -> None:
        self._robot().open_servoj(vmax, amax, jmax)

    def stop(self) -> None:
        robot = self._robot_provider()
        if robot is not None:
            robot.stop_motion()

    def joint_position_rad(self) -> tuple[float, ...] | None:
        robot = self._robot_provider()
        read_position = getattr(robot, "joint_position", None)
        if read_position is None:
            return None
        return JointTarget.from_degrees(read_position()).positions_rad
