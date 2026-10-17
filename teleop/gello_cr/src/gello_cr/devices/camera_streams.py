"""Configuration of the three preview/capture image slots (no device I/O)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from gello_cr.recording.schema import IMAGE_KEYS


@dataclass(frozen=True, slots=True)
class CameraStreamConfig:
    name: str
    serial: str
    mode: str = "camera"
    roi_norm: tuple[float, ...] = (0.0, 0.0, 1.0, 1.0)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("相机窗口名称不能为空")
        if not isinstance(self.serial, str) or not self.serial.strip():
            raise ValueError(f"{self.name}：请选择相机序列号")
        if self.mode not in ("camera", "roi"):
            raise ValueError(f"{self.name}：画面来源必须是 camera 或 roi")
        if len(self.roi_norm) != 4 or not all(math.isfinite(v) for v in self.roi_norm):
            raise ValueError(f"{self.name}：ROI 必须包含四个有限数值")
        x1, y1, x2, y2 = self.roi_norm
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError(f"{self.name}：ROI 必须满足 0≤x1<x2≤1、0≤y1<y2≤1")

    @property
    def description(self) -> str:
        mode = "完整画面" if self.mode == "camera" else f"ROI {list(self.roi_norm)}"
        return f"{self.serial} · {mode}"


def resolve_camera_streams(dataset: dict) -> tuple[CameraStreamConfig, ...]:
    """Read explicit slots, or migrate the existing two-camera + Base ROI layout."""
    entries = dataset.get("camera_streams")
    if entries is None:
        return (
            CameraStreamConfig("Base RGB", dataset["base_camera_serial"]),
            CameraStreamConfig("Wrist RGB", dataset["wrist_camera_serial"]),
            CameraStreamConfig(
                "Base ROI", dataset["base_camera_serial"], "roi", tuple(dataset["base_roi_norm"])
            ),
        )
    if not isinstance(entries, list) or len(entries) != 3:
        raise ValueError("camera_streams 必须配置三个录制窗口")
    streams = tuple(CameraStreamConfig(**entry) for entry in entries)
    if len({stream.name for stream in streams}) != 3:
        raise ValueError("三个相机窗口名称不能重复")
    return streams


def camera_stream_metadata(streams: tuple[CameraStreamConfig, ...]) -> list[dict]:
    return [
        dict(asdict(stream), image_key=image_key)
        for stream, image_key in zip(streams, IMAGE_KEYS, strict=True)
    ]
