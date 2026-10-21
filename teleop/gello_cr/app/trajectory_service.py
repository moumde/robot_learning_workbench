"""Trajectory recording, storage, import and playback orchestration."""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from teleop.gello_cr.motion import (
    MotionLease,
    MotionPreempted,
    MotionSource,
)
from teleop.gello_cr.trajectory import (
    ReplayOptions,
    preview_trajectory,
    validate_trajectory,
)


@dataclass
class _RecordingSession:
    lease: MotionLease | None
    generation: int
    thread: threading.Thread | None
    on_finished: Callable[[str | None], None] | None = None
    stopping: bool = False


class TrajectoryService:
    """Application service; device I/O remains behind the runtime adapters."""

    def __init__(self, runtime):
        self.runtime = runtime
        self._event = partial(runtime._event, domain="trajectory")
        self._recording_session = None

    def start_trajectory_recording(self, name, *, on_finished=None):
        if not str(name).strip():
            raise ValueError("Trajectory name cannot be empty")
        if self.runtime._pending_trajectory is not None or self.runtime.trajectory_recorder.frames:
            raise RuntimeError("请先保存或取消上次轨迹")
        if self.runtime.robot is None or self.runtime.state not in ("idle", "following"):
            raise RuntimeError("当前状态不允许录制轨迹")
        generation = self.runtime.stop_generation
        self.runtime.start_follow()
        session = _RecordingSession(
            self.runtime._follow_lease, generation, self.runtime._follow_thread, on_finished
        )
        self._recording_session = session
        try:
            if not self._session_following(session):
                raise MotionPreempted("轨迹录制启动已被停止")
            self.runtime.trajectory_recorder.start(
                name,
                {
                    "source": self.runtime.master_type,
                    "hand_type": "o6" if self.runtime.o6.connected else None,
                },
                should_continue=lambda: self._session_following(session),
                on_finished=lambda error: self._recording_finished(session, error),
            )
            if not self._session_following(session):
                raise MotionPreempted("轨迹录制启动已被停止")
        except Exception:
            session.stopping = True
            try:
                self.runtime.trajectory_recorder._join()
            finally:
                self._stop_session_follow(session)
            self.runtime.trajectory_recorder.cancel()
            if self._recording_session is session:
                self._recording_session = None
            raise
        self._event("info", f"轨迹录制与遥操已开始：{name}")

    def _session_following(self, session):
        return (
            self._recording_session is session
            and self.runtime.stop_generation == session.generation
            and self.runtime.state == "following"
            and self.runtime._follow_thread is session.thread
            and session.lease is not None
            and session.lease.active
        )

    def _owns_session_cleanup(self, session):
        return (
            self._recording_session is session
            and self.runtime._stop_generation == session.generation
            and self.runtime._follow_thread is session.thread
            and self.runtime.state in ("following", "idle", "fault")
            and (session.lease is not None and session.lease.active
                 or self.runtime.motion.current_owner is None)
        )

    def _stop_session_follow(self, session):
        # Every cleanup operation uses this producer's immutable capability.
        # A failed SDK stop may revoke it before raising, so retain session
        # identity to latch that fault while still draining the old producer.
        with self.runtime._state_lock:
            if self._owns_session_cleanup(session):
                self.runtime._follow_stop.set()
        error = None
        try:
            if session.lease is not None:
                session.lease.stop()
        except Exception as exc:
            error = exc
        thread = session.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(2.0)
            if thread.is_alive():
                error = error or TimeoutError("轨迹录制的遥操线程未及时停止")
        try:
            if session.lease is not None:
                session.lease.release(error=error)
        except Exception as exc:
            error = error or exc
        with self.runtime._state_lock:
            if self._owns_session_cleanup(session):
                if error is not None:
                    self.runtime._set_state("fault", str(error))
                    self._event("error", f"轨迹录制停止失败：{error}")
                elif self.runtime.state == "following":
                    self.runtime._set_state("idle")
        if error is not None:
            raise error

    def _recording_finished(self, session, error):
        if session.stopping or self._recording_session is not session:
            return
        current = self._session_following(session)
        try:
            self._stop_session_follow(session)
        except Exception as exc:
            error = error or str(exc)
        # HOME/STOP/fault takeover retains its state and motion ownership.
        with self.runtime._state_lock:
            if (
                error
                and current
                and self.runtime.stop_generation == session.generation
                and self.runtime.state in ("following", "idle")
                and self.runtime.motion.current_owner is None
            ):
                self.runtime._set_state("fault", error)
                self._event("error", f"轨迹录制安全停止：{error}")
        if (
            session.on_finished is not None
            and self.runtime.stop_generation == session.generation
            and self.runtime.state in ("idle", "following", "fault")
        ):
            session.on_finished(error)

    def stop_trajectory_recording(self):
        session = self._recording_session
        if session is not None:
            session.stopping = True
        try:
            if self.runtime._pending_trajectory is None:
                self.runtime._pending_trajectory = self.runtime.trajectory_recorder.stop()
        finally:
            if session is not None:
                self._stop_session_follow(session)
        return self.runtime._pending_trajectory.metadata

    def save_trajectory(self):
        if self.runtime._pending_trajectory is None:
            raise RuntimeError("没有待保存轨迹")
        validate_trajectory(
            self.runtime._pending_trajectory,
            self.runtime.store.data.get("motion", {}).get("joint_limits_rad"),
        )
        path = self.runtime.trajectory_store.save(self.runtime._pending_trajectory)
        self.runtime._pending_trajectory = None
        self.runtime.trajectory_recorder.cancel()
        self._recording_session = None
        self.runtime.list_trajectories()
        self._event("info", f"轨迹已保存：{path}")
        return path

    def cancel_trajectory_recording(self):
        if (
            self._recording_session is not None
            or self.runtime.trajectory_recorder.frames
            or self.runtime._pending_trajectory is not None
        ):
            # Keep the buffer recoverable until both producer stops succeed.
            self.stop_trajectory_recording()
        self.runtime.trajectory_recorder.cancel()
        self.runtime._pending_trajectory = None
        self._recording_session = None

    def list_trajectories(self):
        from dataclasses import asdict

        values = self.runtime.trajectory_store.list()
        self.runtime._trajectory_catalog = [asdict(value) for value in values]
        return self.runtime._trajectory_catalog

    def preview_trajectory(self, trajectory_id):
        self.runtime._trajectory_preview = preview_trajectory(
            self.runtime.trajectory_store.load(trajectory_id)
        )
        return self.runtime._trajectory_preview

    def import_trajectory(self, path, source="legacy_json", episode_index=0):
        from teleop.gello_cr.trajectory.adapters import LegacyJsonAdapter, LeRobotTrajectoryAdapter

        value = (
            LegacyJsonAdapter.load(path)
            if source == "legacy_json"
            else LeRobotTrajectoryAdapter.load(path, episode_index)
            if source == "lerobot"
            else None
        )
        if value is None:
            raise ValueError("Unknown trajectory source")
        validate_trajectory(
            value, self.runtime.store.data.get("motion", {}).get("joint_limits_rad")
        )
        destination = self.runtime.trajectory_store.save(value)
        self.runtime.list_trajectories()
        return destination

    def replay_trajectory(self, trajectory_id, options: ReplayOptions, *, on_finished=None):
        generation = self.runtime.stop_generation
        from teleop.gello_cr.trajectory.validation import (
            validate_options,
            validate_replay_channels,
            validate_replay_speed,
        )

        value = self.runtime.trajectory_store.load(trajectory_id)
        validate_trajectory(
            value, self.runtime.store.data.get("motion", {}).get("joint_limits_rad")
        )
        validate_options(options)
        validate_replay_channels(value, options)
        validate_replay_speed(
            value,
            options,
            math.radians(float(self.runtime.store.data["replay"]["max_joint_speed_deg_s"])),
        )
        if (
            self.runtime.recording
            or self.runtime.trajectory_recorder.frames
            or self.runtime._pending_trajectory is not None
        ):
            raise RuntimeError("请先结束并保存当前轨迹录制")
        if (
            self.runtime._home_lock.locked()
            or self.runtime.replaying
            or self.runtime.state in ("closed", "fault", "preset", "recovering", "point_move")
        ):
            raise RuntimeError("当前状态不允许轨迹回放")
        self.runtime.trajectory_source.check_ready(options.arm_enabled, options.hand_enabled)
        lease = None
        try:
            with self.runtime._state_lock:
                if (
                    self.runtime._stop_generation != generation
                    or self.runtime._shutdown_requested.is_set()
                    or self.runtime._home_lock.locked()
                    or self.runtime.state not in ("idle", "following")
                    or self.runtime.replaying
                ):
                    raise MotionPreempted("Trajectory start cancelled during preparation")
                self.runtime._state = "replay"
                self.runtime._last_error = ""
                self.runtime._replay_stop.clear()
                lease = self.runtime.motion.acquire(
                    MotionSource.REPLAY, allow_preempt=True, on_cancel=self.runtime._replay_stop.set
                )
                self.runtime._trajectory_lease = lease
                self.runtime._trajectory_hand_enabled = options.hand_enabled
            self.runtime._join_follow_producer("Trajectory takeover")
            with self.runtime._state_lock:
                lease.check()
                if self.runtime._stop_generation != generation or self.runtime._replay_stop.is_set():
                    raise MotionPreempted("轨迹回放启动已被停止")
                self.runtime._trajectory_active_id = trajectory_id
                self.runtime._replay_thread = threading.Thread(
                    target=self.runtime._play_trajectory_worker,
                    args=(value, options, lease, generation, on_finished),
                    name="Trajectory-Replay",
                    daemon=True,
                )
                try:
                    self.runtime._start_motion_worker(self.runtime._replay_thread, lease)
                except Exception:
                    self.runtime._replay_thread = None
                    raise
        except Exception as exc:
            if lease is not None:
                lease.release(error=str(exc))
            if self.runtime.stop_generation == generation and self.runtime.state == "replay":
                self.runtime._set_state("fault", str(exc))
            raise

    def _play_trajectory_worker(self, value, options, lease, generation, on_finished):
        error = None
        try:
            self.runtime.trajectory_player.play(
                value,
                options,
                lease=lease,
                max_joint_speed_rad_s=math.radians(
                    float(self.runtime.store.data["replay"]["max_joint_speed_deg_s"])
                ),
            )
        except Exception as exc:
            logging.getLogger("workbench.trajectory").exception("REPLAY_TRAJECTORY failed")
            if self.runtime.stop_generation == generation and self.runtime.state == "replay":
                error = str(exc)
                self.runtime._set_state("fault", error)
            self._event("error", f"轨迹回放失败：{exc}")
        finally:
            lease.release()
            if self.runtime.stop_generation == generation and self.runtime.state == "replay":
                self.runtime._set_state("idle")
            self.runtime._trajectory_active_id = None
            if on_finished is not None:
                on_finished(error)

    def stop_trajectory_replay(self):
        self.runtime._replay_stop.set()
        lease = self.runtime._trajectory_lease
        if lease is not None:
            owned = lease.active
            lease.release()
            if owned and self.runtime._trajectory_hand_enabled:
                self.runtime.o6.hold_current()
        self.runtime.trajectory_player.stop()
        thread = self.runtime._replay_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(3.0)
            if thread.is_alive():
                raise TimeoutError("轨迹回放未及时停止")
        if self.runtime.state == "replay":
            self.runtime._set_state("idle")
