"""Small, non-ROS control interface for a Dobot CR3.

The vendor SDK lives in :mod:`nrc_linux_x86_64.nrc_interface`.  This module
keeps the SDK's socket and output-argument details in one place and exposes
the control flow used by ``nrc_driver_node.cpp`` as a normal Python class.

Units
------
The public joint APIs use radians, which is also the representation used by
the CR3/O6 OpenPI dataset.  The NRC SDK uses degrees for joint positions and
ServoJ limits, so conversion is done internally.  Cartesian poses use
``[x_mm, y_mm, z_mm, roll_rad, pitch_rad, yaw_rad, external_axis]``.

The class controls the six CR3 joints only.  The optional seventh SDK value is
the external axis and is kept in the NRC SDK's native unit.  It is set to zero
unless explicitly supplied.  The O6 hand can be controlled by a separate
interface and concatenated with the arm state using :meth:`get_openpi_state`.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Iterable, Sequence
from core.hardware.servo_state import ServoTransition
from typing import Any

_nrc = None


def _load_nrc():
    global _nrc
    if _nrc is None:
        from importlib import import_module
        _nrc = import_module("vendor.nrc_interface.nrc_linux_x86_64.nrc_interface")
    return _nrc


LOGGER = logging.getLogger(__name__)

NUM_JOINTS = 6
SDK_NUM_AXES = 7

CONTROL_PORT = 6000
TEACH_PORT = 6001
TRACK_PORT = 7000

SERVO_STOPPED = 0
SERVO_READY = 1
SERVO_ERROR = 2
SERVO_RUNNING = 3


class NRCError(RuntimeError):
    """Base exception raised by :class:`CR3Interface`."""


class NRCConnectionError(NRCError):
    """Raised when an NRC socket cannot be connected or becomes unusable."""


class NRCCommandError(NRCError):
    """Raised when the vendor SDK rejects a command."""

    def __init__(self, command: str, code: Any):
        self.command = command
        self.code = code
        super().__init__(f"{command} failed with NRC return code {code!r}")


def _as_float_list(values: Iterable[float], *, name: str) -> list[float]:
    """Convert lists, tuples, and numpy arrays to finite Python floats."""

    if hasattr(values, "tolist"):
        values = values.tolist()
    try:
        result = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a one-dimensional numeric sequence") from exc
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _sdk_vector(values: Sequence[float], api=None):
    """Build the SWIG ``std::vector<double>`` expected by the vendor module."""

    vector = (api if api is not None else _load_nrc()).VectorDouble()
    for value in values:
        vector.append(float(value))
    return vector


def _vector_values(value: Any) -> list[float]:
    """Read a SWIG vector or a regular sequence returned by the SDK."""

    if hasattr(value, "tolist"):
        value = value.tolist()
    return [float(item) for item in value]


def _return_code(result: Any) -> Any:
    """Extract the SDK return code from normal and SWIG tuple results."""

    # Depending on the SWIG build, an ``int&`` output argument is returned as
    # either ``(return_code, output)`` or ``[return_code, output]``.
    if isinstance(result, (tuple, list)):
        if not result:
            return 0
        return result[0]
    return result


def _output_from_result(result: Any, fallback: Any) -> Any:
    """Extract a SWIG output argument while retaining in-place outputs."""

    if isinstance(result, (tuple, list)) and len(result) > 1:
        return result[1]
    return fallback


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



class CR3Interface:
    """Direct Python controller for a six-axis Dobot CR3.

    The normal lifecycle is::

        robot = CR3Interface("192.168.2.14")
        robot.connect()
        robot.power_on()
        robot.open_servoj()
        robot.send_joint_positions(target_q_rad)
        robot.close_servoj()
        robot.power_off()
        robot.disconnect()

    ``connect()`` opens the 6001 teach socket and the 7000 tracking socket by
    default, matching the ROS2 driver.  The 6000 control socket is optional.

    ``servo_vmax``, ``servo_amax``, and ``servo_jmax`` use NRC SDK units
    (degrees/s, degrees/s², and degrees/s³ for the six rotational joints).
    """

    @classmethod
    def from_config(cls, config_path: str | None = None, **overrides: Any):
        """Create an interface from the default CR3/O6 hardware profile."""

        from config.hardware import load_hardware_config

        hardware = load_hardware_config(config_path)
        kwargs = hardware.nrc.interface_kwargs()
        kwargs.update(overrides)
        return cls(**kwargs)

    def __init__(
        self,
        robot_ip: str = "192.168.2.14",
        *,
        control_port: int = CONTROL_PORT,
        teach_port: int = TEACH_PORT,
        track_port: int = TRACK_PORT,
        connect_control: bool = False,
        connection_timeout: float = 10.0,
        connection_poll_period: float = 0.2,
        servo_vmax: Sequence[float] | None = None,
        servo_amax: Sequence[float] | None = None,
        servo_jmax: Sequence[float] | None = None,
        session_guard: Any | None = None,
        api: Any | None = None,
        api_loader: Any | None = None,
        robot_num: int | None = None,
    ) -> None:
        self._api = api
        self._api_loader = api_loader
        self.robot_num = 1 if robot_num is None else int(robot_num)
        self._robot_specific = robot_num is not None
        if not 1 <= self.robot_num <= 4:
            raise ValueError("NRC robot_num must be in 1..4")
        self._message_callback = None
        self.robot_ip = str(robot_ip)
        self.control_port = int(control_port)
        self.teach_port = int(teach_port)
        self.track_port = int(track_port)
        if self.control_port <= 0 or self.teach_port <= 0 or self.track_port <= 0:
            raise ValueError("NRC ports must be positive integers")
        self.connect_control = connect_control
        self.connection_timeout = float(connection_timeout)
        self.connection_poll_period = float(connection_poll_period)
        if self.connection_timeout <= 0 or self.connection_poll_period <= 0:
            raise ValueError("connection_timeout and connection_poll_period must be positive")

        self.servo_vmax = self._constraint_vector(servo_vmax, "servo_vmax")
        self.servo_amax = self._constraint_vector(servo_amax, "servo_amax")
        self.servo_jmax = self._constraint_vector(servo_jmax, "servo_jmax")

        self._fds: dict[int, int] = {}
        self._servo_active = False
        self._connection_complete = False
        self._lock = threading.RLock()
        if session_guard is None:
            from core.hardware_session import RobotSessionLock
            session_guard = RobotSessionLock(self.robot_ip, self.teach_port, self.track_port)
        self._session_guard = session_guard
        self._session_guard_held = False

    @staticmethod
    def _constraint_vector(values: Sequence[float] | None, name: str) -> list[float]:
        if values is None:
            values = [500.0] * SDK_NUM_AXES
        result = _as_float_list(values, name=name)
        if len(result) != SDK_NUM_AXES:
            raise ValueError(f"{name} must contain {SDK_NUM_AXES} values")
        return result

    @property
    def connected(self) -> bool:
        """Both required channels must be present and confirmed by the SDK."""
        with self._lock:
            if not self._connection_complete or any(
                port not in self._fds for port in (self.teach_port, self.track_port)
            ):
                return False
            try:
                return all(status == 0 for status in self.connection_statuses().values())
            except Exception:
                return False

    @property
    def servo_active(self) -> bool:
        """Whether ServoJ tracking has been opened through this instance."""

        return self._servo_active

    def _fd(self, port: int) -> int:
        try:
            return self._fds[port]
        except KeyError as exc:
            raise NRCConnectionError(f"NRC port {port} is not connected") from exc

    def _call(self, command: str, function, *args) -> Any:
        result = function(*args)
        code = _return_code(result)
        if code != 0:
            raise NRCCommandError(command, code)
        return result

    def _connect_port(self, port: int) -> int:
        LOGGER.info("Connecting to CR3 at %s:%d", self.robot_ip, port)
        fd = int(self.api.connect_robot(self.robot_ip, str(port)))
        if fd <= 0:
            raise NRCConnectionError(f"connect_robot({self.robot_ip}, {port}) returned {fd}")
        # Keep ownership immediately: a failed readiness poll may itself fail
        # to disconnect, in which case the endpoint must remain reserved.
        self._fds[port] = fd

        deadline = time.monotonic() + self.connection_timeout
        try:
            status = int(self.api.get_connection_status(fd))
            while status != 0 and time.monotonic() < deadline:
                time.sleep(self.connection_poll_period)
                status = int(self.api.get_connection_status(fd))
            if status != 0:
                raise NRCConnectionError(
                    f"connection to {self.robot_ip}:{port} timed out with status {status}"
                )
        except BaseException as exc:
            try:
                self._disconnect_port(port, fd)
            except Exception as cleanup_error:
                exc.add_note(f"NRC readiness rollback incomplete: {cleanup_error}")
            raise

        LOGGER.info("Connected to CR3 at %s:%d (fd=%d)", self.robot_ip, port, fd)
        return fd

    def connect(self) -> CR3Interface:
        """Connect the sockets required for state reading and ServoJ control."""

        with self._lock:
            if self._fds:
                if self.connected and (
                    not self.connect_control or self.control_port in self._fds
                ):
                    return self
                raise NRCConnectionError("partial NRC connection already exists; call disconnect() first")

            self._session_guard.acquire()
            self._session_guard_held = True
            ports = [self.teach_port, self.track_port]
            if self.connect_control:
                ports.insert(0, self.control_port)
            try:
                for port in ports:
                    self._fds[port] = self._connect_port(port)
                self._connection_complete = True
            except BaseException as exc:
                try:
                    self.disconnect()
                except Exception as cleanup_error:
                    exc.add_note(f"NRC connection rollback incomplete: {cleanup_error}")
                raise
        return self

    def disconnect(self) -> None:
        """Stop ServoJ if needed and close all connected sockets.

        This method does not power the robot off automatically.  Call
        :meth:`power_off` explicitly when the application owns the robot's
        power state.
        """

        with self._lock:
            if self._servo_active:
                try:
                    self.close_servoj()
                except NRCError:
                    LOGGER.exception("Failed to close ServoJ during disconnect")
                self._servo_active = False
            errors = []
            for port, fd in list(self._fds.items()):
                try:
                    self._disconnect_port(port, fd)
                except Exception as exc:
                    errors.append(exc)
            if not self._fds and self._session_guard_held:
                self._connection_complete = False
                self._session_guard.release()
                self._session_guard_held = False
            if errors:
                raise ExceptionGroup("NRC disconnect incomplete", errors)

    def _disconnect_port(self, port: int, fd: int) -> None:
        result = self.api.disconnect_robot(fd)
        if result is not None and _return_code(result) != 0:
            raise NRCCommandError("disconnect_robot", result)
        self._fds.pop(port, None)

    close = disconnect

    def __enter__(self) -> CR3Interface:
        return self.connect()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.disconnect()

    def get_servo_state(self) -> int:
        """Return the NRC servo state: stopped=0, ready=1, error=2, running=3."""

        if self._robot_specific:
            with self._lock:
                return self._read_servo_state_unlocked()
        with self._lock:
            fd = self._fd(self.teach_port)
            output = 0
            result = self._call("get_servo_state", self.api.get_servo_state, fd, output)
            output = _output_from_result(result, output)
            if isinstance(output, (tuple, list)):
                # Some SWIG builds return (return_code, output_value).
                output = output[0]
            try:
                return int(output)
            except (TypeError, ValueError) as exc:
                raise NRCError(f"Unexpected get_servo_state result: {result!r}") from exc

    def get_current_mode(self) -> int:
        """Return the NRC controller mode for diagnostics.

        The controller documents mode ``0`` as teach, ``1`` as remote, and
        ``2`` as run.  The ROS2 power-on service does not gate its power-on
        request on this value, so :meth:`power_on` also keeps that behavior and
        only includes the mode in a failure diagnostic.
        """

        if self._robot_specific:
            with self._lock:
                return self._read_current_mode_unlocked()
        with self._lock:
            output = 0
            result = self._call(
                "get_current_mode", self.api.get_current_mode, self._fd(self.teach_port), output
            )
            output = _output_from_result(result, output)
            if isinstance(output, (tuple, list)):
                output = output[0]
            try:
                return int(output)
            except (TypeError, ValueError) as exc:
                raise NRCError(f"Unexpected get_current_mode result: {result!r}") from exc

    def clear_error(self) -> None:
        """Clear the controller error state."""

        with self._lock:
            self._call("clear_error", self.api.clear_error, self._fd(self.teach_port))

    def power_on(self) -> None:
        """Run the ROS2 driver's clear-error, ready, and power-on sequence."""

        with self._lock:
            fd = self._fd(self.teach_port)
            state = self.get_servo_state()
            if state == SERVO_RUNNING:
                return

            if state == SERVO_ERROR:
                self._call("clear_error", self.api.clear_error, fd)
                # NRC requires a power-off after clear_error before power-on.
                try:
                    self._call("set_servo_poweroff", self.api.set_servo_poweroff, fd)
                except NRCCommandError:
                    LOGGER.warning("Power-off after clear_error was rejected; continuing")
                time.sleep(0.2)
            if state in (SERVO_STOPPED, SERVO_ERROR):
                self._call("set_servo_state(ready)", self.api.set_servo_state, fd, SERVO_READY)
                time.sleep(0.2)

            try:
                self._call("set_servo_poweron", self.api.set_servo_poweron, fd)
            except NRCCommandError as exc:
                try:
                    after_state = self.get_servo_state()
                except NRCError:
                    after_state = "unknown"
                try:
                    mode = self.get_current_mode()
                except NRCError:
                    mode = "unknown"
                raise NRCCommandError(
                    f"set_servo_poweron (state={state}, mode={mode}, after_state={after_state})",
                    exc.code,
                ) from exc

    def power_off(self) -> None:
        """Power the robot off, matching the ROS2 driver's state check."""

        with self._lock:
            fd = self._fd(self.teach_port)
            state = self.get_servo_state()
            if state != SERVO_RUNNING:
                raise NRCCommandError("set_servo_poweroff (servo is not running)", state)
            self._call("set_servo_poweroff", self.api.set_servo_poweroff, fd)

    def _close_servoj_sdk(self, fd: int) -> Any:
        # Older generated vendor Python bindings expose stop_servoJ but omit
        # close_servoJ, while newer bindings expose the exact C++ API.
        close_fn = getattr(self.api, "close_servoJ", None)
        if close_fn is not None:
            return close_fn(fd)
        stop_fn = getattr(self.api, "stop_servoJ", None)
        if stop_fn is None:
            raise NRCError("The NRC Python binding exposes neither close_servoJ nor stop_servoJ")
        return stop_fn(fd)

    def open_servoj(
        self,
        *,
        vmax: Sequence[float] | None = None,
        amax: Sequence[float] | None = None,
        jmax: Sequence[float] | None = None,
        enable_position_control: bool = False,
    ) -> None:
        """Open ServoJ tracking after verifying that the robot is running."""

        with self._lock:
            fd = self._fd(self.track_port)
            state = self.get_servo_state()
            if state != SERVO_RUNNING:
                raise NRCCommandError("open_servoJ (servo is not running)", state)
            if self._servo_active:
                raise NRCCommandError("open_servoJ (already active)", "already active")

            vmax_values = self._constraint_vector(vmax, "vmax") if vmax is not None else self.servo_vmax
            amax_values = self._constraint_vector(amax, "amax") if amax is not None else self.servo_amax
            jmax_values = self._constraint_vector(jmax, "jmax") if jmax is not None else self.servo_jmax
            if enable_position_control:
                self._call("enable_servo_position_motion_control",
                           self.api.enable_servo_position_motion_control, fd, True)
            self._call(
                "open_servoJ",
                self.api.open_servoJ,
                fd,
                self._vector(vmax_values),
                self._vector(amax_values),
                self._vector(jmax_values),
            )
            self._servo_active = True

    open_servoJ = open_servoj

    def close_servoj(self) -> None:
        """Close ServoJ tracking (or use the legacy SDK stop operation)."""

        with self._lock:
            if not self._servo_active:
                return
            fd = self._fd(self.track_port)
            result = self._close_servoj_sdk(fd)
            code = _return_code(result)
            if code != 0:
                raise NRCCommandError("close_servoJ", code)
            self._servo_active = False

    close_servoJ = close_servoj

    def _joint_command_degrees(
        self, joint_positions_rad: Iterable[float], external_axis: float = 0.0
    ):
        joints = _as_float_list(joint_positions_rad, name="joint_positions_rad")
        if len(joints) != NUM_JOINTS:
            raise ValueError(f"joint_positions_rad must contain {NUM_JOINTS} values")
        if not math.isfinite(float(external_axis)):
            raise ValueError("external_axis must be finite")
        # The six CR3 joints use degrees in NRC.  The external axis is passed
        # through unchanged because its unit depends on the robot setup.
        return self._vector([math.degrees(value) for value in joints] + [float(external_axis)])

    def send_joint_positions(
        self,
        joint_positions_rad: Iterable[float],
        *,
        external_axis: float = 0.0,
        require_servoj: bool = True,
    ) -> None:
        """Send one absolute CR3 joint target in radians."""

        with self._lock:
            if require_servoj and not self._servo_active:
                raise NRCCommandError("set_servoJ_pos (ServoJ is not active)", "inactive")
            self._call(
                "set_servoJ_pos",
                self.api.set_servoJ_pos,
                self._fd(self.track_port),
                self._joint_command_degrees(joint_positions_rad, external_axis),
            )

    send_servoj_position = send_joint_positions

    def send_openpi_action(self, action: Iterable[float]) -> list[float]:
        """Send the CR3 part of a 12D OpenPI action and return the O6 part.

        The returned six values are not sent by this class; the caller can
        forward them to the O6 hand controller.  Keeping this split explicit
        prevents hand commands from being silently discarded.
        """

        action_values = _as_float_list(action, name="action")
        if len(action_values) != 12:
            raise ValueError("action must contain 12 CR3/O6 values")
        self.send_joint_positions(action_values[:NUM_JOINTS])
        return action_values[NUM_JOINTS:]

    def get_joint_positions(self, *, include_external_axis: bool = False) -> list[float]:
        """Read six radians; optionally append the external axis in its native unit."""
        values = self._read_position(0)
        joints = [math.radians(value) for value in values[:NUM_JOINTS]]
        return joints + [values[6]] if include_external_axis else joints

    get_joint_positions_rad = get_joint_positions

    def get_tcp_pose(self) -> list[float]:
        """Read xyz millimetres, ABC radians, and the native external axis."""
        return self._read_position(1)

    def _convert_pose_to_sdk_joints(self, pose: Iterable[float]) -> list[float]:
        """Convert a public Cartesian pose to the SDK's seven joint values."""

        pose_values = _as_float_list(pose, name="pose")
        if len(pose_values) != SDK_NUM_AXES:
            raise ValueError("pose must contain [x, y, z, roll, pitch, yaw, external_axis]")
        # Unlike joint positions, the NRC Cartesian API uses radians for ABC.
        sdk_pose = pose_values
        output = self.api.VectorDouble(7)
        with self._lock:
            result = self._call(
                "get_origin_coord_to_target_coord",
                self.api.get_origin_coord_to_target_coord,
                self._fd(self.teach_port),
                1,
                self._vector(sdk_pose),
                0,
                output,
            )
        values = _vector_values(_output_from_result(result, output))
        if len(values) < NUM_JOINTS:
            raise NRCError(f"Expected at least 6 converted joint values, received {values!r}")
        # The ROS2 driver forwards all seven values to set_servoJ_pos.  Keep
        # the external axis so send_cartesian_pose() has the same behavior.
        return values[:NUM_JOINTS] + [values[NUM_JOINTS] if len(values) > NUM_JOINTS else 0.0]

    def convert_pose_to_joints(self, pose: Iterable[float], *, include_external_axis: bool = False) -> list[float]:
        """Convert a Cartesian pose to six CR3 joint angles in radians."""

        sdk_joints = self._convert_pose_to_sdk_joints(pose)
        result = [math.radians(value) for value in sdk_joints[:NUM_JOINTS]]
        return result + [sdk_joints[6]] if include_external_axis else result

    def send_cartesian_pose(self, pose: Iterable[float], *, require_servoj: bool = True) -> None:
        """Convert and send one Cartesian target using the ServoJ channel.

        As in the ROS2 ServoL path, the converted external-axis value is
        forwarded instead of being silently replaced with zero.
        """

        sdk_joints = self._convert_pose_to_sdk_joints(pose)
        self.send_joint_positions(
            [math.radians(value) for value in sdk_joints[:NUM_JOINTS]],
            external_axis=sdk_joints[NUM_JOINTS],
            require_servoj=require_servoj,
        )

    def get_openpi_state(self, hand_state: Iterable[float]) -> list[float]:
        """Return the 12D CR3/O6 state expected by the OpenPI policy."""

        hand = _as_float_list(hand_state, name="hand_state")
        if len(hand) != 6:
            raise ValueError("hand_state must contain 6 values")
        return self.get_joint_positions() + hand


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
            raise NRCError(f"{action}失败: {self._result_description(result)}")


    def _read_servo_state_unlocked(self) -> int:
        result = self.api.get_servo_state_robot(
            self.command_fd,
            self.robot_num,
            0,
        )
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            raise NRCError(f"读取 CR5 伺服状态返回格式错误: {result}")
        self._require_ok(result[0], "读取 CR5 伺服状态")

        state = int(result[1])
        if state not in NRC_SERVO_STATE_NAMES:
            raise NRCError(f"CR5 返回未知伺服状态: {state}")
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
            raise NRCError(f"读取 CR5 运行模式返回格式错误: {last_result}")

        self._require_ok(last_result[0], "读取 CR5 运行模式")
        return int(last_result[1])


    def _set_run_mode_unlocked(self, timeout: float) -> None:
        mode = self._read_current_mode_unlocked()
        state = self._read_servo_state_unlocked()

        if state == 2:
            raise NRCError("CR5 当前处于报警状态，不能切换运行模式")

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
                raise NRCError("CR5 未能退出运行模式")
            time.sleep(0.1)

        result = self.api.set_current_mode_robot(
            self.command_fd,
            self.robot_num,
            2,
        )
        self._require_ok(result, "CR5 进入运行模式")

        if self._read_current_mode_unlocked() != 2:
            raise NRCError("CR5 运行模式确认失败")

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


    def power_on_verified(self, timeout: float = 10.0) -> ServoTransition:
        """Run the verified NRC servo state machine and finish in state 3."""

        actions: list[str] = []

        with self._lock:
            connection_status = int(self.api.get_connection_status(self.command_fd))
            if connection_status != 0:
                raise NRCError(f"CR5 6001 示教端口未连接，状态={connection_status}")

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
                    raise NRCError("CR5 清错后仍处于报警状态(2)")
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
                return ServoTransition(
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
                raise NRCError(
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

            return ServoTransition(
                initial_state,
                final_state,
                tuple(actions),
            )


    def power_off_verified(self, timeout: float = 10.0) -> ServoTransition:
        actions: list[str] = []

        with self._lock:
            initial_state = self._read_servo_state_unlocked()

            if initial_state in (0, 1):
                return ServoTransition(
                    initial_state,
                    initial_state,
                    ("伺服已经下电",),
                )

            if initial_state == 2:
                raise NRCError("CR5 当前为伺服报警状态，请先清除报警")

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

            return ServoTransition(
                initial_state,
                final_state,
                tuple(actions),
            )


    def running_state(self) -> int:
        with self._lock:
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
            raise NRCError(f"读取 CR5 运行状态失败: {result}")

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

            if self.get_servo_state() != 3:
                raise NRCError("CR5 等待停止过程中退出运行状态")

            if self.running_state() == 2:
                stable = 0
            else:
                stable += 1
                if stable >= max(1, int(stable_samples)):
                    return True

            time.sleep(0.05)

        return False

    @property
    def api(self):
        if self._api is None:
            self._api = self._api_loader() if self._api_loader is not None else _load_nrc()
        return self._api

    @property
    def command_fd(self) -> int:
        return self._fds.get(self.teach_port, -1)

    @property
    def servo_fd(self) -> int:
        return self._fds.get(self.track_port, -1)

    def _vector(self, values):
        return _sdk_vector(values, self.api)

    @classmethod
    def from_connected(cls, api, command_fd, servo_fd, *, robot_num=1):
        """Adopt an existing pair for the legacy session constructor, without opening sockets."""
        robot = cls("adopted", api=api, robot_num=robot_num)
        robot._fds = {robot.teach_port: int(command_fd), robot.track_port: int(servo_fd)}
        robot._connection_complete = True
        return robot

    def connection_statuses(self) -> dict[str, int]:
        with self._lock:
            return {str(port): int(self.api.get_connection_status(self._fds.get(port, -1)))
                    for port in (self.teach_port, self.track_port)}

    def wait_connections_ready(self, timeout=10.0):
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            if all(status == 0 for status in self.connection_statuses().values()):
                return
            time.sleep(0.02)
        raise NRCConnectionError(f"NRC connections not ready: {self.connection_statuses()}")

    def register_message_callback(self, callback):
        with self._lock:
            register = getattr(self.api, "set_receive_error_or_warnning_message_callback", None)
            if register is None:
                return None
            self._message_callback = callback
            return register(self._fd(self.teach_port), callback)

    def _read_position(self, coord):
        with self._lock:
            output = self._vector([])
            result = self._call("get_current_position", self.api.get_current_position,
                                self._fd(self.teach_port), int(coord), output)
            values = _vector_values(_output_from_result(result, output))
        if len(values) < SDK_NUM_AXES or not all(math.isfinite(v) for v in values[:7]):
            raise NRCError(f"CR3A 坐标反馈含非有限数值或不足七轴(coord={coord})")
        return values[:SDK_NUM_AXES]

    def forward_kinematics(self, joints_rad, *, external_axis=0.0):
        target = self._joint_command_degrees(joints_rad, external_axis)
        output = self.api.VectorDouble(7)
        with self._lock:
            self._call("forward_kinematics", self.api.get_origin_coord_to_target_coord,
                       self._fd(self.teach_port), 0, target, 1, output)
        values = _vector_values(output)
        if len(values) < 7 or not all(math.isfinite(v) for v in values[:7]):
            raise NRCError("CR3A 正运动学反馈含非有限数值或不足七轴")
        return values[:7]

    def move_joint_positions(self, joints_rad, *, external_axis=0.0,
                             velocity=10.0, acc=20.0, dec=20.0, stop_servoj=True):
        with self._lock:
            if stop_servoj:
                self.close_servoj()
            command = self.api.MoveCmd()
            command.targetPosType = self.api.PosType_data
            command.targetPosValue = self._joint_command_degrees(joints_rad, external_axis)
            command.coord = 0
            command.velocity, command.acc, command.dec = float(velocity), float(acc), float(dec)
            self._require_ok(self.api.robot_movej(self._fd(self.teach_port), command),
                             "CR3A MoveJ 下发")

    def move_cartesian_pose(self, pose, *, velocity=10.0, acc=20.0, dec=20.0):
        values = _as_float_list(pose, name="pose")
        if len(values) != 7:
            raise ValueError("TCP target must contain seven values")
        with self._lock:
            self.close_servoj()
            command = self.api.MoveCmd()
            command.targetPosType = self.api.PosType_data
            command.targetPosValue = self._vector(values)
            command.coord = 1
            command.velocity, command.acc, command.dec = float(velocity), float(acc), float(dec)
            self._require_ok(self.api.robot_movel(self._fd(self.teach_port), command),
                             "CR3A MoveL 下发")

    def stop_motion(self):
        try:
            self.close_servoj()
        finally:
            stop = getattr(self.api, "queue_motion_stop_not_power_off", None)
            if stop is not None and self.command_fd > 0:
                with self._lock:
                    self._require_ok(stop(self.command_fd), "CR3A 队列运动停止")


# A concise alias for callers that prefer the vendor-neutral name.
NRCInterface = CR3Interface


__all__ = [
    "CONTROL_PORT",
    "CR3Interface",
    "NRCCommandError",
    "NRCConnectionError",
    "NRCError",
    "NRCInterface",
    "SERVO_ERROR",
    "SERVO_READY",
    "SERVO_RUNNING",
    "SERVO_STOPPED",
    "TEACH_PORT",
    "TRACK_PORT",
]
