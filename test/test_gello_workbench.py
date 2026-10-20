"""Parent-workbench ownership of GELLO runtime paths and hardware settings."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workbench(tmp_path):
    root = tmp_path / "workbench"
    profile = root / "config/hardware/cr3_o6.toml"
    profile.parent.mkdir(parents=True)
    (root / "config/hardware.py").touch()
    (root / "vendor/nrc_interface").mkdir(parents=True)
    profile.write_text(
        (ROOT / "config/hardware/cr3_o6.toml").read_text()
        .replace('192.168.2.14', '192.0.2.14')
        .replace('teach = 6001', 'teach = 6101')
        .replace('track = 7000', 'track = 7100')
        .replace('"/dev/ttyUSB0"', '"/dev/o6-test"')
        .replace('output_width = 224', 'output_width = 320')
        .replace('output_height = 224', 'output_height = 240')
    )
    config = root / "config/teleop/gello_cr.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({
        "workbench": {"hardware_config": "../hardware/cr3_o6.toml"},
        "gello": {"joint_offsets": [1, 2, 3, 4, 5, 6]},
        "robot": {"ip": "stale-ip", "safety_max_command_speed_rad_s": 0.7},
        "dataset": {"root": "../../dataset/train", "task": "keep the task"},
        "trajectory": {"root": "../../dataset/replay/trajectories"},
        "presets": {"HOME": {"robot_joints_deg": [1] * 7}},
    }))
    return root, config, profile


def test_profile_overrides_physical_settings_and_preserves_calibration(workbench, monkeypatch):
    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    monkeypatch.chdir("/tmp")
    store = IntegratedConfigStore(config, repo_root=root)

    assert store.hardware_profile_path == profile
    assert store.data["hardware"]["name"] == "cr3 + right_o6 (cr3_o6)"
    assert store.data["robot"]["ip"] == "192.0.2.14"
    assert store.data["robot"]["command_port"] == 6101
    assert store.data["robot"]["servo_port"] == 7100
    assert store.data["robot"]["servoj_vmax"] == [500.0] * 7
    assert store.data["robot"]["servoj_amax"] == [500.0] * 7
    assert store.data["robot"]["servoj_jmax"] == [500.0] * 7
    assert store.data["o6"]["port"] == "/dev/o6-test"
    assert store.data["dataset"]["image_size"] == [240, 320]
    assert [store.data["dataset"][key] for key in (
        "camera_width", "camera_height", "camera_fps"
    )] == [640, 480, 30]
    assert store.data["dataset"]["camera_streams"] == [
        {"name": "base_0_rgb", "serial": "254622075848", "mode": "camera", "roi_norm": [0, 0, 1, 1]},
        {"name": "left_wrist_0_rgb", "serial": "317222074617", "mode": "camera", "roi_norm": [0, 0, 1, 1]},
        {"name": "right_wrist_0_rgb", "serial": "262422074985", "mode": "camera", "roi_norm": [0, 0, 1, 1]},
    ]
    assert store.data["gello"]["joint_offsets"] == [1, 2, 3, 4, 5, 6]
    assert store.data["robot"]["safety_max_command_speed_rad_s"] == 0.7
    assert store.data["dataset"]["task"] == "keep the task"
    assert store.data["presets"]["HOME"]["robot_joints_deg"] == [1] * 7
    assert store.deployment_data()["dataset"]["root"] == str(root / "dataset/train")
    assert store.deployment_data()["gello"]["software_root"] == str(root / "vendor/gello")
    assert store.deployment_data()["robot"]["sdk_root"] == str(root / "vendor/nrc_interface/nrc_linux_x86_64")


@pytest.mark.parametrize("field,value", [
    ("robot.ip", "192.0.2.99"),
    ("robot.servoj_vmax", [1.0] * 7),
    ("o6.port", "/dev/unowned"),
    ("dataset.camera_streams.2.serial", "unowned-camera"),
    ("dataset.image_size", [480, 640]),
    ("hardware.name", "unowned profile name"),
])
def test_save_rejects_hardware_owned_edits(workbench, field, value):
    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    original = config.read_bytes()
    store = IntegratedConfigStore(config, repo_root=root)
    data = store.data
    keys = field.split(".")
    for key in keys[:-1]:
        data = data[int(key)] if isinstance(data, list) else data[key]
    data[keys[-1]] = value
    with pytest.raises(ValueError, match="只读|read.only"):
        store.save()
    assert config.read_bytes() == original


def test_save_keeps_json_portable_without_hardware_snapshots(workbench, monkeypatch):
    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    original_profile = profile.read_bytes()
    monkeypatch.setenv("GELLO_CR_DATA_PYTHON", "/tmp/environment-python")
    store = IntegratedConfigStore(config, repo_root=root)
    store.data["dataset"]["task"] = "edited task"
    store.data["dataset"]["root"] = str(root / "dataset/new train")
    store.save()

    saved = json.loads(config.read_text())
    assert profile.read_bytes() == original_profile
    assert saved["dataset"]["task"] == "edited task"
    assert saved["dataset"]["root"] == "../../dataset/new train"
    assert saved["gello"]["software_root"] == "../../vendor/gello"
    assert "sdk_root" not in saved["robot"]
    assert "ip" not in saved["robot"]
    assert "servoj_vmax" not in saved["robot"]
    assert "port" not in saved["o6"]
    assert "camera_streams" not in saved["dataset"]
    assert "image_size" not in saved["dataset"]
    assert "camera_width" not in saved["dataset"]
    assert "name" not in saved["hardware"]
    assert saved["workbench"]["hardware_config"] == "../hardware/cr3_o6.toml"
    assert "/tmp/" not in saved["gello"]["kinematics_urdf"]
    assert saved["dataset"]["worker_python"] != "/tmp/environment-python"
    reloaded = IntegratedConfigStore(config, repo_root=root)
    assert reloaded.data["dataset"]["task"] == "edited task"
    assert reloaded.data["dataset"]["image_size"] == [240, 320]


@pytest.mark.parametrize("old,new", [
    ('transport = "rs485"', 'transport = "can"'),
    ('model = "O6"', 'model = "O7"'),
    ('joint_count = 6', 'joint_count = 7'),
])
def test_rejects_hardware_profiles_the_o6_adapter_cannot_use(workbench, old, new):
    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    profile.write_text(profile.read_text().replace(old, new))
    with pytest.raises(ValueError, match="O6.*RS485|RS485.*O6"):
        IntegratedConfigStore(config, repo_root=root)


def test_explicit_hardware_profile_is_relative_to_parent_root(workbench, monkeypatch):
    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    override = root / "config/hardware/other.toml"
    override.write_text(profile.read_text().replace("192.0.2.14", "192.0.2.20"))
    monkeypatch.chdir("/tmp")
    store = IntegratedConfigStore(config, repo_root=root, hardware_config="config/hardware/other.toml")
    assert store.hardware_profile_path == override
    assert store.data["robot"]["ip"] == "192.0.2.20"
    store.save()
    assert json.loads(config.read_text())["workbench"]["hardware_config"] == "../hardware/cr3_o6.toml"


def test_save_makes_a_repo_local_hardware_reference_portable(workbench):
    from core.workbench.app.settings import OperatorSettings

    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    data = json.loads(config.read_text())
    data["workbench"]["hardware_config"] = str(profile)
    config.write_text(json.dumps(data))
    settings = OperatorSettings(config, lambda path: IntegratedConfigStore(path, repo_root=root))
    settings.save(settings.data)
    settings.data["dataset"]["task"] = "second save"
    settings.save(settings.data)
    assert json.loads(config.read_text())["workbench"]["hardware_config"] == "../hardware/cr3_o6.toml"
    assert json.loads(config.read_text())["dataset"]["task"] == "second save"


def test_factory_guards_each_robot_with_its_actual_profile_endpoint(workbench, monkeypatch):
    from core.hardware.cr3a import Cr3aConfig

    from core.hardware_session import RobotSessionBusyError
    from core.workbench.composition import WorkbenchRuntimeFactory, workbench_paths

    root, config, profile = workbench
    factory = WorkbenchRuntimeFactory(workbench_paths(root))
    store = factory.constructors.TeleopConfigStore(config)
    cfg = store.data["robot"]
    robot_config = Cr3aConfig(
        ip=cfg["ip"], command_port=cfg["command_port"], servo_port=cfg["servo_port"]
    )
    first = factory.constructors.Cr3aDevice(robot_config)
    second = factory.constructors.Cr3aDevice(robot_config)
    assert first._session_guard is not second._session_guard
    try:
        first._session_guard.acquire()
        with pytest.raises(RobotSessionBusyError, match="192.0.2.14:6101/7100"):
            second._session_guard.acquire()
    finally:
        first._session_guard.release()
    second._session_guard.acquire()
    second._session_guard.release()


def test_collection_ui_entry_uses_parent_profile(workbench, monkeypatch):
    from core.workbench.bootstrap.runtime_factory import ConcreteRuntimeFactory
    from hmi.collection.__main__ import main

    root, config, profile = workbench
    built = []
    real_build = ConcreteRuntimeFactory.build

    def capture_build(factory):
        runtime = real_build(factory)
        built.append(runtime)
        return runtime

    monkeypatch.setattr(ConcreteRuntimeFactory, "build", capture_build)
    monkeypatch.chdir("/tmp")
    assert main(["--repo-root", str(root), "--check-only"]) == 0
    assert built[0].store.data["robot"]["ip"] == "192.0.2.14"
    assert built[0].store.hardware_profile_path == profile
    assert built[0].cr3a_lifecycle.device is None


def test_replay_entry_uses_parent_factory_only_for_execution(workbench, monkeypatch, capsys):
    from core.workbench.bootstrap.runtime_factory import ConcreteRuntimeFactory, RuntimeFactoryPaths
    from core.workbench import replay
    from core.workbench.cli import replay_trajectory as cli

    root, config, profile = workbench
    trajectory = root / "trajectory.json"
    trajectory.write_text(json.dumps({
        "version": 3, "recorded_at": "2026-10-17", "sample_period_s": 0.05,
        "frames": [{"t": 0, "robot_joints_deg": [0] * 7}],
    }))
    built = []

    def execute_without_hardware(args, value, options, runtime_factory):
        paths = RuntimeFactoryPaths.from_repo(args.repo_root, config_path=args.config)
        runtime = (runtime_factory or ConcreteRuntimeFactory)(paths).build()
        try:
            built.append(runtime)
        finally:
            runtime.close()

    monkeypatch.setattr(cli, "_execute", execute_without_hardware)
    monkeypatch.chdir("/tmp")
    assert replay.main([str(trajectory), "--repo-root", str(root)]) == 0
    assert built == []
    assert "frame_count" in capsys.readouterr().out
    assert replay.main([str(trajectory), "--repo-root", str(root), "--execute", "--arm-only"]) == 0
    assert built[0].store.data["robot"]["ip"] == "192.0.2.14"
    assert built[0].store.hardware_profile_path == profile


@pytest.mark.parametrize("module,arguments,expected", [
    ("hmi.collection", ["--check-only"], "hardware_connections=not_started"),
    ("core.workbench.replay", [], '"frame_count": 1'),
])
def test_parent_entries_run_from_an_unrelated_working_directory(
    tmp_path, module, arguments, expected,
):
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(json.dumps({
        "version": 3, "frames": [{"t": 0, "robot_joints_deg": [0] * 7}],
    }))
    if module == "core.workbench.replay":
        arguments = [str(trajectory), *arguments]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout



def test_left_hand_uses_shared_profile_address_and_cannot_persist_an_override(workbench):
    from core.workbench.composition import IntegratedConfigStore

    root, config, profile = workbench
    profile.write_text(profile.read_text().replace('side = "right"', 'side = "left"'))
    store = IntegratedConfigStore(config, repo_root=root)
    assert store.deployment_data()["o6"]["hand_id"] == 0x28
    store.save()
    assert "hand_id" not in json.loads(config.read_text())["o6"]
    store.data["o6"]["hand_id"] = 0x27
    with pytest.raises(ValueError, match="只读"):
        store.save()
