"""Measured target completion while the caller retains its motion lease."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import StrEnum

from core.workbench.motion import MotionPreempted

from .interpolation import pose_distance
from .validation import vector


class ReachStatus(StrEnum):
    REACHED = "REACHED"
    TIMEOUT = "TIMEOUT"
    STOPPED = "STOPPED"
    PREEMPTED = "PREEMPTED"
    FAULT = "FAULT"


@dataclass(frozen=True)
class ReachedPolicy:
    joint_tolerance_rad: float = math.radians(0.5)
    position_tolerance_m: float = 0.002
    orientation_tolerance_rad: float = math.radians(1)
    stable_samples: int = 5
    timeout_s: float = 10.0
    sample_period_s: float = 0.02

    def __post_init__(self):
        for name in (
            "joint_tolerance_rad",
            "position_tolerance_m",
            "orientation_tolerance_rad",
            "timeout_s",
            "sample_period_s",
        ):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if type(self.stable_samples) is not int or self.stable_samples < 1:
            raise ValueError("stable_samples must be a positive integer")


def wait_until_reached(
    feedback,
    target_joint,
    target_tcp,
    policy,
    lease,
    stop_event,
    *,
    clock=time.monotonic,
    wait=None,
    keep_alive=None,
):
    wait = wait or (lambda duration, stop: stop.wait(duration))
    started, stable = clock(), 0
    while True:
        if stop_event.is_set():
            return ReachStatus.STOPPED
        try:
            lease.check()
            feedback.check_ready(True, False)
            actual = vector(feedback.read_joints(), 6, "Joint feedback")
            close = all(
                abs(a - b) <= policy.joint_tolerance_rad
                for a, b in zip(actual, target_joint, strict=True)
            )
            if target_tcp is not None:
                actual_tcp = feedback.read_tcp()
                vector(actual_tcp.position_m, 3, "TCP feedback position")
                vector(actual_tcp.orientation_rpy_rad, 3, "TCP feedback orientation")
                position, angle = pose_distance(actual_tcp, target_tcp)
                close = (
                    close
                    and position <= policy.position_tolerance_m
                    and angle <= policy.orientation_tolerance_rad
                )
            # A stop/preemption while feedback was read cannot become REACHED.
            lease.check()
            if stop_event.is_set():
                return ReachStatus.STOPPED
            if clock() - started > policy.timeout_s:
                return ReachStatus.TIMEOUT
            stable = stable + 1 if close else 0
            if stable >= policy.stable_samples:
                return ReachStatus.REACHED
            if clock() - started >= policy.timeout_s:
                return ReachStatus.TIMEOUT
            if keep_alive is not None:
                if keep_alive() is False:
                    return ReachStatus.FAULT
        except MotionPreempted:
            return ReachStatus.PREEMPTED
        except Exception:
            return ReachStatus.FAULT
        wait(
            min(policy.sample_period_s, max(0, policy.timeout_s - (clock() - started))), stop_event
        )
