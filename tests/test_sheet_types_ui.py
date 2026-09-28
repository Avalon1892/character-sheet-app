import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from app.ui.sheet_types import SHEET_TYPE_REGISTRY, normalize_sheet_type
from app.ui.theme import THEME_LABELS, normalize_theme


def test_only_refined_and_two_themes_remain():
    assert set(SHEET_TYPE_REGISTRY) == {"refined"}
    assert set(THEME_LABELS) == {"classic", "dark"}
    for old in ("customizable", "original_spheres", "ultra", "unknown"):
        assert normalize_sheet_type(old) == "refined"
    assert normalize_theme("light") == "classic"


def test_saved_legacy_preferences_open_one_refined_sheet():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        QSettings("Georg", "Character Sheet App").setValue("appearance/theme", "light")
        repository = CharacterRepository(Path(directory) / "characters.db")
        window = MainWindow(repository)
        try:
            cid = repository.create_character("Existing character", "Spheres")
            window.style_store.save(cid, "selection", {"style": "original_spheres"})
            window.refresh_characters(cid)
            app.processEvents()
            assert window.sheet is window.refined_sheet
            assert window.sheet_stack.count() == 1
            assert window.theme == "classic"
            assert window.sheet.character_id == cid
            assert window.build_menu.isEnabled()
            assert "Sheet Types" not in [a.text().replace("&", "") for a in window.menuBar().actions()]
        finally:
            window.close()
            repository.close()
