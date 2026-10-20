"""Whole-path joint/workspace, derivative and kinematics validation."""

import math

import numpy as np

from core.workbench.trajectory.validation import validate_trajectory

from .types import (
    JointLimitViolation,
    TargetOutsideWorkspace,
    TrajectoryLimitViolation,
)


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise TrajectoryLimitViolation(f"{name} must be finite and positive")
    return value


def vector(values, count, name):
    if len(values) != count or not all(math.isfinite(v) for v in values):
        raise TrajectoryLimitViolation(f"{name} requires {count} finite values")
    return tuple(values)


def check_joints(joints, model):
    q = vector(joints, model.joint_count, "Joint")
    if model.joint_limits_rad is not None:
        for i, (v, (lo, hi)) in enumerate(zip(q, model.joint_limits_rad, strict=True)):
            if not lo <= v <= hi:
                raise JointLimitViolation(f"J{i + 1}: {v:.5g} rad outside [{lo}, {hi}]")
    return q


def check_pose(pose, model):
    vector(pose.position_m, 3, "TCP position")
    vector(pose.orientation_rpy_rad, 3, "TCP orientation")
    if model.workspace_limits_m is not None:
        for axis, v, (lo, hi) in zip("XYZ", pose.position_m, model.workspace_limits_m, strict=True):
            if not lo <= v <= hi:
                raise TargetOutsideWorkspace(f"{axis}: {v:.5g} m outside [{lo}, {hi}]")


def derivatives(frames):
    q = np.array([f.robot_joint_command for f in frames], dtype=float)
    t = np.array([f.timestamp for f in frames], dtype=float)
    dt = np.diff(t)
    if len(dt) == 0:
        return q, np.empty((0, q.shape[1])), np.empty((0, q.shape[1]))
    if np.any(dt <= 0):
        raise TrajectoryLimitViolation("Trajectory timestamps must increase strictly")
    velocity = np.diff(q, axis=0) / dt[:, None]
    # Include zero endpoint velocities: each segment starts and ends at rest.
    padded = np.vstack([np.zeros(q.shape[1]), velocity, np.zeros(q.shape[1])])
    acc_dt = np.r_[dt[0] / 2, (dt[1:] + dt[:-1]) / 2, dt[-1] / 2]
    acceleration = np.diff(padded, axis=0) / acc_dt[:, None]
    return q, velocity, acceleration


def validate_planned_trajectory(trajectory, model, velocities=None, accelerations=None):
    validate_trajectory(trajectory, model.joint_limits_rad)
    for frame in trajectory.frames:
        check_joints(frame.robot_joint_command, model)
    q, velocity, acceleration = derivatives(trajectory.frames)
    vmax = np.array(velocities if velocities is not None else model.max_joint_velocity)
    amax = np.array(accelerations if accelerations is not None else model.max_joint_acceleration)
    if np.any(abs(velocity) > vmax * (1 + 1e-8)):
        raise TrajectoryLimitViolation("Joint velocity exceeds limit")
    if np.any(abs(acceleration) > amax * (1 + 1e-8)):
        raise TrajectoryLimitViolation("Joint acceleration exceeds limit")
    if np.any(abs(np.diff(q, axis=0)) > model.max_command_delta_rad + 1e-10):
        raise TrajectoryLimitViolation("Joint delta exceeds motion limit")
