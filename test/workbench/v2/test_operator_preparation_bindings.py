
from __future__ import annotations

import pytest

from core.workbench.app import ApplicationService
from core.workbench.bootstrap.preparation import (
    OperatorPreparationBindings,
    OperatorReadinessProvider,
)
from core.workbench.core.state_machine import (
    Command,
    WorkflowState,
    WorkflowStateMachine,
)


class Master:
    master_type = "gello"

    def __init__(self):
        self.connected = False


class O6:
    def __init__(self):
        self.connected = False


class Engine:
    def __init__(self):
        self.roarm = Master()
        self.o6 = O6()
        self.connect_calls = 0

    def devices_connected(self):
        return self.roarm.connected and self.o6.connected

    def connect_devices(self):
        self.connect_calls += 1
        self.roarm.connected = True
        self.o6.connected = True


class Recorder:
    def __init__(self):
        self.active = False
        self.buffered = 0

    def snapshot(self):
        return {
            "episode_active": self.active,
            "buffered_frames": self.buffered,
        }


class CameraSnapshot:
    running = False
    error = ""


class Cameras:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.running = False

    def start(self, timeout=5.0):
        self.started += 1
        self.running = True

    def stop(self):
        self.stopped += 1
        self.running = False

    def snapshot(self):
        result = CameraSnapshot()
        result.running = self.running
        return result


class Source:
    def __init__(self):
        self.ready = False

    def snapshot_ready(self):
        return self.ready

    def readiness_error(self):
        return "" if self.ready else "腕部相机帧过期（13.00s）"


class Runtime:
    def __init__(self, engine, source):
        self.teleop_engine = engine
        self.master_controller = engine.roarm
        self.o6_controller = engine.o6
        self.sample_source = source


def _service(state=WorkflowState.CONNECTED):
    return ApplicationService(
        state_machine=WorkflowStateMachine(state=state)
    )


def test_prepare_devices_handler_connects_master_and_o6() -> None:
    service = _service()
    engine = Engine()
    recorder = Recorder()
    cameras = Cameras()
    OperatorPreparationBindings(
        service,
        teleop_engine=engine,
        recorder=recorder,
        cameras=cameras,
    ).install()

    result = service.dispatch(Command.PREPARE_DEVICES)

    assert engine.connect_calls == 1
    assert engine.roarm.connected
    assert engine.o6.connected
    assert result.state is WorkflowState.CONNECTED


def test_prepare_devices_is_idempotent_when_already_ready() -> None:
    service = _service()
    engine = Engine()
    engine.roarm.connected = True
    engine.o6.connected = True
    OperatorPreparationBindings(
        service,
        teleop_engine=engine,
        recorder=Recorder(),
        cameras=Cameras(),
    ).install()

    service.dispatch(Command.PREPARE_DEVICES)

    assert engine.connect_calls == 0


def test_start_camera_handler_uses_explicit_command() -> None:
    service = _service()
    cameras = Cameras()
    OperatorPreparationBindings(
        service,
        teleop_engine=Engine(),
        recorder=Recorder(),
        cameras=cameras,
    ).install()

    service.dispatch(
        Command.START_CAMERAS,
        {"timeout": 3.0},
    )

    assert cameras.started == 1


def test_stop_camera_rejected_during_active_episode() -> None:
    service = _service()
    recorder = Recorder()
    recorder.active = True
    cameras = Cameras()
    OperatorPreparationBindings(
        service,
        teleop_engine=Engine(),
        recorder=recorder,
        cameras=cameras,
    ).install()

    with pytest.raises(RuntimeError, match="Episode"):
        service.dispatch(Command.STOP_CAMERAS)

    assert cameras.stopped == 0


def test_stop_camera_rejected_while_episode_pending() -> None:
    service = _service()
    recorder = Recorder()
    recorder.buffered = 12
    cameras = Cameras()
    OperatorPreparationBindings(
        service,
        teleop_engine=Engine(),
        recorder=recorder,
        cameras=cameras,
    ).install()

    with pytest.raises(RuntimeError, match="待处理"):
        service.dispatch(Command.STOP_CAMERAS)

    assert cameras.stopped == 0


def test_readiness_provider_is_read_only() -> None:
    engine = Engine()
    source = Source()
    cameras = Cameras()
    runtime = Runtime(engine, source)
    provider = OperatorReadinessProvider(
        runtime=runtime,
        cameras=cameras,
    )

    snapshot = provider.snapshot()

    assert snapshot["master_type"] == "gello"
    assert not snapshot["master_connected"]
    assert not snapshot["o6_connected"]
    assert not snapshot["cameras_running"]
    assert not snapshot["camera_frames_ready"]
    assert engine.connect_calls == 0
    assert cameras.started == 0


def test_readiness_reports_stale_frames_and_clears_after_recovery():
    engine = Engine()
    source = Source()
    cameras = Cameras()
    cameras.running = True
    provider = OperatorReadinessProvider(runtime=Runtime(engine, source), cameras=cameras)

    snapshot = provider.snapshot()
    assert snapshot['cameras_running']
    assert not snapshot['camera_frames_ready']
    assert '腕部' in snapshot['camera_error']

    source.ready = True
    snapshot = provider.snapshot()
    assert snapshot['camera_frames_ready']
    assert snapshot['camera_error'] == ''
    assert cameras.started == cameras.stopped == 0
