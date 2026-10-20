import math
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication

from teleop.gello_cr.app import ApplicationService, build_application_view_model
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.planning_panel import PlanningPanel


@pytest.fixture
def panel():
    app = QApplication.instance() or QApplication([])
    commands = []
    widget = PlanningPanel(lambda command, payload=None: commands.append((command, payload)))
    service = ApplicationService(
        state_machine=WorkflowStateMachine(state=WorkflowState.ROBOT_ENABLED)
    )
    view = build_application_view_model(service.snapshot(), {}, {})
    widget.render({"status": "IDLE"}, view)
    widget.show()
    app.processEvents()
    yield widget, commands, view
    widget.close()
    from shiboken6 import delete

    delete(widget)


def test_joint_ui_converts_degrees_and_requires_unchanged_preview_to_execute(panel):
    widget, commands, view = panel
    widget.target_spins[0].setValue(90)
    widget.plan_button.click()
    assert commands[-1][0] is Command.PLAN_MOTION
    assert commands[-1][1]["target"][0] == pytest.approx(math.pi / 2)
    assert commands[-1][1]["speed_scale"] == 0.3
    snapshot = {
        "plan_id": "new-plan",
        "preview": {"start_joint_rad": [0] * 6},
        "metrics": {},
        "status": "READY",
    }
    widget.render(snapshot, view)
    assert widget.execute_button.isEnabled()
    widget.execute_button.click()
    assert commands[-1] == (Command.EXECUTE_PLAN, {"plan_id": "new-plan"})
    widget.target_spins[0].setValue(91)
    assert not widget.execute_button.isEnabled()
    assert not widget.save_button.isEnabled()
    widget.render(snapshot, view)
    assert not widget.execute_button.isEnabled()
    assert "碰撞检查：不可用" in widget.preview_text.toPlainText()


def test_tcp_waypoint_editor_converts_units_and_reorders_without_motion(panel):
    widget, commands, view = panel
    widget.mode_combo.setCurrentIndex(widget.mode_combo.findData("waypoints"))
    widget.target_spins[0].setValue(420)
    widget.target_spins[3].setValue(180)
    widget.add_button.click()
    widget.target_spins[0].setValue(430)
    widget.add_button.click()
    widget.table.selectRow(1)
    widget.up_button.click()
    widget.plan_button.click()
    payload = commands[-1][1]
    assert payload["kind"] == "waypoints"
    assert payload["waypoints"][0]["pose"][0] == 0.43
    assert payload["waypoints"][1]["pose"][0] == 0.42
    assert payload["waypoints"][0]["pose"][3] == math.pi
    assert all(command is Command.PLAN_MOTION for command, _ in commands)
    widget.delete_button.click()
    assert widget.table.rowCount() == 1


def test_add_current_reads_tcp_through_command_and_stop_stays_available_while_busy(panel):
    widget, commands, view = panel
    widget.mode_combo.setCurrentIndex(widget.mode_combo.findData("waypoints"))
    widget.add_current_button.click()
    assert commands[-1][0] is Command.READ_MOTION_POSITION
    widget.render(
        {
            "position_serial": 1,
            "position": {"joint_rad": [0] * 6, "tcp": [0.42, -0.08, 0.3, math.pi, 0, 0]},
        },
        view,
    )
    assert widget.table.rowCount() == 1
    assert float(widget.table.item(0, 0).text()) == 420
    widget.render({"running": True, "status": "EXECUTING"}, view, busy=True)
    assert not widget.plan_button.isEnabled()
    assert not widget.table.isEnabled()
