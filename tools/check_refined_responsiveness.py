"""Disposable-character timing and visual checks for Refined play controls."""
import os
import sys
import time
import json
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QEvent
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from tests import test_exploitant_moldable_talents as fixtures


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/refined-speed")
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
    app.setFont(QFont("Segoe UI", 10))
    fixture = fixtures.ExploitantMoldableTalentTests()
    fixture.setUp()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, fixture.folder.name)
    started = time.perf_counter()
    window = MainWindow(fixture.repository)
    timings = {"window_creation_seconds": time.perf_counter() - started}
    print(timings, flush=True)
    try:
        started = time.perf_counter()
        window.resize(1500, 950)
        window.refresh_characters(fixture.character)
        window.show()
        app.processEvents()
        timings["first_character_load_seconds"] = time.perf_counter() - started
        print(timings, flush=True)
        assert window.sheet_type == "refined"
        assert window.original_spheres_sheet is None and window.ultra_sheet is None
        sheet = window.refined_sheet
        control = sheet.refined_disclosures["special_abilities"]
        for theme in ("classic", "light", "dark"):
            window._set_theme(theme)
            sheet.session.select_tab("skills")
            control.set_expanded(False)
            app.processEvents()
            assert control.isVisible()
            window.grab().save(str(output / f"{theme}-collapsed.png"))
            started = time.perf_counter()
            control.click()
            timings[f"{theme}_show_all_ms"] = 1000 * (time.perf_counter() - started)
            app.processEvents()
            t = sheet.special_ability_table
            print({"theme": theme, "expanded": control.adapter.expanded,
                   "rows": t.rowCount(), "height": t.height(), "max_height": t.maximumHeight(),
                   "viewport": t.viewport().height(), "last_row": t.rowViewportPosition(t.rowCount()-1),
                   "last_row_height": t.rowHeight(t.rowCount()-1),
                   "managed": t.property("freeformManaged"), "fill": t.property("fillAvailableHeight")}, flush=True)
            s = sheet.special_abilities_section
            print({"section_height": s.height(), "section_min": s.minimumHeight(),
                   "section_max": s.maximumHeight(), "section_hint": s.sizeHint().height(),
                   "section_layout_min": s.layout().minimumSize().height()}, flush=True)
            assert s.height() >= s.layout().minimumSize().height()
            assert all(not sheet.special_ability_table.isRowHidden(r)
                       for r in range(sheet.special_ability_table.rowCount()))
            assert sheet.special_ability_table.verticalScrollBar().maximum() == 0
            window.grab().save(str(output / f"{theme}-expanded.png"))
        started = time.perf_counter()
        sheet.refresh_all()
        app.processEvents()
        timings["refresh_seconds"] = time.perf_counter() - started
        print(json.dumps(timings, indent=2), flush=True)
        (output / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    finally:
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        fixture.tearDown()


if __name__ == "__main__":
    main()
