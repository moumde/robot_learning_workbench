"""SDK loading tests use Python stand-ins, never the native hardware SDK."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from teleop.gello_cr.hardware.cr3a import Cr3aConfig, Cr3aDevice
from teleop.gello_cr.bootstrap.runtime_factory import Cr3aLifecycle, RuntimeFactoryPaths
from teleop.gello_cr.tests.v2.test_concrete_runtime_factory import CFG


@pytest.fixture(autouse=True)
def isolate_sdk(monkeypatch):
    monkeypatch.delenv('NRC_SDK_ROOT', raising=False)
    for name in ('nrc_interface', '_nrc_host'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield
    for name in ('nrc_interface', '_nrc_host'):
        sys.modules.pop(name, None)


@pytest.mark.parametrize('override', [False, True])
def test_config_and_environment_load_without_pythonpath(tmp_path, monkeypatch, override):
    (tmp_path / 'nrc_interface.py').write_text('marker = 42\n')
    if override:
        monkeypatch.setenv('NRC_SDK_ROOT', str(tmp_path))
    device = Cr3aDevice(Cr3aConfig(ip='unused', sdk_root='/missing' if override else str(tmp_path)))
    before = sys.path.copy()
    assert device._load_api().marker == 42
    assert sys.path == before
    assert device.session is None
    assert device.command_fd == device.servo_fd == -1


def test_repo_fallback_is_selected_without_native_import(monkeypatch):
    import teleop.gello_cr.hardware.cr3a as module
    from teleop.gello_cr.support.paths import workbench_root
    expected = workbench_root()
    def fake_import(name):
        assert name == 'vendor.nrc_interface.nrc_linux_x86_64.nrc_interface'
        assert Path(sys.path[0]) == expected
        return SimpleNamespace(marker=1)
    monkeypatch.setattr(module.importlib, 'import_module', fake_import)
    assert Cr3aDevice(Cr3aConfig(ip='unused'))._load_api().marker == 1


def test_invalid_explicit_root_does_not_fall_back(tmp_path):
    with pytest.raises(FileNotFoundError, match='NRC Python module missing'):
        Cr3aDevice(Cr3aConfig(ip='unused', sdk_root=str(tmp_path)))._load_api()


@pytest.mark.parametrize(('statement', 'message'), [
    ('import nonexistent_nrc_dependency', 'Python module lookup failed'),
    ('raise ImportError("libpython3.12.so.1.0 missing")', 'native SDK loading failed'),
    ('raise OSError("wrong ELF class")', 'native SDK loading failed'),
])
def test_loading_errors_keep_cause_and_restore_path(tmp_path, statement, message):
    (tmp_path / 'nrc_interface.py').write_text(statement)
    before = sys.path.copy()
    with pytest.raises(RuntimeError, match=message) as error:
        Cr3aDevice(Cr3aConfig(ip='unused', sdk_root=str(tmp_path)))._load_api()
    assert error.value.__cause__ is not None
    assert sys.path == before


def test_cached_other_sdk_rejected(tmp_path, monkeypatch):
    (tmp_path / 'nrc_interface.py').write_text('marker = 42')
    monkeypatch.setitem(sys.modules, '_nrc_host', SimpleNamespace(__file__='/other/_nrc_host.so'))
    with pytest.raises(RuntimeError, match='SDK conflict'):
        Cr3aDevice(Cr3aConfig(ip='unused', sdk_root=str(tmp_path)))._load_api()


def test_construction_does_not_load_sdk():
    def forbidden():
        raise AssertionError('SDK must not load before explicit connect')
    device = Cr3aDevice(Cr3aConfig(ip='unused'), api_loader=forbidden)
    assert not device.connected
    assert device.session is None


def test_factory_preserves_robot_sdk_root(tmp_path):
    lifecycle = Cr3aLifecycle(
        store=SimpleNamespace(deployment_data=lambda: {**CFG, 'robot': {**CFG['robot'], 'sdk_root': '/configured/sdk'}}),
        teleop_engine=None, paths=RuntimeFactoryPaths.from_repo(tmp_path),
    )
    assert lifecycle._robot_config().sdk_root == '/configured/sdk'
