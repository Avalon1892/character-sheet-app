from __future__ import annotations

import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.catalogs import DEFAULT_CATALOG
from app.database import CharacterRepository
from app.item_enchantments import available_enchantments, weapon_attack_type
from app.models import EquipmentItem
from app.rules import calculate_attack, roll_attack_and_damage
from app.services.character_calculations import CharacterCalculationService
from app.ui.dialogs import AttackDialog


LONGSWORD_KEY = "pathfinder:weapons-and-ammo:zWRlna42PMJVX6un"


class WeaponEnchantmentEffectsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "test.db")
        self.character_id = self.repository.create_character("Magic Sword", "Pathfinder 1e")
        self.weapon_id = self.repository.add_equipment(
            self.character_id, "Longsword", "Weapon", 1, 4, True, 0,
            "untyped", None, "", state="wielded", catalog_key=LONGSWORD_KEY,
            enhancement_bonus=0, masterwork=False, weapon_damage_dice="1d8",
            weapon_damage_type="slashing", weapon_critical="19-20/x2",
            weapon_range="0",
        )
        self.attack_id = self.repository.add_attack(
            self.character_id, "Longsword", "Melee", "strength", 0, "1d8",
            "strength", 1.0, 0, "19-20/x2", "", self.weapon_id, "", "automatic",
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _add(self, name: str) -> None:
        spec = next(
            value for value in DEFAULT_CATALOG.enchantment_entries("Weapon")
            if value["name"] == name
        )
        self.repository.add_item_enchantment(
            self.character_id, self.weapon_id, spec["key"], spec["name"],
            int(spec["bonus_equivalent"]), str(spec["description"]),
        )

    def test_first_property_automatically_makes_weapon_plus_one_masterwork(self) -> None:
        self._add("Keen")
        weapon = self.repository.list_equipment(self.character_id)[0]
        self.assertEqual(1, weapon.enhancement_bonus)
        self.assertTrue(weapon.masterwork)

    def test_keen_elemental_and_impact_properties_resolve_live_attack_stats(self) -> None:
        for name in ("Keen", "Flaming", "Impact"):
            self._add(name)
        service = CharacterCalculationService(self.repository, self.character_id)
        attack = self.repository.list_attacks(self.character_id)[0]
        profile = service.resolve_attack_profile(attack)
        self.assertEqual("17-20/x2", profile.attack.critical)
        self.assertEqual("2d6", profile.attack.damage_dice)
        self.assertEqual(("1d6", "fire"), (profile.extra_damage[0].dice, profile.extra_damage[0].damage_type))
        attack_modifiers, damage_modifiers = service.attack_effects(attack, 0)
        result = calculate_attack(
            profile.attack, 0, service.ability_results(), "Medium",
            attack_modifiers, damage_modifiers, extra_damage=profile.extra_damage,
        )
        self.assertEqual("2d6+1 + 1d6 fire", result.damage_display)
        _natural, _attack_total, damage_total, rolls = roll_attack_and_damage(
            result, profile.attack.damage_dice, random.Random(7)
        )
        self.assertEqual(3, len(rolls))
        self.assertEqual(sum(rolls) + 1, damage_total)

    def test_old_zero_range_melee_record_stays_melee_and_accepts_keen(self) -> None:
        weapon = self.repository.list_equipment(self.character_id)[0]
        self.assertEqual("Melee", weapon_attack_type(weapon))
        self.assertIn("Keen", {spec.name for spec in available_enchantments(weapon)})


class LinkedWeaponTypeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_linking_old_zero_range_longsword_does_not_switch_to_ranged(self) -> None:
        weapon = EquipmentItem(
            1, "Longsword", "Weapon", 1, 4, True, 0, "untyped", None,
            catalog_key=LONGSWORD_KEY, state="wielded", weapon_damage_dice="1d8",
            weapon_damage_type="slashing", weapon_critical="19-20/x2", weapon_range="0",
        )
        dialog = AttackDialog(equipment=[weapon])
        try:
            dialog.linked_weapon.setCurrentIndex(dialog.linked_weapon.findData(1))
            self.assertEqual("Melee", dialog.attack_type.currentText())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
