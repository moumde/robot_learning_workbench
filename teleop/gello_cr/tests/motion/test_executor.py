from __future__ import annotations

import math

import pytest

from teleop.gello_cr.motion import JointTarget, MotionExecutor, TcpTarget


class FakeRobot:
    def __init__(self) -> None:
        self.calls = []
        self.sent = True

    def send_servoj(self, target):
        self.calls.append(("servo", target))
        return self.sent

    def movej(self, target, velocity, acc, dec):
        self.calls.append(("movej", target, velocity, acc, dec))

    def movel(self, target, velocity, acc, dec):
        self.calls.append(("movel", target, velocity, acc, dec))

    def open_servoj(self, vmax, amax, jmax):
        self.calls.append(("open", vmax, amax, jmax))

    def stop_motion(self):
        self.calls.append(("stop",))

    def joint_position(self):
        return [0, 90, -90, 180, -180, 45, 19]


def test_servo_converts_joint_units_preserves_auxiliary_axis_and_false_result():
    robot = FakeRobot()
    executor = MotionExecutor(lambda: robot)
    target = JointTarget((0, math.pi / 2, -math.pi / 2, math.pi, -math.pi, math.pi / 4), 1, 19)
    robot.sent = False

    assert executor.servo_joint(target) is False
    assert robot.calls[0][0] == "servo"
    assert robot.calls[0][1] == pytest.approx([0, 90, -90, 180, -180, 45, 19])
    assert executor.joint_position_rad() == pytest.approx(target.positions_rad)


def test_move_commands_convert_targets_and_default_deceleration_to_acceleration():
    robot = FakeRobot()
    executor = MotionExecutor(lambda: robot)

    executor.move_joint(JointTarget.from_degrees([10, 20, 30, 40, 50, 60, 7], 2), 4, 5)
    executor.move_tcp(TcpTarget((0.1, -0.2, 0.3), (0.2, -0.1, 0.4), 2, 8), 6, 7, 9)

    assert robot.calls[0][0] == "movej"
    assert robot.calls[0][1] == pytest.approx([10, 20, 30, 40, 50, 60, 7])
    assert robot.calls[0][2:] == (4, 5, 5)
    assert robot.calls[1] == ("movel", [100.0, -200.0, 300.0, 0.2, -0.1, 0.4, 8], 6, 7, 9)


def test_executor_resolves_current_robot_for_each_call_and_uses_full_stop():
    robots = [FakeRobot(), FakeRobot()]
    current = [robots[0]]
    executor = MotionExecutor(lambda: current[0])
    executor.open_servo(1, 2, 3)
    current[0] = robots[1]
    executor.stop()
    current[0] = None
    executor.stop()

    assert robots[0].calls == [("open", 1, 2, 3)]
    assert robots[1].calls == [("stop",)]


def test_native_target_constructors_retain_six_axes_and_native_auxiliary_value():
    joint = JointTarget.from_degrees([0, 90, -90, 180, 45, -45, 13], 4)
    tcp = TcpTarget.from_native([100, -200, 300, 0.1, 0.2, -0.3, 14], 5)

    assert joint.positions_rad == pytest.approx(
        (0, math.pi / 2, -math.pi / 2, math.pi, math.pi / 4, -math.pi / 4)
    )
    assert (joint.auxiliary_axis_deg, joint.timestamp) == (13, 4)
    assert (tcp.xyz_m, tcp.rpy_rad, tcp.timestamp, tcp.auxiliary_axis) == (
        (0.1, -0.2, 0.3),
        (0.1, 0.2, -0.3),
        5,
        14,
    )
