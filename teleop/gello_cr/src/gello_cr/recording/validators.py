"""Compatibility alias for core.workbench.recording.validators; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.recording.validators')

_sys.modules[__name__] = _implementation
