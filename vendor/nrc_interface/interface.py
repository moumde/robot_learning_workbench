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
from typing import Any

if __package__:
    # Normal package import, e.g. ``from examples.cr3_o6.interface import ...``.
    from .nrc_linux_x86_64 import nrc_interface as _nrc
else:
    # Support running scripts directly from examples/cr3_o6. Let a vendor
    # shared-library error propagate unchanged so Python-version mismatches
    # remain visible to the caller.
    from nrc_linux_x86_64 import nrc_interface as _nrc


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


def _sdk_vector(values: Sequence[float]):
    """Build the SWIG ``std::vector<double>`` expected by the vendor module."""

    vector = _nrc.VectorDouble()
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

    def __init__(
        self,
        robot_ip: str = "192.168.2.14",
        *,
        connect_control: bool = False,
        connection_timeout: float = 10.0,
        connection_poll_period: float = 0.2,
        servo_vmax: Sequence[float] | None = None,
        servo_amax: Sequence[float] | None = None,
        servo_jmax: Sequence[float] | None = None,
    ) -> None:
        self.robot_ip = str(robot_ip)
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
        self._lock = threading.RLock()

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
        """Whether the teach and tracking sockets are both connected."""

        return TEACH_PORT in self._fds and TRACK_PORT in self._fds

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
        fd = int(_nrc.connect_robot(self.robot_ip, str(port)))
        if fd <= 0:
            raise NRCConnectionError(f"connect_robot({self.robot_ip}, {port}) returned {fd}")

        deadline = time.monotonic() + self.connection_timeout
        try:
            status = int(_nrc.get_connection_status(fd))
            while status != 0 and time.monotonic() < deadline:
                time.sleep(self.connection_poll_period)
                status = int(_nrc.get_connection_status(fd))
            if status != 0:
                raise NRCConnectionError(
                    f"connection to {self.robot_ip}:{port} timed out with status {status}"
                )
        except BaseException:
            _nrc.disconnect_robot(fd)
            raise

        LOGGER.info("Connected to CR3 at %s:%d (fd=%d)", self.robot_ip, port, fd)
        return fd

    def connect(self) -> "CR3Interface":
        """Connect the sockets required for state reading and ServoJ control."""

        with self._lock:
            if self._fds:
                if self.connected and (not self.connect_control or CONTROL_PORT in self._fds):
                    return self
                raise NRCConnectionError("partial NRC connection already exists; call disconnect() first")

            ports = [TEACH_PORT, TRACK_PORT]
            if self.connect_control:
                ports.insert(0, CONTROL_PORT)
            connected: list[int] = []
            try:
                for port in ports:
                    self._fds[port] = self._connect_port(port)
                    connected.append(port)
            except BaseException:
                for port in reversed(connected):
                    _nrc.disconnect_robot(self._fds.pop(port))
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
            for port, fd in list(self._fds.items()):
                try:
                    _nrc.disconnect_robot(fd)
                finally:
                    self._fds.pop(port, None)

    close = disconnect

    def __enter__(self) -> "CR3Interface":
        return self.connect()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.disconnect()

    def get_servo_state(self) -> int:
        """Return the NRC servo state: stopped=0, ready=1, error=2, running=3."""

        with self._lock:
            fd = self._fd(TEACH_PORT)
            output = 0
            result = self._call("get_servo_state", _nrc.get_servo_state, fd, output)
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

        with self._lock:
            output = 0
            result = self._call("get_current_mode", _nrc.get_current_mode, self._fd(TEACH_PORT), output)
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
            self._call("clear_error", _nrc.clear_error, self._fd(TEACH_PORT))

    def power_on(self) -> None:
        """Run the ROS2 driver's clear-error, ready, and power-on sequence."""

        with self._lock:
            fd = self._fd(TEACH_PORT)
            state = self.get_servo_state()
            if state == SERVO_RUNNING:
                return

            if state == SERVO_ERROR:
                self._call("clear_error", _nrc.clear_error, fd)
                # NRC requires a power-off after clear_error before power-on.
                try:
                    self._call("set_servo_poweroff", _nrc.set_servo_poweroff, fd)
                except NRCCommandError:
                    LOGGER.warning("Power-off after clear_error was rejected; continuing")
                time.sleep(0.2)
            if state in (SERVO_STOPPED, SERVO_ERROR):
                self._call("set_servo_state(ready)", _nrc.set_servo_state, fd, SERVO_READY)
                time.sleep(0.2)

            try:
                self._call("set_servo_poweron", _nrc.set_servo_poweron, fd)
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
            fd = self._fd(TEACH_PORT)
            state = self.get_servo_state()
            if state != SERVO_RUNNING:
                raise NRCCommandError("set_servo_poweroff (servo is not running)", state)
            self._call("set_servo_poweroff", _nrc.set_servo_poweroff, fd)

    @staticmethod
    def _close_servoj_sdk(fd: int) -> Any:
        # Older generated vendor Python bindings expose stop_servoJ but omit
        # close_servoJ, while newer bindings expose the exact C++ API.
        close_fn = getattr(_nrc, "close_servoJ", None)
        if close_fn is not None:
            return close_fn(fd)
        stop_fn = getattr(_nrc, "stop_servoJ", None)
        if stop_fn is None:
            raise NRCError("The NRC Python binding exposes neither close_servoJ nor stop_servoJ")
        return stop_fn(fd)

    def open_servoj(
        self,
        *,
        vmax: Sequence[float] | None = None,
        amax: Sequence[float] | None = None,
        jmax: Sequence[float] | None = None,
    ) -> None:
        """Open ServoJ tracking after verifying that the robot is running."""

        with self._lock:
            fd = self._fd(TRACK_PORT)
            state = self.get_servo_state()
            if state != SERVO_RUNNING:
                raise NRCCommandError("open_servoJ (servo is not running)", state)
            if self._servo_active:
                raise NRCCommandError("open_servoJ (already active)", "already active")

            vmax_values = self._constraint_vector(vmax, "vmax") if vmax is not None else self.servo_vmax
            amax_values = self._constraint_vector(amax, "amax") if amax is not None else self.servo_amax
            jmax_values = self._constraint_vector(jmax, "jmax") if jmax is not None else self.servo_jmax
            self._call(
                "open_servoJ",
                _nrc.open_servoJ,
                fd,
                _sdk_vector(vmax_values),
                _sdk_vector(amax_values),
                _sdk_vector(jmax_values),
            )
            self._servo_active = True

    open_servoJ = open_servoj

    def close_servoj(self) -> None:
        """Close ServoJ tracking (or use the legacy SDK stop operation)."""

        with self._lock:
            fd = self._fd(TRACK_PORT)
            if not self._servo_active:
                return
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
        return _sdk_vector([math.degrees(value) for value in joints] + [float(external_axis)])

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
                _nrc.set_servoJ_pos,
                self._fd(TRACK_PORT),
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

    def get_joint_positions(self) -> list[float]:
        """Read the six CR3 joint positions in radians."""

        with self._lock:
            output = _sdk_vector([])
            result = self._call(
                "get_current_position(joint)",
                _nrc.get_current_position,
                self._fd(TEACH_PORT),
                0,
                output,
            )
            values = _vector_values(_output_from_result(result, output))
            if len(values) < NUM_JOINTS:
                raise NRCError(f"Expected at least 6 joint values, received {values!r}")
            return [math.radians(value) for value in values[:NUM_JOINTS]]

    get_joint_positions_rad = get_joint_positions

    def get_tcp_pose(self) -> list[float]:
        """Read ``[x_mm, y_mm, z_mm, roll_rad, pitch_rad, yaw_rad, ext]``.

        The external-axis value is returned in the NRC SDK's native unit.
        """

        with self._lock:
            output = _sdk_vector([])
            result = self._call(
                "get_current_position(cartesian)",
                _nrc.get_current_position,
                self._fd(TEACH_PORT),
                1,
                output,
            )
            values = _vector_values(_output_from_result(result, output))
            if len(values) < SDK_NUM_AXES:
                raise NRCError(f"Expected 7 Cartesian values, received {values!r}")
            # Cartesian orientation values are already radians in the NRC API.
            return values[:3] + values[3:6] + [values[6]]

    def _convert_pose_to_sdk_joints(self, pose: Iterable[float]) -> list[float]:
        """Convert a public Cartesian pose to the SDK's seven joint values."""

        pose_values = _as_float_list(pose, name="pose")
        if len(pose_values) != SDK_NUM_AXES:
            raise ValueError("pose must contain [x, y, z, roll, pitch, yaw, external_axis]")
        # Unlike joint positions, the NRC Cartesian API uses radians for ABC.
        sdk_pose = pose_values
        output = _sdk_vector([])
        with self._lock:
            result = self._call(
                "get_origin_coord_to_target_coord",
                _nrc.get_origin_coord_to_target_coord,
                self._fd(TEACH_PORT),
                1,
                _sdk_vector(sdk_pose),
                0,
                output,
            )
        values = _vector_values(_output_from_result(result, output))
        if len(values) < NUM_JOINTS:
            raise NRCError(f"Expected at least 6 converted joint values, received {values!r}")
        # The ROS2 driver forwards all seven values to set_servoJ_pos.  Keep
        # the external axis so send_cartesian_pose() has the same behavior.
        return values[:NUM_JOINTS] + [values[NUM_JOINTS] if len(values) > NUM_JOINTS else 0.0]

    def convert_pose_to_joints(self, pose: Iterable[float]) -> list[float]:
        """Convert a Cartesian pose to six CR3 joint angles in radians."""

        sdk_joints = self._convert_pose_to_sdk_joints(pose)
        return [math.radians(value) for value in sdk_joints[:NUM_JOINTS]]

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
