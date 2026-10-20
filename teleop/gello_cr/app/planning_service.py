"""Plan/preview lifecycle and POINT_MOVE playback, separate from pure planning."""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import asdict

from teleop.gello_cr.hardware.kinematics import NrcKinematicsProvider
from teleop.gello_cr.motion import JointTarget, MotionPreempted, MotionSource
from teleop.gello_cr.trajectory import ReplayMode, ReplayOptions, TrajectoryPlayer
from teleop.gello_cr.trajectory.planner import (
    JointMoveRequest,
    PlanningResult,
    TcpMoveRequest,
    TcpPlanningMode,
    TcpPose,
    TrajectoryPlanner,
    Waypoint,
    WaypointRequest,
)
from teleop.gello_cr.trajectory.planner.config import planning_config
from teleop.gello_cr.trajectory.planner.reached import ReachStatus, wait_until_reached
from teleop.gello_cr.trajectory.planner.validation import validate_planned_trajectory


class PointMotionService:
    def __init__(self, runtime):
        self.runtime = runtime
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self.thread = None
        self._lease = None
        self._result = None
        self._profile = None
        self._robot = None
        self._saved_path = ""
        self._status = "IDLE"
        self._error = ""
        self._position = None
        self._position_serial = 0
        self._requested_status = ReachStatus.PREEMPTED
        robot = runtime.store.data["robot"]
        self.player = TrajectoryPlayer(
            runtime.motion,
            runtime.trajectory_source,
            period_s=float(runtime.store.data["replay"]["servoj_period_s"]),
            servo_profile=tuple(
                robot[k] for k in ("servoj_vmax", "servoj_amax", "servoj_jmax")
            ),
            stop_event=self._stop,
        )

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def read_position(self):
        joints = self.runtime.trajectory_source.read_joints()
        pose = self.runtime.trajectory_source.read_tcp()
        with self._lock:
            self._position = {"joint_rad": joints, "tcp": pose.vector()}
            self._position_serial += 1
        return self._position

    def _request(self, payload):
        config = self.runtime.store.data.get("planning", {})
        scale = float(payload.get("speed_scale", config.get("default_speed_scale", 0.3)))
        if not math.isfinite(scale) or not 0 < scale <= 1:
            raise ValueError("speed_scale must be in (0, 1]")
        model, _, _ = planning_config(self.runtime.store.data)
        name = str(payload.get("name", "")).strip() or "Planned motion"
        kind = payload["kind"]
        if kind == "joint":
            return JointMoveRequest(
                tuple(payload["target"]),
                min(model.max_joint_velocity) * scale,
                min(model.max_joint_acceleration) * scale**2,
                name,
            )
        linear = float(config.get("max_linear_velocity_m_s", 0.03))
        angular = float(config.get("max_angular_velocity_rad_s", 0.1))
        if kind == "waypoints":
            waypoints = tuple(
                Waypoint(
                    TcpPose.from_vector(w["pose"]),
                    TcpPlanningMode(w.get("mode", "ptp")),
                    float(w.get("speed_scale", 1)),
                    float(w.get("hold_time_s", 0)),
                )
                for w in payload["waypoints"]
            )
            return WaypointRequest(waypoints, linear, angular, scale, name)
        if kind not in ("tcp_ptp", "tcp_linear"):
            raise ValueError("Unknown planning mode")
        return TcpMoveRequest(
            TcpPose.from_vector(payload["target"]),
            TcpPlanningMode.LINEAR if kind == "tcp_linear" else TcpPlanningMode.PTP,
            linear,
            angular,
            scale,
            name,
        )

    def plan(self, payload):
        if self.running or self.runtime.state not in ("idle", "following"):
            raise RuntimeError("当前状态不允许规划，请先停止运动或复位故障")
        with self._lock:
            self._result = None
            self._saved_path = ""
            self._error = ""
            self._status = "PLANNING"
        try:
            profile = planning_config(self.runtime.store.data)
            robot = self.runtime.robot
            offline = robot is None
            if offline and not (
                isinstance(payload, dict)
                and payload.get("kind") == "joint"
                and "start_joint_rad" in payload
            ):
                raise RuntimeError(
                    "离线模式请使用 Joint PTP 并明确输入规划起点；TCP 规划需要已连接的运动学服务"
                )
            try:
                request = self._request(payload) if isinstance(payload, dict) else payload
            except (KeyError, TypeError, ValueError) as exc:
                result = PlanningResult(False, errors=(f"InvalidWaypoint: {exc}",))
            else:
                result = TrajectoryPlanner(
                    profile[0], None if offline else NrcKinematicsProvider(robot), profile[1]
                ).plan(
                    request,
                    tuple(payload["start_joint_rad"])
                    if offline
                    else self.runtime.trajectory_source.read_joints(),
                )
            if offline and result.success:
                result.trajectory.metadata.planning["offline_only"] = True
            with self._lock:
                self._result, self._profile, self._robot = result, profile, robot
                self._status = "READY" if result.success else "PLANNING_FAILED"
                self._error = "; ".join(result.errors)
            return result
        except Exception as exc:
            with self._lock:
                self._status, self._error = "PLANNING_FAILED", str(exc)
            raise

    def _plan(self, plan_id):
        result = self._result
        if (
            result is None
            or not result.success
            or result.trajectory.metadata.trajectory_id != plan_id
        ):
            raise ValueError("请先规划并查看当前预览")
        return result.trajectory

    def save(self, plan_id):
        with self._lock:
            trajectory = self._plan(plan_id)
            if not self._saved_path:
                self._saved_path = str(self.runtime.trajectory_store.save(trajectory))
            path = self._saved_path
        self.runtime.list_trajectories()
        return path

    def execute(self, plan_id, *, on_finished=None):
        runtime = self.runtime
        generation = runtime.stop_generation
        if (
            self.running
            or runtime.replaying
            or runtime._home_lock.locked()
            or runtime.state not in ("idle", "following")
        ):
            raise RuntimeError("当前状态不允许执行规划")
        with self._lock:
            trajectory = self._plan(plan_id)
            profile = planning_config(runtime.store.data)
            if self._profile != profile or self._robot is not runtime.robot:
                raise ValueError("机器人或规划配置已改变，请重新规划")
        validate_planned_trajectory(trajectory, profile[0])
        runtime.trajectory_source.check_ready(True, False)
        current = runtime.trajectory_source.read_joints()
        if (
            max(
                abs(a - b)
                for a, b in zip(current, trajectory.frames[0].robot_joint_command, strict=True)
            )
            > profile[2].joint_tolerance_rad
        ):
            raise ValueError("机器人已离开规划起点，请重新读取并规划")
        if generation != runtime.stop_generation:
            raise MotionPreempted("Point motion cancelled during preparation")
        self._stop.clear()
        self._requested_status = ReachStatus.PREEMPTED
        lease = None
        try:
            lease = runtime.motion.acquire(
                MotionSource.POINT_MOVE, allow_preempt=True, on_cancel=self._stop.set
            )
            self._lease = lease
            runtime._join_follow_producer("Point motion takeover")
            lease.check()
            if runtime.stop_generation != generation or self._stop.is_set():
                raise MotionPreempted("Point motion start cancelled")
            runtime._set_state("point_move")
            with self._lock:
                self._status, self._error = "EXECUTING", ""
            self.thread = threading.Thread(
                target=self._run,
                args=(trajectory, lease, profile[2], generation, on_finished),
                name="Point-Motion",
                daemon=True,
            )
            self.thread.start()
        except Exception:
            if lease is not None:
                lease.release()
            if runtime.stop_generation == generation and runtime.state == "point_move":
                runtime._set_state("idle")
            raise

    def _run(self, trajectory, lease, policy, generation, on_finished):
        runtime = self.runtime
        error = None
        status = None

        def reached(active, stop):
            with self._lock:
                self._status = "WAITING_FOR_TARGET"
            final = trajectory.frames[-1]
            kind = trajectory.metadata.planning["planner_type"]
            target_tcp = (
                TcpPose.from_vector(trajectory.metadata.planning["target_pose"])
                if kind != "joint_ptp"
                else None
            )
            return wait_until_reached(
                runtime.trajectory_source,
                final.robot_joint_command,
                target_tcp,
                policy,
                active,
                stop,
                keep_alive=lambda: active.servo_joint(
                    JointTarget(final.robot_joint_command, time.monotonic())
                ),
            )

        try:
            status = self.player.play(
                trajectory,
                ReplayOptions(mode=ReplayMode.ABSOLUTE, hand_enabled=False),
                lease=lease,
                start_tolerance_rad=policy.joint_tolerance_rad,
                on_target=reached,
            )
            if status is None or (
                status is ReachStatus.STOPPED and self._requested_status is ReachStatus.PREEMPTED
            ):
                status = self._requested_status
            if status in (ReachStatus.TIMEOUT, ReachStatus.FAULT):
                error = "目标到达超时" if status is ReachStatus.TIMEOUT else "目标到达反馈异常"
        except Exception as exc:
            logging.getLogger("workbench.motion").exception("EXECUTE_PLAN failed")
            error, status = str(exc), ReachStatus.FAULT
        finally:
            try:
                lease.release(error=error)
            except Exception as exc:
                logging.getLogger("workbench.motion").exception("EXECUTE_PLAN release failed")
                error, status = str(exc), ReachStatus.FAULT
            if runtime.stop_generation == generation and runtime.state == "point_move":
                runtime._set_state("fault" if error else "idle", error or "")
            elif runtime.state == "fault":
                status = ReachStatus.FAULT
            with self._lock:
                self._status, self._error = status.value, error or ""
            runtime._event(
                "error" if error else "info",
                f"精确走点：{status.value}" + (f" · {error}" if error else ""),
            )
            if on_finished is not None:
                on_finished(error)

    def stop(self):
        self._requested_status = ReachStatus.STOPPED
        self._stop.set()
        if self._lease is not None:
            self._lease.release()
        self.player.stop()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(3)
            if self.thread.is_alive():
                raise TimeoutError("精确走点线程未及时停止")

    def snapshot(self):
        with self._lock:
            result = self._result
            trajectory = result.trajectory if result is not None else None
            return {
                "plan_id": trajectory.metadata.trajectory_id if trajectory else None,
                "preview": trajectory.metadata.planning if trajectory else None,
                "metrics": asdict(result.metrics) if result else {},
                "warnings": result.warnings if result else (),
                "errors": result.errors if result else (),
                "status": self._status,
                "error": self._error,
                "running": self.running,
                "saved_path": self._saved_path,
                "position": self._position,
                "position_serial": self._position_serial,
                "default_speed_scale": self.runtime.store.data.get("planning", {}).get(
                    "default_speed_scale", 0.3
                ),
            }
