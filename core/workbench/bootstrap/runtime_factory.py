"""Concrete construction of the current GELLO/CR3A/O6 collection runtime.

Construction is intentionally side-effect free with respect to hardware.  The
factory instantiates controller/device objects but never calls connect(),
power_on(), start_follow(), camera start, or recorder start_episode().
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from core.hardware.camera_streams import camera_stream_metadata, resolve_camera_streams
from core.hardware.cameras import SharedCameraGroup
from core.hardware.cr3a import Cr3aConfig, Cr3aDevice
from core.hardware.realsense import RealSenseRgbDevice
from core.workbench.app import RuntimeLifecycleCallbacks
from core.workbench.paths import workbench_root
from core.workbench.recording.batch import BatchManager, recording_profile
from core.workbench.recording.formats import DatasetFormat, DatasetWriterConfig
from core.workbench.recording.source import CR3O6CaptureSource
from core.workbench.recording.writers.factory import WriterFactory

EventCallback = Callable[[str, str], None]


@dataclass(frozen=True, slots=True)
class RuntimeFactoryPaths:
    repo_root: Path
    config_path: Path
    linker_hand_sdk_root: Path
    nrc_sdk_root: Path | None

    @classmethod
    def from_repo(
        cls,
        repo_root: str | Path,
        *,
        config_path: str | Path | None = None,
    ) -> RuntimeFactoryPaths:
        requested_root = Path(repo_root).expanduser().resolve()
        root = workbench_root(requested_root)
        integrated = (root / "config/hardware.py").is_file()
        config = (
            Path(config_path).expanduser().resolve()
            if config_path is not None
            else root / "config" / ("teleop/gello_cr.json" if integrated else "workbench.json")
        )
        nrc_root = root / "vendor" / ("nrc_interface/nrc_linux_x86_64" if integrated else "nrc")
        return cls(
            repo_root=root,
            config_path=config,
            linker_hand_sdk_root=(root / "vendor" / (
                "actuator/linkerhand-python-sdk" if integrated else "linker_hand_python_sdk"
            ) / "LinkerHand"),
            nrc_sdk_root=nrc_root if nrc_root.is_dir() else None,
        )


@dataclass(frozen=True, slots=True)
class RuntimeConstructors:
    TeleopConfigStore: Any
    RoArmSerialController: Any
    Inverse3Controller: Any
    GelloController: Any
    O6Controller: Any
    TeleopRuntime: Any
    RecordingSession: Any
    Cr3aDevice: Any = Cr3aDevice
    RealSenseRgbDevice: Any = RealSenseRgbDevice

    @classmethod
    def load_defaults(cls) -> RuntimeConstructors:
        from core.hardware.o6 import O6Controller
        from core.workbench.app.config_store import TeleopConfigStore
        from core.workbench.app.runtime import TeleopRuntime
        from core.workbench.recording.session import RecordingSession
        from teleop.devices.inverse3 import Inverse3Controller
        from teleop.devices.roarm import RoArmSerialController
        from teleop.gello_cr.controller import TeleopController
        from teleop.gello_cr.device import GelloController

        return cls(
            TeleopConfigStore=TeleopConfigStore.from_file,
            RoArmSerialController=RoArmSerialController,
            Inverse3Controller=Inverse3Controller,
            GelloController=GelloController,
            O6Controller=O6Controller,
            TeleopRuntime=partial(
                TeleopRuntime, teleop_controller_factory=TeleopController,
            ),
            RecordingSession=RecordingSession,
        )


class Cr3aLifecycle:
    """Explicit CR3A lifecycle callbacks used by ApplicationService."""

    def __init__(
        self,
        *,
        store: Any,
        teleop_engine: Any,
        paths: RuntimeFactoryPaths,
        device_constructor: Any = Cr3aDevice,
        event_callback: EventCallback | None = None,
    ) -> None:
        self._store = store
        self._teleop_engine = teleop_engine
        self._paths = paths
        self._device_constructor = device_constructor
        self._event_callback = event_callback
        self.device: Any | None = None
        self.session: Any | None = None
        self._attached = False

        # Tracks the application's requested robot power state.
        # A fault/reset from CONNECTED must never enable the robot.
        self._desired_enabled = False
        self._status_lock = threading.Lock()
        self._feedback_io_lock = threading.RLock()
        self._feedback_stop = threading.Event()
        self._feedback_thread: threading.Thread | None = None
        self._status = {
            "connected": False,
            "servo_state": "unknown",
            "sampled_at": None,
            "desired_enabled": False,
            "error": "",
        }

    def status_snapshot(self) -> dict[str, Any]:
        """Read the last worker observation; never call the SDK from GUI polls."""
        with self._status_lock:
            return dict(self._status)

    def _refresh_status(self) -> None:
        with self._feedback_io_lock:
            session, device = self.session, self.device
            connected = False
            servo, error = "unknown", ""
            if session is not None and device is not None:
                try:
                    connected = bool(device.connected)
                    if connected:
                        state = int(session.servo_state())
                        servo = {0: "off", 1: "off", 2: "error", 3: "on"}.get(state, "unknown")
                        if state == 2:
                            error = "CR3A Servo 报警，servo_state=2"
                    else:
                        error = "CR3A 连接反馈已断开"
                except Exception as exc:
                    servo, error = "error", f"{type(exc).__name__}: {exc}"
            with self._status_lock:
                self._status = {
                    "connected": connected,
                    "servo_state": servo,
                    "sampled_at": time.monotonic(),
                    "desired_enabled": self._desired_enabled,
                    "error": error,
                }
            if session is not None and not connected:
                # Unexpected loss keeps the runtime fault latch. Planned
                # disconnect stops this producer before detaching the session.
                try:
                    self._teleop_engine.detach_robot(session, error or "CR3A 连接反馈已断开")
                except Exception as exc:
                    self._event("error", f"CR3A 断线停止失败: {exc}")

    def _feedback_loop(self) -> None:
        while not self._feedback_stop.wait(0.25):
            self._refresh_status()

    def _start_feedback(self) -> None:
        if self._feedback_thread is not None and self._feedback_thread.is_alive():
            return
        self._feedback_stop.clear()
        self._feedback_thread = threading.Thread(
            target=self._feedback_loop,
            name="CR3A-Feedback",
            daemon=True,
        )
        self._feedback_thread.start()

    def stop_feedback(self, timeout: float = 0.5) -> None:
        """Bounded join; retain resources for retry if an SDK read is stuck."""
        self._feedback_stop.set()
        thread = self._feedback_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                raise TimeoutError("CR3A 反馈线程未及时停止；保留连接供重试关闭")
        self._feedback_thread = None

    def _event(self, level: str, message: str) -> None:
        if self._event_callback is not None:
            self._event_callback(level, message)

    def _robot_config(self) -> Cr3aConfig:
        cfg = self._store.deployment_data()["robot"]
        return Cr3aConfig(
            ip=str(cfg["ip"]),
            command_port=int(cfg.get("command_port", 6001)),
            servo_port=int(cfg.get("servo_port", 7000)),
            robot_num=int(cfg.get("robot_num", 1)),
            motion_mode="servoj",
            movej_velocity=float(cfg["movej_velocity"]),
            movej_acc=float(cfg["movej_acc"]),
            movej_dec=float(cfg["movej_dec"]),
            movej_period_s=float(cfg["movej_period_s"]),
            movej_low_latency=bool(cfg["movej_low_latency"]),
            servoj_vmax=cfg["servoj_vmax"],
            servoj_amax=cfg["servoj_amax"],
            servoj_jmax=cfg["servoj_jmax"],
            sdk_root=cfg.get("sdk_root")
            or (str(self._paths.nrc_sdk_root) if self._paths.nrc_sdk_root is not None else None),
        )

    def connect(self) -> Any:
        if self._attached and self.device is not None and getattr(self.device, "connected", False):
            return self.session
        if self.device is not None:
            # A prior failed rollback may still own native sockets and the
            # shared endpoint lock. Finish that cleanup before replacing it.
            self.disconnect()

        device = self._device_constructor(
            self._robot_config(),
            event_callback=self._event_callback,
        )
        try:
            device.connect(timeout=10.0)
            session = device.session
            if session is None:
                raise RuntimeError("CR3A connected without NRC session")
            self._teleop_engine.attach_robot(session)
            self._attached = True
        except Exception as exc:
            self._attached = False
            try:
                device.close()
            except Exception as cleanup_error:
                self.device = device
                self.session = device.session
                exc.add_note(f"Failed connection cleanup: {cleanup_error}")
            raise

        self.device = device
        self.session = session
        self._desired_enabled = False
        self._refresh_status()
        self._start_feedback()
        self._event("info", "CR3A 已连接；未上使能，未启动 ServoJ")
        return session

    def _require_session(self) -> Any:
        session = self.session
        if session is None:
            raise RuntimeError("CR3A 尚未连接")
        return session

    def power_on(self) -> Any:
        with self._feedback_io_lock:
            session = self._require_session()
            try:
                transition = session.power_on()
                state = int(session.servo_state())
                if state != 3:
                    raise RuntimeError(f"CR3A 上使能确认失败，servo_state={state}")
                self._desired_enabled = True
                return transition
            finally:
                self._refresh_status()

    def power_off(self) -> Any:
        with self._feedback_io_lock:
            session = self._require_session()
            try:
                self._teleop_engine.stop_motion("下使能前停止当前动作")
                transition = session.power_off()
                state = int(session.servo_state())
                if state not in (0, 1):
                    raise RuntimeError(f"CR3A 下使能确认失败，servo_state={state}")
                self._desired_enabled = False
                return transition
            finally:
                self._refresh_status()

    def _reset(self, label: str) -> Any:
        with self._feedback_io_lock:
            session = self._require_session()
            if self.device is None or not self.device.connected:
                raise RuntimeError("CR3A 连接尚未恢复；请断开连接后重新连接")
            self._teleop_engine.stop_motion(f"{label}前确认运动已停止")
            transition = None

            # Restore only a power state explicitly requested before the fault.
            # A never-enabled connection remains disabled after reset.
            if self._desired_enabled:
                state = int(session.servo_state())
                if state != 3:
                    transition = session.power_on()
                    state = int(session.servo_state())
                if state != 3:
                    raise RuntimeError(f"{label}失败，servo_state={state}")

            # Feedback loss detaches the runtime but retains the native session
            # for cleanup. Reuse it only after explicit reset and confirmed I/O.
            self._teleop_engine.attach_robot(session)
            self._teleop_engine.acknowledge_fault()
            if self._desired_enabled:
                message = f"{label}完成；恢复使能状态，保持 idle，不自动恢复跟随"
            else:
                message = f"{label}完成；保持未使能状态，不自动恢复跟随"
            self._event("info", message)
            self._refresh_status()
            return transition

    def reset_fault(self) -> Any:
        return self._reset("FAULT 复位")

    def reset_estop(self) -> Any:
        return self._reset("ESTOP 复位")

    def shutdown_power(self) -> None:
        session = self.session
        if session is not None and session.servo_state() == 3:
            session.power_off()
            if session.servo_state() not in (0, 1):
                raise RuntimeError("Shutdown power-off not confirmed")
            self._desired_enabled = False

    def disconnect(self) -> bool:
        self.stop_feedback()
        self._attached = False
        device = self.device
        session = self.session
        errors = []
        if session is not None:
            try:
                detached = self._teleop_engine.detach_robot(
                    session,
                    "ApplicationService 断开 CR3A",
                    expected=True,
                )
                if detached is False:
                    # Unexpected loss has already cleared engine.robot; its
                    # producers may still be unwinding with the old session.
                    self._teleop_engine.stop_motion("CR3A 断线后确认运动已停止")
            except Exception as exc:
                errors.append(exc)
        if device is not None and not errors:
            try:
                device.close()
            except Exception as exc:
                errors.append(exc)
        if errors:
            failure = ExceptionGroup("CR3A disconnect incomplete", errors)
            if self.device is not None and self.session is not None:
                try:
                    # Teardown stopped the previous sampler before touching
                    # the session. Retained resources still need fresh status
                    # while the operator resolves the error and retries.
                    self._start_feedback()
                except Exception as feedback_error:
                    failure.add_note(f"CR3A feedback restart failed: {feedback_error}")
            raise failure
        self.device = None
        self.session = None
        self._desired_enabled = False
        if getattr(self._teleop_engine, "state", None) == "fault":
            self._teleop_engine.acknowledge_fault()
        self._refresh_status()
        self._event("info", "CR3A 已断开；不会自动重连")
        return True

    def callbacks(self) -> RuntimeLifecycleCallbacks:
        return RuntimeLifecycleCallbacks(
            connect=self.connect,
            disconnect=self.disconnect,
            power_on=self.power_on,
            power_off=self.power_off,
            reset_fault=self.reset_fault,
            reset_estop=self.reset_estop,
        )


@dataclass(slots=True)
class ConcreteRuntime:
    paths: RuntimeFactoryPaths
    store: Any
    roarm_controller: Any
    inverse3_controller: Any
    gello_controller: Any
    master_controller: Any
    o6_controller: Any
    teleop_engine: Any
    sample_source: CR3O6CaptureSource
    recorder: Any
    camera_devices: dict[str, Any]
    cr3a_lifecycle: Cr3aLifecycle

    @property
    def lifecycle(self) -> RuntimeLifecycleCallbacks:
        return self.cr3a_lifecycle.callbacks()

    _closed_resources: set[str] = field(default_factory=set, init=False)

    def close(self) -> None:
        """Drain motion before releasing devices; failed cleanup can be retried."""
        errors = []
        steps = [
            ("robot_feedback", self.cr3a_lifecycle.stop_feedback),
            ("motion", lambda: self.teleop_engine.shutdown(close_devices=False)),
            *(
                (name, lambda device=device: device.close(hold=False))
                for name, device in (
                    ("gello", self.gello_controller),
                    ("inverse3", self.inverse3_controller),
                    ("roarm", self.roarm_controller),
                )
                if device is not None
            ),
            ("o6", self.o6_controller.close),
            ("robot_power", self.cr3a_lifecycle.shutdown_power),
            ("robot_connection", self.cr3a_lifecycle.disconnect),
        ]
        for name, close in steps:
            if name in self._closed_resources:
                continue
            try:
                close()
            except Exception as exc:
                exc.add_note(f"shutdown resource: {name}")
                errors.append(exc)
                if name in ("motion", "robot_feedback"):
                    break
            else:
                self._closed_resources.add(name)
        if errors:
            raise ExceptionGroup("Runtime shutdown incomplete", errors)


class ConcreteRuntimeFactory:
    """Build current production runtime objects without opening hardware."""

    def __init__(
        self,
        paths: RuntimeFactoryPaths,
        *,
        constructors: RuntimeConstructors | None = None,
        event_callback: EventCallback | None = None,
    ) -> None:
        self.paths = paths
        self.constructors = constructors or RuntimeConstructors.load_defaults()
        self.event_callback = event_callback

    def build(self) -> ConcreteRuntime:
        c = self.constructors
        store = c.TeleopConfigStore(self.paths.config_path)
        cfg = store.deployment_data()

        master_type = str(cfg["master"]["type"])
        roarm = inverse3 = gello = None
        if master_type == "gello":
            gello_cfg = cfg["gello"]
            software_root = Path(gello_cfg["software_root"]).expanduser()
            if not software_root.is_absolute():
                software_root = self.paths.config_path.parent / software_root
            master = gello = c.GelloController(
                port=gello_cfg["port"],
                software_root=str(software_root.resolve()),
                joint_ids=gello_cfg["joint_ids"],
                joint_offsets=gello_cfg["joint_offsets"],
                joint_signs=gello_cfg["joint_signs"],
                gripper_config=gello_cfg["gripper_config"],
                baudrate=gello_cfg["baudrate"],
                feedback_hz=gello_cfg["feedback_hz"],
                feedback_timeout_s=gello_cfg["feedback_timeout_s"],
            )
        elif master_type == "roarm":
            master = roarm = c.RoArmSerialController(
                cfg["roarm"]["port"],
                cfg["roarm"]["baudrate"],
                cfg["roarm"]["feedback_hz"],
            )
        elif master_type == "inverse3":
            master = inverse3 = c.Inverse3Controller(
                cfg["inverse3"]["uri"],
                cfg["inverse3"]["device_id"],
                cfg["inverse3"]["grip_device_id"],
                cfg["inverse3"]["feedback_hz"],
                basis=cfg["inverse3"]["basis"],
            )
        else:
            raise ValueError(f"unsupported master type: {master_type}")

        o6 = c.O6Controller(
            cfg["o6"]["port"],
            self.paths.linker_hand_sdk_root,
            cfg["o6"]["hand_id"],
            cfg["o6"]["baudrate"],
        )
        engine = c.TeleopRuntime(store, master, o6)
        from core.workbench.diagnostics import diagnostic_report

        engine.release_info = diagnostic_report(cfg, self.paths.repo_root)

        def runtime_event(level: str, message: str) -> None:
            getattr(logging.getLogger("workbench.recording"), level)(message)
            engine.events.put((level, message))
            if self.event_callback is not None:
                self.event_callback(level, message)

        dataset_cfg = cfg["dataset"]
        worker_python = dataset_cfg["worker_python"]
        streams = resolve_camera_streams(dataset_cfg)
        sample_source = CR3O6CaptureSource(engine.dataset_sample, dataset_cfg, streams=streams)
        writer_factory = WriterFactory(
            DatasetWriterConfig(
                format=DatasetFormat(dataset_cfg.get("format", "lerobot_v3")),
                worker_python=worker_python,
                repo_prefix=dataset_cfg["repo_prefix"],
                video_codec=dataset_cfg.get("video_codec"),
                hdf5_compression=dataset_cfg.get("hdf5_compression"),
            ),
            worker_pythons=dataset_cfg.get("worker_pythons"),
        )
        recording_session = c.RecordingSession(
            source=sample_source,
            writer_factory=writer_factory,
            event_callback=runtime_event,
            fps=int(dataset_cfg["fps"]),
            image_size=tuple(dataset_cfg["image_size"]),
        )
        default_root = Path(dataset_cfg.get("root") or self.paths.repo_root / "dataset" / "train")
        staging_root = (
            dataset_cfg.get("staging_root") or default_root.expanduser().parent / "staging"
        )
        recorder = BatchManager(
            recording_session,
            staging_root=staging_root,
            writer_factory=writer_factory,
            event_callback=runtime_event,
            profile_provider=lambda: recording_profile(
                mode=dataset_cfg.get("recording_mode", "tcp"),
                fps=int(dataset_cfg["fps"]),
                image_size=dataset_cfg["image_size"],
                camera_configuration=camera_stream_metadata(resolve_camera_streams(dataset_cfg)),
                hardware_profile={"robot": "cr3a", "hand_id": cfg["o6"]["hand_id"]},
            ),
        )

        camera_group = SharedCameraGroup(
            streams, config=dataset_cfg, device_constructor=c.RealSenseRgbDevice,
        )
        camera_devices = camera_group.views

        def hardware_event(level, message):
            getattr(logging.getLogger("workbench.hardware"), level)(message)
            engine.events.put((level, message))
            if self.event_callback is not None:
                self.event_callback(level, message)

        lifecycle = Cr3aLifecycle(
            store=store,
            teleop_engine=engine,
            paths=self.paths,
            device_constructor=c.Cr3aDevice,
            event_callback=lambda level, message: hardware_event(level, message),
        )

        return ConcreteRuntime(
            paths=self.paths,
            store=store,
            roarm_controller=roarm,
            inverse3_controller=inverse3,
            gello_controller=gello,
            master_controller=master,
            o6_controller=o6,
            teleop_engine=engine,
            sample_source=sample_source,
            recorder=recorder,
            camera_devices=camera_devices,
            cr3a_lifecycle=lifecycle,
        )
