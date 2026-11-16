"""Validate trajectories and produce small numeric previews without device I/O."""

from __future__ import annotations

import math
from datetime import datetime
from uuid import UUID

from .model import ReplayMode, ReplayOptions, Trajectory

VECTOR_FIELDS = (
    "robot_joint_state",
    "robot_joint_command",
    "robot_tcp_state",
    "robot_tcp_command",
    "hand_state",
    "hand_command",
)


def validate_frame(frame, joint_limits_rad=None):
    if not math.isfinite(frame.timestamp) or frame.timestamp < 0:
        raise ValueError("Trajectory timestamp must be finite and nonnegative")
    for name in VECTOR_FIELDS:
        values = getattr(frame, name)
        if values is None:
            continue
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            raise ValueError(f"{name} must contain six finite values")
        if name.startswith("robot_joint") and joint_limits_rad is not None:
            if len(joint_limits_rad) != 6:
                raise ValueError("joint_limits_rad requires six pairs")
            if any(not lo <= q <= hi for q, (lo, hi) in zip(values, joint_limits_rad, strict=True)):
                raise ValueError(f"{name} exceeds joint limits")
    if all(getattr(frame, name) is None for name in VECTOR_FIELDS):
        raise ValueError("Trajectory frame contains no state or command")


def validate_trajectory(trajectory: Trajectory, joint_limits_rad=None) -> None:
    meta = trajectory.metadata
    UUID(meta.trajectory_id)
    datetime.fromisoformat(meta.created_at)
    if not trajectory.name.strip() or meta.name != trajectory.name:
        raise ValueError("Trajectory name is required and must match metadata")
    if meta.joint_mask is not None and (
        len(meta.joint_mask) != 6
        or any(type(v) is not bool for v in meta.joint_mask)
        or not any(meta.joint_mask)
    ):
        raise ValueError("Trajectory joint_mask requires six booleans selecting at least one joint")
    if not all(str(v).strip() for v in (meta.robot_type, meta.control_mode, meta.source)):
        raise ValueError("Trajectory metadata is incomplete")
    if not math.isfinite(meta.fps) or meta.fps <= 0:
        raise ValueError("Trajectory fps must be positive")
    if not trajectory.frames or len(trajectory.frames) != meta.frame_count:
        raise ValueError("Trajectory must contain frames matching metadata")
    previous = None
    for frame in trajectory.frames:
        validate_frame(frame, joint_limits_rad)
        if previous is not None and frame.timestamp <= previous:
            raise ValueError("Trajectory timestamps must increase strictly")
        previous = frame.timestamp
    duration = trajectory.frames[-1].timestamp - trajectory.frames[0].timestamp
    if not math.isfinite(meta.duration_s) or not math.isclose(
        duration, meta.duration_s, abs_tol=1e-9
    ):
        raise ValueError("Trajectory duration does not match metadata")


def validate_options(options: ReplayOptions) -> None:
    if not isinstance(options.mode, ReplayMode):
        raise ValueError("Unknown replay mode")
    if not math.isfinite(options.time_scale) or not 0.1 <= options.time_scale <= 2.0:
        raise ValueError("time_scale must be between 0.1 and 2.0")
    if (
        isinstance(options.repeat, bool)
        or not isinstance(options.repeat, int)
        or options.repeat < 1
    ):
        raise ValueError("repeat must be a positive integer")
    if not options.arm_enabled and not options.hand_enabled:
        raise ValueError("Enable arm, hand, or both")
    if options.joint_mask is not None and (
        len(options.joint_mask) != 6
        or any(type(v) is not bool for v in options.joint_mask)
        or (options.arm_enabled and not any(options.joint_mask))
    ):
        raise ValueError("joint_mask requires six booleans with at least one arm joint enabled")
    if not math.isfinite(options.transition_s) or not 2.0 <= options.transition_s <= 5.0:
        raise ValueError("Initial transition must take 2 to 5 seconds")


def joint_target(frame):
    return (
        frame.robot_joint_command
        if frame.robot_joint_command is not None
        else frame.robot_joint_state
    )


def hand_target(frame):
    return frame.hand_command if frame.hand_command is not None else frame.hand_state


def validate_replay_channels(trajectory, options):
    if options.arm_enabled and any(joint_target(f) is None for f in trajectory.frames):
        raise ValueError("Arm replay requires joint command or state in every frame")
    if options.hand_enabled and any(hand_target(f) is None for f in trajectory.frames):
        raise ValueError("Hand replay requires hand command or state in every frame")


def replay_joint_mask(trajectory: Trajectory, options: ReplayOptions) -> tuple[bool, ...]:
    return options.joint_mask or trajectory.metadata.joint_mask or (True,) * 6


def validate_replay_speed(
    trajectory: Trajectory, options: ReplayOptions, max_joint_speed_rad_s: float
) -> None:
    if not math.isfinite(max_joint_speed_rad_s) or max_joint_speed_rad_s <= 0:
        raise ValueError("Replay joint speed limit must be finite and positive")
    if not options.arm_enabled:
        return
    mask = replay_joint_mask(trajectory, options)
    for previous, frame in zip(trajectory.frames, trajectory.frames[1:], strict=False):
        a, b = joint_target(previous), joint_target(frame)
        if a is None or b is None:
            raise ValueError("Arm replay requires joint command or state in every frame")
        duration = (frame.timestamp - previous.timestamp) / options.time_scale
        if any(
            selected and abs(y - x) / duration > max_joint_speed_rad_s
            for selected, x, y in zip(mask, a, b, strict=True)
        ):
            raise ValueError("Trajectory joint speed exceeds replay limit at this time_scale")


def preview_trajectory(trajectory: Trajectory) -> dict:
    validate_trajectory(trajectory)
    frames = trajectory.frames
    joints = [joint_target(f) for f in frames]

    def bounds(values):
        present = [v for v in values if v is not None]
        return (
            [[min(v[i] for v in present), max(v[i] for v in present)] for i in range(6)]
            if present
            else None
        )

    speed = [0.0] * 6
    for first, second, a, b in zip(frames, frames[1:], joints, joints[1:], strict=False):
        if a is not None and b is not None:
            speed = [
                max(s, abs(y - x) / (second.timestamp - first.timestamp))
                for s, x, y in zip(speed, a, b, strict=True)
            ]
    return {
        "name": trajectory.name,
        "trajectory_id": trajectory.metadata.trajectory_id,
        "frame_count": len(frames),
        "duration_s": trajectory.metadata.duration_s,
        "fps": trajectory.metadata.fps,
        "robot_type": trajectory.metadata.robot_type,
        "source": trajectory.metadata.source,
        "created_at": trajectory.metadata.created_at,
        "warnings": (trajectory.metadata.planning or {}).get("warnings", []),
        "max_joint_delta_rad": [
            max(
                (
                    abs(b[i] - a[i])
                    for a, b in zip(joints, joints[1:], strict=False)
                    if a is not None and b is not None
                ),
                default=0.0,
            )
            for i in range(6)
        ],
        "joint_range_rad": bounds(joints),
        "max_joint_velocity_rad_s": speed,
        "tcp_range": bounds([f.robot_tcp_command or f.robot_tcp_state for f in frames]),
        "hand_range": bounds([hand_target(f) for f in frames]),
        "start_joint_rad": joints[0],
        "end_joint_rad": joints[-1],
    }
