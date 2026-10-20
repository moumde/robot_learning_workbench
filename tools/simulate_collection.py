#!/usr/bin/env python3
"""Exercise the real Qt/teleop/recorder stack with explicitly simulated devices.

Run the parent composition with the UI Python and existing writer environments. No
device discovery or hardware constructor is used. Outputs are simulation data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from simulation_devices import SimulationRig  # noqa: E402

from core.hardware.cr3a import Cr3aDevice  # noqa: E402
from core.workbench.bootstrap.operator_app import build_operator_application  # noqa: E402
from core.workbench.bootstrap.runtime_factory import (  # noqa: E402
    RuntimeConstructors,
)
from core.workbench.composition import WorkbenchRuntimeFactory, workbench_paths  # noqa: E402
from core.workbench.core.state_machine import Command, WorkflowState  # noqa: E402
from core.workbench.recording.validation_service import validate_in_worker  # noqa: E402
from hmi.collection.command_port import CommandRequest  # noqa: E402
from hmi.collection.session import create_operator_window  # noqa: E402
from vendor.camera.d435.camera_interface import CR3O6CameraInterface  # noqa: E402
from vendor.nrc_interface.interface import CR3Interface  # noqa: E402


def resident_mb():
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return None


class SimulationRun:
    def __init__(self, args):
        self.args = args
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.report = {
            "simulation": True,
            "real_hardware_tested": False,
            "requested_healthy_recording_s": args.duration,
            "checks": [],
            "episodes": [],
            "datasets": [],
            "events": [],
            "samples": [],
            "unhandled_errors": [],
        }
        self.qt = QApplication.instance() or QApplication([])
        self.rig = SimulationRig()
        config = json.loads((ROOT / "config/teleop/gello_cr.json").read_text())
        config["robot"]["ip"] = "simulation.invalid"
        config["gello"]["port"] = "/simulation/gello"
        config["o6"]["port"] = "/simulation/o6"
        config["trajectory"]["root"] = str(self.output / "dataset/replay/trajectories")
        config["dataset"].update(
            root=str(self.output / "dataset/train"),
            staging_root=str(self.output / "dataset/staging"),
            task="SIMULATION ONLY - connectivity and stability",
            format="lerobot_v21",
            image_size=[224, 224],
            worker_python=args.hdf5_python,
            worker_pythons={
                "lerobot_v21": args.v21_python,
                "lerobot_v3": args.v3_python,
                "hdf5": args.hdf5_python,
            },
            camera_streams=[
                {"name": name, "serial": serial, "mode": "camera", "roi_norm": [0, 0, 1, 1]}
                for name, serial in zip(
                    ["Base RGB", "Wrist RGB", "Camera 3 RGB"],
                    ["SIM-BASE", "SIM-WRIST", "SIM-THIRD"],
                    strict=True,
                )
            ],
        )
        profile_path = self.output / "simulation_hardware.toml"
        hardware = (ROOT / "config/hardware/cr3_o6.toml").read_text()
        hardware = hardware.replace('ip = "192.168.2.14"', 'ip = "192.0.2.10"')
        hardware = hardware.replace('modbus = "/dev/ttyUSB0"', 'modbus = "/simulation/o6"')
        hardware = hardware.replace('width = 640', 'width = 224').replace('height = 480', 'height = 224')
        profile_path.write_text(hardware)
        config.setdefault("workbench", {})["hardware_config"] = str(profile_path)
        config_path = self.output / "simulation_config.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        constructors = replace(
            RuntimeConstructors.load_defaults(),
            GelloController=self.rig.master_constructor,
            O6Controller=self.rig.hand_constructor,
            Cr3aDevice=lambda config, **kw: Cr3aDevice(config, api=self.rig.api, **kw),
            RealSenseRgbDevice=lambda config: self.rig.camera_constructor(
                replace(config, width=224, height=224)
            ),
        )
        self.baseline_threads = {t.ident for t in threading.enumerate()}
        self.rig.start()
        factory = WorkbenchRuntimeFactory(
            workbench_paths(ROOT, config_path=config_path),
            hardware_config=profile_path,
            constructors=constructors,
        )
        self.app = build_operator_application(ROOT, factory=factory)
        self.service = self.app.backend.service
        self.recorder = self.app.runtime.recorder
        self.engine = self.app.runtime.teleop_engine
        self.service.subscribe(
            lambda event: self.report["events"].append(
                {
                    "sequence": event.sequence,
                    "kind": event.kind,
                    "level": event.level.value,
                    "state": event.state.name,
                    "message": event.message,
                    "command": event.command.name if event.command else None,
                    "elapsed_s": time.monotonic() - self.started,
                }
            )
        )
        self.window = create_operator_window(self.app.backend, refresh_ms=100)
        self.window.setWindowTitle("SIMULATION ONLY - Robot Learning Workbench")
        self.window.collection.task_edit.setText(config["dataset"]["task"])
        self.window.collection.root_edit.setText(config["dataset"]["root"])
        self.window.show()
        self.heartbeat_gaps = []
        self.last_heartbeat = time.monotonic()
        self.heartbeat = QTimer()
        self.heartbeat.setInterval(20)
        self.heartbeat.timeout.connect(self.beat)
        self.heartbeat.start()
        self.next_sample = self.started
        self.next_progress = self.started
        self.task = config["dataset"]["task"]
        self.payload = {
            "task": self.task,
            "base_root": config["dataset"]["root"],
            "source": "teleop",
            "description": "SIMULATED hardware, no real robot",
        }

    def beat(self):
        now = time.monotonic()
        self.heartbeat_gaps.append(now - self.last_heartbeat)
        self.last_heartbeat = now

    def check(self, condition, message, **details):
        self.report["checks"].append({"passed": bool(condition), "message": message, **details})
        if not condition:
            raise AssertionError(message + " " + repr(details))

    def pump(self):
        self.qt.processEvents()
        now = time.monotonic()
        if now >= self.next_sample:
            rec = self.recorder.snapshot()
            sample = {
                "elapsed_s": now - self.started,
                "rss_mb": resident_mb(),
                "threads": threading.active_count(),
                "workflow": self.service.state.name,
                "runtime": self.engine.state,
                "frames": rec["buffered_frames"],
                "recording": rec["episode_active"],
                "error": rec["error"],
            }
            self.report["samples"].append(sample)
            self.next_sample = now + 1
        if now >= self.next_progress:
            print(
                json.dumps({"progress": self.report["samples"][-1]}, ensure_ascii=False), flush=True
            )
            self.next_progress = now + 15
        if self.report["unhandled_errors"]:
            raise RuntimeError(
                "Unhandled Qt/worker exception: " + str(self.report["unhandled_errors"])
            )
        time.sleep(0.003)

    def wait(self, condition, timeout=10, message="condition timed out"):
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() >= deadline:
                raise TimeoutError(message)
            self.pump()

    def run_for(self, seconds, *, healthy=False):
        start_frames = self.recorder.snapshot()["buffered_frames"]
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.pump()
            if healthy:
                rec = self.recorder.snapshot()
                if self.engine.state != "following" or not rec["episode_active"] or rec["error"]:
                    raise AssertionError(
                        f"Healthy run interrupted: {self.engine.snapshot()} / {rec}"
                    )
        if healthy:
            rec = self.recorder.snapshot()
            count = rec["buffered_frames"] - start_frames
            self.check(
                count >= seconds * 20 * 0.85 - 1,
                "Recording keeps up with configured 20 FPS",
                seconds=seconds,
                frames=count,
                effective_fps=rec["quality"]["effective_fps"],
            )

    def command(self, command, payload=None, timeout=180):
        self.wait(
            lambda: self.service.can(command, payload),
            timeout=5,
            message=f"{command.name} denied: {self.service.permission(command, payload).reason}",
        )
        sequence = self.service.snapshot().event_sequence
        started = time.monotonic()
        self.app.backend.command_port.submit(CommandRequest.create(command, payload))
        self.wait(
            lambda: command not in self.app.backend.command_port.pending_commands,
            timeout=timeout,
            message=f"{command.name} did not complete",
        )
        events = [
            e
            for e in self.report["events"]
            if e["sequence"] > sequence and e["command"] == command.name
        ]
        self.check(
            any(e["kind"] == "command_completed" for e in events)
            and not any(e["kind"] in ("command_failed", "command_rejected") for e in events),
            command.name + " completed",
            elapsed_s=time.monotonic() - started,
            events=events,
        )

    def start_follow(self):
        self.rig.motion_enabled = False
        self.command(Command.START_TELEOP)
        self.rig.motion_enabled = True
        self.wait(
            lambda: (self.engine.snapshot().get("gello_telemetry") or {}).get("sent_count", 0),
            message="Teleop did not publish its first accepted target",
        )

    def finish(self, *, outcome="success", label="healthy"):
        before = self.recorder.snapshot()
        self.command(Command.FINISH_EPISODE, {"outcome": outcome, "notes": "SIMULATION " + label})
        after = self.recorder.snapshot()
        self.report["episodes"].append(
            {
                "label": label,
                "format": before["format"],
                "outcome": outcome,
                "frames": after["last_saved"]["frame_count"],
                "quality": after["last_saved"]["quality"],
                "saved": after["last_saved"],
            }
        )
        self.check(not after["episode_pending"], "Episode resolved after save")

    def dataset(self):
        self.command(Command.FINALIZE_DATASET)
        snapshot = self.recorder.snapshot()
        root = Path(snapshot["root"])
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="Simulation-Validation") as pool:
            future = pool.submit(
                validate_in_worker, snapshot["format"], root, self.recorder.writer_factory
            )
            self.wait(future.done, timeout=180, message="Dataset readback validation timed out")
            validation = future.result()
        self.report["datasets"].append(
            {"root": str(root), "format": snapshot["format"], "validation": validation}
        )
        self.check(validation["valid"], "Finalized dataset is readable", **validation)
        episodes = [e for e in self.report["episodes"] if e["format"] == snapshot["format"]]
        self.check(
            validation["episode_count"] == len(episodes)
            and validation["frame_count"] == sum(e["frames"] for e in episodes),
            "Finalized episode/frame totals equal saved episodes; discarded data excluded",
            **validation,
        )

    def safe_idle(self):
        self.rig.motion_enabled = False
        self.command(Command.STOP_MOTION)

    def test(self):
        for command in (Command.POWER_ON, Command.START_TELEOP, Command.START_EPISODE):
            self.check(
                not self.service.can(command, self.payload),
                command.name + " blocked while disconnected",
            )
        self.command(Command.CONNECT)
        self.check(not self.service.can(Command.START_TELEOP), "Teleop blocked before Servo ON")
        self.command(Command.POWER_ON)
        self.command(Command.PREPARE_DEVICES)
        self.command(Command.START_CAMERAS)
        self.wait(lambda: self.app.readiness.snapshot().get("camera_frames_ready"))
        groups = {id(view.group) for view in self.app.runtime.camera_devices.values()}
        group = next(iter(self.app.runtime.camera_devices.values())).group
        self.check(len(groups) == 1 and isinstance(group.interface, CR3O6CameraInterface),
                   "Collection uses one parent camera interface")
        self.check(isinstance(self.app.runtime.cr3a_lifecycle.device.backend, CR3Interface),
                   "Collection uses the parent robot connection owner")
        self.start_follow()
        self.command(Command.CREATE_DATASET, self.payload)
        healthy_start = time.monotonic()
        sampling_start = self.rig.sample_count
        sends_start = self.rig.api.send_count
        camera_start = [c.frame_count for c in self.rig.cameras]
        recording_s = 0.0
        for index in range(3):
            self.command(Command.START_EPISODE, self.payload)
            for command in (
                Command.RETURN_HOME,
                Command.DISCONNECT,
                Command.PREPARE_DEVICES,
                Command.SELECT_DATASET_FORMAT,
                Command.STOP_CAMERAS,
            ):
                self.check(
                    not self.service.can(command, {"format": "hdf5"}),
                    command.name + " locked during recording",
                )
            episode_start = time.monotonic()
            self.run_for(self.args.duration / 3, healthy=True)
            recording_s += time.monotonic() - episode_start
            if index == 0:
                self.window.grab().save(str(self.output / "recording.png"))
            self.finish(label=f"healthy-{index + 1}")
        self.report["healthy_recording_wall_s"] = time.monotonic() - healthy_start
        self.report["healthy_recording_s"] = recording_s
        elapsed = time.monotonic() - healthy_start
        self.report["healthy_signals"] = {
            "elapsed_including_episode_save_s": elapsed,
            "sample_hz": (self.rig.sample_count - sampling_start) / elapsed,
            "motion_commands": self.rig.api.send_count - sends_start,
            "camera_hz": [
                (c.frame_count - count) / elapsed
                for c, count in zip(self.rig.cameras, camera_start, strict=True)
            ],
        }
        self.command(Command.START_EPISODE, self.payload)
        self.run_for(3, healthy=True)
        saved = self.recorder.snapshot()["saved_episodes"]
        self.command(Command.DISCARD_EPISODE)
        self.check(
            self.recorder.snapshot()["saved_episodes"] == saved,
            "Discard does not add a saved episode",
        )

        # A failed input must stop following, and signal restoration alone must not resume it.
        self.command(Command.START_EPISODE, self.payload)
        self.run_for(2, healthy=True)
        self.rig.master_online = False
        lost_at = time.monotonic()
        self.wait(
            lambda: self.service.state is WorkflowState.FAULT,
            message="GELLO loss did not propagate to workflow/UI",
        )
        self.check(
            self.engine.state == "fault",
            "GELLO loss stops teleop",
            detection_s=time.monotonic() - lost_at,
        )
        self.window.grab().save(str(self.output / "gello_fault.png"))
        self.check(
            not self.service.can(Command.RESET_FAULT), "Pending recording blocks fault reset"
        )
        self.finish(outcome="failure", label="GELLO signal loss")
        self.rig.motion_enabled = False
        self.rig.master_online = True
        self.run_for(0.6)
        self.check(self.engine.state != "following", "GELLO restoration does not auto-follow")
        self.command(Command.RESET_FAULT)
        self.command(Command.PREPARE_DEVICES)
        self.start_follow()

        self.command(Command.START_EPISODE, self.payload)
        self.run_for(2, healthy=True)
        self.rig.cameras_online = False
        lost_at = time.monotonic()
        self.wait(
            lambda: bool(self.recorder.snapshot()["error"]),
            message="Camera loss did not reach recorder",
        )
        self.wait(lambda: not self.recorder.snapshot()["episode_active"])
        self.window.refresh_from_presenter()
        self.check(
            not self.app.readiness.snapshot()["camera_frames_ready"],
            "Camera fault is visible and recording stopped",
            detection_s=time.monotonic() - lost_at,
            error=self.recorder.snapshot()["error"],
        )
        self.window.grab().save(str(self.output / "camera_fault.png"))
        self.command(Command.DISCARD_EPISODE)
        if self.service.can(Command.STOP_CAMERAS):
            self.command(Command.STOP_CAMERAS)
        self.rig.cameras_online = True
        self.command(Command.START_CAMERAS)
        self.wait(lambda: self.app.readiness.snapshot().get("camera_frames_ready"))
        self.command(Command.START_EPISODE, self.payload)
        self.run_for(2, healthy=True)
        self.finish(label="camera recovery")

        self.rig.robot_online = False
        lost_at = time.monotonic()
        self.wait(
            lambda: self.service.state is WorkflowState.FAULT,
            message="Robot loss did not reach workflow",
        )
        self.check(
            self.engine.state == "fault",
            "Robot disconnect stops teleop",
            detection_s=time.monotonic() - lost_at,
        )
        self.rig.motion_enabled = False
        self.rig.robot_online = True
        self.run_for(0.6)
        self.check(self.engine.state != "following", "Robot restoration does not auto-follow")
        self.command(Command.DISCONNECT)
        self.command(Command.CONNECT)
        self.check(
            self.service.state is WorkflowState.CONNECTED,
            "Reconnected robot requires explicit Servo ON",
        )
        self.command(Command.POWER_ON)
        self.start_follow()
        self.rig.hand_online = False
        lost_at = time.monotonic()
        self.wait(
            lambda: self.service.state is WorkflowState.FAULT, message="O6 loss did not stop teleop"
        )
        self.check(
            self.engine.state == "fault",
            "O6 disconnect stops teleop",
            detection_s=time.monotonic() - lost_at,
        )
        self.rig.motion_enabled = False
        self.rig.hand_online = True
        self.command(Command.RESET_FAULT)
        self.command(Command.PREPARE_DEVICES)
        self.start_follow()
        self.command(Command.START_EPISODE, self.payload)
        self.run_for(2, healthy=True)
        stopped_at = time.monotonic()
        self.command(Command.EMERGENCY_STOP)
        self.check(
            self.service.state is WorkflowState.ESTOP and self.engine.state != "following",
            "Software emergency stop preempts recording teleop",
            elapsed_s=time.monotonic() - stopped_at,
        )
        self.finish(outcome="failure", label="software emergency stop")
        self.rig.motion_enabled = False
        self.command(Command.RESET_ESTOP)
        self.check(self.engine.state == "idle", "Emergency reset leaves motion idle")
        self.dataset()

        # The same recording flow must work in the other real writer environments.
        self.start_follow()
        for format_name in ("hdf5", "lerobot_v3"):
            self.command(Command.SELECT_DATASET_FORMAT, {"format": format_name})
            self.command(Command.CREATE_DATASET, self.payload)
            self.command(Command.START_EPISODE, self.payload)
            self.run_for(3, healthy=True)
            self.finish(label=format_name)
            self.dataset()
        self.safe_idle()
        for _ in range(3):
            self.command(Command.POWER_OFF)
            self.command(Command.DISCONNECT)
            self.command(Command.CONNECT)
            self.command(Command.POWER_ON)
        self.command(Command.POWER_OFF)
        self.command(Command.DISCONNECT)

    def close(self):
        self.window._timer.stop()
        self.heartbeat.stop()
        try:
            self.app.close()
        finally:
            self.rig.close()
            self.window.hide()
        time.sleep(0.2)
        survivors = [
            t.name
            for t in threading.enumerate()
            if t.ident not in self.baseline_threads and t.is_alive()
        ]
        self.check(
            not survivors, "No application worker threads survive shutdown", threads=survivors
        )

    def save_report(self):
        gaps = sorted(self.heartbeat_gaps)
        self.report["ui_heartbeat"] = {
            "interval_s": 0.02,
            "ticks": len(gaps),
            "max_gap_s": max(gaps, default=0),
            "p95_gap_s": gaps[int((len(gaps) - 1) * 0.95)] if gaps else None,
        }
        self.report["total_wall_s"] = time.monotonic() - self.started
        self.report["simulated_sdk"] = {
            name: getattr(self.rig.api, name)
            for name in (
                "connect_count",
                "disconnect_count",
                "send_count",
                "movej_count",
                "stop_count",
                "power_on_count",
            )
        }
        self.report["passed"] = (
            not self.report.get("failure")
            and all(c["passed"] for c in self.report["checks"])
            and not self.report["unhandled_errors"]
        )
        (self.output / "report.json").write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2, default=str)
        )
        print(
            json.dumps(
                {
                    "passed": self.report["passed"],
                    "report": str(self.output / "report.json"),
                    "failure": self.report.get("failure"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration",
        type=float,
        default=300,
        help="Total healthy recording seconds across three episodes",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--v21-python", required=True)
    parser.add_argument("--v3-python", required=True)
    parser.add_argument("--hdf5-python", default=sys.executable)
    args = parser.parse_args()
    for name in ("v21_python", "v3_python", "hdf5_python"):
        setattr(args, name, os.path.abspath(os.path.expanduser(getattr(args, name))))
    if args.duration <= 0:
        parser.error("duration must be positive")
    run = SimulationRun(args)
    original_hook = sys.excepthook
    original_thread_hook = threading.excepthook
    sys.excepthook = lambda *info: run.report["unhandled_errors"].append(
        "".join(traceback.format_exception(*info))
    )
    threading.excepthook = lambda info: run.report["unhandled_errors"].append(
        "".join(traceback.format_exception(info.exc_type, info.exc_value, info.exc_traceback))
    )
    try:
        run.test()
    except Exception:
        run.report["failure"] = traceback.format_exc()
        print(run.report["failure"], flush=True)
        # Resolve only simulated data in this isolated test output before cleanup.
        try:
            run.engine.stop_motion("simulation cleanup")
            run.recorder.stop_episode()
            if run.recorder.snapshot().get("episode_pending"):
                run.recorder.discard_episode()
        except Exception:
            run.report["cleanup_failure"] = traceback.format_exc()
    finally:
        try:
            run.close()
        except Exception:
            run.report["failure"] = run.report.get("failure", "") + traceback.format_exc()
        run.save_report()
        sys.excepthook = original_hook
        threading.excepthook = original_thread_hook
    return 0 if run.report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
