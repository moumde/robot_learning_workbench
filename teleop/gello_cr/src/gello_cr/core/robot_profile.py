"""Compatibility alias for core.workbench.core.robot_profile; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.core.robot_profile')

_sys.modules[__name__] = _implementation
