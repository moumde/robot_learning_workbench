"""Preview or replay a LeRobot CR3/O6 episode from ``dataset/replay``.

Preview only parses and summarizes the trajectory, without connecting hardware::

    ./scripts/run_nrc.sh python core/openpi/cr3_o6/replay_trajectory.py --preview-only

Real robot movement requires an explicit confirmation::

    ./scripts/run_nrc.sh python core/openpi/cr3_o6/replay_trajectory.py --confirm-motion

Actions are six absolute CR3 joint targets in radians followed by six O6
positions in the native 0..255 range. The episode is read from its LeRobot
parquet file; timestamps control replay timing.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import functools
import inspect
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
LINKERHAND_SDK_ROOT = REPO_ROOT / "vendor" / "actuator" / "linkerhand-python-sdk"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(LINKERHAND_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(LINKERHAND_SDK_ROOT))

from config.hardware import HardwareConfig, load_hardware_config  # noqa: E402


LOGGER = logging.getLogger("cr3_o6_trajectory_replay")

ACTION_DIM = 12
CONTROL_HZ = 20.0
DEFAULT_DATASET = REPO_ROOT / "dataset" / "replay" / "teleop_once"
INITIAL_ROBOT_POSITION = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
INITIAL_HAND_POSITION = (157, 95, 175, 0, 0, 0)
DEFAULT_MAX_JOINT_SPEED_RAD_S = 1.0
DEFAULT_INITIAL_MOVE_DURATION_S = 3.0
DEFAULT_FIRST_ACTION_MOVE_DURATION_S = 5.0
DEFAULT_O6_SPEED = 100


@dataclass(frozen=True)
class Trajectory:
    actions: np.ndarray
    timestamps: np.ndarray
    episode_index: int
    source: Path
    fps: float

    @property
    def duration_s(self) -> float:
        return float(self.timestamps[-1] - self.timestamps[0])


def _load_fps(dataset_dir: Path) -> float:
    try:
        info = json.loads((dataset_dir / "meta" / "info.json").read_text())
        fps = float(info.get("fps", CONTROL_HZ))
    except (OSError, ValueError, TypeError):
        fps = CONTROL_HZ
    return fps if math.isfinite(fps) and fps > 0 else CONTROL_HZ


def _episode_path(dataset_dir: Path, episode_index: int) -> Path:
    if episode_index < 0:
        raise ValueError("--episode-index must be non-negative")
    data_dir = dataset_dir / "data"
    expected = [path for index, path in _episode_paths(dataset_dir) if index == episode_index]
    if expected:
        return expected[0]
    available = _episode_paths(dataset_dir)
    if not available:
        raise FileNotFoundError(f"No parquet episodes found under {data_dir}")
    raise FileNotFoundError(
        f"Episode {episode_index} not found under {data_dir}; "
        f"available episode indices: {[index for index, _path in available]}"
    )


def _episode_paths(dataset_dir: Path) -> list[tuple[int, Path]]:
    paths = (dataset_dir / "data").glob("chunk-*/episode_*.parquet")
    episodes = []
    for path in paths:
        try:
            episode_index = int(path.stem.removeprefix("episode_"))
        except ValueError:
            continue
        episodes.append((episode_index, path))
    return sorted(episodes, key=lambda item: (item[0], str(item[1])))


def load_trajectory(
    dataset_dir: Path, episode_index: int, *, hand_min: int = 0, hand_max: int = 255
) -> Trajectory:
    """Load and validate one LeRobot episode without importing hardware SDKs."""

    dataset_dir = Path(dataset_dir).expanduser().resolve()
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Parquet replay requires pandas and pyarrow; run setup_nrc_env.sh") from exc

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

    try:
        actions = np.stack(
            [np.asarray(value, dtype=np.float64).reshape(-1) for value in table["action"]]
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Could not parse the action column in {source}") from exc
    if actions.shape != (len(table), ACTION_DIM):
        raise ValueError(f"action must have shape [N, {ACTION_DIM}], got {actions.shape}")
    if not np.all(np.isfinite(actions)):
        raise ValueError("Action column contains NaN or Inf")
    if np.any((actions[:, 6:] < hand_min) | (actions[:, 6:] > hand_max)):
        raise ValueError(f"O6 actions are outside the configured range [{hand_min}, {hand_max}]")

    timestamps = np.asarray(table["timestamp"], dtype=np.float64)
    if timestamps.shape != (len(actions),) or not np.all(np.isfinite(timestamps)):
        raise ValueError("timestamp must be a finite one-dimensional column")
    if np.any(np.diff(timestamps) < 0):
        raise ValueError("timestamps must be monotonically increasing")

    fps = _load_fps(dataset_dir)
    max_recorded_speed = (
        float(np.max(np.abs(np.diff(actions[:, :6], axis=0))) * fps)
        if len(actions) > 1
        else 0.0
    )
    LOGGER.info(
        "Loaded episode %d: %d frames, %.2f s at %.2f fps, source=%s",
        episode_index,
        len(actions),
        float(timestamps[-1] - timestamps[0]),
        fps,
        source,
    )
    LOGGER.info("Recorded max CR3 target change: %.3f rad/s", max_recorded_speed)
    LOGGER.info("First action: %s", np.round(actions[0], 4).tolist())
    LOGGER.info("Last action:  %s", np.round(actions[-1], 4).tolist())
    return Trajectory(actions, timestamps, episode_index, source, fps)


def _patch_pymodbus_slave_argument() -> None:
    """Bridge SDK ``slave=`` calls to pymodbus APIs using ``device_id=``."""

    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError as exc:
        raise RuntimeError("LinkerHand RS485 requires pymodbus in the NRC environment") from exc

    for method_name in ("read_input_registers", "write_registers"):
        method = getattr(ModbusSerialClient, method_name, None)
        if method is None:
            continue
        parameters = inspect.signature(method).parameters
        if "slave" in parameters or "device_id" not in parameters:
            continue
        if getattr(method, "_workbench_slave_compat", False):
            continue

        @functools.wraps(method)
        def compatible_method(self: Any, *args: Any, _method=method, **kwargs: Any):
            if "slave" in kwargs:
                kwargs["device_id"] = kwargs.pop("slave")
            return _method(self, *args, **kwargs)

        compatible_method._workbench_slave_compat = True
        setattr(ModbusSerialClient, method_name, compatible_method)


def _load_hand_api():
    try:
        from LinkerHand.linker_hand_api import LinkerHandApi
    except ImportError as exc:
        raise RuntimeError(f"Could not import the vendored LinkerHand SDK at {LINKERHAND_SDK_ROOT}") from exc
    return LinkerHandApi


def _close_hand(hand_api: Any) -> None:
    hand = getattr(hand_api, "hand", None)
    for method_name in ("close", "close_can_interface"):
        close = getattr(hand, method_name, None)
        if callable(close):
            try:
                close()
            except Exception:
                LOGGER.exception("Failed to close LinkerHand backend")
            return


def _move_to_position(
    robot: Any,
    hand: Any,
    arm_target: np.ndarray,
    hand_target: np.ndarray,
    *,
    duration_s: float,
    max_joint_speed_rad_s: float,
    label: str,
) -> None:
    """Move by interpolated ServoJ commands, limiting CR3 target slew."""

    current = np.asarray(robot.get_joint_positions(), dtype=np.float64)
    if current.shape != (6,) or not np.all(np.isfinite(current)):
        raise RuntimeError(f"CR3 joint position must be a finite six-vector, got {current}")
    arm_target = np.asarray(arm_target, dtype=np.float64)
    hand_target = np.asarray(hand_target, dtype=np.float64)
    if arm_target.shape != (6,) or not np.all(np.isfinite(arm_target)):
        raise ValueError("CR3 target must be a finite six-vector")
    if hand_target.shape != (6,) or not np.all(np.isfinite(hand_target)):
        raise ValueError("O6 target must be a finite six-vector")
    hand_target = np.clip(np.rint(hand_target), 0, 255).astype(np.int64)
    steps = max(
        1,
        math.ceil(duration_s * CONTROL_HZ),
        math.ceil(float(np.max(np.abs(arm_target - current))) / max_joint_speed_rad_s * CONTROL_HZ),
    )
    LOGGER.info(
        "Moving to %s: arm=%s hand=%s steps=%d",
        label,
        np.round(arm_target, 4).tolist(),
        hand_target.tolist(),
        steps,
    )
    hand.finger_move(hand_target.tolist())
    started = time.monotonic()
    for step in range(1, steps + 1):
        command = current + (arm_target - current) * (step / steps)
        robot.send_joint_positions(command.tolist())
        remaining = started + step / CONTROL_HZ - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


def replay_trajectory(
    trajectory: Trajectory,
    robot: Any,
    hand: Any,
    *,
    time_scale: float,
    max_joint_speed_rad_s: float,
    disable_slew_limit: bool,
    repeat: int,
) -> None:
    """Send timestamped actions, optionally repeating the same episode."""

    first_timestamp = float(trajectory.timestamps[0])
    for repetition in range(repeat):
        if repetition > 0:
            _move_to_position(
                robot,
                hand,
                trajectory.actions[0, :6],
                trajectory.actions[0, 6:],
                duration_s=DEFAULT_FIRST_ACTION_MOVE_DURATION_S,
                max_joint_speed_rad_s=max_joint_speed_rad_s,
                label="first action before repeated replay",
            )
        LOGGER.info(
            "Replaying episode %d, repeat %d/%d, time scale %.3f%s",
            trajectory.episode_index,
            repetition + 1,
            repeat,
            time_scale,
            " (slew limit disabled)" if disable_slew_limit else "",
        )
        started = time.monotonic()
        previous_timestamp = first_timestamp
        previous_command = trajectory.actions[0, :6].copy()
        limited_count = 0
        for index, (action, timestamp) in enumerate(
            zip(trajectory.actions, trajectory.timestamps, strict=True)
        ):
            deadline = started + (float(timestamp) - first_timestamp) / time_scale
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)

            arm_target = action[:6].copy()
            if not disable_slew_limit and index > 0:
                elapsed = max((float(timestamp) - previous_timestamp) / time_scale, 1e-6)
                max_step = max_joint_speed_rad_s * elapsed
                limited_target = previous_command + np.clip(
                    arm_target - previous_command, -max_step, max_step
                )
                if not np.allclose(arm_target, limited_target):
                    limited_count += 1
                arm_target = limited_target

            robot.send_joint_positions(arm_target.tolist())
            hand.finger_move(np.rint(action[6:]).astype(np.int64).tolist())
            previous_command = arm_target
            previous_timestamp = float(timestamp)
        LOGGER.info("Replay complete; slew-limited frames=%d", limited_count)


def replay_dataset(
    trajectories: list[Trajectory],
    robot: Any,
    hand: Any,
    *,
    time_scale: float,
    max_joint_speed_rad_s: float,
    disable_slew_limit: bool,
    repeat: int,
    transition_duration_s: float,
) -> None:
    """Replay every episode in dataset order, repeating the complete sequence."""

    if not trajectories:
        raise ValueError("Dataset contains no episodes to replay")
    total = len(trajectories)
    for repetition in range(repeat):
        for position, trajectory in enumerate(trajectories):
            if repetition > 0 or position > 0:
                _move_to_position(
                    robot,
                    hand,
                    trajectory.actions[0, :6],
                    trajectory.actions[0, 6:],
                    duration_s=transition_duration_s,
                    max_joint_speed_rad_s=max_joint_speed_rad_s,
                    label=f"start of episode {trajectory.episode_index}",
                )
            LOGGER.info(
                "Dataset pass %d/%d: episode %d (%d/%d)",
                repetition + 1,
                repeat,
                trajectory.episode_index,
                position + 1,
                total,
            )
            replay_trajectory(
                trajectory,
                robot,
                hand,
                time_scale=time_scale,
                max_joint_speed_rad_s=max_joint_speed_rad_s,
                disable_slew_limit=disable_slew_limit,
                repeat=1,
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--episode-index", type=int, default=None)
    parser.add_argument(
        "--all-episodes",
        action="store_true",
        help="Replay all dataset episodes in index order instead of one episode",
    )
    parser.add_argument("--config", default=None, help="Hardware profile TOML")
    parser.add_argument("--transport", choices=("rs485", "can"), default=None)
    parser.add_argument("--modbus", default=None, help="Override hand.linkerhand.modbus")
    parser.add_argument("--can", default=None, help="Override hand.linkerhand.can")
    parser.add_argument("--preview-only", action="store_true", help="Load and summarize; do not connect hardware")
    parser.add_argument("--confirm-motion", action="store_true", help="Required for real hardware movement")
    parser.add_argument("--no-auto-power-on", action="store_true")
    parser.add_argument("--time-scale", type=float, default=1.0, help="1.0 uses recorded timestamps")
    parser.add_argument("--max-joint-speed-rad-s", type=float, default=DEFAULT_MAX_JOINT_SPEED_RAD_S)
    parser.add_argument("--disable-slew-limit", action="store_true")
    parser.add_argument("--o6-speed", type=int, default=DEFAULT_O6_SPEED)
    parser.add_argument("--initial-move-duration-s", type=float, default=DEFAULT_INITIAL_MOVE_DURATION_S)
    parser.add_argument("--first-action-move-duration-s", type=float, default=DEFAULT_FIRST_ACTION_MOVE_DURATION_S)
    parser.add_argument(
        "--repeat", type=int, default=1,
        help="Number of times to play the selected episode or complete dataset",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.all_episodes and args.episode_index is not None:
        raise SystemExit("Use either --all-episodes or --episode-index, not both")
    if args.preview_only == args.confirm_motion:
        raise SystemExit("Choose exactly one: --preview-only or --confirm-motion")
    if args.preview_only and (args.no_auto_power_on or args.disable_slew_limit):
        raise SystemExit("Motion-control options cannot be used with --preview-only")
    if args.time_scale <= 0 or not math.isfinite(args.time_scale):
        raise SystemExit("--time-scale must be finite and positive")
    if args.max_joint_speed_rad_s <= 0 or not math.isfinite(args.max_joint_speed_rad_s):
        raise SystemExit("--max-joint-speed-rad-s must be finite and positive")
    if args.o6_speed < 10 or args.o6_speed > 255:
        raise SystemExit("--o6-speed must be in [10, 255]")
    if args.initial_move_duration_s <= 0 or args.first_action_move_duration_s <= 0:
        raise SystemExit("Move durations must be positive")
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    try:
        hardware = load_hardware_config(args.config)
        if hardware.hand.model.upper() != "O6" or hardware.hand.joint_count != 6:
            raise ValueError("CR3/O6 trajectory replay requires a six-joint O6 hand")
        dataset_dir = args.data_dir.expanduser()
        if not dataset_dir.is_absolute():
            dataset_dir = REPO_ROOT / dataset_dir
        if args.all_episodes:
            episode_paths = _episode_paths(dataset_dir)
            if not episode_paths:
                raise FileNotFoundError(f"No parquet episodes found under {dataset_dir / 'data'}")
            trajectories = [
                load_trajectory(
                    dataset_dir,
                    episode_index,
                    hand_min=hardware.hand.state_min,
                    hand_max=hardware.hand.state_max,
                )
                for episode_index, _path in episode_paths
            ]
            LOGGER.info("Loaded complete dataset: %d episodes", len(trajectories))
        else:
            trajectories = [
                load_trajectory(
                    dataset_dir,
                    0 if args.episode_index is None else args.episode_index,
                    hand_min=hardware.hand.state_min,
                    hand_max=hardware.hand.state_max,
                )
            ]
        first_trajectory = trajectories[0]
    except (RuntimeError, ValueError, OSError) as exc:
        LOGGER.error("Trajectory replay failed: %s", exc)
        return 1

    if args.preview_only:
        LOGGER.info("Preview-only: trajectory validated; no hardware was connected")
        return 0

    try:
        if (args.transport or hardware.hand.transport) == "rs485":
            _patch_pymodbus_slave_argument()
        LinkerHandApi = _load_hand_api()
        hand_kwargs = hardware.hand.api_kwargs(
            transport=args.transport, modbus=args.modbus, can=args.can
        )
        robot = hardware.create_nrc_interface()
        hand_api = None
        servo_opened = False
        powered_by_client = False
        try:
            LOGGER.info("Connecting CR3 %s from %s", hardware.nrc.ip, hardware.source)
            robot.connect()
            hand_endpoint = hand_kwargs["modbus"] if hand_kwargs["modbus"] != "None" else hand_kwargs["can"]
            LOGGER.info("Connecting %s LinkerHand %s via %s", hardware.hand.side, hardware.hand.model, hand_endpoint)
            hand_api = LinkerHandApi(**hand_kwargs)
            if hand_api.hand_type != hardware.hand.side or str(hand_api.hand_joint).upper() != "O6":
                raise RuntimeError(f"Unexpected LinkerHand: {hand_api.hand_type}/{hand_api.hand_joint}")
            hand_api.set_speed([args.o6_speed] * hardware.hand.joint_count)

            from vendor.nrc_interface.interface import SERVO_RUNNING

            if robot.get_servo_state() != SERVO_RUNNING:
                if args.no_auto_power_on:
                    raise RuntimeError("CR3 is not running and --no-auto-power-on was specified")
                LOGGER.info("CR3 is not running; powering it on")
                robot.power_on()
                powered_by_client = True
            if robot.get_servo_state() != SERVO_RUNNING:
                raise RuntimeError("CR3 is not in running state")

            robot.open_servoj()
            servo_opened = True
            _move_to_position(
                robot,
                hand_api,
                np.asarray(INITIAL_ROBOT_POSITION[:6]),
                np.asarray(INITIAL_HAND_POSITION),
                duration_s=args.initial_move_duration_s,
                max_joint_speed_rad_s=args.max_joint_speed_rad_s,
                label="initial position",
            )
            _move_to_position(
                robot,
                hand_api,
                first_trajectory.actions[0, :6],
                first_trajectory.actions[0, 6:],
                duration_s=args.first_action_move_duration_s,
                max_joint_speed_rad_s=args.max_joint_speed_rad_s,
                label="first recorded action",
            )
            if args.all_episodes:
                replay_dataset(
                    trajectories,
                    robot,
                    hand_api,
                    time_scale=args.time_scale,
                    max_joint_speed_rad_s=args.max_joint_speed_rad_s,
                    disable_slew_limit=args.disable_slew_limit,
                    repeat=args.repeat,
                    transition_duration_s=args.first_action_move_duration_s,
                )
            else:
                replay_trajectory(
                    first_trajectory,
                    robot,
                    hand_api,
                    time_scale=args.time_scale,
                    max_joint_speed_rad_s=args.max_joint_speed_rad_s,
                    disable_slew_limit=args.disable_slew_limit,
                    repeat=args.repeat,
                )
            return 0
        except KeyboardInterrupt:
            LOGGER.info("Replay stopped by user")
            return 0
        finally:
            if servo_opened:
                try:
                    _move_to_position(
                        robot,
                        hand_api,
                        np.asarray(INITIAL_ROBOT_POSITION[:6]),
                        np.asarray(INITIAL_HAND_POSITION),
                        duration_s=args.initial_move_duration_s,
                        max_joint_speed_rad_s=args.max_joint_speed_rad_s,
                        label="final initial position",
                    )
                except Exception:
                    LOGGER.exception("Failed to return to initial position")
                try:
                    robot.close_servoj()
                except Exception:
                    LOGGER.exception("Failed to close CR3 ServoJ")
            if hand_api is not None:
                _close_hand(hand_api)
            if powered_by_client:
                try:
                    robot.power_off()
                except Exception:
                    LOGGER.exception("Failed to power off CR3")
            robot.disconnect()
    except (RuntimeError, ValueError, OSError) as exc:
        LOGGER.error("Trajectory replay failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
