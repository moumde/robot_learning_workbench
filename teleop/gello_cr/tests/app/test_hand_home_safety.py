import time

import pytest

from gello_cr.app.config_store import TeleopConfigStore
from gello_cr.app.runtime import TeleopRuntime
from tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


@pytest.fixture
def runtime(tmp_path):
    store = TeleopConfigStore(tmp_path / "workbench.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    engine = TeleopRuntime(store, FakeRoArm(), FakeO6())
    engine.attach_robot(FakeRobot())
    yield engine
    engine.shutdown()


@pytest.mark.parametrize("stage", ["feedback", "profile"])
def test_hand_action_cannot_restart_after_emergency_stop(runtime, stage):
    hand = runtime.o6
    target = tuple(runtime.store.data["o6"]["actions"]["抓取"])
    original = hand.latest if stage == "feedback" else hand.set_profile
    interrupted = False

    def stop_then_return(*args):
        nonlocal interrupted
        result = original(*args)
        if not interrupted:
            interrupted = True
            runtime.emergency_stop("test stop during hand startup")
        return result

    if stage == "feedback":
        hand.latest = stop_then_return
    else:
        hand.set_profile = stop_then_return
    with pytest.raises(RuntimeError, match="停止|取消"):
        runtime.execute_o6_action("抓取")
    assert target not in hand.targets
    assert runtime.state == "fault"
    assert not runtime.o6_action_active


def test_save_home_rejects_expired_hand_feedback(runtime):
    previous = runtime.save_home()
    hand = runtime.o6
    hand.latest = lambda: (hand.position, hand.fault, time.monotonic() - 10)
    with pytest.raises(RuntimeError, match="feedback expired"):
        runtime.save_home()
    assert runtime.store.data["presets"]["HOME"] == previous


def test_home_never_moves_with_expired_connected_hand_feedback(runtime):
    runtime.save_home()
    hand = runtime.o6
    hand.latest = lambda: (hand.position, hand.fault, time.monotonic() - 10)
    with pytest.raises(RuntimeError, match="feedback expired"):
        runtime.return_home()
    assert runtime.robot.movej_targets == []
    assert runtime.motion.current_owner is None


def test_home_cannot_report_success_using_expired_arrival_feedback(runtime):
    runtime.save_home()
    hand = runtime.o6
    hand.latest = lambda: (
        hand.position, hand.fault,
        time.monotonic() - (10 if runtime.robot.movej_targets else 0),
    )
    with pytest.raises(RuntimeError, match="feedback expired"):
        runtime.return_home()
    assert runtime.state == "fault"
    assert runtime.motion.current_owner is None
