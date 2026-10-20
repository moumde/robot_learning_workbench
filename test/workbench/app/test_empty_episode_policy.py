from types import SimpleNamespace

import pytest

from core.workbench.app.service import ApplicationService
from core.workbench.app.runtime_bindings import RuntimeCommandBindings, RuntimeLifecycleCallbacks
from core.workbench.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from test.workbench.v2.test_operator_application import Factory
from core.workbench.bootstrap.operator_app import build_operator_application


def test_zero_frame_pending_episode_can_be_discarded_without_resetting_fault():
    episode = {"episode_active": False, "episode_pending": True, "buffered_frames": 0}
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.FAULT))
    service.set_recording_snapshot(lambda: episode)
    service.set_handler(Command.DISCARD_EPISODE, lambda payload: episode.update(episode_pending=False))
    assert service.can(Command.DISCARD_EPISODE)
    service.dispatch(Command.DISCARD_EPISODE)
    assert service.state is WorkflowState.FAULT
    assert not service.can(Command.DISCARD_EPISODE)


def test_zero_frame_pending_episode_blocks_reset_until_discarded():
    episode = {"episode_active": False, "episode_pending": True, "buffered_frames": 0}
    resets = []
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.FAULT))
    RuntimeCommandBindings(
        service, teleop_engine=None, recorder=None,
        lifecycle=RuntimeLifecycleCallbacks(reset_fault=lambda: resets.append(True)),
        recording_snapshot=lambda: episode,
    ).install()
    with pytest.raises(RuntimeError, match="Episode 未处理"):
        service.dispatch(Command.RESET_FAULT)
    assert not resets


def test_zero_frame_pending_episode_blocks_plan_execution():
    runs = []
    bindings = RuntimeCommandBindings(
        ApplicationService(),
        teleop_engine=SimpleNamespace(point_motion=SimpleNamespace(execute=lambda *a, **kw: runs.append(a))),
        recorder=None,
        recording_snapshot=lambda: {"episode_pending": True, "buffered_frames": 0},
    )
    with pytest.raises(RuntimeError, match="待处理 Episode"):
        bindings._execute_plan({"plan_id": "new-plan"})
    assert not runs


def test_empty_pending_exit_requires_discard_before_shutdown(tmp_path):
    factory = Factory()
    original = factory.runtime.recorder.snapshot
    factory.runtime.recorder.snapshot = lambda: {**original(), "episode_pending": True}
    app = build_operator_application(tmp_path, factory=factory)
    try:
        with pytest.raises(RuntimeError, match="暂无可保存帧"):
            app.close(save_pending=True)
        assert not app._closed_resources
        assert not app.backend.presenter.closed
    finally:
        factory.runtime.recorder.snapshot = original
        app.close()
