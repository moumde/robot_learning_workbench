"""Format-independent source validation and atomic batch publication."""

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4

from .errors import RecordingError
from .journal import read_frames
from .manifest import (
    PROFILE_FIELDS,
    BatchStatus,
    SegmentManifest,
    SegmentStatus,
    atomic_json,
    durable_directory,
    fsync_directory,
    now,
)
from .metadata import DatasetSessionMetadata, build_dataset_name
from .schema import recording_schema
from .segment import episode_records, is_partial, selected_records
from .validation import validate_capture_frame


@dataclass
class MergeValidationReport:
    valid: bool = True
    segments: int = 0
    episodes: int = 0
    frames: int = 0
    partial_episodes: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MergeValidator:
    def validate(self, batch, batch_root):
        report = MergeValidationReport(segments=len(batch.segments))
        try:
            for segment_id in batch.segments:
                segment = SegmentManifest.load(Path(batch_root) / segment_id)
                if segment.batch_id != batch.batch_id:
                    raise RecordingError(f"{segment_id}: batch_id mismatch")
                if segment.dataset_format != batch.dataset_format:
                    raise RecordingError(f"{segment_id}: dataset_format mismatch")
                if segment.status == SegmentStatus.ACTIVE:
                    raise RecordingError(f"{segment_id}: segment is still active")
                for key in PROFILE_FIELDS:
                    if segment.profile[key] != batch.profile[key]:
                        raise RecordingError(f"{segment_id}: {key} mismatch")
            records = episode_records(batch_root, batch.segments)
            indices = [record["episode_index"] for record in records]
            if len(set(indices)) != len(indices):
                raise RecordingError("Duplicate global episode indices")
            report.partial_episodes = [
                record["episode_index"]
                for record in records
                if is_partial(record) and not record["resolution"]
            ]
            if report.partial_episodes:
                raise RecordingError(f"Resolve partial episodes first: {report.partial_episodes}")
            selected = selected_records(records)
            if not selected:
                raise RecordingError("Batch has no retained episode frames to merge")
            schema = recording_schema(batch.profile["recording_mode"])
            for record in selected:
                previous = None
                count = 0
                for frame in read_frames(record["journal_path"]):
                    validate_capture_frame(frame, schema, previous_timestamp=previous)
                    if frame.metadata["recording_mode"] != schema.name or any(
                        image.shape != (*batch.profile["image_size"], 3)
                        for image in frame.images.values()
                    ):
                        raise RecordingError("Journal frame differs from the batch schema")
                    previous = frame.timestamp
                    count += 1
                if not count or count != record["frame_count"]:
                    raise RecordingError(
                        f"Episode {record['episode_index']}: invalid journal length"
                    )
                if record["status"] == "saved" and record["result"]["frame_count"] != count:
                    raise RecordingError("Saved episode journal is incomplete")
                report.episodes += 1
                report.frames += count
        except Exception as exc:
            report.valid = False
            report.errors.append(str(exc))
        return report


def publish_batch(batch, batch_root, writer_factory, *, event):
    """Write a fresh dataset on the target filesystem, validate, then rename."""
    from .mergers.factory import create_merger

    report = MergeValidator().validate(batch, batch_root)
    atomic_json(Path(batch_root) / "merge_validation.json", asdict(report))
    if not report.valid:
        raise RecordingError("; ".join(report.errors))
    event("info", f"Merge validation PASS · batch_id={batch.batch_id}")
    output_root = Path(batch.output_root)
    durable_directory(output_root)
    dataset_id = str(uuid4())
    created_at = now()
    name = build_dataset_name(batch.task_name, created_at, batch.dataset_format)
    final = output_root / f"{name}_{dataset_id[:8]}"
    temporary = output_root / f".tmp_{dataset_id}"
    batch.status = BatchStatus.FINALIZING
    batch.final_dataset_id = dataset_id
    batch.final_path, batch.temp_path = str(final), str(temporary)
    batch.save(batch_root)
    profile = batch.profile
    session = DatasetSessionMetadata(
        dataset_id,
        batch.task_name,
        profile["robot_type"],
        profile["hand_type"],
        profile["fps"],
        tuple(profile["image_size"]),
        profile["recording_mode"],
        created_at,
        temporary,
        final.name,
    )
    records = selected_records(episode_records(batch_root, batch.segments))
    merger = create_merger(batch.dataset_format, writer_factory)
    validation = merger.merge(records, session)
    event("info", f"Dataset merged · batch_id={batch.batch_id}")
    if validation is None or not validation["valid"]:
        raise RecordingError("Final validation FAILED: " + str(validation))
    mapping = [
        {
            "episode_index": i,
            "segment_id": record["segment_id"],
            "global_episode_index": record["episode_index"],
            "local_episode_index": record["local_episode_index"],
            "partial_promoted": is_partial(record),
        }
        for i, record in enumerate(records)
    ]
    atomic_json(
        temporary / "batch_provenance.json",
        {
            "batch_id": batch.batch_id,
            "task_name": batch.task_name,
            "dataset_format": batch.dataset_format,
            "created_at": created_at,
            "dataset_id": dataset_id,
            "segments": batch.segments,
            "episode_mapping": mapping,
            "published_path": str(final),
            "validation": validation,
        },
    )
    event("info", f"Final validation PASS · batch_id={batch.batch_id}")
    sync_tree(temporary)
    atomic_publish(temporary, final)
    batch.status, batch.last_error = BatchStatus.COMPLETED, ""
    batch.save(batch_root)
    event("info", f"Dataset published: {final}")
    return final


def atomic_publish(temporary, final):
    if final.exists():
        raise FileExistsError(f"Final dataset already exists: {final}")
    os.rename(temporary, final)
    fsync_directory(final.parent)


def sync_tree(root):
    directories = [root]
    for path in root.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        elif path.is_dir():
            directories.append(path)
    for path in reversed(directories):
        fsync_directory(path)
