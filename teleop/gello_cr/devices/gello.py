"""GELLO master-device adapter.

This module owns all GELLO/Dynamixel-specific import and I/O details.  The rest
of the application consumes only ``MasterDevice`` snapshots.

Important semantic detail:
- GELLO channels 1..6 are arm joint angles in radians.
- GELLO channel 7 is mapped by ``DynamixelRobot`` into a normalized
  gripper scalar in [0, 1]; it is therefore exposed as ``auxiliary["gripper"]``
  rather than pretending to be a seventh radian joint.

``software_root`` is a transitional compatibility hook for the current nested
GELLO checkout.  It is deliberately configuration-driven; no machine-specific
absolute path is embedded here.  A later dependency-cleanup phase can install
the GELLO package normally and set ``software_root=None``.
"""

from __future__ import annotations

import logging
import math
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teleop.gello_cr.core.contracts import JointState, MasterSnapshot

RobotFactory = Callable[..., Any]

_ARM_JOINT_NAMES = ("j1", "j2", "j3", "j4", "j5", "j6")


def _require_gello_source(root: Path) -> None:
    """Refuse mixed cached sources without replacing live device modules."""
    package_root = root / "gello"
    for name, module in tuple(sys.modules.items()):
        if name != "gello" and not name.startswith("gello."):
            continue
        paths = ([module.__file__] if getattr(module, "__file__", None) else [])
        paths.extend(getattr(module, "__path__", ()))
        if not paths or any(
            not Path(path).resolve().is_relative_to(package_root) for path in paths
        ):
            raise RuntimeError(
                f"GELLO 源码来源冲突：{name} 已从 {', '.join(map(str, paths)) or '未知路径'} 加载；"
                f"当前配置要求 {package_root}。请退出工作台并重新启动，避免混用已加载设备模块。"
            )


@dataclass(frozen=True, slots=True)
class GelloConfig:
    """Configuration required only by the GELLO device adapter."""

    port: str
    joint_ids: tuple[int, int, int, int, int, int]
    joint_offsets: tuple[float, float, float, float, float, float]
    joint_signs: tuple[int, int, int, int, int, int]
    gripper_config: tuple[int, float, float]
    baudrate: int = 57600
    feedback_hz: float = 100.0
    feedback_timeout_s: float = 0.5
    software_root: str | None = None

    def __post_init__(self) -> None:
        if not self.port.strip():
            raise ValueError("GELLO port cannot be empty")
        if len(self.joint_ids) != 6:
            raise ValueError("GELLO joint_ids must contain J1..J6")
        if len(set(self.joint_ids)) != 6:
            raise ValueError("GELLO joint_ids must be unique")
        if any(value <= 0 for value in self.joint_ids):
            raise ValueError("GELLO joint_ids must be positive")
        if len(self.joint_offsets) != 6:
            raise ValueError("GELLO joint_offsets must contain six values")
        if any(not math.isfinite(value) for value in self.joint_offsets):
            raise ValueError("GELLO joint_offsets must be finite")
        if len(self.joint_signs) != 6 or any(value not in (-1, 1) for value in self.joint_signs):
            raise ValueError("GELLO joint_signs must contain six values of -1 or +1")
        if len(self.gripper_config) != 3:
            raise ValueError("GELLO gripper_config must be (id, open_deg, close_deg)")
        gripper_id, open_deg, close_deg = self.gripper_config
        if int(gripper_id) <= 0:
            raise ValueError("GELLO gripper id must be positive")
        if int(gripper_id) in self.joint_ids:
            raise ValueError("GELLO gripper id must not duplicate an arm joint id")
        if not math.isfinite(float(open_deg)) or not math.isfinite(float(close_deg)):
            raise ValueError("GELLO gripper endpoints must be finite")
        if float(open_deg) == float(close_deg):
            raise ValueError("GELLO gripper endpoints must be different")
        if self.baudrate <= 0:
            raise ValueError("GELLO baudrate must be positive")
        if not math.isfinite(self.feedback_hz) or self.feedback_hz <= 0:
            raise ValueError("GELLO feedback_hz must be positive")
        if not math.isfinite(self.feedback_timeout_s) or self.feedback_timeout_s <= 0:
            raise ValueError("GELLO feedback_timeout_s must be positive")


class GelloDevice:
    """Read-only GELLO adapter implementing the master-device contract."""

    def __init__(
        self,
        config: GelloConfig,
        *,
        robot_factory: RobotFactory | None = None,
    ) -> None:
        self.config = config
        self._robot_factory = robot_factory
        self._robot: Any = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self._latest: MasterSnapshot | None = None
        self._error = ""

    @property
    def io_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def connected(self) -> bool:
        return self.io_alive and not self.error

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def latest(self) -> MasterSnapshot | None:
        with self._lock:
            return self._latest

    def feedback_age_s(self) -> float | None:
        latest = self.latest()
        if latest is None:
            return None
        return max(0.0, time.monotonic() - latest.timestamp)

    def feedback_fresh(self) -> bool:
        age = self.feedback_age_s()
        return age is not None and age <= self.config.feedback_timeout_s

    def connect(self, timeout: float = 5.0) -> MasterSnapshot:
        if timeout <= 0:
            raise ValueError("GELLO connect timeout must be positive")

        if self.connected:
            latest = self.latest()
            if latest is None:
                raise RuntimeError("GELLO is connected but has no feedback")
            return latest

        self.close()

        factory = self._robot_factory or self._load_robot_factory()
        try:
            self._robot = factory(
                joint_ids=self.config.joint_ids,
                joint_offsets=self.config.joint_offsets,
                joint_signs=self.config.joint_signs,
                real=True,
                port=self.config.port,
                baudrate=self.config.baudrate,
                gripper_config=self.config.gripper_config,
            )
        except Exception:
            self._robot = None
            raise

        self._stop.clear()
        self._ready.clear()
        with self._lock:
            self._latest = None
            self._error = ""

        self._thread = threading.Thread(
            target=self._run,
            name="GELLO-Feedback",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(timeout):
            error = self.error or "GELLO feedback startup timed out"
            self.close()
            raise TimeoutError(error)

        if self.error:
            error = self.error
            self.close()
            raise RuntimeError(error)

        latest = self.latest()
        if latest is None:
            self.close()
            raise RuntimeError("GELLO produced no valid feedback")
        return latest

    def close(self) -> None:
        self._stop.set()

        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            raise TimeoutError("GELLO feedback thread did not exit")

        robot = self._robot
        self._robot = None
        self._thread = None

        if robot is not None:
            robot.close()

    def _load_robot_factory(self) -> RobotFactory:
        """Load the current nested GELLO implementation without hardcoded paths."""

        if self.config.software_root:
            root = Path(self.config.software_root).expanduser().resolve()
            if not root.is_dir():
                raise FileNotFoundError(f"GELLO software_root does not exist: {root}")
            _require_gello_source(root)
            root_text = str(root)
            # A Conda/site-packages entry may precede a previously added root.
            # Make an explicit source authoritative even when already present.
            while root_text in sys.path:
                sys.path.remove(root_text)
            sys.path.insert(0, root_text)

        try:
            from gello.robots.dynamixel import DynamixelRobot
        except Exception as exc:
            raise RuntimeError(
                "Unable to import gello.robots.dynamixel.DynamixelRobot. "
                "Install GELLO or configure gello.software_root."
            ) from exc

        if self.config.software_root:
            _require_gello_source(root)

        if not callable(getattr(DynamixelRobot, "get_joint_state_sample", None)):
            raise RuntimeError(
                "GELLO SDK must expose get_joint_state_sample() with physical bus timestamps; "
                "use the bundled vendor/gello SDK or update the configured software_root."
            )
        logging.getLogger("workbench.hardware").info(
            "GELLO source: %s; Python: %s",
            getattr(sys.modules.get("gello.robots.dynamixel"), "__file__", "installed package"),
            sys.executable,
        )
        return DynamixelRobot

    def _run(self) -> None:
        period = 1.0 / self.config.feedback_hz
        next_cycle = time.monotonic()

        try:
            while not self._stop.is_set():
                sample_reader = getattr(self._robot, "get_joint_state_sample", None)
                if not callable(sample_reader):
                    raise RuntimeError(
                        "GELLO SDK lacks get_joint_state_sample() with physical bus timestamps"
                    )
                sample = sample_reader()
                if sample is None:
                    self._stop.wait(period)
                    continue
                raw, timestamp = sample
                timestamp = float(timestamp)
                now = time.monotonic()
                if not math.isfinite(timestamp) or timestamp > now:
                    raise RuntimeError("GELLO physical sample timestamp is invalid")
                if now - timestamp > self.config.feedback_timeout_s:
                    raise RuntimeError("GELLO physical sample timed out")
                values = tuple(float(value) for value in raw)

                if len(values) != 7:
                    raise RuntimeError(f"GELLO feedback must contain 7 values, got {len(values)}")
                if any(not math.isfinite(value) for value in values):
                    raise RuntimeError("GELLO feedback contains non-finite values")

                arm = values[:6]
                gripper = float(values[6])

                snapshot = MasterSnapshot(
                    timestamp=timestamp,
                    joints=JointState(
                        timestamp=timestamp,
                        names=_ARM_JOINT_NAMES,
                        positions_rad=arm,
                    ),
                    auxiliary={"gripper": gripper},
                )

                with self._lock:
                    self._latest = snapshot
                self._ready.set()

                next_cycle += period
                wait_time = next_cycle - time.monotonic()
                if wait_time > 0:
                    self._stop.wait(wait_time)
                else:
                    next_cycle = time.monotonic()
        except Exception as exc:
            if not self._stop.is_set():
                with self._lock:
                    self._error = f"GELLO feedback thread failed: {type(exc).__name__}: {exc}"
                self._ready.set()


@dataclass(frozen=True)
class GelloFeedback:
    """Joint and auxiliary feedback consumed by motion controllers."""

    timestamp: float
    joints_rad: tuple[float, float, float, float, float, float, float]

    @property
    def arm_joints_rad(self) -> tuple[float, float, float, float, float, float]:
        return self.joints_rad[:6]

    @property
    def gripper(self) -> float:
        return float(self.joints_rad[6])

    @property
    def joints(self) -> tuple[float, float, float, float]:
        return self.joints_rad[:4]


class GelloController:
    """Expose GELLO joint feedback using the device snapshot contract."""

    master_type = "gello"
    passive = True

    def __init__(
        self,
        port: str,
        software_root: str,
        joint_ids: Sequence[int],
        joint_offsets: Sequence[float],
        joint_signs: Sequence[int],
        gripper_config: Sequence[float],
        baudrate: int = 57600,
        feedback_hz: float = 20.0,
        feedback_timeout_s: float = 0.5,
    ):
        self.port = str(port)
        self.software_root = str(software_root)
        self.joint_ids = tuple(int(value) for value in joint_ids)
        self.joint_offsets = tuple(float(value) for value in joint_offsets)
        self.joint_signs = tuple(int(value) for value in joint_signs)
        self.gripper_config = tuple(gripper_config)
        self.baudrate = int(baudrate)
        self.feedback_hz = float(feedback_hz)
        self.feedback_timeout_s = float(feedback_timeout_s)

        if len(self.gripper_config) != 3:
            raise ValueError("GELLO gripper_config 必须包含 ID/open/close 三个值")

        config = GelloConfig(
            port=self.port,
            software_root=self.software_root,
            joint_ids=self.joint_ids,
            joint_offsets=self.joint_offsets,
            joint_signs=self.joint_signs,
            gripper_config=(
                int(self.gripper_config[0]),
                float(self.gripper_config[1]),
                float(self.gripper_config[2]),
            ),
            baudrate=self.baudrate,
            feedback_hz=self.feedback_hz,
            feedback_timeout_s=self.feedback_timeout_s,
        )
        self._device = GelloDevice(config)

    @property
    def io_alive(self) -> bool:
        return self._device.io_alive

    @property
    def connected(self) -> bool:
        return self._device.connected

    @property
    def error(self) -> str:
        return self._device.error

    @staticmethod
    def _feedback_from_snapshot(snapshot: Any) -> GelloFeedback:
        arm = tuple(float(value) for value in snapshot.joints.positions_rad)
        if len(arm) != 6:
            raise RuntimeError("GELLO arm feedback must contain 6 joints")
        try:
            gripper = float(snapshot.auxiliary["gripper"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("GELLO feedback is missing auxiliary gripper") from exc
        return GelloFeedback(
            timestamp=float(snapshot.timestamp),
            joints_rad=(
                arm[0],
                arm[1],
                arm[2],
                arm[3],
                arm[4],
                arm[5],
                gripper,
            ),
        )

    def latest(self) -> GelloFeedback | None:
        snapshot = self._device.latest()
        if snapshot is None:
            return None
        return self._feedback_from_snapshot(snapshot)

    def connect(self, timeout: float = 5.0) -> GelloFeedback:
        return self._feedback_from_snapshot(self._device.connect(timeout=float(timeout)))

    def close(self, hold: bool = False) -> None:
        del hold
        self._device.close()
