"""Render representative original Pathfinder classes for visual regression review."""
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
from app.models import ClassFeatureState
from app.ui.main_window import MainWindow


CASES = (
    ("paladin", "Paladin", "pathfinder-class:paladin", 10, "charisma", 18),
    ("hunter", "Hunter", "pathfinder-class:hunter", 8, "wisdom", 18),
    ("psychic", "Psychic", "pathfinder-class:psychic", 7, "wisdom", 18),
)


def main() -> None:
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        repository = CharacterRepository(Path(directory) / "preview.db")
        ids: dict[str, int] = {}
        for slug, name, preset, level, ability, score in CASES:
            character_id = repository.create_character(f"{name} Visual Check", "Pathfinder 1e")
            repository.update_ability_score(character_id, ability, score)
            class_id = repository.add_class_level(
                character_id, name, level, "3/4", "Good", "Good", "Good",
                preset_key=preset, hit_die=8, hp_gained=level * 6,
            )
            ids[slug] = character_id
            if slug == "paladin":
                repository.save_class_feature_state(
                    ClassFeatureState(character_id, class_id, "smite", 4, active=True)
                )
            elif slug == "hunter":
                repository.save_class_feature_state(
                    ClassFeatureState(
                        character_id, class_id, "animal_focus", level,
                        active=True, choices_json='["Bull"]',
                    )
                )

        window = MainWindow(repository)
        window.resize(1440, 920)
        window.refresh_characters(ids["paladin"])
        window.show()
        app.processEvents()
        scrolls = (
            window.sheet.builder_scroll,
            window.sheet.core_scroll,
            window.sheet.inventory_scroll,
            window.sheet.magic_scroll,
        )
        for theme in ("classic", "light", "dark"):
            window._set_theme(theme)
            for slug, *_unused in CASES:
                window._select_character(ids[slug])
                for page in range(4):
                    window.sheet.page_tabs.setCurrentIndex(page)
                    scrolls[page].verticalScrollBar().setValue(0)
                    app.processEvents()
                    window.grab().save(str(output / f"{theme}-{slug}-page-{page}.png"))
                    scrolls[page].verticalScrollBar().setValue(
                        scrolls[page].verticalScrollBar().maximum()
                    )
                    app.processEvents()
                    window.grab().save(
                        str(output / f"{theme}-{slug}-page-{page}-bottom.png")
                    )
        window.close()
        repository.close()


if __name__ == "__main__":
    main()
