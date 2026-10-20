"""Quaternion and NRC orientation conversions (radians, wxyz)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np


def _normalize_quaternion(values: Sequence[Any]) -> tuple[float, float, float, float]:
    if len(values) != 4:
        raise ValueError("四元数必须包含 w/x/y/z 四个值")
    quaternion = tuple(float(value) for value in values)
    norm = math.sqrt(sum(value * value for value in quaternion))
    if not math.isfinite(norm) or norm <= 1e-12:
        raise ValueError("四元数无效")
    return tuple(value / norm for value in quaternion)


def _quaternion_multiply(
    left: Sequence[Any], right: Sequence[Any]
) -> tuple[float, float, float, float]:
    lw, lx, ly, lz = _normalize_quaternion(left)
    rw, rx, ry, rz = _normalize_quaternion(right)
    return _normalize_quaternion(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )
    )


def _quaternion_inverse(values: Sequence[Any]) -> tuple[float, float, float, float]:
    w, x, y, z = _normalize_quaternion(values)
    return (w, -x, -y, -z)


def _rotation_matrix_to_quaternion(
    matrix: Sequence[Sequence[float]],
) -> tuple[float, float, float, float]:
    rotation = np.asarray(matrix, dtype=float)
    if rotation.shape != (3, 3):
        raise ValueError("旋转矩阵必须是 3x3")
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = (
            0.25 * scale,
            (rotation[2, 1] - rotation[1, 2]) / scale,
            (rotation[0, 2] - rotation[2, 0]) / scale,
            (rotation[1, 0] - rotation[0, 1]) / scale,
        )
    elif rotation[0, 0] > rotation[1, 1] and rotation[0, 0] > rotation[2, 2]:
        scale = math.sqrt(1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2]) * 2.0
        quaternion = (
            (rotation[2, 1] - rotation[1, 2]) / scale,
            0.25 * scale,
            (rotation[0, 1] + rotation[1, 0]) / scale,
            (rotation[0, 2] + rotation[2, 0]) / scale,
        )
    elif rotation[1, 1] > rotation[2, 2]:
        scale = math.sqrt(1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2]) * 2.0
        quaternion = (
            (rotation[0, 2] - rotation[2, 0]) / scale,
            (rotation[0, 1] + rotation[1, 0]) / scale,
            0.25 * scale,
            (rotation[1, 2] + rotation[2, 1]) / scale,
        )
    else:
        scale = math.sqrt(1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1]) * 2.0
        quaternion = (
            (rotation[1, 0] - rotation[0, 1]) / scale,
            (rotation[0, 2] + rotation[2, 0]) / scale,
            (rotation[1, 2] + rotation[2, 1]) / scale,
            0.25 * scale,
        )
    return _normalize_quaternion(quaternion)


def _nrc_abc_to_quaternion(
    values: Sequence[Any],
) -> tuple[float, float, float, float]:
    if len(values) != 3:
        raise ValueError("NRC ABC 必须包含三个值")
    a, b, c = (float(value) for value in values)
    qa = (math.cos(a / 2.0), math.sin(a / 2.0), 0.0, 0.0)
    qb = (math.cos(b / 2.0), 0.0, math.sin(b / 2.0), 0.0)
    qc = (math.cos(c / 2.0), 0.0, 0.0, math.sin(c / 2.0))
    return _quaternion_multiply(_quaternion_multiply(qa, qb), qc)


def _quaternion_to_nrc_abc(
    values: Sequence[Any],
) -> tuple[float, float, float]:
    """Convert a relative quaternion to NRC intrinsic X'-Y'-Z' Euler radians."""
    w, x, y, z = _normalize_quaternion(values)
    r00 = 1.0 - 2.0 * (y * y + z * z)
    r01 = 2.0 * (x * y - w * z)
    r02 = 2.0 * (x * z + w * y)
    r10 = 2.0 * (x * y + w * z)
    r11 = 1.0 - 2.0 * (x * x + z * z)
    r12 = 2.0 * (y * z - w * x)
    r22 = 1.0 - 2.0 * (x * x + y * y)

    b = math.asin(max(-1.0, min(1.0, r02)))
    if abs(math.cos(b)) > 1e-8:
        a = math.atan2(-r12, r22)
        c = math.atan2(-r01, r00)
    elif b > 0:
        a = math.atan2(r10, r11)
        c = 0.0
    else:
        a = math.atan2(-r10, r11)
        c = 0.0
    return (a, b, c)


def _quaternion_to_nrc_abc_near(
    values: Sequence[Any], reference: Sequence[Any]
) -> tuple[float, float, float]:
    if len(reference) != 3:
        raise ValueError("NRC ABC 参考值必须包含三个值")
    a, b, c = _quaternion_to_nrc_abc(values)
    raw_candidates = (
        (a, b, c),
        (a + math.pi, math.pi - b, c + math.pi),
        (a + math.pi, -math.pi - b, c + math.pi),
    )
    target = tuple(float(value) for value in reference)
    candidates = []
    for candidate in raw_candidates:
        adjusted = tuple(
            value + 2.0 * math.pi * round((target[index] - value) / (2.0 * math.pi))
            for index, value in enumerate(candidate)
        )
        candidates.append(adjusted)
    return min(
        candidates,
        key=lambda candidate: sum((candidate[index] - target[index]) ** 2 for index in range(3)),
    )


def _wrapped_angle_delta(target: float, origin: float) -> float:
    return (float(target) - float(origin) + math.pi) % (2.0 * math.pi) - math.pi


def _quaternion_distance(left: Sequence[Any], right: Sequence[Any]) -> float:
    first = _normalize_quaternion(left)
    second = _normalize_quaternion(right)
    dot = abs(sum(a * b for a, b in zip(first, second, strict=True)))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


def _quaternion_slerp(
    origin: Sequence[Any], target: Sequence[Any], ratio: float
) -> tuple[float, float, float, float]:
    first = _normalize_quaternion(origin)
    second = _normalize_quaternion(target)
    amount = max(0.0, min(1.0, float(ratio)))
    dot = sum(a * b for a, b in zip(first, second, strict=True))
    if dot < 0.0:
        second = tuple(-value for value in second)
        dot = -dot
    if dot > 0.9995:
        return _normalize_quaternion(
            tuple(first[index] + amount * (second[index] - first[index]) for index in range(4))
        )
    angle = math.acos(max(-1.0, min(1.0, dot)))
    denominator = math.sin(angle)
    first_weight = math.sin((1.0 - amount) * angle) / denominator
    second_weight = math.sin(amount * angle) / denominator
    return _normalize_quaternion(
        tuple(first_weight * first[index] + second_weight * second[index] for index in range(4))
    )
