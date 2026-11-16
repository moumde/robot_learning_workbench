"""Robot-independent trajectory values: radians, metres, and raw hand positions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class ReplayMode(Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass(frozen=True)
class ReplayOptions:
    mode: ReplayMode = ReplayMode.RELATIVE
    time_scale: float = 1.0
    repeat: int = 1
    arm_enabled: bool = True
    hand_enabled: bool = True
    joint_mask: tuple[bool, ...] | None = None
    transition_s: float = 3.0


@dataclass(frozen=True)
class TrajectoryFrame:
    timestamp: float
    robot_joint_state: tuple[float, ...] | None = None
    robot_joint_command: tuple[float, ...] | None = None
    robot_tcp_state: tuple[float, ...] | None = None
    robot_tcp_command: tuple[float, ...] | None = None
    hand_state: tuple[float, ...] | None = None
    hand_command: tuple[float, ...] | None = None


@dataclass(frozen=True)
class TrajectoryMetadata:
    trajectory_id: str
    name: str
    created_at: str
    robot_type: str
    hand_type: str | None
    control_mode: str
    fps: float
    frame_count: int
    duration_s: float
    source: str
    description: str = ""
    joint_mask: tuple[bool, ...] | None = None
    planning: dict[str, Any] | None = None


@dataclass(frozen=True)
class Trajectory:
    name: str
    frames: tuple[TrajectoryFrame, ...]
    metadata: TrajectoryMetadata


def make_trajectory(
    name: str,
    frames,
    *,
    fps: float = 20.0,
    robot_type="cr3a",
    hand_type="o6",
    control_mode="joint",
    source="manual",
    description="",
    trajectory_id=None,
    created_at=None,
    joint_mask=None,
) -> Trajectory:
    frames = tuple(frames)
    metadata = TrajectoryMetadata(
        trajectory_id or str(uuid4()),
        name,
        created_at or datetime.now(UTC).isoformat(),
        robot_type,
        hand_type,
        control_mode,
        fps,
        len(frames),
        frames[-1].timestamp - frames[0].timestamp if frames else 0.0,
        source,
        description,
        tuple(joint_mask) if joint_mask is not None else None,
    )
    return Trajectory(name, frames, metadata)
