import json
import math

import pytest

from teleop.gello_cr.motion import MotionCoordinator, MotionExecutor, MotionSafety, MotionSource
from teleop.gello_cr.trajectory import (
    ReplayMode,
    ReplayOptions,
    TrajectoryFrame,
    TrajectoryPlayer,
    TrajectoryStore,
    make_trajectory,
)
from teleop.gello_cr.trajectory.adapters import LegacyJsonAdapter


class Hardware:
    def __init__(self):
        self.joints = (10.0, 20.0, 0.0, 0.0, 0.0, 0.0)
        self.targets = []
        self.hands = []
        self.now = 0.0
        self.stops = 0

    def joint_position(self):
        return [v * 180 / 3.141592653589793 for v in self.joints] + [0.0]

    def read_joints(self):
        return self.joints

    def open_servoj(self, *args):
        pass

    def send_servoj(self, native):
        self.joints = tuple(v * 3.141592653589793 / 180 for v in native[:6])
        self.targets.append(self.joints)
        return True

    def movej(self, native, *args):
        self.send_servoj(native)

    def stop_motion(self):
        self.stops += 1

    def send_hand(self, hand):
        self.hands.append(hand)

    def hold_hand(self):
        pass

    def check_ready(self, arm_enabled, hand_enabled):
        pass

    def wait(self, duration, stop):
        self.now += duration
        return stop.is_set()


def setup_player():
    hardware = Hardware()
    motion = MotionCoordinator(MotionExecutor(lambda: hardware))
    player = TrajectoryPlayer(motion, hardware, clock=lambda: hardware.now, wait=hardware.wait)
    return hardware, motion, player


def demo():
    return make_trajectory(
        "demo",
        [
            TrajectoryFrame(
                0.0, robot_joint_command=(1.0, 2.0, 0.0, 0.0, 0.0, 0.0), hand_command=(200.0,) * 6
            ),
            TrajectoryFrame(
                1.0, robot_joint_command=(2.0, 4.0, 0.0, 0.0, 0.0, 0.0), hand_command=(100.0,) * 6
            ),
            TrajectoryFrame(
                2.0, robot_joint_command=(3.0, 6.0, 0.0, 0.0, 0.0, 0.0), hand_command=(50.0,) * 6
            ),
        ],
        fps=1.0,
    )


def test_relative_replay_keeps_unselected_joints_at_current_start():
    hardware, motion, player = setup_player()
    player.play(
        demo(),
        ReplayOptions(
            mode=ReplayMode.RELATIVE, joint_mask=(True, False, False, False, False, False)
        ),
    )
    assert hardware.targets[-1] == pytest.approx((12.0, 20.0, 0.0, 0.0, 0.0, 0.0))
    assert hardware.hands[-1] == (50.0,) * 6
    assert motion.current_owner is None


def test_time_scale_and_repeat_use_recorded_deadlines():
    hardware, _, player = setup_player()
    player.play(
        demo(),
        ReplayOptions(mode=ReplayMode.RELATIVE, time_scale=2.0, repeat=2, hand_enabled=False),
    )
    assert hardware.now == pytest.approx(2.0)
    assert not hardware.hands


def test_hand_only_sends_no_arm_command():
    hardware, motion, player = setup_player()
    player.play(demo(), ReplayOptions(mode=ReplayMode.RELATIVE, arm_enabled=False))
    assert not hardware.targets
    assert hardware.hands
    assert motion.current_owner is None


def test_home_preemption_prevents_late_replay_commands_or_cleanup_stop():
    hardware, motion, player = setup_player()
    original = hardware.send_hand
    home = []

    def send(hand):
        original(hand)
        if not home:
            home.append(motion.acquire(MotionSource.HOME, allow_preempt=True))

    hardware.send_hand = send
    player.play(demo(), ReplayOptions(mode=ReplayMode.RELATIVE))
    assert home[0].active
    assert len(hardware.targets) == 1
    assert hardware.stops == 1


def test_legacy_joint_selection_survives_storage_and_default_playback(tmp_path):
    path = tmp_path / "wrist.json"
    path.write_text(
        json.dumps(
            {
                "version": 3,
                "robot_joint_indices": [6],
                "frames": [
                    {"t": 0.0, "robot_joints_deg": [0.0] * 7},
                    {"t": 1.0, "robot_joints_deg": [10.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0]},
                ],
            }
        )
    )
    store = TrajectoryStore(tmp_path / "library")
    imported = LegacyJsonAdapter.load(path)
    store.save(imported)
    value = store.load(imported.metadata.trajectory_id)
    hardware, _, player = setup_player()
    player.play(value, ReplayOptions(hand_enabled=False))

    assert hardware.targets[-1] == pytest.approx((10.0, 20.0, 0.0, 0.0, 0.0, math.radians(20.0)))
    assert all(target[0] == 10.0 for target in hardware.targets)


def test_absolute_transition_obeys_speed_limit_before_sending_targets():
    hardware, motion, player = setup_player()
    value = make_trajectory("far start", [TrajectoryFrame(0.0, robot_joint_command=(0.0,) * 6)])

    with pytest.raises(ValueError, match="transition joint speed"):
        player.play(
            value,
            ReplayOptions(mode=ReplayMode.ABSOLUTE, hand_enabled=False),
            max_joint_speed_rad_s=1.0,
        )

    assert not hardware.targets
    assert motion.current_owner is None


def test_absolute_replay_interpolates_from_current_pose_before_recorded_frames():
    hardware, motion, player = setup_player()
    hardware.joints = (0.0,) * 6
    player.play(
        demo(), ReplayOptions(mode=ReplayMode.ABSOLUTE, hand_enabled=False, transition_s=2.0)
    )
    assert hardware.now == pytest.approx(4.0)
    assert hardware.targets[0][:2] == pytest.approx((0.005, 0.01))
    assert hardware.targets[-1][:2] == pytest.approx((3.0, 6.0))
    assert motion.current_owner is None


def test_rejected_arm_command_faults_instead_of_silently_finishing():
    hardware, motion, player = setup_player()
    hardware.send_servoj = lambda _target: False
    with pytest.raises(RuntimeError, match="not accepted"):
        player.play(demo(), ReplayOptions())
    assert not hardware.hands
    assert motion.current_owner is None


def test_arm_only_stop_never_sends_hand_hold():
    hardware, motion, player = setup_player()
    holds = []
    hardware.hold_hand = lambda: holds.append(True)

    def wait(duration, stop):
        player.stop()
        return True

    player._wait = wait
    player.play(demo(), ReplayOptions(hand_enabled=False))
    assert not holds and not hardware.hands
    assert motion.current_owner is None


def test_motion_safety_failure_revokes_replay_before_out_of_range_target():
    hardware = Hardware()
    hardware.joints = (0.0,) * 6
    motion = MotionCoordinator(
        MotionExecutor(lambda: hardware),
        safety=MotionSafety(lambda: {"motion": {"joint_limits_rad": [(-0.1, 0.1)] * 6}}),
    )
    player = TrajectoryPlayer(motion, hardware, clock=lambda: hardware.now, wait=hardware.wait)
    with pytest.raises(RuntimeError, match="limit"):
        player.play(demo(), ReplayOptions(hand_enabled=False))
    assert motion.current_owner is None
    assert all(max(target) <= 0.1 + 1e-12 for target in hardware.targets)
