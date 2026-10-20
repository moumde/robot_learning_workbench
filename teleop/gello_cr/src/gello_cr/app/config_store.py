"""Compatibility alias for core.workbench.app.config_store; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.app.config_store')

_sys.modules[__name__] = _implementation
