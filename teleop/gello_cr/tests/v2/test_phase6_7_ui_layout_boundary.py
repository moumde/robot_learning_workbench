"""Preview, emergency control and bounded log contracts with real Qt widgets."""

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from gello_cr.app import ApplicationService
from gello_cr.core.state_machine import Command
from gello_cr.ui.command_port import CallbackCommandPort
from gello_cr.ui.main_window import OperatorMainWindow
from gello_cr.ui.presenter import OperatorUiPresenter

ROOT = Path(__file__).resolve().parents[2]


def _source(path):
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    requests, preview = [], {}
    presenter = OperatorUiPresenter(
        ApplicationService(),
        runtime_snapshot=lambda: {},
        recorder_snapshot=lambda: {},
        preview_snapshot=lambda: preview,
    )
    widget = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    widget._timer.stop()
    widget.show()
    app.processEvents()
    yield widget, requests, preview
    widget._shutdown_complete = True
    widget.close()
    presenter.close()
    delete(widget)
    app.processEvents()


def test_main_window_has_three_preview_panels(window) -> None:
    widget, _, _ = window

    assert [title.text() for title in widget.collection.preview_titles] == [
        "Base RGB",
        "Wrist RGB",
        "Base ROI",
    ]
    for label in (
        widget.collection.base_preview,
        widget.collection.wrist_preview,
        widget.collection.roi_preview,
    ):
        assert label.isVisible()
        assert label.property("role") == "previewImage"


def test_main_window_renders_preview_from_presenter_frame(window) -> None:
    widget, _, preview = window
    images = [np.zeros((24, 32, 3), dtype=np.uint8) for _ in range(3)]
    preview.update(
        base_rgb=images[0],
        wrist_rgb=images[1],
        roi_rgb=images[2],
        base_timestamp=1,
        wrist_timestamp=1,
        roi_timestamp=1,
    )

    widget.refresh_from_presenter()

    for label, metrics in zip(
        (
            widget.collection.base_preview,
            widget.collection.wrist_preview,
            widget.collection.roi_preview,
        ),
        widget.collection.camera_metrics,
        strict=True,
    ):
        assert not label.pixmap().isNull()
        assert label.text() == ""
        assert metrics.property("state") == "success"


def test_main_window_does_not_read_physical_camera_objects() -> None:
    source = _source("src/gello_cr/ui/main_window.py")

    for forbidden in (
        "RealSenseRgbDevice",
        "CameraPollingService",
        "pyrealsense2",
        ".latest()",
        ".wrist_camera",
        ".base_camera",
    ):
        assert forbidden not in source


def test_estop_is_prominent_independent_header_control(window) -> None:
    widget, requests, _ = window

    assert widget.estop_button.property("role") == "estopButton"
    assert widget.estop_button.minimumWidth() >= 230
    assert widget.estop_button.minimumHeight() >= 64
    for index in range(widget.navigation.count()):
        widget.navigation.setCurrentRow(index)
        assert widget.estop_button.isVisible()
    widget.estop_button.click()
    assert [request.command for request in requests] == [Command.EMERGENCY_STOP]


def test_event_log_is_bounded_and_compact(window) -> None:
    widget, _, _ = window

    assert widget.event_log.maximumHeight() <= 145
    for index in range(450):
        widget.event_log.appendPlainText(str(index))
    assert widget.event_log.document().blockCount() == 400
    assert widget.event_log.toPlainText().splitlines()[0] == "50"


def test_operator_app_supplies_preview_source_without_starting_camera() -> None:
    source = _source("src/gello_cr/bootstrap/operator_app.py")

    # Alternate/test sources may return an empty preview; concrete cameras are
    # injected through the presentation boundary and never auto-started.
    assert "preview_snapshot = getattr(" in source
    assert '"preview_snapshot"' in source
    assert "preview_snapshot=preview_snapshot" in source
    assert ".cameras.start(" not in source
