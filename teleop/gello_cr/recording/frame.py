"""Canonical robot-learning capture values, independent of storage formats."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class CaptureFrame:
    timestamp: float
    observation_state: tuple[float, ...]
    action: tuple[float, ...]
    images: Mapping[str, np.ndarray]
    robot_joint_state: tuple[float, ...] | None = None
    robot_joint_command: tuple[float, ...] | None = None
    robot_tcp_state: tuple[float, ...] | None = None
    robot_tcp_command: tuple[float, ...] | None = None
    hand_state: tuple[float, ...] | None = None
    hand_command: tuple[float, ...] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
