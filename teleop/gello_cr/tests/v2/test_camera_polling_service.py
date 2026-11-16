
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pytest

from teleop.gello_cr.bootstrap.camera_service import CameraPollingService
from teleop.gello_cr.hardware.camera_streams import CameraStreamConfig


@dataclass
class Snapshot:
    image_rgb: np.ndarray
    timestamp: float


class Camera:
    def __init__(self, image, *, fail=False):
        self.image = image
        self.fail = fail
        self.connected = False
        self.error = ""
        self.closed = 0
        self.connect_calls = 0
        self.timestamp = time.monotonic()

    def connect(self, timeout=5.0):
        self.connect_calls += 1
        if self.fail:
            raise RuntimeError("camera connect failed")
        self.connected = True
        self.timestamp = time.monotonic()
        return Snapshot(self.image, self.timestamp)

    def latest(self):
        if not self.connected:
            return None
        return Snapshot(self.image, self.timestamp)

    def close(self):
        self.connected = False
        self.closed += 1


class Source:
    def __init__(self):
        self.wrist = None
        self.base = None
        self.roi = None
        self.cleared_wrist = 0
        self.cleared_base = 0

    def update_stream(self, index, image, timestamp):
        if index == 0:
            self.base = (image, timestamp)
        elif index == 1:
            self.wrist = (image, timestamp)
        else:
            self.roi = image

    def clear_streams(self):
        self.base = self.wrist = self.roi = None


def _service(*, fail_base=False):
    wrist_image = np.zeros((4, 6, 3), dtype=np.uint8)
    base_image = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    wrist = Camera(wrist_image)
    base = Camera(base_image, fail=fail_base)
    source = Source()
    service = CameraPollingService(
        cameras={"wrist": wrist, "base": base},
        streams=(CameraStreamConfig("Base", "base"), CameraStreamConfig("Wrist", "wrist"),
                 CameraStreamConfig("ROI", "base", "roi", (0.25, 0.25, 0.75, 0.75))),
        sample_source=source,
        poll_hz=50.0,
    )
    return service, wrist, base, source


def test_camera_service_constructor_does_not_connect() -> None:
    service, wrist, base, source = _service()

    assert not service.running
    assert not wrist.connected
    assert not base.connected
    assert source.wrist is None
    assert source.base is None


def test_explicit_start_connects_both_and_publishes_roi() -> None:
    service, wrist, base, source = _service()

    snapshot = service.start()

    assert set(snapshot.connected_serials) == {"wrist", "base"}
    assert source.wrist is not None
    assert source.base is not None
    assert source.roi.shape[0] > 0
    assert source.roi.shape[1] > 0
    service.stop()


def test_failed_second_camera_rolls_back_first_camera() -> None:
    service, wrist, base, source = _service(fail_base=True)

    with pytest.raises(RuntimeError, match="camera connect failed"):
        service.start()

    assert not wrist.connected
    assert not base.connected
    assert wrist.closed >= 1
    assert base.closed >= 1
    assert source.wrist is None
    assert source.base is None


def test_stop_closes_both_and_clears_sample_source() -> None:
    service, wrist, base, source = _service()
    service.start()

    service.stop()
    service.stop()

    assert not service.running
    assert not wrist.connected
    assert not base.connected
    assert source.wrist is None
    assert source.base is None


def test_camera_worker_surfaces_device_error() -> None:
    service, wrist, base, source = _service()
    service.start()

    base.error = "base stream failed"
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not service.error:
        time.sleep(0.01)

    assert "base stream failed" in service.error
    assert source.base is source.wrist is source.roi is None
    service.stop()


def test_camera_worker_invalidates_cached_images_on_disconnect():
    service, wrist, base, source = _service()
    service.start()
    try:
        base.connected = False
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not service.error:
            time.sleep(0.01)
        assert 'base' in service.error
        assert source.base is source.wrist is source.roi is None
    finally:
        service.stop()


def test_three_physical_cameras_publish_distinct_images_and_close():
    cameras = {str(i): Camera(np.full((6, 8, 3), i * 70, dtype=np.uint8)) for i in range(3)}
    streams = tuple(CameraStreamConfig(f"Camera {i}", str(i)) for i in range(3))
    source = Source()
    service = CameraPollingService(cameras=cameras, streams=streams, sample_source=source)
    try:
        service.start()
        assert len(service.snapshot().connected_serials) == 3
        assert source.base[0][0, 0, 0] == 0
        assert source.wrist[0][0, 0, 0] == 70
        assert source.roi[0, 0, 0] == 140
        assert all(camera.connect_calls == 1 for camera in cameras.values())
    finally:
        service.stop()
    assert all(not camera.connected for camera in cameras.values())
    assert source.roi is None


def test_one_camera_can_supply_full_frame_and_two_different_rois():
    image = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)
    camera = Camera(image)
    source = Source()
    streams = (
        CameraStreamConfig("Full", "a"),
        CameraStreamConfig("Left", "a", "roi", (0, 0, 0.5, 1)),
        CameraStreamConfig("Right", "a", "roi", (0.5, 0, 1, 1)),
    )
    service = CameraPollingService(cameras={"a": camera}, streams=streams, sample_source=source)
    try:
        service.start()
        assert camera.connect_calls == 1
        np.testing.assert_array_equal(source.base[0], image)
        np.testing.assert_array_equal(source.wrist[0], image[:, :4])
        np.testing.assert_array_equal(source.roi, image[:, 4:])
    finally:
        service.stop()


def test_failed_third_camera_closes_all_streams():
    cameras = {str(i): Camera(np.zeros((4, 6, 3), dtype=np.uint8), fail=i == 2) for i in range(3)}
    source = Source()
    service = CameraPollingService(
        cameras=cameras, streams=tuple(CameraStreamConfig(str(i), str(i)) for i in range(3)),
        sample_source=source,
    )
    with pytest.raises(RuntimeError, match="camera connect failed"):
        service.start()
    assert all(not camera.connected for camera in cameras.values())
    assert source.base is source.wrist is source.roi is None


def test_camera_stop_preserves_streams_until_bridge_has_exited():
    import threading

    service, wrist, base, source = _service()
    service.start()
    entered, release = threading.Event(), threading.Event()
    latest = base.latest

    def blocked_latest():
        entered.set()
        release.wait(5)
        return latest()

    base.latest = blocked_latest
    try:
        assert entered.wait(1)
        with pytest.raises(ExceptionGroup, match="Camera shutdown incomplete"):
            service.stop()
        assert wrist.connected and base.connected
        assert source.base is not None
    finally:
        release.set()
        service.stop()
    assert not wrist.connected and not base.connected
