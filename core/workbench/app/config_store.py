"""Teleoperation defaults and atomic configuration persistence."""

from __future__ import annotations

import copy
import json
import math
import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from core.hardware.camera_streams import resolve_camera_streams
from core.workbench.core.servo_limits import servo_limit_vector
from core.workbench.paths import workbench_root

GELLO_SDK_ROOT = workbench_root() / "vendor/gello"

ROARM_DEFAULT_PORT = (
    "/dev/serial/by-id/"
    "usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_"
    "36df624f63e4ee118642737d4c11a646-if00-port0"
)


O6_DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"


DEFAULT_CONFIG: dict[str, Any] = {
    "hardware": {"profile": "cr3a_o6", "name": "CR3A + O6"},
    "version": 1,
    "logging": {"level": "INFO"},
    "ui": {"refresh_ms": 100},
    "master": {
        "type": "gello",
    },
    "robot": {
        "ip": "192.168.1.245",
        "command_port": 6001,
        "servo_port": 7000,
        "robot_num": 1,
        "motion_mode": "servoj",
        "movej_velocity": 10.0,
        "movej_acc": 20.0,
        "movej_dec": 20.0,
        "movej_period_s": 0.1,
        "movej_low_latency": False,
        "movej_max_segment_deg": 2.0,
        "movej_duplicate_deadband_deg": 0.05,
        "safety_max_command_step_rad": math.radians(20.0),
        "safety_max_command_speed_rad_s": 0.8,
        "safety_speed_violation_cycles": 3,
        "safety_max_tracking_error_rad": math.radians(20.0),
        "servoj_vmax": 80.0,
        "servoj_amax": 200.0,
        "servoj_jmax": 150.0,
    },
    "roarm": {
        "port": ROARM_DEFAULT_PORT,
        "baudrate": 115200,
        "feedback_hz": 20.0,
        "feedback_timeout_s": 0.6,
        "m5_open_rad": 0.7977,
        "m5_closed_rad": 3.1447,
    },
    "inverse3": {
        "uri": "ws://127.0.0.1:10001",
        "device_id": "",
        "grip_device_id": "",
        "basis": "XYZ",
        "feedback_hz": 20.0,
        "feedback_timeout_s": 0.6,
    },
    "gello": {
        "port": "/dev/serial/by-id/usb-FTDI_USB__-__Serial_Converter_FTB6W7LM-if00-port0",
        "baudrate": 57600,
        "software_root": str(GELLO_SDK_ROOT),
        "control_mode": "joint",
        "joint_scale": 1.0,
        "kinematics_urdf": str(
            GELLO_SDK_ROOT / "gello/factr/urdf/yam_active_gello/robot.urdf"
        ),
        "xyz_axis_map": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "j6_sign": 1,
        "xyz_scale": [1.0, 1.0, 1.0],
        "joint_ids": [1, 2, 3, 4, 5, 6],
        "joint_offsets": [
            4.574337507945,
            3.060291671832,
            1.402049963022,
            1.363700443325,
            1.471087575582,
            2.994338975058,
        ],
        "joint_signs": [1, 1, -1, 1, 1, 1],
        "locked_joints": [],
        "gripper_config": [7, 200.478515625, 147.3046875],
        "feedback_hz": 100.0,
        "feedback_timeout_s": 0.5,
        "startup_settle_s": 0.5,
    },
    "o6": {
        "port": O6_DEFAULT_PORT,
        "baudrate": 115200,
        "hand_id": 0x27,
        "open": [253, 253, 253, 253, 253, 253],
        "closed": [90, 99, 50, 50, 50, 50],
        "speed": [20, 20, 20, 20, 20, 20],
        "torque": [30, 30, 30, 30, 30, 30],
        "command_deadband": 2,
        "feedback_timeout_s": 1.0,
        "action_timeout_s": 15.0,
        "open_action": "张开手",
        "closed_action": "抓取",
        "actions": {
            "张开手": [250, 250, 250, 250, 250, 250],
            "中指": [91, 132, 0, 250, 0, 0],
            "轻微抓取": [107, 90, 129, 250, 250, 250],
            "小拇指": [30, 250, 40, 40, 40, 250],
            "抓取": [78, 85, 123, 250, 250, 250],
        },
    },
    "teleop": {
        "scale_xyz": [2.0, 2.0, 2.0],
        "scale_rpy": [1.0, 1.0, 1.0],
        "max_delta_xyz_mm": [100.0, 100.0, 100.0],
        "max_delta_rpy_rad": [0.35, 0.35, 0.35],
        "max_tcp_speed_mm_s": 30.0,
        "max_tcp_angular_speed_rad_s": 0.1,
        "max_master_jump_mm": 35.0,
        "max_master_angular_jump_rad": 0.35,
        "period_s": 0.05,
    },
    "preset": {
        "robot_velocity_percent": 10.0,
        "robot_acc_percent": 20.0,
        "robot_dec_percent": 20.0,
        "timeout_s": 90.0,
    },
    "planning": {
        "joint_sample_hz": 100.0,
        "tcp_position_step_m": 0.002,
        "tcp_rotation_step_deg": 1.0,
        "default_speed_scale": 0.3,
        "max_joint_velocity_rad_s": 0.5,
        "max_joint_acceleration_rad_s2": 1.0,
        "max_linear_velocity_m_s": 0.03,
        "max_angular_velocity_rad_s": 0.1,
        "max_ik_step_rad": 0.35,
        "reached": {
            "joint_tolerance_deg": 0.5,
            "tcp_position_tolerance_mm": 2.0,
            "tcp_orientation_tolerance_deg": 1.0,
            "stable_samples": 5,
            "timeout_s": 10.0,
            "sample_period_s": 0.02,
        },
    },
    "trajectory": {"root": "../dataset/replay/trajectories"},
    "replay": {
        "servoj_period_s": 0.01,
        "mode_switch_settle_s": 0.2,
        "sample_period_s": 0.05,
        "max_duration_s": 300.0,
        "max_joint_speed_deg_s": 120.0,
    },
    "dataset": {
        "format": "lerobot_v3",
        "camera_poll_hz": 30.0,
        "staging_root": None,
        "recording_mode": "tcp",
        "root": "../dataset/train",
        "repo_prefix": "local/cr3_o6",
        "task": "Pick up the object and place it in the target container.",
        "fps": 20,
        "image_size": [480, 640],
        "camera_max_age_s": 0.5,
        "camera_max_skew_s": 0.1,
        "action_max_age_s": 0.25,
        "max_tracking_error_deg": 5.0,
        "wrist_camera_serial": "317222074617",
        "base_camera_serial": "254622075848",
        "base_roi_norm": [0.37, 0.56, 0.55, 0.79],
        "camera_streams": None,
        "worker_python": "~/miniconda3/envs/lerobot/bin/python",
        "worker_pythons": {},
        "video_codec": None,
        "hdf5_compression": None,
    },
    "shortcuts": {
        "prepare": "F5",
        "power_on": "Ctrl+F6",
        "start_follow": "F6",
        "stop_follow": "F7",
        "episode_start": "F8",
        "episode_save_next": "F9",
        "episode_discard_retry": "F10",
        "home": "F11",
        "emergency_stop": "F12",
        "o6_open": "1",
        "o6_grasp": "2",
        "o6_light_grasp": "3",
    },
    "presets": {},
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _six_uint8(values: Sequence[Any], name: str) -> list[int]:
    if len(values) != 6:
        raise ValueError(f"{name} 必须包含 6 个数值")
    converted = [int(round(float(value))) for value in values]
    if any(value < 0 or value > 255 for value in converted):
        raise ValueError(f"{name} 必须在 0..255 范围内")
    return converted


class TeleopConfigStore:
    """Load and atomically persist teleoperation settings and taught poses."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data = self.load()

    @classmethod
    def from_file(cls, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Workbench config missing: {path}. Copy your calibrated configuration "
                "to config/workbench.json; see docs/migration_v1.md."
            )
        return cls(path)

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                data = copy.deepcopy(DEFAULT_CONFIG)
                self._validate(data)
                return data
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"读取遥操作配置失败: {self.path}: {exc}") from exc
            data = _deep_merge(DEFAULT_CONFIG, loaded)
            # An explicitly saved action library is complete; deleted actions
            # must not reappear from defaults after restarting the editor.
            if "actions" in loaded.get("o6", {}):
                data["o6"]["actions"] = copy.deepcopy(loaded["o6"]["actions"])
            self._validate(data)
            return data

    def save(self) -> None:
        with self._lock:
            self._validate(self.data)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            temp_path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp_path, self.path)

    def update_runtime(self, values: dict[str, Any]) -> None:
        with self._lock:
            previous = self.data
            self.data = _deep_merge(self.data, values)
            try:
                self.save()
            except Exception:
                self.data = previous
                raise

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.path.parent / path
        return path.resolve()

    def _resolve_worker_python(self, value: str | Path) -> str:
        # Preserve the venv entry point: resolving its symlink selects the base Python.
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.path.parent / path
        return os.path.abspath(path)

    def deployment_data(self) -> dict[str, Any]:
        """Resolve deployment paths without saving environment overrides to disk."""
        data = copy.deepcopy(self.data)
        for group, key in (
            ("dataset", "root"),
            ("dataset", "staging_root"),
            ("trajectory", "root"),
            ("gello", "software_root"),
            ("gello", "kinematics_urdf"),
            ("robot", "sdk_root"),
        ):
            if data[group].get(key):
                data[group][key] = str(self.resolve_path(data[group][key]))
        if worker_python := data["dataset"].get("worker_python"):
            data["dataset"]["worker_python"] = self._resolve_worker_python(worker_python)
        data["dataset"]["worker_pythons"] = {
            key: self._resolve_worker_python(value)
            for key, value in data["dataset"].get("worker_pythons", {}).items()
        }
        if override := os.environ.get("GELLO_CR_DATA_PYTHON"):
            data["dataset"]["worker_python"] = self._resolve_worker_python(override)
        return data

    def _validate(self, data: dict[str, Any]) -> None:
        from core.workbench.recording.formats import DatasetFormat
        from core.workbench.trajectory.planner import TrajectoryPlanner
        from core.workbench.trajectory.planner.config import planning_config
        from core.workbench.trajectory.planner.validation import positive

        if data["hardware"]["profile"] != "cr3a_o6":
            raise ValueError("hardware.profile must be cr3a_o6")
        if data["logging"]["level"] not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("logging.level is invalid")
        refresh = data["ui"]["refresh_ms"]
        if isinstance(refresh, bool) or not isinstance(refresh, int) or refresh < 20:
            raise ValueError("ui.refresh_ms must be an integer >= 20")
        for group, key in (
            ("dataset", "camera_poll_hz"),
            ("gello", "feedback_hz"),
            ("inverse3", "feedback_hz"),
            ("roarm", "feedback_hz"),
            ("teleop", "period_s"),
            ("robot", "movej_period_s"),
        ):
            rate = float(data[group][key])
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError(f"{group}.{key} must be positive and finite")
        for value in (
            data["dataset"]["root"],
            data["dataset"].get("staging_root"),
            data["trajectory"]["root"],
        ):
            if value and self.resolve_path(value).is_file():
                raise ValueError(f"Output directory is a file: {value}")
        for port in (data["robot"]["command_port"], data["robot"]["servo_port"]):
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError("Robot ports must be integers in 1..65535")
        model, settings, _ = planning_config(data)
        TrajectoryPlanner(model, settings=settings)
        planning = data["planning"]
        scale = positive(float(planning["default_speed_scale"]), "default_speed_scale")
        if scale > 1:
            raise ValueError("default_speed_scale must be <= 1")
        for field in ("max_linear_velocity_m_s", "max_angular_velocity_rad_s"):
            positive(float(planning[field]), field)
        DatasetFormat(data["dataset"]["format"])
        if data["dataset"].get("hdf5_compression") not in (None, "gzip", "lzf"):
            raise ValueError("HDF5 compression must be gzip, lzf or null")
        master_type = data["master"]["type"]
        if master_type not in ("roarm", "inverse3", "gello"):
            raise ValueError("主臂类型必须是 roarm、inverse3 或 gello")
        robot_num = data["robot"]["robot_num"]
        if isinstance(robot_num, bool) or not isinstance(robot_num, int) or not 1 <= robot_num <= 4:
            raise ValueError("NRC robot_num 必须是 1～4 的整数")
        robot = data["robot"]
        if not isinstance(robot["movej_low_latency"], bool):
            raise ValueError("MoveJ 低延迟开关必须是布尔值")
        segment_deg = float(robot["movej_max_segment_deg"])
        if not math.isfinite(segment_deg) or not 0.1 <= segment_deg <= 5.0:
            raise ValueError("MoveJ 单段上限必须在 0.1..5.0 度之间")
        duplicate_deadband = float(robot["movej_duplicate_deadband_deg"])
        if not math.isfinite(duplicate_deadband) or not 0.0 <= duplicate_deadband <= 1.0:
            raise ValueError("MoveJ 重复目标抑制阈值必须在 0.0..1.0 度之间")
        for key in ("servoj_vmax", "servoj_amax", "servoj_jmax"):
            servo_limit_vector(robot[key], key)
        for key, label in (
            ("safety_max_command_step_rad", "GELLO 单帧跳变限制"),
            ("safety_max_command_speed_rad_s", "GELLO 速度限制"),
            ("safety_max_tracking_error_rad", "CR5 跟踪误差限制"),
        ):
            if not math.isfinite(float(robot[key])) or float(robot[key]) <= 0:
                raise ValueError(f"{label}必须大于 0")
        if int(robot["safety_speed_violation_cycles"]) < 1:
            raise ValueError("GELLO 速度超限连续帧数必须为正整数")
        scales = data["teleop"]["scale_xyz"]
        limits = data["teleop"]["max_delta_xyz_mm"]
        if len(scales) != 3 or len(limits) != 3:
            raise ValueError("XYZ 倍率和范围必须各包含 3 个值")
        if any(not math.isfinite(float(value)) or float(value) == 0 for value in scales):
            raise ValueError("XYZ 倍率必须是非零有限数")
        if any(float(value) <= 0 for value in limits):
            raise ValueError("XYZ 安全范围必须大于 0")
        if float(data["teleop"]["max_tcp_speed_mm_s"]) <= 0:
            raise ValueError("TCP 速度限制必须大于 0")
        rpy_scales = data["teleop"]["scale_rpy"]
        rpy_limits = data["teleop"]["max_delta_rpy_rad"]
        if len(rpy_scales) != 3 or len(rpy_limits) != 3:
            raise ValueError("RPY 倍率和范围必须各包含 3 个值")
        if any(not math.isfinite(float(value)) or float(value) == 0 for value in rpy_scales):
            raise ValueError("RPY 倍率必须是非零有限数")
        if any(not 0 < float(value) <= math.pi for value in rpy_limits):
            raise ValueError("RPY 安全范围必须在 0..pi rad 内")
        if float(data["teleop"]["max_tcp_angular_speed_rad_s"]) <= 0:
            raise ValueError("TCP 姿态速度限制必须大于 0")
        angular_jump = float(data["teleop"]["max_master_angular_jump_rad"])
        if not 0 < angular_jump <= math.pi:
            raise ValueError("主臂姿态单帧跳变限制必须在 0..pi rad 内")
        inverse3 = data["inverse3"]
        if not str(inverse3["uri"]).startswith(("ws://", "wss://")):
            raise ValueError("Inverse Service 地址必须以 ws:// 或 wss:// 开头")
        if float(inverse3["feedback_hz"]) <= 0:
            raise ValueError("Inverse3 反馈频率必须大于 0")
        if float(inverse3["feedback_timeout_s"]) <= 0:
            raise ValueError("Inverse3 反馈超时必须大于 0")
        if not str(inverse3["basis"]).strip():
            raise ValueError("Inverse3 basis 不能为空")
        gello = data["gello"]
        if not str(gello["port"]).strip():
            raise ValueError("GELLO 串口不能为空")
        if int(gello["baudrate"]) <= 0:
            raise ValueError("GELLO 波特率必须大于 0")
        if not str(gello["software_root"]).strip():
            raise ValueError("GELLO 软件目录不能为空")
        if gello["control_mode"] not in (
            "joint",
            "xyz_j6",
            "xyz_j6_tcp_ik",
            "tcp_6d",
        ):
            raise ValueError("GELLO control_mode 必须是 joint、xyz_j6、xyz_j6_tcp_ik 或 tcp_6d")
        if not str(gello["kinematics_urdf"]).strip():
            raise ValueError("GELLO kinematics_urdf 不能为空")
        if gello["control_mode"] != "joint":
            urdf_path = self.resolve_path(gello["kinematics_urdf"])
            if not urdf_path.is_file():
                raise ValueError("GELLO TCP/XYZ 模式的 URDF 文件不存在")
        xyz_axis_map = gello["xyz_axis_map"]
        if (
            not isinstance(xyz_axis_map, list)
            or len(xyz_axis_map) != 3
            or any(
                not isinstance(row, list)
                or len(row) != 3
                or any(not math.isfinite(float(value)) for value in row)
                for row in xyz_axis_map
            )
        ):
            raise ValueError("GELLO xyz_axis_map 必须是 3x3 有限矩阵")
        if int(gello["j6_sign"]) not in (-1, 1):
            raise ValueError("GELLO j6_sign 必须为 ±1")
        xyz_scale = gello["xyz_scale"]
        if len(xyz_scale) != 3 or any(
            not math.isfinite(float(value)) or float(value) == 0 for value in xyz_scale
        ):
            raise ValueError("GELLO xyz_scale 必须包含 3 个非零有限数")
        joint_ids = gello["joint_ids"]
        offsets = gello["joint_offsets"]
        signs = gello["joint_signs"]
        if len(joint_ids) != 6 or len(offsets) != 6 or len(signs) != 6:
            raise ValueError("GELLO 必须配置 6 个关节")
        if any(int(value) < 1 for value in joint_ids):
            raise ValueError("GELLO 关节 ID 必须为正整数")
        if any(not math.isfinite(float(value)) for value in offsets):
            raise ValueError("GELLO joint_offsets 必须是有限数")
        if any(int(value) not in (-1, 1) for value in signs):
            raise ValueError("GELLO joint_signs 必须为 ±1")
        locked_joints = gello["locked_joints"]
        if (
            not isinstance(locked_joints, list)
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 6
                for value in locked_joints
            )
            or len(set(locked_joints)) != len(locked_joints)
        ):
            raise ValueError("GELLO locked_joints 必须是 1～6 的不重复整数列表")
        gripper_config = gello["gripper_config"]
        if len(gripper_config) != 3:
            raise ValueError("GELLO gripper_config 必须包含 ID、张开端和闭合端")
        if int(gripper_config[0]) < 1:
            raise ValueError("GELLO gripper ID 必须为正整数")
        if float(gello["feedback_hz"]) <= 0 or float(gello["feedback_timeout_s"]) <= 0:
            raise ValueError("GELLO 反馈频率和超时必须大于 0")
        joint_scale = float(gello["joint_scale"])
        if not math.isfinite(joint_scale) or not 0.5 <= joint_scale <= 1.5:
            raise ValueError("GELLO J1-J6 关节倍率必须在 0.5..1.5 之间")
        if float(gello["startup_settle_s"]) < 0:
            raise ValueError("GELLO 启动稳定时间不能为负数")
        preset = data["preset"]
        for key, label in (
            ("robot_velocity_percent", "CR5 回位速度"),
            ("robot_acc_percent", "CR5 回位加速度"),
            ("robot_dec_percent", "CR5 回位减速度"),
        ):
            value = float(preset[key])
            if not 0 < value <= 100:
                raise ValueError(f"{label}必须在 0..100% 之间")
        if float(data["preset"]["timeout_s"]) <= 0:
            raise ValueError("预设回位等待上限必须大于 0")
        replay = data["replay"]
        if not str(data["trajectory"]["root"]).strip():
            raise ValueError("轨迹保存目录不能为空")
        if not 0.01 <= float(replay["sample_period_s"]) <= 1.0:
            raise ValueError("关节录制采样周期必须在 0.01..1.0 秒")
        if not 0.005 <= float(replay["servoj_period_s"]) <= 0.02:
            raise ValueError("ServoJ 重放周期必须在 0.005..0.02 秒")
        if not 0.0 <= float(replay["mode_switch_settle_s"]) <= 1.0:
            raise ValueError("运动模式切换稳定时间必须在 0..1 秒")
        if float(replay["max_duration_s"]) <= 0:
            raise ValueError("关节录制最长时间必须大于 0")
        if float(replay["max_joint_speed_deg_s"]) <= 0:
            raise ValueError("关节重放速度安全上限必须大于 0")
        m5_open = float(data["roarm"]["m5_open_rad"])
        m5_closed = float(data["roarm"]["m5_closed_rad"])
        if abs(m5_closed - m5_open) < 0.1:
            raise ValueError("RoArm M5 开合端点过于接近")
        _six_uint8(data["o6"]["open"], "O6 张开端点")
        _six_uint8(data["o6"]["closed"], "O6 闭合端点")
        _six_uint8(data["o6"]["speed"], "O6 速度")
        _six_uint8(data["o6"]["torque"], "O6 力矩")
        if float(data["o6"]["action_timeout_s"]) <= 0:
            raise ValueError("O6 动作等待上限必须大于 0")
        actions = data["o6"]["actions"]
        if not isinstance(actions, dict) or not actions:
            raise ValueError("O6 快捷动作必须是非空字典")
        for action_name, target in actions.items():
            if not isinstance(action_name, str) or not action_name.strip():
                raise ValueError("O6 快捷动作名称不能为空")
            _six_uint8(target, f"O6 快捷动作 {action_name}")
        for key in ("open_action", "closed_action"):
            if data["o6"][key] not in actions:
                raise ValueError(f"O6 {key} 必须引用已保存的动作")
        dataset = data["dataset"]
        if dataset["recording_mode"] not in ("tcp", "joint"):
            raise ValueError("记录模式必须是 tcp 或 joint")
        if not str(dataset["root"]).strip():
            raise ValueError("LeRobot 数据集根目录不能为空")
        repo_prefix = str(dataset["repo_prefix"]).strip()
        if repo_prefix.count("/") != 1 or any(not part for part in repo_prefix.split("/", 1)):
            raise ValueError("LeRobot repo_prefix 必须是 owner/name 格式")
        if not str(dataset["task"]).strip():
            raise ValueError("LeRobot 任务文字不能为空")
        if not 1 <= int(dataset["fps"]) <= 60:
            raise ValueError("LeRobot FPS 必须在 1..60 之间")
        image_size = dataset["image_size"]
        if (
            not isinstance(image_size, list)
            or len(image_size) != 2
            or any(int(value) < 2 or int(value) > 2160 or int(value) % 2 for value in image_size)
        ):
            raise ValueError("LeRobot image_size 必须是 [height, width]")
        if float(dataset["camera_max_age_s"]) <= 0:
            raise ValueError("LeRobot 相机帧超时必须大于 0")
        for key in ("camera_max_skew_s", "action_max_age_s", "max_tracking_error_deg"):
            if not math.isfinite(float(dataset[key])) or float(dataset[key]) <= 0:
                raise ValueError(f"LeRobot {key} 必须是大于 0 的有限数")
        if not str(dataset["wrist_camera_serial"]).strip():
            raise ValueError("CAMERA1 腕部相机序列号不能为空")
        if not str(dataset["base_camera_serial"]).strip():
            raise ValueError("CAMERA2 基座相机序列号不能为空")
        if dataset["wrist_camera_serial"] == dataset["base_camera_serial"]:
            raise ValueError("CAMERA1 和 CAMERA2 不能配置为同一个序列号")
        roi = dataset["base_roi_norm"]
        if not isinstance(roi, list) or len(roi) != 4:
            raise ValueError("base_roi_norm 必须是 [x1, y1, x2, y2]")
        x1, y1, x2, y2 = [float(value) for value in roi]
        if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
            raise ValueError("base_roi_norm 必须满足 0<=x1<x2<=1 且 0<=y1<y2<=1")
        resolve_camera_streams(dataset)
        if not str(dataset["worker_python"]).strip():
            raise ValueError("LeRobot worker_python 不能为空")
        shortcuts = data["shortcuts"]
        if not isinstance(shortcuts, dict):
            raise ValueError("shortcuts 必须是字典")
        missing_shortcuts = set(DEFAULT_CONFIG["shortcuts"]) - set(shortcuts)
        if missing_shortcuts:
            raise ValueError("缺少快捷键配置: " + ", ".join(sorted(missing_shortcuts)))
        assigned: dict[str, str] = {}
        for action_name in DEFAULT_CONFIG["shortcuts"]:
            sequence = str(shortcuts[action_name]).strip()
            if not sequence:
                continue
            normalized = sequence.casefold()
            if normalized in assigned:
                raise ValueError(
                    f"快捷键 {sequence} 同时分配给 {assigned[normalized]} 和 {action_name}"
                )
            assigned[normalized] = action_name
