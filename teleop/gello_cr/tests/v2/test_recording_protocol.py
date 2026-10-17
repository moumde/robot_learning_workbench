from __future__ import annotations

import json
import socket
import struct

import pytest

from gello_cr.recording.protocol import (
    MAX_HEADER_SIZE,
    MAX_RAW_SIZE,
    read_exact,
    receive_packet,
    send_packet,
)


def test_send_and_receive_packet_round_trip() -> None:
    left, right = socket.socketpair()
    try:
        send_packet(left, {"op": "ping", "text": "测试"}, b"abc")
        payload, raw = receive_packet(right)
    finally:
        left.close()
        right.close()

    assert payload == {"op": "ping", "text": "测试"}
    assert raw == b"abc"


def test_send_packet_does_not_mutate_caller_payload() -> None:
    left, right = socket.socketpair()
    payload = {"op": "ping"}
    try:
        send_packet(left, payload, b"x")
        receive_packet(right)
    finally:
        left.close()
        right.close()

    assert payload == {"op": "ping"}


def test_receive_packet_removes_transport_raw_size_field() -> None:
    left, right = socket.socketpair()
    try:
        send_packet(left, {"op": "frame"}, b"1234")
        payload, _ = receive_packet(right)
    finally:
        left.close()
        right.close()

    assert "raw_size" not in payload


def test_read_exact_handles_fragmented_stream() -> None:
    left, right = socket.socketpair()
    try:
        left.sendall(b"ab")
        left.sendall(b"cde")
        assert read_exact(right, 5) == b"abcde"
    finally:
        left.close()
        right.close()


def test_read_exact_zero_size_returns_empty_bytes() -> None:
    left, right = socket.socketpair()
    try:
        assert read_exact(right, 0) == b""
    finally:
        left.close()
        right.close()


def test_read_exact_fails_if_peer_closes_early() -> None:
    left, right = socket.socketpair()
    left.sendall(b"ab")
    left.close()
    try:
        with pytest.raises(EOFError, match="connection closed"):
            read_exact(right, 3)
    finally:
        right.close()


def test_receive_rejects_zero_or_oversized_header() -> None:
    for header_size in (0, MAX_HEADER_SIZE + 1):
        left, right = socket.socketpair()
        try:
            left.sendall(struct.pack("!I", header_size))
            with pytest.raises(ValueError, match="header size"):
                receive_packet(right)
        finally:
            left.close()
            right.close()


def test_receive_rejects_oversized_raw_payload_before_reading_raw() -> None:
    left, right = socket.socketpair()
    try:
        encoded = json.dumps(
            {"op": "frame", "raw_size": MAX_RAW_SIZE + 1},
            separators=(",", ":"),
        ).encode("utf-8")
        left.sendall(struct.pack("!I", len(encoded)) + encoded)
        with pytest.raises(ValueError, match="raw size"):
            receive_packet(right)
    finally:
        left.close()
        right.close()


def test_receive_requires_json_object() -> None:
    left, right = socket.socketpair()
    try:
        encoded = b"[]"
        left.sendall(struct.pack("!I", len(encoded)) + encoded)
        with pytest.raises(ValueError, match="JSON payload"):
            receive_packet(right)
    finally:
        left.close()
        right.close()
