"""Compatibility entry and import alias for the parent collection console."""
import sys as _sys
from importlib import import_module as _import_module

if __name__ == "__main__":
    from hmi.collection.__main__ import main
    raise SystemExit(main())
else:
    _sys.modules[__name__] = _import_module("hmi.collection.__main__")
