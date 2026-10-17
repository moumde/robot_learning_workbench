
from __future__ import annotations

import threading
import time

import pytest

from gello_cr.app import ApplicationService, CommandSuperseded
from gello_cr.core.state_machine import Command, WorkflowState


def test_estop_preempts_blocked_normal_handler() -> None:
    service = ApplicationService()
    started = threading.Event()
    release = threading.Event()
    estop_handler_seen = threading.Event()
    normal_errors = []

    def connect(_payload):
        started.set()
        assert release.wait(2.0)

    def estop(_payload):
        assert service.state is WorkflowState.ESTOP
        estop_handler_seen.set()

    service.set_handler(Command.CONNECT, connect)
    service.set_handler(Command.EMERGENCY_STOP, estop)

    def run_connect():
        try:
            service.dispatch(Command.CONNECT)
        except Exception as exc:
            normal_errors.append(exc)

    thread = threading.Thread(target=run_connect)
    thread.start()
    assert started.wait(1.0)

    result = service.dispatch(Command.EMERGENCY_STOP)

    assert result.state is WorkflowState.ESTOP
    assert estop_handler_seen.is_set()
    assert service.state is WorkflowState.ESTOP

    release.set()
    thread.join(1.0)

    assert isinstance(normal_errors[0], CommandSuperseded)
    assert service.state is WorkflowState.ESTOP


def test_late_normal_completion_reasserts_estop() -> None:
    service = ApplicationService()
    started = threading.Event()
    release = threading.Event()
    safety_calls = []

    def connect(_payload):
        started.set()
        assert release.wait(2.0)

    def estop(payload):
        safety_calls.append(dict(payload))

    service.set_handler(Command.CONNECT, connect)
    service.set_handler(Command.EMERGENCY_STOP, estop)

    errors = []

    def guarded():
        try:
            service.dispatch(Command.CONNECT)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=guarded)
    thread.start()
    assert started.wait(1.0)

    service.dispatch(Command.EMERGENCY_STOP)
    release.set()
    thread.join(1.0)

    assert service.state is WorkflowState.ESTOP
    assert isinstance(errors[0], CommandSuperseded)
    assert len(safety_calls) == 2
    assert safety_calls[-1]["superseded_command"] == "CONNECT"


def test_external_fault_can_preempt_normal_handler() -> None:
    service = ApplicationService()
    started = threading.Event()
    release = threading.Event()
    errors = []

    def connect(_payload):
        started.set()
        assert release.wait(2.0)

    service.set_handler(Command.CONNECT, connect)

    def run():
        try:
            service.dispatch(Command.CONNECT)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    assert started.wait(1.0)

    service.report_external_fault("feedback lost")
    assert service.state is WorkflowState.FAULT

    release.set()
    thread.join(1.0)

    assert isinstance(errors[0], CommandSuperseded)
    assert service.state is WorkflowState.FAULT


def test_normal_handlers_remain_serialized() -> None:
    service = ApplicationService()
    active = 0
    maximum = 0
    guard = threading.Lock()
    first_started = threading.Event()
    release_first = threading.Event()

    def connect(_payload):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        first_started.set()
        release_first.wait(2.0)
        with guard:
            active -= 1

    service.set_handler(Command.CONNECT, connect)

    errors = []

    def call():
        try:
            service.dispatch(Command.CONNECT)
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=call)
    t2 = threading.Thread(target=call)
    t1.start()
    assert first_started.wait(1.0)
    t2.start()
    time.sleep(0.05)

    assert maximum == 1

    release_first.set()
    t1.join(1.0)
    t2.join(1.0)

    assert maximum == 1
    assert errors


def test_safety_handler_failure_never_restores_active_state() -> None:
    service = ApplicationService()

    def fail(_payload):
        raise RuntimeError("stop failed")

    service.set_handler(Command.EMERGENCY_STOP, fail)

    with pytest.raises(RuntimeError, match="stop failed"):
        service.dispatch(Command.EMERGENCY_STOP)

    assert service.state is WorkflowState.ESTOP
