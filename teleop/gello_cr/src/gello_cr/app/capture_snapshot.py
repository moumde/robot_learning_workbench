"""State and accepted-target sampling for the capture source."""

from __future__ import annotations

import math
import time
from typing import Any

from gello_cr.control.geometry import (
    _wrapped_angle_delta,
)


class CaptureSnapshot:
    """Application service; device I/O remains behind the runtime adapters."""

    def __init__(self, runtime):
        self.runtime = runtime

    def dataset_sample(self) -> dict[str, Any]:
        """Read a bounded-age state/action sample (not hardware synchronized).

        The observation follows the portable OpenPI interface contract: six CR5
        joints in radians, TCP XYZ+RPY in metres/radians, then six raw O6
        positions.  The action is the shortest TCP delta from current feedback
        to the last command sent by follow/preset/replay plus the last O6 RS485
        target. Joint mode records six feedback joints and six absolute sent
        joint targets in radians, each followed by O6 values; it normally
        uses the current motion owner and its last accepted joint target.
        GELLO-specific quality telemetry remains optional diagnostics. SDK success is not an
        execution acknowledgement.
        """
        state = self.runtime.state
        if state in ("fault", "closed"):
            raise RuntimeError("遥操已故障或关闭，无法继续记录 Episode")
        robot = self.runtime.robot
        if robot is None:
            raise RuntimeError("CR5 连接已丢失")

        sample_started_at = time.monotonic()
        recording_mode = self.runtime.store.data["dataset"]["recording_mode"]
        gello_joint_follow = (
            self.runtime.master_type == "gello"
            and state == "following"
            and self.runtime.store.data["gello"]["control_mode"] == "joint"
        )
        with self.runtime._state_lock:
            telemetry = self.runtime._gello_telemetry
            target_tcp = self.runtime._dataset_target_tcp_controller
            target_joints_deg = self.runtime._dataset_target_joints_deg
            action_timestamp = self.runtime._dataset_action_timestamp
        owner = self.runtime.motion.current_owner
        motion_error = self.runtime.motion.status.error
        if motion_error:
            raise RuntimeError(f"运动未正常结束，无法继续记录 Episode: {motion_error}")
        holding_last_target = owner is None and state == "idle" and not motion_error
        command = self.runtime.motion.last_joint_target
        tcp_command = self.runtime.motion.last_tcp_target
        if owner is not None or holding_last_target:
            if command is not None:
                target_joints_deg = tuple(math.degrees(v) for v in command.positions_rad)
                action_timestamp = command.timestamp
                if recording_mode == "tcp" and not (
                    state in ("preset", "recovering") and target_tcp is not None
                ):
                    target_tcp = robot.forward_kinematics(
                        list(target_joints_deg) + [command.auxiliary_axis_deg]
                    )
            elif state not in ("preset", "recovering"):
                target_joints_deg = None
            if tcp_command is not None:
                target_tcp = tuple(v * 1000.0 for v in tcp_command.xyz_m) + tuple(
                    tcp_command.rpy_rad
                )
                action_timestamp = tcp_command.timestamp
        elif state not in ("following", "preset", "recovering", "point_move", "replay", "dagger"):
            target_joints_deg = None
        quality = {}
        # The shared motion target supports Teleop, Replay, Policy, and point
        # motion. Taught HOME/preset targets also remain valid while moving.
        home_joint_action = (
            recording_mode == "joint" and not gello_joint_follow and target_joints_deg is not None
        )
        if (
            recording_mode == "joint"
            and (not gello_joint_follow or telemetry is None or not telemetry["sent_count"])
            and not home_joint_action
        ):
            raise RuntimeError("关节记录需要活动控制源的已下发目标")
        if gello_joint_follow and (telemetry is None or not telemetry["sent_count"]):
            quality["gello_telemetry_missing"] = 1.0
            gello_joint_follow = False
        if gello_joint_follow:
            age_limit = float(self.runtime.store.data["dataset"]["action_max_age_s"])
            feedback_age = sample_started_at - telemetry["feedback_at"]
            quality["feedback_age_s"] = feedback_age
            quality["feedback_stale"] = float(feedback_age > age_limit)
            pending_target_deg = float(telemetry.get("pending_target_deg", 0.0))
            duplicate_deadband = (
                float(self.runtime.store.data["robot"]["movej_duplicate_deadband_deg"])
                if getattr(self.runtime.robot, "motion_mode", "servoj") == "movej"
                else 0.0
            )
            validated_at = float(telemetry.get("validated_at", telemetry["command_at"]))
            effective_action_at = (
                validated_at
                if pending_target_deg <= duplicate_deadband
                else telemetry["command_at"]
            )
            action_age = sample_started_at - effective_action_at
            quality["sdk_submit_age_s"] = sample_started_at - telemetry["command_at"]
            quality["action_stale"] = float(action_age > age_limit)
            tracking_limit = float(self.runtime.store.data["dataset"]["max_tracking_error_deg"])
            tracking_error_deg = float(telemetry["tracking_error_deg"])
            quality["tracking_error_deg"] = tracking_error_deg
            quality["tracking_error_limit_deg"] = tracking_limit
            quality["tracking_error_exceeded"] = float(tracking_error_deg > tracking_limit)
            if telemetry.get("low_latency", False):
                desired_error = float(telemetry["desired_tracking_error_deg"])
                quality["desired_tracking_error_deg"] = desired_error
                quality["desired_tracking_error_exceeded"] = float(desired_error > tracking_limit)
            joints = list(telemetry["actual_deg"])
            target_joints_deg = tuple(telemetry["target_full_deg"][:6])
            if recording_mode == "tcp":
                target_tcp = robot.forward_kinematics(telemetry["target_full_deg"])
            quality["validated_target_age_s"] = sample_started_at - validated_at
            quality["pending_target_deg"] = pending_target_deg
            action_timestamp = effective_action_at
        else:
            joints = [float(value) for value in robot.joint_position()]
        if len(joints) < 6 or any(not math.isfinite(value) for value in joints[:6]):
            raise RuntimeError("CR5 六关节反馈无效")
        current_tcp = [float(value) for value in robot.tcp_position()]
        if len(current_tcp) < 6 or any(not math.isfinite(value) for value in current_tcp[:6]):
            raise RuntimeError("CR5 TCP 反馈无效")

        o6_position, o6_fault, o6_timestamp = self.runtime.o6.latest()
        now = time.monotonic()
        if o6_position is None or len(o6_position) != 6:
            raise RuntimeError("O6 位置反馈不完整")
        quality["o6_feedback_stale"] = float(
            now - o6_timestamp > float(self.runtime.store.data["o6"]["feedback_timeout_s"])
        )
        quality["o6_fault_present"] = float(o6_fault is None or any(o6_fault))

        commanded_tcp = target_tcp
        if target_tcp is None:
            target_tcp = current_tcp
        if state == "following":
            action_age_limit = float(self.runtime.store.data["dataset"]["action_max_age_s"])
            quality["action_stale"] = max(
                quality.get("action_stale", 0.0),
                float(now - action_timestamp > action_age_limit),
            )
        hand_command = getattr(self.runtime.o6, "last_sent_target", None)
        o6_target = hand_command
        if o6_target is None:
            o6_target = o6_position
        if len(o6_target) != 6:
            raise RuntimeError("O6 实际下发目标不完整")

        delta_xyz_m = [
            (float(target_tcp[index]) - current_tcp[index]) / 1000.0 for index in range(3)
        ]
        delta_rpy_rad = [
            _wrapped_angle_delta(float(target_tcp[index]), current_tcp[index])
            for index in range(3, 6)
        ]
        observation_state = (
            [math.radians(value) for value in joints[:6]]
            + [value / 1000.0 for value in current_tcp[:3]]
            + current_tcp[3:6]
            + [float(value) for value in o6_position]
        )

        action = delta_xyz_m + delta_rpy_rad + [float(value) for value in o6_target]
        if recording_mode == "joint":
            observation_state = observation_state[:6] + observation_state[12:]
            joint_targets_deg = (
                target_joints_deg if home_joint_action else telemetry["target_full_deg"][:6]
            )
            action = [math.radians(value) for value in joint_targets_deg] + [
                float(value) for value in o6_target
            ]

        quality["sample_latency_s"] = now - sample_started_at
        quality["command_age_s"] = now - action_timestamp
        return {
            "timestamp": now,
            "quality": quality,
            "observation_state": observation_state,
            "action": action,
            "recording_mode": recording_mode,
            "robot_joint_state": tuple(math.radians(value) for value in joints[:6]),
            "robot_joint_command": tuple(math.radians(v) for v in target_joints_deg)
            if target_joints_deg is not None
            else None,
            "robot_tcp_state": tuple(v / 1000.0 for v in current_tcp[:3]) + tuple(current_tcp[3:6]),
            "robot_tcp_command": tuple(v / 1000.0 for v in commanded_tcp[:3])
            + tuple(commanded_tcp[3:6])
            if commanded_tcp is not None
            else None,
            "hand_state": tuple(o6_position),
            "hand_command": tuple(hand_command) if hand_command is not None else None,
            "metadata": {
                "motion_source": owner.name if owner is not None else None,
                "motion_state": state,
                "holding_last_accepted_target": bool(
                    holding_last_target and (command is not None or tcp_command is not None)
                ),
            },
        }
