#!/usr/bin/env python3
"""Replay a recorded CR3 TCP/PTP LeRobot v2.1 dataset.

This replay path is intentionally different from the generic OpenPI trajectory
replayer: it controls the CR3 only and never sends an O6 hand command.  The
default ``joint`` mode replays the six CR3 targets stored in ``action``.  The
optional ``tcp`` mode converts the six-value ``target.tcp_pose`` field
(``x, y, z, roll, pitch, yaw``) to CR3 joints online before motion, which is
useful when the dataset is being treated as a Cartesian waypoint recording.

Preview without hardware::

    ./scripts/run_nrc.sh python core/openpi/cr3_o6/replay_ptp_dataset.py \
        --preview-only

Real movement requires an explicit confirmation::

    ./scripts/run_nrc.sh python core/openpi/cr3_o6/replay_ptp_dataset.py \
        --confirm-motion

The default dataset is ``dataset/replay/ptp_rectangle_v21``.  The robot is
moved smoothly from its current joint position to the first recorded target,
then the episode timestamps are used for replay.  No global/home position is
assumed and the O6 is not initialized or commanded by this script.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.trajectory_bridge import (  # noqa: E402
    episode_paths,
    joint_action_arrays,
    load_shared_trajectory,
)

LOGGER = logging.getLogger("cr3_o6_ptp_replay")

ACTION_DIM = 12
ARM_DIM = 6
TCP_DIM = 6
CONTROL_HZ = 20.0
DEFAULT_DATASET = REPO_ROOT / "dataset" / "replay" / "ptp_rectangle_v21"
DEFAULT_MAX_JOINT_SPEED_RAD_S = 1.0
DEFAULT_INITIAL_MOVE_DURATION_S = 3.0


@dataclass(frozen=True)
class PtpTrajectory:
    actions: np.ndarray
    timestamps: np.ndarray
    target_tcp_poses: np.ndarray | None
    episode_index: int
    source: Path
    fps: float

    @property
    def duration_s(self) -> float:
        return float(self.timestamps[-1] - self.timestamps[0])


def _episode_paths(dataset_dir: Path) -> list[tuple[int, Path]]:
    return episode_paths(dataset_dir)


def _episode_path(dataset_dir: Path, episode_index: int) -> Path:
    if episode_index < 0:
        raise ValueError("--episode-index must be non-negative")
    for index, path in _episode_paths(dataset_dir):
        if index == episode_index:
            return path
    available = [index for index, _path in _episode_paths(dataset_dir)]
    if not available:
        raise FileNotFoundError(f"No parquet episodes found under {dataset_dir / 'data'}")
    raise FileNotFoundError(
        f"Episode {episode_index} not found under {dataset_dir / 'data'}; "
        f"available episode indices: {available}"
    )


def load_ptp_trajectory(
    dataset_dir: Path,
    episode_index: int,
    *,
    control_space: str,
) -> PtpTrajectory:
    """Read joint/PTP V2.1/V3 recordings through the common rad/m model."""
    if control_space not in ("joint", "tcp"):
        raise ValueError("control_space must be joint or tcp")
    dataset_dir = Path(dataset_dir).expanduser().resolve()
    value = load_shared_trajectory(dataset_dir, episode_index)
    actions, timestamps = joint_action_arrays(value, require_hand=False)
    poses = None
    if control_space == "tcp":
        if any(frame.robot_tcp_command is None for frame in value.frames):
            raise ValueError("TCP replay requires target.tcp_pose in every frame")
        poses = np.asarray([frame.robot_tcp_command for frame in value.frames], dtype=np.float64)
        poses[:, :3] *= 1000.0  # Existing parent NRC IK interface accepts mm/rad.
    source = _episode_path(dataset_dir, episode_index)
    LOGGER.info(
        "Loaded PTP episode %d: %d frames, %.3f s; O6 will not be commanded",
        episode_index,
        len(actions),
        value.metadata.duration_s,
    )
    return PtpTrajectory(actions, timestamps, poses, episode_index, source, value.metadata.fps)


def _joint_targets(
    trajectory: PtpTrajectory,
    robot: Any | None,
    *,
    control_space: str,
) -> np.ndarray:
    if control_space == "joint":
        return trajectory.actions[:, :ARM_DIM].copy()
    if robot is None:
        raise ValueError("TCP replay needs a connected robot for online inverse kinematics")
    if trajectory.target_tcp_poses is None:
        raise ValueError("TCP replay has no target TCP poses")

    converted: list[list[float]] = []
    for frame_index, pose in enumerate(trajectory.target_tcp_poses):
        try:
            # The dataset stores the six TCP values.  The NRC adapter expects
            # the optional external-axis value as a seventh value.
            joints = np.asarray(
                robot.convert_pose_to_joints([*pose.tolist(), 0.0]), dtype=np.float64
            )
        except Exception as exc:
            raise RuntimeError(f"IK conversion failed at frame {frame_index}: {exc}") from exc
        if joints.shape != (ARM_DIM,) or not np.all(np.isfinite(joints)):
            raise RuntimeError(
                f"IK returned an invalid six-joint target at frame {frame_index}: {joints}"
            )
        converted.append(joints.tolist())
    return np.asarray(converted, dtype=np.float64)


def _check_joint_steps(joint_targets: np.ndarray, max_ik_step_rad: float) -> None:
    if len(joint_targets) < 2:
        return
    largest = float(np.max(np.abs(np.diff(joint_targets, axis=0))))
    if largest > max_ik_step_rad:
        raise ValueError(
            f"Adjacent CR3 targets differ by up to {largest:.3f} rad, above "
            f"--max-ik-step-rad {max_ik_step_rad:.3f}"
        )


def _move_smoothly(
    robot: Any,
    target: np.ndarray,
    *,
    duration_s: float,
    max_joint_speed_rad_s: float,
    label: str,
) -> None:
    current = np.asarray(robot.get_joint_positions(), dtype=np.float64)
    if current.shape != (ARM_DIM,) or not np.all(np.isfinite(current)):
        raise RuntimeError(f"CR3 feedback must be a finite six-vector, got {current}")
    target = np.asarray(target, dtype=np.float64)
    if target.shape != (ARM_DIM,) or not np.all(np.isfinite(target)):
        raise ValueError(f"{label} target must be a finite six-vector")

    steps = max(
        1,
        math.ceil(duration_s * CONTROL_HZ),
        math.ceil(float(np.max(np.abs(target - current))) / max_joint_speed_rad_s * CONTROL_HZ),
    )
    LOGGER.info("Moving to %s in %d steps: %s", label, steps, np.round(target, 5).tolist())
    started = time.monotonic()
    for step in range(1, steps + 1):
        command = current + (target - current) * (step / steps)
        robot.send_joint_positions(command.tolist())
        remaining = started + step / CONTROL_HZ - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


def replay_trajectory(
    trajectory: PtpTrajectory,
    joint_targets: np.ndarray,
    robot: Any,
    *,
    time_scale: float,
    max_joint_speed_rad_s: float,
    disable_slew_limit: bool,
) -> None:
    """Replay CR3 joint targets at the recorded timestamps."""

    first_timestamp = float(trajectory.timestamps[0])
    started = time.monotonic()
    previous_timestamp = first_timestamp
    previous_command = joint_targets[0].copy()
    limited_count = 0

    for index, (target, timestamp) in enumerate(
        zip(joint_targets, trajectory.timestamps, strict=True)
    ):
        deadline = started + (float(timestamp) - first_timestamp) / time_scale
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

        command = target.copy()
        if not disable_slew_limit and index > 0:
            elapsed = max((float(timestamp) - previous_timestamp) / time_scale, 1e-6)
            max_step = max_joint_speed_rad_s * elapsed
            limited_command = previous_command + np.clip(
                command - previous_command, -max_step, max_step
            )
            if not np.allclose(command, limited_command):
                limited_count += 1
            command = limited_command

        robot.send_joint_positions(command.tolist())
        previous_command = command
        previous_timestamp = float(timestamp)

    LOGGER.info("Replay complete; slew-limited frames=%d", limited_count)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--episode-index", type=int, default=0)
    parser.add_argument("--config", default=None, help="Hardware profile TOML")
    parser.add_argument(
        "--control-space",
        choices=("joint", "tcp"),
        default="joint",
        help="Replay action CR3 joints, or convert target.tcp_pose to joints online",
    )
    parser.add_argument(
        "--preview-only", action="store_true", help="Validate and summarize without hardware"
    )
    parser.add_argument(
        "--confirm-motion", action="store_true", help="Required before real robot movement"
    )
    parser.add_argument("--no-auto-power-on", action="store_true")
    parser.add_argument("--power-off-on-exit", action="store_true")
    parser.add_argument(
        "--time-scale", type=float, default=1.0, help="1.0 uses recorded timestamps"
    )
    parser.add_argument(
        "--max-joint-speed-rad-s", type=float, default=DEFAULT_MAX_JOINT_SPEED_RAD_S
    )
    parser.add_argument("--disable-slew-limit", action="store_true")
    parser.add_argument("--max-ik-step-rad", type=float, default=0.5)
    parser.add_argument(
        "--initial-move-duration-s", type=float, default=DEFAULT_INITIAL_MOVE_DURATION_S
    )
    parser.add_argument("--return-to-first-action", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.preview_only == args.confirm_motion:
        raise SystemExit("Choose exactly one: --preview-only or --confirm-motion")
    if args.time_scale <= 0 or not math.isfinite(args.time_scale):
        raise SystemExit("--time-scale must be finite and positive")
    if args.max_joint_speed_rad_s <= 0 or not math.isfinite(args.max_joint_speed_rad_s):
        raise SystemExit("--max-joint-speed-rad-s must be finite and positive")
    if args.max_ik_step_rad <= 0 or not math.isfinite(args.max_ik_step_rad):
        raise SystemExit("--max-ik-step-rad must be finite and positive")
    if args.initial_move_duration_s <= 0:
        raise SystemExit("--initial-move-duration-s must be positive")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )

    dataset_dir = args.data_dir.expanduser()
    if not dataset_dir.is_absolute():
        dataset_dir = REPO_ROOT / dataset_dir
    try:
        trajectory = load_ptp_trajectory(
            dataset_dir,
            args.episode_index,
            control_space=args.control_space,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        LOGGER.error("PTP replay failed during dataset validation: %s", exc)
        return 1

    if args.preview_only:
        if args.control_space == "joint":
            _check_joint_steps(trajectory.actions[:, :ARM_DIM], args.max_ik_step_rad)
        LOGGER.info("Preview-only: dataset validated; no hardware was connected")
        return 0

    robot = None
    servo_opened = False
    powered_by_client = False
    joint_targets: np.ndarray | None = None
    try:
        from config.hardware import load_hardware_config
        from vendor.nrc_interface.interface import SERVO_RUNNING

        hardware = load_hardware_config(args.config)
        robot = hardware.create_nrc_interface()
        LOGGER.info("Connecting CR3 %s from %s", hardware.nrc.ip, hardware.source)
        robot.connect()

        if robot.get_servo_state() != SERVO_RUNNING:
            if args.no_auto_power_on:
                raise RuntimeError("CR3 is not running and --no-auto-power-on was specified")
            LOGGER.info("CR3 is not running; powering it on")
            robot.power_on()
            powered_by_client = True
        if robot.get_servo_state() != SERVO_RUNNING:
            raise RuntimeError("CR3 is not in running state")

        joint_targets = _joint_targets(
            trajectory,
            robot,
            control_space=args.control_space,
        )
        _check_joint_steps(joint_targets, args.max_ik_step_rad)
        robot.open_servoj()
        servo_opened = True
        _move_smoothly(
            robot,
            joint_targets[0],
            duration_s=args.initial_move_duration_s,
            max_joint_speed_rad_s=args.max_joint_speed_rad_s,
            label="first recorded CR3 target",
        )
        LOGGER.info(
            "Replaying episode %d in %s mode; O6 remains untouched",
            trajectory.episode_index,
            args.control_space,
        )
        replay_trajectory(
            trajectory,
            joint_targets,
            robot,
            time_scale=args.time_scale,
            max_joint_speed_rad_s=args.max_joint_speed_rad_s,
            disable_slew_limit=args.disable_slew_limit,
        )
        if args.return_to_first_action:
            _move_smoothly(
                robot,
                joint_targets[0],
                duration_s=args.initial_move_duration_s,
                max_joint_speed_rad_s=args.max_joint_speed_rad_s,
                label="first recorded CR3 target after replay",
            )
        return 0
    except KeyboardInterrupt:
        LOGGER.info("PTP replay stopped by user")
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        LOGGER.error("PTP replay failed: %s", exc)
        return 1
    finally:
        if robot is not None:
            if servo_opened:
                try:
                    robot.close_servoj()
                except Exception:
                    LOGGER.exception("Failed to close CR3 ServoJ")
            if powered_by_client and args.power_off_on_exit:
                try:
                    robot.power_off()
                except Exception:
                    LOGGER.exception("Failed to power off CR3")
            try:
                robot.disconnect()
            except Exception:
                LOGGER.exception("Failed to disconnect CR3")


if __name__ == "__main__":
    raise SystemExit(main())
