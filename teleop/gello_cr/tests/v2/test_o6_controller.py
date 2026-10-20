from __future__ import annotations

import queue
from pathlib import Path
from typing import Any

import pytest

from teleop.gello_cr.hardware import o6 as device_module
from teleop.gello_cr.core.contracts import HandSnapshot


class FakeO6Device:
    instances: list["FakeO6Device"] = []

    def __init__(self, config: Any) -> None:
        self.config = config
        self.connected = True
        self.error = ""
        self.phase = "运行中"
        self.latest_position_timestamp = 123.0
        self.last_sent_target = (1, 2, 3, 4, 5, 6)
        self.closed = False
        self.profile_calls = []
        self.target_calls = []
        self.recover_calls = []
        self.wait_calls = []
        self._thread = None
        self._recovery_requests = queue.Queue()
        self._snapshot = HandSnapshot(
            timestamp=124.0,
            positions=(10, 20, 30, 40, 50, 60),
            faults=(0, 0, 0, 0, 0, 0),
        )
        self.processed = None
        self.__class__.instances.append(self)

    def latest(self) -> HandSnapshot:
        return self._snapshot

    def connect(self, timeout: float = 10.0) -> HandSnapshot:
        assert timeout == pytest.approx(2.5)
        return self._snapshot

    def set_profile(self, speed: Any, torque: Any) -> None:
        self.profile_calls.append((tuple(speed), tuple(torque)))

    def set_target(self, target: Any) -> None:
        self.target_calls.append(tuple(target))

    def hold_current(self) -> None:
        self.target_calls.append(self._snapshot.positions)

    def recover_motor(
        self,
        motor_number: int,
        speed: Any,
        torque: Any,
        timeout: float = 4.0,
        stop_event: Any = None,
    ) -> dict[str, Any]:
        self.recover_calls.append((motor_number, speed, torque, timeout, stop_event))
        return {"motor_number": motor_number}

    def wait_until_position(
        self,
        target: Any,
        tolerance: int = 6,
        timeout: float = 15.0,
        stop_event: Any = None,
    ) -> bool:
        self.wait_calls.append((tuple(target), tolerance, timeout, stop_event))
        return True

    def close(self) -> None:
        self.closed = True

    def _process_recovery(self, hand: Any, request: Any) -> None:
        self.processed = (hand, request)


def _controller(monkeypatch: pytest.MonkeyPatch) -> device_module.O6Controller:
    FakeO6Device.instances.clear()
    monkeypatch.setattr(device_module, "O6Device", FakeO6Device)
    return device_module.O6Controller(
        "/dev/fake-o6",
        Path("/tmp/fake-linker-sdk"),
        hand_id=0x27,
        baudrate=115200,
    )


def test_o6_bridge_preserves_feedback_and_constructor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(monkeypatch)
    device = FakeO6Device.instances[-1]

    assert controller.port == "/dev/fake-o6"
    assert controller.sdk_root == "/tmp/fake-linker-sdk"
    assert controller.hand_id == 0x27
    assert controller.baudrate == 115200

    assert device.config.port == controller.port
    assert device.config.sdk_root == controller.sdk_root
    assert device.config.hand_id == controller.hand_id
    assert device.config.baudrate == controller.baudrate

    assert controller.connect(timeout=2.5) == (10, 20, 30, 40, 50, 60)
    position, fault, timestamp = controller.latest()
    assert position == (10, 20, 30, 40, 50, 60)
    assert fault == (0, 0, 0, 0, 0, 0)
    assert timestamp == pytest.approx(123.0)
    assert controller.last_sent_target == (1, 2, 3, 4, 5, 6)
    assert controller.connected
    assert controller.error == ""
    assert controller.phase == "运行中"


def test_o6_bridge_delegates_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(monkeypatch)
    device = FakeO6Device.instances[-1]

    controller.set_profile((1, 2, 3, 4, 5, 6), (11, 12, 13, 14, 15, 16))
    controller.set_target((21, 22, 23, 24, 25, 26))
    controller.hold_current()
    assert controller.recover_motor(2, 20, 30, timeout=1.5) == {"motor_number": 2}
    assert controller.wait_until_position(
        (10, 20, 30, 40, 50, 60),
        tolerance=5,
        timeout=2.0,
    )

    assert device.profile_calls[-1] == (
        (1, 2, 3, 4, 5, 6),
        (11, 12, 13, 14, 15, 16),
    )
    assert device.target_calls[0] == (21, 22, 23, 24, 25, 26)
    assert device.target_calls[1] == (10, 20, 30, 40, 50, 60)
    assert device.recover_calls[-1][:4] == (2, 20, 30, 1.5)
    assert device.wait_calls[-1][:3] == (
        (10, 20, 30, 40, 50, 60),
        5,
        2.0,
    )

    controller.close()
    assert device.closed
