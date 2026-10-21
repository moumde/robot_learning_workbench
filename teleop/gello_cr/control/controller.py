"""Threaded GELLO following, independent of UI and dataset persistence.

Device adapters own I/O. Hooks publish motion state and command telemetry to
application orchestration without coupling the control loop to a recorder.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from teleop.gello_cr.control.contracts import TeleopHooks
from teleop.gello_cr.control.geometry import (
    _nrc_abc_to_quaternion,
    _quaternion_distance,
    _quaternion_inverse,
    _quaternion_multiply,
    _quaternion_slerp,
    _quaternion_to_nrc_abc,
    _quaternion_to_nrc_abc_near,
    _rotation_matrix_to_quaternion,
    _wrapped_angle_delta,
)
from teleop.gello_cr.devices.gello import GelloFeedback
from teleop.gello_cr.motion import (
    JointTarget,
    MotionCoordinator,
    MotionLease,
    MotionPreempted,
    MotionSource,
)
from teleop.gello_cr.support.errors import TeleopError

from .hand_mapping import binary_o6_action, interpolate_o6_target, should_send_o6_target
from .joint_mapping import RelativeJointMapper
from .joint_safety import (
    LeaderSpeedViolationCounter,
    max_command_step_violation,
    max_tracking_error_violation,
)
from .kinematics import GelloKinematics


class TeleopController:
    """Map GELLO feedback to safe robot and hand commands in one worker thread."""

    def __init__(
        self,
        store: Any,
        master: Any,
        hand: Any,
        *,
        robot: Callable[[], Any],
        hooks: TeleopHooks,
        motion: MotionCoordinator,
    ) -> None:
        self.store = store
        self.master = master
        self.hand = hand
        self._robot = robot
        self.hooks = hooks
        self.motion = motion
        self._thread: threading.Thread | None = None
        self._lease: MotionLease | None = None

    @property
    def robot(self) -> Any:
        return self._robot()

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        lease = self._lease
        self.hooks.stop.set()
        if lease is not None:
            try:
                lease.stop()
                self._hold_hand(lease)
            except MotionPreempted:
                pass
            finally:
                lease.release()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        if self.running:
            raise TimeoutError("GELLO 跟随线程未能在 2 秒内停止")

    def _finish_motion(self, lease: MotionLease, error: Exception | None) -> None:
        """Finish only this worker's command channel and hand ownership."""
        try:
            lease.stop()
        except Exception as exc:
            error = exc
            if self._owns_failure(lease, exc) and self.hooks.state() == "following":
                self.hooks.set_state("fault", str(exc))
            self.hooks.event("error", f"CR5 停止失败: {exc}")
        try:
            self._hold_hand(lease, error)
        except MotionPreempted:
            pass
        except Exception as exc:
            self.hooks.event("error", f"O6 保持失败: {exc}")
        with self.hooks.lock:
            if not error and lease.active and self.hooks.state() == "following":
                self.hooks.set_state("idle", "")
        try:
            lease.release(error=error)
        except Exception as exc:
            if self._owns_failure(lease, exc) and self.hooks.state() in ("idle", "following"):
                self.hooks.set_state("fault", str(exc))
            self.hooks.event("error", f"CR5 运动所有权释放失败: {exc}")

    def _owns_failure(self, lease: MotionLease, error: Exception) -> bool:
        # Safety and SDK failures revoke the lease before returning the error.
        status = self.motion.status
        return lease.active or (status.source is None and status.error == str(error))

    def _hold_hand(self, lease: MotionLease, error: Exception | None = None) -> None:
        with self.hooks.lock:
            try:
                lease.check()
            except MotionPreempted:
                if (
                    error is None
                    or self.hooks.state() != "fault"
                    or not self._owns_failure(lease, error)
                ):
                    raise
            self.hand.hold_current()

    def _ready_to_dispatch(
        self,
        lease: MotionLease,
        master: GelloFeedback,
        stop_generation: int,
        master_timeout: float,
        hand_timeout: float,
    ) -> bool:
        """Recheck the samples and cancellation after potentially blocking device calls."""
        lease.check()
        if (
            self.hooks.stop.is_set()
            or self.hooks.shutdown.is_set()
            or self.hooks.generation() != stop_generation
        ):
            return False
        now = time.monotonic()
        if now - master.timestamp > master_timeout:
            raise TeleopError("GELLO 反馈掉线/超时")
        if self.master.error:
            raise TeleopError(self.master.error)
        position, fault, sampled_at = self.hand.latest()
        if self.hand.error:
            raise TeleopError(self.hand.error)
        if position is None or now - sampled_at > hand_timeout:
            raise TeleopError("O6 反馈掉线/超时")
        if fault is None or any(fault):
            raise TeleopError(f"O6 故障: {fault}")
        return True

    def start(self, master: GelloFeedback, stop_generation: int) -> None:
        if self.robot is None:
            raise TeleopError("请先连接 CR5")
        slave_joints = [float(value) for value in self.robot.joint_position()]
        if len(slave_joints) != 7:
            raise TeleopError("CR5 反馈必须包含 7 个关节值")
        gello_cfg = self.store.data["gello"]
        gello_mode = str(gello_cfg.get("control_mode", "joint"))
        urdf_path = Path(str(gello_cfg["kinematics_urdf"])).expanduser()
        if not urdf_path.is_absolute():
            urdf_path = self.store.path.parent / urdf_path
        kinematics = GelloKinematics(urdf_path) if gello_mode != "joint" else None
        robot_cfg = self.store.data["robot"]
        with self.hooks.lock:
            # HOME reserves its cancellation generation under this same lock.
            # Reject stale startup before acquire can clear HOME's accepted target.
            if self.hooks.shutdown.is_set() or self.hooks.generation() != stop_generation:
                raise TeleopError("GELLO 跟随启动已被停止或 HOME 取消")
            lease = self.motion.acquire(MotionSource.TELEOP, on_cancel=self.hooks.stop.set)
            self._lease = lease
        try:
            with self.hooks.lock:
                lease.check()
                if self.hooks.shutdown.is_set() or self.hooks.generation() != stop_generation:
                    raise TeleopError("GELLO 跟随启动已被软件紧急停止")
                self.hooks.stop.clear()
                self.hooks.reset_targets()
            # Prime feedback before the loop's final freshness/cancellation guard.
            # The NRC adapter leaves its native ServoJ channel closed in MoveJ mode.
            lease.open_servo(
                robot_cfg["servoj_vmax"],
                robot_cfg["servoj_amax"],
                robot_cfg["servoj_jmax"],
            )
            with self.hooks.lock:
                lease.check()
                cancelled = (
                    self.hooks.stop.is_set()
                    or self.hooks.shutdown.is_set()
                    or self.hooks.generation() != stop_generation
                )
                if not cancelled:
                    self.hooks.set_state("following", "")
            if cancelled:
                raise TeleopError("GELLO 跟随启动已被软件紧急停止")
            self._thread = threading.Thread(
                target=self._gello_follow_loop,
                args=(master, slave_joints, stop_generation, lease, kinematics),
                name="GELLO-CR5-Follow",
                daemon=True,
            )
            self._thread.start()
        except Exception as exc:
            with self.hooks.lock:
                if (
                    self._owns_failure(lease, exc)
                    and self.hooks.generation() == stop_generation
                    and self.hooks.state() in ("idle", "following")
                ):
                    self.hooks.set_state("fault", str(exc))
            try:
                self._hold_hand(lease, exc)
            except MotionPreempted:
                pass
            finally:
                lease.release(error=exc)
            raise
        motion_mode = getattr(self.robot, "motion_mode", "servoj")
        if motion_mode == "movej":
            self.hooks.event(
                "info",
                "CR3A MoveJ 跟随已准备："
                f"速度/加速度/减速度={robot_cfg['movej_velocity']}/"
                f"{robot_cfg['movej_acc']}/{robot_cfg['movej_dec']}%，"
                f"指令周期={robot_cfg['movej_period_s']}s；"
                f"短段实验={'开' if robot_cfg['movej_low_latency'] else '关'}，"
                f"单段上限={robot_cfg['movej_max_segment_deg']}°，"
                f"J1-J6倍率={gello_cfg['joint_scale']:.2f}×",
            )
        else:
            self.hooks.event(
                "info",
                f"CR3A {motion_mode} 指令通道已准备；SDK 返回成功不代表从臂已执行。"
                f" ServoJ 参数 v/a/j={robot_cfg['servoj_vmax']}/"
                f"{robot_cfg['servoj_amax']}/{robot_cfg['servoj_jmax']}",
            )
        self.hooks.event(
            "info",
            "GELLO 跟随已启动："
            + (
                "完整 TCP 6D IK：J1-J6 控制 CR3A TCP XYZ+ABC，J7 控制 O6"
                if gello_mode == "tcp_6d"
                else "J1-J5 控制 CR3A XYZ，J6 通过 TCP-C IK 控制 CR3A J6，J7 控制 O6"
                if gello_mode == "xyz_j6_tcp_ik"
                else "J1-J5 控制 CR3A XYZ，J6 直接控制 CR3A J6，J7 控制 O6"
                if gello_mode == "xyz_j6"
                else "J1-J6 控制 CR3A 关节，J7 控制 O6"
            )
            + "；使用当前姿态相对零点",
        )

    def _gello_follow_loop(
        self,
        master_origin: GelloFeedback,
        slave_origin: Sequence[float],
        stop_generation: int,
        lease: MotionLease,
        kinematics: GelloKinematics | None = None,
    ) -> None:
        if kinematics is not None:
            self._gello_xyz_j6_follow_loop(
                master_origin, slave_origin, stop_generation, lease, kinematics
            )
            return
        error: Exception | None = None
        try:
            cfg = self.store.data
            robot_cfg = cfg["robot"]
            gello_cfg = cfg["gello"]
            o6_cfg = cfg["o6"]
            joint_mapper = RelativeJointMapper(
                joint_scale=float(gello_cfg["joint_scale"]),
                locked_joints=tuple(int(value) for value in gello_cfg["locked_joints"]),
            )
            motion_mode = getattr(self.robot, "motion_mode", "servoj")
            low_latency = motion_mode == "movej" and bool(robot_cfg["movej_low_latency"])
            max_segment_deg = float(robot_cfg["movej_max_segment_deg"])
            period = 1.0 / float(gello_cfg["feedback_hz"])
            if getattr(self.robot, "motion_mode", "servoj") == "movej":
                period = max(period, float(getattr(self.robot, "movej_period_s", period)))
            master_timeout = float(gello_cfg["feedback_timeout_s"])
            o6_timeout = float(o6_cfg["feedback_timeout_s"])
            step_limit = float(robot_cfg.get("safety_max_command_step_rad", math.radians(20.0)))
            speed_limit = float(robot_cfg.get("safety_max_command_speed_rad_s", 0.8))
            tracking_limit = float(
                robot_cfg.get("safety_max_tracking_error_rad", math.radians(20.0))
            )
            speed_cycles = int(robot_cfg.get("safety_speed_violation_cycles", 3))
            leader_origin = np.asarray(master_origin.arm_joints_rad, dtype=float)
            last_leader = leader_origin.copy()
            last_leader_timestamp = master_origin.timestamp
            commanded = np.asarray(slave_origin[:6], dtype=float)
            last_target = commanded.copy()
            speed_guard = LeaderSpeedViolationCounter()
            next_cycle = time.monotonic()
            startup_settle_deadline = next_cycle + float(gello_cfg.get("startup_settle_s", 0.5))
            last_hand_action: str | None = None
            last_servoj_log_time = 0.0
            sent_count = 0
            first_sent_at = 0.0
            last_sent_at = 0.0
            last_validated_at = 0.0
            last_diagnostic_at = next_cycle
            window_sent = 0
            recent_send_hz = 0.0
            busy_since: float | None = None
            last_busy_wait_ms = 0.0
            while not self.hooks.stop.is_set():
                lease.check()
                now = time.monotonic()
                master = self.master.latest()
                if master is None or now - master.timestamp > master_timeout:
                    raise TeleopError("GELLO 反馈掉线/超时")
                if self.master.error:
                    raise TeleopError(self.master.error)
                o6_position, o6_fault, o6_timestamp = self.hand.latest()
                if self.hand.error:
                    raise TeleopError(self.hand.error)
                if o6_position is None or now - o6_timestamp > o6_timeout:
                    raise TeleopError("O6 反馈掉线/超时")
                if o6_fault is None or any(o6_fault):
                    raise TeleopError(f"O6 故障: {o6_fault}")
                if self.hooks.generation() != stop_generation:
                    lease.check()
                    raise TeleopError("GELLO 跟随已被软件紧急停止")
                if now < startup_settle_deadline:
                    leader_origin = np.asarray(master.arm_joints_rad, dtype=float)
                    last_leader = leader_origin.copy()
                    last_leader_timestamp = master.timestamp
                    last_target = commanded.copy()
                    speed_guard.reset()
                    next_cycle += period
                    wait_time = next_cycle - time.monotonic()
                    if wait_time > 0:
                        self.hooks.stop.wait(wait_time)
                    else:
                        next_cycle = time.monotonic()
                    continue
                live_robot_cfg = self.store.data["robot"]
                step_limit = float(
                    live_robot_cfg.get("safety_max_command_step_rad", math.radians(20.0))
                )
                speed_limit = float(live_robot_cfg.get("safety_max_command_speed_rad_s", 0.8))
                tracking_limit = float(
                    live_robot_cfg.get("safety_max_tracking_error_rad", math.radians(20.0))
                )
                speed_cycles = int(live_robot_cfg.get("safety_speed_violation_cycles", 3))

                warning_before = self.robot.controller_job_warning if motion_mode == "movej" else ""
                if warning_before and busy_since is None:
                    busy_since = time.monotonic()
                busy_check_ms = 0.0
                dispatch_ready = True
                if low_latency:
                    check_started = time.monotonic()
                    dispatch_ready = self.robot.clear_movej_busy_if_stopped()
                    busy_check_ms = (time.monotonic() - check_started) * 1000.0
                    read_started = time.monotonic()
                    actual = np.asarray(self.robot.joint_position()[:6], dtype=float)
                    feedback_at = time.monotonic()
                    feedback_read_ms = (feedback_at - read_started) * 1000.0
                    # The NRC request may block; construct the segment from samples
                    # fetched after it, and recheck freshness before issuing motion.
                    master = self.master.latest()
                    now = time.monotonic()
                    if master is None or now - master.timestamp > master_timeout:
                        raise TeleopError("GELLO 反馈掉线/超时")
                    if self.master.error:
                        raise TeleopError(self.master.error)
                    o6_position, o6_fault, o6_timestamp = self.hand.latest()
                    if self.hand.error:
                        raise TeleopError(self.hand.error)
                    if o6_position is None or now - o6_timestamp > o6_timeout:
                        raise TeleopError("O6 反馈掉线/超时")
                    if o6_fault is None or any(o6_fault):
                        raise TeleopError(f"O6 故障: {o6_fault}")
                    if self.hooks.stop.is_set():
                        break
                    if self.hooks.generation() != stop_generation:
                        lease.check()
                        raise TeleopError("GELLO 跟随已被软件紧急停止")

                leader = np.asarray(master.arm_joints_rad, dtype=float)
                target = np.asarray(
                    joint_mapper.target_deg(
                        leader,
                        leader_origin,
                        commanded,
                    ),
                    dtype=float,
                )
                step_violation = max_command_step_violation(
                    target,
                    last_target,
                    step_limit,
                )
                if step_violation is not None:
                    raise TeleopError(
                        f"GELLO J{step_violation.joint_number} command step "
                        f"{step_violation.value:.4f}rad exceeds "
                        f"{step_violation.limit:.4f}rad"
                    )
                if master.timestamp != last_leader_timestamp:
                    leader_delta_rad = np.asarray(
                        joint_mapper.leader_delta_rad(
                            leader,
                            last_leader,
                        ),
                        dtype=float,
                    )
                    speed_sample = speed_guard.update(
                        leader_delta_rad,
                        master.timestamp - last_leader_timestamp,
                        speed_limit,
                        speed_cycles,
                    )
                    if speed_sample.violation is not None:
                        violation = speed_sample.violation
                        raise TeleopError(
                            f"GELLO J{violation.joint_number} leader speed "
                            f"{violation.value:.3f}rad/s exceeds "
                            f"{violation.limit:.3f}rad/s"
                        )
                    last_leader = leader.copy()
                    last_leader_timestamp = master.timestamp

                if not low_latency:
                    read_started = time.monotonic()
                    actual = np.asarray(self.robot.joint_position()[:6], dtype=float)
                    feedback_at = time.monotonic()
                    feedback_read_ms = (feedback_at - read_started) * 1000.0
                tracking_violation = max_tracking_error_violation(
                    last_target,
                    actual,
                    tracking_limit,
                )
                if tracking_violation is not None:
                    index = tracking_violation.joint_number - 1
                    raise TeleopError(
                        f"CR5 J{tracking_violation.joint_number} tracking error "
                        f"{tracking_violation.value:.4f}rad exceeds "
                        f"{tracking_violation.limit:.4f}rad; "
                        f"target={last_target[index]:.3f}deg, "
                        f"actual={actual[index]:.3f}deg"
                    )

                desired_target = target.copy()
                desired_error_deg = float(np.max(np.abs(desired_target - actual)))
                if low_latency:
                    # A short segment must not hide an unsafe full leader/follower gap.
                    if math.radians(desired_error_deg) > tracking_limit:
                        raise TeleopError(
                            f"CR3A 完整期望目标跟踪误差 {desired_error_deg:.2f}° "
                            f"超过 {math.degrees(tracking_limit):.2f}°；短段不会放宽安全限位"
                        )
                    if desired_error_deg > max_segment_deg:
                        target = actual + (desired_target - actual) * (
                            max_segment_deg / desired_error_deg
                        )
                segment_delta_deg = float(np.max(np.abs(target - actual)))
                target_full = target.tolist() + [float(slave_origin[6])]
                validated_target = target.copy()
                dispatch_started = time.monotonic()
                last_validated_at = dispatch_started
                duplicate_deadband = (
                    float(live_robot_cfg["movej_duplicate_deadband_deg"])
                    if motion_mode == "movej"
                    else 0.0
                )
                duplicate_hold = (
                    motion_mode == "movej"
                    and sent_count > 0
                    and float(np.max(np.abs(validated_target - last_target))) <= duplicate_deadband
                    and float(np.max(np.abs(validated_target - actual))) <= duplicate_deadband
                )
                if not self._ready_to_dispatch(
                    lease, master, stop_generation, master_timeout, o6_timeout
                ):
                    break
                sent = (
                    lease.servo_joint(JointTarget.from_degrees(target_full))
                    if dispatch_ready and not duplicate_hold
                    else False
                )
                dispatch_finished = time.monotonic()
                dispatch_ms = (dispatch_finished - dispatch_started) * 1000.0
                leader_age_ms = (dispatch_started - master.timestamp) * 1000.0
                if sent is not False:
                    last_target = target.copy()
                    last_sent_at = time.monotonic()
                    if sent_count == 0:
                        first_sent_at = last_sent_at
                    sent_count += 1
                    window_sent += 1
                    if now - last_servoj_log_time >= 1.0:
                        current_error_deg = np.abs(target - actual)
                        self.hooks.event(
                            "info",
                            f"{getattr(self.robot, 'motion_mode', 'servoj')} 发送/反馈："
                            f"target={[round(float(value), 2) for value in target]}，"
                            f"actual={[round(float(value), 2) for value in actual]}，"
                            f"max_err={float(np.max(current_error_deg)):.2f}°",
                        )
                        last_servoj_log_time = now
                warning_after = self.robot.controller_job_warning if motion_mode == "movej" else ""
                if warning_after:
                    if busy_since is None:
                        busy_since = dispatch_finished
                    busy_wait_ms = (dispatch_finished - busy_since) * 1000.0
                else:
                    if busy_since is not None:
                        last_busy_wait_ms = (dispatch_finished - busy_since) * 1000.0
                        busy_since = None
                    busy_wait_ms = 0.0
                phase = (
                    "duplicate_hold"
                    if duplicate_hold
                    else "busy"
                    if warning_after or not dispatch_ready
                    else "submitted"
                    if sent is not False
                    else "idle_deferred"
                    if warning_before
                    else "rate_limited"
                )
                diagnostic_due = dispatch_finished - last_diagnostic_at >= 1.0
                if diagnostic_due:
                    recent_send_hz = window_sent / (dispatch_finished - last_diagnostic_at)
                    last_diagnostic_at = dispatch_finished
                    window_sent = 0
                # Reuse the safety-loop feedback in the UI and recorder. FK is
                # needed only at dataset rate, not on every ServoJ cycle.
                with self.hooks.lock:
                    pending_target_deg = float(np.max(np.abs(validated_target - last_target)))
                    self.hooks.publish_telemetry(
                        {
                            "actual_deg": tuple(float(v) for v in actual),
                            "target_deg": tuple(float(v) for v in last_target),
                            "target_full_deg": tuple(last_target) + (float(slave_origin[6]),),
                            "feedback_at": feedback_at,
                            "command_at": last_sent_at,
                            "validated_at": last_validated_at,
                            "sent_count": sent_count,
                            "send_hz": (
                                (sent_count - 1) / (last_sent_at - first_sent_at)
                                if sent_count > 1
                                else 0.0
                            ),
                            "tracking_error_deg": float(np.max(np.abs(last_target - actual))),
                            "desired_deg": tuple(float(v) for v in desired_target),
                            "desired_tracking_error_deg": desired_error_deg,
                            "validated_deg": tuple(float(v) for v in validated_target),
                            "pending_target_deg": pending_target_deg,
                            "low_latency": low_latency,
                            "latency": {
                                "phase": phase,
                                "leader_age_ms": leader_age_ms,
                                "feedback_read_ms": feedback_read_ms,
                                "busy_check_ms": busy_check_ms,
                                "dispatch_ms": dispatch_ms,
                                "busy_wait_ms": busy_wait_ms,
                                "last_busy_wait_ms": last_busy_wait_ms,
                                "recent_send_hz": recent_send_hz,
                                "segment_delta_deg": segment_delta_deg,
                            },
                        }
                    )
                if diagnostic_due and motion_mode == "movej":
                    self.hooks.event(
                        "info",
                        f"MoveJ 软件时序：短段={'开' if low_latency else '关'}，phase={phase}，"
                        f"GELLO_age={leader_age_ms:.1f}ms，read={feedback_read_ms:.1f}ms，"
                        f"busy_check={busy_check_ms:.1f}ms，dispatch={dispatch_ms:.1f}ms，"
                        f"busy_wait={busy_wait_ms:.1f}ms（上次 {last_busy_wait_ms:.1f}ms），"
                        f"SDK_submit={recent_send_hz:.1f}Hz，span={segment_delta_deg:.2f}°，"
                        f"pending={pending_target_deg:.2f}°，desired_err={desired_error_deg:.2f}°；"
                        "提交不等于执行确认",
                    )

                hand_action = binary_o6_action(
                    master.gripper,
                    open_action=o6_cfg["open_action"],
                    closed_action=o6_cfg["closed_action"],
                )
                if last_hand_action != hand_action:
                    if not self._ready_to_dispatch(
                        lease, master, stop_generation, master_timeout, o6_timeout
                    ):
                        break
                    self.hand.set_target(o6_cfg["actions"][hand_action])
                    last_hand_action = hand_action
                    self.hooks.event(
                        "info",
                        f"GELLO J7 触发 O6 动作：{hand_action}；"
                        f"目标={list(o6_cfg['actions'][hand_action])}",
                    )

                next_cycle += period
                wait_time = next_cycle - time.monotonic()
                if wait_time > 0:
                    self.hooks.stop.wait(wait_time)
                else:
                    next_cycle = time.monotonic()
        except MotionPreempted:
            pass
        except Exception as exc:
            error = exc
            with self.hooks.lock:
                if self.hooks.state() == "following" and self._owns_failure(lease, error):
                    self.hooks.set_state("fault", str(error))
                    self.hooks.event("error", f"GELLO 安全停止：{error}")
        finally:
            self._finish_motion(lease, error)

    def _gello_xyz_j6_follow_loop(
        self,
        master_origin: GelloFeedback,
        slave_origin: Sequence[float],
        stop_generation: int,
        lease: MotionLease,
        kinematics: GelloKinematics,
    ) -> None:
        error: Exception | None = None
        try:
            lease.check()
            cfg = self.store.data
            robot_cfg = cfg["robot"]
            gello_cfg = cfg["gello"]
            o6_cfg = cfg["o6"]
            period = 1.0 / float(gello_cfg["feedback_hz"])
            if getattr(self.robot, "motion_mode", "servoj") == "movej":
                period = max(period, float(getattr(self.robot, "movej_period_s", period)))
            master_timeout = float(gello_cfg["feedback_timeout_s"])
            o6_timeout = float(o6_cfg["feedback_timeout_s"])
            step_limit = float(robot_cfg.get("safety_max_command_step_rad", math.radians(20.0)))
            speed_limit = float(robot_cfg.get("safety_max_command_speed_rad_s", 0.8))
            tracking_limit = float(
                robot_cfg.get("safety_max_tracking_error_rad", math.radians(20.0))
            )
            speed_cycles = int(robot_cfg.get("safety_speed_violation_cycles", 3))
            j6_sign = int(gello_cfg["j6_sign"])
            tcp_ik_mode = str(gello_cfg.get("control_mode")) == "xyz_j6_tcp_ik"
            full_tcp_ik_mode = str(gello_cfg.get("control_mode")) == "tcp_6d"
            leader_origin_joints = np.asarray(master_origin.arm_joints_rad, dtype=float)
            leader_position_joints = leader_origin_joints.copy()
            if not full_tcp_ik_mode:
                leader_position_joints[5] = leader_origin_joints[5]
            leader_origin_pose = kinematics.pose(leader_position_joints)
            leader_origin_xyz = leader_origin_pose[:3, 3].copy()
            leader_origin_rotation = leader_origin_pose[:3, :3].copy()
            base_tcp = np.asarray(self.robot.tcp_position()[:7], dtype=float)
            if len(base_tcp) != 7:
                raise TeleopError("CR3A TCP 反馈必须包含 7 个值")
            slave_origin_orientation = _nrc_abc_to_quaternion(base_tcp[3:6])
            commanded_orientation = slave_origin_orientation
            mapping_slave_origin = base_tcp[:3].copy()
            commanded_xyz = mapping_slave_origin.copy()
            last_sent_target = np.asarray(slave_origin[:7], dtype=float)
            last_j6_target_rad = 0.0
            last_leader_xyz = leader_origin_xyz.copy()
            last_leader_rotation = leader_origin_rotation.copy()
            last_master_timestamp = master_origin.timestamp
            last_j6_change_time = time.monotonic()
            j6_speed_count = 0
            next_cycle = time.monotonic()
            last_cycle_time = next_cycle
            startup_settle_deadline = next_cycle + float(gello_cfg.get("startup_settle_s", 0.5))
            last_hand: tuple[int, ...] | None = None
            while not self.hooks.stop.is_set():
                lease.check()
                now = time.monotonic()
                master = self.master.latest()
                if master is None or now - master.timestamp > master_timeout:
                    raise TeleopError("GELLO 反馈掉线/超时")
                if self.master.error:
                    raise TeleopError(self.master.error)
                o6_position, o6_fault, o6_timestamp = self.hand.latest()
                if self.hand.error:
                    raise TeleopError(self.hand.error)
                if o6_position is None or now - o6_timestamp > o6_timeout:
                    raise TeleopError("O6 反馈掉线/超时")
                if o6_fault is None or any(o6_fault):
                    raise TeleopError(f"O6 故障: {o6_fault}")
                if self.hooks.generation() != stop_generation:
                    lease.check()
                    raise TeleopError("GELLO 跟随已被软件紧急停止")

                leader_joints = np.asarray(master.arm_joints_rad, dtype=float)
                leader_position_joints = leader_joints.copy()
                if not full_tcp_ik_mode:
                    leader_position_joints[5] = leader_origin_joints[5]
                leader_pose = kinematics.pose(leader_position_joints)
                leader_xyz = leader_pose[:3, 3].copy()
                leader_rotation = leader_pose[:3, :3].copy()
                if now < startup_settle_deadline:
                    leader_origin_joints = leader_joints.copy()
                    if not full_tcp_ik_mode:
                        leader_position_joints[5] = leader_origin_joints[5]
                    leader_origin_pose = kinematics.pose(leader_position_joints)
                    leader_origin_xyz = leader_origin_pose[:3, 3].copy()
                    leader_origin_rotation = leader_origin_pose[:3, :3].copy()
                    commanded_orientation = slave_origin_orientation
                    last_leader_xyz = leader_origin_xyz.copy()
                    last_leader_rotation = leader_origin_rotation.copy()
                    last_sent_target = np.asarray(slave_origin[:7], dtype=float)
                    last_j6_target_rad = 0.0
                    last_j6_change_time = now
                    j6_speed_count = 0
                    next_cycle += period
                    wait_time = next_cycle - time.monotonic()
                    if wait_time > 0:
                        self.hooks.stop.wait(wait_time)
                    else:
                        next_cycle = time.monotonic()
                    continue

                live_teleop_cfg = self.store.data["teleop"]
                live_robot_cfg = self.store.data["robot"]
                step_limit = float(
                    live_robot_cfg.get("safety_max_command_step_rad", math.radians(20.0))
                )
                speed_limit = float(live_robot_cfg.get("safety_max_command_speed_rad_s", 0.8))
                tracking_limit = float(
                    live_robot_cfg.get("safety_max_tracking_error_rad", math.radians(20.0))
                )
                speed_cycles = int(live_robot_cfg.get("safety_speed_violation_cycles", 3))
                live_gello_cfg = self.store.data["gello"]
                axis_map = np.asarray(live_gello_cfg["xyz_axis_map"], dtype=float)
                scales = np.asarray(live_gello_cfg["xyz_scale"], dtype=float)
                if master.timestamp != last_master_timestamp:
                    xyz_jump_mm = float(np.linalg.norm(leader_xyz - last_leader_xyz) * 1000.0)
                    max_master_jump_mm = float(live_teleop_cfg["max_master_jump_mm"])
                    if xyz_jump_mm > max_master_jump_mm:
                        raise TeleopError(
                            f"GELLO XYZ 单帧跳变 {xyz_jump_mm:.1f} mm，"
                            f"超过 {max_master_jump_mm:.1f} mm"
                        )
                    if full_tcp_ik_mode:
                        master_rotation_delta = leader_rotation @ last_leader_rotation.T
                        angular_jump = _quaternion_distance(
                            _rotation_matrix_to_quaternion(master_rotation_delta),
                            (1.0, 0.0, 0.0, 0.0),
                        )
                        max_angular_jump = float(live_teleop_cfg["max_master_angular_jump_rad"])
                        if angular_jump > max_angular_jump:
                            raise TeleopError(
                                f"GELLO 姿态单帧跳变 {angular_jump:.3f}rad，"
                                f"超过 {max_angular_jump:.3f}rad"
                            )
                    last_leader_xyz = leader_xyz.copy()
                    last_leader_rotation = leader_rotation.copy()
                    last_master_timestamp = master.timestamp

                mapped_delta_mm = axis_map @ (leader_xyz - leader_origin_xyz) * 1000.0
                mapped_delta_mm = mapped_delta_mm * scales
                desired_xyz = mapping_slave_origin + mapped_delta_mm
                xyz_limits = np.asarray(live_teleop_cfg["max_delta_xyz_mm"], dtype=float)
                total_delta_mm = desired_xyz - mapping_slave_origin
                for index, axis in enumerate("XYZ"):
                    if abs(total_delta_mm[index]) > xyz_limits[index]:
                        raise TeleopError(
                            f"{axis} 相对位移 {total_delta_mm[index]:.1f} mm 超过 "
                            f"±{xyz_limits[index]:.1f} mm"
                        )

                cycle_dt = max(0.001, now - last_cycle_time)
                last_cycle_time = now
                remaining = desired_xyz - commanded_xyz
                distance = float(np.linalg.norm(remaining))
                max_step_mm = float(live_teleop_cfg["max_tcp_speed_mm_s"]) * cycle_dt
                ratio = min(1.0, max_step_mm / distance) if distance > 1e-9 else 1.0
                commanded_xyz = commanded_xyz + remaining * ratio

                orientation_requested = False
                desired_j6_rad = 0.0
                if full_tcp_ik_mode:
                    leader_relative_rotation = leader_rotation @ leader_origin_rotation.T
                    mapped_relative_rotation = axis_map @ leader_relative_rotation @ axis_map.T
                    relative_orientation = _rotation_matrix_to_quaternion(mapped_relative_rotation)
                    relative_abc = np.asarray(
                        _quaternion_to_nrc_abc(relative_orientation), dtype=float
                    )
                    relative_abc *= np.asarray(live_teleop_cfg["scale_rpy"], dtype=float)
                    desired_orientation = _quaternion_multiply(
                        _nrc_abc_to_quaternion(relative_abc),
                        slave_origin_orientation,
                    )
                    desired_relative = _quaternion_multiply(
                        desired_orientation,
                        _quaternion_inverse(slave_origin_orientation),
                    )
                    desired_abc = _quaternion_to_nrc_abc(desired_relative)
                    rpy_limits = [float(value) for value in live_teleop_cfg["max_delta_rpy_rad"]]
                    for index, axis in enumerate("ABC"):
                        if abs(desired_abc[index]) > rpy_limits[index]:
                            raise TeleopError(
                                f"{axis} 相对转角 {desired_abc[index]:.3f}rad 超过 "
                                f"±{rpy_limits[index]:.3f}rad"
                            )
                    angular_distance = _quaternion_distance(
                        commanded_orientation, desired_orientation
                    )
                    max_angular_step = (
                        float(live_teleop_cfg["max_tcp_angular_speed_rad_s"]) * cycle_dt
                    )
                    angular_ratio = (
                        min(1.0, max_angular_step / angular_distance)
                        if angular_distance > 1e-9
                        else 1.0
                    )
                    commanded_orientation = _quaternion_slerp(
                        commanded_orientation,
                        desired_orientation,
                        angular_ratio,
                    )
                    target_abc = _quaternion_to_nrc_abc_near(commanded_orientation, base_tcp[3:6])
                    orientation_requested = (
                        _quaternion_distance(commanded_orientation, slave_origin_orientation) > 1e-7
                    )
                else:
                    desired_j6_rad = (
                        _wrapped_angle_delta(leader_joints[5], leader_origin_joints[5]) * j6_sign
                    )
                    j6_step_rad = abs(_wrapped_angle_delta(desired_j6_rad, last_j6_target_rad))
                    if j6_step_rad > step_limit:
                        raise TeleopError(
                            f"GELLO J6 command step {j6_step_rad:.4f}rad exceeds "
                            f"{step_limit:.4f}rad"
                        )
                    if j6_step_rad > 1e-9:
                        j6_speed = j6_step_rad / max(0.001, now - last_j6_change_time)
                        if j6_speed > speed_limit:
                            j6_speed_count += 1
                        else:
                            j6_speed_count = 0
                        if j6_speed_count >= speed_cycles:
                            raise TeleopError(
                                f"GELLO J6 leader speed {j6_speed:.3f}rad/s exceeds "
                                f"{speed_limit:.3f}rad/s"
                            )
                        last_j6_change_time = now

                target_tcp = base_tcp.copy()
                target_tcp[:3] = commanded_xyz
                if full_tcp_ik_mode:
                    target_tcp[3:6] = target_abc
                else:
                    target_tcp[3] = base_tcp[3]
                    target_tcp[4] = base_tcp[4]
                    target_tcp[5] = base_tcp[5] + desired_j6_rad
                movement_requested = bool(
                    np.max(np.abs(commanded_xyz - mapping_slave_origin)) > 1e-7
                    or orientation_requested
                    or (not full_tcp_ik_mode and abs(desired_j6_rad) > 1e-7)
                )
                if movement_requested:
                    ik_target_tcp = (
                        target_tcp if (tcp_ik_mode or full_tcp_ik_mode) else base_tcp.copy()
                    )
                    if not tcp_ik_mode and not full_tcp_ik_mode:
                        ik_target_tcp[:3] = commanded_xyz
                        ik_target_tcp[3] = base_tcp[3]
                        ik_target_tcp[4] = base_tcp[4]
                        # Direct J6 mode keeps C fixed while the controller
                        # solves J1-J5 for XYZ, then sets CR3A J6 below.
                        ik_target_tcp[5] = base_tcp[5]
                    target_joints = np.asarray(
                        self.robot.inverse_kinematics(ik_target_tcp.tolist()), dtype=float
                    )
                    if len(target_joints) != 7:
                        raise TeleopError("CR3A 逆运动学必须返回 7 个关节值")
                    target_joints[6] = float(slave_origin[6])
                    if not tcp_ik_mode and not full_tcp_ik_mode:
                        target_joints[5] = float(slave_origin[5]) + math.degrees(desired_j6_rad)
                else:
                    target_joints = np.asarray(slave_origin[:7], dtype=float)

                target_delta_rad = np.abs(np.deg2rad(target_joints[:6] - last_sent_target[:6]))
                if float(np.max(target_delta_rad)) > step_limit:
                    index = int(np.argmax(target_delta_rad))
                    raise TeleopError(
                        f"CR3A J{index + 1} command step {target_delta_rad[index]:.4f}rad "
                        f"exceeds {step_limit:.4f}rad"
                    )
                actual = np.asarray(self.robot.joint_position()[:6], dtype=float)
                tracking_error = np.abs(np.deg2rad(last_sent_target[:6] - actual))
                if float(np.max(tracking_error)) > tracking_limit:
                    index = int(np.argmax(tracking_error))
                    raise TeleopError(
                        f"CR3A J{index + 1} tracking error {tracking_error[index]:.4f}rad "
                        f"exceeds {tracking_limit:.4f}rad"
                    )

                if not self._ready_to_dispatch(
                    lease, master, stop_generation, master_timeout, o6_timeout
                ):
                    break
                sent = lease.servo_joint(JointTarget.from_degrees(target_joints.tolist()))
                if sent is not False:
                    last_sent_target = target_joints.copy()
                    last_j6_target_rad = desired_j6_rad
                self.hooks.publish_tcp_target(target_tcp.tolist())

                hand_target = interpolate_o6_target(
                    master.gripper,
                    o6_cfg["open"],
                    o6_cfg["closed"],
                )
                if should_send_o6_target(
                    hand_target,
                    last_hand,
                    int(o6_cfg["command_deadband"]),
                ):
                    if not self._ready_to_dispatch(
                        lease, master, stop_generation, master_timeout, o6_timeout
                    ):
                        break
                    self.hand.set_target(hand_target)
                    last_hand = hand_target

                next_cycle += period
                wait_time = next_cycle - time.monotonic()
                if wait_time > 0:
                    self.hooks.stop.wait(wait_time)
                else:
                    next_cycle = time.monotonic()
        except MotionPreempted:
            pass
        except Exception as exc:
            error = exc
            with self.hooks.lock:
                if self.hooks.state() == "following" and self._owns_failure(lease, error):
                    self.hooks.set_state("fault", str(error))
                    self.hooks.event("error", f"GELLO XYZ/J6 安全停止：{error}")
        finally:
            self._finish_motion(lease, error)
