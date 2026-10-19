from __future__ import annotations

from pathlib import Path

from hmi.trainui.models import ConfigInfo


class CheckpointService:
    @staticmethod
    def latest_step(experiment_dir: Path) -> int | None:
        if not experiment_dir.is_dir():
            return None
        steps = []
        for child in experiment_dir.iterdir():
            if not child.is_dir() or not child.name.isdigit():
                continue
            # OpenPI checkpoints contain a params subtree. During an in-progress
            # save, the step directory may exist before it becomes usable.
            if (child / "params").exists():
                steps.append(int(child.name))
        return max(steps) if steps else None

    @classmethod
    def status(cls, config: ConfigInfo, exp_name: str) -> tuple[Path, int | None]:
        directory = config.checkpoint_dir(exp_name)
        return directory, cls.latest_step(directory)
