"""Compatibility alias for core.hardware.o6; one shared implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module("core.hardware.o6")
_sys.modules[__name__] = _implementation
