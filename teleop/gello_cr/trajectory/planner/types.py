"""Planning requests and robot constraints, expressed in radians/metres/seconds."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from teleop.gello_cr.support.errors import PlanningError as PlanningError
from teleop.gello_cr.trajectory.model import Trajectory


@dataclass(frozen=True)
class TcpPose:
    """Position plus intrinsic XYZ Euler radians (the existing NRC ABC convention)."""

    position_m: tuple[float, float, float]
    orientation_rpy_rad: tuple[float, float, float]

    @classmethod
    def from_vector(cls, values):
        if len(values) != 6:
            raise ValueError("TCP pose requires six values")
        return cls(tuple(values[:3]), tuple(values[3:]))

    def vector(self):
        return tuple(self.position_m) + tuple(self.orientation_rpy_rad)


class KinematicsProvider(Protocol):
    def forward(self, joint_rad: tuple[float, ...]) -> TcpPose: ...
    def inverse(self, pose: TcpPose, seed_joint_rad=None) -> list[tuple[float, ...]]: ...


class TcpPlanningMode(StrEnum):
    PTP = "ptp"
    LINEAR = "linear"


@dataclass(frozen=True)
class JointMoveRequest:
    target_rad: tuple[float, ...]
    max_velocity: float = 0.5
    max_acceleration: float = 1.0
    name: str = "Joint PTP"


@dataclass(frozen=True)
class TcpMoveRequest:
    target_pose: TcpPose
    mode: TcpPlanningMode = TcpPlanningMode.PTP
    max_linear_velocity: float = 0.03
    max_angular_velocity: float = 0.1
    speed_scale: float = 1.0
    name: str = "TCP Move"


@dataclass(frozen=True)
class Waypoint:
    pose: TcpPose
    motion_type: TcpPlanningMode = TcpPlanningMode.PTP
    speed_scale: float = 1.0
    hold_time_s: float = 0.0


@dataclass(frozen=True)
class WaypointRequest:
    waypoints: tuple[Waypoint, ...]
    max_linear_velocity: float = 0.03
    max_angular_velocity: float = 0.1
    speed_scale: float = 1.0
    name: str = "Waypoints"


@dataclass(frozen=True)
class RobotModel:
    joint_count: int = 6
    joint_limits_rad: tuple[tuple[float, float], ...] | None = None
    workspace_limits_m: tuple[tuple[float, float], ...] | None = None
    max_joint_velocity: tuple[float, ...] = (0.5,) * 6
    max_joint_acceleration: tuple[float, ...] = (1.0,) * 6
    max_command_delta_rad: float = math.radians(20)
    robot_type: str = "cr3a"


@dataclass(frozen=True)
class PlannerSettings:
    sample_hz: float = 100.0
    tcp_position_step_m: float = 0.002
    tcp_rotation_step_rad: float = math.radians(1)
    max_ik_step_rad: float = 0.35
    ik_position_tolerance_m: float = 0.001
    ik_orientation_tolerance_rad: float = math.radians(0.5)
    large_joint_change_rad: float = math.pi / 2


@dataclass(frozen=True)
class PlanningMetrics:
    duration_s: float = 0.0
    frame_count: int = 0
    path_length_joint: float = 0.0
    path_length_tcp_m: float | None = None
    max_joint_velocity: float = 0.0
    max_joint_acceleration: float = 0.0
    max_joint_delta: float = 0.0


@dataclass(frozen=True)
class PlanningResult:
    success: bool
    trajectory: Trajectory | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metrics: PlanningMetrics = field(default_factory=PlanningMetrics)


class TargetOutsideWorkspace(PlanningError):
    pass


class IKFailure(PlanningError):
    pass


class JointLimitViolation(PlanningError):
    pass


class DiscontinuousIK(PlanningError):
    pass


class TrajectoryLimitViolation(PlanningError):
    pass


class InvalidWaypoint(PlanningError):
    pass
