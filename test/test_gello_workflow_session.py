"""Shared trajectory tasks retain the parent's single hardware lifecycle."""

import sys
from types import SimpleNamespace

import pytest

from core import trajectory_bridge as bridge
from core.openpi.cr3_o6 import run_workflow as workflow

# isort: split

from gello_cr.trajectory import TrajectoryFrame, TrajectoryStore, make_trajectory


class WorkflowRobot:
    def __init__(self, *, fail_above=None):
        self.connected = self.servo_active = False
        self.servo = 1
        self.positions = [0.7] * 6
        self.calls = []
        self.sent = []
        self.fail_above = fail_above

    def connect(self):
        self.calls.append("connect")
        self.connected = True

    def power_on(self):
        self.calls.append("power_on")
        self.servo = 3

    def power_off(self):
        self.calls.append("power_off")
        self.servo = 1

    def open_servoj(self):
        self.calls.append("open_servoj")
        self.servo_active = True

    def close_servoj(self):
        self.calls.append("close_servoj")
        self.servo_active = False

    def disconnect(self):
        self.calls.append("disconnect")
        self.connected = False

    def get_servo_state(self):
        return self.servo

    def get_joint_positions(self):
        return self.positions

    def send_joint_positions(self, positions):
        if self.fail_above is not None and positions[0] > self.fail_above:
            self.fail_above = None
            raise RuntimeError("target rejected by fake controller")
        self.positions = list(positions)
        self.sent.append(tuple(positions))


@pytest.fixture
def setup_session(monkeypatch):
    # Only the constants are needed; no native SDK is imported by this test.
    monkeypatch.setitem(
        sys.modules,
        "vendor.nrc_interface.interface",
        SimpleNamespace(SERVO_STOPPED=0, SERVO_READY=1, SERVO_ERROR=2, SERVO_RUNNING=3),
    )
    now = [0.0]

    def wait(duration, stop):
        now[0] += max(duration, 0)
        return stop.is_set()

    real_play = bridge.play_in_existing_session

    def play(value, robot, hand=None, **kwargs):
        return real_play(value, robot, hand, clock=lambda: now[0], wait=wait, **kwargs)

    monkeypatch.setattr(workflow, "play_in_existing_session", play)

    def configure(robot):
        hardware = SimpleNamespace(
            hand=SimpleNamespace(model="O6", joint_count=6, transport="rs485"),
            nrc=SimpleNamespace(ip="offline-test"),
            source="fake-profile.toml",
            create_nrc_interface=lambda: robot,
        )
        monkeypatch.setattr(workflow, "load_hardware_config", lambda path: hardware)

    return configure


def named_task(root, target):
    value = make_trajectory(
        f"target {target}",
        [TrajectoryFrame(0, robot_joint_command=(target,) * 6)],
        hand_type=None,
        joint_mask=(True, False, False, False, False, False),
    )
    directory = TrajectoryStore(root).save(value)
    return {"type": "trajectory", "data_dir": str(directory), "hand_enabled": False}


def test_workflow_two_shared_tasks_open_and_close_exactly_one_session(tmp_path, setup_session):
    robot = WorkflowRobot()
    setup_session(robot)
    tasks = [named_task(tmp_path, target) for target in (0.1, 0.2)]
    workflow._validate_plan({"tasks": tasks})
    assert (
        workflow.run_workflow(tasks=tasks, config_path=None, policy_host="unused", policy_port=8000)
        == 0
    )
    assert robot.calls == [
        "connect",
        "power_on",
        "open_servoj",
        "close_servoj",
        "power_off",
        "disconnect",
    ]
    assert robot.sent[-1] == pytest.approx((0.2, 0.7, 0.7, 0.7, 0.7, 0.7))


def test_shared_task_failure_holds_then_stops_workflow_before_later_task(tmp_path, setup_session):
    robot = WorkflowRobot()
    setup_session(robot)
    tasks = [named_task(tmp_path, target) for target in (0.1, 0.2, 0.3)]
    # Trigger once only after task one reaches its target, during task two.
    original_send = robot.send_joint_positions
    reached_first = [False]

    def send(positions):
        if reached_first[0] and positions[0] > 0.15:
            robot.send_joint_positions = original_send
            raise RuntimeError("second task failed")
        original_send(positions)
        if abs(positions[0] - 0.1) < 1e-10:
            reached_first[0] = True

    robot.send_joint_positions = send
    assert (
        workflow.run_workflow(tasks=tasks, config_path=None, policy_host="unused", policy_port=8000)
        == 1
    )
    assert robot.positions[0] <= 0.15
    assert robot.calls.count("connect") == robot.calls.count("disconnect") == 1
    assert robot.calls.count("open_servoj") == robot.calls.count("close_servoj") == 1
