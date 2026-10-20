"""Hardware-free deployment identity; connected state is supplied by the owner."""

import platform
import subprocess
import sys

from teleop.gello_cr import __version__


def diagnostic_report(config, repo_root, *, connected_devices=None):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        commit = result.stdout.strip() if result.returncode == 0 else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        commit = "unknown"
    dataset = config["dataset"]
    return {
        "version": __version__,
        "git_commit": commit,
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "hardware_profile": config["hardware"]["profile"],
        "master": config["master"]["type"],
        "connected_devices": dict(connected_devices or {}),
        "dataset": {
            key: dataset.get(key)
            for key in (
                "format",
                "fps",
                "image_size",
                "recording_mode",
                "root",
                "staging_root",
                "worker_python",
                "worker_pythons",
            )
        },
    }
