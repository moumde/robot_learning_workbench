"""OpenPI-facing interface for the three CR3/O6 RealSense cameras.

The policy uses three logical image names. Their physical D435 serial numbers
are maintained in ``config/hardware/cr3_o6.toml`` rather than in this adapter:

* ``base_0_rgb``
* ``left_wrist_0_rgb``
* ``right_wrist_0_rgb``

Frames are captured as RGB ``uint8`` arrays and resized with padding to the
configured output size (224x224 by default), which is the image resolution
expected by OpenPI.  The class reuses
LeRobot's RealSense implementation and supports both the newer
``lerobot.cameras.realsense`` API and the older
``lerobot.common.robot_devices.cameras`` API.  LeRobot is imported lazily so
this module can be imported by a script launched through the repository's
``scripts/run_openpi.sh`` wrapper without requiring camera hardware at import
time.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from typing import Any

import cv2
import numpy as np


LOGGER = logging.getLogger(__name__)

CAMERA_NAMES = (
    "base_0_rgb",
    "left_wrist_0_rgb",
    "right_wrist_0_rgb",
)


class CameraInterfaceError(RuntimeError):
    """Base error raised by the CR3/O6 camera interface."""


class CameraDependencyError(CameraInterfaceError):
    """Raised when a compatible LeRobot/RealSense backend is unavailable."""


def _load_lerobot_backend() -> tuple[str, type, type]:
    """Load the installed LeRobot RealSense API without importing it at module load.

    OpenPI currently pins a LeRobot revision that exposes the legacy API, while
    newer LeRobot releases expose ``lerobot.cameras.realsense``.  Keep the
    fallback local to construction so importing this adapter remains cheap and
    does not require ``pyrealsense2`` until a camera is actually used.
    """

    try:
        from lerobot.cameras.realsense import RealSenseCamera, RealSenseCameraConfig

        return "new", RealSenseCamera, RealSenseCameraConfig
    except ImportError as new_error:
        try:
            from lerobot.common.robot_devices.cameras.configs import (
                IntelRealSenseCameraConfig,
            )
            from lerobot.common.robot_devices.cameras.intelrealsense import (
                IntelRealSenseCamera,
            )

            return "old", IntelRealSenseCamera, IntelRealSenseCameraConfig
        except ImportError as old_error:
            raise CameraDependencyError(
                "Could not import a LeRobot RealSense backend. Install LeRobot's camera "
                "dependencies and pyrealsense2, or add the LeRobot source tree to PYTHONPATH. "
                f"New backend error: {new_error}; old backend error: {old_error}"
            ) from old_error


class CR3O6CameraInterface:
    """Capture the three named D435 RGB streams for CR3/O6 OpenPI inference.

    When parameters are omitted, the default configuration is read from
    ``config/hardware/cr3_o6.toml``.  The repository baseline uses 640x480 at 30 FPS
    from each camera, converted to 224x224 RGB images for the policy.
    ``async_read=True`` uses LeRobot's background frame buffers so a camera
    read does not block the robot-control loop on every frame.
    """

    def __init__(
        self,
        *,
        camera_serials: Mapping[str, str | int] | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        output_width: int | None = None,
        output_height: int | None = None,
        async_read: bool | None = None,
        read_timeout_ms: int | None = None,
        camera_backend: tuple[str, type, type] | None = None,
    ) -> None:
        if any(
            value is None
            for value in (
                camera_serials,
                width,
                height,
                fps,
                output_width,
                output_height,
                async_read,
                read_timeout_ms,
            )
        ):
            from config.hardware import load_hardware_config

            defaults = load_hardware_config().d435
            camera_serials = (
                defaults.camera_serials if camera_serials is None else camera_serials
            )
            width = defaults.width if width is None else width
            height = defaults.height if height is None else height
            fps = defaults.fps if fps is None else fps
            output_width = defaults.output_width if output_width is None else output_width
            output_height = (
                defaults.output_height if output_height is None else output_height
            )
            async_read = defaults.async_read if async_read is None else async_read
            read_timeout_ms = (
                defaults.read_timeout_ms
                if read_timeout_ms is None
                else read_timeout_ms
            )

        assert camera_serials is not None
        assert width is not None
        assert height is not None
        assert fps is not None
        assert output_width is not None
        assert output_height is not None
        assert async_read is not None
        assert read_timeout_ms is not None
        serials = dict(camera_serials)
        if set(serials) != set(CAMERA_NAMES):
            raise ValueError(
                f"camera_serials must contain exactly {CAMERA_NAMES}, got {tuple(serials)}"
            )
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("width, height, and fps must be positive")
        if output_width <= 0 or output_height <= 0:
            raise ValueError("output_width and output_height must be positive")
        if read_timeout_ms <= 0:
            raise ValueError("read_timeout_ms must be positive")

        self.camera_serials = {name: str(serials[name]) for name in CAMERA_NAMES}
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.output_width = int(output_width)
        self.output_height = int(output_height)
        self.async_read = bool(async_read)
        self.read_timeout_ms = int(read_timeout_ms)
        self._lock = threading.RLock()

        if camera_backend is None:
            backend_name, camera_class, config_class = _load_lerobot_backend()
        else:
            backend_name, camera_class, config_class = camera_backend
        if backend_name not in {"new", "old"}:
            raise ValueError(f"Unsupported camera backend name: {backend_name!r}")
        self.backend_name = backend_name
        self._camera_class = camera_class
        self._config_class = config_class
        self._cameras = {
            name: self._make_camera(name, self.camera_serials[name])
            for name in CAMERA_NAMES
        }

    @classmethod
    def from_config(cls, config_path: str | None = None, **overrides: Any):
        """Create the camera interface from a hardware profile.

        The import is lazy so callers can still import this adapter without
        loading the configuration or constructing any camera backend.
        """

        from config.hardware import load_hardware_config

        hardware = load_hardware_config(config_path)
        kwargs = hardware.d435.interface_kwargs()
        kwargs.update(overrides)
        return cls(**kwargs)

    def _make_camera(self, name: str, serial_number: str) -> Any:
        del name
        if self.backend_name == "new":
            config = self._config_class(
                serial_number_or_name=serial_number,
                fps=self.fps,
                width=self.width,
                height=self.height,
                use_rgb=True,
                use_depth=False,
            )
        else:
            config = self._config_class(
                serial_number=int(serial_number),
                fps=self.fps,
                width=self.width,
                height=self.height,
                color_mode="rgb",
                use_depth=False,
            )
        return self._camera_class(config)

    @property
    def cameras(self) -> Mapping[str, Any]:
        """The underlying named LeRobot camera objects, exposed for diagnostics."""

        return self._cameras

    @property
    def connected(self) -> bool:
        """Whether all three camera pipelines are connected."""

        return all(
            bool(getattr(camera, "is_connected", False))
            for camera in self._cameras.values()
        )

    def connect(self) -> "CR3O6CameraInterface":
        """Connect and warm up all cameras, cleaning up if any camera fails."""

        with self._lock:
            if self.connected:
                return self

            connected_names: list[str] = []
            try:
                for name, camera in self._cameras.items():
                    LOGGER.info(
                        "Connecting camera %s (serial=%s, %dx%d@%d)",
                        name,
                        self.camera_serials[name],
                        self.width,
                        self.height,
                        self.fps,
                    )
                    camera.connect()
                    connected_names.append(name)
            except BaseException as exc:
                for name in reversed(connected_names):
                    self._safe_disconnect(self._cameras[name], name)
                raise CameraInterfaceError(
                    f"Failed to connect camera {name!r} "
                    f"(serial={self.camera_serials[name]}): {type(exc).__name__}: {exc}"
                ) from exc

        LOGGER.info("All CR3/O6 cameras connected")
        return self

    @staticmethod
    def _safe_disconnect(camera: Any, name: str) -> None:
        try:
            if bool(getattr(camera, "is_connected", False)):
                camera.disconnect()
        except Exception:
            LOGGER.exception("Failed to disconnect camera %s", name)

    def _async_read_camera(self, camera: Any) -> Any:
        """Read asynchronously across both supported LeRobot API versions."""

        if self.backend_name == "new":
            return camera.async_read(timeout_ms=self.read_timeout_ms)
        # The older IntelRealSenseCamera starts its own reader thread and
        # exposes async_read() without a timeout_ms argument.
        return camera.async_read()

    def disconnect(self) -> None:
        """Disconnect all camera pipelines."""

        with self._lock:
            for name, camera in reversed(tuple(self._cameras.items())):
                self._safe_disconnect(camera, name)

    close = disconnect

    def __enter__(self) -> "CR3O6CameraInterface":
        return self.connect()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.disconnect()

    def _read_camera(self, name: str, camera: Any) -> np.ndarray:
        if self.async_read:
            frame = self._async_read_camera(camera)
        else:
            frame = camera.read()

        # A depth-enabled backend may return (color, depth).  Depth is not
        # requested here, but accepting this shape makes the adapter robust.
        if isinstance(frame, tuple):
            frame = frame[0]
        image = np.asarray(frame)
        if image.ndim != 3 or image.shape[-1] != 3:
            raise CameraInterfaceError(
                f"Camera {name!r} returned {image.shape}; expected HxWx3 RGB image"
            )
        if image.dtype != np.uint8:
            image = np.clip(image, 0, 255).astype(np.uint8)
        return self._resize_with_pad(image)

    def _resize_with_pad(self, image: np.ndarray) -> np.ndarray:
        if image.shape[:2] == (self.output_height, self.output_width):
            return np.ascontiguousarray(image)

        image_height, image_width = image.shape[:2]
        ratio = max(image_width / self.output_width, image_height / self.output_height)
        resized_width = max(1, int(image_width / ratio))
        resized_height = max(1, int(image_height / ratio))
        interpolation = cv2.INTER_AREA if ratio >= 1.0 else cv2.INTER_LINEAR
        resized = cv2.resize(
            image, (resized_width, resized_height), interpolation=interpolation
        )

        output = np.zeros((self.output_height, self.output_width, 3), dtype=np.uint8)
        top = (self.output_height - resized_height) // 2
        left = (self.output_width - resized_width) // 2
        output[top : top + resized_height, left : left + resized_width] = resized
        return output

    def read(self) -> dict[str, np.ndarray]:
        """Read one OpenPI-ready RGB frame from each named camera."""

        with self._lock:
            if not self.connected:
                raise CameraInterfaceError(
                    "Cameras are not connected; call connect() first"
                )
            frames: dict[str, np.ndarray] = {}
            for name in CAMERA_NAMES:
                try:
                    frames[name] = self._read_camera(name, self._cameras[name])
                except Exception as exc:
                    raise CameraInterfaceError(
                        f"Failed to read camera {name!r} (serial={self.camera_serials[name]})"
                    ) from exc
            return frames

    get_observation = read

    def read_raw(self) -> dict[str, np.ndarray]:
        """Read frames without resizing, useful for diagnostics or recording."""

        with self._lock:
            if not self.connected:
                raise CameraInterfaceError(
                    "Cameras are not connected; call connect() first"
                )
            frames: dict[str, np.ndarray] = {}
            for name in CAMERA_NAMES:
                camera = self._cameras[name]
                frame = (
                    self._async_read_camera(camera)
                    if self.async_read
                    else camera.read()
                )
                if isinstance(frame, tuple):
                    frame = frame[0]
                image = np.asarray(frame)
                if image.ndim != 3 or image.shape[-1] != 3:
                    raise CameraInterfaceError(
                        f"Camera {name!r} returned invalid image shape {image.shape}"
                    )
                frames[name] = np.ascontiguousarray(
                    np.clip(image, 0, 255).astype(np.uint8, copy=False)
                )
            return frames


__all__ = [
    "CAMERA_NAMES",
    "CameraDependencyError",
    "CameraInterfaceError",
    "CR3O6CameraInterface",
]
