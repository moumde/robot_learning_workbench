"""Exercise DAgger ownership with the real engine and simulated devices."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.runtime import TeleopRuntime as TeleopEngine
from teleop.gello_cr.motion import MotionSource
from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


@pytest.fixture
def engine(tmp_path):
    store = TeleopConfigStore(tmp_path / "teleop.json")
    result = TeleopEngine(store, FakeRoArm(), FakeO6())
    result.attach_robot(FakeRobot())
    yield result
    result.stop_follow("test finished")


def controller():
    started = threading.Event()

    def run(*, stop_event):
        started.set()
        assert stop_event.wait(2)

    return SimpleNamespace(
        robot=SimpleNamespace(start_control=Mock()),
        run=run,
        request_stop=Mock(),
        stop=Mock(),
        snapshot=lambda: {"root": "/tmp/raw", "expert_frames": 12},
        started=started,
    )


def test_dagger_reserves_one_motion_producer_and_finalizes_on_stop(engine):
    first = controller()
    engine.start_external_control(first, engine.stop_generation)
    assert first.started.wait(1) and engine.state == "dagger"
    producer = engine._follow_thread
    engine.start_follow()  # Existing start is idempotent while its slot is occupied.
    assert engine._follow_thread is producer
    second = controller()
    with pytest.raises(RuntimeError):
        engine.start_external_control(second, engine.stop_generation)
    second.robot.start_control.assert_not_called()
    engine.stop_follow("stop DAgger")
    first.request_stop.assert_called()
    first.stop.assert_called_once()
    assert not producer.is_alive() and engine.external_control is None
    assert engine.snapshot()["dagger"]["expert_frames"] == 12


def test_estop_generation_cancels_late_dagger_start_before_servoj(engine):
    generation = engine.stop_generation
    engine.emergency_stop("cancel startup")
    pending = controller()
    with pytest.raises(RuntimeError):
        engine.start_external_control(pending, generation)
    pending.robot.start_control.assert_not_called()


def test_home_preempts_dagger_and_finalizes_it_before_move(engine):
    engine.store.data["presets"]["HOME"] = {"robot_joints_deg": [1.0] * 6 + [0.0]}
    running = controller()
    engine.start_external_control(running, engine.stop_generation)
    assert running.started.wait(1)
    producer = engine._follow_thread
    policy_lease = engine._policy_lease
    original_movej = engine.robot.movej

    def home_movej(*args):
        assert not engine._follow_thread.is_alive()
        running.stop.assert_called_once()
        assert engine.motion.current_owner is MotionSource.HOME
        assert engine.state == "preset"
        original_movej(*args)

    engine.robot.movej = home_movej
    engine.return_home()
    assert not producer.is_alive()
    assert not policy_lease.active
    running.request_stop.assert_called()
    assert engine.external_control is None
    assert engine.robot.joints == [1.0] * 6 + [0.0]
    assert engine.o6.position == tuple(
        engine.store.data["o6"]["actions"][engine.store.data["o6"]["open_action"]]
    )
    assert engine.motion.current_owner is None
    assert engine.state == "idle"
