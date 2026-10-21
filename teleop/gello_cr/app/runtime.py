"""Application motion orchestration, HOME, and unified trajectory integration.

GELLO following lives in control.teleop_controller. Hardware lifetimes are
owned by bootstrap/devices; episode persistence lives in recording.
"""

from __future__ import annotations

import logging
import math
import queue
import sys
import threading
import time
from collections.abc import Sequence
from typing import Any

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.control.contracts import TeleopHooks
from teleop.gello_cr.hardware.nrc_robot import NrcRobotSession as NrcRobotAdapter
from teleop.gello_cr.hardware.o6 import O6Controller
from teleop.gello_cr.motion import (
    MotionCoordinator,
    MotionExecutor,
    MotionLease,
    MotionPreempted,
    MotionSafety,
    MotionSource,
)
from teleop.gello_cr.trajectory import (
    ReplayOptions,
    TrajectoryPlayer,
    TrajectoryRecorder,
    TrajectoryStore,
)

from .capture_snapshot import CaptureSnapshot
from .hand_actions import HandActions
from .home_service import HomeService
from .planning_service import PointMotionService
from .teleop_service import TeleopService
from .trajectory_service import TrajectoryService
from .trajectory_source import RuntimeTrajectorySource


def _default_teleop_controller(*args, **kwargs):
    """Retain direct runtime construction without loading a master plugin at import."""
    from teleop.gello_cr.control.controller import TeleopController

    return TeleopController(*args, **kwargs)


class TeleopRuntime:
    """Coordinate application motion ownership, HOME, and runtime snapshots."""

    def __init__(
        self,
        store: TeleopConfigStore,
        roarm: Any,
        o6: O6Controller,
        *,
        teleop_controller_factory=None,
    ):
        self.store = store
        self.roarm = roarm
        self.o6 = o6
        self.robot: NrcRobotAdapter | None = None
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._state_lock = threading.RLock()
        self._robot_connection_lock = threading.RLock()
        self._home_lock = threading.Lock()
        self._state = "idle"
        self._last_error = ""
        self._diagnostics = {}
        self._recording_snapshot = None
        self._stop_generation = 0
        self._follow_stop = threading.Event()
        self._home_stop = threading.Event()
        self._hand_action_stop = threading.Event()
        self._record_stop = threading.Event()
        self._replay_stop = threading.Event()
        self._shutdown_requested = threading.Event()
        self._follow_thread: threading.Thread | None = None
        self._follow_lease: MotionLease | None = None
        self.external_control = None
        self._last_dagger_snapshot = {}
        self._home_thread: threading.Thread | None = None
        self._home_completed = threading.Event()
        self._home_completed.set()
        self._home_capture_transition: dict[str, Any] | None = None
        self._home_restart_target = None
        self._replay_thread: threading.Thread | None = None
        self._o6_manual_override = False
        self._o6_action_active = False
        self._o6_action_name = ""
        self._dataset_target_tcp_controller: (
            tuple[float, float, float, float, float, float] | None
        ) = None
        self._dataset_target_joints_deg: tuple[float, float, float, float, float, float] | None = (
            None
        )
        self._dataset_action_timestamp = 0.0
        self._gello_telemetry: dict[str, Any] | None = None
        self.motion_executor = MotionExecutor(lambda: self.robot)
        self.motion = MotionCoordinator(
            self.motion_executor,
            safety=MotionSafety(lambda: self.store.data),
            event_callback=self._event,
        )
        self._policy_lease: MotionLease | None = None
        trajectory_cfg = self.store.data.get("trajectory", {})
        self.trajectory_store = TrajectoryStore(
            self.store.resolve_path(trajectory_cfg.get("root", "../dataset/replay/trajectories"))
        )
        self.trajectory_source = RuntimeTrajectorySource(self)
        self.trajectory_recorder = TrajectoryRecorder(
            self.trajectory_source,
            fps=1.0 / float(self.store.data["replay"]["sample_period_s"]),
            max_duration_s=float(self.store.data["replay"]["max_duration_s"]),
            stop_event=self._record_stop,
        )
        robot_cfg = self.store.data["robot"]
        self.trajectory_player = TrajectoryPlayer(
            self.motion,
            self.trajectory_source,
            period_s=float(self.store.data["replay"]["servoj_period_s"]),
            servo_profile=tuple(
                robot_cfg[k] for k in ("servoj_vmax", "servoj_amax", "servoj_jmax")
            ),
            stop_event=self._replay_stop,
        )
        self._pending_trajectory = None
        self._trajectory_catalog = []
        self._trajectory_lease = None
        self._trajectory_hand_enabled = False
        self._trajectory_preview = None
        self._trajectory_active_id = None
        self.teleop_service = TeleopService(self)
        self.hand_actions = HandActions(self)
        self.home_service = HomeService(self)
        self.trajectory_service = TrajectoryService(self)
        self.capture_snapshot = CaptureSnapshot(self)
        self.list_trajectories()
        self.point_motion = PointMotionService(self)
        self.teleop_controller = (
            teleop_controller_factory or _default_teleop_controller
        )(
            store,
            roarm,
            o6,
            robot=lambda: self.robot,
            motion=self.motion,
            hooks=TeleopHooks(
                lock=self._state_lock,
                stop=self._follow_stop,
                shutdown=self._shutdown_requested,
                generation=lambda: self._stop_generation,
                state=lambda: self.state,
                set_state=self._set_state,
                event=self._event,
                reset_targets=self._clear_follow_targets,
                publish_tcp_target=self._set_dataset_target_tcp,
                publish_telemetry=self._publish_gello_telemetry,
            ),
        )

    @property
    def master_type(self) -> str:
        return str(getattr(self.roarm, "master_type", "roarm"))

    def set_master(self, master: Any) -> None:
        if self.state not in ("idle", "fault"):
            raise RuntimeError("当前遥操作状态不允许切换主臂")
        if getattr(self.roarm, "connected", False):
            raise RuntimeError("主臂已连接，不能直接切换类型")
        self.roarm = master
        self.teleop_controller.master = master
        if self.state == "fault" and self.last_error.startswith("主臂"):
            self._set_state("idle")

    @property
    def state(self) -> str:
        with self._state_lock:
            return self._state

    @property
    def last_error(self) -> str:
        with self._state_lock:
            return self._last_error

    @property
    def o6_manual_override(self) -> bool:
        with self._state_lock:
            return self._o6_manual_override

    @property
    def o6_action_active(self) -> bool:
        with self._state_lock:
            return self._o6_action_active

    @property
    def recording(self) -> bool:
        thread = self._record_thread
        return bool(thread is not None and thread.is_alive() and not self._record_stop.is_set())

    @property
    def replaying(self) -> bool:
        thread = self._replay_thread
        return bool(thread is not None and thread.is_alive())

    def attach_robot(self, robot: NrcRobotAdapter) -> None:
        with self._robot_connection_lock:
            if self.robot is not None and self.robot is not robot:
                self.motion.cancel_all("Robot session replaced")
            self.robot = robot
            if self.state == "fault" and self.last_error.startswith("CR5 连接断开"):
                self._set_state("idle")
            self._event("info", "CR5 已接入遥操作引擎")

    def detach_robot(
        self, robot: NrcRobotAdapter | None, reason: str, *, expected: bool = False
    ) -> bool:
        """Detach only the expected stale adapter and stop local command producers."""
        with self._robot_connection_lock:
            with self._state_lock:
                if robot is not None and self.robot is not robot:
                    return False
                if self.robot is None:
                    return False
            stop_error = None
            try:
                if expected:
                    self.stop_motion(reason)
                else:
                    self.motion.cancel_all(reason)
            except Exception as exc:
                stop_error = exc
            if expected and stop_error is not None:
                message = f"CR5 断开前停止失败：{stop_error}"
                if self.state != "closed":
                    self._set_state("fault", message)
                self._event("error", message)
                raise stop_error
            with self._state_lock:
                self.robot = None
                self._stop_generation += 1
            self._follow_stop.set()
            self._home_stop.set()
            self._replay_stop.set()
            try:
                self.o6.hold_current()
            except Exception as exc:
                self._event("error", f"CR5 掉线后 O6 保持失败: {exc}")
            try:
                self._hold_roarm()
            except Exception as exc:
                self._event("error", f"CR5 掉线后主臂保持失败: {exc}")
            message = f"CR5 连接断开：{reason}"
            if self.state != "closed" and (not expected or stop_error is not None):
                self._set_state("fault", message)
            self._event("info" if expected and stop_error is None else "error", message)
            if stop_error is not None:
                raise stop_error
            return True

    def _set_state(self, state: str, error: str = "") -> None:
        with self._state_lock:
            self._state = state
            self._last_error = error

    def _event(self, level: str, message: str, *, domain="teleop") -> None:
        getattr(logging.getLogger(f"workbench.{domain}"), level)(
            message, exc_info=level == "error" and sys.exc_info()[0] is not None,
        )
        self.events.put((level, message))

    def _hold_roarm(self) -> None:
        if getattr(self.roarm, "passive", False):
            return
        if self.roarm.connected:
            self.roarm.hold_current()
        elif getattr(self.roarm, "io_alive", False):
            # 通信线程仍存活但反馈已报错时，不再使用旧位置移动，只重新上力矩。
            self.roarm.lock_torque()

    def connect_master(self) -> Any:
        if self._shutdown_requested.is_set():
            raise RuntimeError("程序正在退出，禁止连接主臂")
        master_feedback = self.roarm.connect()
        if self._shutdown_requested.is_set():
            self.roarm.close(hold=False)
            raise RuntimeError("程序退出已取消主臂连接")
        if self.master_type == "gello":
            self._event(
                "info",
                "GELLO 主臂已连接: "
                + ", ".join(
                    f"J{index + 1}={value:.3f}"
                    for index, value in enumerate(master_feedback.joints_rad)
                ),
            )
            return master_feedback
        if self.master_type == "inverse3":
            orientation_status = (
                f"，ABC={list(master_feedback.rpy_rad)}"
                if master_feedback.rpy_rad is not None
                else "，VerseGrip 未检测到（仅 XYZ 监视，禁止 6D 跟随）"
            )
        else:
            orientation_status = ""
        self._event(
            "info",
            f"{self.master_type} 主臂已连接: XYZ="
            f"[{master_feedback.x:.1f}, {master_feedback.y:.1f}, "
            f"{master_feedback.z:.1f}] mm{orientation_status}",
        )
        return master_feedback

    def connect_devices(self) -> None:
        master_feedback = self.connect_master()
        if self._shutdown_requested.is_set():
            self.roarm.close(hold=False)
            raise RuntimeError("程序退出已取消主臂/O6 连接")
        o6_position = self.o6.connect()
        if self._shutdown_requested.is_set():
            self.o6.close()
            self.roarm.close(hold=False)
            raise RuntimeError("程序退出已取消主臂/O6 连接")
        o6_cfg = self.store.data["o6"]
        self.o6.set_profile(o6_cfg["speed"], o6_cfg["torque"])
        if self.master_type == "gello":
            self._event(
                "info",
                f"GELLO/O6 已连接: J1-J6={list(master_feedback.arm_joints_rad)}, "
                f"J7={master_feedback.gripper:.3f}, O6={list(o6_position)}",
            )
            return
        self._event(
            "info",
            f"{self.master_type}/O6 已连接: 主臂 XYZ="
            f"[{master_feedback.x:.1f}, {master_feedback.y:.1f}, {master_feedback.z:.1f}], "
            f"O6={list(o6_position)}",
        )

    def _set_dataset_target_tcp(self, tcp: Sequence[Any]) -> None:
        # NRC Cartesian targets stay in their native [mm, rad] convention
        # here. dataset_sample() combines this command with same-cycle TCP
        # feedback and exposes the OpenPI action as delta [m, rad].
        controller_values = tuple(float(value) for value in tcp[:6])
        if len(controller_values) != 6 or any(
            not math.isfinite(value) for value in controller_values
        ):
            raise ValueError("CR5 数据集 TCP action 必须是 6 个有限数值")
        with self._state_lock:
            self._dataset_target_tcp_controller = controller_values
            self._dataset_action_timestamp = time.monotonic()

    def _set_dataset_target_joints(self, joints_deg: Sequence[Any]) -> None:
        # Store the active motion target in SDK degree units for capture.
        controller_values = tuple(float(value) for value in joints_deg[:6])
        if len(controller_values) != 6 or any(
            not math.isfinite(value) for value in controller_values
        ):
            raise ValueError("CR5 数据集 joint action 必须是 6 个有限数值")
        with self._state_lock:
            self._dataset_target_joints_deg = controller_values
            self._dataset_action_timestamp = time.monotonic()

    def start_follow(self) -> None:
        return self.teleop_service.start_follow()

    def start_external_control(self, controller, stop_generation: int, *, motion_view=None) -> None:
        """Reserve the existing motion producer slot for the DAgger arbiter."""
        with self._state_lock:
            if self._state != "idle" or self._home_lock.locked():
                raise RuntimeError("请先停止主从跟随或回位，再启动 DAgger")
            if self._follow_thread is not None and self._follow_thread.is_alive():
                raise RuntimeError("已有运动线程，禁止并行启动 DAgger")
            if self._shutdown_requested.is_set() or self._stop_generation != stop_generation:
                raise RuntimeError("DAgger 启动已被停止或退出取消")
            self._follow_stop.clear()
            lease = self.motion.acquire(MotionSource.POLICY, on_cancel=self._follow_stop.set)
            self._policy_lease = lease
            self.external_control = controller
            self._state = "dagger"
        try:
            if motion_view is not None:
                motion_view.bind(lease)
            controller.robot.start_control()
        except Exception as exc:
            lease.release(error=str(exc))
            if self.external_control is controller:
                self.external_control = None
            if self.state == "dagger":
                self._set_state("fault", str(exc))
            raise
        with self._state_lock:
            cancelled = (
                self._stop_generation != stop_generation
                or self._follow_stop.is_set()
                or not lease.active
            )
            if not cancelled:
                self._state = "dagger"
                self._last_error = ""
                self._follow_thread = threading.Thread(
                    target=self._external_control_loop,
                    args=(controller, lease),
                    name="DAgger-Control",
                    daemon=True,
                )
                self._start_motion_worker(self._follow_thread, lease)
        if cancelled:
            try:
                controller.request_stop()
            finally:
                lease.release()
            raise RuntimeError("DAgger 启动已被停止取消")

    def _external_control_loop(self, controller, lease: MotionLease) -> None:
        failure = None
        try:
            controller.run(stop_event=self._follow_stop)
        except MotionPreempted:
            pass
        except Exception as exc:
            if self.state == "dagger" and self._motion_failure(lease, exc):
                failure = str(exc)
                self._set_state("fault", str(exc))
            self._event("error", f"DAgger 已停止：{exc}")
        finally:
            try:
                controller.request_stop()
            except Exception as exc:
                if self.state == "dagger" and self._motion_failure(lease, exc):
                    failure = str(exc)
                    self._set_state("fault", str(exc))
                self._event("error", f"DAgger 停止失败：{exc}")
            if failure is not None and self.motion.current_owner is None:
                self.o6.hold_current()
            try:
                lease.release(error=failure)
            except Exception as exc:
                if self.state in ("dagger", "fault"):
                    self._set_state("fault", str(exc))
                self._event("error", f"DAgger 运动释放失败：{exc}")
            if self.state == "dagger":
                self._set_state("idle")

    def _motion_failure(self, lease: MotionLease, error: Exception) -> bool:
        """Distinguish a rejected current command from a superseded worker."""
        status = self.motion.status
        return lease.active or (status.source is None and status.error == str(error))

    def _join_follow_producer(self, reason: str) -> None:
        """Drain a producer after arbitration has revoked its command lease."""
        self._follow_stop.set()
        if self.external_control is not None:
            self.external_control.request_stop()
        thread = self._follow_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
            if thread.is_alive():
                raise TimeoutError(f"{reason}: motion producer did not exit")
        self.finish_external_control()

    def _start_motion_worker(self, thread: threading.Thread, lease: MotionLease) -> None:
        try:
            thread.start()
        except Exception as exc:
            lease.release(error=str(exc))
            self._set_state("fault", str(exc))
            raise

    def stop_follow(self, reason: str = "人工停止") -> None:
        if self.state == "point_move":
            self.point_motion.stop()
            return
        if self.state == "replay" and self.replaying:
            # A general stop-follow request must not silently restart following.
            self.stop_trajectory_replay()
            self._event("info", f"关节重放已停止：{reason}")
            return
        stop_error = None
        try:
            self.motion.stop_current(reason)
        except Exception as exc:
            stop_error = exc
        self._follow_stop.set()
        try:
            if self.master_type == "gello" or self.external_control is not None:
                self.o6.hold_current()
        except Exception as exc:
            stop_error = stop_error or exc
        if self.external_control is not None:
            self.external_control.request_stop()
        thread = self._follow_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        try:
            self._hold_roarm()
        except Exception as exc:
            self._event("error", f"主臂保持失败: {exc}")
        if thread is not None and thread.is_alive():
            message = "XYZ 跟随线程未能在 2 秒内停止"
            self._set_state("fault", message)
            raise TimeoutError(message)
        self.finish_external_control()
        if stop_error is not None:
            self._set_state("fault", str(stop_error))
            raise stop_error
        if self.state in ("following", "master_free"):
            self._set_state("idle")
        self._event("info", f"跟随已停止：{reason}")

    def finish_external_control(self) -> None:
        """Finalize DAgger only after its motion producer has stopped."""
        controller = self.external_control
        if controller is None:
            return
        if self._follow_thread is not None and self._follow_thread.is_alive():
            raise RuntimeError("DAgger 运动线程仍在运行，不能关闭记录器")
        controller.stop()
        self._last_dagger_snapshot = controller.snapshot()
        self.external_control = None

    def recover_o6_motor(self, motor_number: int) -> dict[str, Any]:
        return self.hand_actions.recover_o6_motor(motor_number)

    def execute_o6_action(self, action_name: str) -> tuple[int, ...]:
        return self.hand_actions.execute_o6_action(action_name)

    def _follow_loop(
        self, master_origin: Any, slave_origin: Sequence[float], lease: MotionLease
    ) -> None:
        return self.teleop_service._follow_loop(master_origin, slave_origin, lease)

    def save_home(self) -> dict[str, Any]:
        return self.home_service.save_home()

    def set_recording_snapshot(self, provider) -> None:
        """Share Episode ownership with direct runtime motion entry points."""
        self._recording_snapshot = provider

    def return_home(self) -> None:
        return self.home_service.return_home()

    def operation_snapshot(self) -> dict[str, Any]:
        """Cached observations used by command policy, without device I/O."""
        motion = self.motion.status
        with self._state_lock:
            return {
                "state": self._state,
                "error": self._last_error,
                "o6_action_active": self._o6_action_active,
                "motion": {
                    "source": motion.source.name if motion.source is not None else None,
                    "running": motion.running,
                },
            }

    def acknowledge_fault(self) -> None:
        """Clear the local runtime fault latch after hardware recovery.

        This method sends no robot/hand/master command. The caller must first
        verify that the underlying hardware recovery/reset has succeeded.
        """
        with self._state_lock:
            if self._state == "closed":
                raise RuntimeError("遥操作引擎已经关闭")
            if self._state not in ("fault", "idle"):
                raise RuntimeError(f"当前运行态 {self._state} 不允许确认故障恢复")
            self._state = "idle"
            self._last_error = ""
        self._event(
            "info",
            "运行时故障已确认清除；保持 idle，不会自动恢复主从跟随",
        )

    def stop_motion(self, reason="人工停止运动"):
        """Stop any motion producer without changing the Episode lifecycle."""
        with self._state_lock:
            self._stop_generation += 1
            self._follow_stop.set()
            self._home_stop.set()
            self._replay_stop.set()
            self._hand_action_stop.set()
        self.motion.cancel_all(reason)
        self._join_follow_producer(reason)
        self.point_motion.stop()
        self.trajectory_player.stop()
        self._wait_home_completion()
        thread = self._replay_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(3)
            if thread.is_alive():
                raise TimeoutError(f"{thread.name} 未及时停止")
        if self.o6.connected:
            self.o6.hold_current()
        self._hold_roarm()
        if self.state not in ("fault", "closed"):
            self._set_state("idle")
        self._event("info", reason)

    def _wait_home_completion(self) -> None:
        """Drain one HOME operation, whose command worker may remain alive."""
        with self._state_lock:
            owner = self._home_thread
            completed = self._home_completed
        if owner is not None and owner is not threading.current_thread():
            if not completed.wait(3.0):
                raise TimeoutError("HOME 回位操作未及时停止")

    def refresh_robot_status(self):
        """Explicit diagnostic I/O runs on the application command worker."""
        robot = self.robot
        if robot is None:
            raise RuntimeError("机器人未连接")
        joints = self.trajectory_source.read_joints()
        tcp = self.trajectory_source.read_tcp()
        self._diagnostics = {
            "joint_rad": joints,
            "tcp": tcp.vector(),
            "servo_state": robot.servo_state(),
            "sampled_at": time.monotonic(),
        }
        return dict(self._diagnostics)

    def emergency_stop(self, reason: str = "软件紧急停止") -> None:
        """Stop commanded motion; this does not replace the cabinet E-stop."""
        with self._state_lock:
            self._stop_generation += 1
            self._follow_stop.set()
            self._home_stop.set()
            self._hand_action_stop.set()
            self._record_stop.set()
            self._replay_stop.set()
        errors: list[str] = []
        try:
            self.motion.cancel_all(reason)
        except Exception as exc:
            errors.append(f"CR5: {exc}")
        if self.external_control is not None:
            try:
                self.external_control.request_stop()
            except Exception as exc:
                errors.append(f"DAgger: {exc}")
        try:
            self.o6.hold_current()
        except Exception as exc:
            errors.append(f"O6: {exc}")
        try:
            self._hold_roarm()
        except Exception as exc:
            errors.append(f"主臂: {exc}")
        message = reason if not errors else reason + "；" + "；".join(errors)
        self._set_state("fault", message)
        self._event("error", message)

    def shutdown(self, *, close_devices: bool = True) -> None:
        self._shutdown_requested.set()
        with self._state_lock:
            self._stop_generation += 1
            self._follow_stop.set()
            self._home_stop.set()
            self._hand_action_stop.set()
            self._record_stop.set()
            self._replay_stop.set()
        errors = []
        try:
            self.stop_follow("程序退出")
        except Exception as exc:
            errors.append(exc)
        if self.robot is not None:
            try:
                self.motion.cancel_all("Shutdown")
            except Exception as exc:
                errors.append(exc)
        home_stopped = True
        try:
            self._wait_home_completion()
        except Exception as exc:
            home_stopped = False
            errors.append(exc)
        for thread in (
            self._record_thread,
            self._replay_thread,
            self.point_motion.thread,
        ):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=3.0)
                if thread.is_alive():
                    errors.append(TimeoutError(f"Thread did not stop: {thread.name}"))
        if close_devices and home_stopped:
            for close in (self.o6.close, lambda: self.roarm.close(hold=True)):
                try:
                    close()
                except Exception as exc:
                    errors.append(exc)
        self._set_state("closed")
        if errors:
            raise ExceptionGroup("Teleop shutdown incomplete", errors)

    def dataset_sample(self) -> dict[str, Any]:
        return self.capture_snapshot.dataset_sample()

    def snapshot(self) -> dict[str, Any]:
        master = self.roarm.latest()
        o6_position, o6_fault, o6_timestamp = self.o6.latest()
        with self._state_lock:
            frames = self.trajectory_recorder.frames
            record_count = len(frames)
            record_duration = frames[-1].timestamp if frames else 0.0
            o6_action_name = self._o6_action_name
            gello_telemetry = (
                dict(self._gello_telemetry) if self._gello_telemetry is not None else None
            )
        motion = self.motion.status
        return {
            "motion": {
                "source": motion.source.name if motion.source is not None else None,
                "mode": motion.mode.name,
                "running": motion.running,
                "started_at": motion.started_at,
                "last_command_at": motion.last_command_at,
                "error": motion.error,
            },
            "state": self.state,
            "error": self.last_error,
            "dagger": self.external_control.snapshot()
            if self.external_control is not None
            else self._last_dagger_snapshot,
            "master_type": self.master_type,
            "gello_telemetry": gello_telemetry,
            "master": master,
            "roarm": master,
            "o6_position": o6_position,
            "o6_fault": o6_fault,
            "o6_timestamp": o6_timestamp,
            "o6_phase": self.o6.phase,
            "o6_manual_override": self.o6_manual_override,
            "o6_action_active": self.o6_action_active,
            "o6_action_name": o6_action_name,
            "recording": self.recording,
            "record_count": record_count,
            "record_duration": record_duration,
            "replaying": self.replaying,
            "planning": self.point_motion.snapshot(),
            "diagnostics": {
                **getattr(self, "release_info", {}),
                **self._diagnostics,
                "last_command_at": motion.last_command_at,
            },
            "trajectory": {
                "items": list(self._trajectory_catalog),
                "preview": self._trajectory_preview,
                "recording": self.recording,
                "playing": self.replaying,
                "frame_count": record_count,
                "duration_s": record_duration,
                "pending": self._pending_trajectory is not None,
                "recording_error": self.trajectory_recorder.error,
                "active_id": self._trajectory_active_id,
            },
            "presets": sorted(self.store.data.get("presets", {}).keys()),
        }

    def _clear_follow_targets(self) -> None:
        self._gello_telemetry = None
        self._dataset_target_tcp_controller = None
        self._dataset_target_joints_deg = None
        self._dataset_action_timestamp = 0.0

    def _publish_gello_telemetry(self, telemetry: dict[str, Any]) -> None:
        self._gello_telemetry = telemetry

    @property
    def stop_generation(self) -> int:
        with self._state_lock:
            return self._stop_generation

    def devices_connected(self) -> bool:
        return bool(self.roarm.connected and self.o6.connected)

    @property
    def _record_thread(self):
        return self.trajectory_recorder.thread

    def start_trajectory_recording(self, name, *, on_finished=None):
        return self.trajectory_service.start_trajectory_recording(name, on_finished=on_finished)

    def stop_trajectory_recording(self):
        return self.trajectory_service.stop_trajectory_recording()

    def save_trajectory(self):
        return self.trajectory_service.save_trajectory()

    def cancel_trajectory_recording(self):
        return self.trajectory_service.cancel_trajectory_recording()

    def list_trajectories(self):
        return self.trajectory_service.list_trajectories()

    def preview_trajectory(self, trajectory_id):
        return self.trajectory_service.preview_trajectory(trajectory_id)

    def import_trajectory(self, path, source="legacy_json", episode_index=0):
        return self.trajectory_service.import_trajectory(path, source, episode_index)

    def replay_trajectory(self, trajectory_id, options: ReplayOptions, *, on_finished=None):
        return self.trajectory_service.replay_trajectory(
            trajectory_id, options, on_finished=on_finished
        )

    def _play_trajectory_worker(self, value, options, lease, generation, on_finished):
        return self.trajectory_service._play_trajectory_worker(
            value, options, lease, generation, on_finished
        )

    def stop_trajectory_replay(self):
        return self.trajectory_service.stop_trajectory_replay()
