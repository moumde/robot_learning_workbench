import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.command_port import CallbackCommandPort
from teleop.gello_cr.ui.main_window import OperatorMainWindow
from teleop.gello_cr.ui.presenter import OperatorUiPresenter


def test_six_pages_share_one_stop_and_navigation_does_not_actuate():
    app = QApplication.instance() or QApplication([])
    requests = []
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.REPLAY_RUNNING))
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: {"motion": {"source": "REPLAY"}},
        recorder_snapshot=lambda: {"episode_active": True, "buffered_frames": 6},
    )
    window = OperatorMainWindow(presenter, CallbackCommandPort(requests.append))
    window.show()
    try:
        assert window.navigation.count() == 6
        for index in range(6):
            window.navigation.setCurrentRow(index)
            app.processEvents()
            assert window.stop_motion_button.isVisible()
            assert window.estop_button.isVisible()
        assert requests == []
        assert len([b for b in window.findChildren(QPushButton) if b.text() == "停止运动"]) == 1
        assert "Recording RECORDING" in window.summary_status.text()
        window.stop_motion_button.click()
        assert requests[-1].command is Command.STOP_MOTION
    finally:
        presenter.close()
        window.close()


def test_offline_joint_planning_is_preview_only(tmp_path):
    from teleop.gello_cr.app.config_store import TeleopConfigStore
    from teleop.gello_cr.app.runtime import TeleopRuntime
    from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm

    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    runtime = TeleopRuntime(store, FakeRoArm(), FakeO6())
    try:
        result = runtime.point_motion.plan(
            {"kind": "joint", "start_joint_rad": [0] * 6, "target": [0.1] * 6, "speed_scale": 0.3}
        )
        assert result.success, result.errors
        assert runtime.motion.current_owner is None
        runtime.point_motion.save(result.trajectory.metadata.trajectory_id)
        assert result.trajectory.metadata.planning["offline_only"]
        from teleop.gello_cr.trajectory import ReplayOptions

        with pytest.raises(ValueError, match="Offline preview only"):
            runtime.trajectory_player.play(result.trajectory, ReplayOptions(hand_enabled=False))
        with pytest.raises(RuntimeError):
            runtime.point_motion.execute(result.trajectory.metadata.trajectory_id)
    finally:
        runtime.shutdown(close_devices=False)
