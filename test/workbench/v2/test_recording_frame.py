from __future__ import annotations

import numpy as np
import pytest

from core.workbench.recording.frame import CaptureFrame
from core.workbench.recording.schema import IMAGE_KEYS
from core.workbench.recording.writers.lerobot_v3 import prepare_frame, resize_rgb_for_openpi


def _sample(value_base: int = 1, value_wrist: int = 2, value_roi: int = 3):
    return CaptureFrame(
        10.0,
        tuple(range(18)),
        tuple(range(12)),
        {
            key: np.full((2, 2, 3), value, dtype=np.uint8)
            for key, value in zip(IMAGE_KEYS, (value_base, value_wrist, value_roi), strict=True)
        },
    )


def test_resize_same_shape_returns_contiguous_uint8() -> None:
    source = np.ones((224, 224, 3), dtype=np.uint8)
    result = resize_rgb_for_openpi(source)

    assert result.shape == (224, 224, 3)
    assert result.dtype == np.uint8
    assert result.flags["C_CONTIGUOUS"]


def test_resize_640x480_preserves_aspect_with_vertical_black_padding() -> None:
    source = np.full((480, 640, 3), 255, dtype=np.uint8)
    result = resize_rgb_for_openpi(source, 224, 224)

    assert result.shape == (224, 224, 3)
    assert np.all(result[:28] == 0)
    assert np.all(result[28:196] == 255)
    assert np.all(result[196:] == 0)


def test_resize_float_zero_one_scales_to_uint8() -> None:
    source = np.ones((10, 10, 3), dtype=np.float32)
    result = resize_rgb_for_openpi(source, 10, 10)

    assert result.dtype == np.uint8
    assert np.all(result == 255)


def test_resize_rejects_non_rgb_shape() -> None:
    with pytest.raises(ValueError, match="HxWx3"):
        resize_rgb_for_openpi(np.zeros((10, 10), dtype=np.uint8))


def test_prepare_frame_preserves_add_frame_payload_contract() -> None:
    prepared = prepare_frame(
        _sample(),
        task="Pick object",
        height=2,
        width=2,
        recording_mode="tcp",
    )

    assert prepared[0] == {
        "op": "add_frame",
        "recording_mode": "tcp",
        "state": [float(value) for value in range(18)],
        "action": [float(value) for value in range(12)],
        "task": "Pick object",
        "height": 2,
        "width": 2,
        "sample_metadata": {"timestamp": 10.0, "quality": {}},
    }


def test_prepare_frame_raw_order_is_base_wrist_roi() -> None:
    prepared = prepare_frame(
        _sample(),
        task="task",
        height=2,
        width=2,
        recording_mode="tcp",
    )

    image_bytes = 2 * 2 * 3
    assert prepared[1][:image_bytes] == bytes([1]) * image_bytes
    assert prepared[1][image_bytes : 2 * image_bytes] == bytes([2]) * image_bytes
    assert prepared[1][2 * image_bytes :] == bytes([3]) * image_bytes


def test_prepare_frame_raw_size_is_three_rgb_images() -> None:
    prepared = prepare_frame(
        _sample(),
        task="task",
        height=2,
        width=2,
        recording_mode="tcp",
    )

    assert len(prepared[1]) == 3 * 2 * 2 * 3


def test_prepare_frame_reuses_frozen_sample_validation() -> None:
    sample = _sample()
    from dataclasses import replace

    sample = replace(sample, action=(0.0,) * 11)

    with pytest.raises(ValueError, match="12"):
        prepare_frame(sample, task="task", height=2, width=2, recording_mode="tcp")
