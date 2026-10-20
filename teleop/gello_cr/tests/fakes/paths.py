"""Locate canonical source for existing implementation-boundary checks."""
from importlib import import_module
from pathlib import Path

LEGACY_ROOT = Path(__file__).resolve().parents[2]

def implementation_path(relative):
    prefix = "src/gello_cr/"
    if relative.startswith(prefix):
        module = "gello_cr." + relative[len(prefix):].removesuffix(".py").replace("/", ".")
        return Path(import_module(module).__file__)
    return LEGACY_ROOT / relative
