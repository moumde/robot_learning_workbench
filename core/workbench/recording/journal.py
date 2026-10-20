"""Durable canonical frame packets, independent of SDK file finalization."""

import json
import os
import struct
from pathlib import Path

import numpy as np

from .frame import CaptureFrame
from .manifest import durable_directory, fsync_directory
from .protocol import MAX_HEADER_SIZE, MAX_RAW_SIZE
from .schema import IMAGE_KEYS
from .writers.frame_mapping import prepare_frame


class FrameJournal:
    def __init__(self, path, *, task, image_size, mode):
        self.path = Path(path)
        durable_directory(self.path.parent)
        self.stream = self.path.open("xb", buffering=0)
        fsync_directory(self.path.parent)
        self.task, self.image_size, self.mode = task, image_size, mode

    def append(self, frame):
        payload, raw = prepare_frame(
            frame,
            task=self.task,
            height=self.image_size[0],
            width=self.image_size[1],
            recording_mode=self.mode,
        )
        payload["capture_metadata"] = dict(frame.metadata)
        payload["raw_size"] = len(raw)
        encoded = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
        packet = memoryview(struct.pack("!I", len(encoded)) + encoded + raw)
        while packet:
            written = self.stream.write(packet)
            if not written:
                raise OSError("Incomplete journal write")
            packet = packet[written:]
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()


def packets(path, *, read_images=True):
    """Read full packets only; a torn last write is not a complete frame."""
    path = Path(path)
    if not path.exists():
        return
    size = path.stat().st_size
    with path.open("rb") as stream:
        while stream.tell() < size:
            prefix = stream.read(4)
            if len(prefix) < 4:
                return
            length = struct.unpack("!I", prefix)[0]
            if not 0 < length <= MAX_HEADER_SIZE:
                raise ValueError(f"Invalid journal header at {stream.tell() - 4}")
            encoded = stream.read(length)
            if len(encoded) < length:
                return
            payload = json.loads(encoded)
            raw_size = int(payload.pop("raw_size"))
            if not 0 <= raw_size <= MAX_RAW_SIZE:
                raise ValueError("Invalid journal image payload size")
            if stream.tell() + raw_size > size:
                return
            if read_images:
                raw = stream.read(raw_size)
            else:
                stream.seek(raw_size, os.SEEK_CUR)
                raw = b""
            yield payload, raw


def count_frames(path):
    return sum(1 for _ in packets(path, read_images=False))


def read_frames(path):
    for payload, raw in packets(path):
        shape = (3, int(payload["height"]), int(payload["width"]), 3)
        images = np.frombuffer(raw, np.uint8).reshape(shape)
        sample = payload["sample_metadata"]
        metadata = {
            **payload.get("capture_metadata", {}),
            "recording_mode": payload["recording_mode"],
            "quality": sample["quality"],
        }
        yield CaptureFrame(
            float(sample["timestamp"]),
            tuple(payload["state"]),
            tuple(payload["action"]),
            {key: images[i] for i, key in enumerate(IMAGE_KEYS)},
            **{key: tuple(value) for key, value in sample.get("raw", {}).items()},
            metadata=metadata,
        )
