
from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.workbench.bootstrap.operator_app import build_operator_application
from core.workbench.core.state_machine import WorkflowState


class Teleop:
    state = "idle"
    last_error = ""

    def shutdown(self, *, close_devices=True):
        self.state = "closed"

    def snapshot(self):
        return {"state": self.state, "last_error": self.last_error}

    def start_follow(self):
        pass

    def stop_follow(self, reason):
        pass

    def finish_external_control(self):
        pass

    def emergency_stop(self, reason):
        pass


class Recorder:
    def close(self):
        pass

    def snapshot(self):
        return {
            "session_active": False,
            "episode_active": False,
            "buffered_frames": 0,
            "saved_episodes": 0,
            "error": "",
            "quality": {"needs_review": False},
        }

    def stop_episode(self):
        pass


class Camera:
    connected = False
    error = ""

    def connect(self, timeout=5.0):
        raise AssertionError("camera must not auto-connect")

    def latest(self):
        return None

    def close(self):
        pass


class SampleSource:
    def clear_streams(self):
        pass

    def clear_base(self):
        pass


class Lifecycle:
    def status_snapshot(self):
        return {"connected": False, "servo_state": "unknown", "sampled_at": None, "error": ""}

    def callbacks(self):
        from core.workbench.app import RuntimeLifecycleCallbacks
        return RuntimeLifecycleCallbacks(
            connect=lambda: None,
            disconnect=lambda: None,
            power_on=lambda: None,
            power_off=lambda: None,
            reset_fault=lambda: None,
            reset_estop=lambda: None,
        )


@dataclass
class Runtime:
    teleop_engine: object
    recorder: object
    camera_devices: dict
    sample_source: object
    cr3a_lifecycle: object
    store: object

    def close(self):
        pass

    @property
    def lifecycle(self):
        return self.cr3a_lifecycle.callbacks()


class Store:
    data = {
        "master": {"type": "gello"},
        "dataset": {
            "base_camera_serial": "base",
            "wrist_camera_serial": "wrist",
            "base_roi_norm": [0.1, 0.1, 0.9, 0.9],
            "task": "task",
            "root": "/tmp/data",
        },
    }


class Factory:
    def __init__(self):
        self.build_calls = 0
        self.runtime = Runtime(
            teleop_engine=Teleop(),
            recorder=Recorder(),
            camera_devices={"base": Camera(), "wrist": Camera()},
            sample_source=SampleSource(),
            cr3a_lifecycle=Lifecycle(),
            store=Store(),
        )

    def build(self):
        self.build_calls += 1
        return self.runtime


def test_operator_application_build_starts_offline(tmp_path) -> None:
    factory = Factory()

    app = build_operator_application(tmp_path, factory=factory)

    assert factory.build_calls == 1
    assert app.backend.service.state is WorkflowState.OFFLINE
    assert not app.cameras.running
    app.close()


def test_operator_application_build_does_not_connect_cameras(tmp_path) -> None:
    factory = Factory()

    app = build_operator_application(tmp_path, factory=factory)

    assert not factory.runtime.camera_devices["wrist"].connected
    assert not factory.runtime.camera_devices["base"].connected
    app.close()


def test_operator_dagger_root_uses_explicit_configuration(tmp_path, monkeypatch) -> None:
    external_openpi = tmp_path / "openpi"
    monkeypatch.setenv("GELLO_CR_OPENPI_ROOT", str(external_openpi))

    app = build_operator_application(tmp_path / "gello_CR", factory=Factory())

    assert app.dagger.openpi_root == external_openpi.resolve()
    app.close()


def test_operator_dagger_root_defaults_to_project(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GELLO_CR_OPENPI_ROOT", raising=False)
    repo_root = tmp_path / "gello_CR"

    app = build_operator_application(repo_root, factory=Factory())

    assert app.dagger.openpi_root == repo_root.resolve()
    app.close()


def test_operator_application_close_is_idempotent(tmp_path) -> None:
    app = build_operator_application(tmp_path, factory=Factory())

    app.close()
    app.close()


def test_operator_application_retains_runtime_object(tmp_path) -> None:
    factory = Factory()
    app = build_operator_application(tmp_path, factory=factory)

    assert app.runtime is factory.runtime
    app.close()


def test_unresolved_trajectory_requires_save_and_is_saved_on_explicit_exit(tmp_path):
    class TrajectoryTeleop(Teleop):
        pending = True
        calls = []

        def snapshot(self):
            return {**super().snapshot(), "trajectory": {"frame_count": 2 if self.pending else 0}}

        def stop_trajectory_recording(self):
            self.calls.append("stop_trajectory")

        def save_trajectory(self):
            self.calls.append("save_trajectory")
            self.pending = False

    factory = Factory()
    factory.runtime.teleop_engine = TrajectoryTeleop()
    app = build_operator_application(tmp_path, factory=factory)
    with pytest.raises(RuntimeError, match="轨迹"):
        app.close()
    assert not app.backend.presenter.closed
    app.close(save_pending=True)
    assert factory.runtime.teleop_engine.calls == ["stop_trajectory", "save_trajectory"]


def test_partial_batch_prevents_shutdown_before_commands_are_closed(tmp_path):
    class PartialRecorder(Recorder):
        def snapshot(self):
            return {**super().snapshot(), "partial_episodes": [{"episode_index": 2, "frame_count": 100}]}
    factory = Factory()
    factory.runtime.recorder = PartialRecorder()
    app = build_operator_application(tmp_path, factory=factory)
    with pytest.raises(RuntimeError, match="Partial"):
        app.close(save_pending=True)
    assert app._closed_resources == set()
    assert not app.backend.presenter.closed
    factory.runtime.recorder = Recorder()
    app.close()


def test_shutdown_stops_sampling_and_motion_before_cameras_and_workers(tmp_path):
    factory = Factory()
    order = []
    factory.runtime.recorder.stop_episode = lambda: order.append("sampling")
    factory.runtime.teleop_engine.shutdown = lambda **kw: order.append("motion")
    factory.runtime.close = lambda: order.append("devices")
    factory.runtime.recorder.close = lambda: order.append("worker")
    app = build_operator_application(tmp_path, factory=factory)
    app.cameras.close = lambda: order.append("cameras")
    app.close()
    assert order == ["sampling", "motion", "cameras", "devices", "worker"]


@pytest.mark.parametrize("failed_stage", ["sampling", "motion"])
def test_shutdown_preserves_dependencies_until_producers_stop(tmp_path, failed_stage):
    factory = Factory()
    order = []
    failed = False

    def stop(stage):
        nonlocal failed
        order.append(stage)
        if stage == failed_stage and not failed:
            failed = True
            raise TimeoutError(f"{stage} still running")

    factory.runtime.recorder.stop_episode = lambda: stop("sampling")
    factory.runtime.teleop_engine.shutdown = lambda **kw: stop("motion")
    factory.runtime.close = lambda: order.append("devices")
    factory.runtime.recorder.close = lambda: order.append("worker")
    app = build_operator_application(tmp_path, factory=factory)
    app.cameras.close = lambda: order.append("cameras")
    with pytest.raises(ExceptionGroup, match="shutdown incomplete"):
        app.close()
    assert "motion" in order
    assert not {"cameras", "devices", "worker"}.intersection(order)
    assert not app.backend.presenter.closed
    app.close()
    assert order[-3:] == ["cameras", "devices", "worker"]
    assert app.backend.presenter.closed
