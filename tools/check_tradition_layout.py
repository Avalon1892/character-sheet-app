"""Verify tradition grouping, visible peer actions, and unchanged dispatch."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication, QPushButton
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from tools.render_refined_sheet import settle

app = QApplication([])
for font in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
app.setFont(QFont('Segoe UI', 10))
out = Path('artifacts/tradition-layout')
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
    repo = CharacterRepository(Path(folder) / 'preview.db')
    cid = repo.create_character('Tradition layout', 'Spheres')
    repo.add_character_tradition(cid, 'preview-casting', 'Casting example', 'Casting')
    repo.add_character_tradition(cid, 'preview-martial', 'Martial example', 'Martial')
    window = MainWindow(repo)
    window.refresh_characters(cid)
    window.show()
    sheet = window.refined_sheet
    for theme in ('classic', 'dark'):
        window._set_theme(theme)
        sheet.session.select_tab('build')
        for width in (1100, 1500):
            window.resize(width, 900)
            settle(app)
            section = sheet.traditions_section
            assert section.isVisible()
            assert section.parentWidget() is sheet.refined_pages['build'][1]
            assert sheet.tradition_table.rowCount() == 2
            assert not sheet.sphere_build_section.isAncestorOf(sheet.tradition_table)
            layout = section.parentWidget().layout()
            assert layout.indexOf(sheet.optional_traditions_section) == layout.indexOf(section) + 1
            buttons = [b for b in section.findChildren(QPushButton) if b.property('prominentAction')]
            assert len(buttons) == 2 and all(b.isVisible() for b in buttons)
            with patch.object(sheet, '_add_tradition') as add:
                for button in buttons:
                    button.click()
                assert {call.args[0] for call in add.call_args_list} == {'Casting', 'Martial'}
            section.grab().save(str(out / f'{theme}-{width}.png'))
        print(theme, 'adjacent tradition boxes and both actions verified', flush=True)
    window.close()
    app.processEvents()
    repo.close()
