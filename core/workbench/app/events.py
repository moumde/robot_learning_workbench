"""Application-level events independent of Qt/PySide."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from core.workbench.core.state_machine import Command, WorkflowState


class EventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AppEvent:
    sequence: int
    kind: str
    level: EventLevel
    state: WorkflowState
    message: str
    command: Command | None = None
    occurred_at: float = field(default_factory=time.time)
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
