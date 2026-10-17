from __future__ import annotations

import math

import numpy as np
import pytest

from gello_cr.recording.image_processing import (
    crop_normalized_roi,
    normalized_roi_bounds,
)


def test_actual_base_roi_preserves_legacy_640x480_pixel_bounds() -> None:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    roi_norm = (0.37, 0.56, 0.55, 0.79)

    bounds = normalized_roi_bounds(image, roi_norm)

    assert bounds == (237, 269, 352, 379)


def test_actual_base_roi_crop_shape_matches_legacy_behavior() -> None:
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    result = crop_normalized_roi(
        image,
        (0.37, 0.56, 0.55, 0.79),
    )

    assert result.bounds_px == (237, 269, 352, 379)
    assert result.image_rgb.shape == (110, 115, 3)
    assert result.image_rgb.flags.c_contiguous


def test_roi_bounds_preserve_legacy_clamping_semantics() -> None:
    image = np.zeros((10, 20, 3), dtype=np.uint8)

    assert normalized_roi_bounds(
        image,
        (-0.5, -1.0, 2.0, 3.0),
    ) == (0, 0, 20, 10)


def test_degenerate_roi_is_forced_to_at_least_one_pixel() -> None:
    image = np.zeros((10, 20, 3), dtype=np.uint8)

    bounds = normalized_roi_bounds(
        image,
        (0.9, 0.9, 0.1, 0.1),
    )

    left, top, right, bottom = bounds
    assert right == left + 1
    assert bottom == top + 1


def test_roi_rejects_invalid_coordinate_vector() -> None:
    image = np.zeros((10, 20, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="exactly four"):
        normalized_roi_bounds(image, (0.1, 0.2, 0.3))

    with pytest.raises(ValueError, match="finite"):
        normalized_roi_bounds(
            image,
            (0.1, 0.2, math.inf, 0.4),
        )


def test_crop_returns_independent_copy() -> None:
    image = np.zeros((10, 20, 3), dtype=np.uint8)
    image[2:5, 4:8] = 17

    result = crop_normalized_roi(
        image,
        (0.2, 0.2, 0.4, 0.5),
    )
    result.image_rgb[:] = 99

    assert np.all(image[2:5, 4:8] == 17)
