"""Render independent sample characters; never opens the live database."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import sys,time,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtWidgets import QApplication,QWidget
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from tools.create_validation_character import build_character

def settle(app):
    until=time.monotonic()+.4
    while time.monotonic()<until:
        app.processEvents()

def main():
    app=QApplication.instance() or QApplication([])
    for font in ("segoeui.ttf","segoeuib.ttf","georgia.ttf","georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+font)
    app.setFont(QFont("Segoe UI",10))
    output=Path(sys.argv[1] if len(sys.argv)>1 else "artifacts/refined-preview");output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,temp)
        repo=CharacterRepository(Path(temp)/"preview.db")
        cid=build_character(repo,"Aster • Refined Sheet")
        window=MainWindow(repo);window.resize(1600,1000);window.refresh_characters(cid)
        window._set_sheet_type("refined");window.show();settle(app)
        quick="--quick" in sys.argv
        requested=next((arg.split("=",1)[1] for arg in sys.argv if arg.startswith("--pages=")),"")
        only_pages=set(requested.split(",")) if requested else None
        for theme in (("classic",) if quick else ("classic","dark")):
            window._set_theme(theme)
            for width,height in ((1600,1000),(1100,800)):
                window.resize(width,height)
                for i in range(window.refined_sheet.page_tabs.count()):
                    if not window.refined_sheet.page_tabs.isTabVisible(i):continue
                    if only_pages and window.refined_sheet.session.tabs._key_at(i) not in only_pages:continue
                    if quick and window.refined_sheet.session.tabs._key_at(i) not in ("core","inventory"):continue
                    window.refined_sheet.page_tabs.setCurrentIndex(i);settle(app)
                    window.grab().save(str(output/f"{theme}-{width}-{window.refined_sheet.session.tabs.current_key()}.png"))
                    if quick:
                        from app.ui.refined.components import ResponsiveRow
                        data=[{"width":width,"class":type(w).__name__,"key":w.property("customizationId"),"hidden":w.isHidden(),"rect":w.geometry().getRect(),"min":(w.minimumSizeHint().width(),w.minimumSizeHint().height()),"hint":(w.sizeHint().width(),w.sizeHint().height()),"children":[(type(c).__name__,c.isHidden(),c.geometry().getRect()) for c in w.findChildren(QWidget,options=__import__('PySide6.QtCore',fromlist=['Qt']).Qt.FindChildOption.FindDirectChildrenOnly)]} for w in window.refined_sheet.findChildren(ResponsiveRow)]
                        (output/f"geometry-{width}.json").write_text(json.dumps(data,indent=2))
        window.close();repo.close()
    print(output)

if __name__=="__main__":main()
