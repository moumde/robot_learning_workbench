"""Shared acknowledged worker lifecycle; backend selection stays in the factory."""

from pathlib import Path
from time import perf_counter

from ..errors import DatasetFinalizeError, WriterError, WriterStateError
from ..frame import CaptureFrame
from ..metadata import DatasetSessionMetadata, EpisodeMetadata, EpisodeResult, session_manifest
from ..worker_client import WorkerClient
from .frame_mapping import prepare_frame
from .lerobot_v3_schema import LEGACY_SAMPLE_IMAGE_KEYS, LEROBOT_IMAGE_FEATURE_KEYS


class WorkerDatasetWriter:
    def __init__(
        self,
        worker_python,
        repo_prefix="local/capture",
        *,
        worker_script=None,
        client_factory=WorkerClient,
        video_codec=None,
        hdf5_compression=None,
    ):
        self.worker_python, self.repo_prefix = str(worker_python), str(repo_prefix)
        self.worker_script = (
            Path(worker_script).expanduser().resolve()
            if worker_script is not None
            else Path(__file__).resolve().parents[1] / "worker.py"
        )
        self._client_factory = client_factory
        self._client = None
        self._session = None
        self._episode = None
        self._frames = 0
        self._saved_episodes = 0
        self._finalized = False
        self._closed = False
        self.repo_id = ""
        self.video_codec = video_codec
        self.hdf5_compression = hdf5_compression
        self.validation_report = None
        self._write_seconds = 0.0
        self._write_count = 0
        self._max_write_seconds = 0.0
        self._write_in_flight = False

    @property
    def metrics(self):
        return {
            "mean_write_latency_s": self._write_seconds / max(1, self._write_count),
            "max_write_latency_s": self._max_write_seconds,
            # Synchronous acknowledgments bound outstanding frames to one.
            "queue_depth": int(self._write_in_flight),
        }

    def _require_open(self):
        if self._session is None or self._finalized or self._closed:
            raise WriterStateError("Writer session is not open")

    def _request(self, payload, *, raw=b"", timeout=30.0):
        try:
            return self._client.request(payload, raw=raw, timeout=timeout)
        except Exception as exc:
            raise WriterError(str(exc)) from exc

    def open(self, session: DatasetSessionMetadata):
        if self._session is not None or self._closed:
            raise WriterStateError("Writer can only open one session")
        owner, prefix = self.repo_prefix.split("/", 1)
        self.repo_id = f"{owner}/{prefix}_{session.dataset_id}"
        self._client = self._client_factory(self.worker_python, worker_script=self.worker_script)
        try:
            session_metadata = session_manifest(session, self.format_name)
            self._request(
                {
                    "op": "init",
                    "format": self.format_name,
                    "video_codec": self.video_codec,
                    "hdf5_compression": self.hdf5_compression,
                    "recording_mode": session.recording_mode,
                    "repo_id": self.repo_id,
                    "root": str(session.root),
                    "fps": session.fps,
                    "height": session.image_size[0],
                    "width": session.image_size[1],
                    "session_metadata": session_metadata,
                },
                timeout=60.0,
            )
        except Exception:
            self.close()
            raise
        self._session = session

    def begin_episode(self, metadata: EpisodeMetadata):
        self._require_open()
        if self._episode is not None:
            raise WriterStateError("Resolve the current episode before beginning another")
        if metadata.episode_index != self._saved_episodes or not metadata.task.strip():
            raise WriterStateError("Episode index/task does not match the writer session")
        self._episode = metadata
        self._frames = 0

    def add_frame(self, frame: CaptureFrame):
        self._require_open()
        if self._episode is None:
            raise WriterStateError("begin_episode must precede add_frame")
        mode = self._session.recording_mode
        if frame.metadata.get("recording_mode", mode) != mode:
            raise WriterStateError("Recording mode differs from dataset session")
        started = perf_counter()
        payload, raw = prepare_frame(
            frame,
            task=self._episode.task,
            height=self._session.image_size[0],
            width=self._session.image_size[1],
            recording_mode=mode,
        )
        self._write_in_flight = True
        try:
            self._request(payload, raw=raw, timeout=15.0)
        finally:
            self._write_in_flight = False
        elapsed = perf_counter() - started
        self._write_seconds += elapsed
        self._max_write_seconds = max(self._max_write_seconds, elapsed)
        self._write_count += 1
        self._frames += 1

    def save_episode(self, metadata: EpisodeResult):
        self._require_open()
        if self._episode is None or not self._frames or metadata.frame_count != self._frames:
            raise WriterStateError("No matching episode frames to save")
        streams = []
        for index, stream in enumerate(self._episode.camera_streams):
            item = dict(stream)
            item.pop("image_key", None)
            item.update(
                sample_key=LEGACY_SAMPLE_IMAGE_KEYS[index],
                feature_key=LEROBOT_IMAGE_FEATURE_KEYS[index],
            )
            streams.append(item)
        collection = {
            "started_at_unix_s": self._episode.started_at_unix_s,
            "ended_at_unix_s": metadata.ended_at_unix_s,
            "context": dict(self._episode.context),
            "camera_streams": streams,
            "task": self._episode.task,
            "outcome": str(metadata.outcome),
            "notes": metadata.notes,
            "duration": max(0.0, metadata.ended_at - self._episode.started_at),
            "quality": dict(metadata.quality),
            "dataset_id": self._session.dataset_id,
            "display_name": self._session.display_name,
        }
        response = self._request({"op": "save_episode", "collection": collection}, timeout=180.0)
        self._saved_episodes = int(response["episodes"])
        self._episode = None
        self._frames = 0

    def discard_episode(self):
        self._require_open()
        if self._episode is None:
            raise WriterStateError("No episode to discard")
        self._request({"op": "clear_episode"}, timeout=60.0)
        self._episode = None
        self._frames = 0

    def finalize(self):
        if self._finalized:
            return
        self._require_open()
        if self._episode is not None:
            raise WriterStateError("Resolve the current episode before finalize")
        try:
            response = self._request({"op": "finalize"}, timeout=180.0)
            self.validation_report = response.get("validation")
        except WriterError as exc:
            raise DatasetFinalizeError(str(exc)) from exc
        self._finalized = True

    def close(self):
        if self._closed:
            return
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                raise WriterError(f"Data worker close failed: {exc}") from exc
        self._closed = True
