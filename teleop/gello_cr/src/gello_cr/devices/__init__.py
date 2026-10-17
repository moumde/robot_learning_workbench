"""Hardware adapters.

Vendor SDKs stay below this boundary. UI/application code imports contracts or
these adapters, never NRC/Dynamixel/LinkerHand/RealSense SDKs directly.
"""

from .cr3a import Cr3aConfig, Cr3aDevice
from .gello import GelloConfig, GelloDevice
from .nrc_robot import NrcRobotSession, NrcServoTransition
from .o6 import O6Config, O6Device
from .realsense import RealSenseRgbConfig, RealSenseRgbDevice

__all__ = [
    "Cr3aConfig",
    "Cr3aDevice",
    "GelloConfig",
    "GelloDevice",
    "NrcRobotSession",
    "NrcServoTransition",
    "O6Config",
    "O6Device",
    "RealSenseRgbConfig",
    "RealSenseRgbDevice",
]
