
from __future__ import annotations

import pytest

from test.workbench.fakes.ui import command_availability
from core.workbench.core.state_machine import Command, WorkflowState


def test_offline_only_allows_connect_workflow_control() -> None:
    policy = command_availability(
        WorkflowState.OFFLINE,
        episode_active=False,
        episode_pending=False,
    )

    assert policy[Command.CONNECT]
    assert not policy[Command.POWER_ON]
    assert not policy[Command.START_TELEOP]
    assert not policy[Command.START_EPISODE]
    assert policy[Command.EMERGENCY_STOP]


def test_connected_allows_power_and_estop() -> None:
    policy = command_availability(
        WorkflowState.CONNECTED,
        episode_active=False,
        episode_pending=False,
    )

    assert policy[Command.POWER_ON]
    assert policy[Command.EMERGENCY_STOP]
    assert not policy[Command.START_TELEOP]


def test_robot_enabled_allows_start_teleop() -> None:
    policy = command_availability(
        WorkflowState.ROBOT_ENABLED,
        episode_active=False,
        episode_pending=False,
    )

    assert policy[Command.START_TELEOP]
    assert policy[Command.EMERGENCY_STOP]
    assert not policy[Command.START_EPISODE]


def test_teleop_running_allows_episode_start() -> None:
    policy = command_availability(
        WorkflowState.TELEOP_RUNNING,
        episode_active=False,
        episode_pending=False,
    )

    assert policy[Command.START_EPISODE]
    assert policy[Command.EMERGENCY_STOP]
    assert not policy[Command.SAVE_SUCCESS]
    assert not policy[Command.DISCARD_EPISODE]


def test_zero_frame_recording_allows_stop_or_discard() -> None:
    policy = command_availability(
        WorkflowState.TELEOP_RUNNING,
        episode_active=True,
        episode_pending=False,
    )

    assert policy[Command.STOP_EPISODE]
    assert not policy[Command.START_EPISODE]
    assert not policy[Command.SAVE_SUCCESS]
    assert not policy[Command.SAVE_FAILURE]
    assert not policy[Command.FINISH_EPISODE]
    assert policy[Command.DISCARD_EPISODE]


def test_stopped_pending_recording_allows_save_discard_and_save_then_next() -> None:
    policy = command_availability(
        WorkflowState.TELEOP_RUNNING,
        episode_active=False,
        episode_pending=True,
    )

    assert not policy[Command.START_EPISODE]
    assert policy[Command.SAVE_SUCCESS]
    assert policy[Command.SAVE_FAILURE]
    assert policy[Command.DISCARD_EPISODE]
    assert not policy[Command.STOP_EPISODE]


@pytest.mark.parametrize(
    "safe_state",
    [WorkflowState.FAULT, WorkflowState.ESTOP],
)
def test_safe_state_allows_only_failure_resolution_for_pending_episode(
    safe_state,
) -> None:
    policy = command_availability(
        safe_state,
        episode_active=False,
        episode_pending=True,
    )

    assert not policy[Command.START_EPISODE]
    assert not policy[Command.SAVE_SUCCESS]
    assert policy[Command.SAVE_FAILURE]
    assert policy[Command.DISCARD_EPISODE]


def test_robot_enabled_allows_full_resolution_for_pending_episode() -> None:
    # Stopping teleop can leave buffered data on ROBOT_ENABLED.
    policy = command_availability(
        WorkflowState.ROBOT_ENABLED,
        episode_active=False,
        episode_pending=True,
    )

    assert policy[Command.SAVE_SUCCESS]
    assert policy[Command.SAVE_FAILURE]
    assert policy[Command.DISCARD_EPISODE]
    assert not policy[Command.STOP_EPISODE]
    assert policy[Command.START_TELEOP]


def test_fault_allows_escalation_to_estop_but_estop_does_not() -> None:
    fault = command_availability(
        WorkflowState.FAULT,
        episode_active=False,
        episode_pending=False,
    )
    estop = command_availability(
        WorkflowState.ESTOP,
        episode_active=False,
        episode_pending=False,
    )

    assert fault[Command.EMERGENCY_STOP]
    assert not estop[Command.EMERGENCY_STOP]


def test_fault_without_pending_episode_has_no_episode_resolution_controls() -> None:
    policy = command_availability(
        WorkflowState.FAULT,
        episode_active=False,
        episode_pending=False,
    )

    assert not policy[Command.SAVE_FAILURE]
    assert not policy[Command.DISCARD_EPISODE]
