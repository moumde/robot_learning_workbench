"""Thread-owned Intel RealSense RGB camera adapter.

The parent camera manager uses this backend for collection without requiring
a LeRobot installation. Each instance owns one physical RGB pipeline.

Important semantics:
- the configured RealSense stream remains 640x480 BGR8 @ 30 FPS by default;
- received frames are converted to contiguous RGB arrays;
- timestamps are local ``time.monotonic()`` receive times, matching the current
  dataset freshness/skew checks;
- ROI cropping is intentionally *not* part of this driver. The base ROI is a
  pure image-processing/data-contract concern, not a third physical camera.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from teleop.gello_cr.core.contracts import CameraSnapshot


def discover_realsense_cameras() -> list[dict[str, str]]:
    """Enumerate available RGB devices without starting any camera pipeline."""
    import pyrealsense2 as rs

    return [
        {
            "serial": device.get_info(rs.camera_info.serial_number),
            "name": device.get_info(rs.camera_info.name),
        }
        for device in rs.context().query_devices()
    ]


@dataclass(frozen=True, slots=True)
class RealSenseRgbConfig:
    serial: str
    width: int = 640
    height: int = 480
    fps: int = 30
    poll_sleep_s: float = 0.002

    def __post_init__(self) -> None:
        if not self.serial.strip():
            raise ValueError("RealSense serial cannot be empty")
        if int(self.width) <= 0 or int(self.height) <= 0:
            raise ValueError("RealSense width/height must be positive")
        if int(self.fps) <= 0:
            raise ValueError("RealSense fps must be positive")
        if not math.isfinite(float(self.poll_sleep_s)) or float(self.poll_sleep_s) <= 0:
            raise ValueError("RealSense poll_sleep_s must be positive and finite")


class RealSenseRgbDevice:
    """Own one RealSense RGB pipeline and its non-blocking polling thread."""

    def __init__(
        self,
        config: RealSenseRgbConfig,
        *,
        rs_module: Any | None = None,
    ) -> None:
        self.config = config
        self._rs = rs_module
        self._pipeline: Any | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self._latest: CameraSnapshot | None = None
        self._error = ""

    @property
    def connected(self) -> bool:
        thread = self._thread
        return (
            thread is not None
            and thread.is_alive()
            and self.latest() is not None
            and not self.error
        )

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def _load_rs(self) -> Any:
        if self._rs is not None:
            return self._rs
        try:
            import pyrealsense2 as rs
        except ImportError as exc:
            raise RuntimeError(
                "pyrealsense2 is not installed; RealSense RGB is unavailable"
            ) from exc
        self._rs = rs
        return rs

    def connect(self, timeout: float = 5.0) -> CameraSnapshot:
        if not math.isfinite(float(timeout)) or float(timeout) <= 0:
            raise ValueError("RealSense connect timeout must be positive")

        if self.connected:
            snapshot = self.latest()
            if snapshot is None:
                raise RuntimeError("RealSense connected without a frame")
            return snapshot

        self.close()

        rs = self._load_rs()
        pipeline = rs.pipeline()
        stream_config = rs.config()
        stream_config.enable_device(str(self.config.serial))
        stream_config.enable_stream(
            rs.stream.color,
            int(self.config.width),
            int(self.config.height),
            rs.format.bgr8,
            int(self.config.fps),
        )

        self._stop.clear()
        self._ready.clear()
        with self._lock:
            self._latest = None
            self._error = ""

        try:
            pipeline.start(stream_config)
        except Exception as exc:
            try:
                pipeline.stop()
            except Exception as cleanup_error:
                exc.add_note(f"Camera cleanup after failed start: {cleanup_error}")
            raise

        self._pipeline = pipeline
        self._thread = threading.Thread(
            target=self._run,
            name=f"RealSense-RGB-{self.config.serial}",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(float(timeout)):
            self.close()
            raise TimeoutError(
                f"RealSense {self.config.serial} did not produce an RGB frame "
                f"within {float(timeout):.2f}s"
            )

        if self.error:
            error = self.error
            self.close()
            raise RuntimeError(error)

        snapshot = self.latest()
        if snapshot is None:
            self.close()
            raise RuntimeError(f"RealSense {self.config.serial} produced no valid RGB frame")
        return snapshot

    def latest(self) -> CameraSnapshot | None:
        with self._lock:
            snapshot = self._latest
            if snapshot is None:
                return None
            image = np.ascontiguousarray(snapshot.image_rgb.copy())
            return CameraSnapshot(
                timestamp=float(snapshot.timestamp),
                serial=str(snapshot.serial),
                image_rgb=image,
                width=int(snapshot.width),
                height=int(snapshot.height),
            )

    def close(self) -> None:
        self._stop.set()

        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

        pipeline = self._pipeline
        errors = []
        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception as exc:
                errors.append(exc)
            else:
                self._pipeline = None
        if thread is not None and thread.is_alive():
            errors.append(TimeoutError("RealSense polling thread did not exit"))
        else:
            self._thread = None
        with self._lock:
            self._latest = None
        if errors:
            raise ExceptionGroup("RealSense shutdown incomplete", errors)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._error = message
        self._ready.set()

    def _run(self) -> None:
        pipeline = self._pipeline
        if pipeline is None:
            self._set_error("RealSense worker started without a pipeline")
            return

        try:
            while not self._stop.is_set():
                frames = pipeline.poll_for_frames()
                if not frames:
                    time.sleep(float(self.config.poll_sleep_s))
                    continue

                color_frame = frames.get_color_frame()
                if not color_frame:
                    time.sleep(float(self.config.poll_sleep_s))
                    continue

                received_at = time.monotonic()
                bgr = np.asanyarray(color_frame.get_data())

                expected_shape = (
                    int(self.config.height),
                    int(self.config.width),
                    3,
                )
                if bgr.shape != expected_shape:
                    raise RuntimeError(
                        f"RealSense RGB shape mismatch: expected {expected_shape}, got {bgr.shape}"
                    )

                if bgr.dtype != np.uint8:
                    raise RuntimeError(
                        f"RealSense RGB dtype mismatch: expected uint8, got {bgr.dtype}"
                    )

                rgb = np.ascontiguousarray(bgr[:, :, ::-1])
                snapshot = CameraSnapshot(
                    timestamp=received_at,
                    serial=str(self.config.serial),
                    image_rgb=rgb,
                    width=int(self.config.width),
                    height=int(self.config.height),
                )

                with self._lock:
                    self._latest = snapshot
                self._ready.set()

        except Exception as exc:
            self._set_error(
                f"RealSense {self.config.serial} RGB worker failed: {type(exc).__name__}: {exc}"
            )
