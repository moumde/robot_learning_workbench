from __future__ import annotations

import pytest

from teleop.gello_cr.app.runtime_bindings import (
    RuntimeCommandBindings,
    RuntimeLifecycleCallbacks,
)
from teleop.gello_cr.app.service import ApplicationService
from teleop.gello_cr.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    RecordingState,
    WorkflowStateMachine,
)


class FakeTeleop:
    def __init__(self):
        self.calls = []
        self.on_emergency = None

    def start_follow(self):
        self.calls.append(("start_follow",))
        return "started"

    def stop_follow(self, reason):
        self.calls.append(("stop_follow", reason))
        return "stopped"

    def emergency_stop(self, reason):
        self.calls.append(("emergency_stop", reason))
        if self.on_emergency is not None:
            self.on_emergency()
        return "estopped"


@pytest.mark.parametrize("runtime_state", ["fault", "preset", "following"])
def test_home_completion_cannot_clear_a_new_stop_or_active_motion(runtime_state):
    service = ApplicationService(state_machine=WorkflowStateMachine(state=WorkflowState.ESTOP))
    teleop = FakeTeleop()
    teleop.state = runtime_state
    RuntimeCommandBindings(service, teleop_engine=teleop, recorder=FakeRecorder()).install()
    with pytest.raises(InvalidTransition):
        service.dispatch(Command.HOME_COMPLETED)
    assert service.state is WorkflowState.ESTOP


def test_home_completion_keeps_pending_data_and_never_restarts_follow():
    service = ApplicationService(state_machine=WorkflowStateMachine(state=WorkflowState.RETURNING_HOME))
    teleop = FakeTeleop()
    teleop.state = "idle"
    recorder = FakeRecorder()
    RuntimeCommandBindings(service, teleop_engine=teleop, recorder=recorder).install()
    service.dispatch(Command.HOME_COMPLETED)
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert recorder.calls == []
    assert teleop.calls == []
    service._state_machine.recording_state = RecordingState.PENDING
    service.dispatch(Command.SAVE_FAILURE)
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert teleop.calls == []


class FakeRecorder:
    def __init__(self):
        self.calls = []

    def start_episode(self, task, base_root, *, metadata=None):
        self.calls.append(
            ("start_episode", task, base_root, metadata)
        )
        return "recording"

    def save_episode(self, outcome="success", notes=""):
        self.calls.append(("save_episode", outcome, notes))
        return "saved"

    def discard_episode(self):
        self.calls.append(("discard_episode",))
        return "discarded"

    def finalize(self):
        self.calls.append(("finalize",))
        return "dataset-root"


def test_finalize_dataset_uses_the_generic_recorder_without_changing_robot_state():
    service, teleop, recorder = _bindings(WorkflowState.ROBOT_ENABLED)
    result = service.dispatch(Command.FINALIZE_DATASET)
    assert result.value == "dataset-root"
    assert recorder.calls == [("finalize",)]
    assert service.state is WorkflowState.ROBOT_ENABLED and not teleop.calls


def _service_at(state):
    return ApplicationService(
        state_machine=WorkflowStateMachine(
            state=state,
            recovery_state=state,
        )
    )


def _bindings(state, lifecycle=None):
    service = _service_at(state)
    teleop = FakeTeleop()
    recorder = FakeRecorder()
    RuntimeCommandBindings(
        service,
        teleop_engine=teleop,
        recorder=recorder,
        lifecycle=lifecycle,
    ).install()
    return service, teleop, recorder


def test_connect_uses_explicit_lifecycle_callback() -> None:
    calls = []
    lifecycle = RuntimeLifecycleCallbacks(
        connect=lambda: calls.append("connect") or "connected"
    )
    service, _, _ = _bindings(
        WorkflowState.OFFLINE,
        lifecycle,
    )

    result = service.dispatch(Command.CONNECT)

    assert calls == ["connect"]
    assert result.value == "connected"
    assert service.state is WorkflowState.CONNECTED


def test_missing_connect_callback_prevents_state_advance() -> None:
    service, _, _ = _bindings(WorkflowState.OFFLINE)

    with pytest.raises(RuntimeError, match="CONNECT"):
        service.dispatch(Command.CONNECT)

    assert service.state is WorkflowState.OFFLINE


def test_power_on_uses_lifecycle_callback() -> None:
    calls = []
    lifecycle = RuntimeLifecycleCallbacks(
        power_on=lambda: calls.append("power_on")
    )
    service, _, _ = _bindings(
        WorkflowState.CONNECTED,
        lifecycle,
    )

    service.dispatch(Command.POWER_ON)

    assert calls == ["power_on"]
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_power_on_for_arm_replay_does_not_require_master_or_hand():
    service = _service_at(WorkflowState.CONNECTED)
    calls = []
    RuntimeCommandBindings(service, teleop_engine=FakeTeleop(), recorder=FakeRecorder(),
        lifecycle=RuntimeLifecycleCallbacks(power_on=lambda: calls.append("power_on")),
        readiness_snapshot=lambda: {"master_connected": False, "o6_connected": False},
    ).install()
    service.dispatch(Command.POWER_ON)
    assert calls == ["power_on"]
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_start_teleop_calls_existing_engine() -> None:
    service, teleop, _ = _bindings(
        WorkflowState.ROBOT_ENABLED
    )

    result = service.dispatch(Command.START_TELEOP)

    assert teleop.calls == [("start_follow",)]
    assert result.value == "started"
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_stop_teleop_forwards_reason() -> None:
    service, teleop, _ = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    service.dispatch(
        Command.STOP_TELEOP,
        {"reason": "operator stop"},
    )

    assert teleop.calls == [
        ("stop_follow", "operator stop")
    ]
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_start_episode_forwards_task_root_and_metadata() -> None:
    service, _, recorder = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    service.dispatch(
        Command.START_EPISODE,
        {
            "task": "Pick motor",
            "base_root": "/data/run",
            "metadata": {"operator": "test"},
        },
    )

    assert recorder.calls == [
        (
            "start_episode",
            "Pick motor",
            "/data/run",
            {"operator": "test", "recording_source": "teleop"},
        )
    ]
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_start_episode_missing_task_keeps_teleop_state() -> None:
    service, _, recorder = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    with pytest.raises(ValueError, match="task"):
        service.dispatch(
            Command.START_EPISODE,
            {"base_root": "/data/run"},
        )

    assert recorder.calls == []
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_start_episode_rejects_non_mapping_metadata() -> None:
    service, _, _ = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    with pytest.raises(TypeError, match="metadata"):
        service.dispatch(
            Command.START_EPISODE,
            {
                "task": "task",
                "base_root": "/data",
                "metadata": ["bad"],
            },
        )

    assert service.state is WorkflowState.TELEOP_RUNNING


@pytest.mark.parametrize(
    ("command", "outcome"),
    [
        (Command.SAVE_SUCCESS, "success"),
        (Command.SAVE_FAILURE, "failure"),
    ],
)
def test_save_commands_forward_outcome_and_notes(
    command,
    outcome,
) -> None:
    service, _, recorder = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    service._state_machine.recording_state = RecordingState.PENDING
    service.dispatch(command, {"notes": "checked"})

    assert recorder.calls == [
        ("save_episode", outcome, "checked")
    ]
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_discard_episode_calls_existing_recorder() -> None:
    service, _, recorder = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    service._state_machine.recording_state = RecordingState.PENDING
    service.dispatch(Command.DISCARD_EPISODE)

    assert recorder.calls == [("discard_episode",)]
    assert service.state is WorkflowState.TELEOP_RUNNING


def test_emergency_stop_calls_engine_after_app_enters_estop() -> None:
    service, teleop, _ = _bindings(
        WorkflowState.TELEOP_RUNNING
    )
    observed = []
    teleop.on_emergency = lambda: observed.append(service.state)

    service.dispatch(
        Command.EMERGENCY_STOP,
        {"reason": "operator E-stop"},
    )

    assert observed == [WorkflowState.ESTOP]
    assert teleop.calls == [
        ("emergency_stop", "operator E-stop")
    ]
    assert service.state is WorkflowState.ESTOP


def test_report_fault_uses_engine_emergency_stop() -> None:
    service, teleop, _ = _bindings(
        WorkflowState.TELEOP_RUNNING
    )

    service.dispatch(
        Command.REPORT_FAULT,
        {"reason": "feedback timeout"},
    )

    assert teleop.calls == [
        ("emergency_stop", "故障停止：feedback timeout")
    ]
    assert service.state is WorkflowState.FAULT


def test_reset_estop_requires_explicit_lifecycle_callback() -> None:
    service, _, _ = _bindings(
        WorkflowState.TELEOP_RUNNING
    )
    service.dispatch(Command.EMERGENCY_STOP)

    with pytest.raises(RuntimeError, match="RESET_ESTOP"):
        service.dispatch(Command.RESET_ESTOP)

    assert service.state is WorkflowState.ESTOP


def test_reset_estop_callback_returns_only_robot_enabled() -> None:
    calls = []
    lifecycle = RuntimeLifecycleCallbacks(
        reset_estop=lambda: calls.append("reset")
    )
    service, _, _ = _bindings(
        WorkflowState.TELEOP_RUNNING,
        lifecycle,
    )

    service.dispatch(Command.EMERGENCY_STOP)
    service.dispatch(Command.RESET_ESTOP)

    assert calls == ["reset"]
    assert service.state is WorkflowState.ROBOT_ENABLED
