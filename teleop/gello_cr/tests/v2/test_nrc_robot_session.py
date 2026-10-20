from __future__ import annotations

from typing import Any

import pytest

from gello_cr.devices.nrc_robot import NrcRobotSession


class MoveCmd:
    pass


class FakeNrcApi:
    PosType_data = 99
    MoveCmd = MoveCmd

    def __init__(self, state: int = 0) -> None:
        self.state = int(state)
        self.mode = 0
        self.calls: list[tuple[Any, ...]] = []
        self.clear_state_after_call = 3
        self.poweron_result = 0
        self.connection_status = {11: 0, 22: 0}
        self.running_states = [0]
        self.joint_position = [0.0] * 7
        self.tcp_position = [0.0] * 7

    @staticmethod
    def VectorDouble(size: int | None = None) -> list[float]:
        if size is None:
            return []
        return [0.0] * int(size)

    def get_connection_status(self, socket_fd: int) -> int:
        self.calls.append(("get_connection_status", socket_fd))
        return self.connection_status[socket_fd]

    def get_servo_state_robot(
        self,
        socket_fd: int,
        robot_num: int,
        _status: int,
    ) -> tuple[int, int]:
        self.calls.append(
            ("get_servo_state_robot", socket_fd, robot_num)
        )
        return (0, self.state)

    def get_current_mode_robot(
        self,
        socket_fd: int,
        robot_num: int,
        _mode: int,
    ) -> tuple[int, int]:
        self.calls.append(
            ("get_current_mode_robot", socket_fd, robot_num)
        )
        return (0, self.mode)

    def set_current_mode_robot(
        self,
        socket_fd: int,
        robot_num: int,
        mode: int,
    ) -> int:
        self.calls.append(
            ("set_current_mode_robot", socket_fd, robot_num, mode)
        )
        self.mode = int(mode)
        return 0

    def get_robot_running_state_robot(
        self,
        socket_fd: int,
        robot_num: int,
        _status: int,
    ) -> tuple[int, int]:
        self.calls.append(
            (
                "get_robot_running_state_robot",
                socket_fd,
                robot_num,
            )
        )
        if len(self.running_states) > 1:
            state = self.running_states.pop(0)
        else:
            state = self.running_states[0]
        return (0, state)

    def clear_error_robot(
        self,
        socket_fd: int,
        robot_num: int,
    ) -> int:
        self.calls.append(
            ("clear_error_robot", socket_fd, robot_num)
        )
        if self.state == 2:
            self.state = int(self.clear_state_after_call)
        return 0

    def set_servo_state_robot(
        self,
        socket_fd: int,
        robot_num: int,
        state: int,
    ) -> int:
        self.calls.append(
            (
                "set_servo_state_robot",
                socket_fd,
                robot_num,
                state,
            )
        )
        if self.state not in (0, 1) or int(state) != 1:
            return -4
        self.state = 1
        return 0

    def set_servo_poweron_robot(
        self,
        socket_fd: int,
        robot_num: int,
    ) -> int:
        self.calls.append(
            ("set_servo_poweron_robot", socket_fd, robot_num)
        )
        if self.poweron_result != 0:
            return self.poweron_result
        if self.state != 1:
            return -4
        self.state = 3
        return 0

    def set_servo_poweroff_robot(
        self,
        socket_fd: int,
        robot_num: int,
    ) -> int:
        self.calls.append(
            ("set_servo_poweroff_robot", socket_fd, robot_num)
        )
        if self.state != 3:
            return -4
        self.state = 1
        return 0

    def get_current_position(
        self,
        socket_fd: int,
        coord: int,
        output: list[float],
    ) -> int:
        self.calls.append(
            ("get_current_position", socket_fd, coord)
        )
        values = (
            self.joint_position
            if int(coord) == 0
            else self.tcp_position
        )
        output.extend(values)
        return 0

    def enable_servo_position_motion_control(
        self,
        servo_fd: int,
        enabled: bool,
    ) -> int:
        self.calls.append(
            (
                "enable_servo_position_motion_control",
                servo_fd,
                enabled,
            )
        )
        return 0

    def open_servoJ(
        self,
        servo_fd: int,
        vmax: list[float],
        amax: list[float],
        jmax: list[float],
    ) -> int:
        self.calls.append(
            (
                "open_servoJ",
                servo_fd,
                tuple(vmax),
                tuple(amax),
                tuple(jmax),
            )
        )
        return 0

    def stop_servoJ(self, servo_fd: int) -> int:
        self.calls.append(("stop_servoJ", servo_fd))
        return 0

    def set_servoJ_pos(
        self,
        servo_fd: int,
        joints: list[float],
    ) -> int:
        self.calls.append(
            ("set_servoJ_pos", servo_fd, tuple(joints))
        )
        return 0

    def robot_movej(
        self,
        command_fd: int,
        command: MoveCmd,
    ) -> int:
        self.calls.append(
            (
                "robot_movej",
                command_fd,
                tuple(command.targetPosValue),
                command.coord,
            )
        )
        return 0

    def robot_movel(
        self,
        command_fd: int,
        command: MoveCmd,
    ) -> int:
        self.calls.append(
            (
                "robot_movel",
                command_fd,
                tuple(command.targetPosValue),
                command.coord,
            )
        )
        return 0

    def queue_motion_stop_not_power_off(
        self,
        command_fd: int,
    ) -> int:
        self.calls.append(
            ("queue_motion_stop_not_power_off", command_fd)
        )
        return 0


def _session(
    api: FakeNrcApi,
    *,
    motion_mode: str = "servoj",
) -> NrcRobotSession:
    return NrcRobotSession(
        api,
        command_fd=11,
        servo_fd=22,
        robot_num=1,
        motion_mode=motion_mode,
        movej_period_s=0.2,
    )


def test_power_on_from_stopped_runs_ready_then_poweron() -> None:
    api = FakeNrcApi(state=0)
    session = _session(api)

    transition = session.power_on(timeout=0.05)

    assert (
        transition.initial_state,
        transition.final_state,
    ) == (0, 3)

    assert ("set_servo_state_robot", 11, 1, 1) in api.calls
    assert ("set_servo_poweron_robot", 11, 1) in api.calls


def test_power_on_alarm_path_clears_before_enabling() -> None:
    api = FakeNrcApi(state=2)
    session = _session(api)

    transition = session.power_on(timeout=0.05)

    assert (
        transition.initial_state,
        transition.final_state,
    ) == (2, 3)
    assert ("clear_error_robot", 11, 1) in api.calls
    assert "确认伺服报警已清除" in transition.actions


def test_power_on_reports_nrc_error_meaning() -> None:
    api = FakeNrcApi(state=1)
    api.poweron_result = -1
    session = _session(api)

    with pytest.raises(
        RuntimeError,
        match="接收控制柜响应失败",
    ):
        session.power_on(timeout=0.05)


def test_connection_statuses_use_both_ports() -> None:
    api = FakeNrcApi(state=0)
    api.connection_status = {11: 0, 22: -2}
    session = _session(api)

    assert session.connection_statuses() == {
        "6001": 0,
        "7000": -2,
    }
    assert not session.connections_ready()


def test_wait_motion_stopped_requires_stable_samples() -> None:
    api = FakeNrcApi(state=3)
    api.running_states = [2, 0, 0, 0]
    session = _session(api)

    assert session.wait_until_motion_stopped(
        timeout=0.5,
        stable_samples=3,
    )

    running_calls = [
        call
        for call in api.calls
        if call[0] == "get_robot_running_state_robot"
    ]
    assert len(running_calls) == 4


def test_joint_feedback_preserves_near_zero_wrap_cleanup() -> None:
    api = FakeNrcApi(state=3)
    api.joint_position = [
        360.2,
        -359.6,
        10.0,
        20.0,
        30.0,
        40.0,
        0.0,
    ]
    session = _session(api)

    values = session.joint_position()

    assert values[:2] == pytest.approx((0.2, 0.4))
    assert values[2:6] == pytest.approx(
        (10.0, 20.0, 30.0, 40.0)
    )


def test_servoj_open_send_and_stop_use_servo_port() -> None:
    api = FakeNrcApi(state=3)
    session = _session(api, motion_mode="servoj")

    session.open_servoj(
        vmax=80.0,
        amax=195.0,
        jmax=120.0,
    )
    assert session.servoj_open

    assert session.send_servoj(
        (1, 2, 3, 4, 5, 6, 0)
    )

    session.stop_servoj()
    assert not session.servoj_open

    assert (
        "enable_servo_position_motion_control",
        22,
        True,
    ) in api.calls
    assert any(
        call[0] == "open_servoJ"
        and call[1] == 22
        and len(call[2]) == 7
        for call in api.calls
    )
    sent = next(call for call in api.calls if call[0] == "set_servoJ_pos")
    assert sent[1] == 22
    assert sent[2] == pytest.approx((1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0.0))
    assert ("stop_servoJ", 22) in api.calls


def test_movej_servo_preparation_does_not_open_native_servoj_channel():
    api = FakeNrcApi(state=3)
    session = _session(api, motion_mode="movej")

    session.open_servoj(80.0, 195.0, 120.0)

    assert api.calls == []
    assert not session.servoj_open


def test_movej_mode_rate_limits_and_honors_busy_warning() -> None:
    api = FakeNrcApi(state=3)
    session = _session(api, motion_mode="movej")

    target = (1, 2, 3, 4, 5, 6, 0)

    assert session.send_servoj(target)
    assert not session.send_servoj(target)

    movej_calls = [
        call for call in api.calls if call[0] == "robot_movej"
    ]
    assert len(movej_calls) == 1

    session._last_movej_send_time = None
    session.record_controller_message(
        "warning",
        "job busy",
        4098,
    )

    api.running_states = [2]
    assert not session.send_servoj(target)
    assert session.controller_job_warning


def test_movej_busy_warning_does_not_skip_queue_stop():
    api = FakeNrcApi(state=3)
    stops = []
    api.queue_motion_stop_not_power_off = lambda fd: stops.append(fd) or 0
    session = _session(api, motion_mode="movej")
    session.record_controller_message("warning", "job busy", 4098)
    session._last_movej_send_time = 1.0

    session.stop_motion()

    assert stops == [11]
    assert session._last_movej_send_time is None


@pytest.mark.parametrize("busy", [False, True])
def test_native_queue_stop_failure_blocks_motion_preemption(busy):
    from gello_cr.errors import HardwareError
    from gello_cr.motion import MotionCoordinator, MotionExecutor, MotionSource

    api = FakeNrcApi(state=3)
    api.queue_motion_stop_not_power_off = lambda _fd: -6
    session = _session(api, motion_mode="movej")
    if busy:
        session.record_controller_message("warning", "job busy", 4098)
    motion = MotionCoordinator(MotionExecutor(lambda: session))
    old = motion.acquire(MotionSource.TELEOP)

    with pytest.raises(HardwareError, match="停止.*通信超时"):
        motion.acquire(MotionSource.HOME, allow_preempt=True)

    assert not old.active
    assert motion.current_owner is None
    assert "通信超时" in motion.status.error
