"""Render representative guided-creator pages for theme regression review."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.ui.character_creation_dialog import GuidedCharacterCreationDialog
from app.ui.theme import style_sheet


def main() -> int:
    application = QApplication.instance() or QApplication([])
    output = Path(__file__).resolve().parents[1] / "artifacts" / "character_creator_preview"
    output.mkdir(parents=True, exist_ok=True)
    for theme in ("classic", "light", "dark"):
        application.setStyleSheet(style_sheet(theme))
        dialog = GuidedCharacterCreationDialog()
        dialog.name.setText("Mira Dawnstep")
        dialog.player_name.setText("Player")
        dialog.race.setText("Human")
        dialog._race_selection = {
            "race_key": "human", "race_name": "Human", "size": "Medium",
            "ability_choice": "dexterity", "variant_key": "",
            "alternate_trait_keys": (), "trait_choices": (),
        }
        dialog._rebuild_race_distribution()
        dialog._refresh_racial_adjustments()
        dialog.resize(1120, 760)
        dialog.show()
        for page in (0, 1, 3, 4):
            dialog.pages.setCurrentIndex(page)
            application.processEvents()
            dialog.grab().save(str(output / f"{theme}-page-{page + 1}.png"))
        dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
