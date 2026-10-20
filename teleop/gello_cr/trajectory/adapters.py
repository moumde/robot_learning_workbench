"""Read-only import of legacy JSON and LeRobot episode Parquet rows."""

from __future__ import annotations

import json
import math
from pathlib import Path

from .model import Trajectory, TrajectoryFrame, make_trajectory
from .validation import validate_trajectory


def _ptp_pose(row, column):
    """Parent rectangle/PTP features use NRC millimetres and Euler radians."""
    pose = row.get(column)
    if pose is None:
        return None
    if len(pose) != 6:
        raise ValueError(f"{column} must contain six values")
    return tuple(float(v) / 1000.0 for v in pose[:3]) + tuple(pose[3:])


class LegacyJsonAdapter:
    @staticmethod
    def load(path) -> Trajectory:
        path = Path(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") not in (1, 2, 3):
            raise ValueError("Unsupported legacy trajectory version")
        frames = []
        raw = value["frames"]
        if not raw:
            raise ValueError("Legacy trajectory contains no frames")
        origin = float(raw[0]["t"])
        for row in raw:
            joints = row["robot_joints_deg"]
            if len(joints) != 7 or not all(math.isfinite(float(v)) for v in joints):
                raise ValueError("Legacy joints must contain seven finite values")
            frames.append(
                TrajectoryFrame(
                    float(row["t"]) - origin,
                    robot_joint_state=tuple(math.radians(float(v)) for v in joints[:6]),
                    hand_state=tuple(float(v) for v in row["o6_position"])
                    if "o6_position" in row
                    else None,
                )
            )
        indices = value.get("robot_joint_indices", [1, 2, 3, 4, 5, 6])
        if (
            not isinstance(indices, list)
            or not indices
            or any(type(i) is not int or not 1 <= i <= 6 for i in indices)
        ):
            raise ValueError("Legacy robot_joint_indices must select joints 1 to 6")
        trajectory = make_trajectory(
            path.stem,
            frames,
            fps=1.0 / float(value.get("sample_period_s", 0.05)),
            source="legacy_json",
            hand_type="o6" if all(f.hand_state is not None for f in frames) else None,
            description="Imported legacy joints: " + ",".join(str(i) for i in indices),
            joint_mask=tuple(i in indices for i in range(1, 7)),
        )
        validate_trajectory(trajectory)
        return trajectory


class LeRobotTrajectoryAdapter:
    @staticmethod
    def load(path, episode_index: int = 0, *, name=None, recording_mode=None) -> Trajectory:
        """Read one joint episode, without importing or modifying LeRobot.

        12-value joint state/action rows retain sent commands. TCP datasets
        (18-value observations) replay measured joints, never reinterpret TCP
        deltas as absolute joint commands; TCP commands remain available in
        the imported frame for inspection.
        """
        import pyarrow.dataset as ds

        if episode_index < 0:
            raise ValueError("episode_index must be nonnegative")
        path = Path(path)
        data = path / "data" if path.is_dir() and (path / "data").is_dir() else path
        table = ds.dataset(data, format="parquet")
        has_observations = "observation.state" in table.schema.names
        columns = ["timestamp", "action"]
        if has_observations:
            columns.append("observation.state")
        # Parent PTP recordings retain native NRC TCP poses as extra features.
        tcp_columns = ("observation.tcp_pose", "target.tcp_pose")
        columns += [column for column in tcp_columns if column in table.schema.names]
        if "episode_index" not in table.schema.names and episode_index != 0:
            raise ValueError("Parquet has no episode_index column; only index 0 is available")
        condition = (
            ds.field("episode_index") == int(episode_index)
            if "episode_index" in table.schema.names
            else None
        )
        rows = table.to_table(columns=columns, filter=condition).to_pylist()
        rows.sort(key=lambda row: row["timestamp"])
        if not rows:
            raise ValueError("Episode has no frames")
        mode = recording_mode or (
            "joint" if not has_observations or len(rows[0]["observation.state"]) == 12 else "tcp"
        )
        if mode not in ("joint", "tcp"):
            raise ValueError("Unknown episode recording mode")
        if mode == "tcp" and not has_observations:
            raise ValueError("TCP delta replay requires observation.state")
        first = float(rows[0]["timestamp"])
        frames = []
        for row in rows:
            state, action = row.get("observation.state"), row["action"]
            if (
                has_observations and (state is None or len(state) != (12 if mode == "joint" else 18))
            ) or len(action) != 12:
                raise ValueError("Episode state/action dimensions do not match recording mode")
            tcp = tuple(state[6:12]) if mode == "tcp" else None
            tcp_command = (
                tuple(a + b for a, b in zip(tcp, action[:6], strict=True))
                if tcp is not None
                else None
            )
            if mode == "joint":
                tcp = _ptp_pose(row, "observation.tcp_pose")
                tcp_command = _ptp_pose(row, "target.tcp_pose")
            frames.append(
                TrajectoryFrame(
                    float(row["timestamp"]) - first,
                    robot_joint_state=tuple(state[:6]) if state is not None else None,
                    robot_joint_command=tuple(action[:6]) if mode == "joint" else None,
                    robot_tcp_state=tcp,
                    robot_tcp_command=tcp_command,
                    hand_state=tuple(state[-6:]) if state is not None else None,
                    hand_command=tuple(action[-6:]),
                )
            )
        duration = frames[-1].timestamp
        trajectory = make_trajectory(
            name or f"{path.stem}_episode_{episode_index}",
            frames,
            fps=(len(frames) - 1) / duration if duration > 0 else 1.0,
            source="lerobot",
            control_mode="joint" if mode == "joint" else "joint_state",
            description="Joint command replay"
            if mode == "joint"
            else "Measured joint replay; original TCP delta commands retained as TCP targets",
        )
        validate_trajectory(trajectory)
        return trajectory
