"""Launch GELLO with the parent workbench configuration and shared hardware."""

from __future__ import annotations

import argparse
import os
from functools import partial
from pathlib import Path

from .workbench import REPO_ROOT, IntegratedConfigStore, WorkbenchRuntimeFactory, workbench_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=os.environ.get("GELLO_CR_REPO_ROOT") or REPO_ROOT)
    parser.add_argument("--config", type=Path, help="GELLO JSON path, relative to the parent repository")
    parser.add_argument("--hardware-config", type=Path, help="Override the shared hardware TOML, relative to the parent repository")
    parser.add_argument("--check-only", action="store_true", help="Construct and close the offline application without connecting hardware")
    args = parser.parse_args(argv)
    paths = workbench_paths(args.repo_root, args.config)

    from gello_cr.bootstrap import build_operator_application
    from gello_cr.ui.__main__ import main as ui_main

    def application_factory(repo_root):
        return build_operator_application(
            repo_root,
            factory=WorkbenchRuntimeFactory(paths, hardware_config=args.hardware_config),
        )

    return ui_main(
        ["--repo-root", str(paths.repo_root), *(["--check-only"] if args.check_only else [])],
        application_factory=application_factory,
        settings_store_factory=partial(
            IntegratedConfigStore.from_file, repo_root=paths.repo_root,
            hardware_config=args.hardware_config,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
