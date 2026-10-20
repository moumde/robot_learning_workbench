"""Build robot planning constraints from the shared application configuration."""

import math

from .reached import ReachedPolicy
from .types import PlannerSettings, RobotModel


def planning_config(config):
    planning = config.get("planning", {})
    motion = config.get("motion", {})
    robot = config.get("robot", {})
    replay = config.get("replay", {})

    def six(value):
        return tuple(value) if isinstance(value, (list, tuple)) else (float(value),) * 6

    def bounds(value):
        return tuple(tuple(pair) for pair in value) if value is not None else None

    # Existing final motion velocity and replay ceiling remain upper bounds.
    ceiling = min(
        math.radians(float(replay.get("max_joint_speed_deg_s", 120))),
        float(motion["max_target_velocity_rad_s"])
        if motion.get("max_target_velocity_rad_s") is not None
        else math.inf,
    )
    velocity = tuple(min(v, ceiling) for v in six(planning.get("max_joint_velocity_rad_s", 0.5)))
    model = RobotModel(
        joint_limits_rad=bounds(motion.get("joint_limits_rad")),
        workspace_limits_m=bounds(motion.get("workspace_limits_m")),
        max_joint_velocity=velocity,
        max_joint_acceleration=six(planning.get("max_joint_acceleration_rad_s2", 1.0)),
        max_command_delta_rad=float(
            motion["max_command_delta_rad"]
            if motion.get("max_command_delta_rad") is not None
            else robot.get("safety_max_command_step_rad", math.radians(20))
        ),
    )
    settings = PlannerSettings(
        sample_hz=float(planning.get("joint_sample_hz", 100)),
        tcp_position_step_m=float(planning.get("tcp_position_step_m", 0.002)),
        tcp_rotation_step_rad=math.radians(float(planning.get("tcp_rotation_step_deg", 1))),
        max_ik_step_rad=float(planning.get("max_ik_step_rad", 0.35)),
        ik_position_tolerance_m=float(planning.get("ik_position_tolerance_m", 0.001)),
        ik_orientation_tolerance_rad=math.radians(
            float(planning.get("ik_orientation_tolerance_deg", 0.5))
        ),
    )
    reached = planning.get("reached", {})
    policy = ReachedPolicy(
        joint_tolerance_rad=math.radians(float(reached.get("joint_tolerance_deg", 0.5))),
        position_tolerance_m=float(reached.get("tcp_position_tolerance_mm", 2)) / 1000,
        orientation_tolerance_rad=math.radians(
            float(reached.get("tcp_orientation_tolerance_deg", 1))
        ),
        stable_samples=reached.get("stable_samples", 5),
        timeout_s=float(reached.get("timeout_s", 10)),
        sample_period_s=float(reached.get("sample_period_s", 0.02)),
    )
    return model, settings, policy
