"""Format-independent dataset identity, naming, and episode results."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .schema import recording_schema


class EpisodeOutcome(str, Enum):  # noqa: UP042 -- keep the separate data worker Python 3.10 compatible.
    SUCCESS = "success"
    FAILURE = "failure"

    def __str__(self):
        return self.value


def build_dataset_name(task_name: str, created_at: str, format_name: str) -> str:
    task = re.sub(r"[^\w.-]+", "_", task_name.strip()).strip("._") or "task"
    stamp = datetime.fromisoformat(created_at).strftime("%Y%m%d-%H%M%S")
    return f"{task}_{stamp}_{format_name}"


@dataclass(frozen=True, slots=True)
class DatasetSessionMetadata:
    dataset_id: str
    task_name: str
    robot_type: str
    hand_type: str | None
    fps: float
    image_size: tuple[int, int]
    recording_mode: str
    created_at: str
    root: Path
    display_name: str


def session_manifest(session: DatasetSessionMetadata, format_name: str) -> dict:
    schema = recording_schema(session.recording_mode)
    layout = {
        "observation_fields": schema.observation_fields,
        "action_fields": schema.action_fields,
        "camera_keys": schema.image_keys,
        "image_size": session.image_size,
        "recording_mode": session.recording_mode,
    }
    return {
        **asdict(session),
        "root": str(session.root),
        "dataset_name": session.display_name,
        "format_version": format_name,
        "schema_version": f"cr3_o6_{session.recording_mode}_abs_v1",
        "schema_hash": hashlib.sha256(json.dumps(layout, sort_keys=True).encode()).hexdigest(),
        **layout,
    }


@dataclass(frozen=True, slots=True)
class EpisodeMetadata:
    task: str
    episode_index: int
    started_at: float
    context: Mapping[str, Any] = field(default_factory=dict)
    started_at_unix_s: float = 0.0
    camera_streams: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    outcome: EpisodeOutcome
    notes: str
    ended_at: float
    frame_count: int
    quality: Mapping[str, Any]
    ended_at_unix_s: float = 0.0
