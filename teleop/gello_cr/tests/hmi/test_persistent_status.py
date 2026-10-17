"""Critical status remains visible while the operator changes pages."""

from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from gello_cr.app import ApplicationService
from gello_cr.core.state_machine import WorkflowState, WorkflowStateMachine
from gello_cr.ui.command_port import CallbackCommandPort
from gello_cr.ui.main_window import OperatorMainWindow
from gello_cr.ui.presenter import OperatorUiPresenter


def test_global_status_keeps_servo_feedback_and_all_fault_sources_visible():
    app = QApplication.instance() or QApplication([])
    ready = {
        "robot_profile": "cr3a_o6",
        "robot_name": "台架 CR3A",
        "robot_connected": True,
        "servo_state": "unknown",
        "robot_error": "Servo 反馈过期",
        "master_type": "gello",
        "master_connected": True,
        "master_ready": False,
        "master_error": "GELLO 掉线",
        "camera_error": "腕部相机断流",
    }
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: {},
        recorder_snapshot=lambda: {"error": "磁盘写入失败"},
        readiness_snapshot=lambda: ready,
    )
    window = OperatorMainWindow(presenter, CallbackCommandPort(lambda request: None))
    window._timer.stop()
    try:
        window.navigation.setCurrentRow(1)
        window.refresh_from_presenter()
        assert "未知" in window.servo_badge.text()
        assert "台架 CR3A" in window.identity_label.text()
        assert "GELLO 掉线" in window.notification.text()
        assert "腕部相机断流" in window.notification.text()
        assert "磁盘写入失败" in window.notification.text()
        assert window.notification.property("state") == "error"
        assert not window.home_button.isEnabled()
    finally:
        presenter.close()
        window._shutdown_complete = True
        window.close()
        delete(window)
        app.processEvents()
