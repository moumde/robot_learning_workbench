"""Pure GELLO -> CR3A relative joint mapping.

This module contains no hardware I/O, timing, threading, Qt, or NRC SDK calls.
It captures the already-validated joint-mode mapping semantics from the legacy
TeleopEngine so they can be tested independently before the runtime loop is
bridged to V2 control code.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

JOINT_COUNT = 6


def _six_finite(values: Sequence[float], name: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if len(result) != JOINT_COUNT:
        raise ValueError(f"{name} must contain exactly {JOINT_COUNT} values")
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def wrapped_delta_rad(current_rad: float, origin_rad: float) -> float:
    """Return the shortest signed angular delta in radians."""
    current = float(current_rad)
    origin = float(origin_rad)
    if not math.isfinite(current) or not math.isfinite(origin):
        raise ValueError("angle values must be finite")
    delta = current - origin
    return math.atan2(math.sin(delta), math.cos(delta))


@dataclass(frozen=True, slots=True)
class RelativeJointMapper:
    """Map GELLO J1-J6 relative motion onto a CR3A startup pose.

    `locked_joints` uses operator-facing one-based numbering J1..J6.
    """

    joint_scale: float = 1.0
    locked_joints: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        scale = float(self.joint_scale)
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("joint_scale must be positive and finite")
        normalized = tuple(int(value) for value in self.locked_joints)
        if len(set(normalized)) != len(normalized):
            raise ValueError("locked_joints must not contain duplicates")
        if any(value < 1 or value > JOINT_COUNT for value in normalized):
            raise ValueError("locked_joints must contain only J1..J6")
        object.__setattr__(self, "joint_scale", scale)
        object.__setattr__(self, "locked_joints", normalized)

    @property
    def locked_indices(self) -> tuple[int, ...]:
        return tuple(value - 1 for value in self.locked_joints)

    def relative_rad(
        self,
        leader_rad: Sequence[float],
        leader_origin_rad: Sequence[float],
    ) -> tuple[float, ...]:
        leader = _six_finite(leader_rad, "leader_rad")
        origin = _six_finite(leader_origin_rad, "leader_origin_rad")
        locked = set(self.locked_indices)
        return tuple(
            0.0 if index in locked else self.joint_scale * wrapped_delta_rad(current, zero)
            for index, (current, zero) in enumerate(zip(leader, origin, strict=True))
        )

    def target_deg(
        self,
        leader_rad: Sequence[float],
        leader_origin_rad: Sequence[float],
        slave_origin_deg: Sequence[float],
    ) -> tuple[float, ...]:
        """Return six CR3A targets in native NRC degrees."""
        slave_origin = _six_finite(slave_origin_deg, "slave_origin_deg")
        relative = self.relative_rad(leader_rad, leader_origin_rad)
        return tuple(
            base_deg + math.degrees(delta_rad)
            for base_deg, delta_rad in zip(slave_origin, relative, strict=True)
        )

    def leader_delta_rad(
        self,
        leader_rad: Sequence[float],
        previous_leader_rad: Sequence[float],
    ) -> tuple[float, ...]:
        """Return scaled absolute wrapped motion for leader-speed checks."""
        leader = _six_finite(leader_rad, "leader_rad")
        previous = _six_finite(previous_leader_rad, "previous_leader_rad")
        locked = set(self.locked_indices)
        return tuple(
            0.0 if index in locked else self.joint_scale * abs(wrapped_delta_rad(current, last))
            for index, (current, last) in enumerate(zip(leader, previous, strict=True))
        )
