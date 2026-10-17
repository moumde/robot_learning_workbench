
from __future__ import annotations

import pytest

from gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    WorkflowStateMachine,
)


def test_prepare_devices_is_connected_self_transition() -> None:
    machine = WorkflowStateMachine(
        state=WorkflowState.CONNECTED
    )

    assert machine.apply(
        Command.PREPARE_DEVICES
    ) is WorkflowState.CONNECTED


def test_prepare_devices_is_robot_enabled_self_transition() -> None:
    machine = WorkflowStateMachine(
        state=WorkflowState.ROBOT_ENABLED
    )

    assert machine.apply(
        Command.PREPARE_DEVICES
    ) is WorkflowState.ROBOT_ENABLED


@pytest.mark.parametrize(
    "state",
    (
        WorkflowState.OFFLINE,
        WorkflowState.CONNECTED,
        WorkflowState.ROBOT_ENABLED,
        WorkflowState.TELEOP_RUNNING,
    ),
)
def test_start_cameras_is_safe_self_transition(state) -> None:
    machine = WorkflowStateMachine(state=state)

    assert machine.apply(Command.START_CAMERAS) is state


@pytest.mark.parametrize("state", tuple(WorkflowState))
def test_stop_cameras_preserves_live_dagger_observations(
    state,
) -> None:
    machine = WorkflowStateMachine(state=state)
    if state is WorkflowState.DAGGER_RUNNING:
        with pytest.raises(InvalidTransition):
            machine.apply(Command.STOP_CAMERAS)
    else:
        assert machine.apply(Command.STOP_CAMERAS) is state


def test_prepare_devices_rejected_offline() -> None:
    machine = WorkflowStateMachine()

    with pytest.raises(InvalidTransition):
        machine.apply(Command.PREPARE_DEVICES)


@pytest.mark.parametrize(
    "state",
    (WorkflowState.FAULT, WorkflowState.ESTOP),
)
def test_start_cameras_rejected_in_safety_state(state) -> None:
    machine = WorkflowStateMachine(state=state)

    with pytest.raises(InvalidTransition):
        machine.apply(Command.START_CAMERAS)
