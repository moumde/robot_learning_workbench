"""Visible status and preview regressions, using the real offline Qt shell."""

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from gello_cr.app import ApplicationService
from gello_cr.core.state_machine import WorkflowState, WorkflowStateMachine
from gello_cr.ui.command_port import CallbackCommandPort
from gello_cr.ui.main_window import OperatorMainWindow
from gello_cr.ui.presenter import OperatorUiPresenter


@pytest.fixture
def shell():
    app = QApplication.instance() or QApplication([])
    recorder, requests = {}, []
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.TELEOP_RUNNING))
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: {"motion": {"source": "TELEOP"}},
        recorder_snapshot=lambda: recorder,
    )
    window = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    window._timer.stop()
    window.show()
    app.processEvents()
    yield window, recorder, requests, app
    presenter.close()
    window._shutdown_complete = True
    window.close()
    delete(window)
    app.processEvents()


def test_recovery_discovery_preserves_page_and_offers_explicit_entry(shell):
    window, recorder, requests, app = shell
    window.navigation.setCurrentRow(1)
    recorder["recoverable_batches"] = [
        {
            "batch_id": "unfinished",
            "task_name": "pick",
            "dataset_format": "hdf5",
            "episodes": 0,
            "segments": 1,
            "error": "",
            "partial_episodes": [],
        }
    ]
    window.refresh_from_presenter()
    app.processEvents()
    assert window.navigation.currentRow() == 1
    assert window.recovery_button.isVisible()
    window.recovery_button.click()
    assert window.pages.currentIndex() == 3
    assert window.dataset_page.isVisibleTo(window.pages.currentWidget())
    assert requests == []


def test_workflow_summary_exposes_human_readable_headline(shell):
    window, recorder, _, _ = shell
    recorder.update(episode_pending=True, buffered_frames=0)
    window.refresh_from_presenter()
    assert "主从跟随运行中" in window.state_headline.text()
    assert "等待成功 / 失败 / 丢弃" in window.state_headline.text()
    assert window.state_headline.property("state") == "warning"


def test_preview_rescales_when_layout_changes_without_new_frame(shell):
    from gello_cr.ui.preview_model import CameraPreview

    window, _, _, _ = shell
    preview = CameraPreview(
        base_timestamp=1,
        base_rgb=np.zeros((480, 640, 3), dtype=np.uint8),
    )
    label = window.collection.base_preview
    label.setFixedSize(300, 200)
    window.render_preview(preview)
    assert label.pixmap().width() == 266
    label.setFixedSize(420, 280)
    window.render_preview(preview)
    assert label.pixmap().width() == 373


def test_camera_metrics_clear_when_stream_disappears(shell):
    from gello_cr.ui.preview_model import CameraPreview

    window, _, _, _ = shell
    window.render_preview(CameraPreview(streams=({"status": "OK", "fps": 30, "age_s": 0.01},)))
    assert "30.0 FPS" in window.collection.camera_metrics[0].text()
    window.render_preview(CameraPreview())
    assert "OFFLINE" in window.collection.camera_metrics[0].text()
    assert "30.0" not in window.collection.camera_metrics[0].text()
