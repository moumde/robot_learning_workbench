"""Preview trajectories, or execute with the parent hardware profile and lock."""

from __future__ import annotations

import argparse
import os
from functools import partial
from pathlib import Path

from .composition import REPO_ROOT, WorkbenchRuntimeFactory, workbench_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo-root", type=Path, default=os.environ.get("GELLO_CR_REPO_ROOT") or REPO_ROOT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--hardware-config", type=Path)
    args, replay_args = parser.parse_known_args(argv)
    paths = workbench_paths(args.repo_root, args.config)

    from core.workbench.cli.replay_trajectory import main as replay_main

    return replay_main(
        [*replay_args, "--repo-root", str(paths.repo_root), "--config", str(paths.config_path)],
        runtime_factory=partial(WorkbenchRuntimeFactory, hardware_config=args.hardware_config),
    )


if __name__ == "__main__":
    raise SystemExit(main())
