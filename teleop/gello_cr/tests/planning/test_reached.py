import threading

import pytest

from gello_cr.motion import MotionCoordinator, MotionExecutor, MotionSource
from gello_cr.trajectory import ReplayMode, ReplayOptions, TrajectoryPlayer
from gello_cr.trajectory.planner import JointMoveRequest, RobotModel, TrajectoryPlanner
from gello_cr.trajectory.planner.reached import ReachedPolicy, ReachStatus, wait_until_reached


class Hardware:
    def __init__(self):
        self.joints = (0,) * 6
        self.targets = []
        self.now = 0.0

    def joint_position(self):
        import math

        return [math.degrees(v) for v in self.joints] + [0]

    def read_joints(self):
        return self.joints

    def open_servoj(self, *args):
        pass

    def send_servoj(self, native):
        import math

        self.joints = tuple(math.radians(v) for v in native[:6])
        self.targets.append(self.joints)
        return True

    def stop_motion(self):
        pass

    def check_ready(self, *args):
        pass

    def wait(self, duration, stop):
        self.now += duration
        return stop.is_set()


def setup():
    hardware = Hardware()
    hardware.joints = (0,) * 6
    motion = MotionCoordinator(MotionExecutor(lambda: hardware))
    lease = motion.acquire(MotionSource.POINT_MOVE, on_cancel=lambda: None)
    return hardware, motion, lease


def test_reached_requires_consecutive_actual_feedback():
    hardware, motion, lease = setup()
    sequence = iter([(0.09,) * 6, (0.1,) * 6, (0,) * 6, (0.1,) * 6, (0.1,) * 6])
    samples = []

    def read():
        result = next(sequence)
        samples.append(result)
        return result

    hardware.read_joints = read
    result = wait_until_reached(
        hardware,
        (0.1,) * 6,
        None,
        ReachedPolicy(stable_samples=2, joint_tolerance_rad=0.001),
        lease,
        threading.Event(),
        clock=lambda: hardware.now,
        wait=hardware.wait,
    )
    assert result is ReachStatus.REACHED
    assert len(samples) == 5
    lease.release()


@pytest.mark.parametrize(
    "behavior, expected",
    [
        ("timeout", ReachStatus.TIMEOUT),
        ("stop", ReachStatus.STOPPED),
        ("preempt", ReachStatus.PREEMPTED),
        ("fault", ReachStatus.FAULT),
    ],
)
def test_reach_exit_reasons(behavior, expected):
    hardware, motion, lease = setup()
    stop = threading.Event()
    if behavior == "stop":
        stop.set()
    elif behavior == "preempt":
        motion.acquire(MotionSource.HOME, allow_preempt=True)
    elif behavior == "fault":
        hardware.read_joints = lambda: (float("nan"),) * 6
    result = wait_until_reached(
        hardware,
        (1,) * 6,
        None,
        ReachedPolicy(timeout_s=0.05),
        lease,
        stop,
        clock=lambda: hardware.now,
        wait=hardware.wait,
    )
    assert result is expected
    motion.cancel_all()


def test_tcp_reach_uses_rotation_distance_across_euler_wrap():
    from gello_cr.trajectory.planner import TcpPose

    hardware, motion, lease = setup()
    hardware.read_tcp = lambda: TcpPose((0, 0, 0), (0, 0, 3.141592653589793))
    result = wait_until_reached(
        hardware,
        (0,) * 6,
        TcpPose((0, 0, 0), (0, 0, -3.141592653589793)),
        ReachedPolicy(stable_samples=2),
        lease,
        threading.Event(),
        clock=lambda: hardware.now,
        wait=hardware.wait,
    )
    assert result is ReachStatus.REACHED
    lease.release()


def test_planned_playback_holds_point_lease_until_feedback_validation():
    hardware, motion, lease = setup()
    result = TrajectoryPlanner(RobotModel()).plan(JointMoveRequest((0.1,) * 6), (0,) * 6)
    player = TrajectoryPlayer(motion, hardware, clock=lambda: hardware.now, wait=hardware.wait)

    def reached(active, stop):
        assert motion.current_owner is MotionSource.POINT_MOVE
        assert hardware.targets[-1] == pytest.approx((0.1,) * 6)
        return wait_until_reached(
            hardware,
            (0.1,) * 6,
            None,
            ReachedPolicy(stable_samples=2),
            active,
            stop,
            clock=lambda: hardware.now,
            wait=hardware.wait,
        )

    status = player.play(
        result.trajectory,
        ReplayOptions(mode=ReplayMode.ABSOLUTE, hand_enabled=False),
        lease=lease,
        start_tolerance_rad=0.01,
        on_target=reached,
    )
    assert status is ReachStatus.REACHED
    assert hardware.now == pytest.approx(result.metrics.duration_s + 0.02)
    assert motion.current_owner is None


def test_planned_playback_rejects_changed_start_without_opening_servo():
    hardware, motion, lease = setup()
    result = TrajectoryPlanner(RobotModel()).plan(JointMoveRequest((0.1,) * 6), (0,) * 6)
    hardware.joints = (0.2,) * 6
    player = TrajectoryPlayer(motion, hardware, clock=lambda: hardware.now, wait=hardware.wait)
    with pytest.raises(ValueError, match="start"):
        player.play(
            result.trajectory,
            ReplayOptions(mode=ReplayMode.ABSOLUTE, hand_enabled=False),
            lease=lease,
            start_tolerance_rad=0.01,
        )
    assert not hardware.targets
    assert motion.current_owner is None
