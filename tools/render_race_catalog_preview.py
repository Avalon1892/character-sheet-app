"""Render the race chooser in each bundled theme for visual verification."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.models import CharacterDetails, RaceTraitChoice
from app.ui.race_dialog import RaceCatalogDialog
from app.ui.theme import style_sheet


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "_visual-checks/races")
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    trait_key = "race-alt-trait:human:dual-talent"
    details = CharacterDetails(
        1, race="Human", race_key="human",
        race_alternate_trait_keys=(trait_key,),
        race_trait_choices=(RaceTraitChoice(
            trait_key, "ability_scores", ("strength", "dexterity")
        ),),
    )
    variant_key = "race-alt-trait:tiefling:variant-tiefling-abilities"
    previews = (
        ("dual-talent", details),
        ("variant-ability", CharacterDetails(
            2, race="Tiefling", race_key="tiefling",
            race_alternate_trait_keys=(variant_key,),
            race_trait_choices=(RaceTraitChoice(
                variant_key, "variant_abilities", ("10",)
            ),),
        )),
    )
    for label, preview_details in previews:
        dialog = RaceCatalogDialog(preview_details)
        for theme in ("classic", "dark"):
            dialog.setStyleSheet(style_sheet(theme))
            dialog.show()
            application.processEvents()
            if not dialog.grab().save(str(output / f"race-catalog-{label}-{theme}.png")):
                raise RuntimeError(f"Could not render {theme} race catalog preview")
        dialog.close()


if __name__ == "__main__":
    main()
