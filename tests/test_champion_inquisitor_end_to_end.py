from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from app.class_feature_rules import archetype_optional_features
from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.content import archetype_entry
from app.database import CharacterRepository
from app.models import ClassFeatureSelection
from app.spellbook import SpellBookService
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.dialogs import ClassLevelDialog


CHAMPION_INQUISITOR = (
    "spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor"
)


class ChampionInquisitorEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary_directory.name) / "champion-inquisitor.db"
        )
        self.character_id = self.repository.create_character("Champion", "Spheres")
        self.class_level_id = self.repository.add_class_level(
            self.character_id,
            "Inquisitor",
            5,
            "3/4",
            "Good",
            "Poor",
            "Good",
            preset_key="pathfinder-class:inquisitor",
            hit_die=8,
            hp_gained=32,
        )
        self.repository.set_class_archetype_keys(
            self.character_id, self.class_level_id, (CHAMPION_INQUISITOR,)
        )
        self.archetype = archetype_entry(CHAMPION_INQUISITOR)
        self.option = archetype_optional_features(self.archetype)[0]
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    def _special_ability_names(self) -> set[str]:
        return {
            self.sheet.special_ability_table.item(row, 1).text()
            for row in range(self.sheet.special_ability_table.rowCount())
        }

    def _advancement_automatic(self) -> dict[str, str]:
        return {
            self.sheet.advancement_table.item(row, 0).text():
            self.sheet.advancement_table.item(row, 1).text()
            for row in range(self.sheet.advancement_table.rowCount())
        }

    def test_champion_replaces_spells_and_projects_base_sphere_training(self) -> None:
        names = self._special_ability_names()
        self.assertTrue(
            {"Casting", "Spell Pool", "Blended Training", "Proficiencies"}
            <= names
        )
        self.assertTrue({"Domain (INQ)", "Judgment", "Monster Lore", "Stern Gaze"} <= names)
        self.assertTrue(
            {"Inquisitor Spells", "Orisons", "Exchange Spell (Medium)"}.isdisjoint(names)
        )
        self.assertNotIn("Greater Training", names)

        capabilities = self.sheet._class_capabilities
        self.assertTrue(capabilities.magic)
        self.assertTrue(capabilities.martial)
        self.assertFalse(capabilities.traditional_spells)
        self.assertFalse(bool(self.sheet.spells_known_section.property("ruleAvailable")))

        budgets = self._advancement_automatic()
        self.assertEqual("5", budgets["Sphere talents"])
        self.assertNotIn("Spells known / recorded", budgets)

    def test_removed_spellcasting_keeps_saved_records_out_of_spellbook(self) -> None:
        spell_id = self.repository.add_spell(
            self.character_id,
            "Detect Alignment",
            system="Prepared",
            level=1,
            school_or_sphere="Divination",
        )
        self.repository.add_prepared_spell(
            self.character_id,
            self.class_level_id,
            spell_id,
            prepared_count=1,
        )

        service = SpellBookService(self.repository, self.character_id)
        self.assertEqual((), service.traditional_entries())
        self.assertIsNone(service.traditional_level_ceiling())
        self.assertFalse(
            service.cast_traditional(f"traditional:spell:{spell_id}").changed
        )
        # Archetype changes are presentation/rules gates, never destructive
        # migrations of a character's previously recorded spells.
        self.assertEqual(1, len(self.repository.list_spells(self.character_id)))
        self.assertEqual(
            1, len(self.repository.list_prepared_spells(self.character_id))
        )

    def test_domain_keeps_powers_but_does_not_restore_champion_spellcasting(self) -> None:
        slot = next(
            item for item in resolve_class_choice_slots(
                self.repository, self.character_id
            )
            if item.key == "inquisitor-domain"
        )
        fire = next(option for option in slot.options if option.name == "Fire Domain")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character_id, slot, (fire.key,))
        )
        self.sheet.refresh_all()

        names = self._special_ability_names()
        self.assertIn("Fire Domain", names)
        self.assertIn("Fire Bolt", names)
        self.assertNotIn("Burning Hands", names)
        self.assertFalse(self.sheet._class_capabilities.traditional_spells)
        self.assertFalse(bool(self.sheet.spells_known_section.property("ruleAvailable")))
        self.assertEqual((), SpellBookService(
            self.repository, self.character_id
        ).traditional_entries())

    def test_legacy_greater_training_choice_projects_and_migrates_in_edit_flow(self) -> None:
        self.repository.save_class_feature_selection(
            ClassFeatureSelection(
                self.character_id,
                self.class_level_id,
                self.option.key,
                "Optional Exchange",
                "enabled",
                self.option.name,
                self.option.description,
            )
        )
        self.sheet.refresh_all()

        names = self._special_ability_names()
        self.assertIn("Greater Training", names)
        self.assertNotIn("Monster Lore", names)
        self.assertNotIn("Stern Gaze", names)
        self.assertNotIn("Optional Exchange — Greater Training", names)
        self.assertEqual("7", self._advancement_automatic()["Sphere talents"])

        captured = {}
        class_level = self.repository.list_class_levels(self.character_id)[0]

        edit_dialog = ClassLevelDialog(
            class_level=class_level,
            selected_archetype_keys=(CHAMPION_INQUISITOR,),
            selected_optional_feature_keys=(self.option.key,),
        )
        try:
            self.assertEqual("inquisitor", edit_dialog.preset.currentData())
            self.assertEqual((CHAMPION_INQUISITOR,), edit_dialog.archetype_keys)
            self.assertTrue(
                edit_dialog.optional_exchange_checkboxes[self.option.key].isChecked()
            )
        finally:
            edit_dialog.close()

        class AcceptedEditDialog:
            values = {
                "class_name": class_level.class_name,
                "level": class_level.level,
                "bab_progression": class_level.bab_progression,
                "fort_progression": class_level.fort_progression,
                "reflex_progression": class_level.reflex_progression,
                "will_progression": class_level.will_progression,
                "preset_key": class_level.preset_key,
                "hit_die": class_level.hit_die,
                "hp_gained": class_level.hp_gained,
            }
            archetype_keys = (CHAMPION_INQUISITOR,)
            selected_optional_feature_keys = (self.option.key,)

            def __init__(dialog_self, *args):
                captured["selected_optional"] = args[4]

            def exec(dialog_self):
                return QDialog.DialogCode.Accepted

        with patch("app.ui.character_sheet.ClassLevelDialog", AcceptedEditDialog):
            self.sheet._edit_class_with_dialog(class_level, False)

        self.assertEqual((self.option.key,), captured["selected_optional"])
        saved = self.repository.list_class_feature_selections(self.character_id)
        self.assertEqual(1, len(saved))
        self.assertEqual("Archetype exchange", saved[0].option_type)
        self.assertEqual(self.option.key, saved[0].feature_key)


if __name__ == "__main__":
    unittest.main()
