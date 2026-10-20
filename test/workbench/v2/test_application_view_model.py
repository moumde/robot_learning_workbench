
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.workbench.app.service import ApplicationSnapshot
from core.workbench.app.view_model import build_application_view_model
from core.workbench.core.state_machine import Command, WorkflowState


def _app(
    state: WorkflowState,
    *,
    recovery: WorkflowState | None = None,
    error: str = "",
) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        state=state,
        recovery_state=recovery or state,
        event_sequence=0,
        last_error=error,
    )


def test_offline_view_model() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.OFFLINE),
        {"state": "idle"},
        {},
    )

    assert vm.workflow_label == "OFFLINE"
    assert vm.headline.startswith("OFFLINE")
    assert vm.severity == "info"
    assert vm.actions[Command.CONNECT]


def test_connected_view_model_preserves_runtime_state() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.CONNECTED),
        {"state": "idle"},
        {},
    )

    assert vm.runtime_state == "idle"
    assert vm.actions[Command.POWER_ON]
    assert vm.actions[Command.DISCONNECT]


def test_robot_enabled_headline_never_claims_following() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.ROBOT_ENABLED),
        {"state": "idle"},
        {},
    )

    assert "跟随未启动" in vm.headline
    assert vm.actions[Command.START_TELEOP]


def test_teleop_running_headline() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        {"state": "following"},
        {},
    )

    assert "主从跟随运行中" in vm.headline
    assert vm.actions[Command.START_EPISODE]


def test_active_recording_contains_frame_count() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        {"state": "following"},
        {
            "episode_active": True,
            "buffered_frames": 42,
            "saved_episodes": 3,
        },
    )

    assert vm.episode_active
    assert not vm.episode_pending
    assert vm.buffered_frames == 42
    assert vm.saved_episodes == 3
    assert "42 frames" in vm.headline
    assert vm.actions[Command.STOP_EPISODE]


def test_pending_recording_is_warning_and_saveable() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        {"state": "following"},
        {
            "episode_active": False,
            "buffered_frames": 20,
        },
    )

    assert vm.episode_pending
    assert vm.severity == "warning"
    assert vm.actions[Command.SAVE_SUCCESS]
    assert vm.actions[Command.SAVE_FAILURE]
    assert vm.actions[Command.DISCARD_EPISODE]


def test_fault_is_error_and_uses_application_error() -> None:
    vm = build_application_view_model(
        _app(
            WorkflowState.FAULT,
            recovery=WorkflowState.ROBOT_ENABLED,
            error="tracking timeout",
        ),
        {"state": "fault", "last_error": "runtime fault"},
        {},
    )

    assert vm.severity == "error"
    assert vm.application_error == "tracking timeout"
    assert vm.runtime_error == "runtime fault"
    assert vm.recovery_state is WorkflowState.ROBOT_ENABLED
    assert vm.actions[Command.RESET_FAULT]


def test_estop_is_always_error() -> None:
    vm = build_application_view_model(
        _app(
            WorkflowState.ESTOP,
            recovery=WorkflowState.ROBOT_ENABLED,
        ),
        {"state": "idle"},
        {},
    )

    assert vm.severity == "error"
    assert vm.headline.startswith("ESTOP")
    assert vm.actions[Command.RESET_ESTOP]


def test_runtime_error_marks_view_error_even_outside_fault_state() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.ROBOT_ENABLED),
        {"state": "idle", "error": "feedback stale"},
        {},
    )

    assert vm.severity == "error"
    assert vm.runtime_error == "feedback stale"


def test_recorder_error_marks_view_error() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        {"state": "following"},
        {
            "buffered_frames": 8,
            "error": "disk problem",
        },
    )

    assert vm.recording_error == "disk problem"
    assert vm.severity == "error"
    assert vm.actions[Command.SAVE_FAILURE]


def test_quality_review_marks_warning_without_error() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        {"state": "following"},
        {
            "quality": {"needs_review": True},
        },
    )

    assert vm.quality_needs_review
    assert vm.severity == "warning"


def test_dataset_session_flag_is_preserved() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        {},
        {"session_active": True},
    )

    assert vm.dataset_session_active


def test_unknown_runtime_state_has_explicit_fallback() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.OFFLINE),
        {},
        {},
    )

    assert vm.runtime_state == "unknown"


def test_view_model_is_frozen() -> None:
    vm = build_application_view_model(
        _app(WorkflowState.OFFLINE),
        {},
        {},
    )

    with pytest.raises(FrozenInstanceError):
        vm.severity = "error"  # type: ignore[misc]


def test_builder_does_not_mutate_source_mappings() -> None:
    runtime = {"state": "idle"}
    recorder = {
        "episode_active": False,
        "buffered_frames": 2,
        "quality": {"needs_review": False},
    }

    build_application_view_model(
        _app(WorkflowState.TELEOP_RUNNING),
        runtime,
        recorder,
    )

    assert runtime == {"state": "idle"}
    assert recorder["buffered_frames"] == 2
    assert recorder["quality"] == {"needs_review": False}
