"""Operator-visible regressions, exercised with real offscreen Qt widgets."""

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from shiboken6 import delete

from core.workbench.app import ApplicationService, build_application_view_model
from core.workbench.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from hmi.collection.command_port import CallbackCommandPort
from hmi.collection.main_window import OperatorMainWindow
from hmi.collection.pages.dataset_manager import DatasetManagerPage
from hmi.collection.planning_panel import PlanningPanel
from hmi.collection.presenter import OperatorUiPresenter


@pytest.fixture
def operator_window():
    app = QApplication.instance() or QApplication([])
    requests, recorder = [], {}
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    presenter = OperatorUiPresenter(service, runtime_snapshot=lambda: {}, recorder_snapshot=lambda: recorder)
    window = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    window.show()
    window.activateWindow()
    app.processEvents()
    yield window, requests, recorder, app
    presenter.close()
    window._shutdown_complete = True
    window.close()
    delete(window)
    app.processEvents()


def test_emergency_f12_reaches_command_port_from_owned_modal_without_repeat(operator_window):
    window, requests, _, app = operator_window
    modal = QDialog(window)
    modal.setModal(True)
    modal.show()
    modal.activateWindow()
    app.processEvents()
    try:
        QTest.keyClick(modal, Qt.Key_F12)
        app.sendEvent(modal, QKeyEvent(QEvent.KeyPress, Qt.Key_F12, Qt.NoModifier, '', True))
        app.sendEvent(modal, QKeyEvent(QEvent.KeyRelease, Qt.Key_F12, Qt.NoModifier, '', True))
        app.processEvents()
        assert [request.command for request in requests] == [Command.EMERGENCY_STOP]
    finally:
        modal.hide()
        delete(modal)


def test_emergency_f12_is_scoped_to_owning_window_and_detaches_on_close(operator_window):
    window, requests, _, app = operator_window
    unrelated = QDialog()
    unrelated.show()
    unrelated.activateWindow()
    app.processEvents()
    try:
        QTest.keyClick(unrelated, Qt.Key_F12)
        assert requests == []
        unrelated.hide()
        window.activateWindow()
        app.processEvents()
        QTest.keyClick(window, Qt.Key_F12)
        assert [request.command for request in requests] == [Command.EMERGENCY_STOP]
        requests.clear()
        window._shutdown_complete = True
        window.close()
        modal = QDialog(window)
        modal.setModal(True)
        modal.show()
        modal.activateWindow()
        app.processEvents()
        try:
            QTest.keyClick(modal, Qt.Key_F12)
            assert requests == []
        finally:
            modal.hide()
            delete(modal)
    finally:
        delete(unrelated)


def test_rejected_replan_cannot_execute_or_save_previous_target():
    app = QApplication.instance() or QApplication([])
    requests = []
    panel = PlanningPanel(lambda command, payload=None: requests.append((command, payload)))
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    view = build_application_view_model(service.snapshot(), {}, {})
    first = {'plan_id': 'first-plan', 'preview': {'target_joint_rad': [0] * 6}, 'status': 'READY'}
    try:
        panel.render({}, view)
        panel.plan_button.click()
        panel.render(first, view)
        assert panel.execute_button.isEnabled()
        panel.target_spins[0].setValue(20)
        panel.plan_button.click()
        assert requests[-1][0] is Command.PLAN_MOTION
        # A request rejected before the planner starts leaves the prior snapshot unchanged.
        panel.render(first, view)
        assert not panel.execute_button.isEnabled()
        assert not panel.save_button.isEnabled()
        second = {'plan_id': 'second-plan', 'preview': {'target_joint_rad': [0.35] * 6}, 'status': 'READY'}
        panel.render(second, view)
        assert panel.execute_button.isEnabled()
        panel.execute_button.click()
        assert requests[-1] == (Command.EXECUTE_PLAN, {'plan_id': 'second-plan'})
    finally:
        delete(panel)


def test_dataset_rescan_to_empty_clears_previous_validation_details():
    app = QApplication.instance() or QApplication([])
    page = DatasetManagerPage(lambda *args: None)
    try:
        page.render({'items': [{'path': '/previous', 'name': 'previous', 'format': 'hdf5', 'status': 'VALID',
                               'validation': {'valid': True, 'errors': [], 'warnings': []}}]}, {}, False)
        page.table.selectRow(0)
        assert 'PASS' in page.details.toPlainText()
        page.render({'items': []}, {}, False)
        assert page.details.toPlainText() == ''
        assert not page.validate_button.isEnabled()
    finally:
        delete(page)


def test_zero_frame_pending_episode_keeps_resolution_and_exit_confirmation(operator_window, monkeypatch):
    window, requests, recorder, _ = operator_window
    recorder.update(session_active=True, episode_active=False, episode_pending=True, buffered_frames=0)
    window.refresh_from_presenter()
    assert window.collection.discard_button.isEnabled()
    assert not window.collection.episode_start_button.isEnabled()
    confirmations = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: confirmations.append(args[2]) or QMessageBox.Cancel)
    assert not window.close()
    assert len(confirmations) == 1
    assert requests == []


def test_partial_selection_survives_regular_presenter_refresh():
    from hmi.collection.recovery_panel import RecoveryPanel

    app = QApplication.instance() or QApplication([])
    requests = []
    panel = RecoveryPanel(lambda command, payload=None: requests.append((command, payload)))
    snapshot = {'batch_id': 'active-batch', 'partial_episodes': [
        {'episode_index': 1, 'frame_count': 10}, {'episode_index': 2, 'frame_count': 20},
    ]}
    panel.show()
    panel.activateWindow()
    panel.render(snapshot)
    app.processEvents()
    try:
        panel.partials.showPopup()
        QTest.keyClick(panel.partials.view(), Qt.Key_Down)
        assert panel.partials.view().currentIndex().row() == 1
        panel.render(snapshot)
        QTest.keyClick(panel.partials.view(), Qt.Key_Enter)
        panel.failure_button.click()
        assert requests[-1] == (Command.RESOLVE_PARTIAL_EPISODE, {
            'batch_id': 'active-batch', 'episode_index': 2, 'decision': 'failure',
        })
    finally:
        panel.partials.hidePopup()
        delete(panel)


@pytest.mark.parametrize('action', ['dataset_root', 'legacy_json', 'lerobot'])
def test_file_chooser_keeps_emergency_stop_available(operator_window, action):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QFileDialog

    window, requests, _, app = operator_window
    visited = []

    def stop_and_cancel():
        dialog = app.activeModalWidget()
        visited.append(isinstance(dialog, QFileDialog))
        if dialog is not None:
            QTest.keyClick(dialog, Qt.Key_F12)
            dialog.reject()

    QTimer.singleShot(0, stop_and_cancel)
    if action == 'dataset_root':
        window.collection.root_edit.setText('/tmp')
        window.collection._choose_dataset_root()
    elif action == 'legacy_json':
        window.trajectory_panel._import_json()
    else:
        window.trajectory_panel._import_episode()
    assert visited == [True]
    assert [request.command for request in requests] == [Command.EMERGENCY_STOP]
