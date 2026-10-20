from test.workbench.fakes.paths import implementation_path


def _source(path):
    return implementation_path(path).read_text(encoding="utf-8")


def test_main_window_never_calls_camera_or_runtime_objects() -> None:
    source = _source("hmi/collection/main_window.py")

    for forbidden in (
        "CameraPollingService",
        "TeleopEngine",
        "connect_devices()",
        ".cameras.start(",
        ".wrist_camera",
        ".base_camera",
    ):
        assert forbidden not in source


def test_main_window_submits_preparation_commands() -> None:
    source = _source("hmi/collection/pages/collection.py")
    assert "Command.PREPARE_DEVICES" in source
    assert "Command.START_CAMERAS" in source
    assert "Command.STOP_CAMERAS" in source


def test_readiness_only_narrows_primary_workflow_buttons() -> None:
    from core.workbench.app import ApplicationService, build_application_view_model
    from core.workbench.core.state_machine import Command, WorkflowState, WorkflowStateMachine

    for state, connected, camera, teleop_allowed, record_allowed in (
        (WorkflowState.OFFLINE, True, True, False, False),
        (WorkflowState.ROBOT_ENABLED, False, True, False, False),
        (WorkflowState.ROBOT_ENABLED, True, True, True, False),
        (WorkflowState.TELEOP_RUNNING, True, False, False, False),
        (WorkflowState.TELEOP_RUNNING, True, True, False, True),
    ):
        service = ApplicationService(state_machine=WorkflowStateMachine(state))
        ready = {
            "master_connected": connected,
            "o6_connected": connected,
            "camera_frames_ready": camera,
        }
        view = build_application_view_model(service.snapshot(), {}, {}, ready)
        assert view.actions[Command.START_TELEOP] is teleop_allowed
        assert view.actions[Command.START_EPISODE] is record_allowed


def test_operator_app_does_not_start_devices_or_cameras() -> None:
    source = _source("core/workbench/bootstrap/operator_app.py")

    assert ".cameras.start(" not in source
    assert ".connect_devices(" not in source
    assert ".power_on(" not in source
    assert ".start_follow(" not in source


def test_preparation_handlers_live_outside_ui_layer() -> None:
    source = _source("core/workbench/bootstrap/preparation.py")

    assert "self._teleop_engine.connect_devices()" in source
    assert "self._cameras.start(" in source
    assert "self._cameras.stop()" in source
    assert "PySide6" not in source
    assert "PyQt5" not in source
