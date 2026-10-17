
from __future__ import annotations

import threading
import time

import pytest

from gello_cr.app import ApplicationService, CommandSuperseded
from gello_cr.core.state_machine import Command, WorkflowState
from gello_cr.ui.command_port import (
    AsyncApplicationCommandPort,
    CommandPortClosed,
    CommandPortError,
    CommandRequest,
)


def test_normal_submit_is_non_blocking_for_long_handler() -> None:
    service = ApplicationService()
    started = threading.Event()
    release = threading.Event()

    def connect(_payload):
        started.set()
        release.wait(2.0)

    service.set_handler(Command.CONNECT, connect)
    port = AsyncApplicationCommandPort(service)

    before = time.monotonic()
    port.submit(CommandRequest.create(Command.CONNECT))
    elapsed = time.monotonic() - before

    assert elapsed < 0.1
    assert started.wait(1.0)

    release.set()
    port.close()


def test_safety_lane_bypasses_blocked_normal_lane() -> None:
    service = ApplicationService()
    normal_started = threading.Event()
    release_normal = threading.Event()
    safety_seen = threading.Event()

    def connect(_payload):
        normal_started.set()
        release_normal.wait(2.0)

    def estop(_payload):
        safety_seen.set()

    service.set_handler(Command.CONNECT, connect)
    service.set_handler(Command.EMERGENCY_STOP, estop)

    errors = []
    port = AsyncApplicationCommandPort(
        service,
        error_callback=lambda _request, exc: errors.append(exc),
    )

    port.submit(CommandRequest.create(Command.CONNECT))
    assert normal_started.wait(1.0)

    port.submit(
        CommandRequest.create(
            Command.EMERGENCY_STOP,
            {"reason": "operator"},
        )
    )

    assert safety_seen.wait(1.0)
    assert service.state is WorkflowState.ESTOP

    release_normal.set()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if any(isinstance(exc, CommandSuperseded) for exc in errors):
            break
        time.sleep(0.01)

    assert any(isinstance(exc, CommandSuperseded) for exc in errors)
    assert service.state is WorkflowState.ESTOP
    port.close()


def test_normal_lane_preserves_fifo_order() -> None:
    service = ApplicationService()
    calls = []

    service.set_handler(
        Command.CONNECT,
        lambda _payload: calls.append("connect"),
    )
    service.set_handler(
        Command.POWER_ON,
        lambda _payload: calls.append("power_on"),
    )

    port = AsyncApplicationCommandPort(service)
    port.submit(CommandRequest.create(Command.CONNECT))
    port.submit(CommandRequest.create(Command.POWER_ON))

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and len(calls) < 2:
        time.sleep(0.01)

    assert calls == ["connect", "power_on"]
    assert service.state is WorkflowState.ROBOT_ENABLED
    port.close()


def test_close_rejects_new_submissions() -> None:
    service = ApplicationService()
    port = AsyncApplicationCommandPort(service)
    port.close()

    with pytest.raises(CommandPortClosed):
        port.submit(CommandRequest.create(Command.CONNECT))


def test_close_discards_pending_normal_commands() -> None:
    service = ApplicationService()
    first_started = threading.Event()
    release = threading.Event()
    calls = []

    def connect(_payload):
        calls.append("connect")
        first_started.set()
        release.wait(2.0)

    service.set_handler(Command.CONNECT, connect)
    port = AsyncApplicationCommandPort(service)

    port.submit(CommandRequest.create(Command.CONNECT))
    assert first_started.wait(1.0)
    port.submit(CommandRequest.create(Command.POWER_ON))

    with pytest.raises(CommandPortError, match="尚未退出"):
        port.close(timeout=0.0)
    release.set()
    time.sleep(0.05)

    assert calls == ["connect"]
