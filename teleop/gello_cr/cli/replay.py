"""Preview trajectories, or execute with the parent hardware profile and lock."""

from __future__ import annotations

import argparse
import logging
import os
from functools import partial
from pathlib import Path

from teleop.gello_cr.bootstrap.composition import (
    REPO_ROOT,
    WorkbenchRuntimeFactory,
    workbench_paths,
)
from teleop.gello_cr.support.logging_config import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo-root", type=Path, default=os.environ.get("GELLO_CR_REPO_ROOT") or REPO_ROOT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--hardware-config", type=Path)
    args, replay_args = parser.parse_known_args(argv)
    configure_logging(repo_root=args.repo_root)
    try:
        paths = workbench_paths(args.repo_root, args.config)

        from teleop.gello_cr.cli.replay_trajectory import main as replay_main

        return replay_main(
            [*replay_args, "--repo-root", str(paths.repo_root), "--config", str(paths.config_path)],
            runtime_factory=partial(WorkbenchRuntimeFactory, hardware_config=args.hardware_config),
        )
    except Exception:
        logging.getLogger("workbench.replay").exception("Replay startup or execution failed")
        raise



if __name__ == "__main__":
    raise SystemExit(main())
