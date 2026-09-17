"""Offscreen integration and visual verification using disposable characters."""
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.optional_traditions import OptionalTraditionService
from app.ui.main_window import MainWindow, CodexDialog
from app.ui.optional_traditions import OptionalTraditionDialog
from app.ui.dialog_theme import dialog_stylesheet
from tools.render_refined_sheet import settle

app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
app.setFont(QFont('Segoe UI', 10))
output = Path('artifacts/optional-traditions')
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
    repo = CharacterRepository(Path(folder) / 'preview.db')
    cid = repo.create_character('Optional tradition preview', 'Spheres')
    service = OptionalTraditionService(repo, cid)
    service.add('crafting:city-construction')
    service.add('tinker:clockwork', 'Dominant tradition; Craft (clockwork)')
    window = MainWindow(repo)
    window.resize(1500, 950)
    window.refresh_characters(cid)
    window.show()
    sheet = window.refined_sheet
    codex = CodexDialog(parent=window)
    for theme in ('classic', 'light', 'dark'):
        window._set_theme(theme)
        sheet.session.select_tab('inventory')
        settle(app)
        section = sheet.optional_traditions_section
        assert section.table.rowCount() == 2
        assert section.isVisible()
        section.grab().save(str(output / (theme + '-section.png')))
        picker = OptionalTraditionDialog('Tinker', parent=window)
        picker.setStyleSheet(dialog_stylesheet(theme))
        picker.show()
        picker.search.setText('Planar Attuned')
        picker.list.setCurrentRow(0)
        settle(app)
        assert 'Elemental Plane' in picker.details.toPlainText()
        picker.grab().save(str(output / (theme + '-picker.png')))
        picker.close()
        print(theme, 'section and picker OK', flush=True)
    other = repo.create_character('No optional traditions', 'Spheres')
    window.refresh_characters(other)
    settle(app)
    assert sheet.optional_traditions_section.table.rowCount() == 0
    codex.close()
    window.close()
    app.processEvents()
    repo.close()
