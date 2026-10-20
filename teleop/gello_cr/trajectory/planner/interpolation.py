"""Quintic progress and shortest-path orientation interpolation."""

import math

from teleop.gello_cr.control.geometry import (
    _nrc_abc_to_quaternion,
    _quaternion_distance,
    _quaternion_slerp,
    _quaternion_to_nrc_abc_near,
)

from .types import TcpPose


def quintic(alpha):
    return alpha**3 * (10 + alpha * (-15 + 6 * alpha))


def pose_distance(a, b):
    return (
        math.dist(a.position_m, b.position_m),
        _quaternion_distance(
            _nrc_abc_to_quaternion(a.orientation_rpy_rad),
            _nrc_abc_to_quaternion(b.orientation_rpy_rad),
        ),
    )


def interpolate_pose(a, b, alpha):
    orientation = _quaternion_slerp(
        _nrc_abc_to_quaternion(a.orientation_rpy_rad),
        _nrc_abc_to_quaternion(b.orientation_rpy_rad),
        alpha,
    )
    return TcpPose(
        tuple(x + (y - x) * alpha for x, y in zip(a.position_m, b.position_m, strict=True)),
        _quaternion_to_nrc_abc_near(orientation, a.orientation_rpy_rad),
    )
