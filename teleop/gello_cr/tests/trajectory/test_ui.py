"""Exercise trajectory actions through the real Qt command boundary."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.command_port import CallbackCommandPort
from teleop.gello_cr.ui.main_window import OperatorMainWindow
from teleop.gello_cr.ui.presenter import OperatorUiPresenter


@pytest.fixture
def trajectory_window():
    app = QApplication.instance() or QApplication([])
    service = ApplicationService(
        state_machine=WorkflowStateMachine(state=WorkflowState.ROBOT_ENABLED)
    )
    snapshot = {
        "trajectory": {
            "items": [
                {
                    "trajectory_id": "demo-id",
                    "name": "wrist demo",
                    "joint_mask": [False] * 5 + [True],
                },
            ]
        }
    }
    requests = []
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: snapshot,
        recorder_snapshot=lambda: {},
        readiness_snapshot=lambda: {
            "master_connected": True,
            "o6_connected": True,
            "robot_connected": True,
            "servo_state": "on",
            "capabilities": {"supports_joint_control": True},
        },
    )
    widget = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    yield widget, snapshot, requests, service
    snapshot["trajectory"] = {}
    presenter.close()
    widget.close()
    app.processEvents()


def test_trajectory_record_stop_and_save_use_application_commands(trajectory_window):
    widget, snapshot, requests, _ = trajectory_window
    panel = widget.trajectory_panel
    widget.motion_workspace.set_mode("record")
    panel.record_name.setText("pick demo")
    panel.record_button.click()
    assert requests[-1].command is Command.START_TRAJECTORY_RECORDING
    assert requests[-1].payload == {"name": "pick demo"}

    snapshot["trajectory"].update(recording=True, frame_count=20, duration_s=1.0)
    widget.refresh_from_presenter()
    panel.finish_button.click()
    assert requests[-1].command is Command.STOP_TRAJECTORY_RECORDING
    assert not panel.play_button.isEnabled()


def test_trajectory_selection_and_replay_options_reach_command_port(trajectory_window):
    widget, snapshot, requests, _ = trajectory_window
    panel = widget.trajectory_panel
    assert [check.isChecked() for check in panel.joint_checks] == [False] * 5 + [True]
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData("absolute"))
    panel.speed_spin.setValue(0.5)
    panel.repeat_spin.setValue(2)
    panel.hand_check.setChecked(False)
    panel.play_button.click()
    assert requests[-1].command is Command.REPLAY_TRAJECTORY
    assert requests[-1].payload == {
        "trajectory_id": "demo-id",
        "options": {
            "mode": "absolute",
            "time_scale": 0.5,
            "repeat": 2,
            "arm_enabled": True,
            "hand_enabled": False,
            "joint_mask": [False] * 5 + [True],
        },
    }
    snapshot["trajectory"]["preview"] = {
        "name": "wrist demo",
        "trajectory_id": "demo-id",
        "frame_count": 20,
        "duration_s": 1.0,
        "fps": 20.0,
        "robot_type": "cr3a",
        "joint_range_rad": [[0.0, 0.1]] * 6,
        "max_joint_velocity_rad_s": [0.1] * 6,
        "start_joint_rad": [0.0] * 6,
        "end_joint_rad": [0.1] * 6,
        "tcp_range": None,
        "hand_range": None,
    }
    widget.refresh_from_presenter()
    assert "wrist demo" in panel.preview_text.toPlainText()
    assert "rad/s" in panel.preview_text.toPlainText()


def test_hand_only_and_replay_stop_work_without_master_or_cameras(trajectory_window):
    widget, snapshot, requests, service = trajectory_window
    panel = widget.trajectory_panel
    panel.arm_check.setChecked(False)
    assert panel.play_button.isEnabled()
    service.dispatch(Command.REPLAY_TRAJECTORY)
    snapshot["trajectory"]["playing"] = True
    widget.refresh_from_presenter()
    assert widget.stop_motion_button.isEnabled()
    assert widget.estop_button.isEnabled()
    widget.stop_motion_button.click()
    assert requests[-1].command is Command.STOP_MOTION


def test_library_refresh_preserves_selection_and_preview_uses_selected_id(trajectory_window):
    widget, snapshot, requests, _ = trajectory_window
    panel = widget.trajectory_panel
    second = {
        "trajectory_id": "other-id",
        "name": "second demo",
        "source": "lerobot",
        "duration_s": 2.5,
        "frame_count": 50,
        "fps": 20.0,
        "robot_type": "cr3a",
    }
    snapshot["trajectory"]["items"].append(second)
    widget.refresh_from_presenter()
    panel.saved_list.setCurrentRow(1)
    assert "lerobot" in panel.saved_list.currentItem().text()
    assert "2.50 s" in panel.saved_list.currentItem().text()
    assert "second demo" in panel.preview_summary.text()
    assert "预览" in panel.preview_hint.text()
    assert panel.joint_table.item(0, 0).text() == "—"

    snapshot["trajectory"]["items"] = [second, snapshot["trajectory"]["items"][0]]
    widget.refresh_from_presenter()
    assert panel.saved_list.currentItem().data(Qt.UserRole) == "other-id"
    panel.preview_button.click()
    assert requests[-1].command is Command.PREVIEW_TRAJECTORY
    assert requests[-1].payload == {"trajectory_id": "other-id"}


def test_preview_table_converts_real_joint_values_and_clears_stale_data(trajectory_window):
    widget, snapshot, _, _ = trajectory_window
    panel = widget.trajectory_panel
    snapshot["trajectory"]["preview"] = {
        "trajectory_id": "demo-id",
        "name": "wrist demo",
        "robot_type": "cr3a",
        "source": "manual",
        "duration_s": 1.0,
        "frame_count": 20,
        "fps": 20.0,
        "joint_range_rad": [[-1.5707963267948966, 1.5707963267948966]] * 6,
        "start_joint_rad": [0.0] * 6,
        "end_joint_rad": [1.5707963267948966] * 6,
        "max_joint_velocity_rad_s": [3.141592653589793] * 6,
        "max_joint_delta_rad": [0.017453292519943295] * 6,
        "tcp_range": None,
        "hand_range": None,
        "warnings": ["check start position"],
    }
    widget.refresh_from_presenter()
    assert panel.joint_table.item(0, 0).text() == "0.00"
    assert panel.joint_table.item(0, 1).text() == "90.00"
    assert panel.joint_table.item(0, 2).text() == "−90.00 ～ 90.00"
    assert panel.joint_table.item(0, 3).text() == "180.00"
    assert panel.joint_table.item(0, 4).text() == "1.00"
    assert "°/s" in panel.joint_table.horizontalHeaderItem(3).text()
    assert "check start position" in panel.preview_warnings.text()

    snapshot["trajectory"]["items"].append({"trajectory_id": "empty", "name": "new"})
    widget.refresh_from_presenter()
    panel.saved_list.setCurrentRow(1)
    assert panel.joint_table.item(0, 0).text() == "—"
    assert "check start position" not in panel.preview_warnings.text()
    assert not panel.preview_text.toPlainText()


def test_modes_expose_only_relevant_actions_without_submitting_commands(trajectory_window):
    widget, _, requests, _ = trajectory_window
    panel = widget.trajectory_panel
    panel.record_name.setText("mode demo")
    assert not panel.record_button.isEnabled()
    panel.record_button.click()
    assert not requests
    panel.set_mode("record")
    assert not requests
    assert panel.replay_center.isHidden()
    assert not panel.record_center.isHidden()
    assert not panel.play_button.isEnabled()
    panel.play_button.click()
    assert not requests
    panel.record_button.click()
    assert requests[-1].command is Command.START_TRAJECTORY_RECORDING


def test_rec_indicator_only_marks_active_recording(trajectory_window):
    window, snapshot, _, _ = trajectory_window
    window.motion_workspace.set_mode("record")
    indicator = window.trajectory_panel._ui.trajectory_record_indicator
    assert "REC" not in indicator.text()
    snapshot["trajectory"].update(recording=True, frame_count=4)
    window.refresh_from_presenter()
    assert "REC" in indicator.text()
    snapshot["trajectory"].update(recording=False, pending=True)
    window.refresh_from_presenter()
    assert "REC" not in indicator.text()
    assert "待保存" in indicator.text()
