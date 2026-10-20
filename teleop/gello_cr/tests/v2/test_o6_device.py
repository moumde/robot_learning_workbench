from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from teleop.gello_cr.hardware.o6 import O6Config, O6Device


class FakeHand:
    def __init__(
        self,
        *,
        hand_id: int,
        modbus_port: str,
        baudrate: int,
        state: tuple[int, ...] = (10, 20, 30, 40, 50, 60),
        fault: tuple[int, ...] = (0, 0, 0, 0, 0, 0),
    ) -> None:
        self.hand_id = hand_id
        self.modbus_port = modbus_port
        self.baudrate = baudrate
        self.state = list(state)
        self.fault = list(fault)
        self.speed_calls: list[list[int]] = []
        self.torque_calls: list[list[int]] = []
        self.position_calls: list[list[int]] = []
        self.single_position_calls: list[tuple[int, int]] = []
        self.single_speed_calls: list[tuple[int, int]] = []
        self.single_torque_calls: list[tuple[int, int]] = []
        self.closed = False

    def get_state(self) -> list[int]:
        return list(self.state)

    def get_fault(self) -> list[int]:
        return list(self.fault)

    def set_speed(self, value: list[int]) -> None:
        self.speed_calls.append(list(value))

    def set_torque(self, value: list[int]) -> None:
        self.torque_calls.append(list(value))

    def set_joint_positions(self, value: list[int]) -> None:
        self.position_calls.append(list(value))
        self.state = list(value)

    def _set_pos(self, index: int, value: int) -> None:
        self.single_position_calls.append((index, int(value)))
        self.state[index] = int(value)

    def _set_speed(self, index: int, value: int) -> None:
        self.single_speed_calls.append((index, int(value)))

    def _set_torque(self, index: int, value: int) -> None:
        self.single_torque_calls.append((index, int(value)))

    def set_thumb_pitch(self, v: int) -> None: self._set_pos(0, v)
    def set_thumb_yaw(self, v: int) -> None: self._set_pos(1, v)
    def set_index_pitch(self, v: int) -> None: self._set_pos(2, v)
    def set_middle_pitch(self, v: int) -> None: self._set_pos(3, v)
    def set_ring_pitch(self, v: int) -> None: self._set_pos(4, v)
    def set_little_pitch(self, v: int) -> None: self._set_pos(5, v)

    def set_thumb_speed(self, v: int) -> None: self._set_speed(0, v)
    def set_thumb_yaw_speed(self, v: int) -> None: self._set_speed(1, v)
    def set_index_speed(self, v: int) -> None: self._set_speed(2, v)
    def set_middle_speed(self, v: int) -> None: self._set_speed(3, v)
    def set_ring_speed(self, v: int) -> None: self._set_speed(4, v)
    def set_little_speed(self, v: int) -> None: self._set_speed(5, v)

    def set_thumb_torque(self, v: int) -> None: self._set_torque(0, v)
    def set_thumb_yaw_torque(self, v: int) -> None: self._set_torque(1, v)
    def set_index_torque(self, v: int) -> None: self._set_torque(2, v)
    def set_middle_torque(self, v: int) -> None: self._set_torque(3, v)
    def set_ring_torque(self, v: int) -> None: self._set_torque(4, v)
    def set_little_torque(self, v: int) -> None: self._set_torque(5, v)

    def close(self) -> None:
        self.closed = True


def _config(port: Path) -> O6Config:
    return O6Config(
        port=str(port),
        sdk_root=None,
        hand_id=0x27,
        baudrate=115200,
        position_poll_s=0.01,
        fault_poll_s=0.02,
        loop_sleep_s=0.001,
    )


def _wait(predicate: Any, timeout: float = 0.5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("condition did not become true before timeout")


def test_o6_connect_returns_typed_snapshot(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB0"
    port.touch()
    hand = FakeHand(hand_id=0x27, modbus_port=str(port), baudrate=115200)

    device = O6Device(_config(port), hand_factory=lambda **kwargs: hand)
    try:
        snapshot = device.connect(timeout=0.5)
        assert snapshot.positions == (10, 20, 30, 40, 50, 60)
        assert snapshot.faults == (0, 0, 0, 0, 0, 0)
        assert device.connected
        assert device.phase == "运行中"
        assert device.latest_position_timestamp > 0
    finally:
        device.close()

    assert hand.closed


def test_o6_profile_and_target_are_serialized_on_worker(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB0"
    port.touch()
    hand = FakeHand(hand_id=0x27, modbus_port=str(port), baudrate=115200)
    device = O6Device(_config(port), hand_factory=lambda **kwargs: hand)

    try:
        device.connect(timeout=0.5)
        device.set_profile((1, 2, 3, 4, 5, 6), (11, 12, 13, 14, 15, 16))
        device.set_target((90, 91, 92, 93, 94, 95))

        _wait(lambda: bool(hand.position_calls))
        assert hand.speed_calls[-1] == [1, 2, 3, 4, 5, 6]
        assert hand.torque_calls[-1] == [11, 12, 13, 14, 15, 16]
        assert hand.position_calls[-1] == [90, 91, 92, 93, 94, 95]
        assert device.last_sent_target == (90, 91, 92, 93, 94, 95)
    finally:
        device.close()


def test_o6_target_validation_rejects_out_of_range(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB0"
    port.touch()
    device = O6Device(_config(port), hand_factory=lambda **kwargs: None)

    with pytest.raises(ValueError, match="0..255"):
        device.set_target((0, 1, 2, 3, 4, 300))


def test_o6_wait_until_position_observes_fault(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB0"
    port.touch()
    hand = FakeHand(
        hand_id=0x27,
        modbus_port=str(port),
        baudrate=115200,
        fault=(0, 0, 2, 0, 0, 0),
    )
    device = O6Device(_config(port), hand_factory=lambda **kwargs: hand)

    try:
        device.connect(timeout=0.5)
        assert not device.wait_until_position(
            (10, 20, 30, 40, 50, 60),
            timeout=0.1,
        )
    finally:
        device.close()


def test_o6_recovery_preserves_current_target_before_restoring_power(
    tmp_path: Path,
) -> None:
    port = tmp_path / "ttyUSB0"
    port.touch()
    hand = FakeHand(
        hand_id=0x27,
        modbus_port=str(port),
        baudrate=115200,
        fault=(0, 1, 0, 0, 0, 0),
    )
    device = O6Device(_config(port), hand_factory=lambda **kwargs: hand)

    try:
        device.connect(timeout=0.5)
        result = device.recover_motor(2, speed=22, torque=33, timeout=1.0)

        assert hand.single_position_calls[0] == (1, 20)
        assert hand.single_speed_calls[0] == (1, 22)
        assert hand.single_torque_calls[0] == (1, 33)
        assert result["motor_number"] == 2
        assert result["fault_before"] == (0, 1, 0, 0, 0, 0)
        assert device.last_sent_target == tuple(hand.state)
    finally:
        device.close()


def test_o6_recovery_rejects_unsafe_fault_code(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB0"
    port.touch()
    hand = FakeHand(
        hand_id=0x27,
        modbus_port=str(port),
        baudrate=115200,
        fault=(0, 0, 3, 0, 0, 0),
    )
    device = O6Device(_config(port), hand_factory=lambda **kwargs: hand)

    try:
        device.connect(timeout=0.5)
        with pytest.raises(RuntimeError, match="禁止软件重新上力"):
            device.recover_motor(3, speed=20, torque=30, timeout=1.0)
        assert hand.single_torque_calls == []
    finally:
        device.close()


@pytest.mark.parametrize("error", ["", "O6 communication failed"])
def test_o6_wait_does_not_accept_cached_goal_without_a_new_position_read(tmp_path, error):
    device = O6Device(_config(tmp_path / "fake"))
    target = (10, 20, 30, 40, 50, 60)
    device._set_snapshot(positions=target, faults=(0,) * 6, position_read=True)
    device._error = error

    assert not device.wait_until_position(target, timeout=0.01)


def test_o6_wait_accepts_new_physical_position_feedback(tmp_path):
    port = tmp_path / "ttyUSB0"
    port.touch()
    hand = FakeHand(hand_id=0x27, modbus_port=str(port), baudrate=115200)
    device = O6Device(_config(port), hand_factory=lambda **kwargs: hand)
    try:
        device.connect(timeout=0.5)
        target = (70,) * 6
        device.set_target(target)
        assert device.wait_until_position(target, timeout=0.5)
    finally:
        device.close()
