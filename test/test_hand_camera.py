"""Connection/read-only test for the configured LinkerHand and D435 cameras.

``run_openpi.sh`` changes the working directory to ``module/openpi``.  Run
this file from the repository root with an explicit path::

    ./scripts/run_openpi.sh python ../../test/test_hand_camera.py

Example with CAN::

    ./scripts/run_openpi.sh python ../../test/test_hand_camera.py \
        --transport can --can can0

This script only initializes the right O6, reads its current six joint
positions, connects the three cameras, and reads camera frames.  It does not
send a hand or robot motion command.
"""

from __future__ import annotations

import argparse
import functools
import inspect
import logging
import math
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np


# The launcher intentionally runs from module/openpi, so neither the
# repository root nor the vendored LinkerHand SDK is on sys.path by default.
# Resolve both paths from this file instead of relying on the caller's cwd or
# a machine-specific PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
LINKERHAND_SDK_ROOT = REPO_ROOT / "vendor" / "actuator" / "linkerhand-python-sdk"
for import_root in (REPO_ROOT, LINKERHAND_SDK_ROOT):
    import_root_string = str(import_root)
    if import_root_string not in sys.path:
        sys.path.insert(0, import_root_string)

from config.hardware import load_hardware_config  # noqa: E402

LOGGER = logging.getLogger("cr3_o6_connection_test")


def patch_pymodbus_slave_argument() -> None:
    """Keep the SDK's ``slave=`` calls working with newer pymodbus releases.

    The vendored SDK was written for pymodbus 3.5.x.  Some newer releases
    renamed this keyword to ``device_id``.  Patch only when the installed API
    no longer accepts ``slave``; the pinned SDK version remains untouched.
    """

    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError as exc:
        raise RuntimeError(
            "RS485 testing requires pymodbus. Install the LinkerHand SDK dependencies "
            "in the OpenPI environment (see vendor/actuator/linkerhand-python-sdk/requirements.txt)."
        ) from exc

    for method_name in ("read_input_registers", "write_registers"):
        method = getattr(ModbusSerialClient, method_name, None)
        if method is None:
            continue
        parameters = inspect.signature(method).parameters
        if "slave" in parameters or "device_id" not in parameters:
            continue

        @functools.wraps(method)
        def compatibility_method(self, *args, _method=method, **kwargs):
            if "slave" in kwargs:
                kwargs["device_id"] = kwargs.pop("slave")
            return _method(self, *args, **kwargs)

        setattr(ModbusSerialClient, method_name, compatibility_method)


def _load_hand_api():
    try:
        from LinkerHand.linker_hand_api import LinkerHandApi

        return LinkerHandApi
    except ImportError as exc:
        raise RuntimeError(
            f"LinkerHand SDK import failed from {LINKERHAND_SDK_ROOT}. "
            "Check that the vendored SDK and its dependencies are available in the OpenPI environment."
        ) from exc


def _validate_hand_state(
    state: Sequence[float], *, expected_length: int, state_min: int, state_max: int
) -> list[int]:
    values = [float(value) for value in state]
    if len(values) != expected_length:
        raise AssertionError(
            f"Expected {expected_length} hand joint values, got {len(values)}: {values!r}"
        )
    if not all(
        math.isfinite(value) and state_min <= value <= state_max for value in values
    ):
        raise AssertionError(
            f"Hand joint values must be finite and in [{state_min}, {state_max}], "
            f"got {values!r}"
        )
    return [int(round(value)) for value in values]


def _close_hand(hand_api) -> None:
    """Close either the RS485 or CAN implementation behind LinkerHandApi."""

    hand = getattr(hand_api, "hand", None)
    if hand is None:
        return
    for method_name in ("close", "close_can_interface"):
        method = getattr(hand, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                LOGGER.exception("Failed to close LinkerHand through %s()", method_name)
            return
    LOGGER.warning(
        "No close method found on LinkerHand backend %s", type(hand).__name__
    )


def _validate_frames(
    frames: dict[str, np.ndarray],
    expected_names: tuple[str, ...],
    expected_shape: tuple[int, int, int],
) -> None:
    if set(frames) != set(expected_names):
        raise AssertionError(
            f"Expected camera keys {expected_names}, got {tuple(frames)}"
        )
    for name in expected_names:
        image = np.asarray(frames[name])
        if image.shape != expected_shape:
            raise AssertionError(
                f"Camera {name} returned shape {image.shape}, expected {expected_shape}"
            )
        if image.dtype != np.uint8:
            raise AssertionError(
                f"Camera {name} returned dtype {image.dtype}, expected uint8"
            )
        if not image.flags.c_contiguous:
            raise AssertionError(f"Camera {name} returned a non-contiguous image")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=None,
        help="Hardware TOML path (default: config/hardware/cr3_o6.toml)",
    )
    parser.add_argument(
        "--transport",
        choices=("rs485", "can"),
        default=None,
        help="Override the LinkerHand transport from the config",
    )
    parser.add_argument(
        "--modbus", default=None, help="Override the O6 RS485 device path"
    )
    parser.add_argument("--can", default=None, help="Override the O6 CAN interface")
    parser.add_argument(
        "--frames", type=int, default=1, help="Number of camera frames to read"
    )
    parser.add_argument(
        "--camera-timeout-ms",
        type=int,
        default=None,
        help="Override the camera read timeout from the config",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.frames <= 0:
        raise ValueError("--frames must be positive")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    hand_api = None
    cameras = None
    try:
        hardware = load_hardware_config(args.config)
        LinkerHandApi = _load_hand_api()
        transport = args.transport or hardware.hand.transport
        if transport == "rs485":
            patch_pymodbus_slave_argument()
        hand_kwargs = hardware.hand.api_kwargs(
            transport=transport,
            modbus=args.modbus,
            can=args.can,
        )
        LOGGER.info(
            "Connecting %s LinkerHand %s via %s",
            hardware.hand.side,
            hardware.hand.model,
            hand_kwargs["modbus"] if transport == "rs485" else hand_kwargs["can"],
        )
        hand_api = LinkerHandApi(**hand_kwargs)
        if (
            hand_api.hand_type != hardware.hand.side
            or hand_api.hand_joint.upper() != hardware.hand.model.upper()
        ):
            raise AssertionError(
                f"Unexpected hand configuration: type={hand_api.hand_type!r}, "
                f"joint={hand_api.hand_joint!r}; expected "
                f"type={hardware.hand.side!r}, joint={hardware.hand.model!r}"
            )
        hand_state = _validate_hand_state(
            hand_api.get_state(),
            expected_length=hardware.hand.joint_count,
            state_min=hardware.hand.state_min,
            state_max=hardware.hand.state_max,
        )
        LOGGER.info(
            "%s LinkerHand %s connected; current state [0..255]: %s",
            hardware.hand.side,
            hardware.hand.model,
            hand_state,
        )

        camera_overrides = {}
        if args.camera_timeout_ms is not None:
            camera_overrides["read_timeout_ms"] = args.camera_timeout_ms
        cameras = hardware.create_d435_interface(**camera_overrides)
        LOGGER.info("Using hardware config: %s", hardware.source)
        camera_names = tuple(hardware.d435.camera_serials)
        expected_shape = (hardware.d435.output_height, hardware.d435.output_width, 3)
        cameras.connect()
        if not cameras.connected:
            raise AssertionError(
                "Camera interface reports disconnected after connect()"
            )
        LOGGER.info("Three D435 cameras connected: %s", cameras.camera_serials)

        for index in range(args.frames):
            frames = cameras.read()
            _validate_frames(frames, camera_names, expected_shape)
            LOGGER.info(
                "Camera frame %d/%d received: %s",
                index + 1,
                args.frames,
                {name: frames[name].shape for name in camera_names},
            )

        LOGGER.info("LinkerHand + three-camera connection test passed")
        return 0
    except (AssertionError, ImportError, RuntimeError, ValueError, OSError) as exc:
        LOGGER.error("Connection test failed: %s", exc)
        return 1
    finally:
        if cameras is not None:
            cameras.disconnect()
        if hand_api is not None:
            _close_hand(hand_api)


if __name__ == "__main__":
    sys.exit(main())
