"""Status presentation separates readiness, position snapshots and actionable faults."""

import math
import time

import pytest
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from teleop.gello_cr.app import ApplicationService, build_application_view_model
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.command_port import CallbackCommandPort
from teleop.gello_cr.ui.main_window import OperatorMainWindow
from teleop.gello_cr.ui.pages.robot_status import RobotStatusPage
from teleop.gello_cr.ui.presenter import OperatorUiPresenter
from teleop.gello_cr.ui.readiness import OperatorReadiness


@pytest.fixture
def page():
    app = QApplication.instance() or QApplication([])
    requests = []
    widget = RobotStatusPage(lambda command: requests.append(command))
    yield widget, requests, app
    delete(widget)
    app.processEvents()


def render(
    widget,
    state=WorkflowState.OFFLINE,
    *,
    ready=None,
    diagnostics=None,
    recorder=None,
    runtime=None,
    busy=False,
):
    service = ApplicationService(state_machine=WorkflowStateMachine(state))
    values = ready or {}
    view = build_application_view_model(service.snapshot(), runtime or {}, recorder or {}, values)
    widget.render(view, OperatorReadiness.from_mapping(values), diagnostics or {}, busy)


def test_offline_summary_distinguishes_discovery_from_connection(page):
    widget, requests, _ = page
    render(
        widget,
        ready={
            "robot_name": "CR3 + O6",
            "robot_connected": False,
            "master_type": "gello",
            "master_discovered": True,
        },
    )
    assert "未连接" in widget.connection_value.text()
    assert "已发现" in widget.master_value.text() and "未连接" in widget.master_value.text()
    assert "未连接" in widget.servo_value.text()
    assert widget.joint_table.item(0, 1).text() == "未连接"
    assert widget.technical_panel.isHidden()
    assert not widget.refresh_button.isEnabled()
    assert not widget.reset_fault_button.isEnabled()
    assert requests == []


def test_position_snapshot_has_units_and_does_not_override_live_servo(page):
    widget, _, _ = page
    diagnostics = {
        "joint_rad": [0, math.pi / 2, -math.pi / 2, 0, 0, 0],
        "tcp": [0.346, -0.116, 0.303, math.pi / 2, 0, -math.pi],
        "servo_state": 0,
        "sampled_at": time.monotonic() - 10,
    }
    render(
        widget,
        WorkflowState.ROBOT_ENABLED,
        ready={"robot_connected": True, "servo_state": "on", "master_connected": True},
        diagnostics=diagnostics,
    )
    assert "ON" in widget.servo_value.text()
    assert widget.joint_table.item(1, 1).text() == "90.000"
    assert widget.tcp_table.item(0, 1).text() == "346.000"
    assert widget.tcp_table.item(3, 1).text() == "90.000"
    assert "快照" in widget.feedback_hint.text() and "秒前" in widget.feedback_hint.text()
    assert widget.refresh_button.isEnabled()


def test_old_position_values_are_not_presented_after_disconnect(page):
    widget, _, _ = page
    diagnostics = {"joint_rad": [1] * 6, "tcp": [1] * 6, "sampled_at": time.monotonic()}
    render(
        widget,
        WorkflowState.ROBOT_ENABLED,
        ready={"robot_connected": True, "servo_state": "on"},
        diagnostics=diagnostics,
    )
    assert widget.joint_table.item(0, 1).text() != "未连接"
    render(widget, ready={"robot_connected": False}, diagnostics=diagnostics)
    assert widget.joint_table.item(0, 1).text() == "未连接"
    assert widget.tcp_table.item(0, 1).text() == "未连接"
    assert "未连接" in widget.feedback_hint.text()


def test_unknown_live_servo_does_not_fall_back_to_cached_on_state(page):
    widget, _, _ = page
    render(
        widget,
        WorkflowState.ROBOT_ENABLED,
        ready={"robot_connected": True, "servo_state": "unknown"},
        diagnostics={"servo_state": 3},
    )
    assert "未确认" in widget.servo_value.text()
    assert widget.servo_value.property("state") != "success"


def test_fault_sources_and_pending_episode_remedy_are_visible(page):
    widget, _, _ = page
    render(
        widget,
        WorkflowState.FAULT,
        ready={
            "robot_connected": True,
            "robot_error": "反馈过期",
            "master_error": "GELLO 掉线",
            "o6_error": "末端报警",
        },
        recorder={"episode_pending": True, "buffered_frames": 20, "error": "写盘中断"},
        runtime={"state": "fault", "error": "目标发送失败"},
    )
    text = widget.fault_banner.text()
    for message in ("反馈过期", "GELLO 掉线", "末端报警", "写盘中断", "目标发送失败"):
        assert message in text
    assert not widget.fault_banner.isHidden()
    assert not widget.reset_fault_button.isEnabled()
    assert "保存" in widget.fault_hint.text() and "丢弃" in widget.fault_hint.text()
    assert not widget.fault_hint.isHidden()


def test_buttons_keep_explicit_commands_and_technical_details_copy(page):
    widget, requests, app = page
    render(
        widget,
        WorkflowState.FAULT,
        ready={"robot_connected": True},
        diagnostics={
            "version": "1.0.0",
            "dataset": {"format": "lerobot_v21", "root": "/data/train"},
        },
    )
    widget.refresh_button.click()
    widget.reset_fault_button.click()
    assert requests == [Command.REFRESH_ROBOT_STATUS, Command.RESET_FAULT]
    widget.details_toggle.click()
    assert not widget.technical_panel.isHidden()
    widget.copy_details_button.click()
    assert app.clipboard().text() == widget.details.toPlainText()
    assert "/data/train" in app.clipboard().text()
    render(widget, WorkflowState.ESTOP, ready={"robot_connected": True})
    widget.reset_estop_button.click()
    assert requests[-1] is Command.RESET_ESTOP


def test_busy_disables_normal_actions_without_render_dispatch(page):
    widget, requests, _ = page
    render(
        widget,
        WorkflowState.ROBOT_ENABLED,
        ready={"robot_connected": True, "servo_state": "on"},
        busy=True,
    )
    assert not widget.refresh_button.isEnabled()
    assert not widget.reset_fault_button.isEnabled()
    assert requests == []


def test_connect_shortcut_only_navigates_and_footer_stays_visible():
    from PySide6.QtCore import QPoint

    app = QApplication.instance() or QApplication([])
    requests = []
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service, runtime_snapshot=lambda: {}, recorder_snapshot=lambda: {}
    )
    window = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    window._timer.stop()
    try:
        window.resize(1180, 820)
        window.show()
        window.navigation.setCurrentRow(3)
        window.robot_page.details_toggle.click()
        app.processEvents()
        container = window.pages.currentWidget()
        for button in (
            window.robot_page.refresh_button,
            window.robot_page.reset_fault_button,
            window.robot_page.reset_estop_button,
        ):
            assert button.isVisibleTo(container)
            assert container.rect().contains(
                button.mapTo(container, QPoint(button.width() - 1, button.height() - 1))
            )
        window.robot_page.connection_button.click()
        assert window.navigation.currentRow() == 0
        assert requests == []
    finally:
        presenter.close()
        window._shutdown_complete = True
        window.close()
        delete(window)
        app.processEvents()
