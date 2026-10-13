"""Execute an ordered CR3/O6 policy and trajectory workflow in one session."""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.hardware import load_hardware_config  # noqa: E402
from core.openpi.cr3_o6.deploy_policy import (  # noqa: E402
    DEFAULT_INITIAL_MOVE_DURATION_S,
    DEFAULT_POLICY_HOST,
    DEFAULT_POLICY_PORT,
    MAX_JOINT_TARGET_SPEED_RAD_S,
    ActionChunkController,
    CR3O6ObservationSource,
    _close_hand,
    _load_hand_api,
    _move_to_initial_position,
    _patch_pymodbus_slave_argument,
    _validate_action_chunk,
)
from core.openpi.cr3_o6.replay_trajectory import (  # noqa: E402
    DEFAULT_FIRST_ACTION_MOVE_DURATION_S,
    DEFAULT_MAX_JOINT_SPEED_RAD_S,
    _episode_paths,
    _move_to_position,
    load_trajectory,
    replay_trajectory,
)


LOGGER = logging.getLogger("cr3_o6_workflow")


def _validate_plan(plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list) or not plan["tasks"]:
        raise ValueError("Workflow plan must contain a non-empty 'tasks' list")
    tasks = plan["tasks"]
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise ValueError(f"Task {index} must be an object")
        kind = task.get("type")
        if kind == "policy":
            prompt = task.get("prompt")
            duration = task.get("duration_s")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"Policy task {index} requires a non-empty prompt")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration)
                or duration <= 0
            ):
                raise ValueError(f"Policy task {index} requires duration_s > 0")
        elif kind == "replay":
            data_dir = task.get("data_dir")
            repeat = task.get("repeat", 1)
            time_scale = task.get("time_scale", 1.0)
            if not isinstance(data_dir, str) or not data_dir.strip():
                raise ValueError(f"Replay task {index} requires data_dir")
            if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 1:
                raise ValueError(f"Replay task {index} requires repeat >= 1")
            if (
                isinstance(time_scale, bool)
                or not isinstance(time_scale, (int, float))
                or not math.isfinite(time_scale)
                or time_scale <= 0
            ):
                raise ValueError(f"Replay task {index} requires time_scale > 0")
        else:
            raise ValueError(f"Task {index} has unsupported type {kind!r}")
    return tasks


def _load_replay_task(task: dict[str, Any], hardware: Any):
    dataset_dir = Path(task["data_dir"]).expanduser()
    if not dataset_dir.is_absolute():
        dataset_dir = REPO_ROOT / dataset_dir
    dataset_dir = dataset_dir.resolve()
    episode_paths = _episode_paths(dataset_dir)
    if not episode_paths:
        raise FileNotFoundError(f"No parquet episodes found under {dataset_dir / 'data'}")
    indices = [episode_index for episode_index, _path in episode_paths]
    LOGGER.info(
        "Replay dataset %s: %d episodes in order %s",
        dataset_dir,
        len(indices),
        indices,
    )
    trajectories = [
        load_trajectory(
            dataset_dir,
            episode_index,
            hand_min=hardware.hand.state_min,
            hand_max=hardware.hand.state_max,
        )
        for episode_index in indices
    ]
    return trajectories, int(task.get("repeat", 1)), float(task.get("time_scale", 1.0))


def _run_policy_task(
    task: dict[str, Any],
    policy: Any,
    source: CR3O6ObservationSource,
    robot: Any,
    hand: Any,
) -> None:
    prompt = task["prompt"].strip()
    duration_s = float(task["duration_s"])
    LOGGER.info("Starting PI05 task for %.2f s: %s", duration_s, prompt)
    warmup = _validate_action_chunk(policy.infer(source.read(prompt)))
    LOGGER.info("Policy warmup succeeded: action chunk shape=%s", warmup.shape)
    controller = ActionChunkController(
        policy,
        source,
        robot,
        hand,
        prompt,
        max_joint_speed_rad_s=MAX_JOINT_TARGET_SPEED_RAD_S,
        initial_actions=warmup,
    )
    try:
        controller.run(duration_s)
    finally:
        controller.stop()


def _run_replay_task(
    trajectories: list[Any],
    robot: Any,
    hand: Any,
    *,
    repeat: int,
    time_scale: float,
    max_joint_speed_rad_s: float,
) -> None:
    from vendor.nrc_interface.interface import SERVO_RUNNING

    total = len(trajectories)
    for repetition in range(repeat):
        if robot.get_servo_state() != SERVO_RUNNING:
            raise RuntimeError(
                "CR3 left the running state before dataset replay; "
                "workflow halted without attempting recovery motion"
            )
        LOGGER.info(
            "Returning CR3/O6 to the initial position before dataset pass %d/%d",
            repetition + 1,
            repeat,
        )
        _move_to_initial_position(
            robot,
            hand,
            DEFAULT_INITIAL_MOVE_DURATION_S,
            MAX_JOINT_TARGET_SPEED_RAD_S,
        )
        for position, trajectory in enumerate(trajectories):
            if robot.get_servo_state() != SERVO_RUNNING:
                raise RuntimeError(
                    "CR3 left the running state before trajectory playback; "
                    "workflow halted without attempting recovery motion"
                )
            _move_to_position(
                robot,
                hand,
                trajectory.actions[0, :6],
                trajectory.actions[0, 6:],
                duration_s=DEFAULT_FIRST_ACTION_MOVE_DURATION_S,
                max_joint_speed_rad_s=max_joint_speed_rad_s,
                label=f"transition to episode {trajectory.episode_index}",
            )
            LOGGER.info(
                "Dataset pass %d/%d: episode %d (%d/%d)",
                repetition + 1,
                repeat,
                trajectory.episode_index,
                position + 1,
                total,
            )
            replay_trajectory(
                trajectory,
                robot,
                hand,
                time_scale=time_scale,
                max_joint_speed_rad_s=max_joint_speed_rad_s,
                disable_slew_limit=False,
                repeat=1,
            )


def run_workflow(
    *,
    tasks: list[dict[str, Any]],
    config_path: str | None,
    policy_host: str,
    policy_port: int,
) -> int:
    hardware = load_hardware_config(config_path)
    if hardware.hand.model.upper() != "O6" or hardware.hand.joint_count != 6:
        raise ValueError("CR3/O6 workflow requires a six-joint O6 hand")

    policy_tasks = [task for task in tasks if task["type"] == "policy"]
    replay_cache: dict[int, tuple[list[Any], int, float]] = {}
    for index, task in enumerate(tasks):
        if task["type"] == "replay":
            replay_cache[index] = _load_replay_task(task, hardware)

    policy = None
    cameras = None
    source = None
    if policy_tasks:
        from openpi_client import websocket_client_policy

        policy = websocket_client_policy.WebsocketClientPolicy(host=policy_host, port=policy_port)
        LOGGER.info(
            "Connected to policy server %s:%d; metadata=%s",
            policy_host,
            policy_port,
            policy.get_server_metadata(),
        )
        cameras = hardware.create_d435_interface()

    _patch_pymodbus_slave_argument() if hardware.hand.transport == "rs485" else None
    LinkerHandApi = _load_hand_api()
    robot = hardware.create_nrc_interface()
    hand_api = None
    servo_opened = False
    powered_by_workflow = False
    exit_code = 0
    cleanup_failed = False

    try:
        LOGGER.info("Connecting CR3 %s from %s", hardware.nrc.ip, hardware.source)
        robot.connect()
        hand_kwargs = hardware.hand.api_kwargs()
        endpoint = hand_kwargs["modbus"] if hand_kwargs["modbus"] != "None" else hand_kwargs["can"]
        LOGGER.info("Connecting %s LinkerHand O6 via %s", hardware.hand.side, endpoint)
        hand_api = LinkerHandApi(**hand_kwargs)
        if hand_api.hand_type != hardware.hand.side or str(hand_api.hand_joint).upper() != "O6":
            raise RuntimeError(f"Unexpected LinkerHand: {hand_api.hand_type}/{hand_api.hand_joint}")
        hand_api.set_speed([100] * hardware.hand.joint_count)

        if cameras is not None:
            cameras.connect()
            source = CR3O6ObservationSource(hardware, robot, hand_api, cameras)

        from vendor.nrc_interface.interface import (
            SERVO_ERROR,
            SERVO_READY,
            SERVO_RUNNING,
            SERVO_STOPPED,
        )

        state = robot.get_servo_state()
        if state == SERVO_ERROR:
            raise RuntimeError(
                "CR3 is already in SERVO_ERROR before workflow start; "
                "inspect and clear the controller alarm manually before retrying"
            )
        if state != SERVO_RUNNING:
            if state not in (SERVO_STOPPED, SERVO_READY):
                raise RuntimeError(f"Unexpected CR3 servo state {state}; refusing to power on")
            LOGGER.info("CR3 servo state is %s; powering on for the workflow", state)
            robot.power_on()
            powered_by_workflow = True
        if robot.get_servo_state() != SERVO_RUNNING:
            raise RuntimeError("CR3 did not reach the running state")

        robot.open_servoj()
        servo_opened = True
        _move_to_initial_position(
            robot,
            hand_api,
            DEFAULT_INITIAL_MOVE_DURATION_S,
            MAX_JOINT_TARGET_SPEED_RAD_S,
        )

        for index, task in enumerate(tasks, start=1):
            if robot.get_servo_state() != SERVO_RUNNING:
                raise RuntimeError(
                    f"CR3 servo state is no longer running before workflow task {index}; stopping"
                )
            LOGGER.info(
                "Workflow task %d/%d: %s (%s)",
                index,
                len(tasks),
                task.get("name", task["type"]),
                task["type"],
            )
            if task["type"] == "policy":
                _run_policy_task(task, policy, source, robot, hand_api)
            else:
                trajectories, repeat, time_scale = replay_cache[index - 1]
                _run_replay_task(
                    trajectories,
                    robot,
                    hand_api,
                    repeat=repeat,
                    time_scale=time_scale,
                    max_joint_speed_rad_s=DEFAULT_MAX_JOINT_SPEED_RAD_S,
                )
            state = robot.get_servo_state()
            if state != SERVO_RUNNING:
                raise RuntimeError(
                    f"CR3 entered servo state {state} after workflow task {index}; "
                    "remaining tasks were not started"
                )
        LOGGER.info("Workflow completed successfully")
    except KeyboardInterrupt:
        LOGGER.info("Workflow interrupted by operator")
    except Exception:
        LOGGER.exception("Workflow failed; later tasks will not be started")
        exit_code = 1
    finally:
        if servo_opened:
            try:
                if robot.get_servo_state() == SERVO_RUNNING:
                    _move_to_initial_position(
                        robot,
                        hand_api,
                        DEFAULT_INITIAL_MOVE_DURATION_S,
                        MAX_JOINT_TARGET_SPEED_RAD_S,
                    )
                else:
                    LOGGER.error("Skipping final home move because CR3 is not in running state")
                    cleanup_failed = True
            except Exception:
                LOGGER.exception("Failed to return CR3/O6 to the initial position")
                cleanup_failed = True
            try:
                robot.close_servoj()
            except Exception:
                LOGGER.exception("Failed to close CR3 ServoJ")
                cleanup_failed = True
        if cameras is not None:
            try:
                cameras.disconnect()
            except Exception:
                LOGGER.exception("Failed to disconnect D435 cameras")
                cleanup_failed = True
        if hand_api is not None:
            _close_hand(hand_api)
        if powered_by_workflow:
            try:
                if robot.get_servo_state() == SERVO_RUNNING:
                    robot.power_off()
                else:
                    LOGGER.error("Skipping power-off because CR3 is not in running state")
                    cleanup_failed = True
            except Exception:
                LOGGER.exception("Failed to power off CR3 at workflow end")
                cleanup_failed = True
        try:
            robot.disconnect()
        except Exception:
            LOGGER.exception("Failed to disconnect CR3")
            cleanup_failed = True

    if cleanup_failed and exit_code == 0:
        LOGGER.error("Workflow cleanup failed")
        exit_code = 1
    return exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Hardware profile TOML")
    parser.add_argument("--host", default=DEFAULT_POLICY_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_POLICY_PORT)
    parser.add_argument("--plan-json", required=True, help="JSON workflow plan")
    parser.add_argument("--confirm-motion", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.confirm_motion:
        raise SystemExit("Real robot workflow requires --confirm-motion")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    try:
        tasks = _validate_plan(json.loads(args.plan_json))
        return run_workflow(
            tasks=tasks,
            config_path=args.config,
            policy_host=args.host,
            policy_port=args.port,
        )
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        LOGGER.exception("Invalid or failed workflow")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
