"""Compatibility alias for teleop.gello_cr.kinematics; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('teleop.gello_cr.kinematics')

_sys.modules[__name__] = _implementation
