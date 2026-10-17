
from __future__ import annotations

import pytest

from gello_cr.app.runtime_bindings import RuntimeCommandBindings
from gello_cr.app.service import ApplicationService
from gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    RecordingState,
    WorkflowStateMachine,
)


class Teleop:
    def emergency_stop(self, reason):
        return reason

    def start_follow(self):
        return None

    def stop_follow(self, reason):
        return reason


class Recorder:
    def __init__(self):
        self.calls = []

    def save_episode(self, outcome="success", notes=""):
        self.calls.append(("save", outcome, notes))

    def discard_episode(self):
        self.calls.append(("discard",))

    def start_episode(self, task, root, metadata=None):
        self.calls.append(("start", task, root, metadata))


def _bound_service(state, recovery):
    service = ApplicationService(
        state_machine=WorkflowStateMachine(
            state=state,
            recovery_state=recovery,
            recording_state=RecordingState.PENDING,
        )
    )
    recorder = Recorder()
    RuntimeCommandBindings(
        service,
        teleop_engine=Teleop(),
        recorder=recorder,
    ).install()
    return service, recorder


@pytest.mark.parametrize(
    "safe_state",
    [WorkflowState.FAULT, WorkflowState.ESTOP],
)
def test_failure_episode_can_be_saved_without_leaving_safe_state(
    safe_state,
) -> None:
    service, recorder = _bound_service(
        safe_state,
        WorkflowState.ROBOT_ENABLED,
    )
    service.dispatch(
        Command.SAVE_FAILURE,
        {"notes": "faulted rollout"},
    )
    assert recorder.calls == [
        ("save", "failure", "faulted rollout")
    ]
    assert service.state is safe_state


@pytest.mark.parametrize(
    "safe_state",
    [WorkflowState.FAULT, WorkflowState.ESTOP],
)
def test_episode_can_be_discarded_without_leaving_safe_state(
    safe_state,
) -> None:
    service, recorder = _bound_service(
        safe_state,
        WorkflowState.ROBOT_ENABLED,
    )
    service.dispatch(Command.DISCARD_EPISODE)
    assert recorder.calls == [("discard",)]
    assert service.state is safe_state


@pytest.mark.parametrize(
    "safe_state",
    [WorkflowState.FAULT, WorkflowState.ESTOP],
)
def test_success_save_is_forbidden_in_safe_state(safe_state) -> None:
    service, recorder = _bound_service(
        safe_state,
        WorkflowState.ROBOT_ENABLED,
    )
    with pytest.raises(InvalidTransition):
        service.dispatch(Command.SAVE_SUCCESS)
    assert recorder.calls == []
    assert service.state is safe_state


def test_success_episode_can_be_saved_from_robot_enabled_after_home() -> None:
    service, recorder = _bound_service(
        WorkflowState.ROBOT_ENABLED,
        WorkflowState.ROBOT_ENABLED,
    )
    service.dispatch(
        Command.SAVE_SUCCESS,
        {"notes": "completed before home"},
    )
    assert recorder.calls == [
        ("save", "success", "completed before home")
    ]
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_estop_from_recording_keeps_robot_enabled_recovery_target() -> None:
    machine = WorkflowStateMachine(
        state=WorkflowState.TELEOP_RUNNING,
        recovery_state=WorkflowState.TELEOP_RUNNING,
        recording_state=RecordingState.PENDING,
    )
    service = ApplicationService(state_machine=machine)
    recorder = Recorder()
    RuntimeCommandBindings(
        service,
        teleop_engine=Teleop(),
        recorder=recorder,
    ).install()

    service.dispatch(Command.EMERGENCY_STOP)
    service.dispatch(Command.SAVE_FAILURE)

    assert machine.recovery_state is WorkflowState.ROBOT_ENABLED
    assert service.state is WorkflowState.ESTOP
