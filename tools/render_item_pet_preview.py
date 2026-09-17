"""Render the item-price editor and Pet/Familiar page in every theme."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.models import BondedCompanion
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.dialogs import EquipmentDialog
from app.ui.theme import style_sheet


def main() -> None:
    root = Path(".codex-previews")
    root.mkdir(exist_ok=True)
    database = root / "item-pet-preview.db"
    database.unlink(missing_ok=True)
    repository = CharacterRepository(database)
    try:
        character = repository.create_character("Pet Preview", "Spheres")
        repository.add_class_level(
            character,
            "Fighter",
            6,
            "Full",
            "Good",
            "Poor",
            "Poor",
            "pathfinder-class:fighter",
            10,
            60,
        )
        repository.add_martial_talent(
            character,
            "Pet",
            "Beastmastery",
            "Talent",
            catalog_key="beastmastery:talent:pet",
            catalog_category="Talent",
        )
        repository.update_bonded_companion(
            BondedCompanion(
                character,
                "familiar",
                "Ember",
                "Fox, Firefoot Fennec",
                0,
                0,
                '{"familiar_key": "fox-firefoot-fennec"}',
                "Alert desert scout.",
            )
        )
        item_id = repository.add_equipment(
            character,
            "Longsword",
            "Weapon",
            1,
            4,
            False,
            0,
            "untyped",
            None,
            "",
            value_gp=15,
            enhancement_bonus=2,
            masterwork=True,
        )
        application = QApplication.instance() or QApplication([])
        sheet = CharacterSheetWidget(repository)
        sheet.resize(1500, 940)
        sheet.load_character(character)
        sheet.show()
        application.processEvents()
        pet_index = next(
            index
            for index in range(sheet.page_tabs.count())
            if "PET / FAMILIAR" in sheet.page_tabs.tabText(index)
        )
        sheet.page_tabs.setCurrentIndex(pet_index)
        application.processEvents()
        item = next(
            value for value in repository.list_equipment(character)
            if value.id == item_id
        )
        for theme in ("classic", "light", "dark"):
            sheet.setStyleSheet(style_sheet(theme))
            application.processEvents()
            sheet.grab().save(str(root / f"pet-familiar-{theme}.png"))
            dialog = EquipmentDialog(item=item)
            dialog.setStyleSheet(style_sheet(theme))
            dialog.resize(720, 760)
            dialog.show()
            application.processEvents()
            dialog.grab().save(str(root / f"item-price-{theme}.png"))
            dialog.close()
        skills = sheet.skills_section
        skills.setParent(None)
        skills.setProperty("freeformManaged", True)
        skills.resize(820, 760)
        sheet._refresh_skills()
        skills.show()
        for theme in ("classic", "light", "dark"):
            skills.setStyleSheet(style_sheet(theme))
            application.processEvents()
            skills.grab().save(str(root / f"skills-resized-{theme}.png"))
        skills.close()
        sheet.close()
    finally:
        repository.close()


if __name__ == "__main__":
    main()
