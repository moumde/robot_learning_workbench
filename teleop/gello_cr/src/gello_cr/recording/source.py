"""Canonical capture source and shared camera cache, independent of storage formats."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import numpy as np

from gello_cr.devices.camera_streams import CameraStreamConfig, camera_stream_metadata

from .frame import CaptureFrame
from .schema import IMAGE_KEYS
from .validation import RAW_FIELDS


class CaptureSource(Protocol):
    def capture(self) -> CaptureFrame: ...


def _immutable_image(image: Any) -> Any:
    if isinstance(image, np.ndarray):
        # Own immutable bytes, rather than a writable producer buffer or an array
        # whose WRITEABLE flag a snapshot consumer could turn back on.
        return np.frombuffer(image.tobytes(), dtype=image.dtype).reshape(image.shape)
    copier = getattr(image, "copy", None)
    return copier() if callable(copier) else image


class CR3O6CaptureSource:
    """One image cache supplies preview and canonical frames to any writer."""

    def __init__(
        self,
        robot_sample: Callable[[], Mapping[str, Any]],
        dataset_config: Mapping[str, Any],
        *,
        streams: tuple[CameraStreamConfig, ...] = (),
    ) -> None:
        self._robot_sample = robot_sample
        self._dataset_config = dataset_config
        self._streams = streams
        self._metadata = camera_stream_metadata(streams) if streams else []
        self._names = tuple(s.name for s in streams) if streams else ("基座", "腕部", "第三路")
        self._lock = threading.RLock()
        self._images = [None, None, None]
        self._timestamps = [0.0, 0.0, 0.0]
        self._fps = [0.0, 0.0, 0.0]
        self._stream_errors = ["", "", ""]

    def update_stream(self, index: int, image_rgb: Any, timestamp: float) -> None:
        image = _immutable_image(image_rgb)
        with self._lock:
            self._set_image_locked(index, image, timestamp)

    def _set_image_locked(self, index: int, image: Any, timestamp: float) -> None:
        previous = self._timestamps[index]
        if previous > 0 and timestamp > previous:
            current_fps = 1.0 / (timestamp - previous)
            self._fps[index] = (
                current_fps if not self._fps[index] else 0.8 * self._fps[index] + 0.2 * current_fps
            )
        self._images[index] = image
        self._timestamps[index] = float(timestamp)
        self._stream_errors[index] = ""
        if image is None:
            self._fps[index] = 0.0

    def clear_streams(self) -> None:
        with self._lock:
            self._images = [None, None, None]
            self._timestamps = [0.0, 0.0, 0.0]
            self._fps = [0.0, 0.0, 0.0]
            self._stream_errors = ["", "", ""]

    def invalidate_streams(self, error: str) -> None:
        """A stopped bridge can no longer supply any of its required streams."""
        with self._lock:
            self._images = [None, None, None]
            self._stream_errors = [str(error)] * 3

    def update_wrist(self, image_rgb: Any, timestamp: float) -> None:
        self.update_stream(1, image_rgb, timestamp)

    def update_base(self, image_rgb: Any, roi_rgb: Any, timestamp: float) -> None:
        # Compatibility with the original base RGB + base ROI producer.
        image, roi = _immutable_image(image_rgb), _immutable_image(roi_rgb)
        with self._lock:
            self._set_image_locked(0, image, timestamp)
            self._set_image_locked(2, roi, timestamp)

    def clear_wrist(self) -> None:
        self.update_stream(1, None, 0.0)

    def clear_base(self) -> None:
        self.update_base(None, None, 0.0)

    def preview_snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            statuses = tuple(
                "ERROR"
                if self._stream_errors[i]
                else "OFFLINE"
                if self._images[i] is None
                else "STALE"
                if not 0
                <= now - self._timestamps[i]
                <= float(self._dataset_config["camera_max_age_s"])
                else "OK"
                for i in range(3)
            )
            return {
                "streams": tuple(
                    {
                        "name": name,
                        "fps": self._fps[i] if statuses[i] == "OK" else 0.0,
                        "last_fps": self._fps[i],
                        "age_s": now - self._timestamps[i] if self._timestamps[i] else None,
                        "status": statuses[i],
                        "error": self._stream_errors[i],
                    }
                    for i, name in enumerate(self._names)
                ),
                "base_rgb": self._images[0],
                "wrist_rgb": self._images[1],
                "roi_rgb": self._images[2],
                "base_timestamp": self._timestamps[0],
                "wrist_timestamp": self._timestamps[1],
                "roi_timestamp": self._timestamps[2],
                "stream_names": tuple(s.name for s in self._streams)
                or ("Base RGB", "Wrist RGB", "Base ROI"),
                "stream_descriptions": tuple(s.description for s in self._streams),
            }

    def snapshot_ready(self) -> bool:
        return not self.readiness_error()

    def readiness_error(self) -> str:
        cfg = self._dataset_config
        max_age = float(cfg["camera_max_age_s"])
        max_skew = float(cfg["camera_max_skew_s"])
        now = time.monotonic()
        with self._lock:
            for index in (1, 0, 2):
                name = self._names[index]
                if self._stream_errors[index]:
                    return f"{name}相机连接丢失：{self._stream_errors[index]}"
                if self._images[index] is None:
                    return f"{name}尚无 RGB 画面，请启动相机"
                age = now - self._timestamps[index]
                if not 0 <= age <= max_age:
                    reason = "帧过期" if age > max_age else "帧时间异常"
                    return (
                        f"{name}相机{reason}（时龄 {age:.2f}s，阈值 {max_age:.2f}s）；"
                        "请停止后重新启动相机"
                    )
            skew = max(self._timestamps) - min(self._timestamps)
            if skew > max_skew:
                return (
                    f"相机画面不同步（相差 {skew:.2f}s，阈值 {max_skew:.2f}s）；"
                    "持续异常时请停止后重新启动相机"
                )
        return ""

    def capture(self) -> CaptureFrame:
        cfg = self._dataset_config
        sample = dict(self._robot_sample())
        with self._lock:
            images = tuple(self._images)
            timestamps = tuple(self._timestamps)
            errors = tuple(self._stream_errors)
        now = time.monotonic()
        max_age = float(cfg["camera_max_age_s"])
        for index in (1, 0, 2):
            if errors[index]:
                raise RuntimeError(f"{self._names[index]}相机连接丢失：{errors[index]}")
            if images[index] is None:
                raise RuntimeError(f"{self._names[index]}尚无 RGB 图像，请先启动相机")
            age = now - timestamps[index]
            if not 0 <= age <= max_age:
                reason = "帧过期" if age > max_age else "帧时间异常"
                raise RuntimeError(
                    f"{self._names[index]}相机{reason}（时龄 {age:.2f}s，阈值 {max_age:.2f}s）"
                )
        skew = max(timestamps) - min(timestamps)
        quality = sample.setdefault("quality", {})
        quality.update(
            camera_skew_s=skew, camera_skew_exceeded=float(skew > float(cfg["camera_max_skew_s"]))
        )
        for name, timestamp in zip(("base", "wrist", "roi"), timestamps, strict=True):
            age = now - timestamp
            quality.update(
                {
                    f"{name}_timestamp": timestamp,
                    f"{name}_age_s": age,
                    f"{name}_age_exceeded": float(not 0 <= age <= max_age),
                }
            )
        state, action = tuple(sample["observation_state"]), tuple(sample["action"])
        mode = sample.get("recording_mode", "tcp")
        raw = {
            key: tuple(sample[key]) if sample[key] is not None else None
            for key in RAW_FIELDS
            if key in sample
        }
        raw.setdefault("robot_joint_state", state[:6])
        raw.setdefault("hand_state", state[-6:])
        raw.setdefault("hand_command", action[-6:])
        if mode == "joint":
            raw.setdefault("robot_joint_command", action[:6])
        else:
            raw.setdefault("robot_tcp_state", state[6:12])
            raw.setdefault(
                "robot_tcp_command",
                tuple(a + b for a, b in zip(state[6:12], action[:6], strict=True)),
            )
        metadata = {
            **sample.get("metadata", {}),
            "quality": quality,
            "recording_mode": mode,
            "camera_streams": self._metadata,
        }
        return CaptureFrame(
            float(sample["timestamp"]),
            state,
            action,
            dict(zip(IMAGE_KEYS, images, strict=True)),
            metadata=metadata,
            **raw,
        )
