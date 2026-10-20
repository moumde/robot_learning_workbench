"""Read-only format validation in the configured data Python environment."""

from pathlib import Path

from .worker_client import WorkerClient


def validate_in_worker(format_name, root, writer_factory):
    python = writer_factory.worker_pythons.get(format_name, writer_factory.config.worker_python)
    client = WorkerClient(python, Path(__file__).with_name("worker.py"))
    try:
        return client.request(
            {"op": "validate", "format": format_name, "root": str(root)}, timeout=180.0
        )["validation"]
    finally:
        client.close()
