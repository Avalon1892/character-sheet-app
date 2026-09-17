"""Render the talent browser, Weather drawbacks, and companion training UI."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.models import AnimalCompanion
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.dialogs import MagicTalentCatalogDialog, SphereAcquisitionDialog
from app.ui.theme import style_sheet


def main() -> None:
    output = Path(".codex-previews")
    output.mkdir(exist_ok=True)
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        repository = CharacterRepository(Path(directory) / "preview.db")
        character = repository.create_character("Companion Preview", "Spheres")
        class_id = repository.add_class_level(
            character, "Inquisitor", 4, "3/4", "Good", "Poor", "Good",
            "pathfinder-class:inquisitor", 8, 30,
        )
        repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:sacred-huntsmaster",),
        )
        repository.update_animal_companion(
            AnimalCompanion(character, name="Asha", species_key="cat-big-lion-tiger")
        )
        sheet = CharacterSheetWidget(repository)
        sheet.resize(1500, 940)
        sheet.load_character(character)
        sheet.show()
        application.processEvents()
        companion_index = sheet.page_tabs.indexOf(sheet.companion_scroll)
        sheet.page_tabs.setCurrentIndex(companion_index)
        for theme in ("classic", "light", "dark"):
            sheet.setStyleSheet(style_sheet(theme))
            application.processEvents()
            sheet.grab().save(str(output / f"animal-companion-training-{theme}.png"))

            talents = MagicTalentCatalogDialog([], sheet)
            talents.setStyleSheet(style_sheet(theme))
            talents.show()
            application.processEvents()
            talents.grab().save(str(output / f"magic-talent-browser-{theme}.png"))
            talents.close()

            drawbacks = SphereAcquisitionDialog(
                set(), sheet, fixed_sphere="Weather"
            )
            drawbacks.setStyleSheet(style_sheet(theme))
            drawbacks.show()
            application.processEvents()
            drawbacks.grab().save(str(output / f"weather-drawbacks-{theme}.png"))
            drawbacks.close()
        sheet.close()
        repository.close()


if __name__ == "__main__":
    main()
