"""Dataset worker entry point for the dedicated recording Python environment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The recording environment need not install the operator package. Direct
# execution locates the same package tree as the parent recorder process.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gello_cr.recording.worker_loop import run_worker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-fd", type=int, required=True)
    args = parser.parse_args()
    return run_worker(args.worker_fd)


if __name__ == "__main__":
    raise SystemExit(main())
