
from __future__ import annotations

import threading

import pytest

from gello_cr.app.event_buffer import ApplicationEventBuffer
from gello_cr.app.events import AppEvent, EventLevel
from gello_cr.core.state_machine import WorkflowState


def _event(sequence: int) -> AppEvent:
    return AppEvent(
        sequence=sequence,
        kind="test",
        level=EventLevel.INFO,
        state=WorkflowState.CONNECTED,
        message=f"event-{sequence}",
    )


def test_buffer_preserves_fifo_order() -> None:
    buffer = ApplicationEventBuffer(capacity=4)
    buffer.push(_event(1))
    buffer.push(_event(2))
    buffer.push(_event(3))

    assert [event.sequence for event in buffer.drain()] == [1, 2, 3]
    assert len(buffer) == 0


def test_buffer_drops_oldest_when_capacity_is_exceeded() -> None:
    buffer = ApplicationEventBuffer(capacity=2)
    buffer.push(_event(1))
    buffer.push(_event(2))
    buffer.push(_event(3))

    assert buffer.dropped_count == 1
    assert [event.sequence for event in buffer.drain()] == [2, 3]


def test_partial_drain_preserves_remaining_events() -> None:
    buffer = ApplicationEventBuffer(capacity=4)
    for value in range(4):
        buffer.push(_event(value))

    assert [event.sequence for event in buffer.drain(limit=2)] == [0, 1]
    assert [event.sequence for event in buffer.drain()] == [2, 3]


def test_zero_limit_drains_nothing() -> None:
    buffer = ApplicationEventBuffer()
    buffer.push(_event(1))

    assert buffer.drain(limit=0) == ()
    assert len(buffer) == 1


def test_invalid_capacity_and_limit_are_rejected() -> None:
    with pytest.raises(ValueError, match="capacity"):
        ApplicationEventBuffer(capacity=0)

    buffer = ApplicationEventBuffer()
    with pytest.raises(ValueError, match="limit"):
        buffer.drain(limit=-1)


def test_non_app_event_is_rejected() -> None:
    buffer = ApplicationEventBuffer()

    with pytest.raises(TypeError, match="AppEvent"):
        buffer.push("bad")  # type: ignore[arg-type]


def test_buffer_accepts_concurrent_producers() -> None:
    buffer = ApplicationEventBuffer(capacity=200)

    def producer(start: int) -> None:
        for value in range(start, start + 50):
            buffer.push(_event(value))

    threads = [
        threading.Thread(target=producer, args=(0,)),
        threading.Thread(target=producer, args=(50,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    events = buffer.drain()
    assert len(events) == 100
    assert {event.sequence for event in events} == set(range(100))
    assert buffer.dropped_count == 0
