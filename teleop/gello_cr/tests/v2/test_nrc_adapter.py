from __future__ import annotations

from teleop.gello_cr.hardware.nrc_robot import (
    NrcRobotSession,
    NrcServoTransition,
)


class FakeApi:
    def __init__(self) -> None:
        self.connection_status = {11: 0, 22: -2}

    def get_connection_status(self, fd: int) -> int:
        return self.connection_status[fd]


def test_session_preserves_constructor_and_connection_statuses() -> None:
    api = FakeApi()
    adapter = NrcRobotSession(
        api,
        command_fd=11,
        servo_fd=22,
        robot_num=1,
        motion_mode="servoj",
        movej_velocity=10.0,
        movej_acc=20.0,
        movej_dec=20.0,
        movej_period_s=0.1,
        movej_low_latency=False,
    )

    assert isinstance(adapter, NrcRobotSession)
    assert adapter.api is api
    assert adapter.command_fd == 11
    assert adapter.servo_fd == 22
    assert adapter.robot_num == 1
    assert adapter.motion_mode == "servoj"
    assert adapter.connection_statuses() == {
        "6001": 0,
        "7000": -2,
    }


def test_servo_transition_preserves_state_and_actions() -> None:
    transition = NrcServoTransition(
        initial_state=1,
        final_state=3,
        actions=("设置运行模式", "伺服上电"),
    )
    assert transition.initial_state == 1
    assert transition.final_state == 3
    assert transition.actions == (
        "设置运行模式",
        "伺服上电",
    )


def test_session_preserves_controller_warning_behavior() -> None:
    adapter = NrcRobotSession(
        FakeApi(),
        command_fd=11,
        servo_fd=22,
        robot_num=1,
    )

    assert adapter.controller_job_warning == ""
    adapter.record_controller_message(
        "warning",
        "controller job busy",
        4098,
    )
    assert "4098" in adapter.controller_job_warning
    assert "controller job busy" in adapter.controller_job_warning
