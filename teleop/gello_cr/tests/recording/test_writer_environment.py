"""Writer preparation happens before recording can start any motion."""

import subprocess
from pathlib import Path

import pytest

from teleop.gello_cr.recording.errors import WriterError
from teleop.gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from teleop.gello_cr.recording.writers.factory import WriterFactory


def factory(python, format_name=DatasetFormat.LEROBOT_V21, **kwargs):
    return WriterFactory(
        DatasetWriterConfig(format=format_name, worker_python=str(python)), **kwargs
    )


def test_missing_custom_interpreter_is_not_overwritten(tmp_path):
    python = tmp_path / "custom" / "python"
    with pytest.raises(WriterError) as exc:
        factory(python).prepare_environment()
    assert str(python) in str(exc.value)
    assert "setup_gello_writer_env.sh v21" in str(exc.value)
    assert not python.exists()


def test_default_v21_is_prepared_before_success_is_reported(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    monkeypatch.setattr(environment, "_repository_root", lambda: tmp_path)
    monkeypatch.setattr(environment.platform, "system", lambda: "Linux")
    monkeypatch.setattr(environment.shutil, "which", lambda tool: "/bin/" + tool)
    script = tmp_path / "scripts" / "setup_gello_writer_env.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/bash\n")
    python = tmp_path / "module" / "gello_writers" / "v21" / ".venv" / "bin" / "python"
    commands, events = [], []

    def run(command, **kwargs):
        commands.append(command)
        if command[-1] == "v21":
            assert command == ["/bin/bash", str(script), "v21"]
            python.parent.mkdir(parents=True)
            python.touch()
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(environment.subprocess, "run", run)
    monkeypatch.setattr(environment, "_install_default_v21", run)
    writer = factory(python)
    writer.prepare_environment(event_callback=lambda *event: events.append(event))
    writer.prepare_environment(event_callback=lambda *event: events.append(event))

    assert sum(command[-1] == "v21" for command in commands) == 1
    assert commands[1][0] == str(python)
    assert sum("首次准备" in event[1] for event in events) == 1
    assert "CPU" in events[0][1]


def test_existing_broken_interpreter_reports_diagnostics_without_install(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    python = tmp_path / "python"
    python.touch()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="No module named lerobot")

    monkeypatch.setattr(environment.subprocess, "run", run)
    with pytest.raises(WriterError, match="No module named lerobot"):
        factory(python).prepare_environment()
    assert len(commands) == 1 and commands[0][0] == str(python)


def test_v3_missing_environment_requires_explicit_source(tmp_path):
    with pytest.raises(WriterError) as exc:
        factory(tmp_path / "missing", DatasetFormat.LEROBOT_V3).prepare_environment()
    assert "GELLO_V3_LEROBOT_SPEC" in str(exc.value)
    assert "setup_gello_writer_env.sh v3" in str(exc.value)


def test_selected_format_uses_its_own_interpreter(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    python = tmp_path / "hdf5-python"
    python.touch()
    commands = []
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda command, **kwargs: (
            commands.append(command)
            or subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        ),
    )
    factory(
        tmp_path / "v21-missing",
        DatasetFormat.HDF5,
        worker_pythons={"hdf5": str(python)},
    ).prepare_environment()
    assert commands[0][0] == str(python)
    assert "h5py" in commands[0][-1]


def test_virtualenv_interpreter_entry_path_is_preserved(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    python = tmp_path / "venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    base = tmp_path / "system/python"
    commands = []
    original_resolve = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda path, *a, **kw: base if path == python else original_resolve(path, *a, **kw),
    )
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda command, **kwargs: (
            commands.append(command)
            or subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        ),
    )
    factory(python).prepare_environment()
    assert commands[0][0] == str(python)


def test_install_failure_exposes_reason_and_does_not_probe(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    monkeypatch.setattr(environment, "_repository_root", lambda: tmp_path)
    monkeypatch.setattr(environment.platform, "system", lambda: "Linux")
    monkeypatch.setattr(environment.shutil, "which", lambda tool: "/bin/" + tool)
    script = tmp_path / "scripts" / "setup_gello_writer_env.sh"
    script.parent.mkdir()
    script.touch()
    commands = []
    monkeypatch.setattr(
        environment,
        "_install_default_v21",
        lambda command, **kwargs: (
            commands.append(command)
            or subprocess.CompletedProcess(command, 1, stdout="", stderr="index unavailable")
        ),
    )
    python = tmp_path / "module/gello_writers/v21/.venv/bin/python"
    with pytest.raises(WriterError, match="index unavailable"):
        factory(python).prepare_environment()
    assert len(commands) == 1


def test_default_interpreter_is_not_auto_installed_on_windows(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    monkeypatch.setattr(environment, "_repository_root", lambda: tmp_path)
    monkeypatch.setattr(environment.platform, "system", lambda: "Windows")
    python = tmp_path / "module/gello_writers/v21/.venv/bin/python"
    with pytest.raises(WriterError, match="setup_gello_writer_env.sh v21"):
        factory(python).prepare_environment()
    assert not python.exists()


def test_existing_motion_may_check_but_never_install_environment(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.writers import environment

    monkeypatch.setattr(environment, "_repository_root", lambda: tmp_path)
    monkeypatch.setattr(environment.platform, "system", lambda: "Linux")
    monkeypatch.setattr(environment.shutil, "which", lambda tool: "/bin/" + tool)
    python = tmp_path / "module/gello_writers/v21/.venv/bin/python"
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *a, **kw: pytest.fail("must not install"),
    )
    with pytest.raises(WriterError, match="setup_gello_writer_env.sh v21"):
        factory(python).prepare_environment(allow_install=False)


def test_install_timeout_kills_and_reaps_process_group(monkeypatch, tmp_path):
    from teleop.gello_cr.recording.writers import environment

    calls = []

    class Process:
        pid = 123456
        returncode = -9

        def communicate(self, timeout=None):
            calls.append(("communicate", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired(["bash", "setup"], timeout)
            return "", ""

    def popen(command, **kwargs):
        assert kwargs["start_new_session"] is True
        return Process()

    monkeypatch.setattr(environment.subprocess, "Popen", popen)
    monkeypatch.setattr(environment.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(
        environment.os,
        "killpg",
        lambda pid, sig: calls.append(("killpg", pid, sig)),
        raising=False,
    )
    with pytest.raises(subprocess.TimeoutExpired):
        environment._install_default_v21(["bash", "setup"], cwd=tmp_path)
    assert calls[0] == ("communicate", 1800)
    assert calls[1] == ("killpg", 123456, environment.signal.SIGKILL)
    assert calls[2] == ("communicate", None)
