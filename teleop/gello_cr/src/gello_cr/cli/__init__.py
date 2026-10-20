"""Compatibility exports for core.workbench.cli; implementation lives in the parent."""

from importlib import import_module as _import_module

_implementation = _import_module('core.workbench.cli')
__all__ = getattr(_implementation, "__all__", [
    name for name in vars(_implementation) if not name.startswith("_")
])


def __getattr__(name):
    return getattr(_implementation, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_implementation)))
