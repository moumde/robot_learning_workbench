"""Pure point/waypoint planning; never acquires motion or controls devices."""

from __future__ import annotations

import math
from dataclasses import asdict, replace
from datetime import UTC, datetime

import numpy as np

from core.workbench.trajectory.model import TrajectoryFrame, make_trajectory

from .interpolation import interpolate_pose, pose_distance, quintic
from .types import (
    DiscontinuousIK,
    IKFailure,
    InvalidWaypoint,
    JointMoveRequest,
    PlannerSettings,
    PlanningError,
    PlanningMetrics,
    PlanningResult,
    RobotModel,
    TcpMoveRequest,
    TcpPlanningMode,
    TcpPose,
    TrajectoryLimitViolation,
    WaypointRequest,
)
from .validation import (
    check_joints,
    check_pose,
    derivatives,
    positive,
    validate_planned_trajectory,
)


class TrajectoryPlanner:
    def __init__(self, model: RobotModel, kinematics=None, settings=None):
        settings = settings or PlannerSettings()
        self.model, self.kinematics, self.settings = model, kinematics, settings
        if model.joint_count != 6:
            raise ValueError("The current Trajectory model requires six joints")
        for name, count in (("joint_limits_rad", 6), ("workspace_limits_m", 3)):
            bounds = getattr(model, name)
            if bounds is not None and (
                len(bounds) != count
                or any(
                    len(pair) != 2 or not all(math.isfinite(v) for v in pair) or pair[0] > pair[1]
                    for pair in bounds
                )
            ):
                raise ValueError(f"{name} requires {count} finite ordered pairs")
        for name in ("max_joint_velocity", "max_joint_acceleration"):
            values = getattr(model, name)
            if len(values) != 6:
                raise ValueError(f"{name} requires six limits")
            for v in values:
                positive(v, name)
        positive(model.max_command_delta_rad, "max_command_delta_rad")
        for name, value in asdict(settings).items():
            positive(value, name)

    def _forward(self, joints):
        if self.kinematics is None:
            return None
        try:
            pose = self.kinematics.forward(joints)
            check_pose(pose, self.model)
            return pose
        except PlanningError:
            raise
        except Exception as exc:
            raise IKFailure(f"FK: {exc}") from exc

    def _inverse(self, pose, seed, continuous=False):
        if self.kinematics is None:
            raise IKFailure("No kinematics provider configured")
        check_pose(pose, self.model)
        try:
            candidates = self.kinematics.inverse(pose, seed_joint_rad=seed)
        except Exception as exc:
            raise IKFailure(str(exc)) from exc
        valid = []
        reasons = []
        for raw in candidates:
            try:
                q = check_joints(raw, self.model)
                if (
                    continuous
                    and max(abs(a - b) for a, b in zip(q, seed, strict=True))
                    > self.settings.max_ik_step_rad
                ):
                    raise DiscontinuousIK("IK branch changes more than max_ik_step_rad")
                actual = self._forward(q)
                dp, dr = pose_distance(actual, pose)
                if (
                    dp > self.settings.ik_position_tolerance_m
                    or dr > self.settings.ik_orientation_tolerance_rad
                ):
                    raise IKFailure(f"IK/FK residual: {dp:.5g} m, {dr:.5g} rad")
                valid.append(q)
            except PlanningError as exc:
                reasons.append(exc)
        if not valid:
            if reasons:
                raise reasons[-1]
            raise IKFailure("No IK solution")
        return min(valid, key=lambda q: sum((a - b) ** 2 for a, b in zip(q, seed, strict=True)))

    def _joint(self, start, target, velocity, acceleration):
        target = check_joints(target, self.model)
        delta = np.abs(np.array(target) - start)
        # max s'(u)=15/8; max |s''(u)|=10/sqrt(3) for quintic smoothstep.
        duration = max(
            1 / self.settings.sample_hz,
            float(np.max(1.875 * delta / velocity)),
            float(np.max(np.sqrt((10 / math.sqrt(3)) * delta / acceleration))),
            float(np.max(1.875 * delta))
            / (self.model.max_command_delta_rad * self.settings.sample_hz),
        )
        steps = max(2, math.ceil(duration * self.settings.sample_hz))
        return [
            TrajectoryFrame(
                duration * i / steps,
                robot_joint_command=tuple(
                    a + (b - a) * quintic(i / steps) for a, b in zip(start, target, strict=True)
                ),
            )
            for i in range(steps + 1)
        ]

    def _tcp(self, start, request, velocity, acceleration):
        if not isinstance(request.mode, TcpPlanningMode):
            raise InvalidWaypoint("Unknown TCP motion type")
        check_pose(request.target_pose, self.model)
        scale = positive(request.speed_scale, "speed_scale")
        if scale > 1:
            raise TrajectoryLimitViolation("speed_scale must be <= 1")
        linear = positive(request.max_linear_velocity, "max_linear_velocity") * scale
        angular = positive(request.max_angular_velocity, "max_angular_velocity") * scale
        origin = self._forward(start)
        if origin is None:
            raise IKFailure("TCP planning requires kinematics")
        distance, rotation = pose_distance(origin, request.target_pose)
        duration = max(
            1 / self.settings.sample_hz, 1.875 * distance / linear, 1.875 * rotation / angular
        )
        if request.mode is TcpPlanningMode.PTP:
            target = self._inverse(request.target_pose, start)
            frames = self._joint(start, target, velocity * scale, acceleration * scale**2)
            # Bound actual FK path speed too: endpoint distance alone is insufficient for PTP.
            return self._retime(
                frames, velocity * scale, acceleration * scale**2, linear, angular, duration
            )
        steps = max(
            2,
            math.ceil(duration * self.settings.sample_hz),
            math.ceil(1.875 * distance / self.settings.tcp_position_step_m),
            math.ceil(1.875 * rotation / self.settings.tcp_rotation_step_rad),
        )
        frames = [TrajectoryFrame(0.0, robot_joint_command=start)]
        seed = start
        for i in range(1, steps + 1):
            pose = interpolate_pose(origin, request.target_pose, quintic(i / steps))
            seed = self._inverse(pose, seed, continuous=True)
            frames.append(TrajectoryFrame(duration * i / steps, robot_joint_command=seed))
        return self._retime(frames, velocity * scale, acceleration * scale**2, linear, angular)

    def _retime(self, frames, velocity, acceleration, linear, angular, min_duration=0):
        _, v, a = derivatives(frames)
        factor = max(
            1.0,
            float(np.max(abs(v) / velocity)),
            math.sqrt(float(np.max(abs(a) / acceleration))),
            min_duration / frames[-1].timestamp,
        )
        poses = [self._forward(f.robot_joint_command) for f in frames]
        for first, second, pa, pb in zip(frames, frames[1:], poses, poses[1:], strict=False):
            dp, dr = pose_distance(pa, pb)
            dt = second.timestamp - first.timestamp
            factor = max(factor, dp / dt / linear, dr / dt / angular)
        return [
            replace(f, timestamp=f.timestamp * factor * (1 + 1e-9), robot_tcp_command=pose.vector())
            for f, pose in zip(frames, poses, strict=True)
        ]

    def plan(self, request, start_joint_rad) -> PlanningResult:
        warnings = []
        if self.kinematics is None:
            warnings.append("离线关节规划：未检查 FK/TCP 路径；连接机器人后需重新规划再执行")
        if self.model.joint_limits_rad is None:
            warnings.append("未配置关节硬限位；请在 motion.joint_limits_rad 配置现场范围")
        if self.model.workspace_limits_m is None:
            warnings.append("未配置 TCP 工作空间；请在 motion.workspace_limits_m 配置现场范围")
        warnings.extend(getattr(self.kinematics, "warnings", ()))
        try:
            start = check_joints(start_joint_rad, self.model)
            velocity = np.array(self.model.max_joint_velocity)
            acceleration = np.array(self.model.max_joint_acceleration)
            if isinstance(request, JointMoveRequest):
                velocity = np.minimum(velocity, positive(request.max_velocity, "max_velocity"))
                acceleration = np.minimum(
                    acceleration, positive(request.max_acceleration, "max_acceleration")
                )
                frames = self._joint(start, request.target_rad, velocity, acceleration)
                kind = "joint_ptp"
            elif isinstance(request, TcpMoveRequest):
                frames = self._tcp(start, request, velocity, acceleration)
                kind = f"tcp_{request.mode.value}"
            elif isinstance(request, WaypointRequest):
                if not request.waypoints:
                    raise InvalidWaypoint("At least one waypoint is required")
                frames = [TrajectoryFrame(0, robot_joint_command=start)]
                for index, waypoint in enumerate(request.waypoints):
                    if not math.isfinite(waypoint.speed_scale) or not 0 < waypoint.speed_scale <= 1:
                        raise InvalidWaypoint(
                            f"Waypoint {index + 1}: speed_scale must be in (0, 1]"
                        )
                    if not math.isfinite(waypoint.hold_time_s) or waypoint.hold_time_s < 0:
                        raise InvalidWaypoint(
                            f"Waypoint {index + 1}: hold time must be nonnegative"
                        )
                    segment = self._tcp(
                        frames[-1].robot_joint_command,
                        TcpMoveRequest(
                            waypoint.pose,
                            waypoint.motion_type,
                            request.max_linear_velocity,
                            request.max_angular_velocity,
                            request.speed_scale * waypoint.speed_scale,
                        ),
                        velocity,
                        acceleration,
                    )
                    offset = frames[-1].timestamp
                    frames.extend(replace(f, timestamp=f.timestamp + offset) for f in segment[1:])
                    if waypoint.hold_time_s:
                        frames.append(
                            replace(
                                frames[-1], timestamp=frames[-1].timestamp + waypoint.hold_time_s
                            )
                        )
                kind = "waypoints"
            else:
                raise InvalidWaypoint("Unknown motion request")
            # FK is optional for Joint PTP. When supplied, validate the full sampled path.
            poses = (
                [
                    TcpPose.from_vector(f.robot_tcp_command)
                    if f.robot_tcp_command is not None
                    else self._forward(f.robot_joint_command)
                    for f in frames
                ]
                if self.kinematics
                else []
            )
            frames = (
                [
                    replace(f, robot_tcp_command=p.vector())
                    for f, p in zip(frames, poses, strict=True)
                ]
                if poses
                else frames
            )
            trajectory = make_trajectory(
                request.name,
                frames,
                fps=self.settings.sample_hz,
                robot_type=self.model.robot_type,
                hand_type=None,
                source="planner",
            )
            validate_planned_trajectory(trajectory, self.model, velocity, acceleration)
            q, v, a = derivatives(frames)
            metrics = PlanningMetrics(
                frames[-1].timestamp,
                len(frames),
                float(np.sum(np.linalg.norm(np.diff(q, axis=0), axis=1))),
                sum(
                    math.dist(a.position_m, b.position_m)
                    for a, b in zip(poses, poses[1:], strict=False)
                )
                if poses
                else None,
                float(np.max(abs(v))),
                float(np.max(abs(a))),
                float(np.max(abs(np.diff(q, axis=0)))),
            )
            if (
                max(abs(a - b) for a, b in zip(start, frames[-1].robot_joint_command, strict=True))
                > self.settings.large_joint_change_rad
            ):
                warnings.append("关节变化较大；请检查 IK 分支与腕部姿态（无可靠奇异值信息）")
            details = {
                "planner_type": kind,
                "request": asdict(request),
                "start_joint_rad": start,
                "target_joint_rad": frames[-1].robot_joint_command,
                "start_pose": poses[0].vector() if poses else None,
                "target_pose": (
                    request.target_pose.vector()
                    if isinstance(request, TcpMoveRequest)
                    else request.waypoints[-1].pose.vector()
                    if isinstance(request, WaypointRequest)
                    else poses[-1].vector()
                    if poses
                    else None
                ),
                "velocity_limit": velocity.tolist(),
                "acceleration_limit": acceleration.tolist(),
                "planning_timestamp": datetime.now(UTC).isoformat(),
                "metrics": asdict(metrics),
                "warnings": warnings,
                "collision_checking": "unavailable",
            }
            trajectory = replace(
                trajectory, metadata=replace(trajectory.metadata, planning=details)
            )
            return PlanningResult(True, trajectory, warnings=tuple(warnings), metrics=metrics)
        except (PlanningError, ValueError, TypeError) as exc:
            code = (
                type(exc).__name__ if isinstance(exc, PlanningError) else "TrajectoryLimitViolation"
            )
            return PlanningResult(False, errors=(f"{code}: {exc}",), warnings=tuple(warnings))
