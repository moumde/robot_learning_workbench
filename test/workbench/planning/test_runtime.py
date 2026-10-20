import math
import threading
import time
from types import SimpleNamespace

import pytest

from core.workbench.app import ApplicationService
from core.workbench.app.config_store import TeleopConfigStore
from core.workbench.app.runtime import TeleopRuntime
from core.workbench.app.runtime_bindings import RuntimeCommandBindings
from core.workbench.core.state_machine import (
    Command,
    InvalidTransition,
    WorkflowState,
    WorkflowStateMachine,
)
from core.hardware.kinematics import NrcKinematicsProvider
from core.workbench.motion import MotionSource
from core.workbench.trajectory.planner import TcpPose
from test.workbench.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


class CartesianRobot(FakeRobot):
    def forward_kinematics(self, joints):
        q = [math.radians(v) for v in joints[:6]]
        return [v * 1000 for v in q[:3]] + q[3:] + [0]

    def inverse_kinematics(self, pose):
        q = [v / 1000 for v in pose[:3]] + list(pose[3:6])
        return [math.degrees(v) for v in q] + [0]

    def tcp_position(self):
        return self.forward_kinematics(self.joints)


@pytest.fixture
def setup(tmp_path):
    config = TeleopConfigStore(tmp_path / "config.json")
    config.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    config.data["planning"]["reached"].update(
        stable_samples=2, timeout_s=0.06, sample_period_s=0.01
    )
    engine = TeleopRuntime(config, FakeRoArm(), FakeO6())
    engine.attach_robot(CartesianRobot())
    recorder_state = {"buffered_frames": 0, "episode_active": False}
    service = ApplicationService(
        state_machine=WorkflowStateMachine(state=WorkflowState.ROBOT_ENABLED)
    )
    bindings = RuntimeCommandBindings(
        service,
        teleop_engine=engine,
        recorder=SimpleNamespace(),
        recording_snapshot=lambda: recorder_state,
    ).install()
    yield engine, service, bindings, recorder_state
    engine.shutdown(close_devices=False)


def wait_for(condition):
    deadline = time.monotonic() + 2
    while not condition():
        assert time.monotonic() < deadline
        threading.Event().wait(0.005)


def plan(service, kind="joint", target=None):
    result = service.dispatch(
        Command.PLAN_MOTION, {"kind": kind, "target": target or [0.0001] * 6, "speed_scale": 0.3}
    )
    assert result.value.success, result.value.errors
    return result.value.trajectory.metadata.trajectory_id


def test_plan_preview_save_and_execute_use_point_motion_chain(setup):
    engine, service, bindings, state = setup
    plan_id = plan(service, "tcp_linear")
    assert not engine.robot.servoj_targets
    assert engine.motion.current_owner is None
    snapshot = engine.point_motion.snapshot()
    assert snapshot["status"] == "READY" and snapshot["preview"]["planner_type"] == "tcp_linear"
    saved = service.dispatch(Command.SAVE_MOTION_PLAN, {"plan_id": plan_id}).value
    assert saved and engine.trajectory_store.load(plan_id).metadata.source == "planner"
    assert service.state is WorkflowState.ROBOT_ENABLED
    service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    engine.point_motion.thread.join(2)
    wait_for(lambda: service.state is WorkflowState.ROBOT_ENABLED)
    assert engine.point_motion.snapshot()["status"] == "REACHED"
    assert engine.robot.servoj_targets
    assert engine.motion.current_owner is None


def test_execute_rejects_changed_start_and_pending_dataset_before_any_command(setup):
    engine, service, _, state = setup
    plan_id = plan(service)
    state["buffered_frames"] = 3
    with pytest.raises(RuntimeError, match="Episode"):
        service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    state["buffered_frames"] = 0
    engine.robot.joints[0] = 10
    with pytest.raises(ValueError, match="起点"):
        engine.point_motion.execute(plan_id)
    assert not engine.robot.servoj_targets


def test_changed_constraints_and_failed_replan_invalidate_previous_plan(setup):
    engine, service, _, _ = setup
    plan_id = plan(service)
    engine.store.data["motion"] = {"workspace_limits_m": [(-0.1, 0.1)] * 3}
    with pytest.raises(ValueError, match="配置已改变"):
        engine.point_motion.execute(plan_id)
    result = engine.point_motion.plan({"kind": "tcp_ptp", "target": [1, 0, 0, 0, 0, 0]})
    assert not result.success
    with pytest.raises(ValueError, match="预览"):
        engine.point_motion.execute(plan_id)


def test_stop_during_reached_wait_never_reports_success(setup):
    engine, service, _, _ = setup
    plan_id = plan(service)
    engine.store.data["planning"]["reached"]["stable_samples"] = 10
    plan_id = plan(service)
    service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    wait_for(lambda: engine.point_motion.snapshot()["status"] == "WAITING_FOR_TARGET")
    service.dispatch(Command.STOP_POINT_MOTION)
    assert engine.point_motion.snapshot()["status"] == "STOPPED"
    assert engine.state == "idle"
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert engine.motion.current_owner is None


def test_home_priority_preempts_point_without_old_worker_stopping_home(setup):
    engine, service, bindings, _ = setup
    plan_id = plan(service, target=[0.1] * 6)
    service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    wait_for(lambda: bool(engine.robot.servoj_targets))
    home = engine.motion.acquire(MotionSource.HOME, allow_preempt=True)
    engine.point_motion.thread.join(2)
    assert engine.motion.current_owner is MotionSource.HOME
    assert engine.point_motion.snapshot()["status"] == "PREEMPTED"
    home.release()


def test_timeout_is_fault_when_commands_were_sent_but_actual_feedback_stays_still(setup):
    engine, service, _, _ = setup
    engine.robot.send_servoj = lambda joints: engine.robot.servoj_targets.append(joints) or True
    # Position differs by more than reached tolerance, with a short path duration.
    plan_id = plan(service, target=[0.01] * 6)
    service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    engine.point_motion.thread.join(2)
    wait_for(lambda: service.state is WorkflowState.FAULT)
    assert engine.point_motion.snapshot()["status"] == "TIMEOUT"
    assert engine.state == "fault"
    assert engine.motion.current_owner is None


def test_old_point_completion_does_not_finish_new_execution(setup):
    engine, service, bindings, _ = setup
    bindings._point_run = 2
    service._state_machine.state = WorkflowState.POINT_MOVE_RUNNING
    with pytest.raises(InvalidTransition):
        service.dispatch(Command.POINT_MOTION_COMPLETED, {"run": 1})
    assert service.state is WorkflowState.POINT_MOVE_RUNNING
    assert bindings._point_run == 2


def test_nrc_adapter_converts_only_native_joint_and_position_units():
    robot = CartesianRobot()
    provider = NrcKinematicsProvider(robot)
    pose = TcpPose((0.1, -0.2, 0.3), (0.2, -0.1, 1.0))
    assert provider.forward((0.1, -0.2, 0.3, 0.2, -0.1, 1)).vector() == pytest.approx(pose.vector())
    assert provider.inverse(pose, seed_joint_rad=(0,) * 6)[0] == pytest.approx(pose.vector())


def test_estop_during_execution_cannot_be_overwritten_by_completion(setup):
    engine, service, _, _ = setup
    plan_id = plan(service, target=[0.1] * 6)
    service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    wait_for(lambda: bool(engine.robot.servoj_targets))
    service.dispatch(Command.EMERGENCY_STOP, {"reason": "test stop"})
    engine.point_motion.thread.join(2)
    wait_for(lambda: not engine.point_motion.running)
    assert service.state is WorkflowState.ESTOP
    assert engine.state == "fault"
    assert engine.point_motion.snapshot()["status"] == "FAULT"
    assert engine.motion.current_owner is None


def test_home_requires_explicit_point_stop_and_preserves_home_lease(setup):
    engine, service, _, _ = setup
    engine.store.data["presets"]["HOME"] = {"robot_joints_deg": [0] * 7}
    engine.o6.connected = False
    plan_id = plan(service, target=[0.1] * 6)
    service.dispatch(Command.EXECUTE_PLAN, {"plan_id": plan_id})
    wait_for(lambda: bool(engine.robot.servoj_targets))
    producer = engine.point_motion.thread
    point_lease = engine.point_motion._lease
    with pytest.raises(RuntimeError, match="idle"):
        engine.return_home()
    assert producer.is_alive() and engine.point_motion.thread is producer
    assert point_lease.active
    assert engine.motion.current_owner is MotionSource.POINT_MOVE
    assert engine.state == "point_move"
    assert engine.robot.movej_targets == []
    service.dispatch(Command.STOP_POINT_MOTION)
    assert not engine.point_motion.running
    assert not point_lease.active
    assert engine.state == "idle"
    assert engine.point_motion.snapshot()["status"] == "STOPPED"
    original_movej = engine.robot.movej

    def home_movej(*args):
        assert not producer.is_alive()
        assert engine.state == "preset"
        assert engine.motion.current_owner is MotionSource.HOME
        original_movej(*args)

    engine.robot.movej = home_movej
    engine.return_home()
    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert engine.robot.movej_targets[-1] == [0] * 7
