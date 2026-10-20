
from __future__ import annotations

from teleop.gello_cr.app.service import ApplicationService
from teleop.gello_cr.core.state_machine import WorkflowState, WorkflowStateMachine


def _service(state, recovery=None):
    return ApplicationService(
        state_machine=WorkflowStateMachine(
            state=state,
            recovery_state=recovery or state,
        )
    )


def test_external_fault_from_teleop_enters_fault() -> None:
    service = _service(WorkflowState.TELEOP_RUNNING)

    result = service.report_external_fault("tracking timeout")

    assert result is WorkflowState.FAULT
    assert service.state is WorkflowState.FAULT
    assert service.snapshot().last_error == "tracking timeout"


def test_external_fault_from_recording_uses_safe_recovery_target() -> None:
    service = _service(WorkflowState.TELEOP_RUNNING)

    service.report_external_fault("camera/robot fault")

    snapshot = service.snapshot()
    assert snapshot.state is WorkflowState.FAULT
    assert snapshot.recovery_state is WorkflowState.ROBOT_ENABLED


def test_external_fault_preserves_estop_priority() -> None:
    service = _service(
        WorkflowState.ESTOP,
        WorkflowState.ROBOT_ENABLED,
    )

    result = service.report_external_fault("runtime also faulted")

    assert result is WorkflowState.ESTOP
    assert service.state is WorkflowState.ESTOP
    assert service.snapshot().recovery_state is WorkflowState.ROBOT_ENABLED


def test_repeated_same_fault_is_idempotent() -> None:
    service = _service(WorkflowState.TELEOP_RUNNING)
    events = []
    service.subscribe(events.append)

    service.report_external_fault("same fault")
    first_count = len(events)
    service.report_external_fault("same fault")

    assert len(events) == first_count
    assert service.state is WorkflowState.FAULT


def test_new_fault_detail_updates_existing_fault_without_transition() -> None:
    service = _service(WorkflowState.TELEOP_RUNNING)
    events = []
    service.subscribe(events.append)

    service.report_external_fault("first")
    service.report_external_fault("second")

    assert service.state is WorkflowState.FAULT
    assert service.snapshot().last_error == "second"
    assert events[-1].kind == "external_fault_observed"
    assert events[-1].message == "second"


def test_external_fault_event_contains_runtime_details() -> None:
    service = _service(WorkflowState.ROBOT_ENABLED)
    events = []
    service.subscribe(events.append)

    service.report_external_fault(
        "feedback lost",
        {"runtime": "TeleopEngine"},
    )

    event = events[-1]
    assert event.kind == "external_fault_observed"
    assert event.details["runtime"] == "TeleopEngine"
