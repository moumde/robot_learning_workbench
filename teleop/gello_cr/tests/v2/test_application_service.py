from __future__ import annotations

import pytest

from gello_cr.app.events import EventLevel
from gello_cr.app.service import ApplicationService
from gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    WorkflowStateMachine,
)


def _service_at(state: WorkflowState) -> ApplicationService:
    machine = WorkflowStateMachine(state=state, recovery_state=state)
    return ApplicationService(state_machine=machine)


def test_normal_command_runs_handler_before_state_transition() -> None:
    service = _service_at(WorkflowState.OFFLINE)
    observed = []

    def handler(payload):
        observed.append(service.state)
        return payload["value"]

    service.set_handler(Command.CONNECT, handler)
    result = service.dispatch(Command.CONNECT, {"value": 7})

    assert observed == [WorkflowState.OFFLINE]
    assert result.value == 7
    assert result.previous_state is WorkflowState.OFFLINE
    assert result.state is WorkflowState.CONNECTED
    assert service.state is WorkflowState.CONNECTED


def test_failed_normal_handler_leaves_state_unchanged() -> None:
    service = _service_at(WorkflowState.CONNECTED)

    def fail(_payload):
        raise RuntimeError("power failed")

    service.set_handler(Command.POWER_ON, fail)

    with pytest.raises(RuntimeError, match="power failed"):
        service.dispatch(Command.POWER_ON)

    assert service.state is WorkflowState.CONNECTED
    assert "power failed" in service.snapshot().last_error


def test_save_failure_keeps_recording_state() -> None:
    service = _service_at(WorkflowState.TELEOP_RUNNING)
    from gello_cr.core.state_machine import RecordingState
    service._state_machine.recording_state = RecordingState.PENDING

    def fail(_payload):
        raise IOError("disk full")

    service.set_handler(Command.SAVE_SUCCESS, fail)

    with pytest.raises(IOError, match="disk full"):
        service.dispatch(Command.SAVE_SUCCESS)

    assert service.state is WorkflowState.TELEOP_RUNNING


def test_invalid_transition_never_calls_handler() -> None:
    service = _service_at(WorkflowState.OFFLINE)
    called = []

    service.set_handler(
        Command.START_TELEOP,
        lambda payload: called.append(payload),
    )

    with pytest.raises(InvalidTransition):
        service.dispatch(Command.START_TELEOP)

    assert called == []
    assert service.state is WorkflowState.OFFLINE


def test_emergency_stop_enters_estop_before_handler_runs() -> None:
    service = _service_at(WorkflowState.TELEOP_RUNNING)
    observed = []

    service.set_handler(
        Command.EMERGENCY_STOP,
        lambda payload: observed.append(service.state),
    )
    service.dispatch(Command.EMERGENCY_STOP)

    assert observed == [WorkflowState.ESTOP]
    assert service.state is WorkflowState.ESTOP


def test_failed_emergency_handler_still_leaves_service_in_estop() -> None:
    service = _service_at(WorkflowState.TELEOP_RUNNING)

    def fail(_payload):
        assert service.state is WorkflowState.ESTOP
        raise RuntimeError("stop transport failed")

    service.set_handler(Command.EMERGENCY_STOP, fail)

    with pytest.raises(RuntimeError, match="stop transport failed"):
        service.dispatch(Command.EMERGENCY_STOP)

    assert service.state is WorkflowState.ESTOP


def test_estop_reset_from_recording_never_auto_resumes_teleop() -> None:
    service = _service_at(WorkflowState.TELEOP_RUNNING)

    service.dispatch(Command.EMERGENCY_STOP)
    assert service.state is WorkflowState.ESTOP

    service.dispatch(Command.RESET_ESTOP)
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_fault_reset_from_teleop_never_auto_resumes_teleop() -> None:
    service = _service_at(WorkflowState.TELEOP_RUNNING)

    service.dispatch(Command.REPORT_FAULT)
    assert service.state is WorkflowState.FAULT

    service.dispatch(Command.RESET_FAULT)
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_failed_reset_handler_keeps_estop_state() -> None:
    service = _service_at(WorkflowState.TELEOP_RUNNING)
    service.dispatch(Command.EMERGENCY_STOP)

    service.set_handler(
        Command.RESET_ESTOP,
        lambda payload: (_ for _ in ()).throw(
            RuntimeError("reset failed")
        ),
    )

    with pytest.raises(RuntimeError, match="reset failed"):
        service.dispatch(Command.RESET_ESTOP)

    assert service.state is WorkflowState.ESTOP


def test_payload_is_read_only_mapping_for_handler() -> None:
    service = _service_at(WorkflowState.OFFLINE)

    def handler(payload):
        with pytest.raises(TypeError):
            payload["changed"] = True
        return payload["name"]

    service.set_handler(Command.CONNECT, handler)
    result = service.dispatch(Command.CONNECT, {"name": "robot"})

    assert result.value == "robot"


def test_subscriber_receives_monotonic_event_sequence() -> None:
    service = _service_at(WorkflowState.OFFLINE)
    events = []
    service.subscribe(events.append)

    service.dispatch(Command.CONNECT)
    service.dispatch(Command.POWER_ON)

    assert [event.sequence for event in events] == list(
        range(1, len(events) + 1)
    )
    assert events[-1].state is WorkflowState.ROBOT_ENABLED


def test_unsubscribe_stops_future_events() -> None:
    service = _service_at(WorkflowState.OFFLINE)
    events = []
    unsubscribe = service.subscribe(events.append)

    service.dispatch(Command.CONNECT)
    count = len(events)
    unsubscribe()
    service.dispatch(Command.POWER_ON)

    assert len(events) == count


def test_bad_subscriber_does_not_break_command_or_other_subscribers() -> None:
    service = _service_at(WorkflowState.OFFLINE)
    events = []

    def broken(_event):
        raise RuntimeError("UI observer failed")

    service.subscribe(broken)
    service.subscribe(events.append)

    service.dispatch(Command.CONNECT)

    assert service.state is WorkflowState.CONNECTED
    assert events


def test_rejected_command_emits_warning_event() -> None:
    service = _service_at(WorkflowState.OFFLINE)
    events = []
    service.subscribe(events.append)

    with pytest.raises(InvalidTransition):
        service.dispatch(Command.START_EPISODE)

    assert events[-1].kind == "command_rejected"
    assert events[-1].level is EventLevel.WARNING
    assert events[-1].state is WorkflowState.OFFLINE
