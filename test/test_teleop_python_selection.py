"""Launchers honor explicit Python choices and compatible active Conda."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") or "D:/Program Files/Git/bin/bash.exe"


def bash_path(path):
    value = str(path).replace("\\", "/")
    if len(value) > 2 and value[1] == ":":
        return "/" + value[0].lower() + value[2:]
    return value


@pytest.fixture
def workspace(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("teleop_python.sh", "run_nrc.sh", "run_teleop.sh", "run_gello_replay.sh"):
        source = ROOT / "scripts" / name
        if source.exists():
            shutil.copyfile(source, scripts / name)
    return tmp_path


def fake_python(root, *, compatible=True, venv=False, hardware_ready=True):
    python = root / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/usr/bin/env bash\n"
        + ("if [[ \"$*\" == *pymodbus* || \"$*\" == *pyrealsense2* ]]; then echo 'Missing Modbus or RealSense dependency' >&2; exit 1; fi\n" if not hardware_ready else "")
        + ("if [[ \"$*\" == *'import numpy'* ]]; then echo 'NumPy 2 is incompatible' >&2; exit 1; fi\n" if not compatible else "")
        +
        "if [[ \"$*\" == *sys.version_info* ]]; then echo 3.12; exit 0; fi\n"
        "if [[ \"$*\" == *LIBDIR* ]]; then exit 0; fi\n"
        + ("exit 0\n" if compatible else "echo 'NumPy 2 is incompatible' >&2; exit 1\n"),
        encoding="utf-8",
        newline="\n",
    )
    if venv:
        (root / "pyvenv.cfg").write_text("home = /python\n", encoding="utf-8")
    subprocess.run([BASH, "-c", 'chmod +x "$1"', "--", bash_path(python)], check=True)
    return python


def run_selection(workspace, **variables):
    env = os.environ.copy()
    for name in ("GELLO_CR_PYTHON", "NRC_PYTHON", "NRC_ENV", "CONDA_PREFIX", "VIRTUAL_ENV"):
        env.pop(name, None)
    env.update({key: bash_path(value) for key, value in variables.items()})
    return subprocess.run(
        [
            BASH, "-c",
            'source "$1/scripts/teleop_python.sh"; select_teleop_python "$1"; printf "%s" "$TELEOP_PYTHON"',
            "--", bash_path(workspace),
        ],
        capture_output=True, text=True, env=env,
    )


def test_compatible_active_conda_is_reused(workspace):
    candidate = fake_python(workspace / "conda")
    result = run_selection(workspace, CONDA_PREFIX=candidate.parent.parent)
    assert result.returncode == 0, result.stderr
    assert result.stdout == bash_path(candidate)


def test_incompatible_active_conda_falls_back_without_modifying_it(workspace):
    candidate = fake_python(workspace / "conda", compatible=False)
    result = run_selection(workspace, CONDA_PREFIX=candidate.parent.parent)
    assert result.returncode == 0, result.stderr
    assert result.stdout == bash_path(workspace / "module/nrc/.venv/bin/python")
    assert "Conda" in result.stderr and "NumPy" in result.stderr


def test_conda_without_hardware_transport_dependencies_falls_back(workspace):
    candidate = fake_python(workspace / "conda", hardware_ready=False)
    result = run_selection(workspace, CONDA_PREFIX=candidate.parent.parent)
    assert result.returncode == 0, result.stderr
    assert result.stdout == bash_path(workspace / "module/nrc/.venv/bin/python")
    assert "Modbus or RealSense" in result.stderr


@pytest.mark.parametrize("variable", ["GELLO_CR_PYTHON", "NRC_PYTHON", "NRC_ENV"])
def test_explicit_selection_takes_precedence_over_conda(workspace, variable):
    candidate = fake_python(workspace / "conda")
    explicit = workspace / "chosen"
    expected = explicit / "bin/python" if variable == "NRC_ENV" else explicit
    result = run_selection(workspace, CONDA_PREFIX=candidate.parent.parent, **{variable: explicit})
    assert result.returncode == 0, result.stderr
    assert result.stdout == bash_path(expected)


def test_no_active_conda_keeps_default_interpreter(workspace):
    result = run_selection(workspace)
    assert result.returncode == 0, result.stderr
    assert result.stdout == bash_path(workspace / "module/nrc/.venv/bin/python")


@pytest.mark.parametrize("venv", [False, True])
def test_nrc_launcher_reports_selected_virtual_environment(workspace, venv):
    candidate = fake_python(workspace / "chosen", venv=venv)
    env = os.environ.copy()
    env.update(NRC_PYTHON=bash_path(candidate), VIRTUAL_ENV="/stale/environment")
    result = subprocess.run(
        [BASH, bash_path(workspace / "scripts/run_nrc.sh"), BASH, "-c", 'printf "%s" "${VIRTUAL_ENV-unset}"'],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert bash_path(result.stdout) == (bash_path(candidate.parent.parent) if venv else "unset")


@pytest.mark.parametrize("script,args,installs", [
    ("run_teleop.sh", [], True),
    ("run_teleop.sh", ["--check-only"], False),
    ("run_teleop.sh", ["--help"], False),
    ("run_gello_replay.sh", ["trajectory.json"], False),
    ("run_gello_replay.sh", ["trajectory.json", "--execute"], True),
    ("run_gello_replay.sh", ["--execute", "--help"], False),
])
def test_default_setup_only_occurs_for_normal_or_execute_launch(workspace, script, args, installs):
    run_nrc = workspace / "scripts/run_nrc.sh"
    run_nrc.write_text('#!/usr/bin/env bash\nprintf "%s" "$NRC_PYTHON"\n', encoding="utf-8", newline="\n")
    setup = workspace / "scripts/setup_teleop_env.sh"
    setup.write_text('#!/usr/bin/env bash\ntouch "$(dirname "$0")/setup-called"\n', encoding="utf-8", newline="\n")
    subprocess.run([BASH, "-c", 'chmod +x "$1"/*.sh', "--", bash_path(workspace / "scripts")], check=True)
    env = os.environ.copy()
    for name in ("GELLO_CR_PYTHON", "NRC_PYTHON", "NRC_ENV", "CONDA_PREFIX"):
        env.pop(name, None)
    result = subprocess.run([BASH, bash_path(workspace / "scripts" / script), *args], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (workspace / "scripts/setup-called").exists() is installs
    assert bash_path(result.stdout) == bash_path(workspace / "module/nrc/.venv/bin/python")
