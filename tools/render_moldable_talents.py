"""Render the temporary-talent editor with a disposable character, never live data."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent
from PySide6.QtGui import QFontDatabase, QFont
from app.content import martial_entry, magic_entry
from app.exploitant_rules import save_moldable_entries
from app.ui.moldable_talents_dialog import MoldableTalentsDialog
from app.ui.theme import style_sheet
from tests import test_exploitant_moldable_talents as fixtures


def main():
    app = QApplication.instance() or QApplication([])
    for font in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + font)
    app.setFont(QFont("Segoe UI", 9))
    fixture = fixtures.ExploitantMoldableTalentTests()
    fixture.setUp()
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/moldable-dialog")
    output.mkdir(parents=True, exist_ok=True)
    try:
        selections = [fixture._record(martial_entry("boxing:base"), "martial"),
                      fixture._record(magic_entry("warp:base"), "magic")]
        save_moldable_entries(fixture.repository, fixture.character, selections)
        for theme in ("classic", "light", "dark"):
            app.setStyleSheet(style_sheet(theme))
            dialog = MoldableTalentsDialog(fixture.repository, fixture.character, 3, locked_count=2)
            dialog.sphere.setCurrentText("Equipment")
            dialog.show()
            for width in (1560, 1200):
                dialog.resize(width, 840)
                app.processEvents()
                dialog.results.resizeRowsToContents()
                dialog.results.setCurrentCell(3, 0)
                app.processEvents()
                assert dialog.results.columnWidth(0) >= 230
                assert not dialog.clear_all_button.isEnabled()
                assert dialog.grab().save(str(output / f"{theme}-{width}.png"))
            dialog.close()
            dialog.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    finally:
        fixture.tearDown()
    print(output.resolve())


if __name__ == "__main__":
    main()
