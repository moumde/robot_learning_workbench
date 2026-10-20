"""Cancellation and application callbacks shared by master control strategies."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TeleopHooks:
    """Shared cancellation signals and callbacks owned by application orchestration."""

    lock: Any
    stop: threading.Event
    shutdown: threading.Event
    generation: Callable[[], int]
    state: Callable[[], str]
    set_state: Callable[[str, str], None]
    event: Callable[[str, str], None]
    reset_targets: Callable[[], None]
    publish_tcp_target: Callable[[Sequence[float]], None]
    publish_telemetry: Callable[[dict[str, Any]], None]
