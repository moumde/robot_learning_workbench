
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


def test_presenter_exposes_readiness_snapshot() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
        readiness_snapshot=lambda: {
            "master_type": "gello",
            "master_connected": True,
            "o6_connected": True,
            "cameras_running": True,
            "camera_frames_ready": True,
        },
    )

    frame = presenter.poll()

    assert frame.readiness.master_type == "gello"
    assert frame.readiness.devices_ready
    assert frame.readiness.cameras_running
    assert frame.readiness.camera_frames_ready
    presenter.close()


def test_presenter_default_readiness_is_not_ready() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
    )

    frame = presenter.poll()

    assert not frame.readiness.devices_ready
    assert not frame.readiness.cameras_running
    presenter.close()
