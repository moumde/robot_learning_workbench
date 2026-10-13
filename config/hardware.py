"""Load and materialize the workbench hardware configuration.

The TOML file is intentionally independent from any vendor SDK. The factory
methods import vendor adapters lazily, so programs that only inspect or edit
configuration do not need camera or robot shared-library dependencies loaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - project Python is >= 3.11
    raise RuntimeError("Hardware configuration requires Python 3.11 or newer") from exc


DEFAULT_CONFIG_PATH = Path(__file__).with_name("hardware") / "cr3_o6.toml"
D435_CAMERA_NAMES = (
    "base_0_rgb",
    "left_wrist_0_rgb",
    "right_wrist_0_rgb",
)


class HardwareConfigError(ValueError):
    """Raised when the hardware TOML is missing or invalid."""


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HardwareConfigError(f"{name} must be a TOML table")
    return value


def _string(table: Mapping[str, Any], key: str, name: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HardwareConfigError(f"{name}.{key} must be a non-empty string")
    return value.strip()


def _optional_string(
    table: Mapping[str, Any], key: str, default: str, name: str
) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise HardwareConfigError(f"{name}.{key} must be a non-empty string")
    return value.strip()


def _positive_int(table: Mapping[str, Any], key: str, name: str) -> int:
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HardwareConfigError(f"{name}.{key} must be a positive integer")
    return value


def _int(table: Mapping[str, Any], key: str, default: int, name: str) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HardwareConfigError(f"{name}.{key} must be an integer")
    return value


def _positive_float(table: Mapping[str, Any], key: str, name: str) -> float:
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise HardwareConfigError(f"{name}.{key} must be a positive number")
    return float(value)


def _boolean(table: Mapping[str, Any], key: str, default: bool, name: str) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise HardwareConfigError(f"{name}.{key} must be a boolean")
    return value


def _vector7(table: Mapping[str, Any], key: str, name: str) -> tuple[float, ...]:
    value = table.get(key)
    if not isinstance(value, list) or len(value) != 7:
        raise HardwareConfigError(f"{name}.{key} must contain exactly 7 numbers")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise HardwareConfigError(f"{name}.{key} must contain numbers") from exc
    if any(item <= 0 for item in result):
        raise HardwareConfigError(f"{name}.{key} must contain positive numbers")
    return result


@dataclass(frozen=True)
class NrcPorts:
    control: int
    teach: int
    track: int


@dataclass(frozen=True)
class NrcConfig:
    name: str
    ip: str
    ports: NrcPorts
    connect_control: bool
    connection_timeout: float
    connection_poll_period: float
    servoj_vmax: tuple[float, ...]
    servoj_amax: tuple[float, ...]
    servoj_jmax: tuple[float, ...]

    def interface_kwargs(self) -> dict[str, Any]:
        """Return arguments accepted by vendor.nrc_interface.CR3Interface."""

        return {
            "robot_ip": self.ip,
            "connect_control": self.connect_control,
            "connection_timeout": self.connection_timeout,
            "connection_poll_period": self.connection_poll_period,
            "control_port": self.ports.control,
            "teach_port": self.ports.teach,
            "track_port": self.ports.track,
            "servo_vmax": self.servoj_vmax,
            "servo_amax": self.servoj_amax,
            "servo_jmax": self.servoj_jmax,
        }


@dataclass(frozen=True)
class LinkerHandConfig:
    name: str
    side: str
    model: str
    joint_count: int
    state_min: int
    state_max: int
    transport: str
    modbus: str
    can: str

    def api_kwargs(
        self,
        *,
        transport: str | None = None,
        modbus: str | None = None,
        can: str | None = None,
    ) -> dict[str, str]:
        """Return constructor arguments for the vendored LinkerHand SDK."""

        selected_transport = (transport or self.transport).lower()
        if selected_transport not in {"rs485", "can"}:
            raise HardwareConfigError(
                f"hand.linkerhand.transport must be 'rs485' or 'can', got {selected_transport!r}"
            )
        return {
            "hand_type": self.side,
            "hand_joint": self.model,
            "modbus": (modbus or self.modbus)
            if selected_transport == "rs485"
            else "None",
            "can": can or self.can,
        }


@dataclass(frozen=True)
class CameraDeviceConfig:
    name: str
    serial: str


@dataclass(frozen=True)
class D435Config:
    devices: tuple[CameraDeviceConfig, ...]
    width: int
    height: int
    fps: int
    output_width: int
    output_height: int
    async_read: bool
    read_timeout_ms: int

    @property
    def camera_serials(self) -> dict[str, str]:
        return {device.name: device.serial for device in self.devices}

    def interface_kwargs(self) -> dict[str, Any]:
        """Return arguments accepted by CR3O6CameraInterface."""

        return {
            "camera_serials": self.camera_serials,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "output_width": self.output_width,
            "output_height": self.output_height,
            "async_read": self.async_read,
            "read_timeout_ms": self.read_timeout_ms,
        }


@dataclass(frozen=True)
class HardwareConfig:
    source: Path
    nrc: NrcConfig
    hand: LinkerHandConfig
    d435: D435Config

    def create_nrc_interface(self, **overrides: Any):
        """Create vendor.nrc_interface.CR3Interface from this configuration."""

        from vendor.nrc_interface.interface import CR3Interface

        kwargs = self.nrc.interface_kwargs()
        kwargs.update(overrides)
        return CR3Interface(**kwargs)

    def create_d435_interface(self, **overrides: Any):
        """Create vendor.camera.d435.CR3O6CameraInterface from this configuration."""

        from vendor.camera.d435.camera_interface import CR3O6CameraInterface

        kwargs = self.d435.interface_kwargs()
        kwargs.update(overrides)
        return CR3O6CameraInterface(**kwargs)


def _load_nrc(table: Mapping[str, Any]) -> NrcConfig:
    name = "nrc"
    ports = _mapping(table.get("ports"), f"{name}.ports")
    servoj = _mapping(table.get("servoj"), f"{name}.servoj")
    return NrcConfig(
        name=_string(table, "name", name),
        ip=_string(table, "ip", name),
        ports=NrcPorts(
            control=_positive_int(ports, "control", f"{name}.ports"),
            teach=_positive_int(ports, "teach", f"{name}.ports"),
            track=_positive_int(ports, "track", f"{name}.ports"),
        ),
        connect_control=_boolean(table, "connect_control", False, name),
        connection_timeout=_positive_float(table, "connection_timeout", name),
        connection_poll_period=_positive_float(
            table, "connection_poll_period", name
        ),
        servoj_vmax=_vector7(servoj, "vmax", f"{name}.servoj"),
        servoj_amax=_vector7(servoj, "amax", f"{name}.servoj"),
        servoj_jmax=_vector7(servoj, "jmax", f"{name}.servoj"),
    )


def _load_hand(table: Mapping[str, Any]) -> LinkerHandConfig:
    name = "hand.linkerhand"
    transport = _string(table, "transport", name).lower()
    if transport not in {"rs485", "can"}:
        raise HardwareConfigError(
            f"{name}.transport must be 'rs485' or 'can', got {transport!r}"
        )
    state_min = _int(table, "state_min", 0, name)
    state_max = _int(table, "state_max", 255, name)
    if state_min >= state_max:
        raise HardwareConfigError(f"{name}.state_min must be less than state_max")
    return LinkerHandConfig(
        name=_string(table, "name", name),
        side=_string(table, "side", name),
        model=_string(table, "model", name),
        joint_count=_positive_int(table, "joint_count", name),
        state_min=state_min,
        state_max=state_max,
        transport=transport,
        modbus=_optional_string(table, "modbus", "/dev/ttyUSB0", name),
        can=_optional_string(table, "can", "can0", name),
    )


def _load_d435(table: Mapping[str, Any]) -> D435Config:
    name = "cameras.d435"
    devices_table = _mapping(table.get("devices"), f"{name}.devices")
    devices = tuple(
        CameraDeviceConfig(
            name=device_name,
            serial=_string(
                _mapping(device, f"{name}.devices.{device_name}"),
                "serial",
                f"{name}.devices.{device_name}",
            ),
        )
        for device_name, device in devices_table.items()
    )
    actual_names = tuple(device.name for device in devices)
    if set(actual_names) != set(D435_CAMERA_NAMES):
        raise HardwareConfigError(
            f"{name}.devices must contain {D435_CAMERA_NAMES}, got {actual_names}"
        )
    devices_by_name = {device.name: device for device in devices}
    return D435Config(
        devices=tuple(devices_by_name[device_name] for device_name in D435_CAMERA_NAMES),
        width=_positive_int(table, "width", name),
        height=_positive_int(table, "height", name),
        fps=_positive_int(table, "fps", name),
        output_width=_positive_int(table, "output_width", name),
        output_height=_positive_int(table, "output_height", name),
        async_read=_boolean(table, "async_read", True, name),
        read_timeout_ms=_positive_int(table, "read_timeout_ms", name),
    )


def load_hardware_config(path: str | Path | None = None) -> HardwareConfig:
    """Load and validate a hardware profile, defaulting to config/hardware/cr3_o6.toml."""

    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    config_path = config_path.expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Hardware configuration does not exist: {config_path}")

    with config_path.open("rb") as stream:
        data = tomllib.load(stream)

    nrc = _mapping(data.get("nrc"), "nrc")
    hand_root = _mapping(data.get("hand"), "hand")
    hand = _mapping(hand_root.get("linkerhand"), "hand.linkerhand")
    cameras_root = _mapping(data.get("cameras"), "cameras")
    d435 = _mapping(cameras_root.get("d435"), "cameras.d435")
    return HardwareConfig(
        source=config_path,
        nrc=_load_nrc(nrc),
        hand=_load_hand(hand),
        d435=_load_d435(d435),
    )


__all__ = [
    "CameraDeviceConfig",
    "D435Config",
    "HardwareConfig",
    "HardwareConfigError",
    "LinkerHandConfig",
    "NrcConfig",
    "NrcPorts",
    "load_hardware_config",
]

