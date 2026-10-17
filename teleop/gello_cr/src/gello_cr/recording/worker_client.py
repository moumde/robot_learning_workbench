"""LeRobot worker subprocess client.

This is the hardware-process side of the recorder bridge. It owns:
- one socketpair endpoint;
- the LeRobot worker subprocess;
- serialized request/response access;
- stderr diagnostics;
- the permanent communication-error latch after transport/protocol failure.

The worker script path is explicit so the recorder can select the packaged
entry point or an application-provided worker without changing the protocol.
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any

from .errors import WriterError
from .protocol import receive_packet, send_packet


class WorkerClientError(WriterError):
    """Worker process/transport failure exposed to the recorder."""


class WorkerClient:
    def __init__(
        self,
        python_executable: str,
        worker_script: str | Path,
    ) -> None:
        executable = Path(python_executable).expanduser()
        if not executable.is_file():
            raise FileNotFoundError(f"LeRobot Python does not exist: {executable}")

        script = Path(worker_script).expanduser().resolve()
        if not script.is_file():
            raise FileNotFoundError(f"LeRobot worker script does not exist: {script}")

        parent_socket, child_socket = socket.socketpair()
        self._socket = parent_socket
        self._request_lock = threading.Lock()
        self._communication_error = ""
        self._stderr_lines: deque[str] = deque(maxlen=30)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        worker_lib = executable.parent.parent / "lib"
        inherited_library_path = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = str(worker_lib) + (
            f":{inherited_library_path}" if inherited_library_path else ""
        )

        try:
            self._process = subprocess.Popen(
                [
                    str(executable),
                    str(script),
                    "--worker-fd",
                    str(child_socket.fileno()),
                ],
                pass_fds=(child_socket.fileno(),),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception:
            parent_socket.close()
            child_socket.close()
            raise

        child_socket.close()
        self._stderr_thread = threading.Thread(
            target=self._collect_stderr,
            name="LeRobot-Worker-Stderr",
            daemon=True,
        )
        self._stderr_thread.start()

    def _collect_stderr(self) -> None:
        stream = self._process.stderr
        if stream is None:
            return
        for line in stream:
            text = line.rstrip()
            if text:
                self._stderr_lines.append(text)

    def request(
        self,
        payload: dict[str, Any],
        raw: bytes = b"",
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        with self._request_lock:
            if self._communication_error:
                raise WorkerClientError(self._communication_error)

            if self._process.poll() is not None:
                details = "\n".join(self._stderr_lines)
                raise WorkerClientError(
                    f"LeRobot worker exited with code "
                    f"{self._process.returncode}" + (f":\n{details}" if details else "")
                )

            previous_timeout = self._socket.gettimeout()
            self._socket.settimeout(timeout)
            try:
                send_packet(self._socket, payload, raw)
                response, _ = receive_packet(self._socket)
            except (OSError, EOFError, ValueError) as exc:
                details = "\n".join(self._stderr_lines)
                self._communication_error = f"LeRobot worker communication failed: {exc}" + (
                    f"\n{details}" if details else ""
                )
                # A late response must never be mistaken for the next request's
                # acknowledgement after a timeout (there are no request IDs).
                raise WorkerClientError(self._communication_error) from exc
            finally:
                self._socket.settimeout(previous_timeout)

            if not response.get("ok", False):
                raise WorkerClientError(str(response.get("error", "Unknown worker error")))
            return response

    def close(self) -> None:
        try:
            self._socket.close()
        except OSError:
            pass

        if self._process.poll() is None:
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=2.0)

        thread = self._stderr_thread
        if thread is not threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                raise WorkerClientError("LeRobot stderr thread did not stop")
        if self._process.stderr is not None:
            self._process.stderr.close()
