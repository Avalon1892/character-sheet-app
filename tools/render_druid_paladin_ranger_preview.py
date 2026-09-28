"""Render representative Druid, Paladin, and Ranger families in every theme."""
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
        "druid", "Druid", "pathfinder-class:druid", 10,
        "wisdom", 20, 8, "3/4", "Good", "Poor", "Good",
        "spheres-archetype:pathfinder-class:druid:avatar",
    ),
    (
        "paladin", "Paladin", "pathfinder-class:paladin", 11,
        "charisma", 20, 10, "Full", "Good", "Poor", "Good",
        "pathfinder-archetype:pathfinder-class:paladin:holy-gun",
    ),
    (
        "ranger", "Ranger", "pathfinder-class:ranger", 9,
        "wisdom", 18, 10, "Full", "Good", "Good", "Poor",
        "spheres-archetype:pathfinder-class:ranger:sphere-ranger",
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
            fortitude, reflex, will, archetype,
        ) in CASES:
            character_id = repository.create_character(
                f"{name} Archetype Preview", "Pathfinder 1e"
            )
            repository.update_ability_score(character_id, ability, score)
            class_id = repository.add_class_level(
                character_id, name, level, bab, fortitude, reflex, will,
                preset_key=preset, hit_die=hit_die, hp_gained=level * 6,
            )
            repository.set_class_archetype_keys(
                character_id, class_id, (archetype,)
            )
            characters[slug] = character_id

        window = MainWindow(repository)
        window.resize(1440, 920)
        window.refresh_characters(characters["druid"])
        window.show()
        application.processEvents()
        scrolls = (
            window.sheet.builder_scroll,
            window.sheet.core_scroll,
            window.sheet.inventory_scroll,
            window.sheet.magic_scroll,
        )
        for theme in ("classic", "dark"):
            window._set_theme(theme)
            for slug, character_id in characters.items():
                window._select_character(character_id)
                for page in range(4):
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
