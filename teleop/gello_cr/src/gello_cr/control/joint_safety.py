"""Compatibility alias for teleop.gello_cr.joint_safety; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('teleop.gello_cr.joint_safety')

_sys.modules[__name__] = _implementation
