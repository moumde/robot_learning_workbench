"""Functional interchange tests with actual Parquet and a borrowed robot session."""

from dataclasses import replace

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from core.trajectory_bridge import (
    episode_paths,
    load_shared_trajectory,
    play_in_existing_session,
    validate_session_trajectory,
)

# isort: split

from gello_cr.trajectory import (
    ReplayMode,
    ReplayOptions,
    TrajectoryFrame,
    TrajectoryStore,
    make_trajectory,
)


def write_episode(root, rows, *, version="v2.1"):
    filename = "episode_000000.parquet" if version == "v2.1" else "file-000.parquet"
    path = root / "data" / "chunk-000" / filename
    path.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return root


def row(index, *, episode=0, tcp=False):
    return {
        "episode_index": episode,
        "frame_index": index,
        "timestamp": index * 0.05,
        "observation.state": [0.1] * 6 + ([0.3, 0.2, 0.1, 0, 0, 0] if tcp else []) + [100] * 6,
        "action": ([0.002] * 6 if tcp else [0.2] * 6) + [120] * 6,
    }


def test_v3_discovers_actual_episode_indices_and_preserves_tcp_delta_semantics(tmp_path):
    root = write_episode(
        tmp_path,
        [row(0, episode=7, tcp=True), row(1, episode=7, tcp=True), row(0, episode=2, tcp=True)],
        version="v3.0",
    )
    assert [index for index, _ in episode_paths(root)] == [2, 7]
    value = load_shared_trajectory(root, 7)
    assert len(value.frames) == 2
    assert value.frames[0].robot_joint_command is None
    assert value.frames[0].robot_joint_state == (0.1,) * 6
    assert value.frames[0].robot_tcp_command[:3] == pytest.approx((0.302, 0.202, 0.102))


def test_parent_ptp_import_converts_only_tcp_translation_from_mm_to_m(tmp_path):
    from gello_cr.trajectory.adapters import LeRobotTrajectoryAdapter

    item = row(0)
    item.update(
        {
            "observation.tcp_pose": [350, -20, 250, 0, 1.57, 0],
            "target.tcp_pose": [400, 30, 260, 0, 1.57, 0],
        }
    )
    root = write_episode(tmp_path, [item])
    value = LeRobotTrajectoryAdapter.load(root, 0)
    assert value.frames[0].robot_joint_command == (0.2,) * 6
    assert value.frames[0].robot_tcp_state == pytest.approx((0.35, -0.02, 0.25, 0, 1.57, 0))
    assert value.frames[0].robot_tcp_command == pytest.approx((0.4, 0.03, 0.26, 0, 1.57, 0))
    stored = TrajectoryStore(tmp_path / "named").save(value)
    assert load_shared_trajectory(stored) == value


class Robot:
    connected = True
    servo_active = True

    def __init__(self):
        self.position = [0.7] * 6
        self.sent = []

    def get_servo_state(self):
        return 3

    def get_joint_positions(self):
        return self.position

    def send_joint_positions(self, values):
        self.position = list(values)
        self.sent.append(tuple(values))


class Clock:
    value = 0.0

    def now(self):
        return self.value

    def wait(self, duration, stop):
        self.value += max(0, duration)
        return stop.is_set()


def test_named_trajectory_retains_mask_and_reuses_open_session_across_tasks(tmp_path):
    value = make_trajectory(
        "mask",
        [
            TrajectoryFrame(0, robot_joint_command=(0.1,) * 6),
            TrajectoryFrame(0.05, robot_joint_command=(0.11,) * 6),
        ],
        hand_type=None,
        joint_mask=(True, False, False, False, False, False),
    )
    path = TrajectoryStore(tmp_path).save(value)
    assert episode_paths(path) == [(0, path / "trajectory.parquet")]
    loaded = load_shared_trajectory(path, 0)
    assert loaded.metadata.joint_mask == value.metadata.joint_mask
    robot, clock = Robot(), Clock()
    options = ReplayOptions(mode=ReplayMode.ABSOLUTE, hand_enabled=False, transition_s=2)
    for _ in range(2):
        play_in_existing_session(loaded, robot, options=options, clock=clock.now, wait=clock.wait)
        assert robot.servo_active and robot.connected
    assert robot.sent[-1] == pytest.approx((0.11, 0.7, 0.7, 0.7, 0.7, 0.7))
    assert all(command[1:] == (0.7,) * 5 for command in robot.sent)


def test_offline_plan_and_missing_hand_rejected_before_parent_sends_any_command(tmp_path):
    value = make_trajectory(
        "offline", [TrajectoryFrame(0, robot_joint_command=(0,) * 6)], hand_type=None
    )
    offline = replace(value, metadata=replace(value.metadata, planning={"offline_only": True}))
    robot = Robot()
    options = ReplayOptions(hand_enabled=False)
    with pytest.raises(ValueError, match="[Oo]ffline"):
        play_in_existing_session(offline, robot, options=options)
    with pytest.raises(ValueError, match="[Hh]and"):
        validate_session_trajectory(value, ReplayOptions())
    assert robot.sent == []


def test_parent_generic_loader_reads_joint_v3_but_rejects_tcp_delta_actions(tmp_path):
    from core.openpi.cr3_o6.replay_trajectory import load_trajectory

    joint = write_episode(tmp_path / "joint", [row(0, episode=4)], version="v3.0")
    value = load_trajectory(joint, 4)
    np.testing.assert_allclose(value.actions[0], [0.2] * 6 + [120] * 6)
    tcp = write_episode(tmp_path / "tcp", [row(0, tcp=True)])
    with pytest.raises(ValueError, match="[Ss]hared|trajectory"):
        load_trajectory(tcp, 0)


@pytest.mark.parametrize("has_observations", [True, False])
def test_parent_ptp_loader_reads_converted_tcp_values_in_native_units(tmp_path, has_observations):
    from core.openpi.cr3_o6.replay_ptp_dataset import load_ptp_trajectory

    item = row(0)
    item["target.tcp_pose"] = [350, 0, 200, 0, 1.57, 0]
    if not has_observations:
        item.pop("observation.state")
    value = load_ptp_trajectory(write_episode(tmp_path, [item]), 0, control_space="tcp")
    np.testing.assert_allclose(value.target_tcp_poses[0], [350, 0, 200, 0, 1.57, 0])
