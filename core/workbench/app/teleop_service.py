"""Teleop startup and configured Cartesian master following."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Sequence
from typing import Any

from core.workbench.control.geometry import (
    _nrc_abc_to_quaternion,
    _quaternion_distance,
    _quaternion_inverse,
    _quaternion_multiply,
    _quaternion_slerp,
    _quaternion_to_nrc_abc,
    _quaternion_to_nrc_abc_near,
    _wrapped_angle_delta,
)
from core.workbench.motion import (
    JointTarget,
    MotionLease,
    MotionPreempted,
    MotionSource,
)


class TeleopService:
    """Start teleop and retain the configured alternative master mapping."""

    def __init__(self, runtime):
        self.runtime = runtime

    def start_follow(self) -> None:
        if self.runtime._home_lock.locked():
            raise RuntimeError("HOME 回位正在执行")
        if self.runtime._shutdown_requested.is_set():
            raise RuntimeError("程序正在退出，禁止启动主从跟随")
        if self.runtime.robot is None:
            raise RuntimeError("请先连接纳博特控制柜")
        if not self.runtime.roarm.connected or not self.runtime.o6.connected:
            raise RuntimeError("请先连接主臂和 O6")
        if self.runtime.master_type == "gello" and self.runtime.o6_action_active:
            raise RuntimeError("O6 单独动作尚未结束，不能交接给 GELLO J7")
        with self.runtime._state_lock:
            state = self.runtime._state
            stop_generation = self.runtime._stop_generation
        if state in ("recovering", "preset", "closed", "replay", "point_move"):
            raise RuntimeError("其他运动正在执行，请等待完成")
        if self.runtime._follow_thread is not None and self.runtime._follow_thread.is_alive():
            return
        self.runtime.finish_external_control()
        if self.runtime.robot.servo_state() != 3:
            raise RuntimeError("CR5 尚未上电运行，请先使能机器人")
        if self.runtime._shutdown_requested.is_set():
            raise RuntimeError("程序退出已取消主从跟随启动")

        cfg = self.runtime.store.data
        master = self.runtime.roarm.latest()
        o6_position, o6_fault, o6_timestamp = self.runtime.o6.latest()
        now = time.monotonic()
        master_timeout = float(
            cfg["inverse3"]["feedback_timeout_s"]
            if self.runtime.master_type == "inverse3"
            else cfg["gello"]["feedback_timeout_s"]
            if self.runtime.master_type == "gello"
            else cfg["roarm"]["feedback_timeout_s"]
        )
        if master is None or now - master.timestamp > master_timeout:
            raise RuntimeError("主臂反馈超时")
        if self.runtime.master_type == "inverse3" and master.orientation_wxyz is None:
            raise RuntimeError(
                "Inverse3 只能提供 XYZ；未检测到 VerseGrip 姿态，禁止启动不锁 RPY 的 6D 跟随"
            )
        if o6_position is None or now - o6_timestamp > float(cfg["o6"]["feedback_timeout_s"]):
            raise RuntimeError("O6 反馈超时")
        if o6_fault is None or any(o6_fault):
            raise RuntimeError(f"O6 故障: {o6_fault}")

        if self.runtime.master_type == "gello":
            self.runtime.teleop_controller.start(master, stop_generation)
            self.runtime._follow_thread = self.runtime.teleop_controller.thread
            return

        slave_tcp = self.runtime.robot.tcp_position()
        self.runtime._set_dataset_target_tcp(slave_tcp)
        robot_cfg = cfg["robot"]
        with self.runtime._state_lock:
            if (
                self.runtime._shutdown_requested.is_set()
                or self.runtime._stop_generation != stop_generation
            ):
                raise RuntimeError("XYZ 跟随启动已被软件紧急停止")
            self.runtime._follow_stop.clear()
        lease = self.runtime.motion.acquire(
            MotionSource.TELEOP, on_cancel=self.runtime._follow_stop.set
        )
        try:
            if getattr(self.runtime.robot, "motion_mode", "servoj") != "movej":
                lease.open_servo(
                    robot_cfg["servoj_vmax"],
                    robot_cfg["servoj_amax"],
                    robot_cfg["servoj_jmax"],
                )
            if (
                self.runtime._follow_stop.is_set()
                or self.runtime._shutdown_requested.is_set()
                or self.runtime._stop_generation != stop_generation
            ):
                raise RuntimeError("XYZ 跟随启动已被软件紧急停止")
            if not getattr(self.runtime.roarm, "passive", False):
                self.runtime.roarm.release_torque()
            if (
                self.runtime._follow_stop.is_set()
                or self.runtime._shutdown_requested.is_set()
                or self.runtime._stop_generation != stop_generation
            ):
                raise RuntimeError("XYZ 跟随启动已被软件紧急停止")
        except Exception as exc:
            if self.runtime._stop_generation == stop_generation and self.runtime.state != "closed":
                self.runtime._set_state("fault", str(exc))
            try:
                lease.release(error=str(exc))
            finally:
                self.runtime._hold_roarm()
            raise

        with self.runtime._state_lock:
            cancelled = (
                self.runtime._follow_stop.is_set()
                or self.runtime._shutdown_requested.is_set()
                or self.runtime._stop_generation != stop_generation
            )
            if not cancelled:
                self.runtime._state = "following"
                self.runtime._last_error = ""
        if cancelled:
            lease.release()
            self.runtime._hold_roarm()
            raise RuntimeError("XYZ 跟随启动已被软件紧急停止")
        self.runtime._follow_thread = threading.Thread(
            target=self.runtime._follow_loop,
            args=(master, slave_tcp, lease),
            name=f"{self.runtime.master_type}-CR5-Follow",
            daemon=True,
        )
        self.runtime._start_motion_worker(self.runtime._follow_thread, lease)
        if self.runtime.master_type == "inverse3":
            self.runtime._event(
                "info",
                "跟随已启动：Inverse3 XYZ + VerseGrip 相对 RPY；O6 仅使用独立快捷动作",
            )
        else:
            hand_mode = (
                "O6 保持独立动作，M5 已屏蔽" if self.runtime.o6_manual_override else "M5 控制 O6"
            )
            self.runtime._event("info", f"跟随已启动：XYZ 增量映射，RPY 已锁定；{hand_mode}")

    def _follow_loop(
        self, master_origin: Any, slave_origin: Sequence[float], lease: MotionLease
    ) -> None:
        cfg = self.runtime.store.data
        teleop_cfg = cfg["teleop"]
        inverse3_mode = self.runtime.master_type == "inverse3"
        scales = [float(value) for value in teleop_cfg["scale_xyz"]]
        rpy_scales = [float(value) for value in teleop_cfg["scale_rpy"]]
        max_jump = float(teleop_cfg["max_master_jump_mm"])
        max_angular_jump = float(teleop_cfg["max_master_angular_jump_rad"])
        period = float(teleop_cfg["period_s"])
        master_timeout = float(
            cfg["inverse3"]["feedback_timeout_s"]
            if inverse3_mode
            else cfg["roarm"]["feedback_timeout_s"]
        )
        o6_timeout = float(cfg["o6"]["feedback_timeout_s"])
        m5_open = float(cfg["roarm"]["m5_open_rad"])
        m5_closed = float(cfg["roarm"]["m5_closed_rad"])
        o6_open = [float(value) for value in cfg["o6"]["open"]]
        o6_closed = [float(value) for value in cfg["o6"]["closed"]]
        hand_deadband = int(cfg["o6"]["command_deadband"])

        commanded_xyz = [float(value) for value in slave_origin[:3]]
        commanded_rpy = [float(value) for value in slave_origin[3:6]]
        slave_orientation = _nrc_abc_to_quaternion(slave_origin[3:6])
        commanded_orientation = slave_orientation
        mapping_master_origin = list(master_origin.xyz)
        mapping_slave_origin = list(commanded_xyz)
        mapping_orientation_origin = master_origin.orientation_wxyz if inverse3_mode else None
        mapping_slave_orientation = commanded_orientation
        last_master = master_origin
        last_master_timestamp = master_origin.timestamp
        last_hand: list[int] | None = None
        next_cycle = time.monotonic()
        error = ""
        try:
            while not self.runtime._follow_stop.is_set():
                now = time.monotonic()
                master = self.runtime.roarm.latest()
                if master is None or now - master.timestamp > master_timeout:
                    raise RuntimeError("主臂反馈掉线/超时")
                if self.runtime.roarm.error:
                    raise RuntimeError(self.runtime.roarm.error)
                if inverse3_mode and master.orientation_wxyz is None:
                    raise RuntimeError("VerseGrip 姿态反馈丢失")

                o6_position, o6_fault, o6_timestamp = self.runtime.o6.latest()
                if self.runtime.o6.error:
                    raise RuntimeError(self.runtime.o6.error)
                if o6_position is None or now - o6_timestamp > o6_timeout:
                    raise RuntimeError("O6 反馈掉线/超时")
                if o6_fault is None or any(o6_fault):
                    raise RuntimeError(f"O6 故障: {o6_fault}")

                if master.timestamp != last_master_timestamp:
                    jump = math.dist(master.xyz, last_master.xyz)
                    if jump > max_jump:
                        raise RuntimeError(f"主臂单帧跳变 {jump:.1f} mm，超过 {max_jump:.1f} mm")
                    if inverse3_mode:
                        angular_jump = _quaternion_distance(
                            master.orientation_wxyz,
                            last_master.orientation_wxyz,
                        )
                        if angular_jump > max_angular_jump:
                            raise RuntimeError(
                                "VerseGrip 单帧姿态跳变 "
                                f"{angular_jump:.3f} rad，超过 {max_angular_jump:.3f} rad"
                            )
                    last_master = master
                    last_master_timestamp = master.timestamp

                live_teleop_cfg = self.runtime.store.data["teleop"]
                live_scales = [float(value) for value in live_teleop_cfg["scale_xyz"]]
                if live_scales != scales:
                    # Rebase only the mapping origin so changing gain/direction
                    # cannot jump the current target. The original CR5 origin
                    # below remains the fixed safety-envelope reference.
                    mapping_master_origin = list(master.xyz)
                    mapping_slave_origin = list(commanded_xyz)
                    scales = live_scales
                live_rpy_scales = [float(value) for value in live_teleop_cfg["scale_rpy"]]
                if inverse3_mode and live_rpy_scales != rpy_scales:
                    mapping_orientation_origin = master.orientation_wxyz
                    mapping_slave_orientation = commanded_orientation
                    rpy_scales = live_rpy_scales
                limits = [float(value) for value in live_teleop_cfg["max_delta_xyz_mm"]]
                scaled_delta = [
                    (master.xyz[index] - mapping_master_origin[index]) * scales[index]
                    for index in range(3)
                ]
                desired_xyz = [
                    mapping_slave_origin[index] + scaled_delta[index] for index in range(3)
                ]
                total_delta = [
                    desired_xyz[index] - float(slave_origin[index]) for index in range(3)
                ]
                for index, axis in enumerate("XYZ"):
                    if abs(total_delta[index]) > limits[index]:
                        raise RuntimeError(
                            f"{axis} 相对位移 {total_delta[index]:.1f} mm 超过 ±{limits[index]:.1f} mm"
                        )

                dt = max(0.001, now - (next_cycle - period))
                remaining = [desired_xyz[index] - commanded_xyz[index] for index in range(3)]
                distance = math.sqrt(sum(value * value for value in remaining))
                # The GUI may update the speed while following.  Read this one
                # value every cycle so the new limit takes effect without
                # stopping ServoJ or resetting the teleoperation origin.
                max_speed = float(live_teleop_cfg["max_tcp_speed_mm_s"])
                max_step = max_speed * dt
                ratio = min(1.0, max_step / distance) if distance > 1e-9 else 1.0
                commanded_xyz = [
                    commanded_xyz[index] + remaining[index] * ratio for index in range(3)
                ]

                target_tcp = list(slave_origin[:7])
                target_tcp[:3] = commanded_xyz
                if inverse3_mode:
                    relative_orientation = _quaternion_multiply(
                        master.orientation_wxyz,
                        _quaternion_inverse(mapping_orientation_origin),
                    )
                    relative_rpy = _quaternion_to_nrc_abc(relative_orientation)
                    scaled_relative_orientation = _nrc_abc_to_quaternion(
                        [relative_rpy[index] * rpy_scales[index] for index in range(3)]
                    )
                    desired_orientation = _quaternion_multiply(
                        scaled_relative_orientation,
                        mapping_slave_orientation,
                    )
                    rpy_limits = [float(value) for value in live_teleop_cfg["max_delta_rpy_rad"]]
                    total_rpy_delta = _quaternion_to_nrc_abc(
                        _quaternion_multiply(
                            desired_orientation,
                            _quaternion_inverse(slave_orientation),
                        )
                    )
                    for index, axis in enumerate("ABC"):
                        if abs(total_rpy_delta[index]) > rpy_limits[index]:
                            raise RuntimeError(
                                f"{axis} 相对转角 {total_rpy_delta[index]:.3f} rad "
                                f"超过 ±{rpy_limits[index]:.3f} rad"
                            )
                    angular_distance = _quaternion_distance(
                        commanded_orientation,
                        desired_orientation,
                    )
                    max_angular_step = float(live_teleop_cfg["max_tcp_angular_speed_rad_s"]) * dt
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
                    commanded_rpy = [
                        _wrapped_angle_delta(value, 0.0)
                        for value in _quaternion_to_nrc_abc_near(
                            commanded_orientation,
                            commanded_rpy,
                        )
                    ]
                    target_tcp[3:6] = commanded_rpy
                target_joints = self.runtime.robot.inverse_kinematics(target_tcp)
                lease.servo_joint(JointTarget.from_degrees(target_joints))
                self.runtime._set_dataset_target_tcp(target_tcp)

                if not inverse3_mode and not self.runtime.o6_manual_override:
                    grip = (master.t - m5_open) / (m5_closed - m5_open)
                    grip = max(0.0, min(1.0, grip))
                    hand_target = [
                        int(round(o6_open[index] + grip * (o6_closed[index] - o6_open[index])))
                        for index in range(6)
                    ]
                    if (
                        last_hand is None
                        or max(abs(a - b) for a, b in zip(hand_target, last_hand, strict=True))
                        >= hand_deadband
                    ):
                        self.runtime.o6.set_target(hand_target)
                        last_hand = hand_target

                next_cycle += period
                wait_time = next_cycle - time.monotonic()
                if wait_time > 0:
                    self.runtime._follow_stop.wait(wait_time)
                else:
                    next_cycle = time.monotonic()
        except MotionPreempted:
            pass
        except Exception as exc:
            if self.runtime.state == "following" and self.runtime._motion_failure(lease, exc):
                error = str(exc)
                self.runtime._set_state("fault", error)
                self.runtime._event("error", f"安全停止：{error}")
        finally:
            owned = lease.active
            try:
                lease.release(error=error or None)
            except Exception as exc:
                error = str(exc)
                if self.runtime.state == "following":
                    self.runtime._set_state("fault", error)
                self.runtime._event("error", f"CR5 停止失败: {exc}")
            try:
                if owned or (error and self.runtime.motion.current_owner is None):
                    self.runtime._hold_roarm()
            except Exception as exc:
                self.runtime._event("error", f"主臂保持失败: {exc}")
            if owned and not error and self.runtime.state == "following":
                self.runtime._set_state("idle")
