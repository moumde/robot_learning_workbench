"""Pure joint-safety primitives for GELLO -> CR3A teleoperation.

This module contains no hardware I/O, Qt, threads, timers, or vendor SDK calls.
The active following loop uses these safety constraints:

- command-step limit in radians;
- CR3A tracking-error limit in radians;
- GELLO leader-speed limit with per-joint consecutive-violation counting.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

JOINT_COUNT = 6
_MIN_SPEED_PERIOD_S = 1e-3


def _six_finite(values: Sequence[float], name: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if len(result) != JOINT_COUNT:
        raise ValueError(f"{name} must contain exactly {JOINT_COUNT} values")
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _positive_finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return result


@dataclass(frozen=True, slots=True)
class JointSafetyViolation:
    """One max-joint safety violation.

    `joint_number` is operator-facing one-based J1..J6.
    """

    joint_number: int
    value: float
    limit: float


@dataclass(frozen=True, slots=True)
class LeaderSpeedSample:
    """Leader-speed calculation result for one GELLO feedback update."""

    speed_rad_s: tuple[float, ...]
    violation_counts: tuple[int, ...]
    violation: JointSafetyViolation | None


def command_step_rad(
    target_deg: Sequence[float],
    previous_target_deg: Sequence[float],
) -> tuple[float, ...]:
    """Absolute per-joint command step, preserving legacy degree->rad math."""

    target = _six_finite(target_deg, "target_deg")
    previous = _six_finite(previous_target_deg, "previous_target_deg")
    return tuple(
        abs(math.radians(current - last)) for current, last in zip(target, previous, strict=True)
    )


def tracking_error_rad(
    target_deg: Sequence[float],
    actual_deg: Sequence[float],
) -> tuple[float, ...]:
    """Absolute per-joint target-vs-feedback error in radians."""

    target = _six_finite(target_deg, "target_deg")
    actual = _six_finite(actual_deg, "actual_deg")
    return tuple(
        abs(math.radians(commanded - feedback))
        for commanded, feedback in zip(target, actual, strict=True)
    )


def max_command_step_violation(
    target_deg: Sequence[float],
    previous_target_deg: Sequence[float],
    limit_rad: float,
) -> JointSafetyViolation | None:
    """Return the largest command-step violation, or None.

    Legacy semantics use strict `>`; a value exactly equal to the limit passes.
    """

    limit = _positive_finite(limit_rad, "command step limit")
    values = command_step_rad(target_deg, previous_target_deg)
    index = max(range(JOINT_COUNT), key=values.__getitem__)
    value = values[index]
    if value > limit:
        return JointSafetyViolation(
            joint_number=index + 1,
            value=value,
            limit=limit,
        )
    return None


def max_tracking_error_violation(
    target_deg: Sequence[float],
    actual_deg: Sequence[float],
    limit_rad: float,
) -> JointSafetyViolation | None:
    """Return the largest CR3A tracking-error violation, or None."""

    limit = _positive_finite(limit_rad, "tracking error limit")
    values = tracking_error_rad(target_deg, actual_deg)
    index = max(range(JOINT_COUNT), key=values.__getitem__)
    value = values[index]
    if value > limit:
        return JointSafetyViolation(
            joint_number=index + 1,
            value=value,
            limit=limit,
        )
    return None


class LeaderSpeedViolationCounter:
    """Stateful consecutive GELLO leader-speed violation counter.

    This preserves the current runtime behavior:

    - speed = wrapped/scaled leader delta / max(1 ms, sample period);
    - each joint has an independent consecutive-over-limit counter;
    - a safe sample resets that joint's counter to zero;
    - the threshold comparison is strict `>`;
    - a stop is triggered when the largest count reaches `violation_cycles`.

    The speed limit and required cycle count are passed on every update so the
    legacy runtime's live-config behavior can be preserved in Phase 3.2b.
    """

    def __init__(self) -> None:
        self._counts = [0] * JOINT_COUNT

    @property
    def counts(self) -> tuple[int, ...]:
        return tuple(self._counts)

    def reset(self) -> None:
        self._counts[:] = [0] * JOINT_COUNT

    def update(
        self,
        leader_delta_rad: Sequence[float],
        sample_period_s: float,
        speed_limit_rad_s: float,
        violation_cycles: int,
    ) -> LeaderSpeedSample:
        delta = _six_finite(leader_delta_rad, "leader_delta_rad")
        if any(value < 0.0 for value in delta):
            raise ValueError("leader_delta_rad must contain absolute non-negative values")

        period = float(sample_period_s)
        if not math.isfinite(period) or period < 0.0:
            raise ValueError("sample_period_s must be finite and non-negative")
        period = max(_MIN_SPEED_PERIOD_S, period)

        limit = _positive_finite(speed_limit_rad_s, "speed limit")
        cycles = int(violation_cycles)
        if cycles <= 0:
            raise ValueError("violation_cycles must be positive")

        speed = tuple(value / period for value in delta)

        for index, value in enumerate(speed):
            if value > limit:
                self._counts[index] += 1
            else:
                self._counts[index] = 0

        max_index = max(range(JOINT_COUNT), key=self._counts.__getitem__)
        violation = None
        if self._counts[max_index] >= cycles:
            violation = JointSafetyViolation(
                joint_number=max_index + 1,
                value=speed[max_index],
                limit=limit,
            )

        return LeaderSpeedSample(
            speed_rad_s=speed,
            violation_counts=tuple(self._counts),
            violation=violation,
        )
