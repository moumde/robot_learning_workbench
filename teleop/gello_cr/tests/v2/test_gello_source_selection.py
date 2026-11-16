"""Configured vendor sources must win over environment-installed GELLO."""

import importlib
import sys
from types import ModuleType

import pytest

from teleop.gello_cr.devices.gello import GelloConfig, GelloDevice


@pytest.fixture
def clean_gello_imports(monkeypatch):
    saved = {
        name: value
        for name, value in sys.modules.items()
        if name == "gello" or name.startswith("gello.")
    }
    for name in saved:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in list(sys.modules):
        if name == "gello" or name.startswith("gello."):
            sys.modules.pop(name)
    sys.modules.update(saved)


def package(root, marker):
    target = root / "gello" / "robots"
    target.mkdir(parents=True)
    (root / "gello" / "__init__.py").write_text("", encoding="utf-8")
    (target / "__init__.py").write_text("", encoding="utf-8")
    (target / "dynamixel.py").write_text(
        "class DynamixelRobot:\n"
        f"    marker = {marker!r}\n"
        "    def get_joint_state_sample(self): pass\n",
        encoding="utf-8",
    )
    return root


def device(root):
    return GelloDevice(
        GelloConfig(
            port="fake",
            joint_ids=(1, 2, 3, 4, 5, 6),
            joint_offsets=(0,) * 6,
            joint_signs=(1,) * 6,
            gripper_config=(7, 0, 90),
            software_root=str(root) if root else None,
        )
    )


def test_configured_source_takes_priority_even_if_already_later_in_path(
    tmp_path, clean_gello_imports
):
    vendor = package(tmp_path / "vendor", "vendor")
    installed = package(tmp_path / "conda", "conda")
    sys.path[:0] = [str(installed), str(vendor)]
    assert device(vendor)._load_robot_factory().marker == "vendor"


def test_cached_external_package_is_rejected_without_reloading(tmp_path, clean_gello_imports):
    vendor = package(tmp_path / "vendor", "vendor")
    installed = package(tmp_path / "conda", "conda")
    sys.path.insert(0, str(installed))
    old = importlib.import_module("gello.robots.dynamixel")
    with pytest.raises(RuntimeError, match="GELLO.*来源") as exc:
        device(vendor)._load_robot_factory()
    assert str(installed) in str(exc.value)
    assert sys.modules[old.__name__] is old


def test_cached_external_submodule_is_rejected_even_with_vendor_parent(
    tmp_path, clean_gello_imports
):
    vendor = package(tmp_path / "vendor", "vendor")
    sys.path.insert(0, str(vendor))
    importlib.import_module("gello")
    external = ModuleType("gello.dynamixel.driver")
    external.__file__ = str(tmp_path / "conda" / "gello" / "dynamixel" / "driver.py")
    sys.modules[external.__name__] = external
    with pytest.raises(RuntimeError, match="GELLO.*来源"):
        device(vendor)._load_robot_factory()
    assert sys.modules[external.__name__] is external


def test_no_configured_source_retains_installed_package_support(tmp_path, clean_gello_imports):
    installed = package(tmp_path / "conda", "conda")
    sys.path.insert(0, str(installed))
    assert device(None)._load_robot_factory().marker == "conda"
