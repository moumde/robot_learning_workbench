"""Editable configuration boundary; saving never mutates the running store."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SettingField:
    path: str
    label: str
    kind: str = "float"
    minimum: float | None = None
    maximum: float | None = None
    count: int = 1

    def value(self, data):
        for key in self.path.split("."):
            data = data[key]
        return data

    def assign(self, data, value):
        keys = self.path.split(".")
        for key in keys[:-1]:
            data = data[key]
        data[keys[-1]] = value

    def parse(self, texts: list[str]):
        values = []
        for text in texts:
            try:
                value = (
                    text.strip()
                    if self.kind == "text"
                    else (int(text) if self.kind == "int" else float(text))
                )
            except ValueError as exc:
                raise ValueError(f"{self.label}：请输入有效的{self.kind}数值") from exc
            if self.kind == "text":
                if not value:
                    raise ValueError(f"{self.label}不能为空")
            else:
                if not math.isfinite(value):
                    raise ValueError(f"{self.label}必须是有限数")
                if self.minimum is not None and value < self.minimum:
                    raise ValueError(f"{self.label}不能小于 {self.minimum}")
                if self.maximum is not None and value > self.maximum:
                    raise ValueError(f"{self.label}不能大于 {self.maximum}")
            values.append(value)
        if len(values) != self.count:
            raise ValueError(f"{self.label}需要 {self.count} 个值")
        return values[0] if self.count == 1 else values


# One field definition supplies both the form and its input validation.
SETTINGS_GROUPS = {
    "机械臂": (
        SettingField(
            "robot.safety_max_command_step_rad", "单帧关节跳变上限（rad）", minimum=0.000001
        ),
        SettingField(
            "robot.safety_max_command_speed_rad_s", "主臂关节速度上限（rad/s）", minimum=0.000001
        ),
        SettingField("robot.safety_speed_violation_cycles", "速度超限连续帧数", "int", 1),
        SettingField(
            "robot.safety_max_tracking_error_rad", "从臂跟踪误差停止阈值（rad）", minimum=0.000001
        ),
        SettingField(
            "teleop.max_delta_xyz_mm", "相对 XYZ 位移上限（±mm）", minimum=0.000001, count=3
        ),
        SettingField("teleop.max_tcp_speed_mm_s", "TCP 线速度上限（mm/s）", minimum=0.000001),
        SettingField(
            "teleop.max_delta_rpy_rad",
            "相对姿态范围（±rad）",
            minimum=0.000001,
            maximum=math.pi,
            count=3,
        ),
        SettingField(
            "teleop.max_tcp_angular_speed_rad_s", "TCP 角速度上限（rad/s）", minimum=0.000001
        ),
        SettingField("teleop.max_master_jump_mm", "主臂位置跳变上限（mm）", minimum=0.000001),
        SettingField(
            "teleop.max_master_angular_jump_rad",
            "主臂姿态跳变上限（rad）",
            minimum=0.000001,
            maximum=math.pi,
        ),
    ),
    "GELLO": (
        SettingField("gello.joint_scale", "J1–J6 跟随倍率", minimum=0.5, maximum=1.5),
        SettingField("gello.feedback_hz", "反馈 / 关节跟随频率（Hz）", minimum=0.000001),
        SettingField("gello.feedback_timeout_s", "反馈超时（s）", minimum=0.000001),
        SettingField("gello.startup_settle_s", "启动稳定时间（s）", minimum=0),
        SettingField("gello.xyz_scale", "GELLO XYZ 模式倍率（X / Y / Z）", count=3),
        SettingField("teleop.scale_rpy", "姿态倍率（R / P / Y）", count=3),
        SettingField("gello.port", "GELLO 串口路径", "text"),
        SettingField("gello.baudrate", "GELLO 波特率", "int", 1),
        SettingField("gello.software_root", "GELLO 软件目录", "text"),
        SettingField("gello.kinematics_urdf", "运动学 URDF", "text"),
    ),
    "O6 动作": (
        SettingField("o6.speed", "六电机速度（原始值 0–255）", "int", 0, 255, 6),
        SettingField("o6.torque", "六电机力矩（原始值 0–255）", "int", 0, 255, 6),
        SettingField("o6.command_deadband", "连续跟随目标死区（原始值）", "int", 0, 255),
        SettingField("o6.feedback_timeout_s", "反馈超时（s）", minimum=0.000001),
        SettingField("o6.action_timeout_s", "动作等待上限（s）", minimum=0.000001),
        SettingField("o6.port", "O6 串口路径", "text"),
        SettingField("o6.baudrate", "O6 波特率", "int", 1),
        SettingField("o6.hand_id", "Modbus 从站地址（十进制）", "int", 1, 247),
    ),
    "数采与相机": (
        SettingField("dataset.root", "数据集根目录", "text"),
        SettingField("dataset.task", "默认任务描述", "text"),
        SettingField("dataset.repo_prefix", "数据集标识前缀（owner/name）", "text"),
        SettingField("dataset.fps", "采集帧率（Hz）", "int", 1, 60),
        SettingField(
            "dataset.image_size", "保存尺寸（高 / 宽，偶数；原画 480 / 640）", "int", 2, 2160, 2
        ),
        SettingField("dataset.camera_max_age_s", "相机帧最大时龄（s）", minimum=0.000001),
        SettingField("dataset.camera_max_skew_s", "相机画面最大时间差（s）", minimum=0.000001),
        SettingField("dataset.action_max_age_s", "动作最大时龄（s）", minimum=0.000001),
        SettingField(
            "dataset.max_tracking_error_deg", "跟踪误差质量标记阈值（°）", minimum=0.000001
        ),
        SettingField("dataset.worker_python", "数采 Python 解释器", "text"),
    ),
    "规划": (
        SettingField(
            "planning.default_speed_scale", "默认速度比例（0–1）", minimum=0.01, maximum=1
        ),
        SettingField("planning.tcp_position_step_m", "直线位置采样间隔（m）", minimum=0.00001),
        SettingField("planning.tcp_rotation_step_deg", "旋转采样间隔（°）", minimum=0.01),
        SettingField("planning.reached.joint_tolerance_deg", "关节到位容差（°）", minimum=0.001),
        SettingField(
            "planning.reached.tcp_position_tolerance_mm", "TCP 到位容差（mm）", minimum=0.01
        ),
        SettingField("planning.reached.timeout_s", "到位等待时间（s）", minimum=0.1),
    ),
    "控制器连接": (
        SettingField("robot.ip", "控制器 IP / 主机名", "text"),
        SettingField("robot.command_port", "命令端口", "int", 1, 65535),
        SettingField("robot.servo_port", "Servo 端口", "int", 1, 65535),
        SettingField("robot.robot_num", "机器人编号", "int", 1, 4),
    ),
}


class OperatorSettings:
    """Detached draft with atomic persistence and external-edit conflict detection."""

    def __init__(self, path: Path, store_factory):
        self.path = Path(path)
        self._store_factory = store_factory
        self._source_bytes = self.path.read_bytes()
        store = store_factory(self.path)
        self.data = copy.deepcopy(store.data)
        self.read_only_paths = frozenset(getattr(store, "read_only_paths", ()))
        self.hardware_profile_path = getattr(store, "hardware_profile_path", None)
        # Keep owned values separate from the editable public draft. A caller
        # changing settings.data directly must not bypass the save boundary.
        self._read_only_values = {
            path: copy.deepcopy(self._path_value(self.data, path)) for path in self.read_only_paths
        }

    @staticmethod
    def _path_value(data, path):
        for key in path.split("."):
            data = data[int(key)] if isinstance(data, (list, tuple)) else data[key]
        return data

    def is_read_only(self, path: str) -> bool:
        """A locked parent owns every nested field, including camera slots."""
        return any(path == owned or path.startswith(owned + ".") for owned in self.read_only_paths)

    def read_only_reason(self, path: str) -> str:
        source = self.hardware_profile_path or "硬件配置"
        return f"{path} 由硬件配置提供（只读）：{source}"

    def save(self, candidate: dict) -> None:
        for path, original in self._read_only_values.items():
            try:
                unchanged = self._path_value(candidate, path) == original
            except (KeyError, IndexError, TypeError, ValueError):
                unchanged = False
            if not unchanged:
                raise ValueError(self.read_only_reason(path))
        for fields in SETTINGS_GROUPS.values():
            for field in fields:
                value = field.value(candidate)
                values = value if field.count > 1 else [value]
                field.parse([str(item) for item in values])
        o6 = candidate["o6"]
        for name, target in o6["actions"].items():
            SettingField(name, f"O6 动作 {name}", "int", 0, 255, 6).parse(
                [str(value) for value in target]
            )
        for key in ("open_action", "closed_action"):
            if o6[key] not in o6["actions"]:
                raise ValueError(f"O6 {key} 必须选择已保存的动作")
        store = self._store_factory(self.path)
        store.data = copy.deepcopy(candidate)
        # Validate before producing a backup or replacing the configuration file.
        store._validate(store.data)
        if self.path.read_bytes() != self._source_bytes:
            raise RuntimeError("配置已被其他程序修改，请关闭设置页后重新打开再编辑")
        self.path.with_suffix(self.path.suffix + ".bak").write_bytes(self._source_bytes)
        store.save()
        self._source_bytes = self.path.read_bytes()
        self.data = copy.deepcopy(store.data)


def camera_streams(config):
    from core.hardware.camera_streams import resolve_camera_streams

    return resolve_camera_streams(config)


def discover_cameras(jobs, completed):
    from core.hardware.realsense import discover_realsense_cameras

    jobs.start(discover_realsense_cameras, completed, name="CameraDiscovery")
