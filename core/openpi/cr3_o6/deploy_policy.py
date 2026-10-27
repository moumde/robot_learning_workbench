"""Run the CR3/O6 policy client against an OpenPI websocket policy server.

Preview without moving the hardware::

    ./scripts/run_nrc.sh python core/openpi/cr3_o6/deploy_policy.py --preview-only

Real robot motion is disabled unless ``--confirm-motion`` is supplied::

    ./scripts/run_nrc.sh python core/openpi/cr3_o6/deploy_policy.py --confirm-motion

The NRC extension requires Python 3.12. Hardware addresses, camera serials, and
LinkerHand transport are loaded from ``config/hardware/cr3_o6.toml``. The policy
contract is six CR3 joint angles in radians followed by six O6 positions in
the native 0..255 range, at 20 Hz with 30 actions per policy response.
"""

from __future__ import annotations

import argparse
from collections import deque
import functools
import inspect
import logging
import math
from pathlib import Path
import sys
import threading
import time
from typing import Any

import numpy as np
from openpi_client import websocket_client_policy


REPO_ROOT = Path(__file__).resolve().parents[3]
LINKERHAND_SDK_ROOT = REPO_ROOT / "vendor" / "actuator" / "linkerhand-python-sdk"
for import_root in (REPO_ROOT, LINKERHAND_SDK_ROOT):
    import_root_string = str(import_root)
    if import_root_string not in sys.path:
        sys.path.insert(0, import_root_string)

from config.hardware import HardwareConfig, load_hardware_config  # noqa: E402


LOGGER = logging.getLogger("cr3_o6_policy_deploy")

ACTION_DIM = 12
ACTION_HORIZON = 30
CAMERA_NAMES = ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")
CONTROL_HZ = 20.0
DEFAULT_POLICY_HOST = "127.0.0.1"
DEFAULT_POLICY_PORT = 8000
DEFAULT_PROMPT = "Pick up the motor and place it on the right side with the protruding side facing left."
INITIAL_ROBOT_POSITION = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
# INITIAL_HAND_POSITION = (157, 95, 175, 0, 0, 0)
INITIAL_HAND_POSITION = (157, 40, 175, 175, 0, 0)
DEFAULT_INITIAL_MOVE_DURATION_S = 3.0
MAX_JOINT_TARGET_SPEED_RAD_S = 1.0
DEFAULT_O6_SPEED = 100


def _patch_pymodbus_slave_argument() -> None:
    """Bridge SDK ``slave=`` calls to pymodbus APIs using ``device_id=``."""

    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError as exc:
        raise RuntimeError("LinkerHand RS485 requires pymodbus in the NRC environment") from exc

    for method_name in ("read_input_registers", "write_registers"):
        method = getattr(ModbusSerialClient, method_name, None)
        if method is None:
            continue
        parameters = inspect.signature(method).parameters
        if "slave" in parameters or "device_id" not in parameters:
            continue
        if getattr(method, "_workbench_slave_compat", False):
            continue

        @functools.wraps(method)
        def compatible_method(self: Any, *args: Any, _method=method, **kwargs: Any):
            if "slave" in kwargs:
                kwargs["device_id"] = kwargs.pop("slave")
            return _method(self, *args, **kwargs)

        compatible_method._workbench_slave_compat = True
        setattr(ModbusSerialClient, method_name, compatible_method)


def _load_hand_api():
    # The workbench and LinkerHand SDK both use a top-level ``core`` package.
    # Once ``core.openpi`` has been imported, appending the SDK's LinkerHand
    # directory to sys.path is not enough: the already-loaded namespace package
    # keeps its original search path. Extend it so ``core.rs485`` / ``core.can``
    # from the vendored SDK remain importable.
    sdk_core_root = LINKERHAND_SDK_ROOT / "LinkerHand" / "core"
    if not sdk_core_root.is_dir():
        raise RuntimeError(f"LinkerHand SDK core directory is missing: {sdk_core_root}")
    try:
        import core
    except ImportError as exc:
        raise RuntimeError("Could not resolve the workbench 'core' package") from exc
    core_paths = getattr(core, "__path__", None)
    if core_paths is None:
        raise RuntimeError(
            "The imported 'core' module is not a package; cannot expose LinkerHand drivers"
        )
    sdk_core_path = str(sdk_core_root)
    if sdk_core_path not in core_paths:
        core_paths.append(sdk_core_path)

    try:
        from LinkerHand.linker_hand_api import LinkerHandApi
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import the vendored LinkerHand SDK at {LINKERHAND_SDK_ROOT}"
        ) from exc
    return LinkerHandApi


def _close_hand(hand_api: Any) -> None:
    hand = getattr(hand_api, "hand", None)
    for method_name in ("close", "close_can_interface"):
        close = getattr(hand, method_name, None)
        if callable(close):
            try:
                close()
            except Exception:
                LOGGER.exception("Failed to close LinkerHand backend")
            return


def _finite_vector(values: Any, length: int, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.shape != (length,) or not np.all(np.isfinite(array)):
        raise RuntimeError(f"{name} must have shape ({length},) and finite values; got {array.shape}")
    return array


def _validate_action_chunk(result: dict[str, Any]) -> np.ndarray:
    if not isinstance(result, dict) or "actions" not in result:
        raise RuntimeError("Policy response must contain an 'actions' field")
    actions = np.asarray(result["actions"], dtype=np.float32)
    expected_shape = (ACTION_HORIZON, ACTION_DIM)
    if actions.shape != expected_shape or not np.all(np.isfinite(actions)):
        raise RuntimeError(f"Expected finite actions with shape {expected_shape}; got {actions.shape}")
    return np.ascontiguousarray(actions)


def _timing_ms(result: dict[str, Any], section: str) -> float | None:
    timing = result.get(section)
    if not isinstance(timing, dict):
        return None
    value = timing.get("infer_ms")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return float(value)


def _read_policy_action_chunk(
    policy: Any,
    source: "CR3O6ObservationSource",
    prompt: str,
    *,
    label: str = "Policy request",
) -> np.ndarray:
    """Read one observation, request a chunk, and report available timings."""
    observation_started = time.perf_counter()
    observation = source.read(prompt)
    observation_ms = (time.perf_counter() - observation_started) * 1000

    request_started = time.perf_counter()
    response = policy.infer(observation)
    round_trip_ms = (time.perf_counter() - request_started) * 1000
    actions = _validate_action_chunk(response)

    model_ms = _timing_ms(response, "policy_timing")
    server_ms = _timing_ms(response, "server_timing")
    model_text = f"{model_ms:.1f} ms" if model_ms is not None else "n/a"
    server_text = f"{server_ms:.1f} ms" if server_ms is not None else "n/a"
    LOGGER.info(
        "%s timing: model=%s, server policy=%s, client round-trip=%.1f ms, observation=%.1f ms",
        label,
        model_text,
        server_text,
        round_trip_ms,
        observation_ms,
    )
    return actions


class CR3O6ObservationSource:
    """Read the camera, arm, and hand values expected by the trained policy."""

    def __init__(self, hardware: HardwareConfig, robot: Any, hand: Any, cameras: Any):
        self.hardware = hardware
        self.robot = robot
        self.hand = hand
        self.cameras = cameras

    def read(self, prompt: str) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        hand_state = _finite_vector(
            self.hand.get_state(), self.hardware.hand.joint_count, "O6 state"
        )
        if np.any((hand_state < self.hardware.hand.state_min) | (hand_state > self.hardware.hand.state_max)):
            raise RuntimeError(f"O6 state outside configured range: {hand_state.tolist()}")
        state = _finite_vector(
            self.robot.get_openpi_state(hand_state.tolist()), ACTION_DIM, "OpenPI state"
        )
        images = self.cameras.read()
        expected_shape = (
            self.hardware.d435.output_height,
            self.hardware.d435.output_width,
            3,
        )
        observation_images: dict[str, np.ndarray] = {}
        for name in CAMERA_NAMES:
            image = np.asarray(images[name])
            if image.shape != expected_shape or image.dtype != np.uint8:
                raise RuntimeError(
                    f"Camera {name} returned {image.shape}/{image.dtype}; expected {expected_shape}/uint8"
                )
            observation_images[name] = image
        if expected_shape[:2] != (224, 224):
            raise RuntimeError(
                f"The pi05_cr3_o6_lora policy expects 224x224 camera images; configured {expected_shape[:2]}"
            )
        return {"images": observation_images, "state": state, "prompt": prompt}


class ActionChunkController:
    """Execute policy chunks at 20 Hz while limiting CR3 target slew."""

    def __init__(
        self,
        policy: Any,
        source: CR3O6ObservationSource,
        robot: Any,
        hand: Any,
        prompt: str,
        *,
        request_lead_steps: int = 6,
        max_joint_speed_rad_s: float = MAX_JOINT_TARGET_SPEED_RAD_S,
        initial_actions: np.ndarray | None = None,
    ):
        self.policy = policy
        self.source = source
        self.robot = robot
        self.hand = hand
        self.prompt = prompt
        self.request_lead_steps = request_lead_steps
        self.max_joint_speed_rad_s = max_joint_speed_rad_s
        self.actions: deque[np.ndarray] = deque()
        self.stop_event = threading.Event()
        self.request_event = threading.Event()
        self.lock = threading.RLock()
        self.request_in_flight = False
        self.result: np.ndarray | None = None
        self.worker_error: BaseException | None = None
        self.worker: threading.Thread | None = None
        self.last_arm_command = _finite_vector(
            robot.get_joint_positions(), 6, "CR3 current joint position"
        ).astype(np.float64)
        if initial_actions is not None:
            self.actions.extend(_validate_action_chunk({"actions": initial_actions}))

    def _request_worker(self) -> None:
        while not self.stop_event.is_set():
            self.request_event.wait(0.1)
            if self.stop_event.is_set():
                return
            if not self.request_event.is_set():
                continue
            self.request_event.clear()
            try:
                result = _read_policy_action_chunk(
                    self.policy, self.source, self.prompt, label="Action chunk"
                )
                with self.lock:
                    self.result = result
                    self.request_in_flight = False
            except BaseException as exc:
                with self.lock:
                    self.worker_error = exc
                    self.request_in_flight = False
                self.stop_event.set()
                return

    def _schedule_request(self) -> None:
        with self.lock:
            if self.request_in_flight or self.result is not None or self.stop_event.is_set():
                return
            self.request_in_flight = True
        self.request_event.set()

    def _take_result(self) -> None:
        with self.lock:
            result, self.result = self.result, None
        if result is not None:
            self.actions.extend(result)
            LOGGER.info("Received action chunk %s; buffered actions=%d", result.shape, len(self.actions))

    def _apply(self, action: np.ndarray) -> None:
        arm_target = _finite_vector(action[:6], 6, "CR3 action")
        hand_target = np.clip(_finite_vector(action[6:], 6, "O6 action"), 0, 255)
        actual = _finite_vector(self.robot.get_joint_positions(), 6, "CR3 feedback").astype(np.float64)
        max_step = self.max_joint_speed_rad_s / CONTROL_HZ
        target_from_feedback = actual + np.clip(arm_target - actual, -max_step, max_step)
        commanded = self.last_arm_command + np.clip(
            target_from_feedback - self.last_arm_command, -max_step, max_step
        )
        self.last_arm_command = commanded
        self.robot.send_joint_positions(commanded.tolist())
        self.hand.finger_move([int(round(value)) for value in hand_target])

    def run(self, duration_s: float | None = None) -> None:
        self.worker = threading.Thread(target=self._request_worker, name="policy-request", daemon=True)
        self.worker.start()
        self._schedule_request()
        period = 1.0 / CONTROL_HZ
        next_tick = time.monotonic()
        started = next_tick
        try:
            while True:
                with self.lock:
                    worker_error = self.worker_error
                if worker_error is not None:
                    raise RuntimeError(f"Policy request failed: {worker_error}") from worker_error
                if self.stop_event.is_set():
                    return
                self._take_result()
                if duration_s is not None and time.monotonic() - started >= duration_s:
                    return
                if len(self.actions) <= self.request_lead_steps:
                    self._schedule_request()
                if self.actions:
                    self._apply(self.actions.popleft())
                else:
                    LOGGER.warning("Policy action buffer empty; holding current CR3 position")
                    self.robot.send_joint_positions(self.robot.get_joint_positions())
                next_tick += period
                delay = next_tick - time.monotonic()
                if delay > 0:
                    self.stop_event.wait(delay)
                else:
                    next_tick = time.monotonic()
        finally:
            self.stop()

    def stop(self) -> None:
        self.stop_event.set()
        self.request_event.set()
        if self.worker is not None and self.worker is not threading.current_thread():
            self.worker.join(timeout=5.0)
            if self.worker.is_alive():
                raise RuntimeError("Policy request thread did not stop cleanly")
            self.worker = None


def _move_to_initial_position(robot: Any, hand: Any, duration_s: float, max_speed_rad_s: float) -> None:
    if duration_s <= 0 or not math.isfinite(duration_s):
        raise ValueError("initial move duration must be finite and positive")
    target = np.asarray(INITIAL_ROBOT_POSITION[:6], dtype=np.float64)
    current = np.asarray(robot.get_joint_positions(), dtype=np.float64)
    if current.shape != (6,) or not np.all(np.isfinite(current)):
        raise RuntimeError(f"Invalid CR3 current joint position: {current}")
    hand.finger_move(list(INITIAL_HAND_POSITION))
    steps = max(
        1,
        math.ceil(duration_s * CONTROL_HZ),
        math.ceil(float(np.max(np.abs(target - current))) / max_speed_rad_s * CONTROL_HZ),
    )
    started = time.monotonic()
    for step in range(1, steps + 1):
        robot.send_joint_positions((current + (target - current) * (step / steps)).tolist(),
                                   external_axis=INITIAL_ROBOT_POSITION[6])
        remaining = started + step / CONTROL_HZ - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default=None, help="Hardware profile TOML (default: config/hardware/cr3_o6.toml)"
    )
    parser.add_argument("--host", default=DEFAULT_POLICY_HOST, help="OpenPI policy server address")
    parser.add_argument("--port", type=int, default=DEFAULT_POLICY_PORT)
    parser.add_argument("--transport", choices=("rs485", "can"), default=None)
    parser.add_argument("--modbus", default=None, help="Override hand.linkerhand.modbus")
    parser.add_argument("--can", default=None, help="Override hand.linkerhand.can")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--preview-only", action="store_true", help="Infer and discard actions; do not move")
    parser.add_argument("--confirm-motion", action="store_true", help="Explicitly enable real robot motion")
    parser.add_argument("--no-auto-power-on", action="store_true")
    parser.add_argument("--request-lead-steps", type=int, default=6)
    parser.add_argument("--initial-move-duration-s", type=float, default=DEFAULT_INITIAL_MOVE_DURATION_S)
    parser.add_argument("--max-joint-speed-rad-s", type=float, default=MAX_JOINT_TARGET_SPEED_RAD_S)
    parser.add_argument("--o6-speed", type=int, default=DEFAULT_O6_SPEED)
    parser.add_argument("--duration-s", type=float, default=0, help="0 runs until Ctrl-C")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.preview_only == args.confirm_motion:
        raise SystemExit("Choose exactly one mode: --preview-only or --confirm-motion")
    if args.preview_only and args.no_auto_power_on:
        raise SystemExit("--no-auto-power-on is only valid with --confirm-motion")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.request_lead_steps < 1:
        raise SystemExit("--request-lead-steps must be >= 1")
    if args.max_joint_speed_rad_s <= 0 or not math.isfinite(args.max_joint_speed_rad_s):
        raise SystemExit("--max-joint-speed-rad-s must be finite and positive")
    if args.initial_move_duration_s <= 0 or not math.isfinite(args.initial_move_duration_s):
        raise SystemExit("--initial-move-duration-s must be finite and positive")
    if not 10 <= args.o6_speed <= 255:
        raise SystemExit("--o6-speed must be in [10, 255]")
    if args.duration_s < 0 or not math.isfinite(args.duration_s):
        raise SystemExit("--duration-s must be finite and non-negative")
    if not args.prompt.strip():
        raise SystemExit("--prompt cannot be empty")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )

    hardware = load_hardware_config(args.config)
    if hardware.hand.model.upper() != "O6" or hardware.hand.joint_count != 6:
        raise SystemExit("pi05_cr3_o6_lora deployment requires a six-joint O6 hand")
    if (args.transport or hardware.hand.transport) == "rs485":
        _patch_pymodbus_slave_argument()
    LinkerHandApi = _load_hand_api()
    hand_kwargs = hardware.hand.api_kwargs(
        transport=args.transport, modbus=args.modbus, can=args.can
    )
    policy = websocket_client_policy.WebsocketClientPolicy(host=args.host, port=args.port)
    LOGGER.info("Connected to policy server %s:%d; metadata=%s", args.host, args.port,
                policy.get_server_metadata())
    robot = hardware.create_nrc_interface()
    cameras = hardware.create_d435_interface()
    hand_api = None
    controller: ActionChunkController | None = None
    servo_opened = False
    powered_by_client = False
    exit_code = 0
    cleanup_failed = False
    try:
        LOGGER.info("Connecting CR3 %s from %s", hardware.nrc.ip, hardware.source)
        robot.connect()
        LOGGER.info("Connecting %s LinkerHand %s via %s", hardware.hand.side,
                    hardware.hand.model,
                    hand_kwargs["modbus"] if hand_kwargs["modbus"] != "None" else hand_kwargs["can"])
        hand_api = LinkerHandApi(**hand_kwargs)
        if hand_api.hand_type != hardware.hand.side or str(hand_api.hand_joint).upper() != "O6":
            raise RuntimeError(f"Unexpected LinkerHand: {hand_api.hand_type}/{hand_api.hand_joint}")
        cameras.connect()
        source = CR3O6ObservationSource(hardware, robot, hand_api, cameras)

        if args.preview_only:
            warmup = _read_policy_action_chunk(
                policy, source, args.prompt, label="Preview warm-up"
            )
            LOGGER.info("Preview inference succeeded; actions discarded. Shape=%s first=%s",
                        warmup.shape, np.round(warmup[0], 4).tolist())
            started = time.monotonic()
            while not args.duration_s or time.monotonic() - started < args.duration_s:
                request_started = time.monotonic()
                actions = _read_policy_action_chunk(
                    policy, source, args.prompt, label="Preview request"
                )
                LOGGER.info("Preview actions shape=%s first=%s", actions.shape,
                            np.round(actions[0], 4).tolist())
                time.sleep(max(0.0, 0.5 - (time.monotonic() - request_started)))
            return 0

        hand_api.set_speed([args.o6_speed] * hardware.hand.joint_count)
        from vendor.nrc_interface.interface import NRCError, SERVO_RUNNING

        if robot.get_servo_state() != SERVO_RUNNING:
            if args.no_auto_power_on:
                raise NRCError("CR3 is not running and --no-auto-power-on was specified")
            LOGGER.info("CR3 is not running; powering on")
            robot.power_on()
            powered_by_client = True
        if robot.get_servo_state() != SERVO_RUNNING:
            raise NRCError("CR3 is not in running state")
        robot.open_servoj()
        servo_opened = True
        _move_to_initial_position(robot, hand_api, args.initial_move_duration_s,
                                  args.max_joint_speed_rad_s)
        warmup = _read_policy_action_chunk(
            policy, source, args.prompt, label="Policy warm-up"
        )
        LOGGER.info("Policy warmup succeeded: action chunk shape=%s", warmup.shape)
        controller = ActionChunkController(
            policy, source, robot, hand_api, args.prompt,
            request_lead_steps=args.request_lead_steps,
            max_joint_speed_rad_s=args.max_joint_speed_rad_s,
            initial_actions=warmup,
        )
        controller.run(args.duration_s or None)
    except KeyboardInterrupt:
        LOGGER.info("Deployment stopped by user")
    except Exception as exc:
        LOGGER.exception("Deployment failed: %s", exc)
        exit_code = 1
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception:
                LOGGER.exception("Failed to stop policy controller")
                cleanup_failed = True
        if servo_opened:
            try:
                _move_to_initial_position(robot, hand_api, args.initial_move_duration_s,
                                          args.max_joint_speed_rad_s)
            except Exception:
                LOGGER.exception("Failed to return CR3/O6 to the initial position")
                cleanup_failed = True
            try:
                robot.close_servoj()
            except Exception:
                LOGGER.exception("Failed to close CR3 ServoJ")
                cleanup_failed = True
        cameras.disconnect()
        if hand_api is not None:
            _close_hand(hand_api)
        if powered_by_client:
            try:
                robot.power_off()
            except Exception:
                LOGGER.exception("Failed to power off CR3")
                cleanup_failed = True
        robot.disconnect()
        if cleanup_failed and exit_code == 0:
            LOGGER.error("Policy task cleanup failed; stopping the remaining workflow for safety")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
