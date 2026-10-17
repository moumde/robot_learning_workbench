"""Runtime snapshots and hand commands exposed to the trajectory subsystem."""

from __future__ import annotations

import math
import time

from gello_cr.trajectory.model import TrajectoryFrame


class RuntimeTrajectorySource:
    def __init__(self, runtime):
        self.runtime = runtime

    def read_joints(self):
        robot = self.runtime.robot
        if robot is None:
            raise RuntimeError("Robot disconnected")
        native = robot.joint_position()
        if len(native) != 7 or not all(math.isfinite(v) for v in native):
            raise RuntimeError("Robot joint feedback is invalid")
        return tuple(math.radians(v) for v in native[:6])

    def check_ready(self, arm_enabled, hand_enabled):
        if arm_enabled:
            robot = self.runtime.robot
            if robot is None or robot.servo_state() != 3:
                raise RuntimeError("Robot must be connected and enabled for replay")
        if hand_enabled:
            hand = self.runtime.o6
            positions, faults, stamp = hand.latest()
            if (
                not hand.connected
                or hand.error
                or positions is None
                or faults is None
                or any(faults)
            ):
                raise RuntimeError("O6 unavailable or faulted")
            if time.monotonic() - stamp > float(
                self.runtime.store.data["o6"]["feedback_timeout_s"]
            ):
                raise RuntimeError("O6 feedback expired")

    def read_tcp(self):
        from gello_cr.trajectory.planner import TcpPose

        robot = self.runtime.robot
        if robot is None:
            raise RuntimeError("Robot disconnected")
        native = robot.tcp_position()
        if len(native) < 6 or not all(math.isfinite(v) for v in native[:6]):
            raise RuntimeError("Robot TCP feedback is invalid")
        return TcpPose(tuple(v / 1000 for v in native[:3]), tuple(native[3:6]))

    def sample(self):
        joint_state = self.read_joints()
        native_tcp = self.runtime.robot.tcp_position()
        if len(native_tcp) < 6 or not all(math.isfinite(v) for v in native_tcp[:6]):
            raise RuntimeError("Robot TCP feedback is invalid")
        joint_command = self.runtime.motion.last_joint_target
        tcp_command = self.runtime.motion.last_tcp_target
        if tcp_command is not None:
            tcp_command = tuple(tcp_command.xyz_m) + tuple(tcp_command.rpy_rad)
        elif self.runtime._dataset_target_tcp_controller is not None:
            native = self.runtime._dataset_target_tcp_controller
            tcp_command = tuple(v / 1000.0 for v in native[:3]) + tuple(native[3:6])
        hand_state = hand_command = None
        if self.runtime.o6.connected:
            self.check_ready(False, True)
            hand_state = tuple(self.runtime.o6.latest()[0])
            last = self.runtime.o6.last_sent_target
            hand_command = tuple(last) if last is not None else None
        return TrajectoryFrame(
            time.monotonic(),
            robot_joint_state=joint_state,
            robot_joint_command=joint_command.positions_rad if joint_command is not None else None,
            robot_tcp_state=tuple(v / 1000.0 for v in native_tcp[:3]) + tuple(native_tcp[3:6]),
            robot_tcp_command=tcp_command,
            hand_state=hand_state,
            hand_command=hand_command,
        )

    def send_hand(self, target):
        self.check_ready(False, True)
        self.runtime.o6.set_target(target)

    def hold_hand(self):
        self.runtime.o6.hold_current()
