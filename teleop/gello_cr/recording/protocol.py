"""Unix-socket packet protocol for the LeRobot recorder worker.

The wire format is intentionally unchanged from the validated legacy recorder:

    4-byte big-endian JSON-header length
    UTF-8 JSON header
    optional raw bytes

The JSON header carries `raw_size`; `receive_packet()` removes that transport
field before returning the payload to callers.
"""

from __future__ import annotations

import json
import socket
import struct
from collections.abc import Mapping
from typing import Any

MAX_HEADER_SIZE = 4 * 1024 * 1024
# Match the largest configured three-stream RGB frame without removing the wire bound.
MAX_IMAGE_DIMENSION = 2160
MAX_RAW_SIZE = 3 * MAX_IMAGE_DIMENSION * MAX_IMAGE_DIMENSION * 3


def read_exact(sock: socket.socket, size: int) -> bytes:
    """Read exactly `size` bytes or fail if the peer closes early."""

    remaining = int(size)
    if remaining < 0:
        raise ValueError("read size must be non-negative")

    chunks: list[bytes] = []
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError("LeRobot worker connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_packet(
    sock: socket.socket,
    payload: Mapping[str, Any],
    raw: bytes = b"",
) -> None:
    """Send one protocol packet using the existing wire representation."""

    message = dict(payload)
    message["raw_size"] = len(raw)
    encoded = json.dumps(
        message,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    sock.sendall(struct.pack("!I", len(encoded)) + encoded + raw)


def receive_packet(sock: socket.socket) -> tuple[dict[str, Any], bytes]:
    """Receive one packet and return `(payload_without_raw_size, raw)`."""

    header_size = struct.unpack("!I", read_exact(sock, 4))[0]
    if header_size <= 0 or header_size > MAX_HEADER_SIZE:
        raise ValueError(f"Invalid protocol header size: {header_size}")

    payload = json.loads(read_exact(sock, header_size).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Protocol JSON payload must be an object")

    raw_size = int(payload.pop("raw_size", 0))
    if raw_size < 0 or raw_size > MAX_RAW_SIZE:
        raise ValueError(f"Invalid protocol raw size: {raw_size}")

    raw = read_exact(sock, raw_size) if raw_size else b""
    return payload, raw
