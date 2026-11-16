"""Create a PySide6 window from an already-composed OperatorBackend."""

from __future__ import annotations

from .backend import OperatorBackend


def create_operator_window(
    backend: OperatorBackend,
    *,
    refresh_ms: int = 100,
    close_callback=None,
    settings_factory=None,
):
    """Return the PySide6 window without starting the GUI event loop or hardware."""

    # Lazy import keeps ordinary V2 unit tests independent of PySide6.
    from .main_window import OperatorMainWindow

    return OperatorMainWindow(
        backend.presenter,
        backend.command_port,
        refresh_ms=refresh_ms,
        close_callback=close_callback,
        settings_factory=settings_factory,
    )
