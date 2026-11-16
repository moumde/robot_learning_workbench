"""Validate NRC limits without losing the external-axis constraint."""

from __future__ import annotations

import math
from collections.abc import Sequence

ServoLimit = float | Sequence[float]


def servo_limit_vector(value: ServoLimit, name: str) -> tuple[float, ...]:
    """Expand a legacy scalar, or retain all seven configured NRC axes."""
    if isinstance(value, (str, bytes, bool)):
        raise ValueError(f"{name} must be a positive scalar or exactly 7 positive numbers")
    if isinstance(value, Sequence):
        if len(value) != 7 or any(isinstance(item, bool) for item in value):
            raise ValueError(f"{name} must contain exactly 7 positive numbers")
        values = tuple(float(item) for item in value)
    else:
        values = (float(value),) * 7
    if any(not math.isfinite(item) or item <= 0 for item in values):
        raise ValueError(f"{name} must contain positive finite numbers")
    return values
