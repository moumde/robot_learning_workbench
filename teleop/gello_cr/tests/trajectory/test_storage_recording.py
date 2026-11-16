import json
import math
import threading
import time
from dataclasses import replace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from teleop.gello_cr.trajectory import (
    TrajectoryFrame,
    TrajectoryRecorder,
    TrajectoryStore,
    make_trajectory,
    preview_trajectory,
    validate_trajectory,
)
from teleop.gello_cr.trajectory.adapters import LegacyJsonAdapter, LeRobotTrajectoryAdapter


def trajectory():
    return make_trajectory(
        "pick demo",
        [
            TrajectoryFrame(
                0.0,
                robot_joint_state=(0.1,) * 6,
                robot_joint_command=(0.2,) * 6,
                hand_state=(100.0,) * 6,
            ),
            TrajectoryFrame(
                1.0,
                robot_joint_state=(0.2,) * 6,
                robot_joint_command=(0.4,) * 6,
                hand_state=(200.0,) * 6,
            ),
        ],
        fps=1.0,
    )


def test_store_round_trip_list_preview_delete(tmp_path):
    store = TrajectoryStore(tmp_path)
    value = trajectory()
    directory = store.save(value)
    assert (directory / "trajectory.parquet").is_file()
    assert store.load(value.metadata.trajectory_id) == value
    assert store.list() == [value.metadata]
    assert preview_trajectory(value)["max_joint_velocity_rad_s"] == pytest.approx([0.2] * 6)
    store.delete(value.metadata.trajectory_id)
    assert store.list() == []


@pytest.mark.parametrize(
    "frame",
    [
        TrajectoryFrame(math.nan, robot_joint_state=(0.0,) * 6),
        TrajectoryFrame(1.0, robot_joint_state=(0.0,) * 5),
        TrajectoryFrame(1.0, robot_joint_command=(math.inf,) * 6),
        TrajectoryFrame(1.0, hand_command=(0.0,) * 7),
        TrajectoryFrame(0.0, robot_joint_state=(0.0,) * 6),
    ],
)
def test_invalid_frames_rejected_before_storage(tmp_path, frame):
    value = trajectory()
    value = replace(value, frames=(value.frames[0], frame))
    with pytest.raises(ValueError):
        TrajectoryStore(tmp_path).save(value)
    assert not list(tmp_path.iterdir())


def test_joint_limits_checked_when_configured():
    with pytest.raises(ValueError, match="joint limits"):
        validate_trajectory(trajectory(), [(-0.1, 0.1)] * 6)


def test_recorder_records_state_and_command_then_cancel():
    sampled = threading.Event()

    class Source:
        count = 0

        def sample(self):
            self.count += 1
            if self.count > 1:
                sampled.set()
            return TrajectoryFrame(
                time.monotonic(), robot_joint_state=(0.1,) * 6, robot_joint_command=(0.2,) * 6
            )

    recorder = TrajectoryRecorder(Source(), fps=200.0)
    recorder.start("named demo", {"source": "gello"})
    assert sampled.wait(1)
    value = recorder.stop()
    assert not recorder.recording
    assert value.metadata.frame_count >= 2
    assert value.frames[0].timestamp == 0
    assert value.frames[-1].timestamp > 0
    assert value.frames[-1].robot_joint_state != value.frames[-1].robot_joint_command
    recorder.start("discard")
    recorder.cancel()
    assert recorder.frames == ()


def test_legacy_json_import_converts_degrees_and_keeps_state_distinct(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(
        json.dumps(
            {
                "version": 3,
                "frames": [
                    {"t": 3.0, "robot_joints_deg": [90.0] * 6 + [0.0], "o6_position": [200] * 6},
                    {"t": 4.0, "robot_joints_deg": [180.0] * 6 + [0.0], "o6_position": [100] * 6},
                ],
            }
        )
    )
    value = LegacyJsonAdapter.load(path)
    assert value.frames[0].timestamp == 0
    assert value.frames[0].robot_joint_state == pytest.approx([math.pi / 2] * 6)
    assert value.frames[0].robot_joint_command is None
    assert value.metadata.source == "legacy_json"


def test_lerobot_episode_adapter_filters_episode_and_preserves_joint_actions(tmp_path):
    path = tmp_path / "episodes.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "episode_index": 0,
                    "timestamp": 0.0,
                    "observation.state": [0.1] * 6 + [100.0] * 6,
                    "action": [0.2] * 6 + [200.0] * 6,
                },
                {
                    "episode_index": 1,
                    "timestamp": 0.0,
                    "observation.state": [0.3] * 6 + [100.0] * 6,
                    "action": [0.4] * 6 + [200.0] * 6,
                },
            ]
        ),
        path,
    )
    value = LeRobotTrajectoryAdapter.load(path, 1)
    assert len(value.frames) == 1
    assert value.frames[0].robot_joint_command == (0.4,) * 6
    assert value.frames[0].robot_joint_state == (0.3,) * 6
    assert value.metadata.source == "lerobot"


def test_tcp_dataset_import_never_treats_tcp_delta_as_joint_target(tmp_path):
    path = tmp_path / "tcp.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "timestamp": 0.0,
                    "observation.state": [0.1] * 6 + [0.5] * 6 + [100.0] * 6,
                    "action": [0.01] * 6 + [200.0] * 6,
                },
            ]
        ),
        path,
    )
    value = LeRobotTrajectoryAdapter.load(path)
    assert value.frames[0].robot_joint_command is None
    assert value.frames[0].robot_joint_state == (0.1,) * 6
    assert value.frames[0].robot_tcp_command == pytest.approx([0.51] * 6)


def test_episode_without_index_column_cannot_silently_load_another_index(tmp_path):
    path = tmp_path / "single.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "timestamp": 0.0,
                    "observation.state": [0.1] * 6 + [100.0] * 6,
                    "action": [0.2] * 6 + [200.0] * 6,
                },
            ]
        ),
        path,
    )
    with pytest.raises(ValueError, match="episode_index"):
        LeRobotTrajectoryAdapter.load(path, 1)
