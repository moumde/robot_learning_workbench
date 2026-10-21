"""Unified motion modes share a catalog without issuing motion on navigation."""

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.core.state_machine import WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.command_port import CallbackCommandPort
from teleop.gello_cr.ui.main_window import OperatorMainWindow
from teleop.gello_cr.ui.presenter import OperatorUiPresenter


@pytest.fixture
def motion_window():
    app = QApplication.instance() or QApplication([])
    requests = []
    state = WorkflowStateMachine(WorkflowState.ROBOT_ENABLED)
    service = ApplicationService(state_machine=state)
    runtime = {
        "trajectory": {
            "items": [
                {
                    "trajectory_id": "saved-one",
                    "name": "pick path",
                    "source": "planning",
                    "duration_s": 2.5,
                }
            ]
        }
    }
    presenter = OperatorUiPresenter(
        service, runtime_snapshot=lambda: runtime, recorder_snapshot=lambda: {}
    )
    window = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    window._timer.stop()
    yield window, runtime, state, requests, app
    presenter.close()
    window._shutdown_complete = True
    window.close()
    delete(window)
    app.processEvents()


def test_motion_modes_share_actual_library_and_preserve_planning_draft(motion_window):
    window, _, _, requests, _ = motion_window
    workspace = window.motion_workspace
    assert window.navigation.count() == 5
    assert window.navigation.item(1).text() == "轨迹与走点"
    assert window.pages.count() == 5
    assert workspace.mode == "replay"
    workspace.set_mode("plan")
    window.planning_panel.target_spins[0].setValue(12.5)
    workspace.set_mode("record")
    workspace.set_mode("replay")
    workspace.set_mode("plan")
    assert window.planning_panel.target_spins[0].value() == 12.5
    assert workspace.library_host.isAncestorOf(window.trajectory_panel.saved_list)
    assert window.trajectory_panel.saved_list.count() == 1
    assert requests == []


@pytest.mark.parametrize(
    "mode,state,trajectory",
    [
        ("record", WorkflowState.TELEOP_RUNNING, {"recording": True, "frame_count": 10}),
        ("record", WorkflowState.ROBOT_ENABLED, {"pending": True, "frame_count": 10}),
        ("replay", WorkflowState.REPLAY_RUNNING, {"playing": True}),
        ("plan", WorkflowState.POINT_MOVE_RUNNING, {}),
    ],
)
def test_active_motion_keeps_its_controls_visible(motion_window, mode, state, trajectory):
    window, runtime, machine, requests, _ = motion_window
    machine.state = state
    runtime["trajectory"].update(trajectory)
    window.refresh_from_presenter()
    workspace = window.motion_workspace
    assert workspace.mode == mode
    other = "plan" if mode != "plan" else "replay"
    workspace.set_mode(other)
    assert workspace.mode == mode
    assert not workspace.mode_buttons[other].isEnabled()
    assert window.estop_button.isEnabled()
    assert requests == []


def test_library_selection_returns_to_replay_without_actuating(motion_window):
    window, _, _, requests, _ = motion_window
    workspace = window.motion_workspace
    workspace.set_mode("plan")
    library = window.trajectory_panel.saved_list
    library.itemClicked.emit(library.item(0))
    assert workspace.mode == "replay"
    assert requests == []


def test_motion_actions_remain_visible_in_small_window(motion_window):
    window, _, _, _, app = motion_window
    window.resize(1180, 820)
    window.show()
    window.navigation.setCurrentRow(1)
    app.processEvents()
    viewport = window.pages.currentWidget()
    for mode, targets in (
        ("record", [window.trajectory_panel.record_button, window.trajectory_panel.finish_button]),
        ("replay", [window.trajectory_panel.preview_button, window.trajectory_panel.play_button]),
        (
            "plan",
            [
                window.planning_panel.plan_button,
                window.planning_panel.execute_button,
                window.planning_panel.save_button,
            ],
        ),
    ):
        window.motion_workspace.set_mode(mode)
        app.processEvents()
        for button in targets:
            assert button.isVisibleTo(viewport)
            rect = button.rect()
            assert viewport.rect().contains(button.mapTo(viewport, QPoint(rect.left(), rect.top())))
            assert viewport.rect().contains(
                button.mapTo(viewport, QPoint(rect.right(), rect.bottom()))
            )
