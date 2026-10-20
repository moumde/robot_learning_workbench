"""Production entry point for Robot Learning Workbench.

Examples:

    python -m hmi.collection --check-only
    python -m hmi.collection

Neither mode automatically connects hardware.
"""

from __future__ import annotations

import argparse
import os
import sys
from functools import partial
from pathlib import Path

from core.workbench import __version__
from core.workbench.app.settings import OperatorSettings
from core.workbench.bootstrap import build_operator_application
from core.workbench.core.state_machine import WorkflowState
from core.workbench.logging_config import configure_logging
from core.workbench.paths import workbench_root


def _default_repo_root() -> Path:
    configured = os.environ.get("WORKBENCH_ROOT") or os.environ.get("GELLO_CR_REPO_ROOT")
    return workbench_root(configured) if configured else workbench_root()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Robot Learning Workbench",
    )
    parser.add_argument(
        "--repo-root",
        default=str(_default_repo_root()),
        help="parent robot_learning_workbench repository root",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "construct the runtime/backend and exit without importing "
            "PySide6 or connecting hardware"
        ),
    )
    parser.add_argument("--config", type=Path, help="Collection JSON relative to the parent repository")
    parser.add_argument("--hardware-config", type=Path, help="Shared hardware TOML relative to the parent repository")
    return parser


def main(
    argv: list[str] | None = None, *, application_factory=None, settings_store_factory=None
) -> int:
    parser = _parser()
    args, unknown = parser.parse_known_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()

    if unknown:
        parser.error("unrecognized arguments: " + " ".join(unknown))
    if application_factory is None:
        from core.workbench.composition import (
            IntegratedConfigStore,
            WorkbenchRuntimeFactory,
            workbench_paths,
        )
        repo_root = workbench_root(repo_root)
        paths = workbench_paths(repo_root, args.config)
        factory = partial(
            build_operator_application,
            factory=WorkbenchRuntimeFactory(paths, hardware_config=args.hardware_config),
        )
        if settings_store_factory is None:
            settings_store_factory = partial(
                IntegratedConfigStore.from_file, repo_root=repo_root,
                hardware_config=args.hardware_config,
            )
    else:
        factory = application_factory
    operator = factory(repo_root)
    configure_logging(operator.runtime.store.data["logging"]["level"])
    try:
        if operator.backend.service.state is not WorkflowState.OFFLINE:
            raise RuntimeError("Workbench must start OFFLINE")
        if operator.cameras.running:
            raise RuntimeError("camera service unexpectedly started")

        if args.check_only:
            runtime = operator.runtime
            master_type = str(runtime.store.data["master"]["type"])
            print(
                f"Robot Learning Workbench v{__version__}\n"
                f"repo_root={repo_root}\n"
                f"workflow={operator.backend.service.state.name}\n"
                f"master={master_type}\n"
                "cameras=stopped\n"
                "hardware_connections=not_started"
            )
            return 0

        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as exc:
            raise SystemExit(
                "PySide6 is not installed. Install the project UI extra "
                "before launching the Workbench window."
            ) from exc

        from hmi.collection.session import create_operator_window

        store_factory = (
            type(operator.runtime.store)
            if settings_store_factory is None
            else settings_store_factory
        )
        qt_app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
        window = create_operator_window(
            operator.backend,
            close_callback=operator.close,
            refresh_ms=operator.runtime.store.data["ui"]["refresh_ms"],
            settings_factory=lambda: OperatorSettings(operator.runtime.store.path, store_factory),
        )

        dataset_cfg = operator.runtime.store.data["dataset"]
        window.collection.task_edit.setText(str(dataset_cfg.get("task_name", "collection")))
        window.collection.description_edit.setText(str(dataset_cfg["task"]))
        window.collection.root_edit.setText(
            str(operator.runtime.store.resolve_path(dataset_cfg["root"]))
        )

        def persist_dataset_root():
            path = window.collection.root_edit.text().strip()
            if not path:
                window.statusBar().showMessage("数据集父目录不能为空")
                return
            path = str(operator.runtime.store.resolve_path(path))
            try:
                settings = OperatorSettings(operator.runtime.store.path, store_factory)
                if settings.data["dataset"]["root"] != path:
                    settings.data["dataset"]["root"] = path
                    settings.save(settings.data)
                window.collection.root_edit.setText(path)
            except Exception as exc:
                window.statusBar().showMessage(f"默认保存目录未能写入配置：{exc}")

        window.collection.root_edit.editingFinished.connect(persist_dataset_root)
        window.statusBar().showMessage(
            "OFFLINE · cameras stopped · no hardware auto-connect",
            15000,
        )

        qt_app.aboutToQuit.connect(operator.close)
        window.show()
        return int(qt_app.exec())
    finally:
        if args.check_only:
            operator.close()


if __name__ == "__main__":
    raise SystemExit(main())
