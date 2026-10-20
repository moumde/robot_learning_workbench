"""Compatibility package for the parent collection UI."""
from importlib import import_module as _import_module
_parent = _import_module('hmi.collection.controllers')
__all__ = getattr(_parent, "__all__", [n for n in vars(_parent) if not n.startswith("_")])
globals().update({n: getattr(_parent, n) for n in __all__})
def __getattr__(name):
    return getattr(_parent, name)
