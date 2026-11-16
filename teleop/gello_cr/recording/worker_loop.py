"""Existing packet protocol with lazy dataset backend selection at init."""

import socket
import traceback
from dataclasses import asdict
from pathlib import Path

from .protocol import receive_packet, send_packet
from .writers.factory import create_validator, create_worker_service


def run_worker(fd: int) -> int:
    sock = socket.socket(fileno=fd)
    service = None
    validator = None
    root = None
    try:
        while True:
            try:
                request, raw = receive_packet(sock)
            except EOFError:
                break
            try:
                if request.get("op") == "validate" and service is None:
                    validator = create_validator(request["format"])
                    report = validator.validate(Path(request["root"]))
                    send_packet(sock, {"ok": True, "validation": asdict(report)})
                    break
                if request.get("op") == "init" and service is None:
                    format_name = request.get("format", "lerobot_v3")
                    service = create_worker_service(format_name)
                    validator = create_validator(format_name)
                    root = Path(request["root"])
                if service is None:
                    raise RuntimeError("Initialize the dataset before writing")
                response, should_exit = service.handle_request(request, raw)
                if should_exit:
                    response["validation"] = asdict(validator.validate(root))
                send_packet(sock, response)
                if should_exit:
                    break
            except Exception as exc:
                traceback.print_exc()
                send_packet(sock, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        if service is not None:
            service.finalize_best_effort()
        sock.close()
    return 0
