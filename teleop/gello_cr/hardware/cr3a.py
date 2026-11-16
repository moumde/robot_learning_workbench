"""Full CR3A lifecycle adapter over the NRC SDK.

`NrcRobotSession` owns serialized access to an already-connected controller.
`Cr3aDevice` adds the missing lifecycle boundary:

- load/inject the NRC SDK;
- open command port 6001 and servo port 7000;
- roll back partial connections on failure;
- register and retain the NRC warning/error callback;
- expose V2 `RobotSnapshot` values in SI units;
- convert V2 radian joint targets back to native NRC degrees;
- stop motion and close both sockets safely.

Native NRC conventions remain inside this device boundary:
- joint values: degrees;
- TCP xyz: millimetres;
- TCP ABC: radians;
- command vectors: 7 values (CR3A J1..J6 + external-axis placeholder).
"""

from __future__ import annotations

import importlib
import math
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teleop.gello_cr.core.contracts import JointState, RobotSnapshot, TcpPose
from teleop.gello_cr.core.servo_limits import ServoLimit, servo_limit_vector
from teleop.gello_cr.hardware.nrc_robot import NrcRobotSession
from teleop.gello_cr.support.paths import APPLICATION_ROOT, workbench_root
from vendor.nrc_interface.interface import CR3Interface, NRCConnectionError

EventCallback = Callable[[str, str], None]
ApiLoader = Callable[[], Any]

_JOINT_NAMES = ("j1", "j2", "j3", "j4", "j5", "j6")


@dataclass(frozen=True, slots=True)
class Cr3aConfig:
    ip: str
    command_port: int = 6001
    servo_port: int = 7000
    robot_num: int = 1
    motion_mode: str = "servoj"
    movej_velocity: float = 60.0
    movej_acc: float = 90.0
    movej_dec: float = 46.0
    movej_period_s: float = 0.1
    movej_low_latency: bool = False
    servoj_vmax: ServoLimit = 80.0
    servoj_amax: ServoLimit = 195.0
    servoj_jmax: ServoLimit = 120.0
    sdk_root: str | None = None

    def __post_init__(self) -> None:
        if not self.ip.strip():
            raise ValueError("CR3A ip cannot be empty")
        for name, value in (
            ("command_port", self.command_port),
            ("servo_port", self.servo_port),
        ):
            if not 1 <= int(value) <= 65535:
                raise ValueError(f"CR3A {name} must be in 1..65535")
        if int(self.command_port) == int(self.servo_port):
            raise ValueError("CR3A command_port and servo_port must differ")
        if not 1 <= int(self.robot_num) <= 4:
            raise ValueError("CR3A robot_num must be in 1..4")
        if self.motion_mode not in ("servoj", "movej"):
            raise ValueError("CR3A motion_mode must be servoj or movej")
        for name, value in (
            ("movej_velocity", self.movej_velocity),
            ("movej_acc", self.movej_acc),
            ("movej_dec", self.movej_dec),
            ("movej_period_s", self.movej_period_s),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"CR3A {name} must be positive and finite")
        for name in ("servoj_vmax", "servoj_amax", "servoj_jmax"):
            servo_limit_vector(getattr(self, name), name)


class Cr3aDevice:
    """Lifecycle owner for one CR3A/NRC controller connection pair."""

    def __init__(
        self,
        config: Cr3aConfig,
        *,
        api: Any | None = None,
        api_loader: ApiLoader | None = None,
        event_callback: EventCallback | None = None,
        session_guard: Any | None = None,
    ) -> None:
        self.config = config
        self._api = api
        self._api_loader = api_loader
        self._event_callback = event_callback
        self.backend = CR3Interface(
            config.ip, teach_port=config.command_port, track_port=config.servo_port,
            robot_num=config.robot_num, session_guard=session_guard, api_loader=self._load_api,
            servo_vmax=servo_limit_vector(config.servoj_vmax, "servoj_vmax"),
            servo_amax=servo_limit_vector(config.servoj_amax, "servoj_amax"),
            servo_jmax=servo_limit_vector(config.servoj_jmax, "servoj_jmax"),
        )
        self._session_guard = self.backend._session_guard
        self._session: NrcRobotSession | None = None
        self._message_callback: Any = None
        self._latest: RobotSnapshot | None = None
        self._connection_complete = False
        self._lock = threading.RLock()

    @property
    def session(self) -> NrcRobotSession | None:
        """Native NRC session, retained for the staged legacy migration."""
        return self._session

    @property
    def command_fd(self) -> int:
        return self.backend.command_fd

    @property
    def servo_fd(self) -> int:
        return self.backend.servo_fd

    @property
    def connected(self) -> bool:
        return self._connection_complete and self._session is not None and self.backend.connected

    def _event(self, level: str, message: str) -> None:
        callback = self._event_callback
        if callback is not None:
            callback(level, message)

    def _load_api(self) -> Any:
        if self._api is not None:
            return self._api
        if self._api_loader is not None:
            self._api = self._api_loader()
            return self._api

        project = workbench_root()
        shared_root = project / "vendor/nrc_interface/nrc_linux_x86_64"
        root = (
            Path(
                os.environ.get("NRC_SDK_ROOT")
                or self.config.sdk_root
                or (shared_root if shared_root.is_dir() else APPLICATION_ROOT / "vendor/nrc")
            )
            .expanduser()
            .resolve()
        )
        if not (root / "nrc_interface.py").is_file():
            raise FileNotFoundError(
                f"NRC Python module missing: {root / 'nrc_interface.py'}. "
                "Set NRC_SDK_ROOT or robot.sdk_root to the SDK directory."
            )
        # SWIG imports _nrc_host by its top-level name. Never mix SDK copies
        # already cached by Python with an explicitly selected SDK directory.
        module_name = (
            "vendor.nrc_interface.nrc_linux_x86_64.nrc_interface"
            if root == shared_root else "nrc_interface"
        )
        for name in (
            "nrc_interface", "_nrc_host", module_name,
            "vendor.nrc_interface.nrc_linux_x86_64._nrc_host",
        ):
            loaded = sys.modules.get(name)
            if loaded is not None and Path(loaded.__file__).resolve().parent != root:
                raise RuntimeError(
                    f"NRC SDK conflict: {name} already loaded from {loaded.__file__}; "
                    f"requested {root}. Restart the application to change SDK."
                )
        import_root = project if root == shared_root else root
        sys.path.insert(0, str(import_root))
        try:
            self._api = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"NRC Python module lookup failed in {root}: {exc}. "
                "Check nrc_interface.py and _nrc_host extension files; "
                "LD_LIBRARY_PATH does not fix Python module lookup."
            ) from exc
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                f"NRC native SDK loading failed in {root}: {exc}. "
                "Check Python ABI/architecture and shared-library dependencies "
                "with ldd. Set LD_LIBRARY_PATH before launching Python if needed; "
                "PYTHONPATH does not resolve missing shared libraries."
            ) from exc
        finally:
            sys.path.remove(str(import_root))
        return self._api

    def connect(self, timeout: float = 10.0) -> RobotSnapshot:
        if not math.isfinite(float(timeout)) or float(timeout) <= 0:
            raise ValueError("CR3A connect timeout must be positive")
        if self.connected:
            return self.latest()
        self.close()
        self.backend.connection_timeout = float(timeout)
        try:
            self.backend.connect()
            session = NrcRobotSession(
                backend=self.backend, robot_num=self.config.robot_num,
                motion_mode=self.config.motion_mode,
                movej_velocity=self.config.movej_velocity, movej_acc=self.config.movej_acc,
                movej_dec=self.config.movej_dec, movej_period_s=self.config.movej_period_s,
                movej_low_latency=self.config.movej_low_latency,
            )
            self._session = session
            self._register_message_callback(self.backend.api, session, self.command_fd)
            snapshot = self._read_snapshot()
            with self._lock:
                self._latest = snapshot
                self._connection_complete = True
            return snapshot
        except Exception as exc:
            self._connection_complete = False
            try:
                self._disconnect_sockets()
            except Exception as cleanup_error:
                exc.add_note(f"NRC connection rollback incomplete: {cleanup_error}")
            if isinstance(exc, NRCConnectionError):
                raise ConnectionError(str(exc)) from exc
            raise

    def _register_message_callback(
        self,
        api: Any,
        session: NrcRobotSession,
        command_fd: int,
    ) -> None:
        register = getattr(
            api,
            "set_receive_error_or_warnning_message_callback",
            None,
        )
        if register is None:
            self._event(
                "warning",
                "NRC SDK does not expose controller warning callback registration",
            )
            return

        def on_message(
            message_type: Any,
            message: Any,
            message_code: Any,
        ) -> None:
            # Never issue motion commands from the vendor callback thread.
            session.record_controller_message(
                message_type,
                message,
                message_code,
            )
            self._event(
                "warning",
                "NRC controller message: "
                f"type={message_type}, code={message_code}, message={message}",
            )

        # SWIG callbacks need a strong Python reference for the connection life.
        self._message_callback = on_message

        try:
            result = self.backend.register_message_callback(self._message_callback)
        except Exception as exc:
            self._event(
                "warning",
                f"NRC warning callback registration failed: {exc}",
            )
            return

        if result not in (None, 0):
            self._event(
                "warning",
                f"NRC warning callback registration failed: return={result}",
            )

    def _read_snapshot(self) -> RobotSnapshot:
        session = self._require_session()

        joints_native_deg = session.joint_position()
        tcp_native = session.tcp_position()
        servo_state = session.servo_state()

        if len(joints_native_deg) < 6:
            raise RuntimeError("CR3A NRC joint feedback has fewer than 6 joints")
        if len(tcp_native) < 6:
            raise RuntimeError("CR3A NRC TCP feedback has fewer than 6 values")

        timestamp = time.monotonic()
        joint_positions_rad = tuple(math.radians(float(value)) for value in joints_native_deg[:6])
        tcp = TcpPose(
            xyz_m=tuple(float(value) / 1000.0 for value in tcp_native[:3]),
            rpy_rad=tuple(float(value) for value in tcp_native[3:6]),
        )

        return RobotSnapshot(
            timestamp=timestamp,
            joints=JointState(
                timestamp=timestamp,
                names=_JOINT_NAMES,
                positions_rad=joint_positions_rad,
            ),
            tcp=tcp,
            servo_state=int(servo_state),
        )

    def latest(self) -> RobotSnapshot | None:
        if self._session is None:
            return None
        snapshot = self._read_snapshot()
        with self._lock:
            self._latest = snapshot
        return snapshot

    def power_on(self, timeout: float = 10.0) -> None:
        self._require_session().power_on(timeout=float(timeout))

    def power_off(self, timeout: float = 10.0) -> None:
        self._require_session().power_off(timeout=float(timeout))

    def start_joint_servo(self) -> None:
        session = self._require_session()
        session.open_servoj(
            vmax=self.config.servoj_vmax,
            amax=self.config.servoj_amax,
            jmax=self.config.servoj_jmax,
        )

    def send_joint_target(
        self,
        joints_rad: tuple[float, ...],
    ) -> None:
        if len(joints_rad) != 6:
            raise ValueError("CR3A V2 joint target must contain 6 radians")
        if any(not math.isfinite(float(value)) for value in joints_rad):
            raise ValueError("CR3A V2 joint target contains non-finite values")

        native_deg = [math.degrees(float(value)) for value in joints_rad]
        # NRC CR3A command shape remains seven values; ext-axis stays zero.
        native_deg.append(0.0)
        self._require_session().send_servoj(native_deg)

    def stop_motion(self) -> None:
        self._require_session().stop_motion()

    def close(self) -> None:
        errors = []
        session = self._session
        if session is not None:
            try:
                session.stop_motion()
            except Exception as exc:
                errors.append(exc)
        try:
            self._disconnect_sockets()
        except Exception as exc:
            errors.append(exc)
        if errors:
            raise ExceptionGroup("CR3A shutdown incomplete", errors)

    def _disconnect_sockets(self) -> None:
        try:
            self.backend.disconnect()
        finally:
            if self.command_fd == -1 and self.servo_fd == -1:
                self._connection_complete = False
                self._session = None
                self._message_callback = None
                self._latest = None

    def _require_session(self) -> NrcRobotSession:
        session = self._session
        if session is None:
            raise RuntimeError("CR3A is not connected")
        return session
