"""Forward kinematics for the configured GELLO URDF."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class _GelloUrdfJoint:
    origin_xyz: tuple[float, float, float]
    origin_rpy: tuple[float, float, float]
    axis: tuple[float, float, float]


class GelloKinematics:
    """Minimal URDF FK for the six joints of the physical GELLO."""

    def __init__(self, urdf_path: str | Path):
        root = ET.parse(str(Path(urdf_path).expanduser())).getroot()
        joints: dict[int, _GelloUrdfJoint] = {}
        for element in root.findall("joint"):
            name = str(element.attrib["name"])
            if not name.startswith("joint"):
                continue
            number = int(name.removeprefix("joint"))
            origin = element.find("origin")
            axis = element.find("axis")
            if origin is None or axis is None:
                raise ValueError(f"GELLO URDF 关节 {name} 缺少 origin 或 axis")
            origin_xyz = tuple(
                float(value) for value in str(origin.attrib.get("xyz", "0 0 0")).split()
            )
            origin_rpy = tuple(
                float(value) for value in str(origin.attrib.get("rpy", "0 0 0")).split()
            )
            joint_axis = tuple(float(value) for value in str(axis.attrib["xyz"]).split())
            if len(origin_xyz) != 3 or len(origin_rpy) != 3 or len(joint_axis) != 3:
                raise ValueError(f"GELLO URDF 关节 {name} 参数长度错误")
            joints[number] = _GelloUrdfJoint(origin_xyz, origin_rpy, joint_axis)
        if tuple(sorted(joints)) != (1, 2, 3, 4, 5, 6):
            raise ValueError("GELLO URDF 必须包含 joint1～joint6")
        self._joints = tuple(joints[index] for index in range(1, 7))

    @staticmethod
    def _rpy_matrix(rpy: Sequence[float]) -> np.ndarray:
        roll, pitch, yaw = (float(value) for value in rpy)
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        return np.array(
            [
                [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                [-sp, cp * sr, cp * cr],
            ],
            dtype=float,
        )

    @staticmethod
    def _axis_matrix(axis: Sequence[float], angle: float) -> np.ndarray:
        vector = np.asarray(axis, dtype=float)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            raise ValueError("GELLO URDF 关节轴不能为零")
        x, y, z = vector / norm
        cosine = math.cos(float(angle))
        sine = math.sin(float(angle))
        one_minus_cosine = 1.0 - cosine
        return np.array(
            [
                [
                    cosine + x * x * one_minus_cosine,
                    x * y * one_minus_cosine - z * sine,
                    x * z * one_minus_cosine + y * sine,
                ],
                [
                    y * x * one_minus_cosine + z * sine,
                    cosine + y * y * one_minus_cosine,
                    y * z * one_minus_cosine - x * sine,
                ],
                [
                    z * x * one_minus_cosine - y * sine,
                    z * y * one_minus_cosine + x * sine,
                    cosine + z * z * one_minus_cosine,
                ],
            ],
            dtype=float,
        )

    def pose(self, joints_rad: Sequence[float]) -> np.ndarray:
        if len(joints_rad) != 6:
            raise ValueError("GELLO FK 输入必须包含 6 个关节")
        transform = np.eye(4, dtype=float)
        for joint, angle in zip(self._joints, joints_rad, strict=True):
            origin_rotation = self._rpy_matrix(joint.origin_rpy)
            origin_transform = np.eye(4, dtype=float)
            origin_transform[:3, :3] = origin_rotation
            origin_transform[:3, 3] = np.asarray(joint.origin_xyz, dtype=float)
            joint_transform = np.eye(4, dtype=float)
            joint_transform[:3, :3] = self._axis_matrix(joint.axis, float(angle))
            transform = transform @ origin_transform @ joint_transform
        return transform

    def position(self, joints_rad: Sequence[float]) -> np.ndarray:
        return self.pose(joints_rad)[:3, 3].copy()
