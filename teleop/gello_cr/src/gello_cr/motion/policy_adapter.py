"""Compatibility alias for core.workbench.motion.policy_adapter; no duplicated implementation."""

import sys as _sys
from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.motion.policy_adapter')

_sys.modules[__name__] = _implementation
