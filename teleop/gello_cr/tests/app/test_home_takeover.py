"""HOME takes motion ownership while an existing Episode keeps sampling."""

import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.permissions import OperationContext, operation_permission
from teleop.gello_cr.app.runtime import TeleopRuntime
from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
from teleop.gello_cr.app.service import ApplicationService, CommandSuperseded
from teleop.gello_cr.app.view_model import build_application_view_model
from teleop.gello_cr.core.state_machine import (
    Command,
    RecordingState,
    WorkflowState,
    WorkflowStateMachine,
)
from teleop.gello_cr.motion import JointTarget, MotionSource
from teleop.gello_cr.recording.session import RecordingSession
from teleop.gello_cr.recording.source import CR3O6CaptureSource
from teleop.gello_cr.tests.fakes.runtime import FakeGello, FakeO6, FakeRoArm, FakeRobot
from teleop.gello_cr.tests.recording.test_session import Writer


@pytest.fixture
def runtime(tmp_path):
    store = TeleopConfigStore(tmp_path / "workbench.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    engine = TeleopRuntime(store, FakeRoArm(), FakeO6())
    engine.attach_robot(FakeRobot())
    engine.save_home()
    yield engine
    engine.shutdown()


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.TELEOP_RUNNING,
        WorkflowState.REPLAY_RUNNING,
        WorkflowState.POINT_MOVE_RUNNING,
        WorkflowState.DAGGER_RUNNING,
    ],
)
@pytest.mark.parametrize("recording", [RecordingState.RECORDING, RecordingState.PENDING])
def test_home_preempts_normal_motion_without_changing_episode_state(state, recording):
    machine = WorkflowStateMachine(state, recording_state=recording)
    permission = operation_permission(
        Command.RETURN_HOME,
        OperationContext(
            state,
            recording,
            runtime={
                "state": "following",
                "motion": {
                    "source": "TELEOP",
                    "running": True,
                },
            },
        ),
    )
    assert permission.allowed, permission.reason
    assert machine.apply(Command.RETURN_HOME) is WorkflowState.RETURNING_HOME
    assert machine.recording_state is recording
    assert machine.apply(Command.HOME_COMPLETED) is WorkflowState.ROBOT_ENABLED
    assert machine.recording_state is recording
    assert not machine.can(Command.STOP_TELEOP)
    assert machine.can(Command.START_TELEOP)


@pytest.mark.parametrize("mode", ["joint", "tcp"])
def test_home_handoff_and_accepted_target_remain_in_one_episode(runtime, tmp_path, mode):
    runtime.store.data["dataset"]["recording_mode"] = mode
    runtime.store.data["dataset"]["camera_max_age_s"] = 10.0
    old = runtime.motion.acquire(MotionSource.TELEOP)
    old.servo_joint(JointTarget((0.1,) * 6, time.monotonic()))
    runtime._set_state("following")
    runtime._set_dataset_target_tcp([999.0] * 7)  # A prior TCP cache cannot become HOME's action.
    source = CR3O6CaptureSource(runtime.dataset_sample, runtime.store.data["dataset"])
    for index in range(3):
        source.update_stream(index, np.zeros((2, 2, 3), dtype=np.uint8), time.monotonic())
    writer = Writer()
    transition_frame = threading.Event()
    home_frame = threading.Event()
    restart_frame = threading.Event()
    teleop_frame = threading.Event()
    original_add = writer.add_frame

    def add_frame(frame):
        original_add(frame)
        if frame.metadata.get("home_transition"):
            transition_frame.set()
            if frame.metadata.get("motion_source") == "HOME":
                restart_frame.set()
        elif frame.metadata.get("motion_source") == "TELEOP" and restart_frame.is_set():
            teleop_frame.set()
        if frame.metadata.get("motion_source") == "HOME" and not frame.metadata.get(
            "home_transition"
        ):
            home_frame.set()

    writer.add_frame = add_frame
    session = RecordingSession(
        source, lambda: writer, event_callback=lambda *args: None, fps=100, image_size=(2, 2)
    )
    runtime.set_recording_snapshot(session.snapshot)
    entered = threading.Event()
    release = threading.Event()
    arrived = threading.Event()
    release_arrival = threading.Event()
    restart_entered = threading.Event()
    release_restart = threading.Event()
    errors = []
    original_wait = runtime.robot.wait_until_motion_stopped
    original_joints = runtime.robot.joint_position

    def wait_stopped(*args, **kwargs):
        if threading.current_thread().name == "Home-Test" and not runtime.robot.movej_targets:
            entered.set()
            assert release.wait(2)
        return original_wait(*args, **kwargs)

    def joints():
        if threading.current_thread().name == "Home-Test" and runtime.robot.movej_targets:
            arrived.set()
            assert release_arrival.wait(2)
        return original_joints()

    runtime.robot.wait_until_motion_stopped = wait_stopped
    runtime.robot.joint_position = joints

    def home():
        try:
            runtime.return_home()
        except Exception as exc:
            errors.append(exc)
            entered.set()

    thread = threading.Thread(target=home, name="Home-Test")
    restart_thread = None
    try:
        session.start_episode("continuous HOME", tmp_path)
        assert writer.frame_added.wait(1)
        sampling_thread = session._episode_thread
        generation = runtime.stop_generation
        thread.start()
        assert entered.wait(1)
        assert not errors
        assert transition_frame.wait(1)
        assert not old.active
        assert runtime.stop_generation > generation
        transition = next(
            call[1]
            for call in writer.calls
            if call[0] == "add" and call[1].metadata.get("home_transition")
        )
        assert transition.metadata["motion_source"] == "TELEOP"
        assert transition.robot_joint_command == pytest.approx((0.1,) * 6)
        release.set()
        assert arrived.wait(1)
        assert home_frame.wait(1)
        accepted = next(
            call[1]
            for call in writer.calls
            if call[0] == "add" and call[1].metadata.get("motion_source") == "HOME"
        )
        assert accepted.robot_joint_command == pytest.approx((0.0,) * 6)
        if mode == "joint":
            assert accepted.action[:6] == pytest.approx((0.0,) * 6)
        else:
            assert accepted.robot_tcp_command == pytest.approx((0.5, 0.01, 0.3, 1.1, 2.2, 3.3))
        release_arrival.set()
        thread.join(1)
        assert not thread.is_alive()
        assert not errors
        before = session.snapshot()["buffered_frames"]
        writer.frame_added.clear()
        assert writer.frame_added.wait(1)
        assert session._episode_thread is sampling_thread
        assert session.snapshot()["episode_active"]
        assert session.snapshot()["buffered_frames"] > before
        assert not session.snapshot()["error"]
        assert [call[0] for call in writer.calls].count("begin") == 1
        assert runtime.state == "idle"
        assert runtime.motion.current_owner is None
        assert runtime._follow_stop.is_set()
        assert len(runtime.robot.movej_targets) == 1
        # An explicit restart keeps the same Episode live even while the new
        # servo channel is opening and no TELEOP command has been accepted.
        runtime.roarm.connected = False
        runtime.set_master(FakeGello())
        runtime.store.data["gello"]["startup_settle_s"] = 0.0
        original_open = runtime.robot.open_servoj

        def open_servo(*args):
            restart_entered.set()
            assert release_restart.wait(2)
            original_open(*args)

        runtime.robot.open_servoj = open_servo

        def restart():
            try:
                runtime.start_follow()
            except Exception as exc:
                errors.append(exc)

        restart_thread = threading.Thread(target=restart, name="Restart-Test")
        restart_thread.start()
        assert restart_entered.wait(1)
        assert restart_frame.wait(1)
        assert session._episode_thread is sampling_thread
        assert session.snapshot()["episode_active"]
        release_restart.set()
        restart_thread.join(1)
        assert not restart_thread.is_alive()
        assert not errors
        assert teleop_frame.wait(1)
        assert session.snapshot()["episode_active"]
        assert not session.snapshot()["error"]
        assert [call[0] for call in writer.calls].count("begin") == 1
        runtime.stop_follow("test completed")
    finally:
        release.set()
        release_arrival.set()
        release_restart.set()
        thread.join(2)
        if restart_thread is not None:
            restart_thread.join(2)
        session.discard_episode()
        session.finalize()


def test_home_stop_during_o6_profile_never_enqueues_home_hand_target(runtime):
    runtime.o6.set_target([200] * 6)
    original = runtime.o6.set_profile

    def stop_during_profile(*args):
        original(*args)
        runtime.emergency_stop("stop during HOME hand preparation")

    runtime.o6.set_profile = stop_during_profile
    with pytest.raises(RuntimeError, match="停止"):
        runtime.return_home()
    assert runtime.state == "fault"
    assert runtime.o6.targets[-1] == (200,) * 6
    assert runtime.robot.movej_targets == []


def test_delayed_teleop_start_cannot_resume_after_home_finishes(runtime):
    entered = threading.Event()
    release = threading.Event()
    errors = []
    original = runtime.roarm.latest

    def latest():
        if threading.current_thread().name == "Late-Teleop":
            entered.set()
            assert release.wait(2)
        return original()

    runtime.roarm.latest = latest

    def start():
        try:
            runtime.start_follow()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=start, name="Late-Teleop")
    try:
        thread.start()
        assert entered.wait(1)
        runtime.return_home()
        release.set()
        thread.join(1)
        assert not thread.is_alive()
        assert errors
        assert runtime.state == "idle"
        assert runtime.motion.current_owner is None
        assert not runtime.robot.servoj_targets
        assert len(runtime.robot.movej_targets) == 1
    finally:
        release.set()
        thread.join(2)


def test_home_and_explicit_restart_are_available_in_recording_view_model():
    service = ApplicationService(
        state_machine=WorkflowStateMachine(
            WorkflowState.TELEOP_RUNNING, recording_state=RecordingState.RECORDING
        ),
        handlers={Command.RETURN_HOME: lambda payload: None},
    )
    recorder = {"episode_active": True, "buffered_frames": 5}
    ready = {
        "robot_connected": True,
        "servo_state": "on",
        "master_connected": True,
        "o6_connected": True,
    }
    view = build_application_view_model(service.snapshot(), {"state": "following"}, recorder, ready)
    assert view.actions[Command.RETURN_HOME]
    service.dispatch(Command.RETURN_HOME)
    view = build_application_view_model(service.snapshot(), {"state": "idle"}, recorder, ready)
    assert view.episode_active
    assert view.actions[Command.START_TELEOP]
    assert view.workflow_state is WorkflowState.ROBOT_ENABLED


def test_stale_gello_start_does_not_erase_accepted_home_target(runtime):
    runtime.roarm.connected = False
    runtime.set_master(FakeGello())
    entered = threading.Event()
    release = threading.Event()
    errors = []
    original = runtime.robot.joint_position

    def joints():
        if threading.current_thread().name == "Late-Gello":
            entered.set()
            assert release.wait(2)
        return original()

    runtime.robot.joint_position = joints

    def start():
        try:
            runtime.start_follow()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=start, name="Late-Gello")
    try:
        thread.start()
        assert entered.wait(1)
        runtime.return_home()
        accepted_home = runtime.motion.last_joint_target
        release.set()
        thread.join(1)
        assert not thread.is_alive()
        assert errors
        assert runtime.motion.last_joint_target is accepted_home
        assert runtime.state == "idle"
        assert not runtime.robot.servoj_targets
    finally:
        release.set()
        thread.join(2)


def test_home_does_not_reassert_a_historical_stop_into_the_active_episode(runtime):
    active = {"episode_active": False}
    stopped = []

    def stop_episode():
        active["episode_active"] = False
        stopped.append(True)

    recorder = SimpleNamespace(snapshot=lambda: dict(active), stop_episode=stop_episode)
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    bindings = RuntimeCommandBindings(service, teleop_engine=runtime, recorder=recorder).install()
    entered, release = threading.Event(), threading.Event()
    failures = []

    def refresh(_payload):
        entered.set()
        assert release.wait(2)

    def run_refresh():
        try:
            service.dispatch(Command.REFRESH_ROBOT_STATUS)
        except CommandSuperseded:
            pass
        except Exception as exc:
            failures.append(exc)

    service.set_handler(Command.REFRESH_ROBOT_STATUS, refresh)
    thread = threading.Thread(target=run_refresh)
    try:
        service.dispatch(Command.STOP_MOTION)
        service.dispatch(Command.START_TELEOP)
        active["episode_active"] = True
        thread.start()
        assert entered.wait(1)
        service.dispatch(Command.RETURN_HOME)
        assert active["episode_active"]
        release.set()
        thread.join(1)
        assert not thread.is_alive()
        assert not failures
        assert active["episode_active"]
        assert stopped == []
        assert service.state is WorkflowState.ROBOT_ENABLED
    finally:
        release.set()
        if thread.ident is not None:
            thread.join(2)
        bindings.close()


@pytest.mark.parametrize("command", [Command.STOP_TRAJECTORY_RECORDING, Command.CANCEL_TRAJECTORY_RECORDING])
def test_resolving_pre_home_trajectory_preserves_explicitly_restarted_follow(runtime, command):
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    bindings = RuntimeCommandBindings(
        service, teleop_engine=runtime, recorder=SimpleNamespace(snapshot=lambda: {})
    ).install()
    try:
        service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "before home"})
        service.dispatch(Command.RETURN_HOME)
        runtime.trajectory_recorder.thread.join(1)
        service.dispatch(Command.START_TELEOP)
        lease = runtime._follow_lease
        service.dispatch(command)
        assert lease.active
        assert runtime.state == "following"
        assert service.state is WorkflowState.TELEOP_RUNNING
        assert service.can(Command.STOP_TELEOP)
    finally:
        bindings.close()


def test_old_trajectory_save_failure_does_not_hide_a_new_follow_session(runtime):
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    bindings = RuntimeCommandBindings(
        service, teleop_engine=runtime, recorder=SimpleNamespace(snapshot=lambda: {})
    ).install()
    try:
        service.dispatch(Command.START_TRAJECTORY_RECORDING, {"name": "before home"})
        service.dispatch(Command.RETURN_HOME)
        runtime.trajectory_recorder.thread.join(1)
        service.dispatch(Command.START_TELEOP)
        runtime.trajectory_store.save = lambda _: (_ for _ in ()).throw(OSError("disk full"))
        with pytest.raises(OSError, match="disk full"):
            service.dispatch(Command.STOP_TRAJECTORY_RECORDING)
        assert runtime.state == "following"
        assert service.state is WorkflowState.TELEOP_RUNNING
        assert service.can(Command.STOP_TELEOP)
    finally:
        bindings.close()
