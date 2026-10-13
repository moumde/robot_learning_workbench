"""Manual hardware test for :mod:`vendor.nrc_interface.interface`.

The default run is read-only.  It connects to the teach and tracking ports,
reads servo state/joints/TCP, and checks Cartesian-to-joint conversion.

Examples::

    # Read-only validation
    ./scripts/run_nrc.sh python test/test_nrc_interface.py

    # Explicitly test the control path.  The arm target is its current
    # position, so this should not intentionally move the robot.
    ./scripts/run_nrc.sh python test/test_nrc_interface.py \
        --control-test

The control test powers the robot on only when necessary, opens ServoJ, sends
the current joint position once, closes ServoJ, and powers the robot off again
if this script powered it on.  Keep the robot clear and supervised anyway.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


# The launcher changes the working directory. Resolve the repository root from
# this file so the test does not depend on the caller's cwd or PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_string = str(REPO_ROOT)
if repo_root_string not in sys.path:
    sys.path.insert(0, repo_root_string)

from config.hardware import load_hardware_config  # noqa: E402


def _load_nrc_interface():
    """Load the vendor binding and report Python-ABI problems clearly."""

    try:
        return importlib.import_module("vendor.nrc_interface.interface")
    except (ImportError, OSError) as exc:
        detail = str(exc)
        if "libpython3.12" in detail or "Python 3.12" in detail:
            raise RuntimeError(
                "The NRC vendor binding requires Python 3.12, but run_openpi.sh "
                "uses OpenPI's Python 3.11 environment. Rebuild _nrc_host.so for "
                "Python 3.11 or provide a Python 3.12 OpenPI environment before "
                "running this hardware test."
            ) from exc
        raise RuntimeError(
            "Could not load vendor.nrc_interface.interface; check the NRC shared "
            f"library and its dependencies: {exc}"
        ) from exc


LOGGER = logging.getLogger("cr3_interface_test")
SERVO_STOPPED = 0
SERVO_READY = 1
SERVO_ERROR = 2
SERVO_RUNNING = 3
SERVO_STATE_NAMES = {
    SERVO_STOPPED: "stopped",
    SERVO_READY: "ready",
    SERVO_ERROR: "error",
    SERVO_RUNNING: "running",
}


def _assert_vector(name: str, values: Sequence[float], expected_length: int) -> None:
    if len(values) != expected_length:
        raise AssertionError(
            f"{name} has length {len(values)}, expected {expected_length}: {values!r}"
        )
    if not all(math.isfinite(float(value)) for value in values):
        raise AssertionError(f"{name} contains non-finite values: {values!r}")


def run_read_only_test(
    robot: Any,
    *,
    check_cartesian: bool = True,
    servo_state_names: Mapping[int, str] | None = None,
) -> None:
    """Validate connections and all non-motion interface calls."""

    if servo_state_names is None:
        servo_state_names = SERVO_STATE_NAMES
    state = robot.get_servo_state()
    LOGGER.info("Servo state: %d (%s)", state, servo_state_names.get(state, "unknown"))
    if state not in servo_state_names:
        raise AssertionError(f"Unexpected servo state: {state}")

    joints = robot.get_joint_positions()
    _assert_vector("joint positions [rad]", joints, 6)
    LOGGER.info("Joint positions [rad]: %s", [round(value, 6) for value in joints])

    tcp = robot.get_tcp_pose()
    _assert_vector("TCP pose [mm, rad, ext]", tcp, 7)
    LOGGER.info("TCP pose [mm, rad, ext]: %s", [round(value, 6) for value in tcp])

    if check_cartesian:
        converted = robot.convert_pose_to_joints(tcp)
        _assert_vector("Cartesian-converted joints [rad]", converted, 6)
        LOGGER.info(
            "Cartesian conversion result [rad]: %s",
            [round(value, 6) for value in converted],
        )


def run_control_test(robot: Any, *, servo_running: int = SERVO_RUNNING) -> None:
    """Exercise power, ServoJ, and command paths with a no-motion target."""

    initial_state = robot.get_servo_state()
    powered_by_test = False
    servo_opened = False
    try:
        if initial_state != servo_running:
            LOGGER.info("Servo is not running; executing power_on()")
            robot.power_on()
            powered_by_test = True
        if robot.get_servo_state() != servo_running:
            raise AssertionError("Servo did not reach running state after power_on()")

        robot.open_servoj()
        servo_opened = True
        current_joints = robot.get_joint_positions()
        robot.send_joint_positions(current_joints)
        LOGGER.info(
            "ServoJ accepted the current joint position without an intentional move"
        )

    finally:
        if servo_opened:
            robot.close_servoj()
            LOGGER.info("ServoJ closed")
        if powered_by_test:
            robot.power_off()
            LOGGER.info("Robot powered off because this test powered it on")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=None,
        help="Hardware TOML path (default: config/hardware.toml)",
    )
    parser.add_argument(
        "--ip", default=None, help="Override the CR3 controller IP from the config"
    )
    parser.add_argument(
        "--control-test",
        action="store_true",
        help="Also power on if needed, open ServoJ, send the current position, and power off",
    )
    parser.add_argument(
        "--skip-cartesian",
        action="store_true",
        help="Skip the Cartesian pose to joint conversion check",
    )
    parser.add_argument(
        "--connect-control",
        action="store_true",
        dest="connect_control",
        default=None,
        help="Override config and connect the optional control port",
    )
    parser.add_argument(
        "--no-connect-control",
        action="store_false",
        dest="connect_control",
        default=None,
        help="Override config and do not connect the control port",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override the connection timeout in seconds",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    robot = None
    try:
        hardware = load_hardware_config(args.config)
        nrc_overrides = {}
        if args.ip is not None:
            nrc_overrides["robot_ip"] = args.ip
        if args.connect_control is not None:
            nrc_overrides["connect_control"] = args.connect_control
        if args.timeout is not None:
            nrc_overrides["connection_timeout"] = args.timeout

        nrc_interface = _load_nrc_interface()
        servo_state_names = {
            nrc_interface.SERVO_STOPPED: "stopped",
            nrc_interface.SERVO_READY: "ready",
            nrc_interface.SERVO_ERROR: "error",
            nrc_interface.SERVO_RUNNING: "running",
        }
        robot = hardware.create_nrc_interface(**nrc_overrides)
        LOGGER.info("Using hardware config: %s", hardware.source)
        LOGGER.info(
            "Connecting to CR3 at %s (teach=%d, track=%d, control=%d)",
            robot.robot_ip,
            robot.teach_port,
            robot.track_port,
            robot.control_port,
        )
        robot.connect()
        run_read_only_test(
            robot,
            check_cartesian=not args.skip_cartesian,
            servo_state_names=servo_state_names,
        )
        if args.control_test:
            run_control_test(robot, servo_running=nrc_interface.SERVO_RUNNING)
        LOGGER.info("CR3 interface test passed")
        return 0
    except (AssertionError, OSError, RuntimeError, ValueError) as exc:
        LOGGER.error("CR3 interface test failed: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.disconnect()


if __name__ == "__main__":
    sys.exit(main())
