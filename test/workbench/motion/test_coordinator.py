from __future__ import annotations

import threading

import pytest

from core.workbench.motion import (
    JointTarget,
    MotionBusyError,
    MotionCoordinator,
    MotionExecutor,
    MotionMode,
    MotionPreempted,
    MotionSafety,
    MotionSafetyError,
    MotionSource,
    TcpTarget,
)


class FakeRobot:
    def __init__(self) -> None:
        self.calls = []
        self.sent = True
        self.failure = None
        self.stop_failure = None
        self.reads = 0

    def send_servoj(self, target):
        if self.failure:
            raise self.failure
        self.calls.append(("servo", target))
        return self.sent

    def open_servoj(self, *args):
        self.calls.append(("open", *args))

    def movej(self, *args):
        self.calls.append(("movej", *args))

    def movel(self, *args):
        self.calls.append(("movel", *args))

    def stop_motion(self):
        self.calls.append(("stop",))
        if self.stop_failure:
            raise self.stop_failure

    def joint_position(self):
        self.reads += 1
        return [0.0] * 7


def setup_motion(config=None):
    robot = FakeRobot()
    safety = MotionSafety(lambda: config or {})
    return robot, MotionCoordinator(MotionExecutor(lambda: robot), safety)


def target(value=0.0, timestamp=1.0):
    return JointTarget((value,) * 6, timestamp)


def test_owner_priorities_require_explicit_preemption_and_reject_equal_priority():
    _, coordinator = setup_motion()
    lease = coordinator.acquire(MotionSource.TELEOP)

    for source, preempt in [
        (MotionSource.TELEOP, False),
        (MotionSource.POLICY, True),
        (MotionSource.HOME, False),
    ]:
        with pytest.raises(MotionBusyError):
            coordinator.acquire(source, allow_preempt=preempt)

    assert lease.active
    assert coordinator.current_owner is MotionSource.TELEOP


def test_home_revokes_previous_token_then_stops_before_granting_control():
    robot, coordinator = setup_motion()
    observations = []
    teleop = coordinator.acquire(
        MotionSource.TELEOP,
        on_cancel=lambda: observations.append(
            (teleop.active, coordinator.current_owner, list(robot.calls))
        ),
    )

    home = coordinator.acquire(MotionSource.HOME, allow_preempt=True)
    assert observations == [(False, None, [])]
    assert robot.calls == [("stop",)]
    assert home.active
    with pytest.raises(MotionPreempted):
        teleop.servo_joint(target())
    teleop.stop()
    teleop.release()
    assert robot.calls == [("stop",)]
    assert coordinator.current_owner is MotionSource.HOME
    with pytest.raises(MotionBusyError):
        coordinator.acquire(MotionSource.TELEOP, allow_preempt=True)


@pytest.mark.parametrize("operation", ["stop_current", "cancel_all"])
def test_stop_invalidates_owner_and_prevents_worker_sending_again(operation):
    robot, coordinator = setup_motion()
    cancelled = threading.Event()
    lease = coordinator.acquire(MotionSource.REPLAY, on_cancel=cancelled.set)
    lease.servo_joint(target())

    getattr(coordinator, operation)("operator stop")

    assert cancelled.is_set()
    assert not lease.active
    assert coordinator.current_owner is None
    assert coordinator.status.mode is MotionMode.IDLE
    assert not coordinator.status.running
    assert robot.calls[-1] == ("stop",)
    with pytest.raises(MotionPreempted):
        lease.check()
    with pytest.raises(MotionPreempted):
        lease.move_joint(target(), 10, 10)


def test_invalid_target_is_rejected_before_robot_and_error_revokes_lease():
    robot, coordinator = setup_motion()
    lease = coordinator.acquire(MotionSource.POLICY)

    with pytest.raises(MotionSafetyError):
        lease.servo_joint(target(float("nan")))

    assert all(call[0] != "servo" for call in robot.calls)
    assert not lease.active
    assert coordinator.status.error


def test_executor_error_revokes_ownership_and_retains_concrete_error():
    robot, coordinator = setup_motion()
    lease = coordinator.acquire(MotionSource.TELEOP)
    robot.failure = RuntimeError("servo connection lost")

    with pytest.raises(RuntimeError, match="servo connection lost"):
        lease.servo_joint(target())

    assert not lease.active
    assert coordinator.current_owner is None
    assert coordinator.status.error == "servo connection lost"
    assert robot.calls == [("stop",)]


def test_failed_preemption_stop_grants_no_new_owner():
    robot, coordinator = setup_motion()
    teleop = coordinator.acquire(MotionSource.TELEOP)
    robot.stop_failure = RuntimeError("stop failed")

    with pytest.raises(RuntimeError, match="stop failed"):
        coordinator.acquire(MotionSource.HOME, allow_preempt=True)

    assert not teleop.active
    assert coordinator.current_owner is None
    assert coordinator.status.error == "stop failed"


@pytest.mark.parametrize("preempt", [False, True])
def test_cancellation_callback_cannot_restart_motion_during_ownership_transition(preempt):
    robot, coordinator = setup_motion()
    replacements = []

    def restart_motion():
        try:
            replacement = coordinator.acquire(MotionSource.POLICY)
        except MotionBusyError:
            return
        replacements.append(replacement)
        replacement.servo_joint(target())

    coordinator.acquire(MotionSource.TELEOP, on_cancel=restart_motion)
    if preempt:
        coordinator.acquire(MotionSource.HOME, allow_preempt=True)
    else:
        coordinator.cancel_all()

    assert not replacements
    assert robot.calls == [("stop",)]
    assert coordinator.current_owner is (MotionSource.HOME if preempt else None)


def test_servo_baseline_is_read_once_and_unsent_target_does_not_advance_it():
    robot, coordinator = setup_motion({"motion": {"max_command_delta_rad": 0.1}})
    lease = coordinator.acquire(MotionSource.TELEOP)
    lease.open_servo(1, 2, 3)
    robot.sent = False
    assert lease.servo_joint(target(0.08)) is False
    assert coordinator.status.last_command_at is None
    robot.sent = True
    assert lease.servo_joint(target(-0.05, 2)) is True
    assert lease.servo_joint(target(-0.14, 3)) is True
    assert robot.reads == 1
    assert coordinator.status.mode is MotionMode.SERVO_JOINT
    assert coordinator.status.last_command_at is not None
    with pytest.raises(MotionSafetyError):
        lease.servo_joint(target(0.1, 4))


@pytest.mark.parametrize("open_servo", [False, True])
def test_velocity_starts_between_accepted_targets_instead_of_initial_robot_feedback(open_servo):
    robot, coordinator = setup_motion(
        {"motion": {"max_command_delta_rad": 0.2, "max_target_velocity_rad_s": 0.1}}
    )
    lease = coordinator.acquire(MotionSource.POLICY)
    if open_servo:
        lease.open_servo(1, 2, 3)
    robot.sent = False
    assert lease.servo_joint(target(0.15, 1.0)) is False
    robot.sent = True
    assert lease.servo_joint(target(0.1, 1.1)) is True

    with pytest.raises(MotionSafetyError, match="velocity"):
        lease.servo_joint(target(0.15, 1.2))


def test_new_lease_resets_baseline_and_planned_joint_move_accepts_distant_home():
    robot, coordinator = setup_motion({"motion": {"max_command_delta_rad": 0.1}})
    teleop = coordinator.acquire(MotionSource.TELEOP)
    teleop.open_servo(1, 2, 3)
    teleop.servo_joint(target(0.05))
    home = coordinator.acquire(MotionSource.HOME, allow_preempt=True)
    home.move_joint(target(2.0), 10, 20)
    assert coordinator.status.mode is MotionMode.JOINT_MOVE
    home.release()
    replay = coordinator.acquire(MotionSource.REPLAY)
    replay.open_servo(1, 2, 3)
    replay.servo_joint(target(-0.08))
    assert robot.reads == 2


@pytest.mark.parametrize("reopen", [False, True])
def test_planned_move_resets_servo_baseline_before_next_servo_target(reopen):
    robot, coordinator = setup_motion({"motion": {"max_command_delta_rad": 0.1}})
    lease = coordinator.acquire(MotionSource.HOME)
    lease.open_servo(1, 2, 3)
    lease.servo_joint(target(0.05))
    lease.move_joint(target(1.0), 10, 10)
    robot.joint_position = lambda: [57.29577951308232] * 6 + [0]
    if reopen:
        lease.open_servo(1, 2, 3)

    with pytest.raises(MotionSafetyError):
        lease.servo_joint(target(0.1))


def test_release_stops_owner_and_records_worker_error_then_tcp_uses_new_owner():
    robot, coordinator = setup_motion()
    lease = coordinator.acquire(MotionSource.HOME)
    lease.release(error="home timeout")
    assert coordinator.status.error == "home timeout"
    assert coordinator.current_owner is None
    assert robot.calls == [("stop",)]
    point = coordinator.acquire(MotionSource.POINT_MOVE)
    point.move_tcp(TcpTarget((0.1, 0.2, 0.3), (0, 0, 0), 2), 3, 4)
    assert coordinator.status.mode is MotionMode.TCP_MOVE
    assert coordinator.status.error is None


def test_lease_stop_keeps_ownership_for_settling_and_allows_servo_reopen():
    robot, coordinator = setup_motion()
    lease = coordinator.acquire(MotionSource.HOME)
    lease.open_servo(1, 2, 3)

    lease.stop()

    assert lease.active
    assert coordinator.current_owner is MotionSource.HOME
    assert coordinator.status.mode is MotionMode.IDLE
    with pytest.raises(MotionBusyError):
        coordinator.acquire(MotionSource.TELEOP)
    lease.open_servo(1, 2, 3)
    lease.servo_joint(target())
    assert robot.reads == 2


def test_command_and_preemption_are_serialized_across_threads():
    robot, coordinator = setup_motion()
    entered = threading.Event()
    finish = threading.Event()
    original_send = robot.send_servoj

    def delayed_send(value):
        entered.set()
        assert finish.wait(2)
        return original_send(value)

    robot.send_servoj = delayed_send
    teleop = coordinator.acquire(MotionSource.TELEOP)
    sender = threading.Thread(target=lambda: teleop.servo_joint(target()))
    owners = []
    sender.start()
    assert entered.wait(2)
    preemptor = threading.Thread(
        target=lambda: owners.append(coordinator.acquire(MotionSource.HOME, allow_preempt=True))
    )
    preemptor.start()
    finish.set()
    sender.join(2)
    preemptor.join(2)

    assert not sender.is_alive() and not preemptor.is_alive()
    assert robot.calls[0][0] == "servo"
    assert robot.calls[1] == ("stop",)
    assert owners[0].active


def test_status_snapshot_does_not_wait_for_sdk_send_and_stop_still_revokes_lease():
    robot, coordinator = setup_motion()
    entered, release, read = threading.Event(), threading.Event(), threading.Event()
    original = robot.send_servoj

    def send(value):
        entered.set()
        assert release.wait(2)
        return original(value)

    robot.send_servoj = send
    lease = coordinator.acquire(MotionSource.TELEOP)
    sender = threading.Thread(target=lambda: lease.servo_joint(target()))
    sender.start()
    assert entered.wait(1)
    snapshots = []

    def snapshot():
        snapshots.append(coordinator.status)
        read.set()

    reader = threading.Thread(target=snapshot)
    stopper = threading.Thread(target=lambda: coordinator.cancel_all("operator stop"))
    reader.start()
    stopper.start()
    try:
        assert read.wait(0.2), "GUI status waited for SDK send"
        assert snapshots[0].source is MotionSource.TELEOP
    finally:
        release.set()
        sender.join(2)
        reader.join(2)
        stopper.join(2)
    assert not lease.active
    assert coordinator.status.source is None
    assert robot.calls[-1] == ("stop",)
    with pytest.raises(MotionPreempted):
        lease.servo_joint(target())
