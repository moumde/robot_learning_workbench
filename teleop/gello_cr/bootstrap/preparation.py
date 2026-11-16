"""Explicit preparation commands for auxiliary devices and cameras."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from teleop.gello_cr.app import ApplicationService
from teleop.gello_cr.core.state_machine import Command

from .robot_profiles import describe_robot


class OperatorReadinessProvider:
    """Snapshot master/O6/camera readiness without performing hardware I/O."""

    def __init__(
        self,
        *,
        runtime: Any,
        cameras: Any,
        robot_status_snapshot: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        self._runtime = runtime
        self._cameras = cameras
        self._robot_status_snapshot = robot_status_snapshot

    def snapshot(self) -> Mapping[str, Any]:
        master = self._runtime.master_controller
        o6 = self._runtime.o6_controller
        camera = self._cameras.snapshot()
        camera_error = str(camera.error or "")
        if camera.running and not camera_error:
            camera_error = self._runtime.sample_source.readiness_error()

        result = {
            "master_type": str(getattr(master, "master_type", "unknown")),
            "master_connected": bool(getattr(master, "connected", False)),
            "master_error": str(getattr(master, "error", "") or ""),
            "o6_error": str(getattr(o6, "error", "") or ""),
            "o6_connected": bool(getattr(o6, "connected", False)),
            "cameras_running": bool(camera.running),
            "camera_frames_ready": bool(camera.running and not camera_error),
            "camera_error": camera_error,
        }
        store = getattr(self._runtime, "store", None)
        if store is not None:
            config = store.data
            descriptor = describe_robot(config)
            result.update(
                robot_profile=descriptor.profile,
                robot_name=descriptor.name,
                robot_endpoint=f"{config['robot']['ip']} / Robot {config['robot'].get('robot_num', 1)}",
                hand_required=descriptor.hand_required,
                capabilities=asdict(descriptor.capabilities),
            )
            now = time.monotonic()
            master_type = result["master_type"]
            master_cfg = config.get(master_type, {})
            port = master_cfg.get("port")
            if port:
                result["master_discovered"] = result["master_connected"] or Path(port).exists()
            latest = getattr(master, "latest", None)
            if latest is not None:
                sample = latest()
                fresh = sample is not None and 0 <= now - sample.timestamp <= float(
                    master_cfg.get("feedback_timeout_s", 0.5)
                )
                result["master_ready"] = (
                    result["master_connected"] and fresh and not result["master_error"]
                )
                if result["master_connected"] and not fresh and not result["master_error"]:
                    result["master_error"] = "主设备反馈过期或尚未就绪，请检查连接"
            latest_hand = getattr(o6, "latest", None)
            if latest_hand is not None:
                position, fault, sampled_at = latest_hand()
                fresh = position is not None and 0 <= now - sampled_at <= float(
                    config.get("o6", {}).get("feedback_timeout_s", 1.2)
                )
                result["hand_ready"] = (
                    result["o6_connected"]
                    and fresh
                    and fault is not None
                    and not any(fault)
                    and not result["o6_error"]
                )
                if result["o6_connected"] and not result["hand_ready"] and not result["o6_error"]:
                    result["o6_error"] = (
                        f"末端反馈未就绪或故障：{fault}"
                        if fault and any(fault)
                        else "末端反馈过期或尚未就绪"
                    )
        if self._robot_status_snapshot is not None:
            status = self._robot_status_snapshot()
            sampled_at = status.get("sampled_at", 0)
            age = max(0.0, time.monotonic() - sampled_at) if sampled_at else None
            result.update(
                robot_connected=status.get("connected", False),
                servo_state=status.get("servo_state", "unknown"),
                robot_feedback_age_s=age,
                robot_error=status.get("error", ""),
            )
            if status.get("connected") and (age is None or age > 1.5):
                result["servo_state"] = "unknown"
                result["robot_error"] = result["robot_error"] or "机器人反馈过期，请检查连接"
        return result


class OperatorPreparationBindings:
    """Install ApplicationService handlers for preparation commands."""

    def __init__(
        self,
        service: ApplicationService,
        *,
        teleop_engine: Any,
        recorder: Any,
        cameras: Any,
    ) -> None:
        self._service = service
        self._teleop_engine = teleop_engine
        self._recorder = recorder
        self._cameras = cameras

    def install(self) -> OperatorPreparationBindings:
        self._service.set_handler(
            Command.PREPARE_DEVICES,
            self._prepare_devices,
        )
        self._service.set_handler(
            Command.START_CAMERAS,
            self._start_cameras,
        )
        self._service.set_handler(
            Command.STOP_CAMERAS,
            self._stop_cameras,
        )
        return self

    def _prepare_devices(
        self,
        _payload: Mapping[str, Any],
    ) -> Any:
        if self._teleop_engine.devices_connected():
            return None
        return self._teleop_engine.connect_devices()

    def _start_cameras(
        self,
        payload: Mapping[str, Any],
    ) -> Any:
        timeout = float(payload.get("timeout", 5.0))
        return self._cameras.start(timeout=timeout)

    def _stop_cameras(
        self,
        _payload: Mapping[str, Any],
    ) -> None:
        dataset = self._recorder.snapshot()
        if bool(dataset.get("episode_active", False)):
            raise RuntimeError("Episode 正在录制，必须先结束并保存/丢弃后再停止相机")
        if dataset.get("episode_pending", bool(dataset.get("buffered_frames"))):
            raise RuntimeError("Episode 存在待处理帧，必须先保存或丢弃后再停止相机")
        self._cameras.stop()
