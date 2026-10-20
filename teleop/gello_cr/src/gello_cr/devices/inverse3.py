"""Compatibility alias for teleop.devices.inverse3; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('teleop.devices.inverse3')

_sys.modules[__name__] = _implementation
