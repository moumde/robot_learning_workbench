"""Timestamp-based playback through a worker-local MotionLease."""

from __future__ import annotations

import math
import threading
import time
from typing import Protocol

from gello_cr.errors import TrajectoryError
from gello_cr.motion import JointTarget, MotionCoordinator, MotionPreempted, MotionSource

from .model import ReplayMode, ReplayOptions, Trajectory
from .validation import (
    hand_target,
    joint_target,
    replay_joint_mask,
    validate_options,
    validate_replay_channels,
    validate_replay_speed,
    validate_trajectory,
)


class ReplayFeedback(Protocol):
    def read_joints(self) -> tuple[float, ...]: ...
    def send_hand(self, target: tuple[float, ...]) -> None: ...
    def hold_hand(self) -> None: ...
    def check_ready(self, arm_enabled: bool, hand_enabled: bool) -> None: ...


class TrajectoryPlayer:
    def __init__(
        self,
        motion: MotionCoordinator,
        feedback: ReplayFeedback,
        *,
        period_s=0.01,
        servo_profile=(80.0, 200.0, 150.0),
        stop_event=None,
        clock=time.monotonic,
        wait=None,
    ):
        if not math.isfinite(period_s) or period_s <= 0:
            raise ValueError("Servo period must be positive")
        self.motion, self.feedback = motion, feedback
        self.period_s, self.servo_profile = period_s, servo_profile
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self._clock = clock
        self._wait = wait if wait is not None else lambda duration, stop: stop.wait(duration)
        self._lock = threading.Lock()
        self._lease = None
        self._thread = None
        self._playing = False
        self._hand_enabled = False
        self._last_hand_target = None
        self.error = ""

    @property
    def playing(self):
        with self._lock:
            return self._playing

    def request_stop(self):
        self.stop_event.set()

    def stop(self):
        self.request_stop()
        lease = self._lease
        if lease is not None:
            owned = lease.active
            try:
                lease.release()
            finally:
                if owned and self._hand_enabled:
                    self.feedback.hold_hand()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(2.0)
            if self._thread.is_alive():
                raise TimeoutError("Trajectory playback did not stop")

    def _due(self, deadline, lease):
        lease.check()
        if self.stop_event.is_set():
            return False
        delay = deadline - self._clock()
        if delay > 0 and self._wait(delay, self.stop_event):
            return False
        lease.check()
        if self._clock() >= self._next_ready_check:
            self.feedback.check_ready(self._options.arm_enabled, self._options.hand_enabled)
            self._next_ready_check = self._clock() + 0.1
        return not self.stop_event.is_set()

    def _send(self, joints, hand, lease, options):
        lease.check()
        if options.arm_enabled:
            result = lease.servo_joint(JointTarget(tuple(joints), time.monotonic()))
            if result is False:
                raise TrajectoryError("Trajectory joint command was not accepted")
        if options.hand_enabled and hand is not None and tuple(hand) != self._last_hand_target:
            lease.check()
            self.feedback.send_hand(tuple(hand))
            self._last_hand_target = tuple(hand)

    def play(
        self,
        trajectory: Trajectory,
        options: ReplayOptions,
        *,
        lease=None,
        max_joint_speed_rad_s=None,
        start_tolerance_rad=None,
        on_target=None,
    ):
        validate_trajectory(trajectory)
        if (trajectory.metadata.planning or {}).get("offline_only"):
            raise ValueError("Offline preview only; connect the robot and replan before execution")
        validate_options(options)
        if max_joint_speed_rad_s is not None:
            validate_replay_speed(trajectory, options, max_joint_speed_rad_s)
        validate_replay_channels(trajectory, options)
        if start_tolerance_rad is not None:
            if (
                not math.isfinite(start_tolerance_rad)
                or start_tolerance_rad <= 0
                or options.mode is not ReplayMode.ABSOLUTE
                or options.repeat != 1
                or options.time_scale != 1
                or not options.arm_enabled
                or options.hand_enabled
                or options.joint_mask is not None
                or lease is None
                or lease.source is not MotionSource.POINT_MOVE
            ):
                raise ValueError("Planned playback requires an absolute, full-arm POINT_MOVE lease")
        with self._lock:
            if self._playing:
                raise TrajectoryError("Trajectory playback already active")
            self._playing = True
            self._thread = threading.current_thread()
            self._hand_enabled = options.hand_enabled
            self._options = options
            self._next_ready_check = self._clock()
            self._last_hand_target = None
            self.stop_event.clear()
        error = None
        self.error = ""
        try:
            self.feedback.check_ready(options.arm_enabled, options.hand_enabled)
            lease = lease or self.motion.acquire(
                MotionSource.REPLAY, allow_preempt=True, on_cancel=self.request_stop
            )
            self._lease = lease
            lease.check()
            frames = trajectory.frames
            mask = replay_joint_mask(trajectory, options)
            for iteration in range(options.repeat):
                lease.check()
                held = tuple(self.feedback.read_joints()) if options.arm_enabled else None
                if held is not None and (len(held) != 6 or not all(math.isfinite(v) for v in held)):
                    raise ValueError("Current joint feedback must contain six finite radians")
                origin = joint_target(frames[0])

                def mapped(frame, held=held, origin=origin):
                    recorded = joint_target(frame)
                    if not options.arm_enabled:
                        return None
                    return tuple(
                        held[i]
                        if not mask[i]
                        else held[i] + recorded[i] - origin[i]
                        if options.mode is ReplayMode.RELATIVE
                        else recorded[i]
                        for i in range(6)
                    )

                first = mapped(frames[0])
                if start_tolerance_rad is not None and any(
                    abs(a - b) > start_tolerance_rad for a, b in zip(held, first, strict=True)
                ):
                    raise ValueError(
                        "Robot moved from plan start; read current position and replan"
                    )
                if (
                    options.arm_enabled
                    and options.mode is ReplayMode.ABSOLUTE
                    and max_joint_speed_rad_s is not None
                    and any(
                        abs(b - a) / options.transition_s > max_joint_speed_rad_s
                        for a, b in zip(held, first, strict=True)
                    )
                ):
                    raise ValueError("Initial transition joint speed exceeds replay limit")
                if options.arm_enabled and iteration == 0:
                    lease.open_servo(*self.servo_profile)
                # A bounded ServoJ transition replaces an instantaneous jump in
                # absolute mode. It uses the same final safety boundary as replay.
                if (
                    options.arm_enabled
                    and options.mode is ReplayMode.ABSOLUTE
                    and start_tolerance_rad is None
                ):
                    started = self._clock()
                    steps = max(1, math.ceil(options.transition_s / self.period_s))
                    for step in range(1, steps + 1):
                        if not self._due(started + options.transition_s * step / steps, lease):
                            return
                        alpha = step / steps
                        target = tuple(
                            a + (b - a) * alpha for a, b in zip(held, first, strict=True)
                        )
                        self._send(target, None, lease, options)
                started = self._clock()
                t0 = frames[0].timestamp
                for index, frame in enumerate(frames):
                    if index == 0:
                        samples = [(0.0, mapped(frame), hand_target(frame))]
                    else:
                        previous = frames[index - 1]
                        duration = (frame.timestamp - previous.timestamp) / options.time_scale
                        steps = max(1, math.ceil(duration / self.period_s))
                        a, b = mapped(previous), mapped(frame)
                        samples = (
                            (
                                (previous.timestamp - t0) / options.time_scale
                                + duration * k / steps,
                                tuple(x + (y - x) * k / steps for x, y in zip(a, b, strict=True))
                                if a is not None
                                else None,
                                hand_target(frame) if k == steps else hand_target(previous),
                            )
                            for k in range(1, steps + 1)
                        )
                    for offset, joints, hand in samples:
                        if not self._due(started + offset, lease):
                            return
                        self._send(joints, hand, lease, options)
            if on_target is not None:
                return on_target(lease, self.stop_event)
        except MotionPreempted:
            return
        except Exception as exc:
            error = exc
            self.error = str(exc)
            raise
        finally:
            try:
                owned = lease is not None and lease.active
                status = self.motion.status
                own_failure = (
                    error is not None and status.source is None and status.error == str(error)
                )
                if options.hand_enabled and (owned or own_failure):
                    self.feedback.hold_hand()
            finally:
                try:
                    if lease is not None:
                        lease.release(error=error)
                finally:
                    with self._lock:
                        self._playing = False
