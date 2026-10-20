"""Compose GELLO with the parent workbench's paths and hardware ownership."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from config.hardware import HardwareConfigError, load_hardware_config
from core.hardware_session import RobotSessionLock
from core.workbench.app.config_store import DEFAULT_CONFIG, TeleopConfigStore, _deep_merge
from core.workbench.bootstrap.runtime_factory import (
    ConcreteRuntimeFactory,
    RuntimeConstructors,
    RuntimeFactoryPaths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HARDWARE_CONFIG = "../hardware/cr3_o6.toml"
_PROFILE_FIELDS = frozenset({
    "hardware.name",
    "robot.ip", "robot.command_port", "robot.servo_port",
    "robot.servoj_vmax", "robot.servoj_amax", "robot.servoj_jmax",
    "o6.port", "o6.hand_id", "o6.baudrate", "dataset.camera_streams", "dataset.base_camera_serial",
    "dataset.wrist_camera_serial", "dataset.image_size", "dataset.camera_width",
    "dataset.camera_height", "dataset.camera_fps",
})
_PATH_FIELDS = (
    ("dataset", "root"), ("dataset", "staging_root"),
    ("dataset", "worker_python"), ("trajectory", "root"),
    ("gello", "software_root"), ("gello", "kinematics_urdf"),
    ("workbench", "hardware_config"),
)


def _from_root(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def workbench_paths(
    root: str | Path, config_path: str | Path | None = None,
) -> RuntimeFactoryPaths:
    """Resolve integrated paths independently of the process working directory."""
    root = Path(root).expanduser().resolve()
    return RuntimeFactoryPaths(
        repo_root=root,
        config_path=_from_root(root, config_path or "config/teleop/gello_cr.json"),
        linker_hand_sdk_root=root / "vendor/actuator/linkerhand-python-sdk/LinkerHand",
        nrc_sdk_root=root / "vendor/nrc_interface/nrc_linux_x86_64",
    )


class IntegratedConfigStore(TeleopConfigStore):
    """Keep calibrated JSON settings separate from shared physical configuration."""

    read_only_paths = _PROFILE_FIELDS | frozenset({
        "workbench.hardware_config", "robot.sdk_root", "gello.software_root",
    })

    def __init__(
        self, path: str | Path, *, repo_root: str | Path | None = None,
        hardware_config: str | Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root or REPO_ROOT).expanduser().resolve()
        self._hardware_override = hardware_config
        super().__init__(_from_root(self.repo_root, path))

    @classmethod
    def from_file(cls, path: str | Path, **kwargs: Any) -> IntegratedConfigStore:
        root = Path(kwargs.get("repo_root") or REPO_ROOT).expanduser().resolve()
        if not _from_root(root, path).is_file():
            raise FileNotFoundError(f"Workbench config missing: {_from_root(root, path)}")
        return cls(path, **kwargs)

    def _relative(self, path: Path) -> str:
        return os.path.relpath(path, self.path.parent)

    def load(self) -> dict[str, Any]:
        with self._lock:
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"读取遥操作配置失败: {self.path}: {exc}") from exc
            data = _deep_merge(DEFAULT_CONFIG, loaded)
            if "actions" in loaded.get("o6", {}):
                data["o6"]["actions"] = copy.deepcopy(loaded["o6"]["actions"])
            configured = data.setdefault("workbench", {}).setdefault(
                "hardware_config", DEFAULT_HARDWARE_CONFIG,
            )
            profile_path = (
                _from_root(self.repo_root, self._hardware_override)
                if self._hardware_override is not None else self.resolve_path(configured)
            )
            data["workbench"]["hardware_config"] = self._portable_path(configured)
            hardware = load_hardware_config(profile_path)
            hand = hardware.hand
            if (
                hand.model.upper() != "O6" or hand.transport != "rs485"
                or hand.joint_count != 6 or (hand.state_min, hand.state_max) != (0, 255)
            ):
                raise HardwareConfigError(
                    f"GELLO supports only O6 RS485 with 6 joints and state range 0..255: {hardware.source}"
                )
            self.hardware_profile_path = hardware.source
            nrc, cameras = hardware.nrc, hardware.d435
            data["hardware"]["name"] = f"{nrc.name} + {hand.name} ({hardware.source.stem})"
            data["robot"].update(
                ip=nrc.ip, command_port=nrc.ports.teach, servo_port=nrc.ports.track,
                servoj_vmax=list(nrc.servoj_vmax), servoj_amax=list(nrc.servoj_amax),
                servoj_jmax=list(nrc.servoj_jmax),
                sdk_root=self._relative(self.repo_root / "vendor/nrc_interface/nrc_linux_x86_64"),
            )
            data["o6"].update(
                port=hand.modbus, hand_id=0x28 if hand.side == "left" else 0x27,
                baudrate=115200,  # Shared LinkerHandApi uses this O6 RS485 speed.
            )
            data["dataset"].update(
                camera_streams=[{
                    "name": device.name, "serial": device.serial, "mode": "camera",
                    "roi_norm": [0.0, 0.0, 1.0, 1.0],
                } for device in cameras.devices],
                base_camera_serial=cameras.camera_serials["base_0_rgb"],
                wrist_camera_serial=cameras.camera_serials["left_wrist_0_rgb"],
                image_size=[cameras.output_height, cameras.output_width],
                camera_width=cameras.width, camera_height=cameras.height, camera_fps=cameras.fps,
            )
            gello_root = self.repo_root / "vendor/gello"
            data["gello"]["software_root"] = self._relative(gello_root)
            if "kinematics_urdf" not in loaded.get("gello", {}):
                data["gello"]["kinematics_urdf"] = self._relative(
                    gello_root / "gello/factr/urdf/yam_active_gello/robot.urdf",
                )
            self._validate(data)
            self._read_only_values = {
                path: copy.deepcopy(self._value(data, path)) for path in self.read_only_paths
            }
            return data

    @staticmethod
    def _value(data: dict, path: str) -> Any:
        for key in path.split("."):
            data = data[key]
        return data

    def _portable_path(self, value: str | Path) -> str:
        path = Path(value).expanduser()
        if path.is_absolute() and path.resolve().is_relative_to(self.repo_root):
            return self._relative(path.resolve())
        return str(value)

    def save(self) -> None:
        with self._lock:
            for path, original in self._read_only_values.items():
                try:
                    unchanged = self._value(self.data, path) == original
                except (KeyError, TypeError):
                    unchanged = False
                if not unchanged:
                    raise ValueError(f"{path} 由硬件配置提供（只读）：{self.hardware_profile_path}")
            self._validate(self.data)
            saved = copy.deepcopy(self.data)
            for path in _PROFILE_FIELDS | {"robot.sdk_root", "o6.sdk_root", "dataset.base_roi_norm"}:
                group, key = path.split(".")
                saved[group].pop(key, None)
            for group, key in _PATH_FIELDS:
                if saved[group].get(key):
                    saved[group][key] = self._portable_path(saved[group][key])
            saved["dataset"]["worker_pythons"] = {
                key: self._portable_path(value)
                for key, value in saved["dataset"].get("worker_pythons", {}).items()
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            temp_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temp_path, self.path)

    def deployment_data(self) -> dict[str, Any]:
        data = super().deployment_data()
        data["robot"]["sdk_root"] = str(self.repo_root / "vendor/nrc_interface/nrc_linux_x86_64")
        data["gello"]["software_root"] = str(self.repo_root / "vendor/gello")
        return data


class WorkbenchRuntimeFactory(ConcreteRuntimeFactory):
    """Use parent SDKs and acquire endpoint ownership only when a device connects."""

    def __init__(
        self, paths: RuntimeFactoryPaths, hardware_config: str | Path | None = None,
        *, event_callback=None, constructors: RuntimeConstructors | None = None,
    ) -> None:
        constructors = constructors or RuntimeConstructors.load_defaults()
        device_constructor = constructors.Cr3aDevice

        def guarded_device(config, **kwargs):
            kwargs["session_guard"] = RobotSessionLock(
                config.ip, config.command_port, config.servo_port,
            )
            return device_constructor(config, **kwargs)

        super().__init__(
            paths,
            constructors=replace(
                constructors,
                TeleopConfigStore=partial(
                    IntegratedConfigStore.from_file, repo_root=paths.repo_root,
                    hardware_config=hardware_config,
                ),
                Cr3aDevice=guarded_device,
            ),
            event_callback=event_callback,
        )
