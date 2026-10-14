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
from dataclasses import dataclass
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    paths = (dataset_dir / "data").glob("chunk-*/episode_*.parquet")
    episodes: list[tuple[int, Path]] = []
    for path in paths:
        try:
            episode_index = int(path.stem.removeprefix("episode_"))
        except ValueError:
            continue
        episodes.append((episode_index, path))
    return sorted(episodes, key=lambda item: (item[0], str(item[1])))


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


def _load_fps(dataset_dir: Path) -> float:
    try:
        info = json.loads((dataset_dir / "meta" / "info.json").read_text())
        fps = float(info.get("fps", CONTROL_HZ))
    except (OSError, ValueError, TypeError):
        fps = CONTROL_HZ
    return fps if math.isfinite(fps) and fps > 0 else CONTROL_HZ


def _stack_vector_column(values: Any, *, name: str, width: int) -> np.ndarray:
    try:
        result = np.stack([np.asarray(value, dtype=np.float64).reshape(-1) for value in values])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Could not parse the {name} column") from exc
    if result.ndim != 2 or result.shape[1] != width:
        raise ValueError(f"{name} must have shape [N, {width}], got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} contains NaN or Inf")
    return result


def load_ptp_trajectory(
    dataset_dir: Path,
    episode_index: int,
    *,
    control_space: str,
) -> PtpTrajectory:
    """Load and validate one LeRobot v2.1 episode without hardware imports."""

    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Parquet replay requires pandas and pyarrow; use the NRC environment") from exc

    dataset_dir = Path(dataset_dir).expanduser().resolve()
    source = _episode_path(dataset_dir, episode_index)
    try:
        table = pd.read_parquet(source)
    except Exception as exc:
        raise RuntimeError(f"Could not read trajectory parquet {source}: {exc}") from exc

    required = {"action", "timestamp", "frame_index"}
    missing = required - set(table.columns)
    if missing:
        raise ValueError(f"Trajectory is missing columns: {sorted(missing)}")
    table = table.sort_values("frame_index").reset_index(drop=True)
    if table.empty:
        raise ValueError("Trajectory is empty")
    if "episode_index" in table.columns:
        episode_indices = np.asarray(table["episode_index"], dtype=np.int64)
        if np.any(episode_indices != episode_index):
            raise ValueError(f"{source} contains an unexpected episode_index")

    actions = _stack_vector_column(table["action"], name="action", width=ACTION_DIM)
    timestamps = np.asarray(table["timestamp"], dtype=np.float64)
    if timestamps.shape != (len(actions),) or not np.all(np.isfinite(timestamps)):
        raise ValueError("timestamp must be a finite one-dimensional column")
    if np.any(np.diff(timestamps) < 0):
        raise ValueError("timestamps must be monotonically increasing")

    target_tcp_poses: np.ndarray | None = None
    if control_space == "tcp":
        if "target.tcp_pose" not in table.columns:
            raise ValueError("TCP replay requires the target.tcp_pose column")
        target_tcp_poses = _stack_vector_column(
            table["target.tcp_pose"], name="target.tcp_pose", width=TCP_DIM
        )

    hand_variation = float(np.max(np.ptp(actions[:, ARM_DIM:], axis=0)))
    max_recorded_speed = (
        float(np.max(np.abs(np.diff(actions[:, :ARM_DIM], axis=0))) * _load_fps(dataset_dir))
        if len(actions) > 1
        else 0.0
    )
    LOGGER.info(
        "Loaded episode %d: %d frames, %.3f s at %.2f fps, source=%s",
        episode_index,
        len(actions),
        float(timestamps[-1] - timestamps[0]),
        _load_fps(dataset_dir),
        source,
    )
    LOGGER.info("Recorded max CR3 action change: %.3f rad/s", max_recorded_speed)
    LOGGER.info("Recorded O6 action range: %.3f; O6 will not be commanded", hand_variation)
    LOGGER.info("First CR3 target: %s", np.round(actions[0, :ARM_DIM], 5).tolist())
    LOGGER.info("Last CR3 target:  %s", np.round(actions[-1, :ARM_DIM], 5).tolist())
    if target_tcp_poses is not None:
        LOGGER.info(
            "TCP target bounds: min=%s max=%s",
            np.round(np.min(target_tcp_poses[:, :3], axis=0), 3).tolist(),
            np.round(np.max(target_tcp_poses[:, :3], axis=0), 3).tolist(),
        )

    return PtpTrajectory(
        actions=actions,
        timestamps=timestamps,
        target_tcp_poses=target_tcp_poses,
        episode_index=episode_index,
        source=source,
        fps=_load_fps(dataset_dir),
    )


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
            raise RuntimeError(f"IK returned an invalid six-joint target at frame {frame_index}: {joints}")
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

    for index, (target, timestamp) in enumerate(zip(joint_targets, trajectory.timestamps, strict=True)):
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
    parser.add_argument("--preview-only", action="store_true", help="Validate and summarize without hardware")
    parser.add_argument("--confirm-motion", action="store_true", help="Required before real robot movement")
    parser.add_argument("--no-auto-power-on", action="store_true")
    parser.add_argument("--power-off-on-exit", action="store_true")
    parser.add_argument("--time-scale", type=float, default=1.0, help="1.0 uses recorded timestamps")
    parser.add_argument("--max-joint-speed-rad-s", type=float, default=DEFAULT_MAX_JOINT_SPEED_RAD_S)
    parser.add_argument("--disable-slew-limit", action="store_true")
    parser.add_argument("--max-ik-step-rad", type=float, default=0.5)
    parser.add_argument("--initial-move-duration-s", type=float, default=DEFAULT_INITIAL_MOVE_DURATION_S)
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
