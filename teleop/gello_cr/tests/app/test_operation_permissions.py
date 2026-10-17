"""Application commands and presenter must agree on safety and Episode ownership."""

import pytest

from gello_cr.app.config_store import TeleopConfigStore
from gello_cr.app.runtime import TeleopRuntime
from gello_cr.app.runtime_bindings import RuntimeCommandBindings
from gello_cr.app.service import ApplicationService
from gello_cr.app.view_model import build_application_view_model
from gello_cr.bootstrap.runtime_factory import Cr3aLifecycle, RuntimeFactoryPaths
from gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    WorkflowStateMachine,
)
from gello_cr.ui.backend import OperatorBackend
from tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


class Session(FakeRobot):
    def __init__(self):
        super().__init__()
        self.enabled = False

    def servo_state(self):
        return 3 if self.enabled else 1

    def power_on(self):
        self.enabled = True

    def power_off(self):
        self.enabled = False


class Device:
    def __init__(self, _config, **_kwargs):
        self.session = Session()
        self.connected = False

    def connect(self, **_kwargs):
        self.connected = True

    def close(self):
        self.connected = False


class Recorder:
    def __init__(self):
        self.value = {"episode_active": False, "episode_pending": False, "buffered_frames": 0}

    def snapshot(self):
        return dict(self.value)


@pytest.fixture
def application(tmp_path):
    store = TeleopConfigStore(tmp_path / "teleop.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    engine = TeleopRuntime(store, FakeRoArm(), FakeO6())
    lifecycle = Cr3aLifecycle(
        store=store,
        teleop_engine=engine,
        device_constructor=Device,
        paths=RuntimeFactoryPaths(tmp_path, store.path, tmp_path / "hand", None),
    )
    recorder = Recorder()
    backend = OperatorBackend.compose(
        teleop_engine=engine, recorder=recorder, lifecycle=lifecycle.callbacks()
    )
    yield backend, lifecycle
    backend.close()
    lifecycle.disconnect()
    engine.shutdown()


def test_expected_power_off_disconnect_and_reconnect_survive_presenter_poll(application):
    backend, lifecycle = application
    service = backend.service
    for command, expected in (
        (Command.CONNECT, WorkflowState.CONNECTED),
        (Command.POWER_ON, WorkflowState.ROBOT_ENABLED),
        (Command.POWER_OFF, WorkflowState.CONNECTED),
        (Command.DISCONNECT, WorkflowState.OFFLINE),
        (Command.CONNECT, WorkflowState.CONNECTED),
        (Command.POWER_ON, WorkflowState.ROBOT_ENABLED),
    ):
        service.dispatch(command)
        frame = backend.presenter.poll()
        assert service.state is expected
        assert frame.view_model.workflow_state is expected
        assert frame.view_model.runtime_error == ""
    assert lifecycle.session.enabled


def test_unexpected_disconnect_remains_fault_after_poll(application):
    backend, lifecycle = application
    backend.service.dispatch(Command.CONNECT)
    backend.teleop_engine.detach_robot(lifecycle.session, "connection lost")
    assert backend.presenter.poll().view_model.workflow_state is WorkflowState.FAULT


def test_feedback_detects_unexpected_disconnect_and_keeps_fault(application):
    import time

    backend, lifecycle = application
    backend.service.dispatch(Command.CONNECT)
    lifecycle.device.connected = False
    deadline = time.monotonic() + 1
    while backend.teleop_engine.state != "fault" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert backend.teleop_engine.state == "fault"
    assert not lifecycle.status_snapshot()["connected"]
    assert backend.presenter.poll().view_model.workflow_state is WorkflowState.FAULT


def test_disconnect_keeps_devices_open_when_motion_cannot_drain(application):
    import time

    backend, lifecycle = application
    backend.service.dispatch(Command.CONNECT)
    session = lifecycle.session
    device = lifecycle.device
    feedback = lifecycle._feedback_thread
    original = backend.teleop_engine.stop_motion

    def blocked_stop(_reason):
        raise TimeoutError("motion producer still running")

    backend.teleop_engine.stop_motion = blocked_stop
    try:
        for _ in range(2):
            with pytest.raises(ExceptionGroup) as failure:
                backend.service.dispatch(Command.DISCONNECT)
            assert isinstance(failure.value.exceptions[0], TimeoutError)
            assert lifecycle.device is device and device.connected
            assert lifecycle.session is session
            assert backend.teleop_engine.robot is session
            assert backend.teleop_engine.state == "fault"
            assert not feedback.is_alive()
            replacement = lifecycle._feedback_thread
            assert replacement is not feedback and replacement.is_alive()
            feedback = replacement
    finally:
        backend.teleop_engine.stop_motion = original
    backend.presenter.poll()
    backend.service.dispatch(Command.RESET_FAULT)
    sampled_at = lifecycle.status_snapshot()["sampled_at"]
    deadline = time.monotonic() + 1
    while lifecycle.status_snapshot()["sampled_at"] <= sampled_at and time.monotonic() < deadline:
        time.sleep(0.01)
    assert lifecycle.status_snapshot()["sampled_at"] > sampled_at
    assert lifecycle._feedback_thread is feedback and feedback.is_alive()
    assert not session.enabled
    assert session.movej_targets == []
    lifecycle.disconnect()
    assert not feedback.is_alive()


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.CONNECTED,
        WorkflowState.TELEOP_RUNNING,
        WorkflowState.FAULT,
        WorkflowState.ESTOP,
    ],
)
def test_home_cannot_bypass_enable_motion_or_safety_state(state):
    service = ApplicationService(state_machine=WorkflowStateMachine(state))
    moves = []
    service.set_handler(Command.RETURN_HOME, lambda p: moves.append(True))
    assert not service.can(Command.RETURN_HOME)
    with pytest.raises(InvalidTransition):
        service.dispatch(Command.RETURN_HOME)
    assert not moves


@pytest.mark.parametrize(
    "frames,error,success,failure",
    [
        (0, "", False, False),
        (4, "camera unavailable", False, True),
        (4, "", True, True),
    ],
)
def test_pending_save_and_replay_permission_is_shared(frames, error, success, failure):
    episode = {
        "episode_active": False,
        "episode_pending": True,
        "buffered_frames": frames,
        "error": error,
    }
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    service.set_recording_snapshot(lambda: episode)
    calls = []
    service.set_handler(Command.REPLAY_TRAJECTORY, lambda p: calls.append("replay"))
    vm = build_application_view_model(service.snapshot(), {}, episode)
    for command, expected in (
        (Command.REPLAY_TRAJECTORY, False),
        (Command.SAVE_SUCCESS, success),
        (Command.SAVE_FAILURE, failure),
    ):
        assert service.can(command) is expected
        assert vm.actions[command] is expected
    with pytest.raises(InvalidTransition):
        service.dispatch(Command.REPLAY_TRAJECTORY, {"trajectory_id": "example"})
    assert calls == []


def test_home_runtime_rejects_recording_without_altering_it(application):
    backend, _ = application
    backend.service.dispatch(Command.CONNECT)
    backend.service.dispatch(Command.POWER_ON)
    backend.teleop_engine.save_home()
    backend.recorder.value.update(episode_active=True)
    with pytest.raises(RuntimeError, match="Episode|录制"):
        backend.teleop_engine.return_home()
    assert backend.recorder.value["episode_active"]
    assert backend.teleop_engine.robot.movej_targets == []


def test_home_runtime_requires_explicit_enable_and_does_not_enable_implicitly(application):
    backend, _ = application
    backend.service.dispatch(Command.CONNECT)
    backend.teleop_engine.save_home()
    with pytest.raises(RuntimeError, match="使能"):
        backend.teleop_engine.return_home()
    assert not backend.teleop_engine.robot.enabled
    assert backend.teleop_engine.state == "idle"


@pytest.mark.parametrize(
    "state,source,allowed",
    [
        (WorkflowState.ROBOT_ENABLED, "teleop", False),
        (WorkflowState.TELEOP_RUNNING, "teleop", True),
        (WorkflowState.REPLAY_RUNNING, "teleop", False),
        (WorkflowState.REPLAY_RUNNING, "replay", True),
        (WorkflowState.POINT_MOVE_RUNNING, "point_move", True),
        (WorkflowState.POINT_MOVE_RUNNING, "replay", False),
        (WorkflowState.RETURNING_HOME, "home", False),
    ],
)
def test_recording_requires_explicit_matching_source(state, source, allowed):
    service = ApplicationService(state_machine=WorkflowStateMachine(state))
    calls = []
    service.set_handler(Command.START_EPISODE, lambda payload: calls.append(payload["source"]))
    if allowed:
        service.dispatch(Command.START_EPISODE, {"source": source})
        assert calls == [source]
    else:
        with pytest.raises(InvalidTransition):
            service.dispatch(Command.START_EPISODE, {"source": source})
        assert not calls


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_finish_episode_stops_and_saves_on_one_command(outcome):
    episode = {"episode_active": True, "episode_pending": False, "buffered_frames": 3}
    calls = []

    class Recording:
        def snapshot(self):
            return dict(episode)

        def stop_episode(self):
            calls.append("stop")
            episode.update(episode_active=False, episode_pending=True)

        def save_episode(self, outcome, notes):
            calls.append((outcome, notes))
            episode.update(episode_pending=False, buffered_frames=0)

    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    RuntimeCommandBindings(
        service, teleop_engine=None, recorder=Recording(), recording_snapshot=lambda: episode
    ).install()
    service.dispatch(Command.FINISH_EPISODE, {"outcome": outcome, "notes": "reviewed"})
    assert calls == ["stop", (outcome, "reviewed")]
    assert not episode["episode_pending"]
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_finish_episode_invalid_result_does_not_stop_sampling():
    episode = {"episode_active": True, "episode_pending": False, "buffered_frames": 3}
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    calls = []
    service.set_recording_snapshot(lambda: episode)
    service.set_handler(Command.FINISH_EPISODE, lambda p: calls.append("stop"))
    with pytest.raises((InvalidTransition, ValueError), match="结果|outcome"):
        service.dispatch(Command.FINISH_EPISODE, {"outcome": ""})
    assert not calls
    assert episode["episode_active"]


def test_finish_write_failure_keeps_episode_pending():
    episode = {"episode_active": True, "episode_pending": False, "buffered_frames": 3}

    class Recording:
        def snapshot(self):
            return dict(episode)

        def stop_episode(self):
            episode.update(episode_active=False, episode_pending=True)

        def save_episode(self, outcome, notes):
            raise OSError("disk full")

    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    RuntimeCommandBindings(service, teleop_engine=None, recorder=Recording()).install()
    with pytest.raises(OSError, match="disk full"):
        service.dispatch(Command.FINISH_EPISODE, {"outcome": "failure"})
    assert service.snapshot().recording_state.name == "PENDING"
    assert episode["episode_pending"]
    assert episode["buffered_frames"] == 3


@pytest.mark.parametrize("active", [True, False], ids=["finish", "pending-save"])
def test_runtime_fault_blocks_success_before_presenter_synchronizes_workflow(active):
    episode = {"episode_active": active, "episode_pending": not active, "buffered_frames": 4}
    runtime = {"state": "fault", "last_fault": "robot disconnected"}
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    service.set_recording_snapshot(lambda: episode)
    service.set_permission_sources(runtime_snapshot=lambda: runtime)
    calls = []
    command = Command.FINISH_EPISODE if active else Command.SAVE_SUCCESS
    payload = {"outcome": "success"} if active else {}
    service.set_handler(command, lambda p: calls.append(p))

    view = build_application_view_model(service.snapshot(), runtime, episode)
    assert not view.actions[Command.SAVE_SUCCESS]
    assert view.actions[Command.SAVE_FAILURE]
    with pytest.raises(InvalidTransition):
        service.dispatch(command, payload)
    assert calls == []
    assert episode["buffered_frames"] == 4


@pytest.mark.parametrize(
    "servo,master,hand,hand_required,allowed",
    [
        (None, None, None, True, True),
        ("unknown", True, True, True, False),
        ("on", False, True, True, False),
        ("on", True, False, True, False),
        ("on", True, False, False, True),
    ],
)
def test_readiness_optional_feedback_and_hand_requirement_match_policy(
    servo,
    master,
    hand,
    hand_required,
    allowed,
):
    ready = {
        "robot_connected": True,
        "servo_state": servo,
        "master_connected": True,
        "o6_connected": True,
        "master_ready": master,
        "hand_ready": hand,
        "hand_required": hand_required,
    }
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    service.set_permission_sources(readiness_snapshot=lambda: ready)
    vm = build_application_view_model(service.snapshot(), {}, {}, ready)
    assert service.can(Command.START_TELEOP) is allowed
    assert vm.actions[Command.START_TELEOP] is allowed


@pytest.mark.parametrize(
    "state,source,servo,connected,master,hand,allowed",
    [
        (WorkflowState.TELEOP_RUNNING, "teleop", "off", True, True, True, False),
        (WorkflowState.TELEOP_RUNNING, "teleop", "unknown", True, True, True, False),
        (WorkflowState.TELEOP_RUNNING, "teleop", "error", True, True, True, False),
        (WorkflowState.TELEOP_RUNNING, "teleop", "on", False, True, True, False),
        (WorkflowState.TELEOP_RUNNING, "teleop", "on", True, False, True, False),
        (WorkflowState.TELEOP_RUNNING, "teleop", "on", True, True, False, False),
        (WorkflowState.TELEOP_RUNNING, "teleop", "on", True, True, True, True),
        (WorkflowState.TELEOP_RUNNING, "teleop", None, True, None, None, True),
        (WorkflowState.REPLAY_RUNNING, "replay", "on", True, False, False, True),
        (WorkflowState.REPLAY_RUNNING, "replay", "unknown", True, False, False, False),
        (WorkflowState.POINT_MOVE_RUNNING, "point_move", "on", True, False, False, True),
        (WorkflowState.POINT_MOVE_RUNNING, "point_move", "off", True, False, False, False),
    ],
)
def test_recording_rechecks_live_source_readiness(
    state,
    source,
    servo,
    connected,
    master,
    hand,
    allowed,
):
    ready = {
        "robot_connected": connected,
        "servo_state": servo,
        "master_connected": True,
        "o6_connected": True,
        "master_ready": master,
        "hand_ready": hand,
        "camera_frames_ready": True,
        "camera_error": "",
    }
    service = ApplicationService(state_machine=WorkflowStateMachine(state))
    service.set_permission_sources(readiness_snapshot=lambda: ready)
    vm = build_application_view_model(service.snapshot(), {}, {}, ready)
    assert service.can(Command.START_EPISODE, {"source": source}) is allowed
    assert vm.recording_sources[source] is allowed
