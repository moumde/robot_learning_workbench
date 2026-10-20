import threading
from types import SimpleNamespace

from teleop.gello_cr.app import ApplicationService, build_application_view_model
from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
from teleop.gello_cr.core.state_machine import (
    Command,
    MotionState,
    RecordingState,
    WorkflowState,
    WorkflowStateMachine,
)


class Recorder:
    def __init__(self):
        self.active, self.frames = False, 0

    def snapshot(self):
        return {"episode_active": self.active, "buffered_frames": self.frames}

    def start_episode(self, *args, **kwargs):
        self.active, self.frames = True, 1

    def stop_episode(self):
        self.active = False

    def save_episode(self, *args):
        self.frames = 0


def test_replay_recording_uses_explicit_source_and_global_stop_keeps_pending_episode():
    recorder = Recorder()
    calls = []
    engine = SimpleNamespace(
        replay_trajectory=lambda *a, **k: calls.append("replay"),
        stop_motion=lambda reason: calls.append("stop"),
    )
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    RuntimeCommandBindings(
        service, teleop_engine=engine, recorder=recorder, recording_snapshot=recorder.snapshot
    ).install()
    service.dispatch(Command.REPLAY_TRAJECTORY, {"trajectory_id": "demo"})
    service.dispatch(Command.START_EPISODE, {
        "task": "pick", "base_root": "/tmp", "source": "replay",
    })
    vm = build_application_view_model(
        service.snapshot(), {"motion": {"source": "REPLAY"}}, recorder.snapshot()
    )
    assert vm.motion_state is MotionState.REPLAY
    assert vm.recording_state is RecordingState.RECORDING
    service.dispatch(Command.STOP_MOTION)
    assert not recorder.active
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert service.snapshot().recording_state is RecordingState.PENDING
    service.dispatch(Command.SAVE_SUCCESS)
    assert service.snapshot().recording_state is RecordingState.IDLE
    assert calls == ["replay", "stop"]


def test_global_stop_preempts_normal_worker_and_reasserts_against_late_start():
    started, finish = threading.Event(), threading.Event()
    stopped = []
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))

    def blocking(payload):
        started.set()
        assert finish.wait(2)

    service.set_handler(Command.PLAN_MOTION, blocking)
    service.set_handler(Command.STOP_MOTION, lambda p: stopped.append(True))
    errors = []

    def run():
        try:
            service.dispatch(Command.PLAN_MOTION)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    assert started.wait(1)
    service.dispatch(Command.STOP_MOTION)
    assert stopped == [True]
    finish.set()
    worker.join(2)
    assert len(stopped) == 2
    assert errors and type(errors[0]).__name__ == "CommandSuperseded"


def test_recorder_auto_stop_is_reflected_before_outcome_validation():
    recorder = Recorder()
    recorder.active, recorder.frames = True, 3
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.REPLAY_RUNNING))
    RuntimeCommandBindings(
        service,
        teleop_engine=SimpleNamespace(),
        recorder=recorder,
        recording_snapshot=recorder.snapshot,
    ).install()
    recorder.active = False
    service.dispatch(Command.SAVE_FAILURE)
    assert service.state is WorkflowState.REPLAY_RUNNING
    assert service.snapshot().recording_state is RecordingState.IDLE


def test_failed_global_stop_reports_fault_instead_of_ready():
    import pytest

    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.REPLAY_RUNNING))

    def failed(payload):
        raise OSError("controller stop failed")

    service.set_handler(Command.STOP_MOTION, failed)
    with pytest.raises(OSError):
        service.dispatch(Command.STOP_MOTION)
    assert service.state is WorkflowState.FAULT
