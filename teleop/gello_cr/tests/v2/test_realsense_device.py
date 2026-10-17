from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pytest

from gello_cr.devices.realsense import RealSenseRgbConfig, RealSenseRgbDevice


class FakeColorFrame:
    def __init__(self, image: np.ndarray) -> None:
        self._image = image

    def get_data(self) -> np.ndarray:
        return self._image


class FakeFrames:
    def __init__(self, image: np.ndarray | None) -> None:
        self._image = image

    def get_color_frame(self) -> FakeColorFrame | None:
        if self._image is None:
            return None
        return FakeColorFrame(self._image)


class FakeConfig:
    def __init__(self) -> None:
        self.serial: str | None = None
        self.stream_args: tuple[Any, ...] | None = None

    def enable_device(self, serial: str) -> None:
        self.serial = serial

    def enable_stream(self, *args: Any) -> None:
        self.stream_args = args


class FakePipeline:
    def __init__(self, frames: list[np.ndarray | None]) -> None:
        self.frames = deque(frames)
        self.started_with: FakeConfig | None = None
        self.start_count = 0
        self.stop_count = 0

    def start(self, config: FakeConfig) -> None:
        self.started_with = config
        self.start_count += 1

    def poll_for_frames(self) -> FakeFrames | None:
        if not self.frames:
            return None
        return FakeFrames(self.frames.popleft())

    def stop(self) -> None:
        self.stop_count += 1


class FakeRs:
    class stream:
        color = "color"

    class format:
        bgr8 = "bgr8"

    def __init__(self, frame_sets: list[list[np.ndarray | None]]) -> None:
        self.frame_sets = deque(frame_sets)
        self.configs: list[FakeConfig] = []
        self.pipelines: list[FakePipeline] = []

    def config(self) -> FakeConfig:
        config = FakeConfig()
        self.configs.append(config)
        return config

    def pipeline(self) -> FakePipeline:
        frames = self.frame_sets.popleft() if self.frame_sets else []
        pipeline = FakePipeline(frames)
        self.pipelines.append(pipeline)
        return pipeline


def _tiny_config(serial: str = "CAM123") -> RealSenseRgbConfig:
    return RealSenseRgbConfig(
        serial=serial,
        width=2,
        height=1,
        fps=30,
        poll_sleep_s=0.001,
    )


def test_realsense_connect_configures_serial_stream_and_converts_bgr_to_rgb() -> None:
    bgr = np.array([[[1, 2, 3], [10, 20, 30]]], dtype=np.uint8)
    rs = FakeRs([[bgr]])
    device = RealSenseRgbDevice(_tiny_config(), rs_module=rs)

    try:
        snapshot = device.connect(timeout=0.2)

        config = rs.configs[0]
        assert config.serial == "CAM123"
        assert config.stream_args == ("color", 2, 1, "bgr8", 30)

        assert snapshot.serial == "CAM123"
        assert snapshot.width == 2
        assert snapshot.height == 1
        np.testing.assert_array_equal(
            snapshot.image_rgb,
            np.array([[[3, 2, 1], [30, 20, 10]]], dtype=np.uint8),
        )
    finally:
        device.close()


def test_realsense_latest_returns_copy_not_worker_owned_array() -> None:
    bgr = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    rs = FakeRs([[bgr]])
    device = RealSenseRgbDevice(_tiny_config(), rs_module=rs)

    try:
        first = device.connect(timeout=0.2)
        second = device.latest()
        assert second is not None

        first.image_rgb[0, 0, 0] = 255
        third = device.latest()
        assert third is not None
        assert third.image_rgb[0, 0, 0] == 3
    finally:
        device.close()


def test_realsense_invalid_shape_fails_connection() -> None:
    wrong = np.zeros((2, 2, 3), dtype=np.uint8)
    rs = FakeRs([[wrong]])
    device = RealSenseRgbDevice(_tiny_config(), rs_module=rs)

    with pytest.raises(RuntimeError, match="shape mismatch"):
        device.connect(timeout=0.2)

    assert rs.pipelines[0].stop_count >= 1


def test_realsense_timeout_stops_pipeline() -> None:
    rs = FakeRs([[]])
    device = RealSenseRgbDevice(_tiny_config(), rs_module=rs)

    with pytest.raises(TimeoutError, match="did not produce"):
        device.connect(timeout=0.03)

    assert rs.pipelines[0].stop_count >= 1
    assert not device.connected


def test_realsense_close_stops_pipeline_and_clears_latest() -> None:
    bgr = np.zeros((1, 2, 3), dtype=np.uint8)
    rs = FakeRs([[bgr]])
    device = RealSenseRgbDevice(_tiny_config(), rs_module=rs)

    device.connect(timeout=0.2)
    assert device.connected
    device.close()

    assert rs.pipelines[0].stop_count >= 1
    assert not device.connected
    assert device.latest() is None


def test_two_realsense_devices_keep_wrist_and_base_serials_independent() -> None:
    wrist_bgr = np.array([[[1, 0, 0], [1, 0, 0]]], dtype=np.uint8)
    base_bgr = np.array([[[0, 1, 0], [0, 1, 0]]], dtype=np.uint8)

    wrist_rs = FakeRs([[wrist_bgr]])
    base_rs = FakeRs([[base_bgr]])

    wrist = RealSenseRgbDevice(_tiny_config("WRIST"), rs_module=wrist_rs)
    base = RealSenseRgbDevice(_tiny_config("BASE"), rs_module=base_rs)

    try:
        wrist_snapshot = wrist.connect(timeout=0.2)
        base_snapshot = base.connect(timeout=0.2)

        assert wrist_snapshot.serial == "WRIST"
        assert base_snapshot.serial == "BASE"
        assert wrist_rs.configs[0].serial == "WRIST"
        assert base_rs.configs[0].serial == "BASE"
    finally:
        wrist.close()
        base.close()
