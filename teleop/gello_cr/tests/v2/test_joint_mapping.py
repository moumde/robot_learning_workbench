from __future__ import annotations

import math
import pytest

from gello_cr.control.joint_mapping import RelativeJointMapper, wrapped_delta_rad


def _rad(*degrees: float) -> tuple[float, ...]:
    return tuple(math.radians(value) for value in degrees)


def test_zero_relative_motion_holds_slave_startup_pose() -> None:
    mapper = RelativeJointMapper(joint_scale=1.1)
    leader_origin = _rad(10, -20, 30, -40, 50, -60)
    slave_origin = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert mapper.target_deg(leader_origin, leader_origin, slave_origin) == pytest.approx(slave_origin)


def test_joint_scale_matches_legacy_relative_mapping_equation() -> None:
    mapper = RelativeJointMapper(joint_scale=1.1)
    target = mapper.target_deg(
        _rad(11, -18, 27, -36, 45, -54),
        _rad(10, -20, 30, -40, 50, -60),
        (100, 200, 300, 400, 500, 600),
    )
    assert target == pytest.approx((101.1, 202.2, 296.7, 404.4, 494.5, 606.6))


def test_wrap_across_plus_minus_180_uses_shortest_delta() -> None:
    mapper = RelativeJointMapper(joint_scale=1.0)
    target = mapper.target_deg(
        _rad(-179, 0, 0, 0, 0, 0),
        _rad(179, 0, 0, 0, 0, 0),
        (10, 20, 30, 40, 50, 60),
    )
    assert target[0] == pytest.approx(12.0)
    assert target[1:] == pytest.approx((20, 30, 40, 50, 60))


def test_locked_joints_remain_at_slave_startup_pose() -> None:
    mapper = RelativeJointMapper(joint_scale=1.25, locked_joints=(2, 5))
    target = mapper.target_deg(
        _rad(10, 20, 30, 40, 50, 60),
        _rad(0, 0, 0, 0, 0, 0),
        (100, 200, 300, 400, 500, 600),
    )
    assert target == pytest.approx((112.5, 200.0, 337.5, 450.0, 500.0, 675.0))


def test_leader_delta_for_speed_check_uses_wrapped_absolute_motion() -> None:
    mapper = RelativeJointMapper(joint_scale=1.1)
    delta = mapper.leader_delta_rad(
        _rad(-179, 12, 0, 0, 0, 0),
        _rad(179, 10, 0, 0, 0, 0),
    )
    assert delta[0] == pytest.approx(math.radians(2.2))
    assert delta[1] == pytest.approx(math.radians(2.2))
    assert delta[2:] == pytest.approx((0, 0, 0, 0))


def test_locked_joint_is_removed_from_speed_delta() -> None:
    mapper = RelativeJointMapper(joint_scale=1.1, locked_joints=(1, 6))
    delta = mapper.leader_delta_rad(
        _rad(100, 10, 20, 30, 40, 100),
        _rad(0, 0, 0, 0, 0, 0),
    )
    assert delta[0] == 0.0
    assert delta[5] == 0.0
    assert delta[1] == pytest.approx(math.radians(11.0))


def test_mapper_rejects_invalid_dimensions_and_nonfinite_values() -> None:
    mapper = RelativeJointMapper()
    with pytest.raises(ValueError, match="exactly 6"):
        mapper.target_deg((0.0, 0.0), (0.0,) * 6, (0.0,) * 6)
    with pytest.raises(ValueError, match="finite"):
        mapper.leader_delta_rad((0.0, 0.0, 0.0, 0.0, 0.0, math.inf), (0.0,) * 6)


def test_mapper_validates_scale_and_locked_joint_numbers() -> None:
    with pytest.raises(ValueError, match="positive"):
        RelativeJointMapper(joint_scale=0.0)
    with pytest.raises(ValueError, match="J1..J6"):
        RelativeJointMapper(locked_joints=(7,))
    with pytest.raises(ValueError, match="duplicates"):
        RelativeJointMapper(locked_joints=(2, 2))


def test_wrapped_delta_helper_matches_legacy_formula() -> None:
    current = math.radians(-170)
    origin = math.radians(170)
    expected = math.atan2(math.sin(current - origin), math.cos(current - origin))
    assert wrapped_delta_rad(current, origin) == pytest.approx(expected)
