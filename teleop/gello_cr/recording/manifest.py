"""Atomic batch/segment manifests and OS-owned capture locks."""

import fcntl
import json
import os
import socket
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .errors import RecordingError


def now():
    return datetime.now(UTC).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    durable_directory(path.parent)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_directory(path):
    path = Path(path)
    missing = []
    ancestor = path
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    path.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        fsync_directory(created.parent)


class BatchStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    RECOVERABLE = "recoverable"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISCARDED = "discarded"


class SegmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    INVALID = "invalid"


PROFILE_FIELDS = (
    "robot_type",
    "hand_type",
    "recording_mode",
    "fps",
    "image_size",
    "camera_keys",
    "camera_configuration",
    "hardware_profile",
    "observation_fields",
    "action_fields",
    "observation_dim",
    "action_dim",
    "schema_version",
    "schema_hash",
)


@dataclass
class BatchManifest:
    batch_id: str
    task_name: str
    dataset_format: str
    profile: dict
    output_root: str
    created_at: str = field(default_factory=now)
    status: str = BatchStatus.IN_PROGRESS
    segments: list[str] = field(default_factory=list)
    next_episode_index: int = 0
    final_dataset_id: str = ""
    final_path: str = ""
    temp_path: str = ""
    last_error: str = ""
    writer_options: dict = field(default_factory=dict)
    task_description: str = ""

    def save(self, root):
        value = asdict(self)
        value.update(value.pop("profile"))
        atomic_json(Path(root) / "manifest.json", value)

    @classmethod
    def load(cls, root):
        value = read_json(Path(root) / "manifest.json")
        profile = {key: value.pop(key) for key in PROFILE_FIELDS}
        return cls(profile=profile, **value)


@dataclass
class SegmentManifest:
    segment_id: str
    batch_id: str
    dataset_id: str
    dataset_format: str
    profile: dict
    episode_start_index: int
    started_at: str = field(default_factory=now)
    ended_at: str | None = None
    last_update_at: str = field(default_factory=now)
    status: str = SegmentStatus.ACTIVE
    episode_end_index: int | None = None
    frame_count: int = 0
    reason: str = ""

    def save(self, root):
        value = asdict(self)
        value.update(value.pop("profile"))
        atomic_json(Path(root) / "segment.json", value)

    @classmethod
    def load(cls, root):
        value = read_json(Path(root) / "segment.json")
        profile = {key: value.pop(key) for key in PROFILE_FIELDS}
        return cls(profile=profile, **value)


class BatchLock:
    def __init__(self, root):
        self.path = Path(root) / "batch.lock"
        self.stream = None

    def acquire(self):
        durable_directory(self.path.parent)
        stream = self.path.open("a+b")
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            stream.close()
            raise RecordingError("Batch is already open in another process") from exc
        self.stream = stream
        stream.truncate(0)
        stream.write(
            json.dumps(
                {"pid": os.getpid(), "hostname": socket.gethostname(), "started_at": now()}
            ).encode()
        )
        stream.flush()
        os.fsync(stream.fileno())
        return self

    def release(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    @staticmethod
    def held(root):
        path = Path(root) / "batch.lock"
        if not path.exists():
            return False
        with path.open("rb") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            return False
