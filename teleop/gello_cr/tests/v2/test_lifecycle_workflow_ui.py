
from __future__ import annotations

from teleop.gello_cr.tests.fakes.ui import command_availability
from teleop.gello_cr.core.state_machine import Command, WorkflowState


def _policy(state):
    return command_availability(
        state,
        episode_active=False,
        episode_pending=False,
    )


def test_connected_exposes_power_on_and_disconnect() -> None:
    policy = _policy(WorkflowState.CONNECTED)

    assert policy[Command.POWER_ON]
    assert policy[Command.DISCONNECT]
    assert not policy[Command.POWER_OFF]


def test_robot_enabled_exposes_power_off_and_disconnect() -> None:
    policy = _policy(WorkflowState.ROBOT_ENABLED)

    assert policy[Command.POWER_OFF]
    assert policy[Command.DISCONNECT]
    assert not policy[Command.POWER_ON]


def test_fault_exposes_reset_fault_only() -> None:
    policy = _policy(WorkflowState.FAULT)

    assert policy[Command.RESET_FAULT]
    assert not policy[Command.RESET_ESTOP]
    assert not policy[Command.POWER_ON]
    assert not policy[Command.POWER_OFF]


def test_estop_exposes_reset_estop_only() -> None:
    policy = _policy(WorkflowState.ESTOP)

    assert policy[Command.RESET_ESTOP]
    assert not policy[Command.RESET_FAULT]
    assert not policy[Command.POWER_ON]
    assert not policy[Command.POWER_OFF]


def test_offline_does_not_expose_shutdown_or_reset_controls() -> None:
    policy = _policy(WorkflowState.OFFLINE)

    assert not policy[Command.DISCONNECT]
    assert not policy[Command.POWER_OFF]
    assert not policy[Command.RESET_FAULT]
    assert not policy[Command.RESET_ESTOP]
