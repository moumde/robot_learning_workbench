from __future__ import annotations

import math
import pytest

from gello_cr.control.hand_mapping import (
    binary_o6_action,
    interpolate_o6_target,
    should_send_o6_target,
)

OPEN = (157, 95, 175, 0, 0, 0)
CLOSED = (78, 85, 123, 0, 0, 0)


def test_binary_below_threshold_opens() -> None:
    assert binary_o6_action(0.49) == "张开手"


def test_binary_at_threshold_grasps() -> None:
    assert binary_o6_action(0.5) == "抓取"


def test_binary_rejects_nonfinite() -> None:
    with pytest.raises(ValueError, match="finite"):
        binary_o6_action(math.nan)


def test_continuous_endpoints() -> None:
    assert interpolate_o6_target(0.0, OPEN, CLOSED) == OPEN
    assert interpolate_o6_target(1.0, OPEN, CLOSED) == CLOSED


def test_continuous_clamps_fraction() -> None:
    assert interpolate_o6_target(-1.0, OPEN, CLOSED) == OPEN
    assert interpolate_o6_target(2.0, OPEN, CLOSED) == CLOSED


def test_continuous_midpoint_preserves_python_round() -> None:
    assert interpolate_o6_target(0.5, OPEN, CLOSED) == (
        118, 90, 149, 0, 0, 0
    )


def test_deadband_semantics() -> None:
    target = (100, 100, 100, 100, 100, 100)
    assert should_send_o6_target(target, None, 2)
    assert not should_send_o6_target(target, (99, 100, 100, 100, 100, 100), 2)
    assert should_send_o6_target(target, (98, 100, 100, 100, 100, 100), 2)


def test_validation() -> None:
    with pytest.raises(ValueError, match="exactly 6"):
        interpolate_o6_target(0.5, (0, 0), CLOSED)
    with pytest.raises(ValueError, match="non-negative"):
        should_send_o6_target(OPEN, CLOSED, -1)
