"""Configuration-driven validation for motion targets, without hardware I/O."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from .types import JointTarget, MotionMode, MotionSafetyError, TcpTarget


def _finite(value: object, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise MotionSafetyError(f"{name} must be finite") from error
    if not math.isfinite(number):
        raise MotionSafetyError(f"{name} must be finite")
    return number


def _vector(values: Sequence[float], count: int, name: str) -> tuple[float, ...]:
    if len(values) != count:
        raise MotionSafetyError(f"{name} must contain exactly {count} values")
    return tuple(_finite(value, name) for value in values)


def _section(config: Mapping[str, object], name: str) -> Mapping[str, object]:
    section = config.get(name, {})
    if not isinstance(section, Mapping):
        raise MotionSafetyError(f"{name} configuration must be a mapping")
    return section


def _positive_limit(value: object, name: str) -> float | None:
    if value is None:
        return None
    limit = _finite(value, name)
    if limit <= 0.0:
        raise MotionSafetyError(f"{name} must be positive")
    return limit


def _check_bounds(values: tuple[float, ...], limits: object, name: str) -> None:
    if limits is None:
        return
    if not isinstance(limits, Sequence) or len(limits) != len(values):
        raise MotionSafetyError(f"{name} must contain exactly {len(values)} pairs")
    for index, (value, pair) in enumerate(zip(values, limits, strict=True), start=1):
        if not isinstance(pair, Sequence) or len(pair) != 2:
            raise MotionSafetyError(f"{name} entry {index} must be a pair")
        lower = _finite(pair[0], name)
        upper = _finite(pair[1], name)
        if lower > upper:
            raise MotionSafetyError(f"{name} entry {index} lower bound exceeds upper bound")
        if value < lower or value > upper:
            raise MotionSafetyError(
                f"{name} entry {index} target {value} outside [{lower}, {upper}]"
            )


class MotionSafety:
    """Validate targets using the latest optional motion/robot configuration.

    Joint and workspace bounds are inclusive. Delta and velocity limits apply
    only to joint servo commands with a previous target; no model limits are
    assumed when the configuration does not supply them.
    """

    def __init__(
        self,
        config_provider: Callable[[], Mapping[str, object]] | None = None,
    ) -> None:
        self._config_provider = config_provider if config_provider is not None else lambda: {}

    def validate_joint_target(
        self,
        target: JointTarget,
        previous: JointTarget | None = None,
        mode: MotionMode = MotionMode.SERVO_JOINT,
        *,
        validate_velocity: bool = True,
    ) -> None:
        positions = _vector(target.positions_rad, 6, "joint positions_rad")
        timestamp = _finite(target.timestamp, "target timestamp")
        _finite(target.auxiliary_axis_deg, "auxiliary_axis_deg")

        config = self._config_provider()
        motion = _section(config, "motion")
        _check_bounds(positions, motion.get("joint_limits_rad"), "joint_limits_rad")
        if mode is not MotionMode.SERVO_JOINT:
            return

        robot = _section(config, "robot")
        delta_limit = _positive_limit(
            motion.get("max_command_delta_rad", robot.get("safety_max_command_step_rad")),
            "max_command_delta_rad",
        )
        velocity_limit = _positive_limit(
            motion.get("max_target_velocity_rad_s"), "max_target_velocity_rad_s"
        )
        if previous is None:
            return

        previous_positions = _vector(previous.positions_rad, 6, "previous joint positions_rad")
        previous_timestamp = _finite(previous.timestamp, "previous timestamp")
        _finite(previous.auxiliary_axis_deg, "previous auxiliary_axis_deg")
        deltas = tuple(
            abs(current - prior)
            for current, prior in zip(positions, previous_positions, strict=True)
        )
        if delta_limit is not None and any(delta > delta_limit for delta in deltas):
            raise MotionSafetyError(f"joint command delta exceeds {delta_limit} rad")
        if velocity_limit is not None and validate_velocity:
            period = timestamp - previous_timestamp
            if period <= 0.0:
                raise MotionSafetyError("target timestamp must increase for velocity validation")
            if any(delta / period > velocity_limit for delta in deltas):
                raise MotionSafetyError(f"joint target velocity exceeds {velocity_limit} rad/s")

    def validate_tcp_target(self, target: TcpTarget) -> None:
        xyz = _vector(target.xyz_m, 3, "TCP xyz_m")
        _vector(target.rpy_rad, 3, "TCP rpy_rad")
        _finite(target.timestamp, "target timestamp")
        _finite(target.auxiliary_axis, "auxiliary_axis")

        motion = _section(self._config_provider(), "motion")
        _check_bounds(xyz, motion.get("workspace_limits_m"), "workspace_limits_m")
