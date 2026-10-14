#!/usr/bin/env python3
"""Record a small CR3 TCP rectangle as a LeRobot v2.1 dataset.

The default motion is deliberately conservative:

* the current CR3 TCP pose is used as the rectangle's first corner;
* the TCP keeps its current orientation;
* the rectangle is drawn in the XY plane;
* the O6 hand is read for logging but never commanded;
* the generated ``action`` remains the existing 12-D CR3/O6 joint contract,
  so ``core/openpi/cr3_o6/replay_trajectory.py`` can replay the result.

Preview the geometry without connecting to hardware:

    python ptp/record_rectangle_v21.py --preview-only \
        --start-pose 350 0 250 0 1.57 0 0

Record from the robot's current pose. Real motion requires the explicit flag:

    ./scripts/run_nrc.sh python ptp/record_rectangle_v21.py --confirm-motion

The script writes a video-free LeRobot v2.1 dataset by default to
``dataset/replay/ptp_rectangle_v21``.  It also stores actual and target TCP
poses as extra numeric features and writes the generated waypoint plan beside
the dataset.
"""

from __future__ import annotations

import argparse
import functools
import inspect
import json
import logging
import math
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



LOGGER = logging.getLogger("record_rectangle_v21")

FPS = 20.0
ARM_DIM = 6
HAND_DIM = 6
TCP_DIM = 6
ACTION_DIM = ARM_DIM + HAND_DIM
DEFAULT_WIDTH_MM = 50.0
DEFAULT_HEIGHT_MM = 50.0
DEFAULT_SEGMENT_DURATION_S = 2.0
DEFAULT_DWELL_S = 0.5
DEFAULT_MAX_IK_STEP_RAD = 0.5

ARM_STATE_NAMES = [
    "cr3.q1.rad",
    "cr3.q2.rad",
    "cr3.q3.rad",
    "cr3.q4.rad",
    "cr3.q5.rad",
    "cr3.q6.rad",
]
ARM_ACTION_NAMES = [
    "cr3.target_q1.rad",
    "cr3.target_q2.rad",
    "cr3.target_q3.rad",
    "cr3.target_q4.rad",
    "cr3.target_q5.rad",
    "cr3.target_q6.rad",
]
HAND_STATE_NAMES = [
    "o6.thumb_flex.position",
    "o6.thumb_yaw.position",
    "o6.index_flex.position",
    "o6.middle_flex.position",
    "o6.ring_flex.position",
    "o6.little_flex.position",
]
HAND_ACTION_NAMES = [
    "o6.thumb_flex.command",
    "o6.thumb_yaw.command",
    "o6.index_flex.command",
    "o6.middle_flex.command",
    "o6.ring_flex.command",
    "o6.little_flex.command",
]
TCP_NAMES = [
    "x_mm",
    "y_mm",
    "z_mm",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
]


def _finite_vector(values: Iterable[float], length: int, name: str) -> np.ndarray:
    array = np.asarray(list(values), dtype=np.float64)
    if array.shape != (length,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain {length} finite values; got {array}")
    return array


def _parse_vector(values: Sequence[str] | None, length: int, name: str) -> np.ndarray | None:
    if values is None:
        return None
    try:
        return _finite_vector((float(value) for value in values), length, name)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid --{name.replace('_', '-')}: expected {length} numbers") from exc


def _patch_pymodbus_slave_argument() -> None:
    """Support both pymodbus versions used by the vendored O6 SDK."""

    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError:
        return

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
    sdk_root = REPO_ROOT / "vendor" / "actuator" / "linkerhand-python-sdk"
    if str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))
    try:
        from LinkerHand.linker_hand_api import LinkerHandApi
    except ImportError as exc:
        raise RuntimeError(f"Could not import the vendored LinkerHand SDK at {sdk_root}") from exc
    return LinkerHandApi


def _close_hand(hand_api: Any) -> None:
    if hand_api is None:
        return
    hand = getattr(hand_api, "hand", None)
    for method_name in ("close", "close_can_interface"):
        method = getattr(hand, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                LOGGER.exception("Failed to close O6 backend")
            return


def _connect_hand(hardware: Any, args: argparse.Namespace) -> Any:
    _patch_pymodbus_slave_argument()
    LinkerHandApi = _load_hand_api()
    transport = args.transport or hardware.hand.transport
    kwargs = hardware.hand.api_kwargs(
        transport=transport,
        modbus=args.modbus,
        can=args.can,
    )
    hand_api = LinkerHandApi(**kwargs)
    if (
        hand_api.hand_type != hardware.hand.side
        or str(hand_api.hand_joint).upper() != hardware.hand.model.upper()
    ):
        _close_hand(hand_api)
        raise RuntimeError(
            f"Unexpected hand configuration: {hand_api.hand_type!r}/{hand_api.hand_joint!r}"
        )
    return hand_api


def _read_hand_state(hand_api: Any, hardware: Any) -> np.ndarray:
    values = _finite_vector(hand_api.get_state(), HAND_DIM, "O6 state")
    if np.any(values < hardware.hand.state_min) or np.any(values > hardware.hand.state_max):
        raise RuntimeError(f"O6 state outside configured range: {values.tolist()}")
    return values


def _rectangle_waypoints(
    start_pose: np.ndarray,
    width_mm: float,
    height_mm: float,
    plane: str,
    direction: str,
) -> list[np.ndarray]:
    if plane == "xy":
        first = np.array([width_mm, 0.0, 0.0])
        second = np.array([0.0, height_mm, 0.0])
    elif plane == "xz":
        first = np.array([width_mm, 0.0, 0.0])
        second = np.array([0.0, 0.0, height_mm])
    elif plane == "yz":
        first = np.array([0.0, width_mm, 0.0])
        second = np.array([0.0, 0.0, height_mm])
    else:  # pragma: no cover - argparse restricts this
        raise ValueError(f"Unsupported plane {plane!r}")

    if direction == "cw":
        second = -second
    p0 = start_pose.copy()
    p1 = p0.copy()
    p1[:3] += first
    p2 = p1.copy()
    p2[:3] += second
    p3 = p0.copy()
    p3[:3] += second
    return [p0, p1, p2, p3, p0.copy()]


def _sample_waypoint_plan(
    waypoints: list[np.ndarray],
    *,
    fps: float,
    segment_duration_s: float,
    dwell_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return target TCP poses, timestamps, and waypoint ids."""

    poses = [waypoints[0].copy()]
    timestamps = [0.0]
    waypoint_ids = [0]
    current_time = 0.0

    for segment_index, (p0, p1) in enumerate(zip(waypoints[:-1], waypoints[1:])):
        steps = max(1, round(segment_duration_s * fps))
        for step in range(1, steps + 1):
            alpha = step / steps
            poses.append((1.0 - alpha) * p0 + alpha * p1)
            current_time += 1.0 / fps
            timestamps.append(current_time)
            waypoint_ids.append(segment_index + 1)

        dwell_steps = max(0, round(dwell_s * fps))
        for _ in range(dwell_steps):
            poses.append(p1.copy())
            current_time += 1.0 / fps
            timestamps.append(current_time)
            waypoint_ids.append(segment_index + 1)

    return (
        np.asarray(poses, dtype=np.float64),
        np.asarray(timestamps, dtype=np.float64),
        np.asarray(waypoint_ids, dtype=np.int64),
    )


def _fixed_list(values: np.ndarray, dtype: pa.DataType) -> pa.Array:
    values = np.asarray(values)
    if values.ndim != 2:
        raise ValueError(f"Expected a 2-D array for fixed list, got {values.shape}")
    flat = pa.array(values.reshape(-1).tolist(), type=dtype)
    return pa.FixedSizeListArray.from_arrays(flat, values.shape[1])


def _feature_stats(values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values)
    if values.ndim == 1:
        values = values[:, None]
    if not np.all(np.isfinite(values)):
        raise ValueError("Cannot write statistics for NaN/Inf values")
    return {
        "min": np.min(values, axis=0).tolist(),
        "max": np.max(values, axis=0).tolist(),
        "mean": np.mean(values, axis=0).tolist(),
        "std": np.std(values, axis=0).tolist(),
        "count": [int(values.shape[0])],
    }


def _feature_info() -> dict[str, Any]:
    return {
        "observation.state": {
            "dtype": "float32",
            "shape": [ACTION_DIM],
            "names": ARM_STATE_NAMES + HAND_STATE_NAMES,
        },
        "action": {
            "dtype": "float32",
            "shape": [ACTION_DIM],
            "names": ARM_ACTION_NAMES + HAND_ACTION_NAMES,
        },
        "observation.tcp_pose": {
            "dtype": "float32",
            "shape": [TCP_DIM],
            "names": TCP_NAMES,
        },
        "target.tcp_pose": {
            "dtype": "float32",
            "shape": [TCP_DIM],
            "names": TCP_NAMES,
        },
        "waypoint_index": {"dtype": "int64", "shape": [1], "names": None},
        "timestamp": {"dtype": "float32", "shape": [1], "names": None},
        "frame_index": {"dtype": "int64", "shape": [1], "names": None},
        "episode_index": {"dtype": "int64", "shape": [1], "names": None},
        "index": {"dtype": "int64", "shape": [1], "names": None},
        "task_index": {"dtype": "int64", "shape": [1], "names": None},
    }


def _write_v21_dataset(
    output_dir: Path,
    *,
    state: np.ndarray,
    action: np.ndarray,
    actual_tcp: np.ndarray,
    target_tcp: np.ndarray,
    waypoint_ids: np.ndarray,
    timestamps: np.ndarray,
    task: str,
    robot_type: str,
    fps: float,
    overwrite: bool,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"Output directory is not empty: {output_dir}; use --overwrite to replace it"
            )
        shutil.rmtree(output_dir)

    data_dir = output_dir / "data" / "chunk-000"
    meta_dir = output_dir / "meta"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    n = len(state)
    episode_index = np.zeros(n, dtype=np.int64)
    frame_index = np.arange(n, dtype=np.int64)
    global_index = frame_index.copy()
    task_index = np.zeros(n, dtype=np.int64)

    table = pa.table(
        {
            "observation.state": _fixed_list(state.astype(np.float32), pa.float32()),
            "action": _fixed_list(action.astype(np.float32), pa.float32()),
            "observation.tcp_pose": _fixed_list(actual_tcp.astype(np.float32), pa.float32()),
            "target.tcp_pose": _fixed_list(target_tcp.astype(np.float32), pa.float32()),
            "waypoint_index": pa.array(waypoint_ids, type=pa.int64()),
            "timestamp": pa.array(timestamps.astype(np.float32), type=pa.float32()),
            "frame_index": pa.array(frame_index, type=pa.int64()),
            "episode_index": pa.array(episode_index, type=pa.int64()),
            "index": pa.array(global_index, type=pa.int64()),
            "task_index": pa.array(task_index, type=pa.int64()),
        }
    )
    pq.write_table(table, data_dir / "episode_000000.parquet", compression="zstd")

    feature_info = _feature_info()
    info = {
        "codebase_version": "v2.1",
        "robot_type": robot_type,
        "total_episodes": 1,
        "total_frames": n,
        "total_tasks": 1,
        "total_videos": 0,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": int(fps),
        "splits": {"train": "0:1"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": feature_info,
    }
    (meta_dir / "info.json").write_text(json.dumps(info, indent=2) + "\n")
    (meta_dir / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": task}, ensure_ascii=False) + "\n"
    )
    (meta_dir / "episodes.jsonl").write_text(
        json.dumps({"episode_index": 0, "tasks": [task], "length": n}, ensure_ascii=False) + "\n"
    )

    stats_values = {
        "observation.state": state,
        "action": action,
        "observation.tcp_pose": actual_tcp,
        "target.tcp_pose": target_tcp,
        "waypoint_index": waypoint_ids,
        "timestamp": timestamps,
        "frame_index": frame_index,
        "episode_index": episode_index,
        "index": global_index,
        "task_index": task_index,
    }
    stats = {key: _feature_stats(value) for key, value in stats_values.items()}
    (meta_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    (meta_dir / "episodes_stats.jsonl").write_text(
        json.dumps({"episode_index": 0, "stats": stats}, ensure_ascii=False) + "\n"
    )


def _build_plan_summary(
    waypoints: list[np.ndarray],
    *,
    width_mm: float,
    height_mm: float,
    plane: str,
    direction: str,
    segment_duration_s: float,
    dwell_s: float,
    fps: float,
    start_source: str,
) -> dict[str, Any]:
    poses, timestamps, waypoint_ids = _sample_waypoint_plan(
        waypoints,
        fps=fps,
        segment_duration_s=segment_duration_s,
        dwell_s=dwell_s,
    )
    return {
        "robot_type": "cr3_o6",
        "start_source": start_source,
        "plane": plane,
        "direction": direction,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "segment_duration_s": segment_duration_s,
        "dwell_s": dwell_s,
        "fps": fps,
        "waypoints": [pose.tolist() for pose in waypoints],
        "sampled_frames": int(len(poses)),
        "duration_s": float(timestamps[-1]),
        "waypoint_frame_ranges": {
            str(index): [
                int(np.flatnonzero(waypoint_ids == index)[0]),
                int(np.flatnonzero(waypoint_ids == index)[-1]),
            ]
            for index in range(len(waypoints))
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Hardware TOML path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "dataset" / "replay" / "ptp_rectangle_v21",
    )
    parser.add_argument("--width-mm", type=float, default=DEFAULT_WIDTH_MM)
    parser.add_argument("--height-mm", type=float, default=DEFAULT_HEIGHT_MM)
    parser.add_argument("--plane", choices=("xy", "xz", "yz"), default="xy")
    parser.add_argument("--direction", choices=("ccw", "cw"), default="ccw")
    parser.add_argument("--segment-duration-s", type=float, default=DEFAULT_SEGMENT_DURATION_S)
    parser.add_argument("--dwell-s", type=float, default=DEFAULT_DWELL_S)
    parser.add_argument("--fps", type=int, default=int(FPS))
    parser.add_argument("--max-ik-step-rad", type=float, default=DEFAULT_MAX_IK_STEP_RAD)
    parser.add_argument(
        "--start-pose",
        nargs=7,
        metavar=("X", "Y", "Z", "R", "P", "YAW", "EXT"),
        help="TCP pose [mm, mm, mm, rad, rad, rad, external_axis], preview or checked start",
    )
    parser.add_argument(
        "--hand-state",
        nargs=6,
        metavar=("H1", "H2", "H3", "H4", "H5", "H6"),
        help="O6 state for preview; motion mode reads it from hardware",
    )
    parser.add_argument("--transport", choices=("rs485", "can"), default=None)
    parser.add_argument("--modbus", default=None, help="Override O6 RS485 device")
    parser.add_argument("--can", default=None, help="Override O6 CAN device")
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--confirm-motion", action="store_true")
    parser.add_argument("--no-auto-power-on", action="store_true")
    parser.add_argument("--power-off-on-exit", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    if args.preview_only == args.confirm_motion:
        raise SystemExit("Choose exactly one: --preview-only or --confirm-motion")
    if args.width_mm <= 0 or args.height_mm <= 0 or args.width_mm > 200 or args.height_mm > 200:
        raise SystemExit("Rectangle dimensions must be in (0, 200] mm")
    if args.segment_duration_s <= 0 or args.dwell_s < 0:
        raise SystemExit("Segment duration must be positive and dwell must be non-negative")
    if args.fps <= 0:
        raise SystemExit("--fps must be positive")
    if args.max_ik_step_rad <= 0 or not math.isfinite(args.max_ik_step_rad):
        raise SystemExit("--max-ik-step-rad must be finite and positive")


def _preview(args: argparse.Namespace) -> int:
    start_pose = _parse_vector(args.start_pose, 7, "start_pose")
    if start_pose is None:
        raise SystemExit("--preview-only requires --start-pose")
    waypoints = _rectangle_waypoints(
        start_pose[:6],
        args.width_mm,
        args.height_mm,
        args.plane,
        args.direction,
    )
    # Reattach the external axis to every waypoint.
    waypoints = [np.r_[pose, start_pose[6]] for pose in waypoints]
    summary = _build_plan_summary(
        waypoints,
        width_mm=args.width_mm,
        height_mm=args.height_mm,
        plane=args.plane,
        direction=args.direction,
        segment_duration_s=args.segment_duration_s,
        dwell_s=args.dwell_s,
        fps=args.fps,
        start_source="--start-pose",
    )
    print(json.dumps(summary, indent=2))
    return 0


def _record(args: argparse.Namespace) -> int:
    try:
        from config.hardware import load_hardware_config
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "CR3 recording requires the project's Python 3.11+ environment; "
            "use --preview-only outside that environment"
        ) from exc
    try:
        from vendor.nrc_interface.interface import SERVO_RUNNING
    except ImportError as exc:
        raise RuntimeError(
            "CR3 recording requires the Python 3.12 NRC environment; "
            "use --preview-only outside that environment"
        ) from exc

    hardware = load_hardware_config(args.config)
    robot = None
    hand_api = None
    servo_opened = False
    powered_by_client = False
    try:
        robot = hardware.create_nrc_interface()
        robot.connect()
        current_q = _finite_vector(robot.get_joint_positions(), ARM_DIM, "CR3 joint state")
        current_tcp7 = _finite_vector(robot.get_tcp_pose(), 7, "CR3 TCP pose")
        configured_start = _parse_vector(args.start_pose, 7, "start_pose")
        if configured_start is not None:
            position_offset = float(np.linalg.norm(current_tcp7[:3] - configured_start[:3]))
            if position_offset > 5.0:
                raise RuntimeError(
                    f"Current TCP is {position_offset:.1f} mm from --start-pose; refusing to move implicitly"
                )
            start_tcp7 = configured_start
        else:
            start_tcp7 = current_tcp7

        hand_api = _connect_hand(hardware, args)
        hand_initial = _read_hand_state(hand_api, hardware)

        waypoints = _rectangle_waypoints(
            start_tcp7[:6],
            args.width_mm,
            args.height_mm,
            args.plane,
            args.direction,
        )
        waypoints = [np.r_[pose, start_tcp7[6]] for pose in waypoints]
        target_tcp, timestamps, waypoint_ids = _sample_waypoint_plan(
            waypoints,
            fps=args.fps,
            segment_duration_s=args.segment_duration_s,
            dwell_s=args.dwell_s,
        )

        LOGGER.info(
            "Rectangle: plane=%s direction=%s size=%.1f x %.1f mm, %d frames, %.2f s",
            args.plane,
            args.direction,
            args.width_mm,
            args.height_mm,
            len(target_tcp),
            float(timestamps[-1]),
        )
        for index, pose in enumerate(waypoints):
            LOGGER.info("Waypoint %d TCP [mm, rad, ext]: %s", index, np.round(pose, 4).tolist())

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

        states: list[np.ndarray] = []
        actions: list[np.ndarray] = []
        actual_tcps: list[np.ndarray] = []
        target_tcps: list[np.ndarray] = []
        recorded_waypoint_ids: list[int] = []
        recorded_timestamps: list[float] = []
        previous_command = current_q.copy()
        started = time.monotonic()

        for frame_index, (target_pose7, timestamp, waypoint_id) in enumerate(
            zip(target_tcp, timestamps, waypoint_ids, strict=True)
        ):
            deadline = started + float(timestamp)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)

            if frame_index == 0:
                target_q = current_q.copy()
            else:
                target_q = _finite_vector(
                    robot.convert_pose_to_joints(target_pose7.tolist()),
                    ARM_DIM,
                    "IK target",
                )
                step = float(np.max(np.abs(target_q - previous_command)))
                if step > args.max_ik_step_rad:
                    raise RuntimeError(
                        f"IK jump at frame {frame_index}: {step:.4f} rad > "
                        f"--max-ik-step-rad={args.max_ik_step_rad:.4f}"
                    )

            # Deliberately send only CR3 commands. No O6 command is issued.
            robot.send_joint_positions(target_q.tolist())
            actual_q = _finite_vector(robot.get_joint_positions(), ARM_DIM, "CR3 feedback")
            actual_tcp7 = _finite_vector(robot.get_tcp_pose(), 7, "TCP feedback")
            actual_hand = _read_hand_state(hand_api, hardware)

            states.append(np.r_[actual_q, actual_hand])
            # Keep the recorded O6 command constant so the existing 12-D replay
            # format remains valid without making the hand move during capture.
            actions.append(np.r_[target_q, hand_initial])
            actual_tcps.append(actual_tcp7[:6])
            target_tcps.append(target_pose7[:6])
            recorded_waypoint_ids.append(int(waypoint_id))
            recorded_timestamps.append(float(timestamp))
            previous_command = target_q

        state_array = np.asarray(states, dtype=np.float64)
        action_array = np.asarray(actions, dtype=np.float64)
        actual_tcp_array = np.asarray(actual_tcps, dtype=np.float64)
        target_tcp_array = np.asarray(target_tcps, dtype=np.float64)
        timestamp_array = np.asarray(recorded_timestamps, dtype=np.float64)
        waypoint_array = np.asarray(recorded_waypoint_ids, dtype=np.int64)

        output_dir = args.output_dir.expanduser().resolve()
        _write_v21_dataset(
            output_dir,
            state=state_array,
            action=action_array,
            actual_tcp=actual_tcp_array,
            target_tcp=target_tcp_array,
            waypoint_ids=waypoint_array,
            timestamps=timestamp_array,
            task="Move the CR3 TCP around a small rectangle while holding the O6 hand still.",
            robot_type="cr3_o6",
            fps=args.fps,
            overwrite=args.overwrite,
        )
        plan_summary = _build_plan_summary(
            waypoints,
            width_mm=args.width_mm,
            height_mm=args.height_mm,
            plane=args.plane,
            direction=args.direction,
            segment_duration_s=args.segment_duration_s,
            dwell_s=args.dwell_s,
            fps=args.fps,
            start_source="robot.get_tcp_pose()",
        )
        plan_summary["recorded_o6_state"] = hand_initial.tolist()
        plan_summary["recorded_frames"] = int(len(state_array))
        (output_dir / "ptp_plan.json").write_text(json.dumps(plan_summary, indent=2) + "\n")
        (output_dir / "README.md").write_text(
            "# CR3/O6 PTP rectangle LeRobot v2.1 dataset\n\n"
            "Generated by `ptp/record_rectangle_v21.py`. The CR3 follows a small "
            "TCP rectangle while the O6 hand is read but never commanded. "
            "`action` contains absolute CR3 joint targets followed by the constant "
            "O6 state, so the existing joint replay tool can consume it.\n"
        )
        LOGGER.info("Wrote LeRobot v2.1 dataset to %s", output_dir)
        return 0
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
        _close_hand(hand_api)


def main() -> int:
    args = _parse_args()
    _validate_args(args)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    try:
        if args.preview_only:
            return _preview(args)
        return _record(args)
    except (RuntimeError, ValueError, OSError) as exc:
        LOGGER.error("Rectangle recording failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
