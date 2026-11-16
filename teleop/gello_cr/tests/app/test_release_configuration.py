import copy
import json
import os
from pathlib import Path

import pytest

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.support.diagnostics import diagnostic_report


def test_deployment_paths_use_config_directory_without_persisting_overrides(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    store = TeleopConfigStore(config_dir / "workbench.json")
    store.data["dataset"].update(root="../dataset/train", staging_root="../dataset/staging")
    original = copy.deepcopy(store.data)
    monkeypatch.setenv("GELLO_CR_DATA_PYTHON", "/tmp/custom/python")
    effective = store.deployment_data()
    assert effective["dataset"]["root"] == str(tmp_path / "dataset/train")
    assert effective["dataset"]["staging_root"] == str(tmp_path / "dataset/staging")
    assert effective["dataset"]["worker_python"] == "/tmp/custom/python"
    assert store.data == original


@pytest.mark.parametrize("source", ["worker_python", "worker_pythons", "environment"])
@pytest.mark.parametrize("path_kind", ["relative", "home", "absolute"])
def test_deployment_preserves_virtualenv_python_symlink(tmp_path, monkeypatch, source, path_kind):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    system_python = tmp_path / "system-python"
    system_python.write_text("system interpreter", encoding="utf-8")
    venv_python = tmp_path / ".venv/bin/python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(system_python)
    paths = {
        "relative": "../.venv/bin/python",
        "home": "~/" + os.path.relpath(venv_python, Path.home()),
        "absolute": str(venv_python),
    }
    store = TeleopConfigStore(config_dir / "workbench.json")
    monkeypatch.delenv("GELLO_CR_DATA_PYTHON", raising=False)
    if source == "environment":
        monkeypatch.setenv("GELLO_CR_DATA_PYTHON", paths[path_kind])
    elif source == "worker_pythons":
        store.data["dataset"]["worker_pythons"] = {"hdf5": paths[path_kind]}
    else:
        store.data["dataset"]["worker_python"] = paths[path_kind]
    original = copy.deepcopy(store.data)

    dataset = store.deployment_data()["dataset"]

    configured_python = (
        dataset["worker_pythons"]["hdf5"] if source == "worker_pythons" else dataset["worker_python"]
    )
    assert configured_python == str(venv_python)
    assert store.data == original


@pytest.mark.parametrize(
    "changes",
    [
        {"hardware": {"profile": "unknown"}},
        {"dataset": {"camera_poll_hz": 0}},
        {"ui": {"refresh_ms": 0}},
    ],
)
def test_invalid_release_configuration_rejected(tmp_path, changes):
    store = TeleopConfigStore(tmp_path / "workbench.json")
    for group, values in changes.items():
        store.data[group].update(values)
    with pytest.raises(ValueError):
        store.save()


def test_diagnostics_are_read_only_and_do_not_connect_hardware(tmp_path):
    store = TeleopConfigStore(tmp_path / "workbench.json")
    report = diagnostic_report(store.data, tmp_path)
    assert report["version"] == "1.0.0"
    assert report["git_commit"] == "unknown"
    assert report["hardware_profile"] == "cr3a_o6"
    assert report["dataset"]["format"] == store.data["dataset"]["format"]
    assert report["connected_devices"] == {}


@pytest.mark.parametrize(
    "group, field",
    [
        ("gello", "feedback_hz"),
        ("inverse3", "feedback_hz"),
        ("roarm", "feedback_hz"),
        ("teleop", "period_s"),
        ("robot", "movej_period_s"),
    ],
)
@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_feedback_rates_and_control_periods_rejected_on_load(
    tmp_path, group, field, value
):
    config = tmp_path / "workbench.json"
    config.write_text(json.dumps({group: {field: value}}), encoding="utf-8")

    with pytest.raises(ValueError):
        TeleopConfigStore.from_file(config)
