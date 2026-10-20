"""Compatibility import for the parent-owned RealSense RGB backend."""

import sys

from core.hardware import realsense as _implementation

sys.modules[__name__] = _implementation
