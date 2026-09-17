"""Render and verify the revised panels using disposable character data."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from tools.render_refined_sheet import settle

app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
app.setFont(QFont('Segoe UI', 10))
out = Path('artifacts/refined-character-panels'); out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
    repo = CharacterRepository(Path(folder) / 'preview.db')
    cid = repo.create_character('Panel review', 'Spheres')
    repo.add_class_level(cid, 'Prodigy', 5, '3/4', 'Good', 'Poor', 'Good', 'prodigy', 8, 30)
    repo.add_equipment(cid, 'Traveler’s Boots', 'Gear', 1, 1, False, 0, 'untyped', None, '', slot='Feet')
    window = MainWindow(repo); window.refresh_characters(cid); window.show()
    sheet = window.refined_sheet
    for theme in ('classic', 'light', 'dark'):
        window._set_theme(theme)
        window.resize(1500, 1000)
        for page, keys in (('build', ('base_abilities',)), ('core', ('martial_focus',)), ('inventory', ('worn_items', 'equipment_figure'))):
            sheet.session.select_tab(page); settle(app)
            for key in keys:
                section = sheet.custom_sections[key]
                section.grab().save(str(out / f'{theme}-{key}.png'))
            if page == 'inventory':
                row = sheet.custom_sections['worn_items'].parentWidget()
                row.grab().save(str(out / f'{theme}-equipment-row.png'))
                assert sheet.custom_sections['worn_items'].parentWidget() is sheet.custom_sections['equipment_figure'].parentWidget()
        print(theme, 'rendered', flush=True)
    window.close(); window.deleteLater(); app.processEvents(); repo.close()
