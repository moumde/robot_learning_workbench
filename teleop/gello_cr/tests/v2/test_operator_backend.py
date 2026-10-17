
from __future__ import annotations

import time

from gello_cr.app import RuntimeLifecycleCallbacks
from gello_cr.core.state_machine import Command, WorkflowState
from gello_cr.ui.backend import OperatorBackend


class FakeTeleop:
    def __init__(self) -> None:
        self.calls = []
        self.state = "idle"
        self.last_error = ""

    def snapshot(self):
        return {
            "state": self.state,
            "last_error": self.last_error,
        }

    def start_follow(self):
        self.calls.append(("start_follow",))

    def stop_follow(self, reason):
        self.calls.append(("stop_follow", reason))

    def emergency_stop(self, reason):
        self.calls.append(("emergency_stop", reason))
        self.state = "fault"
        self.last_error = reason


class FakeRecorder:
    def __init__(self) -> None:
        self.calls = []

    def snapshot(self):
        return {
            "session_active": False,
            "episode_active": False,
            "buffered_frames": 0,
            "saved_episodes": 0,
            "error": "",
            "quality": {"needs_review": False},
        }

    def start_episode(self, task, base_root, metadata=None):
        self.calls.append(
            ("start_episode", task, base_root, dict(metadata or {}))
        )

    def stop_episode(self):
        self.calls.append(("stop_episode",))

    def save_episode(self, outcome, notes):
        self.calls.append(("save_episode", outcome, notes))

    def discard_episode(self):
        self.calls.append(("discard_episode",))


def _lifecycle(calls):
    return RuntimeLifecycleCallbacks(
        connect=lambda: calls.append("connect"),
        disconnect=lambda: calls.append("disconnect"),
        power_on=lambda: calls.append("power_on"),
        power_off=lambda: calls.append("power_off"),
        reset_fault=lambda: calls.append("reset_fault"),
        reset_estop=lambda: calls.append("reset_estop"),
    )


def _wait_state(backend, state, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if backend.service.state is state:
            return
        time.sleep(0.01)
    raise AssertionError(
        f"state did not become {state.name}: {backend.service.state.name}"
    )


def test_compose_starts_offline_without_calling_runtime_or_lifecycle() -> None:
    teleop = FakeTeleop()
    recorder = FakeRecorder()
    lifecycle_calls = []

    backend = OperatorBackend.compose(
        teleop_engine=teleop,
        recorder=recorder,
        lifecycle=_lifecycle(lifecycle_calls),
    )

    assert backend.service.state is WorkflowState.OFFLINE
    assert teleop.calls == []
    assert recorder.calls == []
    assert lifecycle_calls == []
    backend.close()


def test_backend_connect_uses_application_runtime_binding_async() -> None:
    teleop = FakeTeleop()
    recorder = FakeRecorder()
    lifecycle_calls = []
    backend = OperatorBackend.compose(
        teleop_engine=teleop,
        recorder=recorder,
        lifecycle=_lifecycle(lifecycle_calls),
    )

    from gello_cr.ui.command_port import CommandRequest

    backend.command_port.submit(CommandRequest.create(Command.CONNECT))
    _wait_state(backend, WorkflowState.CONNECTED)

    assert lifecycle_calls == ["connect"]
    assert teleop.calls == []
    backend.close()


def test_presenter_reads_existing_runtime_and_recorder() -> None:
    teleop = FakeTeleop()
    recorder = FakeRecorder()
    lifecycle_calls = []
    backend = OperatorBackend.compose(
        teleop_engine=teleop,
        recorder=recorder,
        lifecycle=_lifecycle(lifecycle_calls),
    )

    frame = backend.presenter.poll()

    assert frame.view_model.workflow_state is WorkflowState.OFFLINE
    assert frame.view_model.runtime_state == "idle"
    backend.close()


def test_backend_close_does_not_shutdown_or_power_hardware() -> None:
    teleop = FakeTeleop()
    recorder = FakeRecorder()
    lifecycle_calls = []
    backend = OperatorBackend.compose(
        teleop_engine=teleop,
        recorder=recorder,
        lifecycle=_lifecycle(lifecycle_calls),
    )

    backend.close()
    backend.close()

    assert teleop.calls == []
    assert recorder.calls == []
    assert lifecycle_calls == []
