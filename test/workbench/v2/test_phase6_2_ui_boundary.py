
from __future__ import annotations

import ast
from test.workbench.fakes.paths import implementation_path

UI_ROOT = implementation_path("hmi/collection")


def _method_source(filename: str, method_name: str) -> str:
    source = (UI_ROOT / filename).read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            return segment
    raise AssertionError(method_name)


def test_async_port_has_separate_normal_and_safety_workers() -> None:
    source = (UI_ROOT / "command_port.py").read_text(encoding="utf-8")

    assert "ApplicationCommand-Normal" in source
    assert "ApplicationCommand-Safety" in source
    assert "_SAFETY_COMMANDS" in source
    assert "Command.EMERGENCY_STOP" in source


def test_main_window_still_never_dispatches_application_service_directly() -> None:
    source = (UI_ROOT / "main_window.py").read_text(encoding="utf-8")

    assert ".dispatch(" not in source
    assert "ApplicationService" not in source


def test_window_closes_command_port() -> None:
    method = _method_source("main_window.py", "closeEvent")

    assert "self._command_port.close(" in method
    assert "self._presenter.close()" in method


def test_window_reports_synchronous_submit_failure_locally() -> None:
    method = _method_source("main_window.py", "_submit")

    assert "try:" in method
    assert "self._command_port.submit(" in method
    assert "ERROR ·" in method
