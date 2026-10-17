import threading
import time
from typing import Any

import pytest

from gello_cr.devices.gello import GelloConfig, GelloDevice


def _config() -> GelloConfig:
    return GelloConfig(
        port="/dev/fake-gello",
        joint_ids=(1, 2, 3, 4, 5, 6),
        joint_offsets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
        joint_signs=(1, 1, -1, 1, 1, 1),
        gripper_config=(7, 200.0, 147.0),
        feedback_hz=200.0,
        feedback_timeout_s=0.2,
    )


class FakeRobot:
    def __init__(self, states: list[tuple[float, ...]]) -> None:
        self.states = states
        self.index = 0
        self.closed = False
        self._lock = threading.Lock()

    def get_joint_state(self) -> tuple[float, ...]:
        with self._lock:
            state = self.states[min(self.index, len(self.states) - 1)]
            self.index += 1
            return state

    def get_joint_state_sample(self):
        return self.get_joint_state(), time.monotonic()

    def close(self) -> None:
        self.closed = True


def test_gello_snapshot_separates_arm_joints_and_gripper() -> None:
    created: dict[str, Any] = {}
    robot = FakeRobot([(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75)])

    def factory(**kwargs: Any) -> FakeRobot:
        created.update(kwargs)
        return robot

    device = GelloDevice(_config(), robot_factory=factory)
    try:
        snapshot = device.connect(timeout=0.5)

        assert snapshot.joints.names == ("j1", "j2", "j3", "j4", "j5", "j6")
        assert snapshot.joints.positions_rad == pytest.approx(
            (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
        )
        assert snapshot.auxiliary["gripper"] == pytest.approx(0.75)
        assert device.connected
        assert device.feedback_fresh()
    finally:
        device.close()

    assert robot.closed
    assert created["joint_ids"] == (1, 2, 3, 4, 5, 6)
    assert created["joint_signs"] == (1, 1, -1, 1, 1, 1)
    assert created["gripper_config"] == (7, 200.0, 147.0)
    assert created["real"] is True
    assert created["port"] == "/dev/fake-gello"


def test_gello_latest_updates_in_background() -> None:
    robot = FakeRobot(
        [
            (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 1.0),
        ]
    )
    device = GelloDevice(_config(), robot_factory=lambda **_: robot)
    try:
        device.connect(timeout=0.5)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            latest = device.latest()
            if latest and latest.joints.positions_rad[0] == 1.0:
                break
            time.sleep(0.005)

        latest = device.latest()
        assert latest is not None
        assert latest.joints.positions_rad == pytest.approx((1, 2, 3, 4, 5, 6))
        assert latest.auxiliary["gripper"] == pytest.approx(1.0)
    finally:
        device.close()


def test_gello_rejects_wrong_feedback_dimension() -> None:
    robot = FakeRobot([(0.0, 0.0, 0.0)])
    device = GelloDevice(_config(), robot_factory=lambda **_: robot)

    with pytest.raises(RuntimeError, match="must contain 7 values"):
        device.connect(timeout=0.5)

    assert robot.closed


def test_gello_rejects_non_finite_feedback() -> None:
    robot = FakeRobot([(0.0, 0.0, 0.0, 0.0, 0.0, float("nan"), 0.5)])
    device = GelloDevice(_config(), robot_factory=lambda **_: robot)

    with pytest.raises(RuntimeError, match="non-finite"):
        device.connect(timeout=0.5)

    assert robot.closed


def test_gello_config_rejects_duplicate_gripper_id() -> None:
    with pytest.raises(ValueError, match="gripper id"):
        GelloConfig(
            port="/dev/fake",
            joint_ids=(1, 2, 3, 4, 5, 6),
            joint_offsets=(0, 0, 0, 0, 0, 0),
            joint_signs=(1, 1, 1, 1, 1, 1),
            gripper_config=(6, 200.0, 147.0),
        )
