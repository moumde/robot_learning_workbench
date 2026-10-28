"""Operator guidance follows real workflow and recorder snapshots, without devices."""

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import delete

from teleop.gello_cr.app import ApplicationService, build_application_view_model
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.pages.collection import CollectionPage
from teleop.gello_cr.ui.readiness import OperatorReadiness


@pytest.fixture
def collection():
    app = QApplication.instance() or QApplication([])
    submitted = []
    page = CollectionPage(lambda command, payload=None: submitted.append((command, payload)))
    yield page, submitted
    delete(page)
    app.processEvents()


def render(page, state, recorder=None, *, busy=False, **readiness):
    devices = OperatorReadiness.from_mapping(readiness)
    service = ApplicationService(state_machine=WorkflowStateMachine(state))
    dataset = recorder or {}
    view = build_application_view_model(service.snapshot(), {}, dataset, readiness)
    page.render(view, devices, dataset, busy)


def test_offline_guidance_explains_the_next_preparation_action(collection):
    page, _ = collection
    render(page, WorkflowState.OFFLINE)

    assert page.connect_button.isEnabled()
    assert "连接机器人" in page.preparation_hint.text()
    assert not page.start_teleop_button.isEnabled()
    assert not page.episode_start_button.isEnabled()
    assert "连接机器人" in page.episode_hint.text()


def test_missing_master_guidance_replaces_ready_message(collection):
    page, _ = collection
    render(page, WorkflowState.ROBOT_ENABLED, master_connected=True, o6_connected=True)
    assert page.start_teleop_button.isEnabled()

    render(page, WorkflowState.ROBOT_ENABLED, master_connected=False, o6_connected=True)
    assert not page.start_teleop_button.isEnabled()
    assert "遥操设备" in page.preparation_hint.text()
    assert "输入设备" in page.start_teleop_button.toolTip()


def test_episode_controls_follow_recording_and_pending_lifecycle(collection):
    page, submitted = collection
    readiness = {
        "robot_connected": True,
        "servo_state": "on",
        "master_connected": True,
        "master_ready": True,
        "o6_connected": True,
        "camera_frames_ready": True,
    }
    page.task_edit.setText("motor_pick")
    page.root_edit.setText("/tmp/collection")
    render(page, WorkflowState.TELEOP_RUNNING, **readiness)
    assert page.episode_start_button.isEnabled()
    assert not page.episode_start_button.isHidden()
    assert not page.episode_stop_button.isEnabled()
    assert not page.save_success_button.isEnabled()
    page.episode_start_button.click()
    assert submitted[-1] == (
        Command.START_COLLECTION,
        {
            "task": "motor_pick",
            "description": "",
            "base_root": "/tmp/collection",
            "source": "teleop",
        },
    )

    render(
        page,
        WorkflowState.TELEOP_RUNNING,
        {"episode_active": True, "buffered_frames": 30},
        **readiness,
    )
    assert not page.episode_start_button.isHidden()
    assert not page.episode_start_button.isEnabled()
    assert not page.episode_stop_button.isHidden()
    assert "REC" in page.episode_headline.text()
    assert "正在录制" in page.preparation_hint.text()
    assert page.episode_stop_button.isEnabled()
    page.episode_stop_button.click()
    assert submitted[-1] == (Command.HOME_AND_SAVE_EPISODE, None)

    render(
        page,
        WorkflowState.TELEOP_RUNNING,
        {"episode_pending": True, "buffered_frames": 30},
        **readiness,
    )
    assert not page.episode_start_button.isHidden()
    assert not page.episode_start_button.isEnabled()
    assert not page.episode_stop_button.isEnabled()
    assert not page.save_success_button.isHidden()
    assert not page.save_failure_button.isHidden()
    assert not page.discard_button.isHidden()
    assert "未保存" in page.episode_headline.text()
    assert "保存" in page.preparation_hint.text()
    assert "成功" in page.episode_hint.text() and "失败" in page.episode_hint.text()
    page.save_success_button.click()
    assert submitted[-1] == (Command.FINISH_COLLECTION, {"outcome": "success"})


@pytest.mark.parametrize("frames", [0, 30])
def test_fault_pending_only_saves_failure_with_frames_or_explicitly_discards(
    collection, monkeypatch, frames
):
    page, submitted = collection
    render(page, WorkflowState.FAULT, {"episode_pending": True, "buffered_frames": frames})

    assert not page.save_success_button.isEnabled()
    assert page.save_failure_button.isEnabled() is bool(frames)
    assert page.discard_button.isEnabled()
    assert not page.discard_button.isHidden()
    assert ("故障" if frames else "暂无可保存帧") in page.episode_hint.text()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    page.discard_button.click()
    assert submitted[-1] == (Command.DISCARD_EPISODE, None)


def test_stale_camera_reason_clears_when_recording_becomes_available(collection):
    page, _ = collection
    page.task_edit.setText("motor_pick")
    page.root_edit.setText("/tmp/collection")
    readiness = {
        "master_connected": True,
        "o6_connected": True,
        "master_ready": True,
        "servo_state": "on",
        "robot_connected": True,
        "cameras_running": True,
    }
    page.recording_source_combo.setCurrentIndex(page.recording_source_combo.findData("teleop"))
    render(page, WorkflowState.TELEOP_RUNNING, camera_error="腕部相机帧过期", **readiness)
    assert not page.episode_start_button.isEnabled()
    assert "腕部相机帧过期" in page.episode_hint.text()
    assert "腕部相机帧过期" in page.episode_start_button.toolTip()

    render(page, WorkflowState.TELEOP_RUNNING, camera_frames_ready=True, **readiness)
    assert page.episode_start_button.isEnabled()
    assert "过期" not in page.episode_hint.text()
    assert "过期" not in page.episode_start_button.toolTip()


def test_busy_guidance_does_not_invite_a_second_command(collection):
    page, _ = collection
    render(page, WorkflowState.TELEOP_RUNNING, busy=True, camera_frames_ready=True)

    assert not page.episode_start_button.isEnabled()
    assert "等待当前操作" in page.episode_hint.text()
    assert "处理" in page.start_teleop_button.toolTip()


def test_recording_quality_warning_remains_visible_with_details_collapsed(collection):
    page, _ = collection
    render(
        page,
        WorkflowState.TELEOP_RUNNING,
        {
            "session_active": True,
            "episode_active": True,
            "buffered_frames": 30,
            "quality": {"needs_review": True},
        },
        camera_frames_ready=True,
    )

    assert page.episode_status.isHidden()
    assert "质量" in page.episode_hint.text()
    assert "详情" in page.episode_hint.text()
    assert page.episode_headline.property("state") == "warning"
    assert page.save_failure_button.isEnabled()
    assert not page.save_failure_button.isHidden()


def test_ready_without_task_explains_setup_before_first_episode(collection):
    page, _ = collection
    readiness = {
        "master_connected": True,
        "o6_connected": True,
        "master_ready": True,
        "servo_state": "on",
        "robot_connected": True,
        "camera_frames_ready": True,
    }
    page.root_edit.setText("/tmp/collection")
    render(page, WorkflowState.ROBOT_ENABLED, **readiness)
    assert not page.episode_start_button.isEnabled()
    render(page, WorkflowState.TELEOP_RUNNING, **readiness)
    assert "任务" in page.episode_headline.text()
    assert "任务名称" in page.episode_hint.text()
    assert not page.episode_start_button.isEnabled()

    page.task_edit.setText("motor_pick")
    render(page, WorkflowState.TELEOP_RUNNING, **readiness)
    assert "可以开始" in page.episode_headline.text()
    assert page.episode_start_button.isEnabled()
    render(page, WorkflowState.TELEOP_RUNNING, **{**readiness, "master_ready": False})
    assert not page.episode_start_button.isEnabled()
    render(page, WorkflowState.TELEOP_RUNNING, **{**readiness, "servo_state": "off"})
    assert not page.episode_start_button.isEnabled()
    render(page, WorkflowState.TELEOP_RUNNING, **readiness)
    page.root_edit.clear()
    assert not page.episode_start_button.isEnabled()


def test_dataset_setup_folds_once_per_session_and_keeps_operator_choice(collection):
    page, _ = collection
    render(page, WorkflowState.ROBOT_ENABLED, camera_frames_ready=True)
    assert not page.dataset_setup_toggle.isChecked()
    assert page.dataset_setup.isHidden()

    render(page, WorkflowState.ROBOT_ENABLED, {"session_active": True}, camera_frames_ready=True)
    assert not page.dataset_setup_toggle.isChecked()
    page.dataset_setup_toggle.click()
    render(page, WorkflowState.ROBOT_ENABLED, {"session_active": True}, camera_frames_ready=True)
    assert page.dataset_setup_toggle.isChecked()
    assert page.finalize_dataset_button.isEnabled()
    assert page.finalize_dataset_button.isVisibleTo(page)
    assert not page.root_edit.isEnabled()


def test_default_recording_workflow_skips_manual_dataset_creation(collection):
    page, _ = collection
    page.task_edit.setText("motor_pick")
    page.root_edit.setText("/data/captures")
    render(
        page,
        WorkflowState.ROBOT_ENABLED,
        master_connected=True,
        o6_connected=True,
        camera_frames_ready=True,
    )

    assert page.episode_start_button.isEnabled()
    assert page.episode_start_button.text() == "开始记录"
    assert "开始记录" in page.preparation_hint.text()
    assert page.episode_start_button.property("role") == "primary"
    assert page.start_teleop_button.property("role") == "quiet"
    assert page.create_dataset_button.isHidden()
    assert "/data/captures" in page.session_summary.text()
    page.dataset_setup_toggle.click()
    assert not page.dataset_setup.isHidden()
    assert page.create_dataset_button.isHidden()
    assert "自动创建" in page.name_preview.text()


def test_return_home_hint_explains_recording_will_be_pending(collection):
    page, _ = collection
    render(page, WorkflowState.TELEOP_RUNNING, {"episode_active": True, "buffered_frames": 30})
    assert "待保存" in page.return_home_button.toolTip()
    assert "待保存" in page.episode_hint.text()


def test_folded_session_keeps_current_task_and_output_identifiable(collection):
    page, _ = collection
    render(
        page,
        WorkflowState.TELEOP_RUNNING,
        {
            "session_active": True,
            "batch_task": "motor_pick",
            "format": "hdf5",
            "root": "/data/captures/motor_pick_batch",
        },
        camera_frames_ready=True,
    )

    assert not page.dataset_setup_toggle.isChecked()
    assert "motor_pick" in page.session_summary.text()
    assert "HDF5" in page.session_summary.text()
    assert page.session_summary.toolTip() == "/data/captures/motor_pick_batch"


def test_recording_summary_shows_final_output_instead_of_staging_segment(collection):
    page, _ = collection
    render(
        page,
        WorkflowState.ROBOT_ENABLED,
        {
            "session_active": True,
            "root": "/data/.staging/motor_pick/segment_000",
            "output_root": "/data/captures/motor_pick",
        },
        camera_frames_ready=True,
    )
    assert "保存目录：/data/captures/motor_pick" in page.session_summary.text()
    assert ".staging" not in page.session_summary.text()
    assert page.session_summary.toolTip() == "/data/captures/motor_pick"


@pytest.mark.parametrize("recording", [True, False], ids=["recording", "pending"])
def test_camera_frames_keep_episode_actions_in_minimum_window_viewport(recording):
    import numpy as np

    from teleop.gello_cr.ui.command_port import CallbackCommandPort
    from teleop.gello_cr.ui.main_window import OperatorMainWindow
    from teleop.gello_cr.ui.presenter import OperatorUiPresenter

    app = QApplication.instance() or QApplication([])
    recorder = {
        "session_active": True,
        "episode_active": recording,
        "episode_pending": not recording,
        "buffered_frames": 32,
    }
    readiness = {
        "robot_connected": True,
        "servo_state": "on",
        "master_connected": True,
        "master_ready": True,
        "o6_connected": True,
        "cameras_running": True,
        "camera_frames_ready": True,
        "capabilities": {"supports_home": True},
    }
    preview = {}
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: {"motion": {"source": "TELEOP"}},
        recorder_snapshot=lambda: recorder,
        readiness_snapshot=lambda: readiness,
        preview_snapshot=lambda: preview,
    )
    window = OperatorMainWindow(presenter, CallbackCommandPort(lambda request: None))
    window._timer.stop()
    try:
        window.resize(1180, 820)
        window.show()
        app.processEvents()
        page = window.collection
        initial_height = page.height()
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        preview.update(
            base_rgb=rgb,
            wrist_rgb=rgb,
            roi_rgb=rgb,
            base_timestamp=1,
            wrist_timestamp=1,
            roi_timestamp=1,
        )
        for _ in range(6):
            window.refresh_from_presenter()
            app.processEvents()
        scroll = window.pages.currentWidget()
        assert scroll.horizontalScrollBar().maximum() == 0
        assert scroll.verticalScrollBar().maximum() == 0
        assert page.height() <= initial_height
        targets = [page.save_success_button, page.save_failure_button, page.discard_button]
        if recording:
            targets += [page.return_home_button, page.episode_stop_button]
        assert page.collection_operations.width() == page.width()
        assert page.collection_operations.y() > page.workspace_scroll.geometry().bottom()
        assert page.collection_operations.parent() is page
        assert not page.episode_start_button.isHidden()
        assert not page.episode_start_button.isEnabled()
        for button in targets:
            assert button.isVisibleTo(window)
            assert button.isEnabled()
            position = button.mapTo(scroll.viewport(), QPoint())
            assert 0 <= position.y() < position.y() + button.height() <= scroll.viewport().height()
            assert 0 <= position.x() < position.x() + button.width() <= scroll.viewport().width()
        operations_position = page.collection_operations.pos()
        page.workspace_scroll.verticalScrollBar().setValue(
            page.workspace_scroll.verticalScrollBar().maximum()
        )
        app.processEvents()
        assert page.collection_operations.pos() == operations_position
        for image, metrics in zip(
            (page.base_preview, page.wrist_preview, page.roi_preview),
            page.camera_metrics,
            strict=True,
        ):
            workspace = page.workspace_scroll.widget()
            image_position = image.mapTo(workspace, QPoint())
            metrics_position = metrics.mapTo(workspace, QPoint())
            assert image_position.y() + image.height() <= metrics_position.y()
            assert metrics_position.y() + metrics.height() <= workspace.height()
    finally:
        presenter.close()
        window._shutdown_complete = True
        window.close()
        delete(window)
        app.processEvents()


def test_unsupported_home_controls_are_hidden_and_busy_keeps_independent_home(collection):
    page, _ = collection
    readiness = {
        "robot_connected": True,
        "servo_state": "on",
        "master_connected": True,
        "o6_connected": True,
        "camera_frames_ready": True,
        "robot_profile": "installed",
    }
    render(
        page,
        WorkflowState.TELEOP_RUNNING,
        {"episode_active": True, "buffered_frames": 4},
        capabilities={"supports_home": False},
        **readiness,
    )
    assert page.return_home_button.isHidden()
    assert page.episode_stop_button.isHidden()
    render(
        page,
        WorkflowState.TELEOP_RUNNING,
        {"episode_active": True, "buffered_frames": 4},
        busy=True,
        capabilities={"supports_home": True},
        **readiness,
    )
    assert not page.return_home_button.isHidden()
    assert page.return_home_button.isEnabled()
    for button in (
        page.episode_start_button,
        page.episode_stop_button,
        page.save_success_button,
        page.save_failure_button,
        page.discard_button,
    ):
        assert not button.isEnabled()
