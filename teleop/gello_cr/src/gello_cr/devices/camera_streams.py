"""Compatibility alias for core.hardware.camera_streams; one shared implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module("core.hardware.camera_streams")
_sys.modules[__name__] = _implementation
