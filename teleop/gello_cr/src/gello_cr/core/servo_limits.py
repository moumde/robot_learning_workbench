"""Compatibility alias for core.workbench.core.servo_limits; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.core.servo_limits')

_sys.modules[__name__] = _implementation
