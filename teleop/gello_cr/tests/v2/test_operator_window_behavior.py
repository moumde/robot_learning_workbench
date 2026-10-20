"""Qt behavior tests; offscreen window, injected backend, no device constructors."""
import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.core.state_machine import Command
from teleop.gello_cr.ui.command_port import CallbackCommandPort
from teleop.gello_cr.ui.main_window import OperatorMainWindow
from teleop.gello_cr.ui.presenter import OperatorUiPresenter


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    recorder = {'episode_active': False, 'buffered_frames': 0}
    service = ApplicationService()
    requests = []
    presenter = OperatorUiPresenter(service, runtime_snapshot=lambda: {},
        recorder_snapshot=lambda: recorder)
    widget = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    widget.show()
    app.processEvents()
    yield widget, recorder, requests, app
    recorder.update(episode_active=False, buffered_frames=0)
    if not presenter.closed:
        widget.close()
    app.processEvents()


@pytest.mark.parametrize('active,frames', [(True,0),(False,3)])
def test_episode_exit_is_blocked_and_does_not_submit_save_or_discard(window, monkeypatch, active, frames):
    widget, recorder, requests, app = window
    warnings = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: (warnings.append(args[2]), QMessageBox.Cancel)[1])
    recorder.update(episode_active=active, buffered_frames=frames)
    assert not widget.close()
    assert widget.isVisible() and warnings and requests == []
    assert not widget._presenter.closed


def test_f12_submits_software_estop_through_command_port(window):
    widget, recorder, requests, app = window
    widget.activateWindow()
    widget.setFocus()
    app.processEvents()
    QTest.keyClick(widget, Qt.Key_F12)
    app.processEvents()
    assert [r.command for r in requests] == [Command.EMERGENCY_STOP]


def test_offline_disables_motion_and_episode_controls(window):
    widget, _, requests, _ = window
    assert widget.collection.connect_button.isEnabled()
    assert not widget.collection.power_on_button.isEnabled()
    assert not widget.collection.start_teleop_button.isEnabled()
    assert not widget.collection.episode_start_button.isEnabled()
    assert requests == []


def test_dataset_format_selection_and_finalize_controls(window):
    widget, recorder, requests, _ = window
    assert widget.collection.dataset_format.currentData() == 'lerobot_v3'
    widget.collection.dataset_format.setCurrentIndex(widget.collection.dataset_format.findData('hdf5'))
    assert requests[-1].command is Command.SELECT_DATASET_FORMAT
    assert requests[-1].payload['format'] == 'hdf5'
    recorder.update(session_active=True, format='hdf5')
    widget.refresh_from_presenter()
    assert not widget.collection.dataset_format.isEnabled()
    assert not widget.collection.create_dataset_button.isEnabled()
    assert widget.collection.finalize_dataset_button.isEnabled()
    recorder.update(buffered_frames=3)
    widget.refresh_from_presenter()
    assert not widget.collection.finalize_dataset_button.isEnabled()
    recorder.update(session_active=False, buffered_frames=0,
                    validation={'valid': True, 'errors': [], 'warnings': []})
    widget.refresh_from_presenter()
    assert widget.collection.dataset_format.isEnabled()
    assert 'validation: PASS' in widget.collection.episode_status.text()


def test_recovery_panel_submits_explicit_partial_and_resume_decisions(window):
    widget, recorder, requests, _ = window
    recorder['recoverable_batches'] = [{
        'batch_id': 'batch-test', 'task_name': 'pick motor', 'dataset_format': 'hdf5',
        'episodes': 2, 'segments': 1, 'error': '',
        'partial_episodes': [{'episode_index': 2, 'frame_count': 100}],
    }]
    widget.refresh_from_presenter()
    panel = widget.dataset_page.recovery
    assert widget.navigation.currentRow() == 0
    assert widget.collection.isVisible()
    widget.recovery_button.click()
    assert widget.navigation.currentRow() == 3
    assert widget.dataset_page.isVisible()
    panel.failure_button.click()
    assert requests[-1].command is Command.RESOLVE_PARTIAL_EPISODE
    assert dict(requests[-1].payload) == {
        'batch_id': 'batch-test', 'episode_index': 2, 'decision': 'failure',
    }
    panel.resume_button.click()
    assert requests[-1].command is Command.RESUME_BATCH
    assert requests[-1].payload['batch_id'] == 'batch-test'


def test_third_preview_refreshes_without_a_new_base_or_wrist_frame(window):
    import numpy as np

    from teleop.gello_cr.ui.preview_model import CameraPreview

    widget, _, _, _ = window
    label = widget.collection.roi_preview
    widget.render_preview(CameraPreview(
        base_timestamp=1, wrist_timestamp=1, roi_timestamp=1,
        roi_rgb=np.zeros((8, 16, 3), dtype=np.uint8),
    ))
    assert label.pixmap().width() > label.pixmap().height()
    widget.render_preview(CameraPreview(
        base_timestamp=1, wrist_timestamp=1, roi_timestamp=2,
        roi_rgb=np.zeros((16, 8, 3), dtype=np.uint8),
        stream_names=('Front', 'Wrist', 'Side camera'),
        stream_descriptions=('a', 'b', 'c'),
    ))
    assert label.pixmap().height() > label.pixmap().width()
    assert widget.collection.preview_titles[2].text() == 'Side camera'
    assert widget.collection.preview_titles[2].toolTip() == 'c'


def test_dataset_root_is_submitted_and_locked_only_for_unresolved_episode(window):
    widget, recorder, requests, app = window
    service = widget._presenter._service
    service.dispatch(Command.CONNECT)
    service.dispatch(Command.POWER_ON)
    service.dispatch(Command.START_TELEOP)
    widget._presenter._readiness_snapshot = lambda: {
        'master_connected': True, 'o6_connected': True,
        'cameras_running': True, 'camera_frames_ready': True,
    }
    widget.collection.root_edit.setText('/tmp/new collection folder')
    widget.collection.task_edit.setText('test task')
    widget.refresh_from_presenter()
    assert widget.collection.root_edit.isEnabled()
    assert widget.collection.root_browse_button.isEnabled()
    widget.collection.episode_start_button.click()
    assert requests[-1].payload['base_root'] == '/tmp/new collection folder'
    recorder.update(episode_active=False, buffered_frames=3)
    widget.refresh_from_presenter()
    assert not widget.collection.root_edit.isEnabled()
    assert not widget.collection.root_browse_button.isEnabled()
    recorder.update(buffered_frames=0, session_active=True)
    widget.refresh_from_presenter()
    assert not widget.collection.root_edit.isEnabled()
    recorder.update(session_active=False)
    widget.refresh_from_presenter()
    assert widget.collection.root_edit.isEnabled()
    assert widget.collection.root_edit.text() == '/tmp/new collection folder'


@pytest.mark.parametrize('saved', [39, 40, 100])
def test_episode_start_recovers_after_camera_frames_resume(window, saved):
    widget, recorder, requests, app = window
    service = widget._presenter._service
    service.dispatch(Command.CONNECT)
    service.dispatch(Command.POWER_ON)
    readiness = {
        'master_connected': True, 'o6_connected': True,
        'cameras_running': True, 'camera_frames_ready': False,
        'camera_error': '腕部相机帧过期（13.00s）；请停止后重新启动双相机',
    }
    widget._presenter._readiness_snapshot = lambda: readiness
    recorder.update(saved_episodes=saved, session_active=True)
    widget.refresh_from_presenter()
    assert '腕部相机帧过期' in widget.collection.camera_hint.text()

    service.dispatch(Command.START_TELEOP)
    widget.refresh_from_presenter()
    assert not widget.collection.episode_start_button.isEnabled()
    assert '腕部相机帧过期' in widget.collection.camera_hint.text()
    assert '请先启动主从跟随' not in widget.collection.episode_hint.text()
    assert widget.collection.stop_cameras_button.isEnabled()

    readiness.update(camera_frames_ready=True, camera_error='')
    widget.refresh_from_presenter()
    assert widget.collection.episode_start_button.isEnabled()
    assert widget.collection.camera_hint.property('state') == 'success'
    assert '暂不能开始' not in widget.collection.episode_hint.text()
    assert widget.collection.saved_metric.text() == str(saved)
    widget.collection.episode_start_button.click()
    assert [r.command for r in requests] == [Command.START_EPISODE]


def test_space_toggles_twice_only_in_dagger_and_ignores_key_repeat(window):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    widget, _, requests, app = window
    service = widget._presenter._service
    widget.activateWindow()
    widget.collection.task_edit.setFocus()
    widget.collection.task_edit.setText('task')
    widget.collection.task_edit.setCursorPosition(4)
    app.processEvents()
    QTest.keyClick(widget.collection.task_edit, Qt.Key_Space)
    assert widget.collection.task_edit.text() == 'task ' and not requests

    service.dispatch(Command.CONNECT)
    service.dispatch(Command.POWER_ON)
    service.dispatch(Command.START_DAGGER)
    widget.refresh_from_presenter()
    widget.setFocus()
    app.processEvents()
    QTest.keyClick(widget, Qt.Key_Space)
    app.sendEvent(widget, QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier, ' ', True))
    QTest.keyClick(widget, Qt.Key_Space)
    assert [r.command for r in requests] == [Command.TOGGLE_INTERVENTION] * 2
    assert not widget.collection.task_edit.isEnabled()
    assert not widget.collection.episode_start_button.isEnabled()
    assert not widget.collection.start_teleop_button.isEnabled()
    QTest.keyClick(widget, Qt.Key_F12)
    assert requests[-1].command is Command.EMERGENCY_STOP

    service.dispatch(Command.EMERGENCY_STOP)
    widget.refresh_from_presenter()
    QTest.keyClick(widget, Qt.Key_Space)
    assert len(requests) == 3
    assert not widget._dagger_shortcut.isEnabled()


def test_dagger_start_requires_fresh_devices_and_submits_selected_fields(window):
    widget, _, requests, _ = window
    service = widget._presenter._service
    service.dispatch(Command.CONNECT)
    service.dispatch(Command.POWER_ON)
    widget.refresh_from_presenter()
    assert not widget.collection.dagger_start_button.isEnabled()
    widget._presenter._readiness_snapshot = lambda: {
        'master_connected': True, 'o6_connected': True,
        'cameras_running': True, 'camera_frames_ready': True,
        'robot_connected': True, 'servo_state': 'on',
    }
    widget.collection.dagger_host.setText('192.168.2.11')
    widget.collection.dagger_root.setText('/tmp/expert sessions')
    widget.collection.task_edit.setText('correct this task')
    widget.refresh_from_presenter()
    assert widget.collection.dagger_start_button.isEnabled()
    widget.collection.dagger_start_button.click()
    assert requests[-1].command is Command.START_DAGGER
    assert requests[-1].payload == {
        'host': '192.168.2.11', 'port': 8000, 'round_id': 'round1',
        'task': 'correct this task', 'base_root': '/tmp/expert sessions',
    }



def test_discovery_shutdown_error_still_stops_application(window, monkeypatch):
    from types import SimpleNamespace

    widget, _, _, _ = window
    stopped, errors = [], []
    discovery_blocked = True

    def close_discovery():
        if discovery_blocked:
            raise TimeoutError("camera discovery still running")

    def shutdown(**kwargs):
        stopped.append(True)
        widget._presenter.close()

    def run_close(operation, completed, **kwargs):
        error = None
        try:
            operation()
        except Exception as exc:
            error = exc
            errors.append(exc)
        completed(None, error)

    widget.settings_editor = SimpleNamespace(close_jobs=close_discovery)
    widget._close_callback = shutdown
    monkeypatch.setattr(widget._jobs, "start", run_close)
    try:
        widget.close()
        assert stopped == [True]
        assert errors and not widget._shutdown_complete
        assert not widget._timer.isActive()
        discovery_blocked = False
        widget.close()
        assert widget._shutdown_complete
        widget.close()
    finally:
        widget.settings_editor = None
        widget._close_callback = None
        widget._closing = False
