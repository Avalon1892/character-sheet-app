"""Render and check the paired Skills page with a disposable populated character."""
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QEvent
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from tools.create_validation_character import build_character
from tools.render_refined_sheet import settle


def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else "artifacts/skills-reference-final")
    output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf","segoeuib.ttf","georgia.ttf","georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+name)
    app.setFont(QFont("Segoe UI",10))
    with tempfile.TemporaryDirectory() as temp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,temp)
        repo=CharacterRepository(Path(temp)/"preview.db")
        cid=build_character(repo,"Skills & Special Abilities")
        window=MainWindow(repo);window.resize(1600,1000)
        window.refresh_characters(cid);window.show()
        sheet=window.refined_sheet
        sheet.session.select_tab("skills")
        scroll=sheet.refined_pages["skills"][0]
        control=sheet.refined_disclosures["special_abilities"]
        try:
            for theme in ("classic","light","dark"):
                window._set_theme(theme)
                for width in (1600,1100,1400):
                    window.resize(width,1000);sheet._refresh_skills();settle(app)
                    for expanded in (False,True):
                        control.set_expanded(expanded);settle(app)
                        scroll.verticalScrollBar().setValue(0)
                        for section in (sheet.skills_section,sheet.special_abilities_section):
                            assert section.height()>=section.layout().minimumSize().height(), (theme,width,section.size(),section.layout().minimumSize())
                        assert scroll.horizontalScrollBar().maximum()==0
                        if width>=1400:
                            assert sheet.skills_section.width()>1.8*sheet.special_abilities_section.width()
                            assert sheet.skills_section.y()==sheet.special_abilities_section.y()
                        else:
                            assert sheet.special_abilities_section.y()>sheet.skills_section.geometry().bottom()
                        for table in (sheet.skill_table,sheet.special_ability_table):
                            assert table.verticalScrollBar().maximum()==0
                            assert table.horizontalScrollBar().maximum()==0
                        if width!=1400:
                            window.grab().save(str(output/f"{theme}-{width}-{'expanded' if expanded else 'preview'}.png"))
                        if expanded:
                            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum());settle(app)
                            if width!=1400:window.grab().save(str(output/f"{theme}-{width}-bottom.png"))
                    print(theme,width,"layout and scrolling OK",flush=True)
        finally:
            window.close();window.deleteLater()
            app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            repo.close()
    print(output)


if __name__=="__main__":main()
