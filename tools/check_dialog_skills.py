"""Temporary-character visual regression probes for dialog and Skills styling."""
import os, sys, tempfile, argparse
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from app.ui.dialogs import FeatCatalogDialog
from app.ui.martial_book_dialog import MartialBookDialog
from app.martial_book import MartialBookService
from app.spellbook import SpellBookService
from app.ui.spellbook_dialog import SpellBookDialog
from tools.render_refined_sheet import settle

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output', default='artifacts/dialog-skills-before')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    for font in ('segoeui.ttf','segoeuib.ttf','georgia.ttf','georgiab.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
    app.setFont(QFont('Segoe UI',10))
    with tempfile.TemporaryDirectory() as temp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,temp)
        repo=CharacterRepository(Path(temp)/'preview.db')
        cid=repo.create_character('UI Preview','Spheres')
        repo.add_class_level(cid,'Prodigy',6,'3/4','Good','Poor','Good','prodigy',8,33)
        for sphere in ('Athletics','Boxing','Equipment','Open Hand'):
            repo.add_martial_talent(cid,sphere,sphere=sphere,notes='Example rules description for visual testing.')
        for sphere in ('Warp','Weather','Alteration'):
            repo.add_spell(cid,sphere+' Sphere',system='Sphere',school_or_sphere=sphere,
                catalog_key=sphere.casefold()+':base',catalog_category='Base Sphere')
        window=MainWindow(repo);window.resize(1400,1000);window.show();window.refresh_characters(cid)
        window._set_sheet_type('refined');sheet=window.refined_sheet
        for theme in ('classic','light','dark'):
            window._set_theme(theme);sheet.session.select_tab('skills');settle(app)
            window.grab().save(str(out/f'{theme}-skills.png'))
            assert sheet.skills_section.height() >= sheet.skills_section.layout().minimumSize().height()
            scroll=sheet.refined_pages['skills'][0]
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum());settle(app)
            window.grab().save(str(out/f'{theme}-skills-bottom.png'))
            scroll.verticalScrollBar().setValue(0)
            print(theme,'table',sheet.skill_table.geometry(),'section',sheet.skills_section.geometry(),
                'managed',sheet.skill_table.property('freeformManaged'),sheet.skill_table.property('fillAvailableHeight'),
                'parent',sheet.skill_table.parentWidget().objectName(),
                'minimum',sheet.skills_section.layout().minimumSize(), 'canvas',sheet.refined_pages['skills'][1].size(),flush=True)
            for name,dialog in [('martial',MartialBookDialog(MartialBookService(repo,cid),sheet)),('feats',FeatCatalogDialog([],sheet)),('spells',SpellBookDialog(SpellBookService(repo,cid),sheet))]:
                dialog.show();settle(app);dialog.grab().save(str(out/f'{theme}-{name}.png'));dialog.close();settle(app)
        window.close();repo.close()

if __name__=='__main__':main()
