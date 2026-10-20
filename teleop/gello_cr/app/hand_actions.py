"""Explicit O6 actions, recovery and hand control handoff."""

from __future__ import annotations

import time
from functools import partial
from typing import Any

from teleop.gello_cr.app.config_store import _six_uint8
from teleop.gello_cr.hardware.o6 import O6_FAULT_NAMES, O6_MOTOR_NAMES


class HandActions:
    """Application service; device I/O remains behind the runtime adapters."""

    def __init__(self, runtime):
        self.runtime = runtime
        self._event = partial(runtime._event, domain="hardware")

    def recover_o6_motor(self, motor_number: int) -> dict[str, Any]:
        """Stop motion and safely re-issue one O6 motor's current-position control."""
        number = int(motor_number)
        with self.runtime._state_lock:
            stop_generation = self.runtime._stop_generation
        if number < 1 or number > len(O6_MOTOR_NAMES):
            raise ValueError("O6 电机编号必须为 1～6")
        if self.runtime._home_thread is not None and self.runtime._home_thread.is_alive():
            raise RuntimeError("预设回位正在执行，请先点击软件紧急停止")
        if (
            self.runtime.state in ("recovering", "point_move", "replay")
            or self.runtime.o6_action_active
        ):
            raise RuntimeError("O6 操作正在执行")
        if not self.runtime.o6.connected:
            raise RuntimeError("请先连接 O6")
        if self.runtime.state == "following":
            self.runtime.stop_follow(f"准备恢复 O6 {number} 号电机")

        position, fault, timestamp = self.runtime.o6.latest()
        if position is None or fault is None:
            raise RuntimeError("O6 尚无完整位置/故障反馈")
        if time.monotonic() - timestamp > float(
            self.runtime.store.data["o6"]["feedback_timeout_s"]
        ):
            raise RuntimeError("O6 反馈超时，禁止重新上力")
        fault_code = int(fault[number - 1])
        if fault_code not in (0, 1):
            fault_name = O6_FAULT_NAMES.get(fault_code, "未知故障")
            raise RuntimeError(
                f"{number} 号电机为 {fault_name}（故障码 {fault_code}），"
                "请先排除硬件故障，程序不会强制上力"
            )

        previous_state = self.runtime.state
        cfg = self.runtime.store.data["o6"]
        with self.runtime._state_lock:
            if self.runtime._stop_generation != stop_generation:
                raise RuntimeError("O6 电机恢复启动已被软件紧急停止")
            self.runtime._hand_action_stop.clear()
            self.runtime._state = "recovering"
            self.runtime._last_error = ""
        self._event(
            "info",
            f"开始恢复 O6 {number} 号电机（{O6_MOTOR_NAMES[number - 1]}）："
            "先保持反馈位置，再重发速度和力矩",
        )
        try:
            result = self.runtime.o6.recover_motor(
                number,
                cfg["speed"][number - 1],
                cfg["torque"][number - 1],
                stop_event=self.runtime._hand_action_stop,
            )
        except Exception as exc:
            if (
                self.runtime._stop_generation == stop_generation
                and self.runtime.state == "recovering"
            ):
                self.runtime._set_state("fault", str(exc))
            raise

        if (
            self.runtime._stop_generation != stop_generation
            or self.runtime.state != "recovering"
            or self.runtime._hand_action_stop.is_set()
        ):
            raise RuntimeError("O6 电机恢复已被软件紧急停止")

        after_fault = tuple(int(value) for value in result["fault_after"])
        after_code = after_fault[number - 1]
        if after_code:
            fault_name = O6_FAULT_NAMES.get(after_code, "未知故障")
            message = (
                f"O6 {number} 号电机恢复后仍为 {fault_name}（故障码 {after_code}）；"
                "请勿继续遥操作，断电检查受阻、温度和供电"
            )
            self.runtime._set_state("fault", message)
            self._event("error", message)
        elif any(after_fault):
            message = (
                f"O6 {number} 号电机故障反馈已为 0，但其他电机仍有故障 "
                f"{list(after_fault)}；请先处理全部故障"
            )
            self.runtime._set_state("fault", message)
            self._event("error", message)
        else:
            restored_state = "master_free" if previous_state == "master_free" else "idle"
            self.runtime._set_state(restored_state)
            self._event(
                "info",
                f"O6 {number} 号电机（{result['motor_name']}）已重发控制，"
                f"位置 {result['position_before']}→{result['position_after']}，故障反馈为 0；"
                "请先低速测试，程序不会自动恢复 XYZ 跟随",
            )
        return result

    def execute_o6_action(self, action_name: str) -> tuple[int, ...]:
        """Move O6 independently while allowing CR5 XYZ following to continue."""
        if self.runtime.master_type == "gello" and self.runtime.state == "following":
            raise RuntimeError("GELLO 跟随时 O6 由 J7 独占控制；请先停止跟随再执行手势")
        with self.runtime._state_lock:
            generation = self.runtime._stop_generation
        name = str(action_name).strip()
        cfg = self.runtime.store.data["o6"]
        actions = cfg.get("actions", {})
        if name not in actions:
            raise ValueError(f"未配置 O6 快捷动作: {name}")
        target = tuple(_six_uint8(actions[name], f"O6 快捷动作 {name}"))
        if self.runtime._home_thread is not None and self.runtime._home_thread.is_alive():
            raise RuntimeError("预设回位正在执行，请先点击软件紧急停止")
        if self.runtime.state in ("recovering", "preset", "point_move", "replay", "closed"):
            raise RuntimeError(f"当前状态 {self.runtime.state} 不允许执行 O6 快捷动作")
        if self.runtime.o6_action_active:
            raise RuntimeError("已有 O6 快捷动作正在执行")
        if not self.runtime.o6.connected:
            raise RuntimeError("请先连接 O6")

        position, fault, timestamp = self.runtime.o6.latest()
        if position is None or fault is None:
            raise RuntimeError("O6 尚无完整位置/故障反馈")
        if time.monotonic() - timestamp > float(cfg["feedback_timeout_s"]):
            raise RuntimeError("O6 反馈超时，禁止执行快捷动作")
        if any(fault):
            raise RuntimeError(f"O6 存在故障，禁止执行快捷动作: {list(fault)}")

        with self.runtime._state_lock:
            if (
                self.runtime._stop_generation != generation
                or self.runtime._shutdown_requested.is_set()
            ):
                raise RuntimeError("O6 快捷动作启动已被停止")
            self.runtime._hand_action_stop.clear()
            self.runtime._o6_manual_override = True
            self.runtime._o6_action_active = True
            self.runtime._o6_action_name = name
        self._event(
            "info",
            f"开始执行 O6 快捷动作“{name}”：目标={list(target)}；"
            "XYZ 跟随可继续，M5 对 O6 的控制已屏蔽",
        )
        try:
            # These device methods enqueue desired values without SDK I/O.
            # Serialize with STOP so no delayed startup can overwrite its hold.
            with self.runtime._state_lock:
                if (
                    self.runtime._stop_generation != generation
                    or self.runtime._hand_action_stop.is_set()
                    or self.runtime._shutdown_requested.is_set()
                ):
                    raise RuntimeError("O6 快捷动作启动已被停止")
                self.runtime.o6.set_profile(cfg["speed"], cfg["torque"])
                if self.runtime._stop_generation != generation:
                    raise RuntimeError("O6 快捷动作启动已被停止")
                self.runtime.o6.set_target(target)
            arrived = self.runtime.o6.wait_until_position(
                target,
                tolerance=6,
                timeout=float(cfg["action_timeout_s"]),
                stop_event=self.runtime._hand_action_stop,
            )
            if not arrived:
                if self.runtime._hand_action_stop.is_set():
                    raise RuntimeError("O6 快捷动作已被软件紧急停止")
                current, current_fault, _ = self.runtime.o6.latest()
                if self.runtime.o6.error:
                    raise RuntimeError(self.runtime.o6.error)
                if current_fault is not None and any(current_fault):
                    raise RuntimeError(f"O6 动作过程中出现故障: {list(current_fault)}")
                raise TimeoutError(
                    f"O6 未在 {float(cfg['action_timeout_s']):g}s 内到达动作“{name}”"
                    f"（当前={list(current) if current is not None else '--'}）"
                )
        except Exception:
            try:
                self.runtime.o6.hold_current()
            except Exception as hold_exc:
                self._event("error", f"O6 失败后保持当前位置失败: {hold_exc}")
            raise
        finally:
            with self.runtime._state_lock:
                self.runtime._o6_action_active = False

        self._event(
            "info",
            f"O6 快捷动作“{name}”完成；手势保持，M5 仍不会控制 O6",
        )
        return target
