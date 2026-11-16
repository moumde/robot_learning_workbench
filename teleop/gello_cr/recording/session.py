"""Sampling, episode lifecycle, and quality accounting over a generic writer."""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .errors import RecordingError
from .frame import CaptureFrame
from .metadata import (
    DatasetSessionMetadata,
    EpisodeMetadata,
    EpisodeOutcome,
    EpisodeResult,
    build_dataset_name,
)
from .schema import recording_schema
from .validation import validate_capture_frame
from .writers.base import DatasetWriter

if TYPE_CHECKING:
    from .source import CaptureSource


class RecordingSession:
    def __init__(
        self,
        source: CaptureSource,
        writer_factory: Callable[[], DatasetWriter],
        *,
        event_callback: Callable[[str, str], None],
        fps=20,
        image_size=(224, 224),
        robot_type="cr3a",
        hand_type="o6",
    ):
        self.source, self.writer_factory = source, writer_factory
        self.event_callback = event_callback
        self.fps = int(fps)
        self.image_size = tuple(image_size)
        if self.fps <= 0 or len(self.image_size) != 2 or min(self.image_size) <= 0:
            raise ValueError("Recording fps and image size must be positive")
        self.robot_type, self.hand_type = robot_type, hand_type
        self._lock = threading.RLock()
        self._writer = None
        self._session_metadata = None
        self._session_root = ""
        self._recording_mode = "tcp"
        self._episode_thread = None
        self._episode_stop = threading.Event()
        self._episode_active = False
        self._buffered_frames = self._saved_episodes = 0
        self._task = self._last_error = ""
        self._started_at = self._stopped_at = 0.0
        self._first_sample_at = self._last_sample_at = 0.0
        self._late_frames = 0
        self._skipped_samples = 0
        self._max_frame_gap_s = 0.0
        self._quality_max = {}
        self._last_camera_timestamps = {}
        self._reused_camera_frames = {"wrist": 0, "base": 0, "roi": 0}
        self._episode_metadata = None
        self._last_saved_summary = {}
        self._validation_report = None

    def _ensure_session(self, base_root, task):
        requested_root = Path(base_root).expanduser().resolve()
        if self._writer is not None and Path(self._session_root).parent == requested_root:
            return
        if self._writer is not None:
            self.finalize()
        writer = self.writer_factory()
        created_at = datetime.now(timezone.utc).isoformat()  # noqa: UP017 -- data worker compatibility.
        name = build_dataset_name(task, created_at, writer.format_name)
        metadata = DatasetSessionMetadata(
            str(uuid4()),
            task,
            self.robot_type,
            self.hand_type,
            self.fps,
            self.image_size,
            self._recording_mode,
            created_at,
            requested_root / name,
            name,
        )
        if metadata.root.exists():
            metadata = replace(metadata, root=requested_root / f"{name}_{metadata.dataset_id[:8]}")
        self.open_writer(writer, metadata)

    def open_writer(self, writer, metadata: DatasetSessionMetadata):
        """Open an explicitly located dataset without owning its outer lifecycle."""
        if self._writer is not None:
            raise RecordingError("A dataset writer is already open")
        try:
            writer.open(metadata)
        except Exception:
            writer.close()
            raise
        with self._lock:
            self._writer = writer
            self._session_metadata = metadata
            self._session_root = str(metadata.root)
            self._saved_episodes = 0
            self._last_saved_summary = {}
            self._validation_report = None
            self._recording_mode = metadata.recording_mode
        self._event("info", f"Dataset session created: {self._session_root}")

    def release_writer(self):
        """Stop sampling and release a writer, preserving its on-disk evidence."""
        self._stop_sampling()
        if self._writer is not None:
            self._writer.close()
        with self._lock:
            self._writer = None
            self._buffered_frames = 0
            self._episode_active = False
            self._episode_metadata = None
            self._task = self._last_error = ""
            self._started_at = 0.0

    def create_dataset(self, task, base_root):
        """Open a generic writer session without starting episode sampling."""
        if self._writer is not None:
            raise RecordingError("请先完成当前数据集，再创建新数据集")
        task = str(task).strip()
        if not task:
            raise ValueError("Dataset task text cannot be empty")
        first = self.source.capture()
        self._validate_frame(first)
        self._recording_mode = first.metadata.get("recording_mode", "tcp")
        self._ensure_session(base_root, task)
        return self._session_root

    def start_episode(self, task, base_root, *, metadata=None):
        task = str(task).strip()
        if not task:
            raise ValueError("Episode task text cannot be empty")
        with self._lock:
            if self._episode_active:
                raise RecordingError("An Episode is already recording")
            if self._episode_metadata is not None:
                raise RecordingError("The previous Episode is not saved or discarded")
        first = self.source.capture()
        self._validate_frame(first)
        mode = first.metadata.get("recording_mode", "tcp")
        if self._writer is not None and mode != self._recording_mode:
            raise RecordingError("切换记录模式前请先结束当前数据集")
        self._recording_mode = mode
        self._ensure_session(base_root, task)
        # Worker initialization can be slow: recapture after the writer opens.
        first = self.source.capture()
        self._validate_frame(first)
        episode = EpisodeMetadata(
            task,
            self._saved_episodes,
            time.monotonic(),
            metadata or {},
            time.time(),
            tuple(first.metadata.get("camera_streams", ())),
        )
        self._writer.begin_episode(episode)
        with self._lock:
            self._task, self._last_error = task, ""
            self._episode_active = True
            self._started_at = episode.started_at
            self._stopped_at = self._first_sample_at = self._last_sample_at = 0.0
            self._late_frames = 0
            self._skipped_samples = 0
            self._max_frame_gap_s = 0.0
            self._quality_max = {}
            self._last_camera_timestamps = {}
            self._reused_camera_frames = {"wrist": 0, "base": 0, "roi": 0}
            self._episode_metadata = episode
            self._episode_stop.clear()
            self._episode_thread = threading.Thread(
                target=self._record_loop, args=(first,), name="Recording-Episode", daemon=True
            )
            self._episode_thread.start()
        self._event("info", f"Episode recording started: {task}")

    def _validate_frame(self, frame):
        validate_capture_frame(frame, recording_schema(frame.metadata.get("recording_mode", "tcp")))
        quality = frame.metadata.get("quality", {})
        for flag in (
            "wrist_age_exceeded",
            "base_age_exceeded",
            "roi_age_exceeded",
            "camera_skew_exceeded",
        ):
            if quality.get(flag, 0):
                raise RecordingError(f"Cannot start Episode: {flag}")

    def _add_frame(self, frame):
        with self._lock:
            writer = self._writer
            previous = self._last_sample_at if self._buffered_frames else None
        if writer is None:
            raise RecordingError("Dataset session is not initialized")
        validate_capture_frame(
            frame, recording_schema(self._recording_mode), previous_timestamp=previous
        )
        if frame.metadata.get("recording_mode", self._recording_mode) != self._recording_mode:
            raise RecordingError("Recording mode differs from dataset session")
        writer.add_frame(frame)
        with self._lock:
            sampled_at = frame.timestamp
            if self._buffered_frames:
                gap = sampled_at - self._last_sample_at
                self._max_frame_gap_s = max(self._max_frame_gap_s, gap)
                if gap > 1.5 / self.fps:
                    self._late_frames += 1
            else:
                self._first_sample_at = sampled_at
            self._last_sample_at = sampled_at
            for key, value in frame.metadata.get("quality", {}).items():
                if key in ("wrist_timestamp", "base_timestamp", "roi_timestamp"):
                    if self._last_camera_timestamps.get(key) == value:
                        self._reused_camera_frames[key.split("_")[0]] += 1
                    self._last_camera_timestamps[key] = value
                else:
                    self._quality_max[key] = max(self._quality_max.get(key, 0.0), float(value))
            self._buffered_frames += 1

    def save_episode(self, outcome="success", notes=""):
        outcome = EpisodeOutcome(outcome)
        self._stop_sampling()
        with self._lock:
            writer, count, error = self._writer, self._buffered_frames, self._last_error
        if writer is None or count <= 0:
            raise RecordingError("There are no Episode frames to save")
        if error and outcome is not EpisodeOutcome.FAILURE:
            raise RecordingError(
                f"Episode stopped with an error; save it only as failure or discard it: {error}"
            )
        result = EpisodeResult(
            outcome,
            str(notes).strip(),
            time.monotonic(),
            count,
            self.snapshot()["quality"],
            time.time(),
        )
        try:
            receipt = writer.save_episode(result)
        except Exception as exc:
            self._last_error = f"保存失败，请检查数据目录，不要重复提交：{exc}"
            raise
        with self._lock:
            self._saved_episodes += 1
            self._buffered_frames = 0
            self._task = ""
            self._started_at = 0.0
            self._last_saved_summary = {
                **asdict(result),
                "task": self._episode_metadata.task,
                "context": dict(self._episode_metadata.context),
                "episode_index": self._episode_metadata.episode_index,
                "local_episode_index": self._episode_metadata.episode_index,
                "dataset_id": self._session_metadata.dataset_id,
                "root": self._session_root,
                "format": writer.format_name,
                **(receipt if isinstance(receipt, Mapping) else {}),
            }
            self._episode_metadata = None
        self._event("info", f"Episode saved: {count} frames; total {self._saved_episodes}")

    def discard_episode(self):
        self._stop_sampling()
        with self._lock:
            writer, count = self._writer, self._buffered_frames
        if writer is not None and self._episode_metadata is not None:
            try:
                writer.discard_episode()
            except Exception as exc:
                self._last_error = f"丢弃失败，数据未确认清除：{exc}"
                raise
        with self._lock:
            self._buffered_frames = 0
            self._task = self._last_error = ""
            self._started_at = 0.0
            self._episode_metadata = None
        self._event("warning", f"Episode discarded: {count} frames")

    def finalize(self):
        with self._lock:
            if self._episode_active or self._episode_metadata is not None:
                raise RecordingError("当前 Episode 未处理；请先结束录制并保存或丢弃")
        self._stop_sampling()
        writer, root = self._writer, self._session_root
        if writer is None:
            return None
        try:
            writer.finalize()
            writer.close()
        except Exception as exc:
            self._last_error = f"数据集收尾失败：{exc}"
            raise
        with self._lock:
            self._validation_report = getattr(writer, "validation_report", None)
            self._writer = None
            self._episode_active = False
            self._episode_metadata = None
            self._task = self._last_error = ""
            self._started_at = 0.0
        self._event("info", f"Dataset finalized: {root}")
        if self._validation_report is not None:
            report = self._validation_report
            self._event(
                "info" if report["valid"] else "error",
                "Dataset validation: "
                + ("PASS" if report["valid"] else "FAILED")
                + (" · " + "; ".join(report["errors"]) if report["errors"] else ""),
            )
        return root

    def _event(self, level: str, message: str) -> None:
        self.event_callback(level, message)

    def _record_loop(self, first_sample: CaptureFrame) -> None:
        period = 1.0 / self.fps
        next_sample = time.monotonic()
        pending_first: CaptureFrame | None = first_sample
        try:
            while not self._episode_stop.is_set():
                sample = pending_first if pending_first is not None else self.source.capture()
                pending_first = None
                self._add_frame(sample)
                next_sample += period
                completed_at = time.monotonic()
                if completed_at > next_sample:
                    # These scheduled sample slots really were skipped: one
                    # synchronous write/ACK is still in flight, with no backlog.
                    # A slot at completed_at is still available for capture.
                    skipped = math.ceil((completed_at - next_sample) / period)
                    with self._lock:
                        self._skipped_samples += skipped
                    next_sample += skipped * period
                wait_time = next_sample - completed_at
                if wait_time > 0:
                    self._episode_stop.wait(wait_time)
        except Exception as exc:
            logging.getLogger("workbench.recording").exception("Recorder episode sampling failed")
            message = f"{type(exc).__name__}: {exc}"
            with self._lock:
                self._last_error = message
            self._event("error", f"Episode recording stopped: {message}")
        finally:
            with self._lock:
                self._episode_active = False
                self._stopped_at = time.monotonic()

    def _stop_sampling(self) -> None:
        self._episode_stop.set()
        with self._lock:
            thread = self._episode_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=16.0)
            if thread.is_alive():
                raise RecordingError("sampling thread did not stop")

    def stop_episode(self) -> None:
        """End sampling while retaining the current buffer for review."""
        self._stop_sampling()
        self._event("info", "Episode 已结束录制；请标注结果并保存，或明确丢弃")

    def close(self) -> None:
        self.finalize()

    def preserve_failed_session(self) -> None:
        """Explicit recovery: release a failed worker, never clear disk data."""
        with self._lock:
            if not self._last_error:
                raise RecordingError("会话没有错误，请正常保存/丢弃后结束数据集")
            writer = self._writer
            root = self._session_root
            error = self._last_error
        self._stop_sampling()
        if writer is not None:
            writer.close()
        with self._lock:
            self._writer = None
            self._buffered_frames = 0
            self._episode_active = False
            self._started_at = 0.0
            self._task = ""
            self._last_error = ""
            self._episode_metadata = None
        self._event(
            "warning",
            f"异常会话已释放，磁盘文件未删除：{root}；"
            f"未完成数据可能不完整，请保留诊断且不要用于训练。原错误：{error}",
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            duration = (
                (self._stopped_at or time.monotonic()) - self._started_at
                if self._started_at
                else 0.0
            )
            span = self._last_sample_at - self._first_sample_at
            quality = {
                "frames": self._buffered_frames,
                "duration_s": duration,
                "configured_fps": self.fps,
                "effective_fps": (self._buffered_frames - 1) / span
                if self._buffered_frames > 1 and span > 0
                else 0.0,
                "late_frames": self._late_frames,
                "skipped_samples": self._skipped_samples,
                "dropped_frames": None,
                "metric_semantics": {
                    "effective_fps": "acknowledged_samples_over_capture_timestamp_span",
                    "late_frames": "acknowledged_sample_gaps_over_1.5_periods",
                    "skipped_samples": "scheduled_sample_slots_skipped_while_capture_or_ack_busy",
                    "dropped_frames": "unknown_no_camera_sequence_or_confirmed_loss_counter",
                    "reused_camera_frames": "unchanged_camera_timestamp_in_acknowledged_samples",
                },
                "max_frame_gap_s": self._max_frame_gap_s,
                "reused_camera_frames": dict(self._reused_camera_frames),
                "max": dict(self._quality_max),
                "timestamp_basis": "host_monotonic_receipt_not_hardware_sync",
            }
            quality["needs_review"] = self._episode_metadata is not None and bool(
                self._buffered_frames < 2
                or quality["effective_fps"] < 0.9 * self.fps
                or self._late_frames
                or self._skipped_samples
                or any(self._reused_camera_frames.values())
                or self._quality_max.get("tracking_error_exceeded", 0.0) > 0.0
                or self._quality_max.get("desired_tracking_error_exceeded", 0.0) > 0.0
                or self._quality_max.get("feedback_stale", 0.0) > 0.0
                or self._quality_max.get("action_stale", 0.0) > 0.0
                or self._quality_max.get("o6_feedback_stale", 0.0) > 0.0
                or self._quality_max.get("o6_fault_present", 0.0) > 0.0
                or self._quality_max.get("wrist_age_exceeded", 0.0) > 0.0
                or self._quality_max.get("base_age_exceeded", 0.0) > 0.0
                or self._quality_max.get("roi_age_exceeded", 0.0) > 0.0
                or self._quality_max.get("camera_skew_exceeded", 0.0) > 0.0
            )
            return {
                "session_active": self._writer is not None,
                "episode_active": self._episode_active,
                "episode_pending": self._episode_metadata is not None and not self._episode_active,
                "buffered_frames": self._buffered_frames,
                "saved_episodes": self._saved_episodes,
                "duration": duration,
                "task": self._task,
                "episode_index": self._episode_metadata.episode_index
                if self._episode_metadata
                else None,
                "root": self._session_root,
                "format": getattr(self._writer or self.writer_factory, "format_name", ""),
                "validation": self._validation_report,
                "writer_metrics": getattr(self._writer, "metrics", {}),
                "dataset_id": self._session_metadata.dataset_id if self._session_metadata else "",
                "display_name": self._session_metadata.display_name
                if self._session_metadata
                else "",
                "error": self._last_error,
                "quality": quality,
                "last_saved": self._last_saved_summary,
            }
