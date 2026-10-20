"""Serialize target validation, execution, and ownership changes under one lock."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

from .executor import MotionExecutor
from .safety import MotionSafety
from .types import (
    MOTION_PRIORITY,
    JointTarget,
    MotionBusyError,
    MotionMode,
    MotionPreempted,
    MotionSource,
    MotionStatus,
    TcpTarget,
)

logger = logging.getLogger("workbench.motion")


class MotionLease:
    """A worker-local capability; every operation checks its immutable token."""

    def __init__(self, coordinator: MotionCoordinator, token: object, source: MotionSource) -> None:
        self._coordinator = coordinator
        self._token = token
        self._source = source

    @property
    def source(self) -> MotionSource:
        return self._source

    @property
    def active(self) -> bool:
        return self._coordinator._active(self)

    def check(self) -> None:
        self._coordinator._check(self)

    def release(self, error: Exception | str | None = None) -> None:
        self._coordinator._release(self, error)

    def open_servo(self, vmax: float, amax: float, jmax: float) -> None:
        """Open servo mode and sample the initial joint baseline for delta validation."""
        self._coordinator._open_servo(self, vmax, amax, jmax)

    def servo_joint(self, target: JointTarget) -> bool:
        """Validate and send a joint target while this lease owns motion."""
        return self._coordinator._execute(
            self,
            MotionMode.SERVO_JOINT,
            target,
            lambda: self._coordinator._executor.servo_joint(target),
        )

    def move_joint(
        self,
        target: JointTarget,
        velocity: float,
        acceleration: float,
        deceleration: float | None = None,
    ) -> None:
        self._coordinator._execute(
            self,
            MotionMode.JOINT_MOVE,
            target,
            lambda: self._coordinator._executor.move_joint(
                target, velocity, acceleration, deceleration
            ),
        )

    def move_tcp(
        self,
        target: TcpTarget,
        velocity: float,
        acceleration: float,
        deceleration: float | None = None,
    ) -> None:
        self._coordinator._execute(
            self,
            MotionMode.TCP_MOVE,
            target,
            lambda: self._coordinator._executor.move_tcp(
                target, velocity, acceleration, deceleration
            ),
        )

    def stop(self) -> None:
        self._coordinator._stop_lease(self)


class MotionCoordinator:
    def __init__(
        self,
        executor: MotionExecutor,
        safety: MotionSafety | None = None,
        event_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._executor = executor
        self._safety = safety or MotionSafety()
        self._event_callback = event_callback
        self._lock = threading.RLock()
        self._token: object | None = None
        self._on_cancel: Callable[[], None] | None = None
        self._status = MotionStatus()
        self._previous: JointTarget | None = None
        self._baseline_sampled = False
        self._previous_is_feedback = False
        self._transitioning = False
        self._last_joint_target: JointTarget | None = None
        self._last_tcp_target: TcpTarget | None = None

    @property
    def last_joint_target(self) -> JointTarget | None:
        with self._lock:
            return self._last_joint_target

    @property
    def last_tcp_target(self) -> TcpTarget | None:
        with self._lock:
            return self._last_tcp_target

    @property
    def status(self) -> MotionStatus:
        # Writers replace this frozen value while holding the ownership lock.
        # Reading the published reference needs no SDK lock and cannot expose
        # a partially updated status. Lease validation and sends stay atomic.
        return self._status

    @property
    def current_owner(self) -> MotionSource | None:
        with self._lock:
            return self._status.source

    def _event(self, level: str, message: str) -> None:
        getattr(logger, level)(message)
        if self._event_callback is not None:
            try:
                self._event_callback(level, message)
            except Exception:
                logger.exception("Motion event callback failed")

    @contextmanager
    def _ownership_transition(self) -> Iterator[None]:
        previous = self._transitioning
        self._transitioning = True
        try:
            yield
        finally:
            self._transitioning = previous

    def acquire(
        self,
        source: MotionSource,
        allow_preempt: bool = False,
        on_cancel: Callable[[], None] | None = None,
    ) -> MotionLease:
        with self._lock:
            if self._transitioning:
                raise MotionBusyError("Motion ownership transition is in progress")
            with self._ownership_transition():
                owner = self._status.source
                if owner is not None:
                    if not allow_preempt or MOTION_PRIORITY[source] <= MOTION_PRIORITY[owner]:
                        raise MotionBusyError(
                            f"Motion owned by {owner.name}; {source.name} cannot acquire"
                        )
                    self._stop_current(f"preempted by {source.name}")
                    self._event("info", f"Motion preempted: {owner.name} -> {source.name}")
                self._token = object()
                self._last_joint_target = None
                self._last_tcp_target = None
                self._on_cancel = on_cancel
                self._previous = None
                self._baseline_sampled = False
                self._previous_is_feedback = False
                self._status = MotionStatus(source=source, started_at=time.monotonic())
                lease = MotionLease(self, self._token, source)
                self._event("info", f"Motion acquired: {source.name}")
                return lease

    def _active(self, lease: MotionLease) -> bool:
        with self._lock:
            return self._token is lease._token

    def _check(self, lease: MotionLease) -> None:
        with self._lock:
            if self._token is not lease._token:
                raise MotionPreempted(f"Motion lease for {lease.source.name} is no longer active")

    def _revoke(self, error: str | None = None) -> MotionSource | None:
        owner = self._status.source
        callback = self._on_cancel
        self._token = None
        self._on_cancel = None
        self._previous = None
        self._baseline_sampled = False
        self._previous_is_feedback = False
        self._status = replace(
            self._status,
            source=None,
            mode=MotionMode.IDLE,
            running=False,
            started_at=None,
            error=error,
        )
        if callback is not None:
            try:
                callback()
            except Exception:
                logger.exception("Motion cancellation callback failed for %s", owner)
        return owner

    def _stop_current(self, reason: str, error: str | None = None) -> None:
        with self._ownership_transition():
            owner = self._revoke(error)
            try:
                self._executor.stop()
            except Exception as exc:
                self._status = replace(self._status, error=str(exc))
                self._event("error", f"Motion stop failed: {owner}, {exc}")
                raise
            self._event("info", f"Motion stopped: {owner.name if owner else 'IDLE'} ({reason})")

    def stop_current(self, reason: str = "stop requested") -> None:
        with self._lock:
            self._stop_current(reason)

    def cancel_all(self, reason: str = "all motion cancelled") -> None:
        with self._lock:
            self._stop_current(reason)

    def _release(self, lease: MotionLease, error: Exception | str | None) -> None:
        with self._lock:
            if not self._active(lease):
                return
            self._stop_current("lease released", str(error) if error is not None else None)
            self._event("info", f"Motion released: {lease.source.name}")

    def _failed(self, exc: Exception) -> None:
        with self._ownership_transition():
            message = str(exc)
            owner = self._revoke(message)
            try:
                self._executor.stop()
            except Exception as stop_error:
                self._event("error", f"Motion cleanup stop failed: {stop_error}")
            self._event("error", f"Motion failed: {owner.name if owner else 'IDLE'} ({message})")

    def _prime_servo_baseline(self) -> None:
        if self._baseline_sampled:
            return
        positions = self._executor.joint_position_rad()
        if positions is not None:
            baseline = JointTarget(positions, time.monotonic())
            self._safety.validate_joint_target(baseline)
            self._previous = baseline
            self._previous_is_feedback = True
        self._baseline_sampled = True

    def _open_servo(self, lease: MotionLease, vmax: float, amax: float, jmax: float) -> None:
        with self._lock:
            self._check(lease)
            try:
                self._prime_servo_baseline()
                self._executor.open_servo(vmax, amax, jmax)
                self._status = replace(self._status, mode=MotionMode.SERVO_JOINT, running=True)
            except Exception as exc:
                self._failed(exc)
                raise

    def _execute(
        self,
        lease: MotionLease,
        mode: MotionMode,
        target: JointTarget | TcpTarget,
        send: Callable[[], Any],
    ) -> Any:
        with self._lock:
            self._check(lease)
            try:
                if mode is MotionMode.TCP_MOVE:
                    self._safety.validate_tcp_target(target)
                else:
                    if mode is MotionMode.SERVO_JOINT:
                        self._prime_servo_baseline()
                    self._safety.validate_joint_target(
                        target,
                        previous=self._previous,
                        mode=mode,
                        validate_velocity=not self._previous_is_feedback,
                    )
                result = send()
                if result is not False:
                    if isinstance(target, JointTarget):
                        self._last_joint_target = target
                    else:
                        self._last_tcp_target = target
                    self._status = replace(
                        self._status, mode=mode, running=True, last_command_at=time.monotonic()
                    )
                    if mode is MotionMode.SERVO_JOINT:
                        self._previous = target
                        self._previous_is_feedback = False
                    else:
                        self._previous = None
                        self._baseline_sampled = False
                        self._previous_is_feedback = False
                return result
            except Exception as exc:
                self._failed(exc)
                raise

    def _stop_lease(self, lease: MotionLease) -> None:
        with self._lock:
            if not self._active(lease):
                return
            try:
                self._executor.stop()
                self._previous = None
                self._baseline_sampled = False
                self._previous_is_feedback = False
                self._status = replace(self._status, mode=MotionMode.IDLE, running=False)
            except Exception as exc:
                self._failed(exc)
                raise
