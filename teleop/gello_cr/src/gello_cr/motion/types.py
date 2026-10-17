"""Robot-independent targets and ownership state for all motion sources."""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from gello_cr.errors import MotionError as MotionError


class MotionBusyError(MotionError):
    """Another source owns the robot and cannot be preempted."""


class MotionPreempted(MotionError):
    """A worker tried to use a lease that no longer owns the robot."""


class MotionSafetyError(MotionError):
    """A target violates the configured final motion boundary."""


class MotionSource(Enum):
    TELEOP = auto()
    POLICY = auto()
    REPLAY = auto()
    POINT_MOVE = auto()
    HOME = auto()


MOTION_PRIORITY = {
    MotionSource.TELEOP: 10,
    MotionSource.POLICY: 10,
    MotionSource.REPLAY: 20,
    MotionSource.POINT_MOVE: 30,
    MotionSource.HOME: 40,
}


class MotionMode(Enum):
    IDLE = auto()
    SERVO_JOINT = auto()
    JOINT_MOVE = auto()
    TCP_MOVE = auto()


@dataclass(frozen=True)
class JointTarget:
    positions_rad: tuple[float, ...]
    timestamp: float
    auxiliary_axis_deg: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions_rad", tuple(self.positions_rad))

    @classmethod
    def from_degrees(cls, native: Sequence[float], timestamp: float | None = None) -> JointTarget:
        if len(native) not in (6, 7):
            raise MotionSafetyError(
                "Joint target must contain six joints and an optional auxiliary axis"
            )
        return cls(
            tuple(math.radians(value) for value in native[:6]),
            time.monotonic() if timestamp is None else timestamp,
            native[6] if len(native) == 7 else 0.0,
        )


@dataclass(frozen=True)
class TcpTarget:
    xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]
    timestamp: float
    auxiliary_axis: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "xyz_m", tuple(self.xyz_m))
        object.__setattr__(self, "rpy_rad", tuple(self.rpy_rad))

    @classmethod
    def from_native(cls, native: Sequence[float], timestamp: float | None = None) -> TcpTarget:
        if len(native) not in (6, 7):
            raise MotionSafetyError(
                "TCP target must contain six coordinates and an optional auxiliary axis"
            )
        return cls(
            tuple(value / 1000.0 for value in native[:3]),
            tuple(native[3:6]),
            time.monotonic() if timestamp is None else timestamp,
            native[6] if len(native) == 7 else 0.0,
        )


@dataclass(frozen=True)
class MotionStatus:
    source: MotionSource | None = None
    mode: MotionMode = MotionMode.IDLE
    running: bool = False
    started_at: float | None = None
    last_command_at: float | None = None
    error: str | None = None
