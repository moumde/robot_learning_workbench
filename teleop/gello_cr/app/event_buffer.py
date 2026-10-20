"""Thread-safe bounded buffer for application events.

ApplicationService handlers may run in worker threads. UI subscribers therefore
must not touch Qt/PySide widgets directly. This buffer is the handoff point:
worker threads push AppEvent objects and the GUI thread drains them.
"""

from __future__ import annotations

import threading
from collections import deque

from .events import AppEvent


class ApplicationEventBuffer:
    """Bounded, non-blocking event handoff for GUI/main-thread consumers."""

    def __init__(self, capacity: int = 256) -> None:
        size = int(capacity)
        if size <= 0:
            raise ValueError("event buffer capacity must be positive")
        self._capacity = size
        self._events: deque[AppEvent] = deque()
        self._lock = threading.Lock()
        self._dropped = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def push(self, event: AppEvent) -> None:
        if not isinstance(event, AppEvent):
            raise TypeError("event must be AppEvent")

        with self._lock:
            if len(self._events) >= self._capacity:
                self._events.popleft()
                self._dropped += 1
            self._events.append(event)

    def drain(self, limit: int | None = None) -> tuple[AppEvent, ...]:
        if limit is not None:
            count = int(limit)
            if count < 0:
                raise ValueError("drain limit must be non-negative")
        else:
            count = None

        with self._lock:
            if count == 0:
                return ()
            if count is None or count >= len(self._events):
                events = tuple(self._events)
                self._events.clear()
                return events

            return tuple(self._events.popleft() for _ in range(count))
