
from __future__ import annotations

import time

import numpy as np
import pytest

from core.workbench.recording.source import CR3O6CaptureSource


class Engine:
    def dataset_sample(self):
        return {"quality": {}}


def _source():
    return CR3O6CaptureSource(
        Engine().dataset_sample,
        {
            "camera_max_age_s": 0.5,
            "camera_max_skew_s": 0.1,
        },
    )


def test_preview_snapshot_starts_empty() -> None:
    source = _source()

    preview = source.preview_snapshot()

    assert preview["base_rgb"] is None
    assert preview["wrist_rgb"] is None
    assert preview["roi_rgb"] is None


def test_preview_snapshot_contains_all_three_images() -> None:
    source = _source()
    now = time.monotonic()
    base = np.zeros((4, 5, 3), dtype=np.uint8)
    wrist = np.ones((4, 5, 3), dtype=np.uint8)
    roi = np.full((2, 3, 3), 2, dtype=np.uint8)

    source.update_wrist(wrist, now)
    source.update_base(base, roi, now)
    preview = source.preview_snapshot()

    assert np.array_equal(preview["base_rgb"], base)
    assert np.array_equal(preview["wrist_rgb"], wrist)
    assert np.array_equal(preview["roi_rgb"], roi)


def test_preview_reuses_immutable_frames_detached_from_the_producer() -> None:
    source = _source()
    now = time.monotonic()
    base = np.zeros((4, 5, 3), dtype=np.uint8)
    wrist = np.zeros((4, 5, 3), dtype=np.uint8)
    roi = np.zeros((2, 3, 3), dtype=np.uint8)

    source.update_wrist(wrist, now)
    source.update_base(base, roi, now)
    preview = source.preview_snapshot()

    base[0, 0, 0] = 255
    second = source.preview_snapshot()
    assert second["base_rgb"] is preview["base_rgb"]
    assert second["base_rgb"][0, 0, 0] == 0
    with pytest.raises(ValueError):
        preview["base_rgb"][0, 0, 0] = 255
    with pytest.raises(ValueError):
        preview["base_rgb"].setflags(write=True)


def test_stale_preview_reports_zero_current_fps(monkeypatch):
    source = _source()
    image = np.zeros((4, 5, 3), dtype=np.uint8)
    source.update_stream(0, image, 100.0)
    source.update_stream(0, image, 100.1)
    monkeypatch.setattr('core.workbench.recording.source.time.monotonic', lambda: 101.0)
    stream = source.preview_snapshot()['streams'][0]
    assert stream['status'] == 'STALE'
    assert stream['fps'] == 0.0
    assert stream['last_fps'] == pytest.approx(10.0)


def test_clear_removes_preview_frames() -> None:
    source = _source()
    now = time.monotonic()
    image = np.zeros((4, 5, 3), dtype=np.uint8)
    source.update_wrist(image, now)
    source.update_base(image, image, now)

    source.clear_wrist()
    source.clear_base()
    preview = source.preview_snapshot()

    assert preview["base_rgb"] is None
    assert preview["wrist_rgb"] is None
    assert preview["roi_rgb"] is None
