"""Reuse compatible active Conda packages without losing format isolation."""

import subprocess
import sys
from types import SimpleNamespace

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from teleop.gello_cr.recording.writers import environment
from teleop.gello_cr.recording.writers.factory import WriterFactory


def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(environment, "_repository_root", lambda: tmp_path)
    monkeypatch.setattr(environment.platform, "system", lambda: "Linux")
    prefix = tmp_path / "conda"
    conda = prefix / "bin/python"
    conda.parent.mkdir(parents=True)
    conda.touch()
    monkeypatch.setenv("CONDA_PREFIX", str(prefix))
    return conda, tmp_path / "module/gello_writers/v21/.venv/bin/python"


def test_compatible_conda_is_used_by_the_actual_writer_without_install(tmp_path, monkeypatch):
    conda, default = paths(tmp_path, monkeypatch)
    commands, events = [], []
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda cmd, **kw: commands.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""),
    )
    writer = WriterFactory(
        DatasetWriterConfig(DatasetFormat.LEROBOT_V21, worker_python=str(default))
    )
    writer.prepare_environment(allow_install=False, event_callback=lambda *e: events.append(e))
    assert writer().worker_python == str(conda)
    assert commands[0][0] == str(conda)
    assert any(str(conda) in e[1] for e in events)


def test_incompatible_conda_falls_back_to_configured_independent_environment(tmp_path, monkeypatch):
    conda, default = paths(tmp_path, monkeypatch)
    default.parent.mkdir(parents=True)
    default.touch()
    commands = []

    def run(cmd, **kw):
        commands.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 1 if cmd[0] == str(conda) else 0, "", "wrong LeRobot version"
        )

    monkeypatch.setattr(environment.subprocess, "run", run)
    writer = WriterFactory(
        DatasetWriterConfig(DatasetFormat.LEROBOT_V21, worker_python=str(default))
    )
    writer.prepare_environment(allow_install=False)
    assert [cmd[0] for cmd in commands] == [str(conda), str(default)]
    assert writer().worker_python == str(default)


def test_custom_configured_interpreter_has_priority_over_active_conda(tmp_path, monkeypatch):
    _, _ = paths(tmp_path, monkeypatch)
    custom = tmp_path / "explicit-python"
    custom.touch()
    commands = []
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda cmd, **kw: commands.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""),
    )
    environment.prepare_writer_environment("lerobot_v21", custom, allow_install=False)
    assert [cmd[0] for cmd in commands] == [str(custom)]


def test_explicitly_selected_conda_can_supply_writer_without_activation(tmp_path, monkeypatch):
    selected, default = paths(tmp_path, monkeypatch)
    prefix = selected.parent.parent
    (prefix / "conda-meta").mkdir()
    monkeypatch.delenv("CONDA_PREFIX")
    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.setattr(sys, "executable", str(selected))
    commands = []
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda cmd, **kw: commands.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""),
    )
    result = environment.prepare_writer_environment("lerobot_v21", default, allow_install=False)
    assert result == str(selected)
    assert commands[0][0] == str(selected)


def test_generic_override_replaces_selected_format_mapping_without_saving(tmp_path, monkeypatch):
    store = TeleopConfigStore(tmp_path / "config.json")
    old_v21, old_v3 = str(tmp_path / "old/v21"), str(tmp_path / "old/v3")
    store.data["dataset"].update(
        format="lerobot_v21", worker_pythons={"lerobot_v21": old_v21, "lerobot_v3": old_v3}
    )
    monkeypatch.setenv("GELLO_CR_DATA_PYTHON", str(tmp_path / "conda/bin/python"))
    effective = store.deployment_data()["dataset"]
    assert effective["worker_pythons"]["lerobot_v21"] == str(tmp_path / "conda/bin/python")
    assert effective["worker_pythons"]["lerobot_v3"] == old_v3
    assert store.data["dataset"]["worker_pythons"]["lerobot_v21"] == old_v21


def test_format_override_takes_priority_over_generic_override(tmp_path, monkeypatch):
    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["dataset"]["format"] = "lerobot_v21"
    monkeypatch.setenv("GELLO_CR_DATA_PYTHON", str(tmp_path / "generic"))
    monkeypatch.setenv("GELLO_CR_V21_PYTHON", str(tmp_path / "v21-python"))
    effective = store.deployment_data()["dataset"]
    assert effective["worker_pythons"]["lerobot_v21"] == str(tmp_path / "v21-python")


def test_batch_recovery_factory_uses_compatible_conda_after_restart(tmp_path, monkeypatch):
    from teleop.gello_cr.recording.batch import BatchManager

    conda, default = paths(tmp_path, monkeypatch)
    monkeypatch.setattr(
        environment.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", "")
    )
    manager = BatchManager.__new__(BatchManager)
    manager.writer_factory = WriterFactory(
        DatasetWriterConfig(DatasetFormat.LEROBOT_V21, worker_python=str(default))
    )
    manager._event = lambda *args: None
    recovered = manager._factory_for(
        SimpleNamespace(dataset_format="lerobot_v21", writer_options={})
    )
    assert recovered().worker_python == str(conda)
    assert manager.writer_factory.worker_pythons["lerobot_v21"] == str(conda)


def test_validation_uses_selected_conda_for_the_requested_format(tmp_path, monkeypatch):
    from teleop.gello_cr.recording import validation_service

    conda, default = paths(tmp_path, monkeypatch)
    monkeypatch.setattr(
        environment.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", "")
    )
    selected = []

    class Client:
        def __init__(self, python, script):
            selected.append(python)

        def request(self, *args, **kwargs):
            return {"validation": {"valid": True}}

        def close(self):
            pass

    monkeypatch.setattr(validation_service, "WorkerClient", Client)
    writer = WriterFactory(
        DatasetWriterConfig(DatasetFormat.LEROBOT_V21, worker_python=str(default))
    )
    assert validation_service.validate_in_worker("lerobot_v21", tmp_path, writer) == {"valid": True}
    assert selected == [str(conda)]
