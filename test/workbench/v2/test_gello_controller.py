from __future__ import annotations

from typing import Any

import pytest

from teleop.gello_cr.devices import gello as device_module
from core.workbench.core.contracts import JointState, MasterSnapshot


def _snapshot(gripper: float = 0.75) -> MasterSnapshot:
    return MasterSnapshot(
        timestamp=123.5,
        joints=JointState(
            timestamp=123.5,
            names=("j1", "j2", "j3", "j4", "j5", "j6"),
            positions_rad=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
        ),
        auxiliary={"gripper": gripper},
    )


class FakeGelloDevice:
    instances: list["FakeGelloDevice"] = []

    def __init__(self, config: Any) -> None:
        self.config = config
        self.io_alive = True
        self.connected = True
        self.error = ""
        self.closed = False
        self._snapshot = _snapshot()
        self.__class__.instances.append(self)

    def latest(self) -> MasterSnapshot:
        return self._snapshot

    def connect(self, timeout: float = 5.0) -> MasterSnapshot:
        assert timeout == pytest.approx(2.5)
        return self._snapshot

    def close(self) -> None:
        self.closed = True


def _controller(monkeypatch: pytest.MonkeyPatch) -> device_module.GelloController:
    FakeGelloDevice.instances.clear()
    monkeypatch.setattr(device_module, "GelloDevice", FakeGelloDevice)
    return device_module.GelloController(
        port="/dev/fake-gello",
        software_root="/tmp/fake-gello-root",
        joint_ids=(1, 2, 3, 4, 5, 6),
        joint_offsets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
        joint_signs=(1, 1, -1, 1, 1, 1),
        gripper_config=(7, 200.0, 147.0),
        baudrate=57600,
        feedback_hz=100.0,
        feedback_timeout_s=0.5,
    )


def test_gello_bridge_preserves_feedback_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(monkeypatch)
    feedback = controller.connect(timeout=2.5)

    assert feedback.timestamp == pytest.approx(123.5)
    assert feedback.joints_rad == pytest.approx((0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75))
    assert feedback.arm_joints_rad == pytest.approx((0.1, 0.2, 0.3, 0.4, 0.5, 0.6))
    assert feedback.gripper == pytest.approx(0.75)
    assert feedback.joints == pytest.approx((0.1, 0.2, 0.3, 0.4))


def test_gello_bridge_preserves_constructor_contract_and_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(monkeypatch)
    device = FakeGelloDevice.instances[-1]

    assert controller.master_type == "gello"
    assert controller.passive is True
    assert controller.port == "/dev/fake-gello"
    assert controller.software_root == "/tmp/fake-gello-root"
    assert controller.joint_ids == (1, 2, 3, 4, 5, 6)
    assert controller.feedback_hz == pytest.approx(100.0)
    assert controller.feedback_timeout_s == pytest.approx(0.5)

    assert device.config.port == controller.port
    assert device.config.joint_ids == controller.joint_ids
    assert device.config.joint_offsets == controller.joint_offsets
    assert device.config.joint_signs == controller.joint_signs
    assert device.config.gripper_config == (7, 200.0, 147.0)

    assert controller.latest() is not None
    assert controller.connected
    assert controller.io_alive
    assert controller.error == ""

    controller.close(hold=True)
    assert device.closed
