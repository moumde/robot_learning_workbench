import pytest

from gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    MotionState,
    RecordingState,
    RobotState,
    WorkflowState,
    WorkflowStateMachine,
)


def test_recording_is_independent_of_replay_and_its_completion():
    state = WorkflowStateMachine(WorkflowState.ROBOT_ENABLED)
    state.apply(Command.REPLAY_TRAJECTORY)
    with pytest.raises(InvalidTransition):
        state.apply(Command.START_EPISODE)
    assert state.apply(Command.START_EPISODE, source="replay") is WorkflowState.REPLAY_RUNNING
    assert state.recording_state is RecordingState.RECORDING
    assert state.apply(Command.TRAJECTORY_COMPLETED) is WorkflowState.ROBOT_ENABLED
    assert state.recording_state is RecordingState.RECORDING
    state.apply(Command.STOP_EPISODE)
    assert state.recording_state is RecordingState.PENDING
    state.apply(Command.SAVE_SUCCESS)
    assert state.recording_state is RecordingState.IDLE
    assert state.motion_state is MotionState.IDLE
    assert state.robot_state is RobotState.ENABLED


def test_teleop_and_recording_stop_are_independent():
    state = WorkflowStateMachine(WorkflowState.TELEOP_RUNNING)
    state.apply(Command.START_EPISODE)
    assert not state.can(Command.SAVE_SUCCESS)
    state.apply(Command.STOP_MOTION)
    assert state.robot_state is RobotState.ENABLED
    assert state.motion_state is MotionState.IDLE
    assert state.recording_state is RecordingState.RECORDING
    state.apply(Command.STOP_EPISODE)
    assert state.can(Command.SAVE_FAILURE)
    assert not state.can(Command.START_EPISODE)


@pytest.mark.parametrize("motion,source", [
    (WorkflowState.REPLAY_RUNNING, "replay"),
    (WorkflowState.POINT_MOVE_RUNNING, "point_move"),
])
def test_fault_preserves_episode_for_explicit_outcome(motion, source):
    state = WorkflowStateMachine(motion)
    state.apply(Command.START_EPISODE, source=source)
    state.apply(Command.EMERGENCY_STOP)
    assert state.robot_state is RobotState.ESTOP
    assert state.recording_state is RecordingState.RECORDING
    state.apply(Command.STOP_EPISODE)
    assert state.can(Command.SAVE_FAILURE)
    assert not state.can(Command.SAVE_SUCCESS)
