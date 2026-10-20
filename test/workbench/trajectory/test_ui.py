"""Exercise trajectory actions through the real Qt command boundary."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from core.workbench.app import ApplicationService
from core.workbench.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from hmi.collection.command_port import CallbackCommandPort
from hmi.collection.main_window import OperatorMainWindow
from hmi.collection.presenter import OperatorUiPresenter


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
