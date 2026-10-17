import json
from types import SimpleNamespace

import numpy as np
import pytest

from gello_cr.app.datasets import DatasetCatalog
from gello_cr.recording.source import CR3O6CaptureSource


def test_catalog_lists_without_validation_and_validates_only_on_explicit_command(
    tmp_path, monkeypatch
):
    root = tmp_path / "pick_20261015_lerobot_v3"
    root.mkdir()
    (root / "batch_provenance.json").write_text(
        json.dumps(
            {
                "dataset_format": "lerobot_v3",
                "task_name": "pick",
                "created_at": "2026-10-15",
                "validation": {"valid": True, "episode_count": 3, "frame_count": 100},
            }
        )
    )
    recorder = SimpleNamespace(snapshot=lambda: {}, writer_factory=object())
    catalog = DatasetCatalog(recorder)
    items = catalog.scan(tmp_path)
    assert items[0]["status"] == "UNCHECKED"
    assert items[0]["episodes"] == 3
    report = {
        "valid": False,
        "errors": ["Episode 1 frame mismatch"],
        "warnings": [],
        "episode_count": 3,
        "frame_count": 99,
    }
    calls = []
    monkeypatch.setattr(
        "gello_cr.app.datasets.validate_in_worker", lambda *a: calls.append(a) or report
    )
    assert catalog.validate(root) == report
    assert len(calls) == 1
    assert catalog.snapshot()["items"][0]["status"] == "INVALID"


def test_camera_metadata_reports_each_stream_independently_without_robot_io(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("gello_cr.recording.source.time.monotonic", lambda: clock[0])
    source = CR3O6CaptureSource(lambda: None, {"camera_max_age_s": 0.5})
    image = np.zeros((4, 4, 3), np.uint8)
    for i in range(3):
        source.update_stream(i, image, 9.9)
    source.update_stream(0, image, 10.0)
    view = source.preview_snapshot()
    assert view["streams"][0]["fps"] == pytest.approx(10.0)
    clock[0] = 10.45
    view = source.preview_snapshot()
    assert [s["status"] for s in view["streams"]] == ["OK", "STALE", "STALE"]
