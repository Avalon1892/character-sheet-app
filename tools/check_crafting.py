"""Disposable crafting-page and dialog visual checks in every theme."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from app.ui.crafting import CraftingCatalogDialog
from tools.render_refined_sheet import settle

app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
app.setFont(QFont('Segoe UI', 10))
out = Path('artifacts/crafting'); out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
    repo = CharacterRepository(Path(folder) / 'preview.db')
    cid = repo.create_character('Crafting review', 'Spheres')
    repo.add_class_level(cid, 'Wizard', 5, '1/2', 'Poor', 'Poor', 'Good', 'wizard', 6, 20)
    window = MainWindow(repo); window.refresh_characters(cid); window.resize(1500,1000); window.show()
    sheet = window.refined_sheet
    for theme in ('classic', 'light', 'dark'):
        window._set_theme(theme); sheet.session.select_tab('crafting'); settle(app)
        sheet.crafting_section.grab().save(str(out/f'{theme}-page.png'))
        for feat, search in ((None,'Longsword'), ('Craft Wondrous Item','Bag of Holding'), ('Craft Magic Arms and Armor','Keen')):
            dialog = CraftingCatalogDialog(repo,cid,feat,window); dialog.show(); settle(app); dialog.resize(1400,840); settle(app)
            dialog.search.setText(search); dialog.debounce.flush(); dialog.table.selectRow(0); settle(app)
            if feat == 'Craft Magic Arms and Armor':
                dialog.base_item.setCurrentIndex(dialog.base_item.findText('Longsword')); settle(app)
            kind = 'property' if feat == 'Craft Magic Arms and Armor' else ('magic' if feat else 'mundane')
            dialog.grab().save(str(out/f'{theme}-{kind}.png'))
            dialog.close(); dialog.deleteLater(); app.processEvents()
        print(theme, 'rendered', flush=True)
    window.close(); window.deleteLater(); app.processEvents(); repo.close()
