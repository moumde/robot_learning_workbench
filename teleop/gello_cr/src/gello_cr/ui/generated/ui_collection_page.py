"""Compatibility import; implementation lives in the parent workbench."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module('hmi.collection.generated.ui_collection_page')
