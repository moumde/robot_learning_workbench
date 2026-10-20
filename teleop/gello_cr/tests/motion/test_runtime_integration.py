"""Exercise runtime fault handling across real motion ownership transitions."""

from __future__ import annotations

import math
import threading
from types import SimpleNamespace

import pytest

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.runtime import TeleopRuntime
from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.motion import MotionSource
from teleop.gello_cr.motion.policy_adapter import PolicyRuntimeView
from teleop.gello_cr.trajectory import ReplayOptions, TrajectoryFrame, make_trajectory
from teleop.gello_cr.ui.backend import RuntimeFaultSnapshotBridge
from teleop.gello_cr.tests.fakes.runtime import FakeGello, FakeO6, FakeRoArm, FakeRobot


class HoldingHand(FakeO6):
    def __init__(self):
        super().__init__()
        self.hold_count = 0
        self.target_sent = threading.Event()

    def set_target(self, target):
        super().set_target(target)
        self.target_sent.set()

    def hold_current(self):
        self.hold_count += 1
        super().hold_current()


class FailingRobot(FakeRobot):
    def send_servoj(self, joints):
        raise RuntimeError("ServoJ SDK failure")

    def movej(self, joints, velocity, acc, dec):
        raise RuntimeError("MoveJ SDK failure")


class FailingReplayRobot(FailingRobot):
    def send_servoj(self, joints):
        if self.servoj_targets:
            super().send_servoj(joints)
        FakeRobot.send_servoj(self, joints)


class BlockedReadRobot(FakeRobot):
    def __init__(self):
        super().__init__()
        self.read_started = threading.Event()
        self.finish_read = threading.Event()

    def joint_position(self):
        self.read_started.set()
        if not self.finish_read.wait(2):
            raise TimeoutError("test did not release robot feedback")
        raise RuntimeError("old producer feedback failed")


@pytest.fixture
def runtime_factory(tmp_path):
    runtimes = []

    def build(robot):
        store = TeleopConfigStore(tmp_path / "teleop.json")
        store.data["trajectory"] = {"root": str(tmp_path / "trajectories")}
        store.data["replay"]["mode_switch_settle_s"] = 0.0
        engine = TeleopRuntime(store, FakeRoArm(), HoldingHand())
        engine.attach_robot(robot)
        runtimes.append(engine)
        return engine

    yield build
    for engine in runtimes:
        engine.shutdown(close_devices=False)


@pytest.mark.parametrize(
    ("delta", "duration", "time_scale"),
    [
        (1.0, 0.1, 1.0),
        (math.radians(80.0), 1.0, 2.0),
    ],
)
def test_replay_rejects_speed_above_configured_limit_before_motion(
    runtime_factory,
    delta,
    duration,
    time_scale,
):
    engine = runtime_factory(FakeRobot())
    value = make_trajectory(
        "too fast",
        [
            TrajectoryFrame(0.0, robot_joint_command=(0.0,) * 6),
            TrajectoryFrame(duration, robot_joint_command=(delta,) * 6),
        ],
    )
    engine.trajectory_store.save(value)

    with pytest.raises(ValueError, match="speed"):
        engine.replay_trajectory(
            value.metadata.trajectory_id, ReplayOptions(hand_enabled=False, time_scale=time_scale)
        )

    assert engine.state == "idle"
    assert engine.motion.current_owner is None
    assert not engine.robot.servoj_open
    assert not engine.robot.servoj_targets


def test_service_stop_replay_does_not_wait_on_its_completion_callback(runtime_factory):
    engine = runtime_factory(FakeRobot())
    value = make_trajectory(
        "stop me",
        [
            TrajectoryFrame(0.0, robot_joint_command=(0.0,) * 6, hand_command=(200.0,) * 6),
            TrajectoryFrame(10.0, robot_joint_command=(0.1,) * 6, hand_command=(190.0,) * 6),
        ],
    )
    engine.trajectory_store.save(value)
    service = ApplicationService(
        state_machine=WorkflowStateMachine(state=WorkflowState.ROBOT_ENABLED)
    )
    RuntimeCommandBindings(service, teleop_engine=engine, recorder=None).install()
    service.dispatch(Command.REPLAY_TRAJECTORY, {"trajectory_id": value.metadata.trajectory_id})
    assert engine.o6.target_sent.wait(1)

    service.dispatch(Command.STOP_TRAJECTORY_REPLAY)

    assert not engine._replay_thread.is_alive()
    assert engine.state == "idle"
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert engine.motion.current_owner is None


def test_fast_replay_completion_returns_workflow_to_enabled(runtime_factory):
    engine = runtime_factory(FakeRobot())
    value = make_trajectory(
        "one frame",
        [
            TrajectoryFrame(0.0, robot_joint_command=(0.0,) * 6, hand_command=(200.0,) * 6),
        ],
    )
    engine.trajectory_store.save(value)
    service = ApplicationService(
        state_machine=WorkflowStateMachine(state=WorkflowState.ROBOT_ENABLED)
    )
    completed = threading.Event()
    service.subscribe(
        lambda event: (
            completed.set()
            if event.command is Command.TRAJECTORY_COMPLETED and event.kind == "command_completed"
            else None
        )
    )
    RuntimeCommandBindings(service, teleop_engine=engine, recorder=None).install()

    service.dispatch(Command.REPLAY_TRAJECTORY, {"trajectory_id": value.metadata.trajectory_id})

    assert completed.wait(1)
    engine._replay_thread.join(1)
    assert not engine.replaying
    assert engine.state == "idle"
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_replay_speed_check_ignores_unselected_recorded_joints(runtime_factory):
    engine = runtime_factory(FakeRobot())
    value = make_trajectory(
        "wrist",
        [
            TrajectoryFrame(0.0, robot_joint_command=(0.0,) * 6),
            TrajectoryFrame(0.1, robot_joint_command=(1.0, 0.0, 0.0, 0.0, 0.0, 0.01)),
        ],
        joint_mask=(False,) * 5 + (True,),
    )
    engine.trajectory_store.save(value)
    engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions(hand_enabled=False))
    engine._replay_thread.join(1)

    assert engine.state == "idle"
    assert engine.robot.servoj_targets[-1][0] == 0.0
    assert engine.robot.servoj_targets[-1][5] == pytest.approx(math.degrees(0.01))


def write_replay(engine):
    value = make_trajectory(
        "demo",
        [
            TrajectoryFrame(0.0, robot_joint_state=(0.0,) * 6, hand_state=(200.0,) * 6),
            TrajectoryFrame(
                0.05, robot_joint_state=(math.radians(0.1),) * 6, hand_state=(190.0,) * 6
            ),
        ],
    )
    engine.trajectory_store.save(value)
    return value.metadata.trajectory_id


def test_policy_sdk_failure_enters_runtime_and_workflow_fault_and_holds_hand(runtime_factory):
    engine = runtime_factory(FailingRobot())
    view = PolicyRuntimeView(
        SimpleNamespace(
            teleop_engine=engine,
            store=engine.store,
            gello_controller=FakeGello(),
            master_controller=engine.roarm,
            o6_controller=engine.o6,
            sample_source=None,
        )
    )

    def run(*, stop_event):
        view.o6_controller.set_target([100] * 6)
        view.robot.send_servoj([0.0] * 7)

    def request_stop():
        view.robot.stop_motion()
        view.o6_controller.hold_current()

    controller = SimpleNamespace(
        robot=SimpleNamespace(start_control=lambda: view.robot.open_servoj(80, 200, 150)),
        run=run,
        request_stop=request_stop,
        stop=request_stop,
        snapshot=lambda: {"phase": "stopped"},
    )
    engine.start_external_control(controller, engine.stop_generation, motion_view=view)
    engine._follow_thread.join(1)
    assert not engine._follow_thread.is_alive()

    service = ApplicationService()
    snapshot = RuntimeFaultSnapshotBridge(service, engine).snapshot()
    assert snapshot["state"] == "fault"
    assert service.state is WorkflowState.FAULT
    assert "ServoJ SDK failure" in snapshot["error"]
    assert snapshot["motion"]["source"] is None
    assert engine.o6.hold_count > 0


def test_replay_arm_failure_holds_hand_after_coordinator_revokes_lease(runtime_factory):
    engine = runtime_factory(FailingReplayRobot())
    trajectory_id = write_replay(engine)

    engine.replay_trajectory(trajectory_id, ReplayOptions())
    engine._replay_thread.join(1)

    assert not engine._replay_thread.is_alive()
    assert engine.state == "fault"
    assert "ServoJ SDK failure" in engine.last_error
    assert engine.motion.current_owner is None
    assert engine.o6.targets[0] == (200,) * 6
    assert engine.o6.hold_count > 0


def test_stop_gello_follow_holds_hand_after_revoking_motion_lease(runtime_factory):
    engine = runtime_factory(FakeRobot())
    engine.roarm.connected = False
    engine.set_master(FakeGello())
    engine.store.data["gello"]["startup_settle_s"] = 0.0
    engine.start_follow()
    assert engine.o6.target_sent.wait(1)
    assert engine.motion.current_owner is MotionSource.TELEOP
    assert engine.robot.servoj_targets[0] == pytest.approx([0.0] * 7)
    holds_before_stop = engine.o6.hold_count

    engine.stop_follow()

    assert engine.motion.current_owner is None
    assert engine.state == "idle"
    assert engine.o6.hold_count > holds_before_stop


def test_preempted_read_failure_does_not_replace_home_state_or_hand_target(runtime_factory):
    robot = BlockedReadRobot()
    engine = runtime_factory(robot)
    trajectory_id = write_replay(engine)
    engine.replay_trajectory(trajectory_id, ReplayOptions())
    thread = engine._replay_thread

    try:
        assert robot.read_started.wait(1)
        # HOME claims its application state before revoking the previous owner.
        engine._set_state("recovering")
        engine.motion.acquire(MotionSource.HOME, allow_preempt=True)
        engine.o6.set_target([30] * 6)
        targets_before_old_exit = list(engine.o6.targets)
        robot.finish_read.set()
        thread.join(1)

        assert not thread.is_alive()
        assert engine.motion.current_owner is MotionSource.HOME
        assert engine.state == "recovering"
        assert engine.o6.targets == targets_before_old_exit
    finally:
        robot.finish_read.set()
        thread.join(1)
        engine.motion.cancel_all("test finished")
