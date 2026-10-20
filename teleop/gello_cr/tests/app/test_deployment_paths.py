from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6 import QtWidgets

from gello_cr.app.config_store import TeleopConfigStore
from gello_cr.bootstrap.runtime_factory import Cr3aLifecycle, RuntimeFactoryPaths
from gello_cr.core.state_machine import WorkflowState
from gello_cr.ui import __main__ as entrypoint
from gello_cr.ui import session


@pytest.mark.parametrize("edit_root", [False, True], ids=["display", "save"])
def test_collection_root_uses_config_directory_from_another_cwd(tmp_path, monkeypatch, edit_root):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    store = TeleopConfigStore(config_dir / "workbench.json")
    store.save()
    elsewhere = tmp_path / "launch" / "nested"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtWidgets.QMainWindow()
    window.collection = SimpleNamespace(
        task_edit=QtWidgets.QLineEdit(window),
        description_edit=QtWidgets.QLineEdit(window),
        root_edit=QtWidgets.QLineEdit(window),
    )
    operator = SimpleNamespace(
        runtime=SimpleNamespace(store=store),
        backend=SimpleNamespace(service=SimpleNamespace(state=WorkflowState.OFFLINE)),
        cameras=SimpleNamespace(running=False),
        close=lambda: None,
    )
    monkeypatch.setattr(entrypoint, "build_operator_application", lambda root: operator)
    monkeypatch.setattr(session, "create_operator_window", lambda *a, **kw: window)
    monkeypatch.setattr(QtWidgets, "QApplication", lambda argv: app)

    def interact():
        if edit_root:
            window.collection.root_edit.setText("../dataset/selected")
            window.collection.root_edit.editingFinished.emit()
            expected = str(tmp_path / "dataset/selected")
            saved = TeleopConfigStore.from_file(store.path)
            assert saved.data["dataset"]["root"] == expected
        else:
            expected = str(tmp_path / "dataset/train")
        assert window.collection.root_edit.text() == expected
        return 0

    monkeypatch.setattr(app, "exec", interact)
    try:
        assert entrypoint.main(["--repo-root", str(tmp_path)], application_factory=lambda root: operator) == 0
    finally:
        app.aboutToQuit.disconnect(operator.close)
        window.close()


def test_check_only_uses_injected_application_factory_and_closes_without_gui(tmp_path, capsys):
    closed, roots = [], []
    operator = SimpleNamespace(
        runtime=SimpleNamespace(
            store=SimpleNamespace(data={"logging": {"level": "INFO"}, "master": {"type": "gello"}})
        ),
        backend=SimpleNamespace(service=SimpleNamespace(state=WorkflowState.OFFLINE)),
        cameras=SimpleNamespace(running=False),
        close=lambda: closed.append(True),
    )

    assert (
        entrypoint.main(
            ["--repo-root", str(tmp_path), "--check-only"],
            application_factory=lambda root: roots.append(root) or operator,
        )
        == 0
    )
    assert roots == [tmp_path]
    assert closed == [True]
    assert "hardware_connections=not_started" in capsys.readouterr().out


def test_cr3a_sdk_root_uses_config_directory_from_another_cwd(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    store = TeleopConfigStore(config_dir / "workbench.json")
    store.data["robot"]["sdk_root"] = "../vendor/custom-nrc"
    elsewhere = tmp_path / "launch" / "nested"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)
    lifecycle = Cr3aLifecycle(
        store=store,
        teleop_engine=None,
        paths=RuntimeFactoryPaths.from_repo(tmp_path),
    )

    assert lifecycle._robot_config().sdk_root == str(tmp_path / "vendor/custom-nrc")
    assert store.data["robot"]["sdk_root"] == "../vendor/custom-nrc"


def test_injected_factories_preserve_selected_profile_for_settings_and_dataset_root(
    tmp_path, monkeypatch
):
    from gello_cr.app.settings import OperatorSettings

    config = tmp_path / "config" / "teleop.json"
    config.parent.mkdir()
    running = TeleopConfigStore(config)
    running.save()
    profile = tmp_path / "selected-hardware.toml"
    profile.write_text('[robot]\nip = "10.0.0.8"\n')
    calls, captured = [], {}

    def store_factory(path):
        calls.append(Path(path))
        store = TeleopConfigStore(path)
        store.data["robot"]["ip"] = "10.0.0.8"
        store.read_only_paths = {"robot.ip"}
        store.hardware_profile_path = profile
        return store

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtWidgets.QMainWindow()
    window.collection = SimpleNamespace(
        task_edit=QtWidgets.QLineEdit(window),
        description_edit=QtWidgets.QLineEdit(window),
        root_edit=QtWidgets.QLineEdit(window),
    )
    operator = SimpleNamespace(
        runtime=SimpleNamespace(store=running),
        backend=SimpleNamespace(service=SimpleNamespace(state=WorkflowState.OFFLINE)),
        cameras=SimpleNamespace(running=False),
        close=lambda: None,
    )

    def create_window(*args, **kwargs):
        captured.update(kwargs)
        return window

    def default_factory_is_not_used(root):
        raise AssertionError("the injected application factory must be used")

    monkeypatch.setattr(entrypoint, "build_operator_application", default_factory_is_not_used)
    monkeypatch.setattr(session, "create_operator_window", create_window)
    monkeypatch.setattr(QtWidgets, "QApplication", lambda argv: app)

    def interact():
        draft = captured["settings_factory"]()
        assert isinstance(draft, OperatorSettings)
        assert draft.hardware_profile_path == profile
        assert draft.data["robot"]["ip"] == "10.0.0.8"
        calls.clear()
        window.collection.root_edit.setText("../dataset/selected")
        window.collection.root_edit.editingFinished.emit()
        assert calls and all(path == config for path in calls)
        assert TeleopConfigStore(config).data["dataset"]["root"] == str(
            tmp_path / "dataset/selected"
        )
        assert captured["settings_factory"]().hardware_profile_path == profile
        return 0

    roots = []
    monkeypatch.setattr(app, "exec", interact)
    try:
        assert (
            entrypoint.main(
                ["--repo-root", str(tmp_path)],
                application_factory=lambda root: roots.append(root) or operator,
                settings_store_factory=store_factory,
            )
            == 0
        )
        assert roots == [tmp_path]
    finally:
        app.aboutToQuit.disconnect(operator.close)
        window.close()
