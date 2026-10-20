"""Journaled segment writer and read-only episode discovery."""

import threading
from dataclasses import asdict, replace
from pathlib import Path

from .errors import RecordingError
from .journal import FrameJournal, count_frames
from .manifest import atomic_json, read_json


def episode_records(batch_root, segments):
    records = []
    for segment_id in segments:
        for path in sorted((Path(batch_root) / segment_id / "episodes").glob("*/episode.json")):
            record = read_json(path)
            record.update(segment_id=segment_id, journal_path=str(path.parent / "frames.bin"))
            record["frame_count"] = count_frames(record["journal_path"])
            resolution = Path(batch_root) / "resolutions" / f"{record['episode_index']:06d}.json"
            record["resolution"] = read_json(resolution)["decision"] if resolution.exists() else ""
            if record["resolution"] not in ("", "failure", "discard"):
                raise ValueError("Unknown partial episode resolution")
            records.append(record)
    return sorted(records, key=lambda record: record["episode_index"])


def is_partial(record):
    return record["status"] not in ("saved", "discarded")


def selected_records(records):
    return [
        record
        for record in records
        if record["status"] == "saved"
        or (is_partial(record) and record.get("resolution") == "failure")
    ]


class SegmentWriter:
    def __init__(self, writer, segment_root, *, batch_id, segment_id, allocate, on_change):
        self.writer, self.root = writer, Path(segment_root)
        self.batch_id, self.segment_id = batch_id, segment_id
        self.allocate, self.on_change = allocate, on_change
        self.record = None
        self.journal = None
        self._write_error = ""
        self._lock = threading.RLock()

    def __getattr__(self, name):
        return getattr(self.writer, name)

    def open(self, session):
        self.session = session
        self.writer.open(session)

    def begin_episode(self, metadata):
        self._write_error = ""
        index = self.allocate()
        self.record_root = self.root / "episodes" / f"{index:06d}"
        context = {
            **metadata.context,
            "batch_id": self.batch_id,
            "segment_id": self.segment_id,
            "global_episode_index": index,
        }
        metadata = replace(metadata, context=context)
        self.record = {
            "episode_index": index,
            "local_episode_index": metadata.episode_index,
            "metadata": asdict(metadata),
            "status": "active",
            "frame_count": 0,
            "result": None,
            "resolution": "",
            "segment_id": self.segment_id,
        }
        self.checkpoint()
        self.on_change(self.record)
        self.journal = FrameJournal(
            self.record_root / "frames.bin",
            task=metadata.task,
            image_size=self.session.image_size,
            mode=self.session.recording_mode,
        )
        self.writer.begin_episode(metadata)

    def add_frame(self, frame):
        with self._lock:
            self.journal.append(frame)
            self.record["frame_count"] += 1
        try:
            self.writer.add_frame(frame)
        except Exception as exc:
            # A valid frame is already durable. Backend rejection/uncertain ACK
            # must leave the canonical journal recoverable, never mark a shorter
            # backend buffer as a successfully saved episode.
            with self._lock:
                self._write_error = str(exc)
                self.record["status"] = "interrupted"
                self.record["reason"] = self._write_error
                self.checkpoint()
            raise

    def save_episode(self, result):
        with self._lock:
            if self._write_error:
                raise RecordingError(
                    "Backend frame write failed; preserve this batch and recover the partial "
                    "episode as failure, or discard it explicitly"
                )
            self.record["result"] = asdict(result)
            self.checkpoint()
        self.writer.save_episode(result)
        with self._lock:
            self.record["status"] = "saved"
            self.checkpoint()
            self.journal.close()
            self.journal = None
        self.on_change(self.record)
        receipt = {
            "episode_index": self.record["episode_index"],
            "local_episode_index": self.record["local_episode_index"],
            "batch_id": self.batch_id,
            "segment_id": self.segment_id,
            "episode_path": str(self.record_root),
            "journal_path": str(self.record_root / "frames.bin"),
        }
        self.record = None
        return receipt

    def discard_episode(self):
        self.writer.discard_episode()
        with self._lock:
            self.record["status"] = "discarded"
            self.checkpoint()
            if self.journal is not None:
                self.journal.close()
                self.journal = None
        self.on_change(self.record)
        self.record = None

    def checkpoint(self):
        with self._lock:
            if self.record is not None:
                atomic_json(self.record_root / "episode.json", self.record)

    def finalize(self):
        self.writer.finalize()

    def close(self):
        try:
            self.writer.close()
        finally:
            if self.journal is not None:
                self.journal.close()
                self.journal = None
