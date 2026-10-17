
from __future__ import annotations

import pytest

from gello_cr.app import ApplicationService
from gello_cr.core.state_machine import Command, WorkflowState
from gello_cr.ui.presenter import OperatorUiPresenter


def _runtime():
    return {"state": "idle", "error": ""}


def _recorder():
    return {
        "session_active": False,
        "episode_active": False,
        "buffered_frames": 0,
        "saved_episodes": 2,
        "error": "",
        "quality": {"needs_review": False},
    }


def test_presenter_combines_application_runtime_and_recorder_snapshots() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
    )

    frame = presenter.poll()

    assert frame.view_model.workflow_state is WorkflowState.OFFLINE
    assert frame.view_model.runtime_state == "idle"
    assert frame.view_model.saved_episodes == 2
    presenter.close()


def test_presenter_drains_application_events_once() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
    )

    service.dispatch(Command.CONNECT)
    first = presenter.poll()
    second = presenter.poll()

    assert first.events
    assert second.events == ()
    presenter.close()


def test_presenter_close_unsubscribes_and_is_idempotent() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
    )

    presenter.close()
    presenter.close()

    assert presenter.closed


def test_closed_presenter_rejects_poll() -> None:
    service = ApplicationService()
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=_runtime,
        recorder_snapshot=_recorder,
    )
    presenter.close()

    with pytest.raises(RuntimeError, match="closed"):
        presenter.poll()
