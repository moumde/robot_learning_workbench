"""Compatibility entry for the parent collection console."""
from hmi.collection.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
