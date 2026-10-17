"""Single workflow state machine for the V2 operator application."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class WorkflowState(Enum):
    OFFLINE = auto()
    CONNECTED = auto()
    ROBOT_ENABLED = auto()
    TELEOP_RUNNING = auto()
    FAULT = auto()
    ESTOP = auto()
    RETURNING_HOME = auto()
    DAGGER_RUNNING = auto()
    REPLAY_RUNNING = auto()
    POINT_MOVE_RUNNING = auto()


class Command(Enum):
    STOP_MOTION = auto()
    LIST_DATASETS = auto()
    VALIDATE_DATASET = auto()
    REFRESH_ROBOT_STATUS = auto()
    CONNECT = auto()
    DISCONNECT = auto()
    PREPARE_DEVICES = auto()
    START_CAMERAS = auto()
    STOP_CAMERAS = auto()
    POWER_ON = auto()
    POWER_OFF = auto()
    START_TELEOP = auto()
    STOP_TELEOP = auto()
    START_EPISODE = auto()
    STOP_EPISODE = auto()
    FINISH_EPISODE = auto()
    FINALIZE_DATASET = auto()
    SELECT_DATASET_FORMAT = auto()
    CREATE_DATASET = auto()
    SCAN_RECOVERABLE_BATCHES = auto()
    RESUME_BATCH = auto()
    FINALIZE_BATCH = auto()
    DISCARD_BATCH = auto()
    RESOLVE_PARTIAL_EPISODE = auto()
    SUSPEND_BATCH = auto()
    SAVE_SUCCESS = auto()
    SAVE_FAILURE = auto()
    DISCARD_EPISODE = auto()
    REPORT_FAULT = auto()
    RESET_FAULT = auto()
    EMERGENCY_STOP = auto()
    RESET_ESTOP = auto()
    HOME_COMPLETED = auto()
    RETURN_HOME = auto()
    START_DAGGER = auto()
    STOP_DAGGER = auto()
    TOGGLE_INTERVENTION = auto()
    START_TRAJECTORY_RECORDING = auto()
    STOP_TRAJECTORY_RECORDING = auto()
    SAVE_TRAJECTORY = auto()
    CANCEL_TRAJECTORY_RECORDING = auto()
    LIST_TRAJECTORIES = auto()
    PREVIEW_TRAJECTORY = auto()
    IMPORT_TRAJECTORY = auto()
    REPLAY_TRAJECTORY = auto()
    STOP_TRAJECTORY_REPLAY = auto()
    TRAJECTORY_COMPLETED = auto()
    READ_MOTION_POSITION = auto()
    PLAN_MOTION = auto()
    EXECUTE_PLAN = auto()
    SAVE_MOTION_PLAN = auto()
    STOP_POINT_MOTION = auto()
    POINT_MOTION_COMPLETED = auto()


class InvalidTransition(RuntimeError):
    pass


class RobotState(Enum):
    OFFLINE = auto()
    CONNECTED = auto()
    ENABLED = auto()
    FAULT = auto()
    ESTOP = auto()


class MotionState(Enum):
    IDLE = auto()
    TELEOP = auto()
    REPLAY = auto()
    HOME = auto()
    POINT_MOVE = auto()
    POLICY = auto()


class RecordingState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PENDING = auto()
    SAVING = auto()
    FINALIZING = auto()
    RECOVERING = auto()


_MOTION = {
    WorkflowState.TELEOP_RUNNING: MotionState.TELEOP,
    WorkflowState.REPLAY_RUNNING: MotionState.REPLAY,
    WorkflowState.POINT_MOVE_RUNNING: MotionState.POINT_MOVE,
    WorkflowState.RETURNING_HOME: MotionState.HOME,
    WorkflowState.DAGGER_RUNNING: MotionState.POLICY,
}
_ENABLED = set(_MOTION) | {WorkflowState.ROBOT_ENABLED}
_TRANSITIONS = {
    (WorkflowState.OFFLINE, Command.CONNECT): WorkflowState.CONNECTED,
    (WorkflowState.CONNECTED, Command.POWER_ON): WorkflowState.ROBOT_ENABLED,
    (WorkflowState.CONNECTED, Command.DISCONNECT): WorkflowState.OFFLINE,
    (WorkflowState.ROBOT_ENABLED, Command.DISCONNECT): WorkflowState.OFFLINE,
    (WorkflowState.ROBOT_ENABLED, Command.POWER_OFF): WorkflowState.CONNECTED,
    (WorkflowState.ROBOT_ENABLED, Command.START_TELEOP): WorkflowState.TELEOP_RUNNING,
    (WorkflowState.TELEOP_RUNNING, Command.STOP_TELEOP): WorkflowState.ROBOT_ENABLED,
    (WorkflowState.ROBOT_ENABLED, Command.START_DAGGER): WorkflowState.DAGGER_RUNNING,
    (WorkflowState.DAGGER_RUNNING, Command.STOP_DAGGER): WorkflowState.ROBOT_ENABLED,
    (WorkflowState.DAGGER_RUNNING, Command.TOGGLE_INTERVENTION): WorkflowState.DAGGER_RUNNING,
    (WorkflowState.REPLAY_RUNNING, Command.TRAJECTORY_COMPLETED): WorkflowState.ROBOT_ENABLED,
    (WorkflowState.REPLAY_RUNNING, Command.STOP_TRAJECTORY_REPLAY): WorkflowState.ROBOT_ENABLED,
    (WorkflowState.POINT_MOVE_RUNNING, Command.POINT_MOTION_COMPLETED): WorkflowState.ROBOT_ENABLED,
    (WorkflowState.POINT_MOVE_RUNNING, Command.STOP_POINT_MOTION): WorkflowState.ROBOT_ENABLED,
}
for _state in (WorkflowState.ROBOT_ENABLED, WorkflowState.TELEOP_RUNNING):
    _TRANSITIONS[_state, Command.REPLAY_TRAJECTORY] = WorkflowState.REPLAY_RUNNING
    _TRANSITIONS[_state, Command.EXECUTE_PLAN] = WorkflowState.POINT_MOVE_RUNNING

_AUXILIARY = {
    Command.FINALIZE_DATASET,
    Command.SELECT_DATASET_FORMAT,
    Command.CREATE_DATASET,
    Command.SCAN_RECOVERABLE_BATCHES,
    Command.RESUME_BATCH,
    Command.FINALIZE_BATCH,
    Command.DISCARD_BATCH,
    Command.RESOLVE_PARTIAL_EPISODE,
    Command.SUSPEND_BATCH,
    Command.LIST_DATASETS,
    Command.VALIDATE_DATASET,
    Command.SAVE_MOTION_PLAN,
    Command.LIST_TRAJECTORIES,
    Command.PREVIEW_TRAJECTORY,
    Command.IMPORT_TRAJECTORY,
    Command.STOP_TRAJECTORY_RECORDING,
    Command.SAVE_TRAJECTORY,
    Command.CANCEL_TRAJECTORY_RECORDING,
    Command.STOP_CAMERAS,
}


@dataclass(slots=True)
class WorkflowStateMachine:
    """Robot/motion transitions and an independent Episode lifecycle."""

    state: WorkflowState = WorkflowState.OFFLINE
    recovery_state: WorkflowState = WorkflowState.OFFLINE
    recording_state: RecordingState = RecordingState.IDLE

    @property
    def robot_state(self):
        return {
            WorkflowState.OFFLINE: RobotState.OFFLINE,
            WorkflowState.CONNECTED: RobotState.CONNECTED,
            WorkflowState.FAULT: RobotState.FAULT,
            WorkflowState.ESTOP: RobotState.ESTOP,
        }.get(self.state, RobotState.ENABLED)

    @property
    def motion_state(self):
        return _MOTION.get(self.state, MotionState.IDLE)

    def can(self, command, *, source="teleop"):
        if command is Command.STOP_CAMERAS and self.state is WorkflowState.DAGGER_RUNNING:
            return False
        if command in _AUXILIARY:
            return True  # Concrete handlers enforce writer/session preconditions.
        if command is Command.START_EPISODE:
            return (
                self.state
                is {
                    "teleop": WorkflowState.TELEOP_RUNNING,
                    "replay": WorkflowState.REPLAY_RUNNING,
                    "point_move": WorkflowState.POINT_MOVE_RUNNING,
                }.get(source)
                and self.recording_state is RecordingState.IDLE
            )
        if command is Command.STOP_EPISODE:
            return self.recording_state is RecordingState.RECORDING
        if command in (Command.FINISH_EPISODE, Command.DISCARD_EPISODE):
            return self.recording_state in (RecordingState.RECORDING, RecordingState.PENDING)
        if command in (Command.SAVE_SUCCESS, Command.SAVE_FAILURE):
            return self.recording_state is RecordingState.PENDING and (
                command is not Command.SAVE_SUCCESS or self.state in _ENABLED
            )
        if (
            command in (Command.DISCONNECT, Command.POWER_OFF)
            and self.recording_state is not RecordingState.IDLE
        ):
            return False
        if command in (Command.PLAN_MOTION, Command.READ_MOTION_POSITION):
            return self.state in (
                WorkflowState.OFFLINE,
                WorkflowState.CONNECTED,
                WorkflowState.ROBOT_ENABLED,
                WorkflowState.TELEOP_RUNNING,
            )
        if command is Command.REFRESH_ROBOT_STATUS:
            return self.state is not WorkflowState.OFFLINE
        if command is Command.PREPARE_DEVICES:
            return self.state in (WorkflowState.CONNECTED, WorkflowState.ROBOT_ENABLED)
        if command is Command.START_CAMERAS:
            return self.state not in (
                WorkflowState.FAULT,
                WorkflowState.ESTOP,
                WorkflowState.RETURNING_HOME,
            )
        if command is Command.START_TRAJECTORY_RECORDING:
            return self.state in _ENABLED or self.state is WorkflowState.CONNECTED
        if command in (
            Command.STOP_POINT_MOTION,
            Command.STOP_TRAJECTORY_REPLAY,
            Command.STOP_DAGGER,
        ) and self.state in (WorkflowState.FAULT, WorkflowState.ESTOP):
            return True
        if command is Command.STOP_MOTION:
            return self.state is not WorkflowState.OFFLINE
        if command is Command.RETURN_HOME:
            return (
                self.state is WorkflowState.ROBOT_ENABLED
                and self.recording_state is RecordingState.IDLE
            )
        if command is Command.HOME_COMPLETED:
            return self.state is WorkflowState.RETURNING_HOME
        if command is Command.EMERGENCY_STOP:
            return self.state is not WorkflowState.ESTOP
        if command is Command.REPORT_FAULT:
            return self.state not in (WorkflowState.FAULT, WorkflowState.ESTOP)
        if command is Command.RESET_FAULT:
            return self.state is WorkflowState.FAULT
        if command is Command.RESET_ESTOP:
            return self.state is WorkflowState.ESTOP
        return (self.state, command) in _TRANSITIONS

    def apply(self, command, *, validated=False, source="teleop"):
        if not validated and not self.can(command, source=source):
            raise InvalidTransition(
                f"{command.name} is not allowed from {self.state.name} / "
                f"{self.recording_state.name}"
            )
        if command is Command.START_EPISODE:
            self.recording_state = RecordingState.RECORDING
        elif command is Command.STOP_EPISODE:
            self.recording_state = RecordingState.PENDING
        elif command in (
            Command.SAVE_SUCCESS,
            Command.SAVE_FAILURE,
            Command.FINISH_EPISODE,
            Command.DISCARD_EPISODE,
            Command.SUSPEND_BATCH,
            Command.DISCARD_BATCH,
        ):
            self.recording_state = RecordingState.IDLE
        elif command in (Command.REPORT_FAULT, Command.EMERGENCY_STOP):
            self.recovery_state = self._safe_recovery_state(self.state)
            self.state = (
                WorkflowState.FAULT if command is Command.REPORT_FAULT else WorkflowState.ESTOP
            )
        elif command in (Command.RESET_FAULT, Command.RESET_ESTOP):
            self.state = self.recovery_state
        elif command is Command.STOP_MOTION:
            if self.state in _ENABLED:
                self.state = WorkflowState.ROBOT_ENABLED
        elif command is Command.RETURN_HOME:
            self.state = WorkflowState.RETURNING_HOME
        elif command is Command.HOME_COMPLETED:
            self.state = self.recovery_state = WorkflowState.ROBOT_ENABLED
        else:
            self.state = _TRANSITIONS.get((self.state, command), self.state)
        return self.state

    @staticmethod
    def _safe_recovery_state(previous):
        if previous in _ENABLED:
            return WorkflowState.ROBOT_ENABLED
        if previous is WorkflowState.CONNECTED:
            return WorkflowState.CONNECTED
        return WorkflowState.OFFLINE
