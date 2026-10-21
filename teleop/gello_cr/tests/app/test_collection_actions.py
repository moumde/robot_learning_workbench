"""Operator collection actions compose the existing motion and Episode lifecycle."""

import threading

import pytest

from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
from teleop.gello_cr.app.service import ApplicationService, CommandSuperseded
from teleop.gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    WorkflowStateMachine,
)
from teleop.gello_cr.ui.command_port import AsyncApplicationCommandPort, CommandRequest


class Recorder:
    def __init__(self, events):
        self.events = events
        self.active = False
        self.frames = 0
        self.error = ""
        self.start_error = self.save_error = None

    def snapshot(self):
        return {
            "episode_active": self.active,
            "episode_pending": not self.active and self.frames > 0,
            "buffered_frames": self.frames,
            "error": self.error,
        }

    def start_episode(self, task, root, *, metadata=None):
        if self.start_error:
            raise self.start_error
        self.events.append("record")
        self.active, self.frames = True, 3

    def stop_episode(self):
        self.events.append("stop_record")
        self.active = False

    def save_episode(self, outcome, notes=""):
        if self.save_error:
            raise self.save_error
        self.events.append("save_" + outcome)
        self.frames = 0
        return "receipt"


class Engine:
    def __init__(self, events, recorder):
        self.events, self.recorder = events, recorder
        self.state = "idle"
        self.home_entered, self.home_release = threading.Event(), threading.Event()
        self.home_release.set()
        self.home_error = self.stop_error = None
        self.stop_seen = threading.Event()

    def snapshot(self):
        return {"state": self.state, "servo_enabled": True}

    def start_follow(self):
        self.events.append("follow")
        self.state = "following"

    def stop_follow(self, reason):
        self.events.append("stop_follow")
        if self.stop_error:
            raise self.stop_error
        self.state = "idle"

    def return_home(self):
        assert self.recorder.active
        self.events.append("home")
        self.state = "preset"
        self.home_entered.set()
        assert self.home_release.wait(2)
        if self.home_error:
            raise self.home_error
        if self.state == "preset":
            self.recorder.frames += 2
            self.events.append("home_arrived")
            self.state = "idle"

    def emergency_stop(self, reason):
        self.events.append("emergency_stop")
        self.state = "fault"
        self.stop_seen.set()


@pytest.fixture
def setup():
    events = []
    recorder = Recorder(events)
    engine = Engine(events, recorder)
    ready = {
        "robot_connected": True,
        "servo_state": "on",
        "master_connected": True,
        "o6_connected": True,
        "camera_frames_ready": True,
        "camera_error": "",
    }
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    bindings = RuntimeCommandBindings(
        service, teleop_engine=engine, recorder=recorder, readiness_snapshot=lambda: ready
    ).install()
    yield service, engine, recorder, events, ready
    engine.home_release.set()
    bindings.close()


def start(service):
    return service.dispatch(
        Command.START_COLLECTION,
        {"task": "pick", "base_root": "/data/captures", "source": "teleop"},
    )


def test_start_collection_starts_follow_and_recording_with_one_intent(setup):
    service, engine, recorder, events, _ = setup
    start(service)
    assert events == ["follow", "record"]
    assert recorder.active and engine.state == "following"
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_failed_recording_start_stops_the_follow_it_started(setup):
    service, engine, recorder, events, _ = setup
    recorder.start_error = OSError("dataset not writable")
    with pytest.raises(OSError, match="not writable"):
        start(service)
    assert events == ["follow", "stop_follow"]
    assert engine.state == "idle" and not recorder.active
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_failed_recording_start_preserves_a_preexisting_manual_follow(setup):
    service, engine, recorder, events, _ = setup
    service.dispatch(Command.START_TELEOP)
    recorder.start_error = OSError("dataset not writable")
    with pytest.raises(OSError):
        start(service)
    assert events == ["follow"]
    assert engine.state == "following"


@pytest.mark.parametrize(
    "readiness",
    [{"camera_frames_ready": False}, {"servo_state": "off"}, {"master_connected": False}],
)
def test_unready_collection_never_starts_motion(setup, readiness):
    service, _, _, events, ready = setup
    ready.update(readiness)
    with pytest.raises(InvalidTransition):
        start(service)
    assert events == []


def test_home_and_save_waits_for_actual_arrival_while_episode_stays_open(setup):
    service, engine, recorder, events, _ = setup
    start(service)
    engine.home_release.clear()
    errors = []

    def finish():
        try:
            service.dispatch(Command.HOME_AND_SAVE_EPISODE)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=finish)
    worker.start()
    try:
        assert engine.home_entered.wait(1)
        assert recorder.active and recorder.frames == 3
        assert "save_success" not in events
        engine.home_release.set()
        worker.join(2)
        assert not worker.is_alive() and not errors
        assert events[-3:] == ["home_arrived", "stop_record", "save_success"]
        assert not recorder.active and recorder.frames == 0
        assert service.state is WorkflowState.ROBOT_ENABLED
        assert engine.state == "idle" and events.count("follow") == 1
    finally:
        engine.home_release.set()
        worker.join(2)


def test_home_failure_does_not_save_success(setup):
    service, engine, recorder, events, _ = setup
    start(service)
    engine.home_error = RuntimeError("target not reached")
    with pytest.raises(RuntimeError, match="target not reached"):
        service.dispatch(Command.HOME_AND_SAVE_EPISODE)
    assert recorder.frames == 3 and "save_success" not in events
    assert service.state is WorkflowState.FAULT


def test_estop_interrupts_home_and_save_without_waiting_for_home_worker(setup):
    service, engine, recorder, events, _ = setup
    start(service)
    engine.home_release.clear()
    errors = []
    port = AsyncApplicationCommandPort(
        service, error_callback=lambda request, error: errors.append(error)
    )
    try:
        port.submit(CommandRequest.create(Command.HOME_AND_SAVE_EPISODE))
        assert engine.home_entered.wait(1)
        port.submit(CommandRequest.create(Command.EMERGENCY_STOP))
        assert engine.stop_seen.wait(1)
        engine.home_release.set()
    finally:
        engine.home_release.set()
        port.close(timeout=3)
    assert service.state is WorkflowState.ESTOP
    assert "save_success" not in events and recorder.frames > 0
    assert any(isinstance(error, CommandSuperseded) for error in errors)


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_direct_finish_stops_follow_before_saving(setup, outcome):
    service, engine, recorder, events, _ = setup
    start(service)
    service.dispatch(Command.FINISH_COLLECTION, {"outcome": outcome})
    assert events[-3:] == ["stop_follow", "stop_record", "save_" + outcome]
    assert engine.state == "idle" and not recorder.active
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_save_failure_leaves_pending_frames_and_motion_stopped(setup):
    service, engine, recorder, _, _ = setup
    start(service)
    recorder.save_error = OSError("disk full")
    with pytest.raises(OSError, match="disk full"):
        service.dispatch(Command.HOME_AND_SAVE_EPISODE)
    assert not recorder.active and recorder.frames == 5
    assert engine.state == "idle" and service.state is WorkflowState.ROBOT_ENABLED
    recorder.save_error = None
    service.dispatch(Command.FINISH_COLLECTION, {"outcome": "success"})
    assert recorder.frames == 0


def test_stop_failure_latches_fault_and_never_saves_success(setup):
    service, engine, recorder, events, _ = setup
    start(service)
    engine.stop_error = RuntimeError("stop acknowledgement failed")
    with pytest.raises(RuntimeError, match="acknowledgement"):
        service.dispatch(Command.FINISH_COLLECTION, {"outcome": "success"})
    assert service.state is WorkflowState.FAULT
    assert recorder.frames > 0 and "save_success" not in events


def test_collection_waits_for_first_accepted_gello_action(tmp_path):
    from teleop.gello_cr.app.config_store import TeleopConfigStore
    from teleop.gello_cr.app.runtime import TeleopRuntime
    from teleop.gello_cr.tests.fakes.runtime import FakeGello, FakeO6, FakeRobot

    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    store.data["dataset"]["recording_mode"] = "joint"
    events = []
    engine = TeleopRuntime(store, FakeGello(), FakeO6())
    import time
    from dataclasses import replace

    engine.roarm.latest = lambda: replace(engine.roarm.value, timestamp=time.monotonic())
    engine.attach_robot(FakeRobot())
    recorder = Recorder(events)
    original_start = recorder.start_episode
    loop_entered, release_loop, recording_attempted = (threading.Event() for _ in range(3))
    original_loop = engine.teleop_controller._gello_follow_loop
    errors = []

    def delayed_loop(*args):
        loop_entered.set()
        assert release_loop.wait(2)
        original_loop(*args)

    def begin(*args, **kwargs):
        recording_attempted.set()
        # The real capture contract rejects an active owner with no sent target.
        engine.dataset_sample()
        return original_start(*args, **kwargs)

    engine.teleop_controller._gello_follow_loop = delayed_loop
    recorder.start_episode = begin
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    bindings = RuntimeCommandBindings(service, teleop_engine=engine, recorder=recorder).install()

    def collect():
        try:
            start(service)
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=collect)
    try:
        worker.start()
        assert loop_entered.wait(1)
        assert not recording_attempted.wait(0.05)
        release_loop.set()
        worker.join(2)
        assert not worker.is_alive() and not errors
        assert recorder.active
        assert engine.motion.status.last_command_at is not None
    finally:
        release_loop.set()
        worker.join(3)
        bindings.close()
        engine.shutdown()


def test_delayed_collection_stop_cannot_cancel_new_home(tmp_path):
    from teleop.gello_cr.app.config_store import TeleopConfigStore
    from teleop.gello_cr.app.runtime import TeleopRuntime
    from teleop.gello_cr.motion import MotionSource
    from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot

    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    engine = TeleopRuntime(store, FakeRoArm(), FakeO6())
    engine.attach_robot(FakeRobot())
    engine.save_home()
    recorder = Recorder([])
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    bindings = RuntimeCommandBindings(service, teleop_engine=engine, recorder=recorder).install()
    stop_entered, release_stop, home_entered, release_home = (threading.Event() for _ in range(4))
    original_stop = engine.stop_follow
    original_wait = engine.robot.wait_until_motion_stopped
    finish_errors, home_errors = [], []

    def delayed_stop(*args, **kwargs):
        stop_entered.set()
        assert release_stop.wait(2)
        return original_stop(*args, **kwargs)

    def delayed_home_wait(*args, **kwargs):
        if threading.current_thread().name == "Concurrent-Home":
            home_entered.set()
            assert release_home.wait(2)
            if engine.motion.current_owner is not MotionSource.HOME:
                return False
        return original_wait(*args, **kwargs)

    def call(command, errors, payload=None):
        try:
            service.dispatch(command, payload)
        except Exception as error:
            errors.append(error)

    finish = threading.Thread(
        target=call, args=(Command.FINISH_COLLECTION, finish_errors, {"outcome": "success"})
    )
    home = threading.Thread(
        target=call, args=(Command.RETURN_HOME, home_errors), name="Concurrent-Home"
    )
    try:
        start(service)
        engine.stop_follow = delayed_stop
        engine.robot.wait_until_motion_stopped = delayed_home_wait
        finish.start()
        assert stop_entered.wait(1)
        home.start()
        assert home_entered.wait(1)
        release_stop.set()
        finish.join(1)
        assert not finish.is_alive()
        assert engine.motion.current_owner is MotionSource.HOME
        release_home.set()
        home.join(2)
        assert not home.is_alive() and not home_errors
        assert any(isinstance(error, CommandSuperseded) for error in finish_errors)
        assert service.state is WorkflowState.ROBOT_ENABLED
        assert recorder.active and recorder.frames > 0
    finally:
        release_stop.set()
        release_home.set()
        if finish.ident:
            finish.join(3)
        if home.ident:
            home.join(3)
        bindings.close()
        engine.shutdown()
