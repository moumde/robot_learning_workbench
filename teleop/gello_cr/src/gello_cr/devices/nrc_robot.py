"""NRC controller session for CR-series robots.

SDK loading and socket creation belong to Cr3aDevice. This session owns
serialized access, servo state transitions, and motion commands.

    Cr3aDevice
        owns SDK loading + 6001/7000 connection lifecycle
            ↓
    NrcRobotSession (this module)
        owns serialized access, servo state machine and motion commands

"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from gello_cr.core.servo_limits import ServoLimit, servo_limit_vector
from gello_cr.errors import HardwareError

NRC_RESULT_NAMES = {
    -6: "通信超时",
    -5: "SDK 异常",
    -4: "当前状态不允许该操作",
    -3: "参数错误",
    -2: "控制柜连接断开",
    -1: "接收控制柜响应失败",
    0: "成功",
}

NRC_SERVO_STATE_NAMES = {
    0: "停止",
    1: "就绪",
    2: "报警",
    3: "运行",
}


@dataclass(frozen=True, slots=True)
class NrcServoTransition:
    initial_state: int
    final_state: int
    actions: tuple[str, ...]


class NrcRobotSession:
    """Serialized access to one already-connected NRC command/servo pair."""

    def __init__(
        self,
        api: Any,
        command_fd: int,
        servo_fd: int,
        robot_num: int,
        motion_mode: str = "movej",
        movej_velocity: float = 10.0,
        movej_acc: float = 20.0,
        movej_dec: float = 20.0,
        movej_period_s: float = 0.1,
        movej_low_latency: bool = False,
    ) -> None:
        self.api = api
        self.command_fd = command_fd
        self.servo_fd = servo_fd
        self.robot_num = int(robot_num)

        if not 1 <= self.robot_num <= 4:
            raise ValueError("NRC robot_num 必须是 1～4 的整数")
        if motion_mode not in ("servoj", "movej"):
            raise ValueError("motion_mode 必须是 servoj 或 movej")
        if float(movej_period_s) <= 0:
            raise ValueError("movej_period_s 必须大于 0")

        self.motion_mode = motion_mode
        self.movej_velocity = float(movej_velocity)
        self.movej_acc = float(movej_acc)
        self.movej_dec = float(movej_dec)
        self.movej_period_s = float(movej_period_s)
        self.movej_low_latency = bool(movej_low_latency)

        self._last_movej_send_time: float | None = None
        self.lock = threading.RLock()
        self.servoj_open = False
        self._controller_job_warning = ""

    @property
    def controller_job_warning(self) -> str:
        with self.lock:
            return self._controller_job_warning

    def record_controller_message(
        self,
        message_type: Any,
        message: Any,
        code: Any,
    ) -> None:
        del message_type
        if int(code) == 4098:
            with self.lock:
                self._controller_job_warning = f"code=4098: {message}"

    def _vector(self, values: Iterable[float]) -> Any:
        vector = self.api.VectorDouble()
        for value in values:
            vector.append(float(value))
        return vector

    @staticmethod
    def _result_ok(result: Any) -> bool:
        try:
            return int(result) == 0
        except (TypeError, ValueError):
            return result == 0

    @staticmethod
    def servo_state_name(state: int) -> str:
        value = int(state)
        return NRC_SERVO_STATE_NAMES.get(value, f"未知({value})")

    @staticmethod
    def _result_description(result: Any) -> str:
        try:
            code = int(result)
        except (TypeError, ValueError):
            return str(result)
        return f"{code}（{NRC_RESULT_NAMES.get(code, '未知返回码')}）"

    def _require_ok(self, result: Any, action: str) -> None:
        if not self._result_ok(result):
            raise HardwareError(f"{action}失败: {self._result_description(result)}")

    def _read_servo_state_unlocked(self) -> int:
        result = self.api.get_servo_state_robot(
            self.command_fd,
            self.robot_num,
            0,
        )
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            raise HardwareError(f"读取 CR5 伺服状态返回格式错误: {result}")
        self._require_ok(result[0], "读取 CR5 伺服状态")

        state = int(result[1])
        if state not in NRC_SERVO_STATE_NAMES:
            raise HardwareError(f"CR5 返回未知伺服状态: {state}")
        return state

    def _read_current_mode_unlocked(self) -> int:
        last_result: Any = None

        for _ in range(5):
            result = self.api.get_current_mode_robot(
                self.command_fd,
                self.robot_num,
                0,
            )
            last_result = result

            if isinstance(result, (tuple, list)) and len(result) >= 2 and int(result[0]) == 0:
                return int(result[1])

            if not isinstance(result, (tuple, list)) or len(result) < 1 or int(result[0]) != -1:
                break

            time.sleep(0.1)

        if not isinstance(last_result, (tuple, list)) or len(last_result) < 2:
            raise HardwareError(f"读取 CR5 运行模式返回格式错误: {last_result}")

        self._require_ok(last_result[0], "读取 CR5 运行模式")
        return int(last_result[1])

    def _set_run_mode_unlocked(self, timeout: float) -> None:
        mode = self._read_current_mode_unlocked()
        state = self._read_servo_state_unlocked()

        if state == 2:
            raise HardwareError("CR5 当前处于报警状态，不能切换运行模式")

        if mode == 2 and state == 3:
            return

        if mode == 2:
            result = self.api.set_current_mode_robot(
                self.command_fd,
                self.robot_num,
                0,
            )
            self._require_ok(result, "CR5 退出运行模式")

            if self._read_current_mode_unlocked() != 0:
                raise HardwareError("CR5 未能退出运行模式")
            time.sleep(0.1)

        result = self.api.set_current_mode_robot(
            self.command_fd,
            self.robot_num,
            2,
        )
        self._require_ok(result, "CR5 进入运行模式")

        if self._read_current_mode_unlocked() != 2:
            raise HardwareError("CR5 运行模式确认失败")

        time.sleep(min(0.3, float(timeout)))

    def _wait_servo_state_unlocked(
        self,
        expected: Iterable[int],
        timeout: float,
        action: str,
    ) -> int:
        expected_states = {int(value) for value in expected}
        deadline = time.monotonic() + float(timeout)
        last_state: int | None = None
        last_error = ""

        while time.monotonic() < deadline:
            try:
                last_state = self._read_servo_state_unlocked()
                last_error = ""
                if last_state in expected_states:
                    return last_state
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.05)

        expected_text = "/".join(
            f"{state}-{self.servo_state_name(state)}" for state in sorted(expected_states)
        )
        detail = last_error or (
            f"最后状态={last_state}-{self.servo_state_name(last_state)}"
            if last_state is not None
            else "没有状态反馈"
        )
        raise TimeoutError(f"{action}超时，期望 {expected_text}，{detail}")

    def wait_connections_ready(self, timeout: float = 10.0) -> None:
        """Wait for both 6001 command and 7000 servo sockets."""

        for label, socket_fd in (
            ("6001 示教端口", self.command_fd),
            ("7000 跟踪端口", self.servo_fd),
        ):
            deadline = time.monotonic() + float(timeout)
            last_status: int | None = None

            while time.monotonic() < deadline:
                with self.lock:
                    last_status = int(self.api.get_connection_status(socket_fd))
                if last_status == 0:
                    break
                time.sleep(0.2)
            else:
                raise TimeoutError(f"CR5 {label}连接未就绪，状态={last_status}")

    def connection_statuses(self) -> dict[str, int]:
        with self.lock:
            return {
                "6001": int(self.api.get_connection_status(self.command_fd)),
                "7000": int(self.api.get_connection_status(self.servo_fd)),
            }

    def connections_ready(self) -> bool:
        return all(status == 0 for status in self.connection_statuses().values())

    def servo_state(self) -> int:
        with self.lock:
            return self._read_servo_state_unlocked()

    def current_mode(self) -> int:
        with self.lock:
            return self._read_current_mode_unlocked()

    def power_on(self, timeout: float = 10.0) -> NrcServoTransition:
        """Run the verified NRC servo state machine and finish in state 3."""

        actions: list[str] = []

        with self.lock:
            connection_status = int(self.api.get_connection_status(self.command_fd))
            if connection_status != 0:
                raise HardwareError(f"CR5 6001 示教端口未连接，状态={connection_status}")

            initial_state = self._read_servo_state_unlocked()
            state = initial_state

            if state == 2:
                result = self.api.clear_error_robot(
                    self.command_fd,
                    self.robot_num,
                )
                self._require_ok(result, "CR5 清除报警")
                actions.append("清除伺服报警")

                time.sleep(0.3)

                state = self._read_servo_state_unlocked()
                if state == 2:
                    raise HardwareError("CR5 清错后仍处于报警状态(2)")
                actions.append("确认伺服报警已清除")

                result = self.api.set_servo_poweroff_robot(
                    self.command_fd,
                    self.robot_num,
                )

                if self._result_ok(result):
                    actions.append("清错后释放伺服占用")
                    state = self._wait_servo_state_unlocked(
                        {0, 1},
                        timeout,
                        "CR5 清错后下电",
                    )
                elif int(result) == -4:
                    actions.append("伺服已经处于下电状态")
                    state = self._wait_servo_state_unlocked(
                        {0, 1},
                        timeout,
                        "CR5 清错后状态稳定",
                    )
                else:
                    self._require_ok(result, "CR5 清错后下电")

                result = self.api.set_servo_state_robot(
                    self.command_fd,
                    self.robot_num,
                    1,
                )
                self._require_ok(result, "CR5 设置伺服就绪")
                actions.append("设置伺服就绪")

                state = self._wait_servo_state_unlocked(
                    {1},
                    timeout,
                    "CR5 进入就绪状态",
                )

            self._set_run_mode_unlocked(timeout)
            actions.append("设置 CR5 运行模式")

            if state == 3:
                return NrcServoTransition(
                    initial_state,
                    state,
                    tuple(actions),
                )

            if state == 0:
                result = self.api.set_servo_state_robot(
                    self.command_fd,
                    self.robot_num,
                    1,
                )
                self._require_ok(result, "CR5 设置伺服就绪")
                actions.append("设置伺服就绪")

                state = self._wait_servo_state_unlocked(
                    {1},
                    timeout,
                    "CR5 进入就绪状态",
                )

            if state != 1:
                raise HardwareError(
                    f"CR5 无法上使能：当前伺服状态={state}-{self.servo_state_name(state)}"
                )

            result = self.api.set_servo_poweron_robot(
                self.command_fd,
                self.robot_num,
            )
            self._require_ok(result, "CR5 伺服上电")
            actions.append("伺服上电")

            final_state = self._wait_servo_state_unlocked(
                {3},
                timeout,
                "CR5 进入运行状态",
            )

            return NrcServoTransition(
                initial_state,
                final_state,
                tuple(actions),
            )

    def power_off(self, timeout: float = 10.0) -> NrcServoTransition:
        actions: list[str] = []

        with self.lock:
            initial_state = self._read_servo_state_unlocked()

            if initial_state in (0, 1):
                return NrcServoTransition(
                    initial_state,
                    initial_state,
                    ("伺服已经下电",),
                )

            if initial_state == 2:
                raise HardwareError("CR5 当前为伺服报警状态，请先清除报警")

            result = self.api.set_servo_poweroff_robot(
                self.command_fd,
                self.robot_num,
            )
            self._require_ok(result, "CR5 伺服下电")
            actions.append("伺服下电")

            final_state = self._wait_servo_state_unlocked(
                {1},
                timeout,
                "CR5 进入就绪状态",
            )

            return NrcServoTransition(
                initial_state,
                final_state,
                tuple(actions),
            )

    def clear_servo_error(
        self,
        timeout: float = 10.0,
    ) -> NrcServoTransition:
        return self.power_on(timeout)

    def running_state(self) -> int:
        with self.lock:
            result = self.api.get_robot_running_state_robot(
                self.command_fd,
                self.robot_num,
                0,
            )

        if (
            not isinstance(result, (tuple, list))
            or len(result) < 2
            or not self._result_ok(result[0])
        ):
            raise HardwareError(f"读取 CR5 运行状态失败: {result}")

        return int(result[1])

    def wait_until_motion_stopped(
        self,
        timeout: float,
        stop_event: threading.Event | None = None,
        stable_samples: int = 3,
    ) -> bool:
        deadline = time.monotonic() + float(timeout)
        stable = 0

        while time.monotonic() < deadline:
            if stop_event is not None and stop_event.is_set():
                return False

            if self.servo_state() != 3:
                raise HardwareError("CR5 等待停止过程中退出运行状态")

            if self.running_state() == 2:
                stable = 0
            else:
                stable += 1
                if stable >= max(1, int(stable_samples)):
                    return True

            time.sleep(0.05)

        return False

    def position(self, coord: int) -> list[float]:
        output = self.api.VectorDouble()

        with self.lock:
            result = self.api.get_current_position(
                self.command_fd,
                int(coord),
                output,
            )

        values = [float(value) for value in output]

        if not self._result_ok(result) or len(values) < 7:
            raise HardwareError(
                f"读取 CR5 坐标失败(coord={coord}, ret={result}, len={len(values)})"
            )

        if not all(math.isfinite(value) for value in values[:7]):
            raise HardwareError(f"CR3A 坐标反馈含非有限数值(coord={coord})")

        # Preserve the legacy near-zero wrap cleanup only.
        if int(coord) == 0:
            for index in range(6):
                wrapped = values[index] - 360.0 * round(values[index] / 360.0)
                if abs(wrapped) < 1.0:
                    values[index] = wrapped

        return values[:7]

    def joint_position(self) -> list[float]:
        return self.position(0)

    def tcp_position(self) -> list[float]:
        return self.position(1)

    def open_servoj(
        self,
        vmax: ServoLimit,
        amax: ServoLimit,
        jmax: ServoLimit,
    ) -> None:
        if self.motion_mode == "movej":
            return

        limits = tuple(servo_limit_vector(value, name) for name, value in (
            ("vmax", vmax), ("amax", amax), ("jmax", jmax)
        ))
        with self.lock:
            enable_result = self.api.enable_servo_position_motion_control(
                self.servo_fd,
                True,
            )
            if not self._result_ok(enable_result):
                raise HardwareError(
                    f"开启 CR5 servoJ 位置控制失败: {self._result_description(enable_result)}"
                )

            result = self.api.open_servoJ(
                self.servo_fd,
                self._vector(limits[0]),
                self._vector(limits[1]),
                self._vector(limits[2]),
            )

        if not self._result_ok(result):
            raise HardwareError(f"开启 CR5 servoJ 失败: {result}")

        self.servoj_open = True

    def stop_servoj(self) -> None:
        if self.motion_mode == "movej":
            return
        if not self.servoj_open:
            return

        with self.lock:
            result = self.api.stop_servoJ(self.servo_fd)

        self.servoj_open = False

        if not self._result_ok(result):
            raise HardwareError(f"停止 CR5 servoJ 失败: {result}")

    def inverse_kinematics(
        self,
        tcp: Sequence[float],
    ) -> list[float]:
        if len(tcp) != 7:
            raise ValueError("CR5 TCP 目标必须包含 7 个值")

        target = self._vector(tcp)
        joints = self.api.VectorDouble(7)

        with self.lock:
            result = self.api.get_origin_coord_to_target_coord(
                self.command_fd,
                1,
                target,
                0,
                joints,
            )

        values = [float(value) for value in joints]

        if not self._result_ok(result) or len(values) < 7:
            raise HardwareError(f"CR5 逆运动学失败: {result}")

        return values[:7]

    def forward_kinematics(
        self,
        joints: Sequence[float],
    ) -> list[float]:
        if len(joints) != 7:
            raise ValueError("CR5 正运动学输入必须包含 7 个关节值")

        target = self._vector(joints)
        tcp = self.api.VectorDouble(7)

        with self.lock:
            result = self.api.get_origin_coord_to_target_coord(
                self.command_fd,
                0,
                target,
                1,
                tcp,
            )

        values = [float(value) for value in tcp]

        if (
            not self._result_ok(result)
            or len(values) < 7
            or any(not math.isfinite(value) for value in values[:7])
        ):
            raise HardwareError(f"CR5 正运动学失败: {result}")

        return values[:7]

    def clear_movej_busy_if_stopped(self) -> bool:
        with self.lock:
            if self._controller_job_warning:
                if self.running_state() != 0:
                    return False

                if self._read_servo_state_unlocked() != 3:
                    raise HardwareError("CR5 等待 MoveJ 空闲时退出运行状态")

                self._controller_job_warning = ""

            return True

    def send_servoj(
        self,
        joints: Sequence[float],
    ) -> bool:
        if len(joints) != 7:
            raise ValueError("CR5 servoJ 目标必须包含 7 个值")

        if self.motion_mode == "movej":
            now = time.monotonic()

            if (
                self._last_movej_send_time is not None
                and now - self._last_movej_send_time < self.movej_period_s
            ):
                return False

            with self.lock:
                if self._controller_job_warning:
                    if not self.movej_low_latency:
                        self.clear_movej_busy_if_stopped()
                    return False

            command = self.api.MoveCmd()
            command.targetPosType = self.api.PosType_data
            command.targetPosValue = self._vector(joints)
            command.coord = 0
            command.velocity = self.movej_velocity
            command.acc = self.movej_acc
            command.dec = self.movej_dec

            with self.lock:
                result = self.api.robot_movej(
                    self.command_fd,
                    command,
                )

            if not self._result_ok(result):
                raise HardwareError(f"发送 CR5 MoveJ 失败: {result}")

            self._last_movej_send_time = now
            return True

        with self.lock:
            result = self.api.set_servoJ_pos(
                self.servo_fd,
                self._vector(joints),
            )

        if not self._result_ok(result):
            raise HardwareError(f"发送 CR5 servoJ 失败: {result}")

        return True

    def movej(
        self,
        joints: Sequence[float],
        velocity: float,
        acc: float,
        dec: float,
    ) -> None:
        if len(joints) != 7:
            raise ValueError("CR5 MoveJ 目标必须包含 7 个值")

        self.stop_servoj()

        command = self.api.MoveCmd()
        command.targetPosType = self.api.PosType_data
        command.targetPosValue = self._vector(joints)
        command.coord = 0
        command.velocity = float(velocity)
        command.acc = float(acc)
        command.dec = float(dec)

        with self.lock:
            result = self.api.robot_movej(
                self.command_fd,
                command,
            )

        if not self._result_ok(result):
            raise HardwareError(f"CR5 MoveJ 下发失败: {result}")

    def movel(
        self,
        tcp: Sequence[float],
        velocity: float,
        acc: float,
        dec: float,
    ) -> None:
        if len(tcp) != 7:
            raise ValueError("CR5 MoveL 目标必须包含 7 个值")

        self.stop_servoj()

        command = self.api.MoveCmd()
        command.targetPosType = self.api.PosType_data
        command.targetPosValue = self._vector(tcp)
        command.coord = 1
        command.velocity = float(velocity)
        command.acc = float(acc)
        command.dec = float(dec)

        with self.lock:
            result = self.api.robot_movel(
                self.command_fd,
                command,
            )

        if not self._result_ok(result):
            raise HardwareError(f"CR5 MoveL 下发失败: {result}")

    def wait_until_joints(
        self,
        target: Sequence[float],
        tolerance_deg: float,
        timeout: float,
    ) -> bool:
        deadline = time.monotonic() + float(timeout)

        while time.monotonic() < deadline:
            current = self.joint_position()

            if max(abs(a - b) for a, b in zip(current[:6], target[:6], strict=True)) <= float(
                tolerance_deg
            ):
                return True

            time.sleep(0.1)

        return False

    def stop_motion(self) -> None:
        try:
            self.stop_servoj()
        finally:
            self._last_movej_send_time = None
            stop = getattr(
                self.api,
                "queue_motion_stop_not_power_off",
                None,
            )
            if stop is not None:
                with self.lock:
                    self._require_ok(stop(self.command_fd), "CR3A 队列运动停止")
