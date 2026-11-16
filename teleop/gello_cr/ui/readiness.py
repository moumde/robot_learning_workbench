"""Read-only device/camera readiness model for the new operator UI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from teleop.gello_cr.core.robot_profile import RobotCapabilities


@dataclass(frozen=True, slots=True)
class OperatorReadiness:
    master_type: str = "unknown"
    master_connected: bool = False
    o6_connected: bool = False
    cameras_running: bool = False
    camera_frames_ready: bool = False
    camera_error: str = ""
    master_error: str = ""
    o6_error: str = ""
    robot_profile: str = ""
    robot_name: str = "未配置机器人"
    robot_endpoint: str = ""
    robot_connected: bool | None = None
    servo_state: str | None = None
    robot_feedback_age_s: float | None = None
    robot_error: str = ""
    master_ready: bool | None = None
    hand_ready: bool | None = None
    master_discovered: bool | None = None
    hand_required: bool = True
    capabilities: RobotCapabilities = RobotCapabilities()

    @property
    def devices_ready(self) -> bool:
        master = self.master_connected if self.master_ready is None else self.master_ready
        hand = self.o6_connected if self.hand_ready is None else self.hand_ready
        return bool(
            master
            and not self.master_error
            and (not self.hand_required or hand and not self.o6_error)
        )

    @classmethod
    def from_mapping(
        cls,
        snapshot: Mapping[str, Any] | None,
    ) -> OperatorReadiness:
        data = snapshot or {}
        return cls(
            robot_profile=str(data.get("robot_profile", "")),
            robot_name=str(data.get("robot_name", "未配置机器人")),
            robot_endpoint=str(data.get("robot_endpoint", "")),
            robot_connected=data.get("robot_connected"),
            servo_state=data.get("servo_state"),
            robot_feedback_age_s=data.get("robot_feedback_age_s"),
            robot_error=str(data.get("robot_error", "") or ""),
            master_ready=data.get("master_ready"),
            hand_ready=data.get("hand_ready"),
            master_discovered=data.get("master_discovered"),
            hand_required=bool(data.get("hand_required", True)),
            capabilities=RobotCapabilities.from_mapping(data.get("capabilities")),
            master_error=str(data.get("master_error", "")),
            o6_error=str(data.get("o6_error", "")),
            master_type=str(data.get("master_type", "unknown")).strip() or "unknown",
            master_connected=bool(data.get("master_connected", False)),
            o6_connected=bool(data.get("o6_connected", False)),
            cameras_running=bool(data.get("cameras_running", False)),
            camera_frames_ready=bool(data.get("camera_frames_ready", False)),
            camera_error=str(data.get("camera_error", "") or "").strip(),
        )
