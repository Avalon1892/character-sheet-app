"""Render the reviewed Wizard, Cleric, and Monk families in every theme."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import CharacterRepository
from app.ui.main_window import MainWindow


CASES = (
    (
        "wizard", "Wizard", "pathfinder-class:wizard", 9,
        "intelligence", 18, 6, "1/2", "Poor", "Poor", "Good",
        "pathfinder-archetype:pathfinder-class:wizard:exploiter-wizard",
    ),
    (
        "cleric", "Cleric", "pathfinder-class:cleric", 7,
        "wisdom", 18, 8, "3/4", "Good", "Poor", "Good",
        "pathfinder-archetype:pathfinder-class:cleric:cloistered-cleric",
    ),
    (
        "monk", "Monk", "pathfinder-class:monk", 12,
        "charisma", 18, 8, "3/4", "Good", "Good", "Good",
        "pathfinder-archetype:pathfinder-class:monk:scaled-fist",
    ),
)


def main() -> None:
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory
        )
        repository = CharacterRepository(Path(directory) / "preview.db")
        characters: dict[str, int] = {}
        for (
            slug, name, preset, level, ability, score, hit_die, bab,
            fort, reflex, will, archetype,
        ) in CASES:
            character_id = repository.create_character(
                f"{name} Archetype Preview", "Pathfinder 1e"
            )
            repository.update_ability_score(character_id, ability, score)
            class_id = repository.add_class_level(
                character_id, name, level, bab, fort, reflex, will,
                preset_key=preset, hit_die=hit_die, hp_gained=level * 6,
            )
            repository.set_class_archetype_keys(
                character_id, class_id, (archetype,)
            )
            characters[slug] = character_id

        window = MainWindow(repository)
        window.resize(1440, 920)
        window.refresh_characters(characters["wizard"])
        window.show()
        application.processEvents()
        scrolls = (
            window.sheet.builder_scroll,
            window.sheet.core_scroll,
            window.sheet.inventory_scroll,
            window.sheet.magic_scroll,
        )
        for theme in ("classic", "light", "dark"):
            window._set_theme(theme)
            for slug in characters:
                window._select_character(characters[slug])
                for page in (0, 1, 3):
                    window.sheet.page_tabs.setCurrentIndex(page)
                    scrolls[page].verticalScrollBar().setValue(0)
                    application.processEvents()
                    window.grab().save(
                        str(output / f"{theme}-{slug}-page-{page}.png")
                    )
        window.close()
        repository.close()


if __name__ == "__main__":
    main()
