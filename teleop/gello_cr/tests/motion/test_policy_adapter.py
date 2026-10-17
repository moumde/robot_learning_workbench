import pytest

from gello_cr.motion import MotionCoordinator, MotionExecutor, MotionPreempted, MotionSource
from gello_cr.motion.policy_adapter import PolicyMotionRobot


class Robot:
    def __init__(self):
        self.targets = []
        self.stops = 0

    def joint_position(self):
        return [0.0] * 7

    def send_servoj(self, target):
        self.targets.append(target)
        return True

    def stop_motion(self):
        self.stops += 1


def test_policy_native_commands_require_ownership_and_keep_units():
    robot = Robot()
    motion = MotionCoordinator(MotionExecutor(lambda: robot))
    view = PolicyMotionRobot(lambda: robot)
    with pytest.raises(MotionPreempted):
        view.send_servoj([1.0] * 7)
    assert not robot.targets
    view.bind(motion.acquire(MotionSource.POLICY))
    assert view.send_servoj([1, 2, 3, 4, 5, 6, 7]) is True
    assert robot.targets[-1] == pytest.approx([1, 2, 3, 4, 5, 6, 7])


def test_preempted_policy_cannot_send_or_stop_home():
    robot = Robot()
    motion = MotionCoordinator(MotionExecutor(lambda: robot))
    view = PolicyMotionRobot(lambda: robot)
    view.bind(motion.acquire(MotionSource.POLICY))
    home = motion.acquire(MotionSource.HOME, allow_preempt=True)
    stops = robot.stops
    with pytest.raises(MotionPreempted):
        view.send_servoj([0.0] * 7)
    view.stop_motion()
    assert robot.stops == stops
    assert home.active
    assert not hasattr(view, "api")
