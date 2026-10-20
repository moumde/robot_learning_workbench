import json
from types import SimpleNamespace

from teleop.gello_cr.cli.replay_trajectory import main
from teleop.gello_cr.trajectory import TrajectoryFrame, TrajectoryStore, make_trajectory


def test_cli_previews_saved_trajectory_without_constructing_runtime(tmp_path, capsys):
    value = make_trajectory("saved demo", [TrajectoryFrame(0.0, robot_joint_state=(0.0,) * 6)])
    directory = TrajectoryStore(tmp_path).save(value)

    def forbidden(_paths):
        raise AssertionError("preview must not construct hardware runtime")

    assert main([str(directory)], runtime_factory=forbidden) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "saved demo"


def test_cli_execute_passes_options_to_shared_player_and_closes_runtime(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(
        json.dumps(
            {
                "version": 3,
                "robot_joint_indices": [6],
                "frames": [
                    {"t": 0.0, "robot_joints_deg": [0.0] * 7},
                ],
            }
        )
    )
    calls = []
    runtime = SimpleNamespace(
        cr3a_lifecycle=SimpleNamespace(
            connect=lambda: calls.append("connect"), power_on=lambda: calls.append("power_on")
        ),
        store=SimpleNamespace(data={"replay": {"max_joint_speed_deg_s": 120.0}, "motion": {}}),
        teleop_engine=SimpleNamespace(
            trajectory_player=SimpleNamespace(
                play=lambda value, options, **kw: calls.append((value, options))
            ),
            trajectory_source=SimpleNamespace(check_ready=lambda arm, hand: None),
        ),
        close=lambda: calls.append("close"),
    )

    def factory(_paths):
        return SimpleNamespace(build=lambda: runtime)

    assert (
        main(
            [str(path), "--execute", "--arm-only", "--time-scale", ".5", "--repeat", "2"],
            runtime_factory=factory,
        )
        == 0
    )
    assert calls[:2] == ["connect", "power_on"]
    value, options = calls[2]
    assert value.metadata.joint_mask == (False,) * 5 + (True,)
    assert not options.hand_enabled
    assert options.time_scale == 0.5 and options.repeat == 2
    assert calls[-1] == "close"
