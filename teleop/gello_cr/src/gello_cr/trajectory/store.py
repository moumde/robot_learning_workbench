"""Compatibility alias for core.workbench.trajectory.store; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.trajectory.store')

_sys.modules[__name__] = _implementation
