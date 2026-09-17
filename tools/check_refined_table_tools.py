"""Exercise Refined filters and search in real pages, with a temporary database."""
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QEvent
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from tools.create_validation_character import build_character
from tools.render_refined_sheet import settle


def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else "artifacts/refined-table-tools")
    output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf","segoeuib.ttf","georgia.ttf","georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+name)
    app.setFont(QFont("Segoe UI",10))
    with tempfile.TemporaryDirectory() as folder:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,folder)
        repo=CharacterRepository(Path(folder)/"preview.db")
        cid=build_character(repo,"Refined usability preview")
        window=MainWindow(repo);window.resize(1500,950);window.refresh_characters(cid);window.show()
        sheet=window.refined_sheet
        try:
            for theme in ("classic","light","dark"):
                window._set_theme(theme)
                for width in (1500,1100):
                    window.resize(width,950)
                    sheet.session.select_tab("skills")
                    bar=sheet.refined_page_searches["skills"]
                    bar.reset();settle(app)
                    sheet.refined_skill_filter.setCurrentText("With ranks");settle(app)
                    assert "skills" in bar.feedback.text()
                    assert sheet.special_ability_table.rowCount()>0
                    window.grab().save(str(output/f"{theme}-{width}-ranked.png"))
                    bar.field.setText("knowledge");bar.apply();settle(app)
                    assert "match" in bar.feedback.text()
                    window.grab().save(str(output/f"{theme}-{width}-search.png"))
                    bar.field.setText("no matching entry");bar.apply();settle(app)
                    assert bar.feedback.text()=="0 matches"
                    window.grab().save(str(output/f"{theme}-{width}-empty.png"))
                    bar.clear_button.click();settle(app)
                    assert sheet.refined_skill_filter.currentIndex()==0
                    assert sheet.refined_pages["skills"][0].horizontalScrollBar().maximum()==0
                    for key in ("abilities","inventory"):
                        sheet.session.select_tab(key);settle(app)
                        assert sheet.refined_pages[key][0].horizontalScrollBar().maximum()==0
                    print(theme,width,"search, filters, reset, layout OK",flush=True)
        finally:
            window.close();window.deleteLater();app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            repo.close()
    print(output)


if __name__=="__main__":main()
