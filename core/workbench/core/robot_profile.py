"""Robot identity and capabilities consumed by generic operator views."""

from dataclasses import dataclass, fields
from typing import Any


@dataclass(frozen=True, slots=True)
class RobotCapabilities:
    supports_home: bool = False
    supports_gripper: bool = False
    supports_dual_arm: bool = False
    supports_joint_control: bool = False
    supports_cartesian_control: bool = False
    supports_freedrive: bool = False

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None):
        data = value or {}
        return cls(**{field.name: bool(data.get(field.name, False)) for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class RobotDescriptor:
    profile: str
    name: str
    joint_names: tuple[str, ...]
    end_effector: str
    hand_required: bool
    capabilities: RobotCapabilities
