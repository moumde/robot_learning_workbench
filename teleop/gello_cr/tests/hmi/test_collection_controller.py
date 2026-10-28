"""Collection actions preserve explicit results and show acknowledged saves."""

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import delete

from teleop.gello_cr.app import ApplicationService, build_application_view_model
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.pages.collection import CollectionPage
from teleop.gello_cr.ui.readiness import OperatorReadiness


@pytest.fixture
def page():
    app = QApplication.instance() or QApplication([])
    requests = []
    widget = CollectionPage(lambda command, payload=None: requests.append((command, payload)))
    yield widget, requests
    delete(widget)
    app.processEvents()


def show(page, dataset, state=WorkflowState.TELEOP_RUNNING):
    ready = {"master_connected": True, "o6_connected": True, "camera_frames_ready": True}
    service = ApplicationService(state_machine=WorkflowStateMachine(state))
    view = build_application_view_model(service.snapshot(), {}, dataset, ready)
    page.render(view, OperatorReadiness.from_mapping(ready), dataset)


@pytest.mark.parametrize("outcome", ["success", "failure"])
@pytest.mark.parametrize("recording", [True, False], ids=["recording", "pending"])
def test_direct_result_buttons_finish_collection_in_one_click(page, outcome, recording):
    widget, requests = page
    show(
        widget,
        {
            "episode_active": recording,
            "episode_pending": not recording,
            "session_active": True,
            "buffered_frames": 4,
        },
    )
    button = widget.save_success_button if outcome == "success" else widget.save_failure_button
    assert not button.isHidden()
    assert button.isEnabled()
    button.click()
    assert requests == [(Command.FINISH_COLLECTION, {"outcome": outcome})]
    assert not hasattr(widget, "outcome_combo")


def test_home_controls_have_separate_motion_and_success_save_commands(page):
    widget, requests = page
    show(widget, {"episode_active": True, "buffered_frames": 4})
    assert widget.return_home_button.isEnabled()
    assert widget.episode_stop_button.text() == "回 HOME 并成功保存"
    widget.return_home_button.click()
    widget.episode_stop_button.click()
    assert requests == [(Command.RETURN_HOME, None), (Command.HOME_AND_SAVE_EPISODE, None)]


def test_teleop_start_uses_collection_command_and_can_resume_active_episode(page):
    widget, requests = page
    widget.task_edit.setText("pick")
    widget.root_edit.setText("/data/captures")
    show(widget, {}, WorkflowState.ROBOT_ENABLED)
    assert widget.episode_start_button.isEnabled()
    assert widget.episode_start_button.text() == "开始记录"
    assert widget.episode_start_button.toolTip() == "启动遥操并开始录制"
    widget.episode_start_button.click()
    assert requests[-1] == (
        Command.START_COLLECTION,
        {"task": "pick", "description": "", "base_root": "/data/captures", "source": "teleop"},
    )
    show(widget, {"episode_active": True, "buffered_frames": 4}, WorkflowState.ROBOT_ENABLED)
    assert widget.episode_start_button.text() == "重新开始遥操"
    assert widget.episode_start_button.isEnabled()
    widget.episode_start_button.click()
    assert requests[-1] == (Command.START_TELEOP, None)


def test_discard_recording_confirms_once_and_cancel_preserves_it(page, monkeypatch):
    widget, requests = page
    show(widget, {"episode_active": True, "session_active": True, "buffered_frames": 4})
    confirmations = []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: confirmations.append(args[2]) or QMessageBox.Cancel
    )
    widget.discard_button.click()
    assert requests == []
    assert len(confirmations) == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    widget.discard_button.click()
    assert requests == [(Command.DISCARD_EPISODE, None)]


@pytest.mark.parametrize(
    ("source", "state"),
    [("replay", WorkflowState.REPLAY_RUNNING), ("point_move", WorkflowState.POINT_MOVE_RUNNING)],
)
def test_explicit_motion_capture_uses_legacy_start_without_teleop(page, source, state):
    widget, requests = page
    widget.task_edit.setText("pick")
    widget.root_edit.setText("/data/captures")
    show(widget, {"session_active": True}, state)
    assert not widget.episode_start_button.isEnabled()
    widget.recording_source_combo.setCurrentIndex(widget.recording_source_combo.findData(source))
    assert widget.episode_start_button.isEnabled()
    assert "遥操" not in widget.preparation_hint.text()
    widget.episode_start_button.click()
    assert requests[-1][0] is Command.START_EPISODE
    assert requests[-1][1]["source"] == source


@pytest.mark.parametrize("source", ["replay", "point_move"])
def test_motion_sources_can_prepare_dataset_before_starting_motion(page, source):
    widget, requests = page
    widget.task_edit.setText("pick")
    widget.root_edit.setText("/data/captures")
    widget.recording_source_combo.setCurrentIndex(widget.recording_source_combo.findData(source))
    show(widget, {}, WorkflowState.ROBOT_ENABLED)
    widget.dataset_setup_toggle.click()
    assert not widget.create_dataset_button.isHidden()
    assert widget.create_dataset_button.isEnabled()
    widget.create_dataset_button.click()
    assert requests[-1] == (
        Command.CREATE_DATASET,
        {"task": "pick", "description": "", "base_root": "/data/captures"},
    )
    show(widget, {"session_active": True}, WorkflowState.ROBOT_ENABLED)
    assert not widget.create_dataset_button.isEnabled()


def test_recorder_clock_metrics_and_save_receipt_are_not_hidden_in_details(page):
    widget, _ = page
    dataset = {
        "session_active": True,
        "episode_active": True,
        "buffered_frames": 842,
        "episode_index": 23,
        "duration": 84.7,
        "quality": {"effective_fps": 10, "skipped_samples": 2, "dropped_frames": None},
    }
    show(widget, dataset)
    assert widget.duration_metric.text() == "00:01:24"
    assert widget.episode_id_label.text() == "Episode 023"
    assert "10.0" in widget.fps_metric.text()
    assert "未统计" in widget.dropped_metric.text()
    assert "2" in widget.dropped_metric.toolTip()
    show(
        widget,
        {
            "session_active": True,
            "last_saved": {
                "episode_index": 23,
                "frame_count": 842,
                "outcome": "failure",
                "root": "/data/staging/pick/segment_000",
                "task": "pick",
            },
        },
    )
    assert not widget.save_receipt.isHidden()
    assert "023" in widget.save_receipt.text()
    assert "842" in widget.save_receipt.text()
    assert "/data/staging/pick/segment_000" in widget.save_receipt.text()


def test_error_pending_has_resolution_without_inviting_an_impossible_save(page):
    widget, _ = page
    show(widget, {"episode_pending": True, "buffered_frames": 0, "error": "camera unavailable"})
    assert not widget.save_success_button.isEnabled()
    assert not widget.save_failure_button.isEnabled()
    assert widget.discard_button.isEnabled()
    assert "暂无可保存帧" in widget.episode_hint.text()
