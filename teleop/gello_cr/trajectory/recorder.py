"""Fixed-cadence recording from a sample source, independent of persistence."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import replace
from typing import Protocol

from .model import TrajectoryFrame, make_trajectory
from .validation import validate_frame, validate_trajectory


class TrajectorySampleSource(Protocol):
    def sample(self) -> TrajectoryFrame: ...


class TrajectoryRecorder:
    def __init__(
        self, source: TrajectorySampleSource, *, fps=20.0, max_duration_s=300.0, stop_event=None
    ):
        if (
            not math.isfinite(fps)
            or fps <= 0
            or not math.isfinite(max_duration_s)
            or max_duration_s <= 0
        ):
            raise ValueError("Recording fps and duration must be positive")
        self.source, self.fps, self.max_duration_s = source, fps, max_duration_s
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self.thread = None
        self._lock = threading.Lock()
        self._frames = []
        self.error = ""
        self._name = ""
        self._metadata = {}

    @property
    def recording(self):
        return self.thread is not None and self.thread.is_alive() and not self.stop_event.is_set()

    @property
    def frames(self):
        with self._lock:
            return tuple(self._frames)

    def start(
        self, name: str, metadata: dict | None = None, *, should_continue=None, on_finished=None
    ) -> None:
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("Trajectory recording already active")
        if not name.strip():
            raise ValueError("Trajectory name cannot be empty")
        self._name, self._metadata = name.strip(), dict(metadata or {})
        self._should_continue = should_continue
        self._on_finished = on_finished
        first = self.source.sample()
        validate_frame(first)
        self._origin = first.timestamp
        candidate = make_trajectory(
            self._name, [replace(first, timestamp=0.0)], fps=self.fps, **self._metadata
        )
        validate_trajectory(candidate)
        with self._lock:
            self._frames = list(candidate.frames)
        self.error = ""
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="Trajectory-Record", daemon=True)
        try:
            self.thread.start()
        except Exception:
            self.thread = None
            self.stop_event.set()
            raise

    def _run(self):
        next_sample = time.monotonic()
        previous = 0.0
        try:
            while not self.stop_event.is_set():
                next_sample += 1.0 / self.fps
                if self.stop_event.wait(max(0.0, next_sample - time.monotonic())):
                    break
                if self._should_continue is not None and not self._should_continue():
                    break
                frame = self.source.sample()
                elapsed = frame.timestamp - self._origin
                if elapsed >= self.max_duration_s:
                    break
                frame = replace(frame, timestamp=elapsed)
                if elapsed <= previous:
                    raise ValueError("Sample timestamps must increase")
                validate_frame(frame)
                with self._lock:
                    self._frames.append(frame)
                previous = elapsed
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.stop_event.set()
            if self._on_finished is not None:
                self._on_finished(self.error or None)

    def _join(self):
        self.stop_event.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(2.0)
            if self.thread.is_alive():
                raise TimeoutError("Trajectory sample source did not stop")

    def stop(self):
        self._join()
        trajectory = make_trajectory(self._name, self.frames, fps=self.fps, **self._metadata)
        validate_trajectory(trajectory)
        return trajectory

    def cancel(self):
        self._join()
        with self._lock:
            self._frames = []
        self.error = ""
