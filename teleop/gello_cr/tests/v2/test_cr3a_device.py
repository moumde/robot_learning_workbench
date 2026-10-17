from __future__ import annotations

import math
from typing import Any

import pytest

from gello_cr.devices.cr3a import Cr3aConfig, Cr3aDevice


class MoveCmd:
    pass


class FakeNrcApi:
    PosType_data = 99
    MoveCmd = MoveCmd

    def __init__(self) -> None:
        self.next_fds = [11, 22]
        self.connect_calls: list[tuple[str, str]] = []
        self.disconnect_calls: list[int] = []
        self.calls: list[tuple[Any, ...]] = []
        self.connection_status = {11: 0, 22: 0}
        self.state = 3
        self.mode = 2
        self.running_state = 0
        self.callback = None
        self.callback_result: Any = 0
        self.joint_position = [10.0, -20.0, 30.0, 40.0, -50.0, 60.0, 0.0]
        self.tcp_position = [400.0, -100.0, 250.0, 3.1, -0.2, 1.5, 0.0]

    @staticmethod
    def VectorDouble(size: int | None = None) -> list[float]:
        if size is None:
            return []
        return [0.0] * int(size)

    def connect_robot(self, ip: str, port: str) -> int:
        self.connect_calls.append((ip, port))
        return int(self.next_fds.pop(0))

    def disconnect_robot(self, fd: int) -> int:
        self.disconnect_calls.append(int(fd))
        return 0

    def get_connection_status(self, fd: int) -> int:
        return int(self.connection_status.get(int(fd), -2))

    def set_receive_error_or_warnning_message_callback(
        self,
        fd: int,
        callback: Any,
    ) -> int:
        self.calls.append(("register_callback", fd))
        self.callback = callback
        return self.callback_result

    def get_servo_state_robot(
        self,
        fd: int,
        robot_num: int,
        _status: int,
    ) -> tuple[int, int]:
        self.calls.append(("get_servo_state_robot", fd, robot_num))
        return 0, int(self.state)

    def get_current_mode_robot(
        self,
        fd: int,
        robot_num: int,
        _mode: int,
    ) -> tuple[int, int]:
        return 0, int(self.mode)

    def set_current_mode_robot(
        self,
        fd: int,
        robot_num: int,
        mode: int,
    ) -> int:
        self.mode = int(mode)
        return 0

    def get_robot_running_state_robot(
        self,
        fd: int,
        robot_num: int,
        _state: int,
    ) -> tuple[int, int]:
        return 0, int(self.running_state)

    def get_current_position(
        self,
        fd: int,
        coord: int,
        output: list[float],
    ) -> int:
        values = self.joint_position if int(coord) == 0 else self.tcp_position
        output.extend(values)
        return 0

    def enable_servo_position_motion_control(
        self,
        fd: int,
        enabled: bool,
    ) -> int:
        self.calls.append(("enable_servo", fd, enabled))
        return 0

    def open_servoJ(
        self,
        fd: int,
        vmax: list[float],
        amax: list[float],
        jmax: list[float],
    ) -> int:
        self.calls.append(
            ("open_servoJ", fd, tuple(vmax), tuple(amax), tuple(jmax))
        )
        return 0

    def stop_servoJ(self, fd: int) -> int:
        self.calls.append(("stop_servoJ", fd))
        return 0

    def set_servoJ_pos(
        self,
        fd: int,
        joints: list[float],
    ) -> int:
        self.calls.append(("set_servoJ_pos", fd, tuple(joints)))
        return 0

    def queue_motion_stop_not_power_off(self, fd: int) -> int:
        self.calls.append(("stop_motion", fd))
        return 0

    def clear_error_robot(self, fd: int, robot_num: int) -> int:
        self.state = 0
        return 0

    def set_servo_state_robot(
        self,
        fd: int,
        robot_num: int,
        state: int,
    ) -> int:
        self.state = int(state)
        return 0

    def set_servo_poweron_robot(self, fd: int, robot_num: int) -> int:
        self.state = 3
        return 0

    def set_servo_poweroff_robot(self, fd: int, robot_num: int) -> int:
        self.state = 1
        return 0


def _config() -> Cr3aConfig:
    return Cr3aConfig(
        ip="192.168.2.14",
        command_port=6001,
        servo_port=7000,
        robot_num=1,
        motion_mode="servoj",
        servoj_vmax=80.0,
        servoj_amax=195.0,
        servoj_jmax=120.0,
    )


def test_cr3a_connect_opens_both_ports_and_returns_si_snapshot() -> None:
    api = FakeNrcApi()
    device = Cr3aDevice(_config(), api=api)

    try:
        snapshot = device.connect(timeout=0.2)

        assert api.connect_calls == [
            ("192.168.2.14", "6001"),
            ("192.168.2.14", "7000"),
        ]
        assert device.command_fd == 11
        assert device.servo_fd == 22
        assert device.connected

        assert snapshot.joints.names == ("j1", "j2", "j3", "j4", "j5", "j6")
        assert snapshot.joints.positions_rad == pytest.approx(
            tuple(math.radians(value) for value in api.joint_position[:6])
        )
        assert snapshot.tcp is not None
        assert snapshot.tcp.xyz_m == pytest.approx((0.4, -0.1, 0.25))
        assert snapshot.tcp.rpy_rad == pytest.approx((3.1, -0.2, 1.5))
        assert snapshot.servo_state == 3
    finally:
        device.close()


def test_cr3a_partial_connection_failure_rolls_back_first_fd() -> None:
    api = FakeNrcApi()
    api.next_fds = [11, -1]
    device = Cr3aDevice(_config(), api=api)

    with pytest.raises(ConnectionError, match="7000"):
        device.connect(timeout=0.2)

    assert api.disconnect_calls == [11]
    assert device.session is None
    assert device.command_fd == -1
    assert device.servo_fd == -1


def test_cr3a_callback_is_retained_and_records_4098_warning() -> None:
    api = FakeNrcApi()
    events: list[tuple[str, str]] = []
    device = Cr3aDevice(
        _config(),
        api=api,
        event_callback=lambda level, message: events.append((level, message)),
    )

    try:
        device.connect(timeout=0.2)
        assert api.callback is not None
        assert device.session is not None

        api.callback("warning", "controller job busy", 4098)

        assert "4098" in device.session.controller_job_warning
        assert any("controller job busy" in message for _, message in events)
    finally:
        device.close()


def test_cr3a_callback_registration_failure_is_nonfatal() -> None:
    api = FakeNrcApi()
    api.callback_result = -1
    events: list[tuple[str, str]] = []
    device = Cr3aDevice(
        _config(),
        api=api,
        event_callback=lambda level, message: events.append((level, message)),
    )

    try:
        snapshot = device.connect(timeout=0.2)
        assert snapshot.servo_state == 3
        assert device.connected
        assert any(
            "callback registration failed" in message
            for _, message in events
        )
    finally:
        device.close()


def test_cr3a_servo_boundary_converts_rad_target_to_native_degrees() -> None:
    api = FakeNrcApi()
    device = Cr3aDevice(_config(), api=api)

    try:
        device.connect(timeout=0.2)
        device.start_joint_servo()
        device.send_joint_target(
            (
                math.radians(10.0),
                math.radians(-20.0),
                math.radians(30.0),
                math.radians(40.0),
                math.radians(-50.0),
                math.radians(60.0),
            )
        )

        assert any(
            call[0] == "open_servoJ"
            and call[1] == 22
            and call[2] == (80.0,) * 7
            and call[3] == (195.0,) * 7
            and call[4] == (120.0,) * 7
            for call in api.calls
        )
        servo_calls = [
            call for call in api.calls if call[0] == "set_servoJ_pos"
        ]
        assert len(servo_calls) == 1
        assert servo_calls[0][1] == 22
        assert servo_calls[0][2] == pytest.approx(
            (10.0, -20.0, 30.0, 40.0, -50.0, 60.0, 0.0)
        )
    finally:
        device.close()


def test_cr3a_rejects_non_six_dimensional_v2_joint_target() -> None:
    api = FakeNrcApi()
    device = Cr3aDevice(_config(), api=api)

    try:
        device.connect(timeout=0.2)
        with pytest.raises(ValueError, match="6 radians"):
            device.send_joint_target((0.0, 0.0, 0.0))
    finally:
        device.close()


def test_cr3a_close_stops_motion_then_disconnects_both_ports() -> None:
    api = FakeNrcApi()
    device = Cr3aDevice(_config(), api=api)
    device.connect(timeout=0.2)

    device.close()

    stop_index = next(
        index
        for index, call in enumerate(api.calls)
        if call[0] == "stop_motion"
    )
    assert stop_index >= 0
    assert api.disconnect_calls == [11, 22]
    assert not device.connected
    assert device.session is None
