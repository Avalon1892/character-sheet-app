from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete as delete_qt_object, isValid

from app.ui.components import FormulaLineEdit


class FormulaLineEditLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_pending_focus_hide_is_safe_after_cpp_parent_deletion(self) -> None:
        parent = QWidget()
        editor = FormulaLineEdit(parent=parent)
        editor.eventFilter(editor, QEvent(QEvent.Type.FocusOut))
        self.assertTrue(editor._completion_hide_timer.isActive())

        uncaught: list[tuple] = []
        previous_hook = sys.excepthook
        sys.excepthook = lambda *exception: uncaught.append(exception)
        try:
            delete_qt_object(parent)
            self.assertFalse(isValid(editor))
            # A queued Python callback may still own the wrapper.  Calling the
            # same slot directly must also be a harmless no-op.
            editor._hide_completion_if_inactive()
            self.application.processEvents()
        finally:
            sys.excepthook = previous_hook
        self.assertEqual([], uncaught)

    def test_explicit_completion_disposal_is_idempotent(self) -> None:
        editor = FormulaLineEdit()
        try:
            editor.eventFilter(editor, QEvent(QEvent.Type.FocusOut))
            editor._dispose_formula_completion()
            editor._dispose_formula_completion()
            self.assertTrue(editor._completion_disposed)
            self.assertFalse(editor._completion_hide_timer.isActive())
            self.assertFalse(editor.completion_popup.isVisible())
        finally:
            editor.deleteLater()
            self.application.processEvents()


if __name__ == "__main__":
    unittest.main()
