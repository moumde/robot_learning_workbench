"""Compatibility alias for teleop.devices.roarm; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('teleop.devices.roarm')

_sys.modules[__name__] = _implementation
