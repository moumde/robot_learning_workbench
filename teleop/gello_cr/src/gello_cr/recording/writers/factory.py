"""Compatibility alias for core.workbench.recording.writers.factory; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.recording.writers.factory')

_sys.modules[__name__] = _implementation
