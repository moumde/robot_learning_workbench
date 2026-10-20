"""Load adapters and invoke the shared trajectory player. Preview is the default."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from core.workbench.paths import workbench_root
from core.workbench.trajectory import ReplayMode, ReplayOptions, TrajectoryStore, preview_trajectory
from core.workbench.trajectory.adapters import LegacyJsonAdapter, LeRobotTrajectoryAdapter
from core.workbench.trajectory.validation import (
    validate_options,
    validate_replay_channels,
    validate_replay_speed,
    validate_trajectory,
)


def _joints(value):
    try:
        indices = [int(item) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use joint numbers such as 1,2,6") from exc
    if not indices or any(i not in range(1, 7) for i in indices):
        raise argparse.ArgumentTypeError("Joint numbers must be between 1 and 6")
    return tuple(i in indices for i in range(1, 7))


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", type=Path, help="Trajectory directory, legacy JSON, or LeRobot dataset/Parquet"
    )
    parser.add_argument(
        "--source", choices=("auto", "trajectory", "legacy_json", "lerobot"), default="auto"
    )
    parser.add_argument("--episode-index", type=int, default=0)
    parser.add_argument("--mode", choices=("relative", "absolute"), default="relative")
    parser.add_argument("--time-scale", type=float, default=1.0)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--joints", type=_joints, help="Selected joints, e.g. 1,2,6; default uses imported mask"
    )
    parser.add_argument("--transition-s", type=float, default=3.0)
    channel = parser.add_mutually_exclusive_group()
    channel.add_argument("--arm-only", action="store_true")
    channel.add_argument("--hand-only", action="store_true")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--preview", action="store_true", help="Print numeric preview without hardware (default)"
    )
    action.add_argument(
        "--execute",
        action="store_true",
        help="Connect selected devices, enable the arm if selected, and play",
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--config", type=Path, help="Override the runtime JSON configuration")
    return parser


def _load(args):
    path = args.path.expanduser().resolve()
    source = args.source
    if source == "auto":
        if path.suffix.lower() == ".json":
            source = "legacy_json"
        elif (path / "meta.json").is_file() or path.name == "trajectory.parquet":
            source = "trajectory"
        else:
            source = "lerobot"
    if source == "legacy_json":
        return LegacyJsonAdapter.load(path)
    if source == "lerobot":
        return LeRobotTrajectoryAdapter.load(path, args.episode_index)
    directory = path.parent if path.is_file() else path
    return TrajectoryStore(directory.parent).load(directory.name)


def _execute(args, value, options, runtime_factory):
    from core.workbench.bootstrap.runtime_factory import ConcreteRuntimeFactory, RuntimeFactoryPaths

    validate_replay_channels(value, options)
    paths = RuntimeFactoryPaths.from_repo(args.repo_root, config_path=args.config)
    runtime = (runtime_factory or ConcreteRuntimeFactory)(paths).build()
    try:
        cfg = runtime.store.data
        validate_trajectory(value, cfg.get("motion", {}).get("joint_limits_rad"))
        limit = math.radians(float(cfg["replay"]["max_joint_speed_deg_s"]))
        validate_replay_speed(value, options, limit)
        if options.hand_enabled:
            runtime.o6_controller.connect()
            runtime.o6_controller.set_profile(cfg["o6"]["speed"], cfg["o6"]["torque"])
        if options.arm_enabled:
            runtime.cr3a_lifecycle.connect()
            runtime.cr3a_lifecycle.power_on()
        engine = runtime.teleop_engine
        engine.trajectory_source.check_ready(options.arm_enabled, options.hand_enabled)
        engine.trajectory_player.play(value, options, max_joint_speed_rad_s=limit)
    finally:
        runtime.close()


def main(argv=None, *, runtime_factory=None):
    parser = _parser()
    args, unknown = parser.parse_known_args(argv)
    parent_root = workbench_root(args.repo_root)
    if runtime_factory is None and (parent_root / "config/hardware.py").is_file():
        if str(parent_root) not in sys.path:
            sys.path.insert(0, str(parent_root))
        from core.workbench.replay import main as workbench_main

        original_args = sys.argv[1:] if argv is None else argv
        return workbench_main([*original_args, "--repo-root", str(parent_root)])
    if unknown:
        parser.error("unrecognized arguments: " + " ".join(unknown))
    try:
        options = ReplayOptions(
            mode=ReplayMode(args.mode),
            time_scale=args.time_scale,
            repeat=args.repeat,
            arm_enabled=not args.hand_only,
            hand_enabled=not args.arm_only,
            joint_mask=args.joints,
            transition_s=args.transition_s,
        )
        validate_options(options)
        value = _load(args)
        if not args.execute:
            print(json.dumps(preview_trajectory(value), ensure_ascii=False, indent=2))
            return 0
        _execute(args, value, options, runtime_factory)
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Replay failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
