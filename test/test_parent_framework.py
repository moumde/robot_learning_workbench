"""Public parent framework contracts, UI resources and executable entry."""
from pathlib import Path
from types import SimpleNamespace


def test_parent_exports_compose_application_commands_and_capture_values():
    from teleop.gello_cr.app import ApplicationService, ApplicationSnapshot, CommandResult
    from teleop.gello_cr.app.config_store import _deep_merge
    from teleop.gello_cr.core import Command, WorkflowState
    from teleop.gello_cr.recording import CaptureFrame

    service = ApplicationService(handlers={Command.CONNECT: lambda payload: payload["name"]})
    result = service.dispatch(Command.CONNECT, {"name": "offline-fake"})
    assert isinstance(result, CommandResult)
    assert result.value == "offline-fake"
    assert result.previous_state is WorkflowState.OFFLINE
    assert result.state is WorkflowState.CONNECTED
    assert isinstance(service.snapshot(), ApplicationSnapshot)
    config = {"dataset": {"fps": 20, "task": "collect"}}
    merged = _deep_merge(config, {"dataset": {"fps": 10}})
    assert merged == {"dataset": {"fps": 10, "task": "collect"}}
    assert config == {"dataset": {"fps": 20, "task": "collect"}}
    frame = CaptureFrame(1.0, (0.1,), (0.2,), {}, metadata={"task": "collect"})
    assert (frame.timestamp, frame.observation_state, frame.action) == (1.0, (0.1,), (0.2,))
    assert frame.metadata == {"task": "collect"}


def test_parent_ui_owns_the_implementation_and_designer_resources():
    import teleop.gello_cr.ui
    from teleop.gello_cr.ui.main_window import OperatorMainWindow
    from teleop.gello_cr.ui.theme import WORKBENCH_STYLESHEET

    assert OperatorMainWindow.__module__ == "teleop.gello_cr.ui.main_window"
    root = Path(teleop.gello_cr.ui.__file__).parent
    assert (root / "forms/main_window.ui").is_file()
    assert (root / "forms/pages/collection_page.ui").is_file()
    assert WORKBENCH_STYLESHEET


def test_parent_entry_check_only_reports_state_and_closes_application(tmp_path, capsys):
    from teleop.gello_cr.core import WorkflowState
    from teleop.gello_cr.ui.__main__ import main

    closed, built = [], []
    operator = SimpleNamespace(
        backend=SimpleNamespace(service=SimpleNamespace(state=WorkflowState.OFFLINE)),
        cameras=SimpleNamespace(running=False),
        runtime=SimpleNamespace(store=SimpleNamespace(data={
            "logging": {"level": "INFO"}, "master": {"type": "gello"},
        })),
        close=lambda: closed.append(True),
    )

    def application_factory(repo_root):
        built.append(repo_root)
        return operator

    assert main(["--repo-root", str(tmp_path), "--check-only"],
                application_factory=application_factory) == 0
    output = capsys.readouterr().out
    assert "workflow=OFFLINE" in output
    assert "master=gello" in output
    assert "cameras=stopped" in output
    assert "hardware_connections=not_started" in output
    assert built == [tmp_path]
    assert closed == [True]
