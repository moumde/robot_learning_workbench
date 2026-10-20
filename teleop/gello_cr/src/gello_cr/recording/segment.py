"""Compatibility alias for core.workbench.recording.segment; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.recording.segment')

_sys.modules[__name__] = _implementation
