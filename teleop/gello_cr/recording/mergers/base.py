"""Merge canonical journals through the existing writer contract."""

from dataclasses import replace
from typing import Protocol

from ..errors import RecordingError
from ..formats import DatasetFormat
from ..journal import read_frames
from ..metadata import EpisodeMetadata, EpisodeOutcome, EpisodeResult
from ..segment import is_partial
from ..writers.factory import create_writer


class DatasetMerger(Protocol):
    def merge(self, records, session) -> None: ...


class JournalDatasetMerger:
    def __init__(self, writer_factory):
        self.writer_factory = writer_factory

    def merge(self, records, session):
        config = self.writer_factory.config
        python = self.writer_factory.worker_pythons.get(self.format_name, config.worker_python)
        writer = create_writer(
            replace(config, format=DatasetFormat(self.format_name), worker_python=python)
        )
        writer.open(session)
        try:
            for index, record in enumerate(records):
                original = record["metadata"]
                metadata = EpisodeMetadata(
                    original["task"],
                    index,
                    original["started_at"],
                    {
                        **original["context"],
                        "global_episode_index": record["episode_index"],
                        "segment_id": record["segment_id"],
                        "partial_promoted": is_partial(record),
                    },
                    original["started_at_unix_s"],
                    tuple(original["camera_streams"]),
                )
                writer.begin_episode(metadata)
                count = 0
                for frame in read_frames(record["journal_path"]):
                    writer.add_frame(frame)
                    count += 1
                    last_timestamp = frame.timestamp
                result = record.get("result") or {}
                quality = dict(result.get("quality", {}))
                if is_partial(record):
                    quality.update(needs_review=True, partial=True, recovery_reason="interruption")
                quality.setdefault("needs_review", False)
                writer.save_episode(
                    EpisodeResult(
                        EpisodeOutcome.FAILURE
                        if is_partial(record)
                        else EpisodeOutcome(result["outcome"]),
                        result.get(
                            "notes", "Recovered partial episode; kept explicitly as failure"
                        ),
                        result.get("ended_at", last_timestamp),
                        count,
                        quality,
                        result.get("ended_at_unix_s", 0.0),
                    )
                )
            writer.finalize()
            if writer.validation_report is not None and not writer.validation_report["valid"]:
                raise RecordingError(
                    "Final validation FAILED: " + "; ".join(writer.validation_report["errors"])
                )
            return writer.validation_report
        finally:
            writer.close()
