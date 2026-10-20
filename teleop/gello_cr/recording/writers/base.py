"""Narrow writer contract: no sampling, devices, or format-specific fields."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ..frame import CaptureFrame
from ..metadata import DatasetSessionMetadata, EpisodeMetadata, EpisodeResult


@dataclass(frozen=True, slots=True)
class WriterCapabilities:
    supports_video: bool
    supports_raw_images: bool
    supports_episode_discard: bool
    supports_structured_robot_state: bool


class DatasetWriter(Protocol):
    format_name: str
    capabilities: WriterCapabilities

    def open(self, session: DatasetSessionMetadata) -> None: ...
    def begin_episode(self, metadata: EpisodeMetadata) -> None: ...
    def add_frame(self, frame: CaptureFrame) -> None: ...
    def save_episode(self, metadata: EpisodeResult) -> Mapping[str, Any] | None: ...
    def discard_episode(self) -> None: ...
    def finalize(self) -> None: ...
    def close(self) -> None: ...
