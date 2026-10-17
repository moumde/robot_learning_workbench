"""Unit boundary for the controller's read-only FK/IK operations."""

import math

from gello_cr.trajectory.planner.types import TcpPose


class NrcKinematicsProvider:
    # This controller API has no seed or all-solutions argument. The planner
    # still validates FK residuals and continuity of the returned branch.
    warnings = ("NRC IK 接口仅返回一个解且不支持 seed；已启用 FK 校验和连续性检查",)

    def __init__(self, session):
        self.session = session

    def forward(self, joint_rad):
        native = self.session.forward_kinematics([math.degrees(v) for v in joint_rad] + [0.0])
        return TcpPose(tuple(v / 1000 for v in native[:3]), tuple(native[3:6]))

    def inverse(self, pose, seed_joint_rad=None):
        native = [v * 1000 for v in pose.position_m] + list(pose.orientation_rpy_rad) + [0.0]
        joint = self.session.inverse_kinematics(native)
        if len(joint) < 6:
            raise ValueError("NRC IK must return six joints")
        return [tuple(math.radians(v) for v in joint[:6])]
