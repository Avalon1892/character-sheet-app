"""Second-pass Refined UI interaction previews using a disposable character."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from tools.render_refined_sheet import settle
from tools.create_validation_character import build_character


def main():
    app=QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+name)
    app.setFont(QFont("Segoe UI",10))
    output=Path(sys.argv[1] if len(sys.argv)>1 else "artifacts/refined-polish-interactions")
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,temp)
        repo=CharacterRepository(Path(temp)/"preview.db")
        cid=build_character(repo,"Aster • Refined Sheet")
        window=MainWindow(repo);window.refresh_characters(cid);window._set_sheet_type("refined")
        window.resize(1600,1000);window.show();settle(app)
        sheet=window.refined_sheet
        for index,field in enumerate(sheet.movement_controls.values()):
            field.set_expression(str(20+index*5))
        sheet._save_movement()
        for theme in ("classic","light","dark"):
            window._set_theme(theme)
            for width in (1600,1100):
                window.resize(width,1000);sheet.session.select_tab("core")
                sheet.movement_edit_toggle.setChecked(True);settle(app)
                sheet.core_scroll.ensureWidgetVisible(sheet.movement_edit_panel);settle(app)
                window.grab().save(str(output/f"{theme}-{width}-movement-editor.png"))
                assert sheet.core_scroll.horizontalScrollBar().maximum()==0
                sheet.movement_edit_toggle.setChecked(False)
            window.resize(1600,1000);sheet.session.select_tab("skills")
            disclosure=sheet.refined_disclosures["special_abilities"]
            disclosure.set_expanded(True);settle(app)
            window.grab().save(str(output/f"{theme}-expanded.png"))
            assert sheet.special_ability_table.verticalScrollBar().maximum()==0
            disclosure.set_expanded(False)
            disclosure.adapter.filter("vision");settle(app)
            window.grab().save(str(output/f"{theme}-filtered.png"))
            disclosure.adapter.filter("")
        window.close();repo.close()
    print(output)


if __name__=="__main__":main()
