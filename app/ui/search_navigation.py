"""Reusable keyboard access to an existing search field; no search logic."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut


def install_search_shortcut(owner, field):
    shortcut = QShortcut(QKeySequence.StandardKey.Find, owner)
    shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
    def focus_search():
        target = field() if callable(field) else field
        if target is not None and target.isVisible():
            target.setFocus(Qt.FocusReason.ShortcutFocusReason)
            target.selectAll()
    shortcut.activated.connect(focus_search)
    return shortcut
