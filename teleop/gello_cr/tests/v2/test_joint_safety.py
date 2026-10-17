from __future__ import annotations

import math

import pytest

from gello_cr.control.joint_safety import (
    LeaderSpeedViolationCounter,
    command_step_rad,
    max_command_step_violation,
    max_tracking_error_violation,
    tracking_error_rad,
)


def test_command_step_math_matches_legacy_degree_to_rad_behavior() -> None:
    values = command_step_rad(
        (11, 18, 33, 36, 55, 54),
        (10, 20, 30, 40, 50, 60),
    )

    assert values == pytest.approx(
        tuple(
            math.radians(value)
            for value in (1, 2, 3, 4, 5, 6)
        )
    )


def test_command_step_violation_reports_max_joint() -> None:
    violation = max_command_step_violation(
        (0, 0, 0, 9, 0, 0),
        (0, 0, 0, 0, 0, 0),
        math.radians(5),
    )

    assert violation is not None
    assert violation.joint_number == 4
    assert violation.value == pytest.approx(math.radians(9))
    assert violation.limit == pytest.approx(math.radians(5))


def test_command_step_equal_to_limit_is_allowed() -> None:
    assert (
        max_command_step_violation(
            (5, 0, 0, 0, 0, 0),
            (0, 0, 0, 0, 0, 0),
            math.radians(5),
        )
        is None
    )


def test_tracking_error_math_matches_legacy_behavior() -> None:
    values = tracking_error_rad(
        (10, 20, 30, 40, 50, 60),
        (9, 22, 27, 44, 45, 66),
    )

    assert values == pytest.approx(
        tuple(
            math.radians(value)
            for value in (1, 2, 3, 4, 5, 6)
        )
    )


def test_tracking_violation_reports_max_joint() -> None:
    violation = max_tracking_error_violation(
        (10, 20, 30, 40, 50, 60),
        (10, 20, 30, 40, 50, 50),
        math.radians(8),
    )

    assert violation is not None
    assert violation.joint_number == 6
    assert violation.value == pytest.approx(math.radians(10))


def test_leader_speed_requires_consecutive_over_limit_samples() -> None:
    guard = LeaderSpeedViolationCounter()
    delta = (0.02, 0, 0, 0, 0, 0)

    first = guard.update(delta, 0.01, 1.0, 3)
    second = guard.update(delta, 0.01, 1.0, 3)
    third = guard.update(delta, 0.01, 1.0, 3)

    assert first.violation is None
    assert second.violation is None
    assert third.violation is not None
    assert third.violation.joint_number == 1
    assert third.violation.value == pytest.approx(2.0)
    assert third.violation_counts == (3, 0, 0, 0, 0, 0)


def test_safe_leader_sample_resets_only_that_joint_counter() -> None:
    guard = LeaderSpeedViolationCounter()

    guard.update((0.02, 0.03, 0, 0, 0, 0), 0.01, 1.0, 5)
    sample = guard.update((0.0, 0.03, 0, 0, 0, 0), 0.01, 1.0, 5)

    assert sample.violation_counts == (0, 2, 0, 0, 0, 0)


def test_leader_speed_uses_legacy_one_millisecond_minimum_period() -> None:
    guard = LeaderSpeedViolationCounter()

    sample = guard.update(
        (0.002, 0, 0, 0, 0, 0),
        0.0001,
        10.0,
        2,
    )

    assert sample.speed_rad_s[0] == pytest.approx(2.0)


def test_leader_speed_equal_to_limit_does_not_increment_counter() -> None:
    guard = LeaderSpeedViolationCounter()

    sample = guard.update(
        (0.01, 0, 0, 0, 0, 0),
        0.01,
        1.0,
        1,
    )

    assert sample.violation is None
    assert sample.violation_counts == (0, 0, 0, 0, 0, 0)


def test_guard_reset_clears_all_violation_counts() -> None:
    guard = LeaderSpeedViolationCounter()
    guard.update((0.02, 0.02, 0, 0, 0, 0), 0.01, 1.0, 5)

    guard.reset()

    assert guard.counts == (0, 0, 0, 0, 0, 0)


def test_safety_primitives_validate_dimensions_and_limits() -> None:
    with pytest.raises(ValueError, match="exactly 6"):
        command_step_rad((0, 0), (0,) * 6)

    with pytest.raises(ValueError, match="positive"):
        max_tracking_error_violation(
            (0,) * 6,
            (0,) * 6,
            0.0,
        )

    guard = LeaderSpeedViolationCounter()
    with pytest.raises(ValueError, match="non-negative"):
        guard.update((-0.1, 0, 0, 0, 0, 0), 0.01, 1.0, 3)

    with pytest.raises(ValueError, match="violation_cycles"):
        guard.update((0,) * 6, 0.01, 1.0, 0)
