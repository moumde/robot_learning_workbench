
from __future__ import annotations

import pytest

from gello_cr.core.state_machine import Command
from gello_cr.ui.command_port import CallbackCommandPort, CommandRequest


def test_callback_command_port_receives_immutable_request() -> None:
    received = []
    port = CallbackCommandPort(received.append)

    request = CommandRequest.create(
        Command.START_EPISODE,
        {"task": "pick", "base_root": "/tmp/data"},
    )
    port.submit(request)

    assert received == [request]
    assert dict(request.payload) == {
        "task": "pick",
        "base_root": "/tmp/data",
    }
    with pytest.raises(TypeError):
        request.payload["task"] = "changed"  # type: ignore[index]


def test_callback_command_port_rejects_wrong_type() -> None:
    port = CallbackCommandPort(lambda request: None)

    with pytest.raises(TypeError, match="CommandRequest"):
        port.submit(Command.CONNECT)  # type: ignore[arg-type]
