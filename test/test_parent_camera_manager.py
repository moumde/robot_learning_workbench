"""Parent camera ownership and timestamp integrity without physical devices."""

from types import SimpleNamespace

import numpy as np
import pytest


class SampledCamera:
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.error = ""
        self.connect_count = 0
        self.close_count = 0
        self.fail_connect = False
        self.fail_close = False
        self.publish(10.0, 7)

    def publish(self, timestamp, value):
        self.sample = SimpleNamespace(
            timestamp=timestamp, serial=self.config.serial,
            image_rgb=np.full((self.config.height, self.config.width, 3), value, np.uint8),
            width=self.config.width, height=self.config.height,
        )

    def connect(self, timeout=5):
        self.connect_count += 1
        self.connected = True
        if self.fail_connect:
            raise OSError("camera startup failed after opening")
        return self.latest()

    def latest(self):
        sample = self.sample
        return SimpleNamespace(**{**vars(sample), "image_rgb": sample.image_rgb.copy()})

    def close(self):
        self.close_count += 1
        if self.fail_close:
            raise OSError("camera close failed")
        self.connected = False


def camera_group(serials=("BASE", "LEFT", "RIGHT")):
    from teleop.gello_cr.hardware.cameras import SharedCameraGroup

    devices = []

    def constructor(config):
        device = SampledCamera(config)
        devices.append(device)
        return device

    streams = tuple(SimpleNamespace(serial=s) for s in serials)
    group = SharedCameraGroup(
        streams,
        config={"camera_width": 4, "camera_height": 2, "camera_fps": 30,
                "image_size": [3, 3]},
        device_constructor=constructor,
    )
    return group, devices


def test_serial_views_use_one_parent_interface_and_retain_real_sample_times():
    from vendor.camera.d435.camera_interface import CR3O6CameraInterface

    group, devices = camera_group()
    assert isinstance(group.interface, CR3O6CameraInterface)
    assert not group.interface.connected
    base, left, right = group.views.values()
    try:
        base.connect(timeout=0.2)
        left.connect(timeout=0.2)
        right.connect(timeout=0.2)
        assert group.interface.connected
        assert [d.connect_count for d in devices] == [1, 1, 1]
        assert base.latest().timestamp == 10.0
        assert base.latest().timestamp == 10.0
        devices[0].publish(12.5, 17)
        sample = base.latest()
        assert sample.timestamp == 12.5
        assert sample.serial == "BASE"
        assert np.all(sample.image_rgb == 17)
        raw = group.interface.read_raw()
        processed = group.interface.read()
        assert tuple(raw) == ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")
        assert raw["base_0_rgb"].shape == (2, 4, 3)
        assert processed["base_0_rgb"].shape == (3, 3, 3)
        base.close()
        assert group.interface.connected  # Other views still own the group.
        assert not base.connected
        left.close()
        right.close()
        assert not group.interface.connected
        assert [d.close_count for d in devices] == [1, 1, 1]
    finally:
        group.close()


def test_cached_frames_do_not_reconnect_after_link_loss():
    group, devices = camera_group()
    base = group.views["BASE"]
    try:
        base.connect()
        devices[0].connected = False
        devices[0].error = "physical camera lost"
        assert not base.connected
        assert "physical camera lost" in base.error
        assert base.latest() is None
        assert devices[0].connect_count == 1
        devices[0].connected = True
        devices[0].error = ""
        assert not base.connected  # Restored signals alone never restart the group.
        base.close()
        devices[0].error = ""
        base.connect()
        assert base.connected
        assert devices[0].connect_count == 2
    finally:
        group.close()


def test_partial_connect_cleans_all_opened_devices_including_failed_one():
    group, devices = camera_group()
    devices[1].fail_connect = True
    with pytest.raises(RuntimeError, match="startup failed"):
        group.views["BASE"].connect()
    assert not any(d.connected for d in devices)
    assert devices[0].close_count >= 1
    assert devices[1].close_count >= 1
    assert group.views["BASE"].latest() is None
    devices[1].fail_connect = False
    try:
        group.views["BASE"].connect()
        assert group.interface.connected
    finally:
        group.close()


def test_close_failure_is_reported_and_all_devices_are_attempted_then_retryable():
    group, devices = camera_group()
    group.views["BASE"].connect()
    devices[1].fail_close = True
    with pytest.raises(ExceptionGroup, match="shutdown"):
        group.close()
    assert not devices[0].connected and not devices[2].connected
    assert devices[1].connected
    devices[1].fail_close = False
    group.close()
    assert not any(d.connected for d in devices)


def test_duplicate_stream_slots_share_a_single_physical_camera():
    group, devices = camera_group(("BASE", "LEFT", "BASE"))
    assert len(devices) == 2
    try:
        for view in group.views.values():
            view.connect()
        assert [d.connect_count for d in devices] == [1, 1]
        assert group.interface.sample("base_0_rgb").timestamp == 10.0
        assert group.interface.sample("right_wrist_0_rgb").timestamp == 10.0
    finally:
        group.close()
    assert [d.close_count for d in devices] == [1, 1]


def test_failed_start_cleanup_can_be_retried_through_an_unowned_view():
    group, devices = camera_group()
    devices[1].fail_connect = True
    devices[1].fail_close = True
    with pytest.raises(RuntimeError, match="startup failed"):
        group.views["BASE"].connect()
    assert devices[1].connected
    devices[1].fail_close = False
    group.views["BASE"].close()
    assert not any(d.connected for d in devices)


@pytest.mark.parametrize("backend", ["new", "old"])
def test_parent_policy_read_and_read_raw_keep_default_backend_semantics(backend):
    from vendor.camera.d435.camera_interface import CAMERA_NAMES, CR3O6CameraInterface

    class BackendCamera:
        def __init__(self, config):
            self.config = config
            self.is_connected = False

        def connect(self):
            self.is_connected = True

        def disconnect(self):
            self.is_connected = False

        def async_read(self, **kwargs):
            assert kwargs == ({"timeout_ms": 100} if backend == "new" else {})
            return np.full((2, 4, 3), 123, dtype=np.uint8)

    interface = CR3O6CameraInterface(
        camera_serials=dict(zip(CAMERA_NAMES, ("101", "102", "103"), strict=True)),
        width=4, height=2, fps=30, output_width=2, output_height=2,
        async_read=True, read_timeout_ms=100,
        camera_backend=(backend, BackendCamera, lambda **kwargs: kwargs),
    )
    try:
        interface.connect()
        assert all(i.shape == (2, 4, 3) for i in interface.read_raw().values())
        images = interface.read()
        assert all(i.shape == (2, 2, 3) for i in images.values())
        np.testing.assert_array_equal(images["base_0_rgb"][0], np.full((2, 3), 123, np.uint8))
        np.testing.assert_array_equal(images["base_0_rgb"][1], np.zeros((2, 3), np.uint8))
        with pytest.raises(RuntimeError, match="no timestamped"):
            interface.sample("base_0_rgb")
    finally:
        interface.disconnect()
    assert not interface.connected


def test_status_snapshot_does_not_wait_for_device_startup():
    import threading
    import time

    from teleop.gello_cr.bootstrap.camera_service import CameraPollingService

    group, devices = camera_group()
    entered, release = threading.Event(), threading.Event()
    original_connect = devices[0].connect
    def slow_connect(timeout=5):
        entered.set()
        release.wait(0.5)
        return original_connect(timeout)
    devices[0].connect = slow_connect
    source = SimpleNamespace(clear_streams=lambda: None, update_stream=lambda *args: None)
    streams = tuple(SimpleNamespace(serial=serial, mode="camera") for serial in group.views)
    service = CameraPollingService(cameras=group.views, streams=streams, sample_source=source)
    errors = []
    def start():
        try:
            service.start()
        except Exception as error:
            errors.append(error)
    worker = threading.Thread(target=start)
    worker.start()
    try:
        assert entered.wait(1)
        begun = time.monotonic()
        snapshot = service.snapshot()
        assert time.monotonic() - begun < 0.1
        assert not snapshot.running
    finally:
        release.set()
        worker.join(2)
        service.close()
    assert not worker.is_alive()
    assert not errors
