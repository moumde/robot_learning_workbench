"""Metadata-only dataset browsing and explicit validation on data workers."""

import json
import threading
from pathlib import Path

from core.workbench.recording.validation_service import validate_in_worker


class DatasetCatalog:
    def __init__(self, recorder):
        self.recorder = recorder
        self._lock = threading.Lock()
        self._items = []
        self._root = ""
        self._reports = {}

    def scan(self, root):
        root = Path(root).expanduser().resolve()
        items = []
        if root.exists():
            candidates = (
                [root] if (root / "batch_provenance.json").exists() else sorted(root.iterdir())
            )
            for directory in candidates:
                if not directory.is_dir() or directory.name.startswith("."):
                    continue
                provenance = directory / "batch_provenance.json"
                session = directory / "meta" / "collection" / "session.json"
                if not (
                    provenance.exists() or session.exists() or (directory / "dataset.hdf5").exists()
                ):
                    continue
                try:
                    metadata = json.loads(session.read_text()) if session.exists() else {}
                    published = json.loads(provenance.read_text()) if provenance.exists() else {}
                    format_name = metadata.get("format_version") or published.get("dataset_format")
                    if not format_name:
                        format_name = (
                            "hdf5"
                            if (directory / "dataset.hdf5").exists()
                            else (
                                "lerobot_v21" if "_lerobot_v21" in directory.name else "lerobot_v3"
                            )
                        )
                    report = self._reports.get(str(directory))
                    items.append(
                        {
                            "path": str(directory),
                            "name": directory.name,
                            "task": metadata.get("task_name")
                            or published.get("task_name")
                            or directory.name,
                            "format": format_name,
                            "created_at": metadata.get("created_at")
                            or published.get("created_at", ""),
                            "status": ("VALID" if report["valid"] else "INVALID")
                            if report
                            else "UNCHECKED",
                            "episodes": (report or published.get("validation", {})).get(
                                "episode_count"
                            ),
                            "frames": (report or published.get("validation", {})).get(
                                "frame_count"
                            ),
                            "validation": report,
                        }
                    )
                except (OSError, ValueError) as exc:
                    items.append(
                        {
                            "path": str(directory),
                            "name": directory.name,
                            "task": "",
                            "format": "unknown",
                            "status": "INVALID",
                            "error": str(exc),
                        }
                    )
        with self._lock:
            self._items, self._root = items, str(root)
        return items

    def validate(self, path):
        path = str(Path(path).expanduser().resolve())
        with self._lock:
            selected = next((item for item in self._items if item["path"] == path), None)
        if selected is None:
            raise ValueError("请先扫描并选择数据集")
        snapshot = self.recorder.snapshot()
        if snapshot.get("session_active") and snapshot.get("root") == path:
            raise ValueError("当前数据集仍在写入，完成后再校验")
        report = validate_in_worker(selected["format"], path, self.recorder.writer_factory)
        self._reports[path] = report
        with self._lock:
            selected.update(
                validation=report,
                status="VALID" if report["valid"] else "INVALID",
                episodes=report["episode_count"],
                frames=report["frame_count"],
            )
        return report

    def snapshot(self):
        with self._lock:
            return {"root": self._root, "items": [dict(item) for item in self._items]}


def preview_dataset_name(task, format_name):
    from datetime import UTC, datetime

    from core.workbench.recording.metadata import build_dataset_name

    if not task.strip():
        return "填写任务名称后预览数据集名称"
    name = build_dataset_name(task, datetime.now(UTC).isoformat(), format_name)
    return f"名称预览：{name}（发布时附加唯一 ID）"
