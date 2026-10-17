
from __future__ import annotations

from gello_cr.app import ApplicationService
from gello_cr.ui.presenter import OperatorUiPresenter


def _runtime():
    return {"state": "idle"}


def _recorder():
    return {
        "episode_active": False,
        "buffered_frames": 0,
        "saved_episodes": 0,
        "quality": {},
    }


def test_presenter_exposes_camera_preview() -> None:
    service = ApplicationService()
    marker = object()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
        preview_snapshot=lambda: {
            "base_rgb": marker,
            "wrist_rgb": marker,
            "roi_rgb": marker,
            "base_timestamp": 12.0,
            "wrist_timestamp": 13.0,
        },
    )

    frame = presenter.poll()

    assert frame.preview.base_rgb is marker
    assert frame.preview.wrist_rgb is marker
    assert frame.preview.roi_rgb is marker
    assert frame.preview.base_timestamp == 12.0
    assert frame.preview.wrist_timestamp == 13.0
    presenter.close()


def test_presenter_preview_defaults_empty() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
    )

    frame = presenter.poll()

    assert not frame.preview.has_base
    assert not frame.preview.has_wrist
    assert not frame.preview.has_roi
    presenter.close()
