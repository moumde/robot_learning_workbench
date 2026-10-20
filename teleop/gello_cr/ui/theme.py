"""Package-owned workbench theme and semantic state helpers."""

from importlib.resources import files

WORKBENCH_STYLESHEET = files("teleop.gello_cr.ui").joinpath("styles/app.qss").read_text(encoding="utf-8")


def set_state(widget, state):
    """Repolish only when the semantic state actually changes."""
    if widget.property("state") != state:
        widget.setProperty("state", state)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
