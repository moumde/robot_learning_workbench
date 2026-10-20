"""Trajectory interchange and playback inside an already owned robot session.

Importing or loading data never imports an SDK. The workflow owns connection,
power and ServoJ lifecycle; the borrowed Player can only send targets and hold.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# Register the integrated src package for callers launched from the parent repo.

# isort: split

from core.workbench.motion import MotionCoordinator
from core.workbench.trajectory import (
    ReplayMode,
    ReplayOptions,
    TrajectoryPlayer,
    TrajectoryStore,
)
from core.workbench.trajectory.adapters import LeRobotTrajectoryAdapter
from core.workbench.trajectory.validation import (
    hand_target,
    validate_options,
    validate_replay_channels,
    validate_replay_speed,
    validate_trajectory,
)

__all__ = [
    "ReplayMode",
    "ReplayOptions",
    "episode_paths",
    "load_shared_trajectory",
    "joint_action_arrays",
    "validate_session_trajectory",
    "play_in_existing_session",
]


def _named_directory(path):
    path = Path(path).expanduser().resolve()
    directory = path.parent if path.is_file() else path
    return directory if (directory / "meta.json").is_file() else None


def episode_paths(path):
    """Enumerate stored episode indices, including episodes sharing V3 files.

    A named UUID trajectory is one episode (index zero). Each LeRobot index
    points to its data directory because V3 can span files or share a file.
    """
    path = Path(path).expanduser().resolve()
    if directory := _named_directory(path):
        return [(0, directory / "trajectory.parquet")]
    data = path / "data" if path.is_dir() else path
    if not data.exists() or (data.is_dir() and not any(data.rglob("*.parquet"))):
        return []
    import pyarrow.dataset as ds

    dataset = ds.dataset(data, format="parquet")
    if "episode_index" not in dataset.schema.names:
        return [(0, data)]
    indices = dataset.to_table(columns=["episode_index"])["episode_index"].unique().to_pylist()
    if any(type(index) is not int or index < 0 for index in indices):
        raise ValueError("episode_index must contain nonnegative integers")
    return [(index, data) for index in sorted(indices)]


def load_shared_trajectory(path, episode_index=0):
    """Read a UUID Store or LeRobot episode using the common rad/m model."""
    path = Path(path).expanduser().resolve()
    if directory := _named_directory(path):
        if episode_index != 0:
            raise ValueError("Named trajectories have only episode index 0")
        return TrajectoryStore(directory.parent).load(directory.name)
    return LeRobotTrajectoryAdapter.load(path, episode_index)


def joint_action_arrays(value, *, require_hand=True):
    """Adapt only unconstrained absolute-joint data to the legacy replay loops.

    Shared trajectory tasks keep masks, plan restrictions and measured-joint
    replay inside the common Player instead of flattening these semantics.
    """
    if (
        value.metadata.planning
        or (value.metadata.joint_mask is not None and not all(value.metadata.joint_mask))
        or value.metadata.control_mode != "joint"
        or any(frame.robot_joint_command is None for frame in value.frames)
    ):
        raise ValueError(
            "Use the shared 'trajectory' task to preserve this trajectory's replay semantics"
        )
    actions = []
    for frame in value.frames:
        hand = hand_target(frame)
        if hand is None and require_hand:
            raise ValueError(
                "Hand data missing; use a shared trajectory task with hand_enabled=false"
            )
        actions.append(
            tuple(frame.robot_joint_command) + (tuple(hand) if hand is not None else (0.0,) * 6)
        )
    return np.asarray(actions, dtype=np.float64), np.asarray(
        [f.timestamp for f in value.frames], dtype=np.float64
    )


def validate_session_trajectory(value, options, *, max_joint_speed_rad_s=1.0):
    """Preflight before a parent workflow connects or performs its initial move."""
    validate_trajectory(value)
    if (value.metadata.planning or {}).get("offline_only"):
        raise ValueError("Offline preview only; connect and replan before execution")
    validate_options(options)
    validate_replay_channels(value, options)
    validate_replay_speed(value, options, max_joint_speed_rad_s)
    if options.hand_enabled and any(
        not all(0 <= position <= 255 for position in hand_target(frame)) for frame in value.frames
    ):
        raise ValueError("Hand positions must be within 0..255")


class _BorrowedSession:
    def __init__(self, robot, hand, *, arm_enabled, hand_enabled):
        self.robot, self.hand = robot, hand
        self.arm_enabled, self.hand_enabled = arm_enabled, hand_enabled

    def check_ready(self, arm_enabled, hand_enabled):
        if arm_enabled and (
            not self.robot.connected
            or not self.robot.servo_active
            or self.robot.get_servo_state() != 3
        ):
            raise RuntimeError(
                "Shared trajectory requires the parent's connected, running ServoJ session"
            )
        if hand_enabled and self.hand is None:
            raise RuntimeError(
                "Shared trajectory hand replay requires the parent's existing hand session"
            )

    def read_joints(self):
        return tuple(self.robot.get_joint_positions())

    joint_position_rad = read_joints

    def open_servo(self, _vmax, _amax, _jmax):
        # Player requests a lease, but only the parent may open/reconfigure ServoJ.
        self.check_ready(True, self.hand_enabled)

    def servo_joint(self, target):
        # The Player refreshes servo feedback every 100 ms; keep the 100 Hz
        # send path free of an extra synchronous status round trip.
        if not self.robot.connected or not self.robot.servo_active:
            raise RuntimeError("Parent ServoJ session is no longer active")
        self.robot.send_joint_positions(list(target.positions_rad))
        return True

    def send_hand(self, target):
        self.hand.finger_move([round(value) for value in target])

    def hold_hand(self):
        if self.hand_enabled and self.hand is not None:
            self.send_hand(self.hand.get_state())

    def stop(self):
        # A released task leaves the parent session open for its next task.
        if (
            self.arm_enabled
            and self.robot.connected
            and self.robot.servo_active
            and self.robot.get_servo_state() == 3
        ):
            self.robot.send_joint_positions(list(self.read_joints()))


def play_in_existing_session(
    value, robot, hand=None, *, options=None, max_joint_speed_rad_s=1.0, clock=None, wait=None
):
    """Play synchronously without owning connection, power or ServoJ lifecycle."""
    options = options or ReplayOptions(hand_enabled=False)
    validate_session_trajectory(value, options, max_joint_speed_rad_s=max_joint_speed_rad_s)
    session = _BorrowedSession(
        robot, hand, arm_enabled=options.arm_enabled, hand_enabled=options.hand_enabled
    )
    session.check_ready(options.arm_enabled, options.hand_enabled)
    kwargs = {"clock": clock} if clock is not None else {}
    player = TrajectoryPlayer(MotionCoordinator(session), session, wait=wait, **kwargs)
    return player.play(value, options, max_joint_speed_rad_s=max_joint_speed_rad_s)
