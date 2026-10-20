"""Pure GELLO J7 -> O6 mapping helpers.

Preserves both validated runtime policies:
- joint mode: binary open/grasp selection at threshold 0.5;
- Cartesian GELLO modes: continuous open->closed interpolation + deadband.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

O6_MOTOR_COUNT = 6


def _six_uint8(values: Sequence[float], name: str) -> tuple[int, ...]:
    converted = tuple(int(round(float(value))) for value in values)
    if len(converted) != O6_MOTOR_COUNT:
        raise ValueError(f"{name} must contain exactly {O6_MOTOR_COUNT} values")
    if any(value < 0 or value > 255 for value in converted):
        raise ValueError(f"{name} values must be in 0..255")
    return converted


def binary_o6_action(
    gripper_fraction: float,
    *,
    threshold: float = 0.5,
    open_action: str = "张开手",
    closed_action: str = "抓取",
) -> str:
    fraction = float(gripper_fraction)
    threshold_value = float(threshold)
    if not math.isfinite(fraction):
        raise ValueError("gripper_fraction must be finite")
    if not math.isfinite(threshold_value):
        raise ValueError("threshold must be finite")
    if not open_action or not closed_action:
        raise ValueError("O6 action names cannot be empty")
    return closed_action if fraction >= threshold_value else open_action


def interpolate_o6_target(
    gripper_fraction: float,
    open_positions: Sequence[float],
    closed_positions: Sequence[float],
) -> tuple[int, ...]:
    fraction = float(gripper_fraction)
    if not math.isfinite(fraction):
        raise ValueError("gripper_fraction must be finite")
    fraction = max(0.0, min(1.0, fraction))

    opened = _six_uint8(open_positions, "open_positions")
    closed = _six_uint8(closed_positions, "closed_positions")

    return tuple(
        int(round(float(a) + fraction * (float(b) - float(a))))
        for a, b in zip(opened, closed, strict=True)
    )


def should_send_o6_target(
    target: Sequence[float],
    previous_target: Sequence[float] | None,
    command_deadband: int,
) -> bool:
    current = _six_uint8(target, "target")
    deadband = int(command_deadband)
    if deadband < 0:
        raise ValueError("command_deadband must be non-negative")
    if previous_target is None:
        return True

    previous = _six_uint8(previous_target, "previous_target")
    return max(abs(a - b) for a, b in zip(current, previous, strict=True)) >= deadband
