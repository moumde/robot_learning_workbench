"""Descriptions registered alongside supported hardware construction."""

from dataclasses import replace

from core.workbench.core.robot_profile import RobotCapabilities, RobotDescriptor

ROBOT_PROFILES = {
    "cr3a_o6": RobotDescriptor(
        profile="cr3a_o6",
        name="CR3A + O6",
        joint_names=("J1", "J2", "J3", "J4", "J5", "J6"),
        end_effector="O6",
        hand_required=True,
        capabilities=RobotCapabilities(
            supports_home=True,
            supports_gripper=True,
            supports_joint_control=True,
            supports_cartesian_control=True,
        ),
    ),
}


def describe_robot(config) -> RobotDescriptor:
    hardware = config["hardware"]
    descriptor = ROBOT_PROFILES[hardware["profile"]]
    return replace(descriptor, name=hardware.get("name") or descriptor.name)
