from __future__ import annotations

import math

import pytest

from teleop.gello_cr.motion.safety import MotionSafety
from teleop.gello_cr.motion.types import JointTarget, MotionMode, MotionSafetyError, TcpTarget


def test_joint_target_shape_is_checked_at_safety_boundary() -> None:
    with pytest.raises(MotionSafetyError, match="6"):
        MotionSafety().validate_joint_target(JointTarget(positions_rad=(0.0, 0.0), timestamp=0.0))


@pytest.mark.parametrize(
    "target",
    [
        JointTarget(positions_rad=(math.nan, 0.0, 0.0, 0.0, 0.0, 0.0), timestamp=0.0),
        JointTarget(positions_rad=(0.0,) * 6, timestamp=math.inf),
        JointTarget(positions_rad=(0.0,) * 6, timestamp=0.0, auxiliary_axis_deg=math.nan),
    ],
)
def test_joint_target_rejects_nonfinite_values(target: JointTarget) -> None:
    with pytest.raises(MotionSafetyError, match="finite"):
        MotionSafety().validate_joint_target(target)


@pytest.mark.parametrize(
    "target",
    [
        TcpTarget(xyz_m=(0.0, 0.0), rpy_rad=(0.0,) * 3, timestamp=0.0),
        TcpTarget(xyz_m=(0.0,) * 3, rpy_rad=(0.0, 0.0), timestamp=0.0),
    ],
)
def test_tcp_target_requires_three_position_and_rotation_values(target: TcpTarget) -> None:
    with pytest.raises(MotionSafetyError, match="3"):
        MotionSafety().validate_tcp_target(target)


@pytest.mark.parametrize(
    "target",
    [
        TcpTarget(xyz_m=(math.inf, 0.0, 0.0), rpy_rad=(0.0,) * 3, timestamp=0.0),
        TcpTarget(xyz_m=(0.0,) * 3, rpy_rad=(0.0, math.nan, 0.0), timestamp=0.0),
        TcpTarget(xyz_m=(0.0,) * 3, rpy_rad=(0.0,) * 3, timestamp=math.nan),
        TcpTarget(xyz_m=(0.0,) * 3, rpy_rad=(0.0,) * 3, timestamp=0.0, auxiliary_axis=math.inf),
    ],
)
def test_tcp_target_rejects_nonfinite_values(target: TcpTarget) -> None:
    with pytest.raises(MotionSafetyError, match="finite"):
        MotionSafety().validate_tcp_target(target)


def test_no_robot_limits_are_assumed_when_configuration_is_absent() -> None:
    safety = MotionSafety()

    safety.validate_joint_target(
        JointTarget(positions_rad=(100.0,) * 6, timestamp=0.0),
        JointTarget(positions_rad=(0.0,) * 6, timestamp=0.0),
    )
    safety.validate_tcp_target(TcpTarget(xyz_m=(100.0,) * 3, rpy_rad=(100.0,) * 3, timestamp=0.0))


def test_joint_limits_accept_boundaries_and_reject_outside_target() -> None:
    safety = MotionSafety(lambda: {"motion": {"joint_limits_rad": [(-1.0, 1.0)] * 6}})

    safety.validate_joint_target(
        JointTarget(positions_rad=(-1.0, 1.0, 0.0, 0.0, 0.0, 0.0), timestamp=0.0)
    )
    with pytest.raises(MotionSafetyError, match="joint"):
        safety.validate_joint_target(
            JointTarget(positions_rad=(0.0, 0.0, 1.01, 0.0, 0.0, 0.0), timestamp=0.0)
        )


def test_workspace_limits_apply_to_position_and_allow_boundaries() -> None:
    safety = MotionSafety(
        lambda: {"motion": {"workspace_limits_m": [(-1.0, 1.0), (-2.0, 2.0), (0.0, 3.0)]}}
    )

    safety.validate_tcp_target(TcpTarget(xyz_m=(-1.0, 2.0, 3.0), rpy_rad=(4.0,) * 3, timestamp=0.0))
    with pytest.raises(MotionSafetyError, match="workspace"):
        safety.validate_tcp_target(
            TcpTarget(xyz_m=(0.0, 0.0, -0.01), rpy_rad=(0.0,) * 3, timestamp=0.0)
        )


def test_servo_delta_uses_motion_limit_before_robot_fallback() -> None:
    safety = MotionSafety(
        lambda: {
            "motion": {"max_command_delta_rad": 0.2},
            "robot": {"safety_max_command_step_rad": 0.01},
        }
    )
    previous = JointTarget(positions_rad=(0.0,) * 6, timestamp=0.0)

    safety.validate_joint_target(
        JointTarget(positions_rad=(0.2, 0.0, 0.0, 0.0, 0.0, 0.0), timestamp=0.0), previous
    )
    with pytest.raises(MotionSafetyError, match="delta"):
        safety.validate_joint_target(
            JointTarget(positions_rad=(0.0, 0.0, 0.0, 0.21, 0.0, 0.0), timestamp=0.0), previous
        )


def test_servo_delta_uses_live_robot_fallback() -> None:
    config = {"robot": {"safety_max_command_step_rad": 0.1}}
    safety = MotionSafety(lambda: config)
    previous = JointTarget(positions_rad=(0.0,) * 6, timestamp=0.0)
    target = JointTarget(positions_rad=(0.15, 0.0, 0.0, 0.0, 0.0, 0.0), timestamp=0.0)

    with pytest.raises(MotionSafetyError, match="delta"):
        safety.validate_joint_target(target, previous)
    config["robot"]["safety_max_command_step_rad"] = 0.2
    safety.validate_joint_target(target, previous)


def test_move_joint_does_not_apply_servo_delta_or_velocity_limit() -> None:
    safety = MotionSafety(
        lambda: {"motion": {"max_command_delta_rad": 0.1, "max_target_velocity_rad_s": 0.1}}
    )

    safety.validate_joint_target(
        JointTarget(positions_rad=(1.0,) * 6, timestamp=0.0),
        JointTarget(positions_rad=(0.0,) * 6, timestamp=0.0),
        mode=MotionMode.JOINT_MOVE,
    )


def test_servo_velocity_uses_timestamp_difference_and_accepts_limit() -> None:
    safety = MotionSafety(lambda: {"motion": {"max_target_velocity_rad_s": 0.5}})
    previous = JointTarget(positions_rad=(0.0,) * 6, timestamp=1.0)

    safety.validate_joint_target(
        JointTarget(positions_rad=(0.125, 0.0, 0.0, 0.0, 0.0, 0.0), timestamp=1.25), previous
    )
    with pytest.raises(MotionSafetyError, match="velocity"):
        safety.validate_joint_target(
            JointTarget(positions_rad=(0.0, 0.2, 0.0, 0.0, 0.0, 0.0), timestamp=1.25), previous
        )


def test_feedback_baseline_can_skip_velocity_while_preserving_delta_validation() -> None:
    safety = MotionSafety(
        lambda: {"motion": {"max_command_delta_rad": 0.2, "max_target_velocity_rad_s": 0.01}}
    )
    previous = JointTarget(positions_rad=(0.0,) * 6, timestamp=1.0)

    safety.validate_joint_target(
        JointTarget(positions_rad=(0.1, 0.0, 0.0, 0.0, 0.0, 0.0), timestamp=1.0),
        previous,
        validate_velocity=False,
    )
    with pytest.raises(MotionSafetyError, match="delta"):
        safety.validate_joint_target(
            JointTarget(positions_rad=(0.3, 0.0, 0.0, 0.0, 0.0, 0.0), timestamp=1.0),
            previous,
            validate_velocity=False,
        )


@pytest.mark.parametrize("timestamp", [0.5, 1.0])
def test_servo_velocity_requires_increasing_timestamps(timestamp: float) -> None:
    safety = MotionSafety(lambda: {"motion": {"max_target_velocity_rad_s": 0.5}})

    with pytest.raises(MotionSafetyError, match="timestamp"):
        safety.validate_joint_target(
            JointTarget(positions_rad=(0.0,) * 6, timestamp=timestamp),
            JointTarget(positions_rad=(0.0,) * 6, timestamp=1.0),
        )


@pytest.mark.parametrize(
    "motion_config",
    [
        {"joint_limits_rad": [(-1.0, 1.0)] * 5},
        {"joint_limits_rad": [(1.0, -1.0)] * 6},
        {"max_command_delta_rad": 0.0},
        {"max_target_velocity_rad_s": math.inf},
    ],
)
def test_malformed_safety_limits_fail_closed(motion_config: dict[str, object]) -> None:
    safety = MotionSafety(lambda: {"motion": motion_config})

    with pytest.raises(MotionSafetyError):
        safety.validate_joint_target(
            JointTarget(positions_rad=(0.0,) * 6, timestamp=2.0),
            JointTarget(positions_rad=(0.0,) * 6, timestamp=1.0),
        )
