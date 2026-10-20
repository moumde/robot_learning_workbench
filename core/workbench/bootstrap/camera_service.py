"""Poll each selected physical camera once and publish the configured image slots."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Any

from core.hardware.camera_streams import CameraStreamConfig
from core.workbench.recording.image_processing import crop_normalized_roi


@dataclass(frozen=True, slots=True)
class CameraServiceSnapshot:
    running: bool
    connected_serials: tuple[str, ...]
    error: str


class CameraPollingService:
    """Shared physical streams feed both preview and recording; construction is offline."""

    def __init__(
        self,
        *,
        cameras: dict[str, Any],
        streams: tuple[CameraStreamConfig, ...],
        sample_source: Any,
        poll_hz: float = 30.0,
    ) -> None:
        rate = float(poll_hz)
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("poll_hz must be positive and finite")
        self._cameras = cameras
        self._streams = streams
        self._sample_source = sample_source
        self._period_s = 1.0 / rate
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._error = ""
        self._connected_serials: tuple[str, ...] = ()

    @property
    def running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive() and not self.error)

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def snapshot(self) -> CameraServiceSnapshot:
        # UI readers observe published state only. Connecting a device group
        # may hold its lifecycle lock while waiting for the first physical frame.
        with self._lock:
            return CameraServiceSnapshot(
                running=self.running,
                connected_serials=self._connected_serials,
                error=self._error,
            )

    def _publish(self, serial, frame) -> None:
        for index, stream in enumerate(self._streams):
            if stream.serial != serial:
                continue
            image = frame.image_rgb
            if stream.mode == "roi":
                image = crop_normalized_roi(image, stream.roi_norm).image_rgb
            self._sample_source.update_stream(index, image, frame.timestamp)

    def start(self, timeout: float = 5.0) -> CameraServiceSnapshot:
        if self.running:
            return self.snapshot()
        if not math.isfinite(float(timeout)) or float(timeout) <= 0:
            raise ValueError("camera timeout must be positive and finite")
        self.stop()
        self._stop.clear()
        with self._lock:
            self._error = ""
        try:
            for serial, camera in self._cameras.items():
                self._publish(serial, camera.connect(timeout=float(timeout)))
        except Exception as exc:
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
            try:
                self.stop()
            except Exception as cleanup_error:
                raise ExceptionGroup(
                    "Camera startup and cleanup failed", [exc, cleanup_error]
                ) from exc
            raise
        with self._lock:
            self._connected_serials = tuple(self._cameras)
        self._thread = threading.Thread(target=self._run, name="RecordingCameraBridge", daemon=True)
        self._thread.start()
        return self.snapshot()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        errors = []
        if thread is not None and thread.is_alive():
            raise ExceptionGroup(
                "Camera shutdown incomplete", [TimeoutError("Camera bridge thread did not stop")]
            )
        self._thread = None
        with self._lock:
            self._connected_serials = ()
        for serial, camera in self._cameras.items():
            try:
                camera.close()
            except Exception as exc:
                exc.add_note(f"camera: {serial}")
                errors.append(exc)
        self._sample_source.clear_streams()
        if errors:
            raise ExceptionGroup("Camera shutdown incomplete", errors)

    close = stop

    def _run(self) -> None:
        last = {}
        try:
            while not self._stop.is_set():
                for serial, camera in self._cameras.items():
                    if camera.error:
                        raise RuntimeError(f"{serial}: {camera.error}")
                    if not camera.connected:
                        raise RuntimeError(f"{serial}: camera disconnected")
                    frame = camera.latest()
                    if frame is not None and frame.timestamp != last.get(serial):
                        self._publish(serial, frame)
                        last[serial] = frame.timestamp
                self._stop.wait(self._period_s)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            invalidate = getattr(self._sample_source, "invalidate_streams", None)
            if callable(invalidate):
                invalidate(message)
            else:
                self._sample_source.clear_streams()
            with self._lock:
                self._error = message
                self._connected_serials = ()
            self._stop.set()
