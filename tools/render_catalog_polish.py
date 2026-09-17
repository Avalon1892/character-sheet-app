"""Read-only catalog previews in every theme; no character database needed."""
import os,sys,argparse
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtWidgets import QApplication,QWidget
from app.ui.dialogs import FeatCatalogDialog,TraitCatalogDialog,MartialTalentCatalogDialog,MagicTalentCatalogDialog,ItemCatalogDialog
from app.ui.dialog_theme import DialogThemeBoundary
from app.ui.refined.theme import stylesheet
from tools.render_refined_sheet import settle

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='artifacts/catalog-ui-polish')
    parser.add_argument('--themes',nargs='+',default=['classic','light','dark'])
    parser.add_argument('--catalogs',nargs='+',default=[])
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    for font in ('segoeui.ttf','segoeuib.ttf','georgia.ttf','georgiab.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
    app.setFont(QFont('Segoe UI',10))
    owner=QWidget();sheet=QWidget(owner);boundary=DialogThemeBoundary(owner)
    for theme in args.themes:
        owner.theme=theme;sheet.setStyleSheet(stylesheet(theme))
        for name,factory in (('feats',lambda:FeatCatalogDialog([],sheet)),('traits',lambda:TraitCatalogDialog([],sheet)),('martial',lambda:MartialTalentCatalogDialog([],sheet)),('magic',lambda:MagicTalentCatalogDialog([],sheet)),('items',lambda:ItemCatalogDialog(sheet))):
            if args.catalogs and name not in args.catalogs:continue
            dialog=factory();boundary.apply(dialog);dialog.resize(1600,900);dialog.show();settle(app)
            dialog.grab().save(str(out/f'{theme}-{name}-empty.png'))
            dialog.results.setCurrentCell(0,0);dialog._queue_current_entry();settle(app)
            dialog.grab().save(str(out/f'{theme}-{name}-selected.png'))
            print(theme,name,'horizontal overflow',dialog.results.horizontalScrollBar().maximum(),flush=True)
            dialog.close();dialog.deleteLater();settle(app)
    owner.close()

if __name__=='__main__':main()
