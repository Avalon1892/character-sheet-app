from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.attack_profiles import UNARMED_ATTACK_TEMPLATE
from app.catalogs import DEFAULT_CATALOG
from app.database import CharacterRepository
from app.item_enchantments import AGILE
from app.rules import calculate_attack
from app.services.character_calculations import CharacterCalculationService
from app.ui.dialogs import AttackDialog
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class UnarmedAndEnchantmentRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "rules.db")
        self.character_id = self.repository.create_character("Pugilist", "Spheres")
        self.attack_id = self.repository.add_attack(
            self.character_id,
            **UNARMED_ATTACK_TEMPLATE.values,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _add_talent(
        self, name: str, sphere: str, category: str = "Talent"
    ) -> int:
        return self.repository.add_martial_talent(
            self.character_id,
            name,
            sphere,
            "Base Sphere" if category == "Base Sphere" else category,
            catalog_key=f"test:{sphere}:{name}".casefold().replace(" ", "-"),
            catalog_category=category,
        )

    def _resolved(self):
        attack = self.repository.list_attacks(self.character_id)[0]
        return CharacterCalculationService(
            self.repository, self.character_id
        ).resolve_attack_profile(attack)

    def test_spheres_talent_total_and_drawback_exclusion_drive_unarmed_die(self) -> None:
        self.assertEqual("1d3", self._resolved().attack.damage_dice)
        self._add_talent("Open Hand Sphere", "Open Hand", "Base Sphere")
        self._add_talent("Boxing Sphere", "Boxing", "Base Sphere")
        self._add_talent("Snap Kick", "Open Hand")
        self.assertEqual("1d4", self._resolved().attack.damage_dice)
        self.assertEqual(3, self._resolved().unarmed.qualifying_talents)

        self._add_talent("Brute Sphere", "Brute", "Base Sphere")
        self.assertEqual("1d6", self._resolved().attack.damage_dice)
        self._add_talent("Armed Combatant", "Brute", "Drawback")
        result = self._resolved()
        self.assertEqual("1d4", result.attack.damage_dice)
        self.assertEqual(("brute",), result.unarmed.excluded_spheres)

    def test_virtual_talents_and_native_progression_follow_som_rule(self) -> None:
        self._add_talent("Open Hand Sphere", "Open Hand", "Base Sphere")
        self.repository.add_trait(self.character_id, "Talented Knuckle")
        result = self._resolved()
        self.assertEqual(3, result.unarmed.qualifying_talents)
        self.assertEqual("1d4", result.attack.damage_dice)

        self.repository.add_class_level(
            self.character_id,
            "Monk",
            5,
            "3/4",
            "Good",
            "Good",
            "Good",
            preset_key="pathfinder-class:monk",
            hit_die=8,
            hp_gained=30,
        )
        result = self._resolved()
        self.assertEqual("2d6", result.attack.damage_dice)
        self.assertIn("effective size", result.unarmed.source)

    def test_agile_amulet_is_an_automatic_default_with_manual_override(self) -> None:
        self.repository.update_ability_score(self.character_id, "dexterity", 18)
        self.repository.update_ability_score(self.character_id, "wisdom", 14)
        amulet_id = self.repository.add_equipment(
            self.character_id,
            "Amulet of Mighty Fists",
            "Gear",
            1,
            0,
            True,
            0,
            "untyped",
            None,
            "",
            slot="Neck",
            state="worn",
            catalog_key="reviewed:amulet-of-mighty-fists:customizable",
        )
        self.repository.add_item_enchantment(
            self.character_id,
            amulet_id,
            AGILE.key,
            AGILE.name,
            AGILE.bonus_equivalent,
            AGILE.description,
        )
        self.assertEqual("strength", self._resolved().attack.damage_ability)
        self.assertIn("requires Weapon Finesse", "\n".join(self._resolved().sources))

        self.repository.add_feat(self.character_id, "Weapon Finesse")
        resolved = self._resolved()
        self.assertEqual("dexterity", resolved.attack.damage_ability)
        service = CharacterCalculationService(self.repository, self.character_id)
        attack_modifiers, damage_modifiers = service.attack_effects(
            resolved.attack, 0
        )
        calculated = calculate_attack(
            resolved.attack,
            0,
            service.ability_results(),
            "Medium",
            attack_modifiers,
            damage_modifiers,
        )
        self.assertEqual("1d3+4", calculated.damage_display)

        original = self.repository.list_attacks(self.character_id)[0]
        self.repository.update_attack(
            self.character_id,
            original.id,
            original.name,
            original.attack_type,
            original.ability,
            original.attack_bonus,
            original.damage_dice,
            "wisdom",
            original.damage_multiplier,
            original.damage_bonus,
            original.critical,
            original.notes,
            original.equipment_id,
            original.profile_key,
            "manual",
        )
        self.assertEqual("wisdom", self._resolved().attack.damage_ability)

        manual = self.repository.list_attacks(self.character_id)[0]
        self.repository.update_attack(
            self.character_id,
            manual.id,
            manual.name,
            manual.attack_type,
            manual.ability,
            manual.attack_bonus,
            manual.damage_dice,
            "strength",
            manual.damage_multiplier,
            manual.damage_bonus,
            manual.critical,
            manual.notes,
            manual.equipment_id,
            manual.profile_key,
            "automatic",
        )
        self.repository.set_equipment_state(self.character_id, amulet_id, "stored")
        self.assertEqual("strength", self._resolved().attack.damage_ability)

    def test_mighty_fists_enhancement_applies_without_linking_the_attack(self) -> None:
        amulet_id = self.repository.add_equipment(
            self.character_id,
            "Amulet of Mighty Fists +2",
            "Gear",
            1,
            0,
            True,
            0,
            "untyped",
            None,
            "",
            slot="Neck",
            state="worn",
            enhancement_bonus=2,
        )
        attack = self.repository.list_attacks(self.character_id)[0]
        service = CharacterCalculationService(self.repository, self.character_id)
        attack_modifiers, damage_modifiers = service.attack_effects(attack, 0)
        self.assertEqual(2, attack_modifiers[-1].value)
        self.assertEqual(2, damage_modifiers[-1].value)
        self.repository.set_equipment_state(self.character_id, amulet_id, "stored")
        service = CharacterCalculationService(self.repository, self.character_id)
        self.assertEqual(([], []), service.attack_effects(attack, 0))

    def test_composable_amulet_is_available_in_the_item_catalog(self) -> None:
        entry = DEFAULT_CATALOG.item_entry(
            "reviewed:amulet-of-mighty-fists:customizable"
        )
        self.assertIsNotNone(entry)
        self.assertEqual("Amulet of Mighty Fists", entry["name"])


class UnarmedAttackDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_unarmed_template_uses_automatic_profile(self) -> None:
        dialog = AttackDialog()
        try:
            dialog.preset.setCurrentIndex(
                dialog.preset.findData("builtin:unarmed")
            )
            values = dialog.values
            self.assertEqual("Unarmed Strike", values["name"])
            self.assertEqual("unarmed", values["profile_key"])
            self.assertEqual("automatic", values["damage_ability_mode"])
        finally:
            dialog.close()

    def test_ranged_weapon_manual_damage_ability_restores_multiplier(self) -> None:
        dialog = AttackDialog()
        try:
            dagger_index = dialog.preset.findText("Dagger")
            self.assertGreaterEqual(dagger_index, 0)
            dialog.preset.setCurrentIndex(dagger_index)
            dialog.attack_type.setCurrentText("Ranged")
            self.assertIsNone(dialog.values["damage_ability"])
            self.assertEqual(0.0, dialog.values["damage_multiplier"])

            dialog.damage_ability.setCurrentIndex(
                dialog.damage_ability.findData("dexterity")
            )
            self.assertEqual("dexterity", dialog.values["damage_ability"])
            self.assertEqual("manual", dialog.values["damage_ability_mode"])
            self.assertEqual(1.0, dialog.values["damage_multiplier"])

            # A deliberate override made after the ability choice remains valid.
            dialog.damage_multiplier.setCurrentIndex(
                dialog.damage_multiplier.findData(0.0)
            )
            self.assertEqual(0.0, dialog.values["damage_multiplier"])
        finally:
            dialog.close()

    def test_sheet_displays_resolved_unarmed_damage_and_item_property(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = CharacterRepository(Path(directory) / "sheet.db")
            character_id = repository.create_character("Agile Pugilist", "Spheres")
            repository.update_ability_score(character_id, "dexterity", 18)
            for index, name in enumerate(
                ("Open Hand Sphere", "Snap Kick", "Iron Fist", "Axe Kick")
            ):
                repository.add_martial_talent(
                    character_id,
                    name,
                    "Open Hand",
                    "Base Sphere" if index == 0 else "Talent",
                    catalog_key=f"test:open-hand:{index}",
                    catalog_category="Base Sphere" if index == 0 else "Talent",
                )
            repository.add_feat(character_id, "Weapon Finesse")
            amulet_id = repository.add_equipment(
                character_id,
                "Amulet of Mighty Fists",
                "Gear",
                1,
                0,
                True,
                0,
                "untyped",
                None,
                "",
                slot="Neck",
                state="worn",
                catalog_key="reviewed:amulet-of-mighty-fists:customizable",
            )
            repository.add_item_enchantment(
                character_id,
                amulet_id,
                AGILE.key,
                AGILE.name,
                AGILE.bonus_equivalent,
                AGILE.description,
            )
            repository.add_attack(character_id, **UNARMED_ATTACK_TEMPLATE.values)
            sheet = CharacterSheetWidget(repository)
            try:
                sheet.load_character(character_id)
                self.assertEqual("1d6+4", sheet.attack_table.item(0, 3).text())
                self.assertIn("[Agile]", sheet.equipment_table.item(0, 0).text())
                self.assertIn("Dexterity to damage", sheet.attack_table.item(0, 0).toolTip())
            finally:
                sheet.close()
                repository.close()


if __name__ == "__main__":
    unittest.main()
