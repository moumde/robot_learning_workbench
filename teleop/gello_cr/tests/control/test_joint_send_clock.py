"""A coarse clock must not turn healthy following into a recording fault."""

from dataclasses import replace

from teleop.gello_cr.tests.control.test_teleop_dispatch_safety import loop  # noqa: F401


def test_equal_send_timestamps_do_not_fault_following(loop, monkeypatch):  # noqa: F811
    telemetry = []
    loop.controller.hooks = replace(loop.controller.hooks, publish_telemetry=telemetry.append)
    loop.robot.stop_after = 2
    # Model two healthy bus sends within one platform clock tick.
    monkeypatch.setattr(loop.stop, "wait", lambda timeout=None: loop.stop.is_set())
    loop.run("joint")
    assert len(loop.robot.targets) == 2
    assert loop.state.value != "fault"
    assert telemetry[-1]["sent_count"] == 2
    assert telemetry[-1]["send_hz"] == 0.0
