"""One parent camera owner, exposed as serial views for preview/recording."""

from __future__ import annotations

import math
import threading
from functools import partial

from vendor.camera.d435.camera_interface import CAMERA_NAMES, CR3O6CameraInterface

from .realsense import RealSenseRgbConfig, RealSenseRgbDevice


class NativeRgbCamera:
    """Adapt the shared timestamped RGB backend to the parent camera interface."""

    def __init__(self, config, *, device_constructor=RealSenseRgbDevice):
        self.device = device_constructor(config)

    @property
    def is_connected(self):
        return bool(self.device.connected and not self.error)

    @property
    def error(self):
        return str(self.device.error or "")

    def connect(self, timeout=5.0):
        return self.device.connect(timeout=timeout)

    def disconnect(self):
        self.device.close()

    def latest_sample(self):
        return self.device.latest()

    def read(self):
        if not self.is_connected:
            raise RuntimeError(self.error or "Camera is disconnected")
        sample = self.latest_sample()
        if sample is None:
            raise RuntimeError("Camera has no sampled RGB frame")
        return sample.image_rgb

    def async_read(self, timeout_ms=None):
        # The backend already owns the sole physical acquisition worker.
        del timeout_ms
        return self.read()


class SharedCameraGroup:
    """Connect one parent-owned set, retaining explicit ownership per serial view.

    Construction never opens devices. A failed group cannot reconnect through
    latest(): callers close their views and explicitly connect/start again.
    """

    def __init__(self, streams, *, config, device_constructor=RealSenseRgbDevice):
        streams = tuple(streams)
        if len(streams) != len(CAMERA_NAMES):
            raise ValueError("The camera group requires exactly three logical image slots")
        self._lock = threading.RLock()
        self._owners = set()
        self._needs_close = False
        self._error = ""
        self._names = {}
        for name, stream in zip(CAMERA_NAMES, streams, strict=True):
            self._names.setdefault(str(stream.serial), name)
        height, width = config.get("image_size", (224, 224))
        self.interface = CR3O6CameraInterface(
            camera_serials={name: str(stream.serial) for name, stream in zip(
                CAMERA_NAMES, streams, strict=True
            )},
            width=int(config.get("camera_width", 640)),
            height=int(config.get("camera_height", 480)),
            fps=int(config.get("camera_fps", 30)),
            output_width=int(width), output_height=int(height),
            async_read=True, read_timeout_ms=5000,
            camera_backend=(
                "native", partial(NativeRgbCamera, device_constructor=device_constructor),
                RealSenseRgbConfig,
            ),
        )
        self.views = {serial: CameraSerialView(self, serial) for serial in self._names}

    def _connect(self, serial, timeout):
        if not math.isfinite(float(timeout)) or timeout <= 0:
            raise ValueError("Camera connect timeout must be positive and finite")
        with self._lock:
            if not self._owners:
                if self._needs_close:
                    self.interface.disconnect()
                    self._needs_close = False
                self._error = ""
                self._needs_close = True
                try:
                    self.interface.connect(timeout=timeout)
                except Exception as exc:
                    self._error = str(exc)
                    raise
            elif self._error or not self.interface.connected:
                raise RuntimeError(self._error or "Close the camera group before reconnecting")
            try:
                sample = self.interface.sample(self._names[serial])
            except Exception:
                if not self._owners:
                    self.interface.disconnect()
                    self._needs_close = False
                raise
            self._owners.add(serial)
            return sample

    def _connected(self, serial):
        with self._lock:
            if serial not in self._owners or self._error:
                return False
            if not self.interface.connected:
                self._error = self.interface.error or "Camera group disconnected; reconnect explicitly"
                return False
            return True

    def _error_for(self, serial):
        del serial
        with self._lock:
            error = self.interface.error
            if error:
                self._error = error
            return self._error

    def _latest(self, serial):
        with self._lock:
            if not self._connected(serial):
                return None
            try:
                return self.interface.sample(self._names[serial])
            except Exception as exc:
                self._error = str(exc)
                return None

    def _release(self, serial):
        with self._lock:
            if serial not in self._owners:
                if not self._owners and self._needs_close:
                    self.interface.disconnect()
                    self._needs_close = False
                return
            if self._owners == {serial}:
                # Retain ownership after failed close so callers can retry it.
                self.interface.disconnect()
                self._needs_close = False
            self._owners.remove(serial)

    def close(self):
        with self._lock:
            self.interface.disconnect()
            self._needs_close = False
            self._owners.clear()


class CameraSerialView:
    """Cached view onto one serial of the parent group; owns no worker/pipeline."""

    def __init__(self, group, serial):
        self.group, self.serial = group, serial
        self.config = RealSenseRgbConfig(
            serial=serial, width=group.interface.width, height=group.interface.height,
            fps=group.interface.fps,
        )

    @property
    def connected(self):
        return self.group._connected(self.serial)

    @property
    def error(self):
        return self.group._error_for(self.serial)

    def connect(self, timeout=5.0):
        return self.group._connect(self.serial, timeout)

    def latest(self):
        return self.group._latest(self.serial)

    def close(self):
        self.group._release(self.serial)
