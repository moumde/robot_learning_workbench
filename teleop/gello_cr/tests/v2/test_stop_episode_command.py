
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
    def start_follow(self):
        return None

    def stop_follow(self, reason):
        return reason

    def emergency_stop(self, reason):
        return reason


class Recorder:
    def __init__(self):
        self.stopped = 0

    def stop_episode(self):
        self.stopped += 1


def test_stop_episode_command_exists() -> None:
    assert Command.STOP_EPISODE.name == "STOP_EPISODE"


def test_recording_can_stop_episode_without_leaving_recording() -> None:
    machine = WorkflowStateMachine(state=WorkflowState.TELEOP_RUNNING, recording_state=RecordingState.RECORDING)

    assert machine.can(Command.STOP_EPISODE)
    assert machine.apply(Command.STOP_EPISODE) is WorkflowState.TELEOP_RUNNING


def test_application_dispatch_stop_episode_keeps_recording_state() -> None:
    service = ApplicationService(
        state_machine=WorkflowStateMachine(
            state=WorkflowState.TELEOP_RUNNING, recording_state=RecordingState.RECORDING
        )
    )

    result = service.dispatch(Command.STOP_EPISODE)

    assert result.previous_state is WorkflowState.TELEOP_RUNNING
    assert result.state is WorkflowState.TELEOP_RUNNING
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_runtime_binding_calls_recorder_stop_episode() -> None:
    service = ApplicationService(
        state_machine=WorkflowStateMachine(
            state=WorkflowState.TELEOP_RUNNING, recording_state=RecordingState.RECORDING
        )
    )
    recorder = Recorder()
    RuntimeCommandBindings(
        service,
        teleop_engine=Teleop(),
        recorder=recorder,
    ).install()

    service.dispatch(Command.STOP_EPISODE)

    assert recorder.stopped == 1
    assert service.state is WorkflowState.TELEOP_RUNNING


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.TELEOP_RUNNING,
        WorkflowState.ROBOT_ENABLED,
        WorkflowState.FAULT,
        WorkflowState.ESTOP,
    ],
)
def test_stop_episode_rejected_outside_recording(state) -> None:
    machine = WorkflowStateMachine(state=state)

    assert not machine.can(Command.STOP_EPISODE)
    with pytest.raises(InvalidTransition):
        machine.apply(Command.STOP_EPISODE)
