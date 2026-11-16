"""Keep the software-stop key available in this Workbench's Qt dialogs."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget


class EmergencyStopFilter(QObject):
    def __init__(self, owner, stop):
        super().__init__(owner)
        self._owner = owner
        self._stop = stop
        self._attached = True
        QApplication.instance().installEventFilter(self)
        owner.destroyed.connect(self.detach)

    def detach(self, *args):
        if self._attached:
            application = QApplication.instance()
            if application is not None:
                application.removeEventFilter(self)
            self._attached = False

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.ShortcutOverride, QEvent.KeyPress, QEvent.KeyRelease):
            return False
        if event.key() != Qt.Key_F12:
            return False
        widget = watched if isinstance(watched, QWidget) else None
        while widget is not None and widget is not self._owner:
            widget = widget.parentWidget()
        if widget is None:
            return False
        event.accept()
        if event.type() == QEvent.KeyPress and not event.isAutoRepeat():
            self._stop()
        return True
