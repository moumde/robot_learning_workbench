"""Application command/event/state orchestration.

Normal command handlers execute outside the state lock. This allows
REPORT_FAULT / EMERGENCY_STOP to preempt a long-running lifecycle/recording
handler while preserving one-at-a-time normal command execution.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from teleop.gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    RecordingState,
    WorkflowState,
    WorkflowStateMachine,
)

from .events import AppEvent, EventLevel
from .permissions import SAFETY_COMMANDS, OperationContext, operation_permission

CommandHandler = Callable[[Mapping[str, Any]], Any]
EventSubscriber = Callable[[AppEvent], None]

_PRETRANSITION_COMMANDS = frozenset(
    {
        Command.REPORT_FAULT,
        Command.EMERGENCY_STOP,
        Command.STOP_MOTION,
    }
)


class CommandSuperseded(RuntimeError):
    """A normal handler finished after a safety transition had taken priority."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: Command
    previous_state: WorkflowState
    state: WorkflowState
    value: Any = None


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    state: WorkflowState
    recovery_state: WorkflowState
    event_sequence: int
    last_error: str
    recording_state: RecordingState = RecordingState.IDLE
    active_command: Command | None = None


class ApplicationService:
    """Single application-layer command dispatcher.

    Normal commands are serialized by ``_normal_dispatch_lock`` but their
    handlers run without holding ``_lock``. Safety commands therefore remain
    able to pretransition the workflow while an opaque lifecycle/recording
    operation is still in progress.

    If a normal handler later returns after FAULT/ESTOP took priority, its
    original workflow transition is suppressed and the active safety handler is
    reasserted once.
    """

    def __init__(
        self,
        *,
        state_machine: WorkflowStateMachine | None = None,
        handlers: Mapping[Command, CommandHandler] | None = None,
    ) -> None:
        self._state_machine = state_machine or WorkflowStateMachine()
        self._handlers: dict[Command, CommandHandler] = dict(handlers or {})
        self._subscribers: list[EventSubscriber] = []
        self._lock = threading.RLock()
        self._normal_dispatch_lock = threading.Lock()
        self._event_sequence = 0
        self._last_error = ""
        self._preemption_generation = 0
        self._recording_snapshot = None
        self._runtime_snapshot = None
        self._readiness_snapshot = None
        self._active_command = None
        self._last_safety_command = None
        self._last_safety_generation = None

    def set_recording_snapshot(self, provider):
        self._recording_snapshot = provider

    def set_permission_sources(self, *, runtime_snapshot=None, readiness_snapshot=None):
        self._runtime_snapshot = runtime_snapshot
        self._readiness_snapshot = readiness_snapshot

    def _sync_recording(self):
        if self._recording_snapshot is not None:
            value = self._recording_snapshot()
            self._state_machine.recording_state = (
                RecordingState.RECORDING
                if value.get("episode_active")
                else RecordingState.PENDING
                if value.get("episode_pending", bool(value.get("buffered_frames")))
                else RecordingState.IDLE
            )
            return value
        return None

    @property
    def state(self) -> WorkflowState:
        with self._lock:
            return self._state_machine.state

    def snapshot(self) -> ApplicationSnapshot:
        with self._lock:
            self._sync_recording()
            return ApplicationSnapshot(
                state=self._state_machine.state,
                recovery_state=self._state_machine.recovery_state,
                event_sequence=self._event_sequence,
                last_error=self._last_error,
                recording_state=self._state_machine.recording_state,
                active_command=self._active_command,
            )

    def permission(self, command: Command, payload: Mapping[str, Any] | None = None):
        with self._lock:
            return self._permission_locked(command, payload)

    def can(self, command: Command, payload: Mapping[str, Any] | None = None) -> bool:
        return self.permission(command, payload).allowed

    def _permission_locked(self, command, payload=None):
        # STOP/F12 must never wait for recorder/device observations.
        safety = command in SAFETY_COMMANDS
        recorder = None if safety else self._sync_recording()
        runtime = self._runtime_snapshot() if not safety and self._runtime_snapshot else None
        readiness = self._readiness_snapshot() if not safety and self._readiness_snapshot else None
        return operation_permission(
            command,
            OperationContext(
                self._state_machine.state,
                self._state_machine.recording_state,
                recorder,
                runtime,
                readiness,
            ),
            payload,
        )

    def set_handler(
        self,
        command: Command,
        handler: CommandHandler | None,
    ) -> None:
        with self._lock:
            if handler is None:
                self._handlers.pop(command, None)
            else:
                self._handlers[command] = handler

    def subscribe(
        self,
        subscriber: EventSubscriber,
    ) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            with self._lock:
                try:
                    self._subscribers.remove(subscriber)
                except ValueError:
                    pass

        return unsubscribe

    def dispatch(
        self,
        command: Command,
        payload: Mapping[str, Any] | None = None,
    ) -> CommandResult:
        data = MappingProxyType(dict(payload or {}))

        if command in (Command.RETURN_HOME, Command.HOME_AND_SAVE_EPISODE):
            return self._dispatch_home(data, save_episode=command is Command.HOME_AND_SAVE_EPISODE)

        if command in _PRETRANSITION_COMMANDS:
            return self._dispatch_safety(command, data)

        with self._normal_dispatch_lock:
            if command is Command.START_COLLECTION:
                return self._dispatch_collection_start(data)
            if command is Command.FINISH_COLLECTION:
                return self._dispatch_collection_finish(data)
            return self._dispatch_normal(command, data)

    def _dispatch_home(self, data: Mapping[str, Any], *, save_episode=False) -> CommandResult:
        command = Command.HOME_AND_SAVE_EPISODE if save_episode else Command.RETURN_HOME
        with self._lock:
            self._validate_locked(command, data)
            handler = self._handlers[Command.RETURN_HOME]
            previous = self._state_machine.state
            self._preemption_generation += 1
            generation = self._preemption_generation
            self._state_machine.apply(Command.RETURN_HOME)
            self._emit_locked(
                kind="state_changed",
                level=EventLevel.INFO,
                message="正在回 HOME，到位后保存成功 Episode"
                if save_episode
                else "机械臂正在回 HOME",
                command=command,
                details=data,
            )
        try:
            value = handler(data)
        except Exception as exc:
            logging.getLogger("workbench.application").exception("RETURN_HOME failed")
            if self._preemption_generation != generation:
                raise CommandSuperseded("HOME 回位被停止或故障中断") from exc
            self.report_external_fault(f"HOME 回位失败：{exc}")
            raise
        with self._lock:
            if (
                self._preemption_generation != generation
                or self.state is not WorkflowState.RETURNING_HOME
            ):
                raise CommandSuperseded("HOME 回位被停止或故障中断")
            state = self._state_machine.apply(Command.HOME_COMPLETED)
            self._last_error = ""
            self._emit_locked(
                kind="home_arrived" if save_episode else "command_completed",
                level=EventLevel.INFO,
                message="机械臂已回 HOME，保持停止",
                command=command,
                details=data,
            )
        if save_episode:
            with self._normal_dispatch_lock:
                result = self._dispatch_collection_finish(
                    MappingProxyType({"outcome": "success"}), expected_generation=generation
                )
            return self._collection_completed(command, previous, result, data)
        return CommandResult(command, previous, state, value)

    def _collection_completed(self, command, previous, result, data):
        with self._lock:
            self._emit_locked(
                kind="command_completed",
                level=EventLevel.INFO,
                message="采集已开始"
                if command is Command.START_COLLECTION
                else "Episode 已保存，保持停止",
                command=command,
                details=data,
            )
        return CommandResult(command, previous, result.state, result.value)

    def _dispatch_collection_start(self, data):
        with self._lock:
            self._validate_locked(Command.START_COLLECTION, data)
            previous = self._state_machine.state
            generation = self._preemption_generation
        # Reject incomplete form data before creating a motion producer.
        for key in ("task", "base_root"):
            if not str(data.get(key, "")).strip():
                raise ValueError(f"{key} is required")
        if data.get("metadata") is not None and not isinstance(data["metadata"], Mapping):
            raise TypeError("metadata must be a mapping")
        started_follow = previous is WorkflowState.ROBOT_ENABLED
        if started_follow:
            self._dispatch_normal(Command.START_TELEOP, data, expected_generation=generation)
        try:
            result = self._dispatch_normal(
                Command.START_EPISODE, data, expected_generation=generation
            )
        except Exception:
            with self._lock:
                owns_follow = (
                    started_follow
                    and self._preemption_generation == generation
                    and self._state_machine.state is WorkflowState.TELEOP_RUNNING
                )
            if owns_follow:
                self._collection_stop(Command.STOP_TELEOP, generation)
            raise
        return self._collection_completed(Command.START_COLLECTION, previous, result, data)

    def _collection_stop(self, command, generation):
        with self._lock:
            if self._preemption_generation != generation:
                raise CommandSuperseded("采集停止已被 HOME、停止或故障中断")
            payload = {"reason": "结束采集"}
            if command is Command.STOP_TELEOP and self._runtime_snapshot is not None:
                motion = (self._runtime_snapshot() or {}).get("motion", {})
                payload["follow_started_at"] = motion.get("started_at")
        try:
            return self._dispatch_normal(
                command, MappingProxyType(payload), expected_generation=generation
            )
        except CommandSuperseded:
            raise
        except Exception as exc:
            # A failed stop acknowledgement cannot turn into a successful save
            # or leave the UI advertising a normal, enabled motion state.
            try:
                self.dispatch(Command.REPORT_FAULT, {"reason": f"采集停止失败：{exc}"})
            except Exception:
                logging.getLogger("workbench.application").exception("Collection fault stop failed")
            raise

    def _dispatch_collection_finish(self, data, *, expected_generation=None):
        with self._lock:
            if expected_generation is not None and (
                self._preemption_generation != expected_generation
                or self._state_machine.state is not WorkflowState.ROBOT_ENABLED
                or self._state_machine.recording_state is not RecordingState.RECORDING
            ):
                raise CommandSuperseded("HOME 完成后的保存已被其他操作中断")
            self._validate_locked(Command.FINISH_COLLECTION, data)
            previous = self._state_machine.state
            generation = self._preemption_generation
        stop = {
            WorkflowState.TELEOP_RUNNING: Command.STOP_TELEOP,
            WorkflowState.REPLAY_RUNNING: Command.STOP_TRAJECTORY_REPLAY,
            WorkflowState.POINT_MOVE_RUNNING: Command.STOP_POINT_MOTION,
        }.get(previous)
        if stop is not None:
            self._collection_stop(stop, generation)
        result = self._dispatch_normal(Command.FINISH_EPISODE, data, expected_generation=generation)
        return self._collection_completed(Command.FINISH_COLLECTION, previous, result, data)

    def _dispatch_safety(
        self,
        command: Command,
        data: Mapping[str, Any],
    ) -> CommandResult:
        with self._lock:
            previous_state = self._state_machine.state
            self._validate_locked(command, data)
            handler = self._handlers.get(command)
            new_state = self._state_machine.apply(command)
            self._last_safety_command = command
            self._preemption_generation += 1
            self._last_safety_generation = self._preemption_generation
            self._last_error = ""
            self._emit_locked(
                kind="state_changed",
                level=EventLevel.WARNING,
                message=(f"{previous_state.name} -> {new_state.name} by {command.name}"),
                command=command,
                details=data,
            )

        try:
            value = handler(data) if handler is not None else None
        except Exception as exc:
            with self._lock:
                self._last_error = f"{type(exc).__name__}: {exc}"
                if command is Command.STOP_MOTION and self._state_machine.can(Command.REPORT_FAULT):
                    self._state_machine.apply(Command.REPORT_FAULT)
                    self._last_safety_command = Command.REPORT_FAULT
                self._emit_locked(
                    kind="command_failed",
                    level=EventLevel.ERROR,
                    message=self._last_error,
                    command=command,
                    details=data,
                )
            raise

        with self._lock:
            current_state = self._state_machine.state
            self._emit_locked(
                kind="command_completed",
                level=EventLevel.INFO,
                message=f"{command.name} completed",
                command=command,
                details=data,
            )
            return CommandResult(
                command=command,
                previous_state=previous_state,
                state=current_state,
                value=value,
            )

    def _apply_normal_transition_locked(self, command):
        if (
            command
            in (
                Command.STOP_TRAJECTORY_RECORDING,
                Command.CANCEL_TRAJECTORY_RECORDING,
            )
            and self._runtime_snapshot is not None
        ):
            # Resolving a preempted recording must not hide the newer follow
            # session that its lease-scoped cleanup deliberately leaves running.
            if (self._runtime_snapshot() or {}).get("state") == "following":
                return self._state_machine.state
        return self._state_machine.apply(command, validated=True)

    def _dispatch_normal(
        self,
        command: Command,
        data: Mapping[str, Any],
        *,
        expected_generation=None,
    ) -> CommandResult:
        with self._lock:
            if (
                expected_generation is not None
                and self._preemption_generation != expected_generation
            ):
                raise CommandSuperseded("采集操作已被 HOME、停止或故障中断")
            generation = self._preemption_generation
            previous_state = self._state_machine.state
            self._validate_locked(command, data)
            handler = self._handlers.get(command)
            self._active_command = command

        try:
            value = handler(data) if handler is not None else None
        except Exception as exc:
            with self._lock:
                if (
                    command is Command.STOP_TRAJECTORY_RECORDING
                    and getattr(exc, "trajectory_recording_stopped", False)
                    and self._state_machine.state is WorkflowState.TELEOP_RUNNING
                    and generation == self._preemption_generation
                ):
                    self._apply_normal_transition_locked(command)
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._emit_locked(
                    kind="command_failed",
                    level=EventLevel.ERROR,
                    message=self._last_error,
                    command=command,
                    details=data,
                )
            raise
        finally:
            with self._lock:
                self._active_command = None

        safety_reassert: (
            tuple[
                Command,
                CommandHandler,
                Mapping[str, Any],
            ]
            | None
        ) = None

        with self._lock:
            current_state = self._state_machine.state
            if current_state is not previous_state or generation != self._preemption_generation:
                message = (
                    f"{command.name} handler completed after workflow changed "
                    f"{previous_state.name} -> {current_state.name}; "
                    "normal transition suppressed"
                )
                self._emit_locked(
                    kind="command_superseded",
                    level=EventLevel.WARNING,
                    message=message,
                    command=command,
                    details=data,
                )
                safety_reassert = self._safety_reassert_locked(
                    current_state,
                    superseded_command=command,
                )
            else:
                new_state = self._apply_normal_transition_locked(command)
                self._last_error = ""
                self._emit_locked(
                    kind="state_changed",
                    level=EventLevel.INFO,
                    message=(f"{previous_state.name} -> {new_state.name} by {command.name}"),
                    command=command,
                    details=data,
                )
                self._emit_locked(
                    kind="command_completed",
                    level=EventLevel.INFO,
                    message=f"{command.name} completed",
                    command=command,
                    details=data,
                )
                return CommandResult(
                    command=command,
                    previous_state=previous_state,
                    state=new_state,
                    value=value,
                )

        if safety_reassert is not None:
            safety_command, safety_handler, safety_payload = safety_reassert
            try:
                safety_handler(safety_payload)
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._emit_locked(
                        kind="safety_reassert_failed",
                        level=EventLevel.ERROR,
                        message=self._last_error,
                        command=safety_command,
                        details=safety_payload,
                    )
            else:
                with self._lock:
                    self._emit_locked(
                        kind="safety_reasserted",
                        level=EventLevel.WARNING,
                        message=(
                            f"{safety_command.name} reasserted after {command.name} completed late"
                        ),
                        command=safety_command,
                        details=safety_payload,
                    )

        raise CommandSuperseded(f"{command.name} was superseded by {current_state.name}")

    def _validate_locked(
        self,
        command: Command,
        data: Mapping[str, Any],
    ) -> None:
        permission = self._permission_locked(command, data)
        if permission.allowed:
            return

        previous_state = self._state_machine.state
        message = f"{command.name} is not allowed from {previous_state.name}: {permission.reason}"
        self._emit_locked(
            kind="command_rejected",
            level=EventLevel.WARNING,
            message=message,
            command=command,
            details=data,
        )
        raise InvalidTransition(message)

    def _safety_reassert_locked(
        self,
        state: WorkflowState,
        *,
        superseded_command: Command,
    ) -> tuple[Command, CommandHandler, Mapping[str, Any]] | None:
        if state is WorkflowState.ESTOP:
            command = Command.EMERGENCY_STOP
        elif state is WorkflowState.FAULT:
            command = Command.REPORT_FAULT
        elif (
            self._last_safety_command is Command.STOP_MOTION
            and self._last_safety_generation == self._preemption_generation
            and state in (WorkflowState.ROBOT_ENABLED, WorkflowState.CONNECTED)
        ):
            command = Command.STOP_MOTION
        else:
            return None

        handler = self._handlers.get(command)
        if handler is None:
            return None

        payload = MappingProxyType(
            {
                "reason": (
                    f"reassert {state.name} after late {superseded_command.name} completion"
                ),
                "superseded_command": superseded_command.name,
            }
        )
        return command, handler, payload

    def report_external_fault(
        self,
        reason: str,
        details: Mapping[str, Any] | None = None,
    ) -> WorkflowState:
        """Synchronize a runtime fault that has already performed safe-stop."""

        message = str(reason).strip() or "runtime fault"
        data = MappingProxyType(dict(details or {}))

        with self._lock:
            current = self._state_machine.state

            if current is WorkflowState.ESTOP:
                if self._last_error != message:
                    self._last_error = message
                    self._emit_locked(
                        kind="external_fault_observed",
                        level=EventLevel.ERROR,
                        message=message,
                        command=Command.REPORT_FAULT,
                        details=data,
                    )
                return current

            if current is WorkflowState.FAULT:
                if self._last_error != message:
                    self._last_error = message
                    self._emit_locked(
                        kind="external_fault_observed",
                        level=EventLevel.ERROR,
                        message=message,
                        command=Command.REPORT_FAULT,
                        details=data,
                    )
                return current

            previous_state = current
            new_state = self._state_machine.apply(Command.REPORT_FAULT)
            self._last_error = message
            self._emit_locked(
                kind="state_changed",
                level=EventLevel.WARNING,
                message=(f"{previous_state.name} -> {new_state.name} by external runtime fault"),
                command=Command.REPORT_FAULT,
                details=data,
            )
            self._emit_locked(
                kind="external_fault_observed",
                level=EventLevel.ERROR,
                message=message,
                command=Command.REPORT_FAULT,
                details=data,
            )
            return new_state

    def _emit_locked(
        self,
        *,
        kind: str,
        level: EventLevel,
        message: str,
        command: Command | None,
        details: Mapping[str, Any],
    ) -> None:
        getattr(logging.getLogger("workbench.application"), level.value)(
            "%s [%s]: %s",
            kind,
            command.name if command is not None else "application",
            message,
            exc_info=level is EventLevel.ERROR and sys.exc_info()[0] is not None,
        )
        self._event_sequence += 1
        event = AppEvent(
            sequence=self._event_sequence,
            kind=kind,
            level=level,
            state=self._state_machine.state,
            message=message,
            command=command,
            details=details,
        )
        subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:
                logging.getLogger("workbench.application").exception("Event subscriber failed")
