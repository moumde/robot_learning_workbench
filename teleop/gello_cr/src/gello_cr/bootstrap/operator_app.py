"""Compatibility alias for core.workbench.bootstrap.operator_app; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.bootstrap.operator_app')

_sys.modules[__name__] = _implementation
