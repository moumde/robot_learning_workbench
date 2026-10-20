"""Public parent framework and transitional imports share actual implementations."""
from pathlib import Path


def test_legacy_domain_imports_share_types_and_private_helpers():
    from gello_cr.app.config_store import _deep_merge as old_merge
    from gello_cr.core.state_machine import Command as OldCommand
    from gello_cr.core.state_machine import WorkflowState as OldState
    from gello_cr.recording.frame import CaptureFrame as OldFrame

    from core.workbench.app.config_store import _deep_merge
    from core.workbench.core.state_machine import Command, WorkflowState
    from core.workbench.recording.frame import CaptureFrame
    assert (OldCommand, OldState, OldFrame, old_merge) == (Command, WorkflowState, CaptureFrame, _deep_merge)


def test_parent_ui_owns_the_implementation_and_designer_resources():
    from gello_cr.ui.main_window import OperatorMainWindow as OldWindow

    import hmi.collection
    from hmi.collection.main_window import OperatorMainWindow
    from hmi.collection.theme import WORKBENCH_STYLESHEET
    assert OldWindow is OperatorMainWindow
    assert OperatorMainWindow.__module__ == "hmi.collection.main_window"
    root = Path(hmi.collection.__file__).parent
    assert (root / "forms/main_window.ui").is_file()
    assert (root / "forms/pages/collection_page.ui").is_file()
    assert WORKBENCH_STYLESHEET


def test_legacy_entry_import_is_the_parent_entry():
    from gello_cr.ui import __main__ as old_entry

    from hmi.collection import __main__ as entry
    assert old_entry is entry
