from __future__ import annotations

import socket
import threading
from collections import deque

import pytest

from gello_cr.recording.protocol import receive_packet, send_packet
from gello_cr.recording.worker_client import WorkerClient, WorkerClientError


class _AliveProcess:
    returncode = None
    stderr = None

    def poll(self):
        return None


class _ExitedProcess:
    returncode = 17
    stderr = None

    def poll(self):
        return 17


def _client_with_socket(sock: socket.socket, process=None) -> WorkerClient:
    client = WorkerClient.__new__(WorkerClient)
    client._socket = sock
    client._request_lock = threading.Lock()
    client._communication_error = ""
    client._stderr_lines = deque(maxlen=30)
    client._process = process or _AliveProcess()
    return client


def test_request_round_trip_preserves_payload_and_raw() -> None:
    client_sock, worker_sock = socket.socketpair()
    client = _client_with_socket(client_sock)

    def worker():
        request, raw = receive_packet(worker_sock)
        assert request == {"op": "ping"}
        assert raw == b"abc"
        send_packet(worker_sock, {"ok": True, "value": 42})

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        response = client.request({"op": "ping"}, b"abc", timeout=1.0)
    finally:
        thread.join(timeout=1.0)
        client_sock.close()
        worker_sock.close()

    assert response == {"ok": True, "value": 42}


def test_worker_error_response_becomes_worker_client_error() -> None:
    client_sock, worker_sock = socket.socketpair()
    client = _client_with_socket(client_sock)

    def worker():
        receive_packet(worker_sock)
        send_packet(
            worker_sock,
            {"ok": False, "error": "ValueError: bad frame"},
        )

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        with pytest.raises(WorkerClientError, match="bad frame"):
            client.request({"op": "frame"}, timeout=1.0)
    finally:
        thread.join(timeout=1.0)
        client_sock.close()
        worker_sock.close()


def test_transport_failure_is_latched_for_future_requests() -> None:
    client_sock, worker_sock = socket.socketpair()
    client = _client_with_socket(client_sock)
    worker_sock.close()

    try:
        with pytest.raises(WorkerClientError, match="communication failed"):
            client.request({"op": "ping"}, timeout=1.0)

        assert client._communication_error

        with pytest.raises(
            WorkerClientError,
            match="communication failed",
        ):
            client.request({"op": "ping"}, timeout=1.0)
    finally:
        client_sock.close()


def test_exited_worker_is_reported_before_socket_use() -> None:
    client_sock, worker_sock = socket.socketpair()
    client = _client_with_socket(client_sock, _ExitedProcess())

    try:
        with pytest.raises(WorkerClientError, match="exited with code 17"):
            client.request({"op": "ping"}, timeout=1.0)
    finally:
        client_sock.close()
        worker_sock.close()


def test_request_restores_previous_socket_timeout() -> None:
    client_sock, worker_sock = socket.socketpair()
    client_sock.settimeout(9.0)
    client = _client_with_socket(client_sock)

    def worker():
        receive_packet(worker_sock)
        send_packet(worker_sock, {"ok": True})

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        client.request({"op": "ping"}, timeout=1.0)
        assert client_sock.gettimeout() == pytest.approx(9.0)
    finally:
        thread.join(timeout=1.0)
        client_sock.close()
        worker_sock.close()


def test_constructor_rejects_missing_python_executable(tmp_path) -> None:
    script = tmp_path / "worker.py"
    script.write_text("pass\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="LeRobot Python"):
        WorkerClient(
            str(tmp_path / "missing-python"),
            worker_script=script,
        )
