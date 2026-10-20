"""Hardware contracts used by the V2 application layer."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class JointState:
    timestamp: float
    names: tuple[str, ...]
    positions_rad: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.names:
            raise ValueError("joint names cannot be empty")
        if len(self.names) != len(self.positions_rad):
            raise ValueError("joint names and positions must have the same length")
        if len(set(self.names)) != len(self.names):
            raise ValueError("joint names must be unique")
        if not math.isfinite(self.timestamp):
            raise ValueError("joint timestamp must be finite")
        if any(not math.isfinite(value) for value in self.positions_rad):
            raise ValueError("joint positions must be finite")


@dataclass(frozen=True, slots=True)
class TcpPose:
    xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]

    def __post_init__(self) -> None:
        values = (*self.xyz_m, *self.rpy_rad)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("TCP pose must contain finite values")


@dataclass(frozen=True, slots=True)
class MasterSnapshot:
    timestamp: float
    joints: JointState
    auxiliary: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RobotSnapshot:
    timestamp: float
    joints: JointState
    tcp: TcpPose | None = None
    servo_state: int | None = None


@dataclass(frozen=True, slots=True)
class CameraSnapshot:
    timestamp: float
    serial: str
    image_rgb: object
    width: int
    height: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.timestamp):
            raise ValueError("camera timestamp must be finite")
        if not self.serial:
            raise ValueError("camera serial cannot be empty")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("camera width/height must be positive")
        shape = getattr(self.image_rgb, "shape", None)
        if shape != (self.height, self.width, 3):
            raise ValueError("camera RGB image shape must match (height, width, 3)")


@dataclass(frozen=True, slots=True)
class HandSnapshot:
    timestamp: float
    positions: tuple[int, ...]
    faults: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.positions) != len(self.faults):
            raise ValueError("hand positions and faults must have the same length")


@runtime_checkable
class CameraDevice(Protocol):
    @property
    def connected(self) -> bool: ...

    def connect(self, timeout: float = 5.0) -> CameraSnapshot: ...

    def latest(self) -> CameraSnapshot | None: ...

    def close(self) -> None: ...


@runtime_checkable
class MasterDevice(Protocol):
    @property
    def connected(self) -> bool: ...

    def connect(self, timeout: float = 5.0) -> MasterSnapshot: ...

    def latest(self) -> MasterSnapshot | None: ...

    def close(self) -> None: ...


@runtime_checkable
class RobotDevice(Protocol):
    @property
    def connected(self) -> bool: ...

    def connect(self, timeout: float = 10.0) -> RobotSnapshot: ...

    def power_on(self, timeout: float = 10.0) -> None: ...

    def power_off(self, timeout: float = 10.0) -> None: ...

    def start_joint_servo(self) -> None: ...

    def send_joint_target(self, joints_rad: tuple[float, ...]) -> None: ...

    def stop_motion(self) -> None: ...

    def latest(self) -> RobotSnapshot | None: ...

    def close(self) -> None: ...


@runtime_checkable
class HandDevice(Protocol):
    @property
    def connected(self) -> bool: ...

    def connect(self, timeout: float = 5.0) -> HandSnapshot: ...

    def set_positions(self, positions: tuple[int, ...]) -> None: ...

    def latest(self) -> HandSnapshot | None: ...

    def close(self) -> None: ...
