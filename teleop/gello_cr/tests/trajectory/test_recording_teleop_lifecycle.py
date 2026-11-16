"""Trajectory capture owns its follow session, independently of dataset Episodes."""

import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.runtime import TeleopRuntime
from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.motion import MotionSource
from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


@pytest.fixture
def setup(tmp_path):
    store = TeleopConfigStore(tmp_path / "teleop.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    store.data["replay"]["sample_period_s"] = 0.005
    master, hand, robot = FakeRoArm(), FakeO6(), FakeRobot()
    master.latest = lambda: replace(master.value, timestamp=time.monotonic())
    engine = TeleopRuntime(store, master, hand)
    engine.attach_robot(robot)
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    episode_calls = []
    recorder = SimpleNamespace(snapshot=lambda: {}, stop_episode=lambda: episode_calls.append("stop"))
    bindings = RuntimeCommandBindings(service, teleop_engine=engine, recorder=recorder).install()
    yield engine, service, bindings, episode_calls
    engine.shutdown(close_devices=False)
    bindings.close()


def test_start_and_finish_trajectory_own_follow_without_dataset_episode(setup):
    engine, service, _, episode_calls = setup
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "coupled"})
    assert engine.state == "following"
    assert engine.recording
    assert service.state is WorkflowState.TELEOP_RUNNING
    assert engine.motion.current_owner is MotionSource.TELEOP

    path = service.dispatch(Command.STOP_TRAJECTORY_RECORDING).value
    assert path.is_dir()
    assert engine.state == "idle"
    assert not engine.recording
    assert engine.motion.current_owner is None
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert episode_calls == []


def test_save_failure_stops_follow_and_preserves_retryable_frames(setup):
    engine, service, _, _ = setup
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "disk full"})
    save = engine.trajectory_store.save
    engine.trajectory_store.save = lambda value: (_ for _ in ()).throw(OSError("disk full"))
    with pytest.raises(OSError, match="disk full"):
        service.dispatch(Command.STOP_TRAJECTORY_RECORDING)
    assert not engine.recording
    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert engine._pending_trajectory is not None
    assert engine.trajectory_recorder.frames
    engine.trajectory_store.save = save
    service.dispatch(Command.SAVE_TRAJECTORY)
    assert not engine.trajectory_recorder.frames
    assert engine.state == "idle"


def test_initial_sample_failure_rolls_back_follow(setup):
    engine, service, _, _ = setup
    engine.trajectory_source.sample = lambda: (_ for _ in ()).throw(RuntimeError("sample failed"))
    with pytest.raises(RuntimeError, match="sample failed"):
        service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "rollback"})
    assert not engine.recording
    assert engine.motion.current_owner is None
    assert engine.state != "following"
    assert not engine.trajectory_recorder.frames


def test_sample_failure_stops_follow_and_reports_fault(setup):
    engine, service, _, _ = setup
    sample = engine.trajectory_source.sample
    sampled = threading.Event()

    def fail_after_first():
        if sampled.is_set():
            raise RuntimeError("capture feedback lost")
        sampled.set()
        return sample()

    engine.trajectory_source.sample = fail_after_first
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "fault"})
    engine.trajectory_recorder.thread.join(2)
    assert not engine.recording
    assert engine.motion.current_owner is None
    assert engine.state == "fault"
    assert service.state is WorkflowState.FAULT
    assert engine.trajectory_recorder.frames


def test_old_recording_completion_cannot_stop_replacement_owner(setup):
    engine, service, _, _ = setup
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "takeover"})
    with engine._state_lock:
        engine._stop_generation += 1
        engine._state = "preset"
    replacement = engine.motion.acquire(MotionSource.HOME, allow_preempt=True)
    engine.trajectory_recorder.thread.join(2)
    assert not engine.recording
    assert replacement.active
    assert engine.state == "preset"
    replacement.release()


def test_cancel_trajectory_stops_follow_without_saving(setup):
    engine, service, _, _ = setup
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "cancel"})
    service.dispatch(Command.CANCEL_TRAJECTORY_RECORDING)
    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert not engine.trajectory_recorder.frames
    assert not engine.list_trajectories()
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_recording_duration_limit_stops_follow_and_saves(setup):
    engine, service, bindings, _ = setup
    engine.trajectory_recorder.max_duration_s = 0.02
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "duration"})
    engine.trajectory_recorder.thread.join(2)
    bindings._completion_jobs.close()
    assert not engine.recording
    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert len(engine.list_trajectories()) == 1


def test_stop_during_initial_sampling_cannot_restart_capture_or_follow(setup):
    engine, service, _, _ = setup
    sampled, release = threading.Event(), threading.Event()
    sample = engine.trajectory_source.sample
    errors = []

    def blocked_sample():
        sampled.set()
        assert release.wait(2)
        return sample()

    def start():
        try:
            service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "preempted"})
        except Exception as exc:
            errors.append(exc)

    engine.trajectory_source.sample = blocked_sample
    worker = threading.Thread(target=start)
    worker.start()
    try:
        assert sampled.wait(2)
        service.dispatch(Command.STOP_MOTION)
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    assert errors
    assert not engine.recording
    assert not engine.trajectory_recorder.frames
    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_sample_fault_cleanup_cannot_overwrite_concurrent_replay_takeover(setup):
    engine, service, _, _ = setup
    source = engine.trajectory_source.sample
    stopping, proceed = threading.Event(), threading.Event()
    finish_follow = engine.trajectory_service._stop_session_follow
    samples = 0

    def sample():
        nonlocal samples
        samples += 1
        if samples > 1:
            raise RuntimeError("sample fault during takeover")
        return source()

    def blocked_finish(session):
        stopping.set()
        assert proceed.wait(2)
        finish_follow(session)

    engine.trajectory_source.sample = sample
    engine.trajectory_service._stop_session_follow = blocked_finish
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "racing replay"})
    try:
        assert stopping.wait(2)
        with engine._state_lock:
            engine._state = "replay"
        replacement = engine.motion.acquire(MotionSource.REPLAY, allow_preempt=True)
    finally:
        proceed.set()
    engine.trajectory_recorder.thread.join(2)
    assert replacement.active
    assert engine.state == "replay"
    assert service.state is not WorkflowState.FAULT
    replacement.release()


def test_recorder_thread_start_failure_rolls_back_follow_and_buffer(setup, monkeypatch):
    engine, service, _, _ = setup
    start = threading.Thread.start

    def fail_recorder(thread):
        if thread.name == "Trajectory-Record":
            raise RuntimeError("recorder thread unavailable")
        return start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_recorder)
    with pytest.raises(RuntimeError, match="recorder thread unavailable"):
        service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "thread failure"})
    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert not engine.recording
    assert not engine.trajectory_recorder.frames


@pytest.mark.parametrize("command", [Command.STOP_TRAJECTORY_RECORDING, Command.CANCEL_TRAJECTORY_RECORDING])
def test_explicit_recording_stop_failure_latches_fault_and_keeps_frames(setup, command):
    engine, service, _, _ = setup
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "stop fault"})
    session = engine.trajectory_service._recording_session

    def failed_stop():
        session.lease.release()
        raise OSError("stop confirmation failed")

    session.lease.stop = failed_stop
    with pytest.raises(OSError, match="stop confirmation failed"):
        service.dispatch(command)
    assert not session.thread.is_alive()
    assert engine.motion.current_owner is None
    assert engine.state == "fault"
    assert service.state is WorkflowState.FAULT
    assert engine.trajectory_recorder.frames
    assert engine._pending_trajectory is not None
    assert "stop confirmation failed" in engine.last_error
    assert not service.can(Command.RETURN_HOME)


def test_recording_stop_failure_cannot_fault_new_home_owner(setup):
    engine, service, _, _ = setup
    service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "home wins stop failure"})
    session = engine.trajectory_service._recording_session
    replacement = []

    def failed_old_stop():
        session.lease.release()
        with engine._state_lock:
            engine._stop_generation += 1
            engine._state = "preset"
        replacement.append(engine.motion.acquire(MotionSource.HOME))
        raise OSError("old stop failed")

    session.lease.stop = failed_old_stop
    with pytest.raises(OSError, match="old stop failed"):
        service.dispatch(Command.STOP_TRAJECTORY_RECORDING)
    assert not session.thread.is_alive()
    assert engine.state == "preset"
    assert replacement[0].active
    assert service.state is not WorkflowState.FAULT
    replacement[0].release()


@pytest.mark.parametrize("source", [MotionSource.REPLAY, MotionSource.POINT_MOVE])
def test_home_finishing_at_start_reservation_preserves_accepted_target(setup, source):
    from teleop.gello_cr.motion import MotionPreempted
    from teleop.gello_cr.trajectory import ReplayOptions, TrajectoryFrame, make_trajectory

    engine, _, _, _ = setup
    engine.store.data["presets"]["HOME"] = {"robot_joints_deg": [0.0] * 7}
    if source is MotionSource.REPLAY:
        value = make_trajectory("late replay", [TrajectoryFrame(0.0, robot_joint_command=(0.0,) * 6)])
        engine.trajectory_store.save(value)

        def start():
            engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions(hand_enabled=False))
    else:
        result = engine.point_motion.plan({"kind": "joint", "target": [0.0001] * 6})
        assert result.success

        def start():
            engine.point_motion.execute(result.trajectory.metadata.trajectory_id)

    entered, release = threading.Event(), threading.Event()
    home_started, home_finished = threading.Event(), threading.Event()
    acquire = engine.motion.acquire
    failures, accepted = [], []

    def delayed_acquire(owner, *args, **kwargs):
        if owner is source:
            entered.set()
            assert release.wait(2)
        return acquire(owner, *args, **kwargs)

    def run_start():
        try:
            start()
        except MotionPreempted:
            pass
        except Exception as exc:
            failures.append(exc)

    def run_home():
        home_started.set()
        try:
            engine.return_home()
            accepted.append(engine.motion.last_joint_target)
        except Exception as exc:
            failures.append(exc)
        finally:
            home_finished.set()

    engine.motion.acquire = delayed_acquire
    worker, home = threading.Thread(target=run_start), threading.Thread(target=run_home)
    try:
        worker.start()
        assert entered.wait(1)
        home.start()
        assert home_started.wait(1)
        # The startup reservation and HOME cannot pass each other. HOME takes
        # over once the existing atomic reservation leaves the shared lock.
        assert not home_finished.wait(0.1)
        release.set()
        worker.join(2)
        home.join(2)
        assert not worker.is_alive() and not home.is_alive()
        assert not failures
        assert accepted and accepted[0] is not None
        assert engine.motion.last_joint_target is accepted[0]
        assert engine.state == "idle"
        assert engine.motion.current_owner is None
    finally:
        release.set()
        if worker.ident is not None:
            worker.join(2)
        if home.ident is not None:
            home.join(2)
