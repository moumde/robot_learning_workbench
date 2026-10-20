"""Exercise real teleop loops with deterministic, hardware-free device boundaries."""

from __future__ import annotations

import copy
import math
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from core.workbench.app.config_store import DEFAULT_CONFIG
from teleop.gello_cr.control import controller as controller_module
from teleop.gello_cr.control.controller import TeleopController, TeleopHooks
from teleop.gello_cr.devices.gello import GelloFeedback
from core.workbench.motion import MotionCoordinator, MotionExecutor, MotionSource


class Clock:
    value = 1000.0

    def monotonic(self):
        return self.value


class LoopStop(threading.Event):
    def __init__(self, clock):
        super().__init__()
        self.clock = clock

    def wait(self, timeout=None):
        if timeout is not None:
            self.clock.value += timeout
        return self.is_set()


class RotatingMaster:
    error = ""

    def __init__(self, clock):
        self.clock = clock
        self.sampled_at = clock.value
        self.joints = (0.0,) * 5 + (0.1,)

    def latest(self):
        return GelloFeedback(self.sampled_at, self.joints + (0.0,))


class Hand:
    error = ""
    fault = (0,) * 6

    def __init__(self, clock, stop):
        self.sampled_at = clock.value
        self.stop = stop
        self.targets = []

    def latest(self):
        return (0,) * 6, self.fault, self.sampled_at

    def set_target(self, target):
        self.targets.append(tuple(target))

    def hold_current(self):
        pass


class Robot:
    motion_mode = "servoj"
    on_read = None
    on_ik = None
    on_send = None

    def __init__(self, stop):
        self.stop = stop
        self.actual = [0.0] * 7
        self.targets = []
        self.stop_after = 1

    def joint_position(self):
        if self.on_read is not None:
            self.on_read()
        return list(self.actual)

    def tcp_position(self):
        return [0.0] * 7

    def inverse_kinematics(self, target):
        if self.on_ik is not None:
            self.on_ik()
        return [0.0] * 5 + [math.degrees(target[5]), 0.0]

    def open_servoj(self, *args):
        pass

    def stop_motion(self):
        pass

    def clear_movej_busy_if_stopped(self):
        return True

    def send_servoj(self, target):
        self.actual = list(target)
        self.targets.append(tuple(target))
        if self.on_send is not None:
            self.on_send()
        if self.stop_after is not None and len(self.targets) >= self.stop_after:
            self.stop.set()
        return True


class WristKinematics:
    """A wrist rotates at a fixed position, isolating pure orientation tracking."""

    def pose(self, joints):
        angle = joints[5]
        cosine, sine = math.cos(angle), math.sin(angle)
        pose = np.eye(4)
        pose[:3, :3] = ((cosine, -sine, 0), (sine, cosine, 0), (0, 0, 1))
        return pose


@pytest.fixture
def loop(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(controller_module, "time", clock)
    stop = LoopStop(clock)
    master = RotatingMaster(clock)
    hand = Hand(clock, stop)
    robot = Robot(stop)
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["gello"].update(startup_settle_s=0.0, joint_scale=1.0, feedback_timeout_s=0.5)
    config["o6"]["feedback_timeout_s"] = 0.5
    config["teleop"]["max_tcp_angular_speed_rad_s"] = 1000.0
    config["robot"].update(
        safety_max_command_step_rad=1.0,
        safety_max_command_speed_rad_s=100.0,
        safety_max_tracking_error_rad=1.0,
    )
    state = SimpleNamespace(value="following", error="", generation=0)

    def set_state(value, error):
        state.value, state.error = value, error

    shutdown = threading.Event()
    hooks = TeleopHooks(
        lock=threading.RLock(),
        stop=stop,
        shutdown=shutdown,
        generation=lambda: state.generation,
        state=lambda: state.value,
        set_state=set_state,
        event=lambda *args: None,
        reset_targets=lambda: None,
        publish_tcp_target=lambda target: None,
        publish_telemetry=lambda value: None,
    )
    motion = MotionCoordinator(MotionExecutor(lambda: robot))
    lease = motion.acquire(MotionSource.TELEOP, on_cancel=stop.set)
    lease.open_servo(1, 2, 3)
    controller = TeleopController(
        SimpleNamespace(data=config),
        master,
        hand,
        robot=lambda: robot,
        hooks=hooks,
        motion=motion,
    )

    def run(mode):
        origin = GelloFeedback(1000.0, (0.0,) * 7)
        config["gello"]["control_mode"] = mode
        if mode == "joint":
            controller._gello_follow_loop(origin, [0.0] * 7, 0, lease)
        else:
            controller._gello_xyz_j6_follow_loop(origin, [0.0] * 7, 0, lease, WristKinematics())

    return SimpleNamespace(
        clock=clock,
        stop=stop,
        master=master,
        hand=hand,
        robot=robot,
        config=config,
        state=state,
        shutdown=shutdown,
        run=run,
        controller=controller,
    )


def invalidate(loop, reason):
    if reason in ("master_stale", "hand_stale"):
        loop.clock.value += 0.6
        if reason == "hand_stale":
            loop.config["gello"]["feedback_timeout_s"] = 5.0
        else:
            loop.hand.sampled_at = loop.clock.value
    elif reason == "stop":
        loop.stop.set()
    elif reason == "generation":
        loop.state.generation += 1
    elif reason == "shutdown":
        loop.shutdown.set()
    elif reason == "master_error":
        loop.master.error = "master reader failed"
    elif reason == "hand_error":
        loop.hand.error = "hand reader failed"
    else:
        loop.hand.fault = (1, 0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("mode", "stage"), [("joint", "read"), ("tcp_6d", "read"), ("tcp_6d", "ik")]
)
@pytest.mark.parametrize(
    "reason",
    [
        "master_stale",
        "hand_stale",
        "stop",
        "generation",
        "shutdown",
        "master_error",
        "hand_error",
        "hand_fault",
    ],
)
def test_blocking_device_call_cannot_dispatch_after_inputs_become_unsafe(loop, mode, stage, reason):
    if reason == "hand_stale":
        loop.config["gello"]["feedback_timeout_s"] = 5.0
    setattr(loop.robot, "on_" + stage, lambda: invalidate(loop, reason))

    loop.run(mode)

    assert loop.robot.targets == []
    assert loop.hand.targets == []
    if reason.endswith("stale") or reason.endswith("error") or reason == "hand_fault":
        assert loop.state.value == "fault"


@pytest.mark.parametrize("mode", ["joint", "tcp_6d"])
@pytest.mark.parametrize("reason", ["master_stale", "hand_stale", "stop", "generation"])
def test_blocking_arm_submission_cannot_issue_a_later_hand_command(loop, mode, reason):
    if reason == "hand_stale":
        loop.config["gello"]["feedback_timeout_s"] = 5.0
    loop.robot.stop_after = None
    loop.robot.on_send = lambda: invalidate(loop, reason)
    original_set_target = loop.hand.set_target

    def record_then_end(target):
        original_set_target(target)
        loop.stop.set()

    loop.hand.set_target = record_then_end

    loop.run(mode)

    assert len(loop.robot.targets) == 1
    assert loop.hand.targets == []


def test_tcp_rotation_holds_its_target_until_master_returns_to_origin(loop):
    loop.robot.stop_after = 5

    def return_to_origin():
        if len(loop.robot.targets) == 3:
            loop.master.joints = (0.0,) * 6
            loop.master.sampled_at = loop.clock.value

    loop.robot.on_send = return_to_origin

    loop.run("tcp_6d")

    j6 = [target[5] for target in loop.robot.targets]
    assert j6 == pytest.approx([5.7295779513, 5.7295779513, 5.7295779513, 0.0, 0.0])


@pytest.mark.parametrize(
    ("mode", "low_latency"), [("joint", False), ("joint", True), ("tcp_6d", False)]
)
@pytest.mark.parametrize(
    "reason",
    [
        "master_stale",
        "hand_stale",
        "stop",
        "generation",
        "shutdown",
        "master_error",
        "hand_error",
        "hand_fault",
    ],
)
def test_movej_start_does_not_dispatch_when_late_feedback_read_invalidates_inputs(
    loop, monkeypatch, mode, low_latency, reason
):
    # start() must acquire a fresh lease with no previously sampled baseline.
    loop.controller.motion.cancel_all("test real start")
    loop.stop.clear()
    loop.robot.motion_mode = "movej"
    loop.robot.controller_job_warning = ""
    loop.config["gello"]["control_mode"] = mode
    loop.config["robot"]["movej_low_latency"] = low_latency
    if reason == "hand_stale":
        loop.config["gello"]["feedback_timeout_s"] = 5.0
    monkeypatch.setattr(controller_module, "GelloKinematics", lambda path: WristKinematics())
    reads = 0

    def invalidate_late_feedback():
        nonlocal reads
        reads += 1
        # The original path reads startup feedback, loop feedback, then a hidden
        # first-command baseline after the final guard. Invalidation there must
        # still prevent dispatch; the fixed path primes before entering the loop.
        if reads == 3:
            invalidate(loop, reason)

    loop.robot.on_read = invalidate_late_feedback

    loop.controller.start(loop.master.latest(), 0)
    loop.controller.thread.join(1.0)

    assert not loop.controller.running
    assert reads >= 3
    assert loop.robot.targets == []
    assert loop.hand.targets == []
