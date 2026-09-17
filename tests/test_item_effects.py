import json
import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.item_effects import (
    automation_for_entry,
    automation_json,
    item_modifiers,
    validate_item_choices,
)
from app.models import EquipmentItem, StatModifier
from app.rules import calculate_ability, calculate_attack, calculate_combat_statistics, calculate_stat
from app.services.character_calculations import CharacterCalculationService


def catalog_item(name: str, state: str = "worn", **values) -> EquipmentItem:
    automation = automation_for_entry({"name": name, "item_type": "equipment"})
    return EquipmentItem(
        id=values.pop("id", 1), name=name, category=values.pop("category", "Gear"),
        quantity=values.pop("quantity", 1), weight=0, equipped=state != "stored",
        ac_bonus=values.pop("ac_bonus", 0), bonus_type=values.pop("bonus_type", "untyped"),
        max_dex_bonus=values.pop("max_dex_bonus", None), state=state,
        automation_json=automation_json(automation), **values,
    )


class ItemEffectProviderTests(unittest.TestCase):
    def test_pre_automation_catalog_item_uses_legacy_family_fallback(self) -> None:
        legacy = EquipmentItem(
            1, "Headband of Inspired Wisdom +6", "Gear", 1, 1, True,
            0, "untyped", None, slot="Headband", catalog_key="legacy-key",
            state="worn", automation_json="",
        )
        result = calculate_ability(10, item_modifiers([legacy])["wisdom"])
        self.assertEqual(16, result.total)

    def test_headband_applies_immediately_only_while_worn(self) -> None:
        worn = catalog_item("Headband of Inspired Wisdom +6")
        stored = catalog_item("Headband of Inspired Wisdom +6", "stored")
        worn_result = calculate_ability(10, item_modifiers([worn])["wisdom"])
        stored_result = calculate_ability(10, item_modifiers([stored])["wisdom"])
        self.assertEqual(16, worn_result.total)
        self.assertEqual(10, stored_result.total)
        self.assertIn("currently stored", stored_result.contributions[-1].reason)

    def test_cloak_and_multi_ability_items_create_independent_effects(self) -> None:
        cloak = item_modifiers([catalog_item("Cloak of Resistance +3")])
        self.assertEqual({"fortitude", "reflex", "will"}, set(cloak))
        belt = item_modifiers([catalog_item("Belt of Physical Perfection +4")])
        self.assertEqual({"strength", "dexterity", "constitution"}, set(belt))

    def test_pathfinder_typed_stacking_suppresses_lower_item_bonus(self) -> None:
        items = [
            catalog_item("Headband of Inspired Wisdom +2", id=1),
            catalog_item("Headband of Inspired Wisdom +6", id=2),
        ]
        result = calculate_ability(10, item_modifiers(items)["wisdom"])
        self.assertEqual(16, result.total)
        self.assertIn("Does not stack", result.contributions[1].reason)

    def test_skill_speed_and_partial_reviewed_providers(self) -> None:
        boots = catalog_item("Boots of Striding")
        speed = calculate_stat([], item_modifiers([boots])["land_speed"])
        self.assertEqual(10, speed.total)
        ring = catalog_item("Ring of Swimming (Improved)")
        self.assertEqual(10, item_modifiers([ring])["skill:swim"][0].value)
        horseshoe = automation_for_entry({"name": "Lucky Horseshoe"})
        self.assertEqual("partial", horseshoe.status)
        self.assertTrue(horseshoe.rules_only)

    def test_choice_schema_rejects_unknown_or_missing_values(self) -> None:
        automation = automation_for_entry({"name": "Headband of Vast Intelligence +4"})
        self.assertEqual("choice", automation.status)
        with self.assertRaises(ValueError):
            validate_item_choices(automation, {})
        with self.assertRaises(ValueError):
            validate_item_choices(automation, {"trained_skill": "not-a-skill"})
        self.assertEqual(
            {"trained_skill": "knowledge_arcana"},
            validate_item_choices(automation, {"trained_skill": "knowledge_arcana"}),
        )

    def test_armor_enhancement_is_part_of_armor_component(self) -> None:
        abilities = {
            key: calculate_ability(10, [])
            for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
        }
        armor = catalog_item(
            "Magic chain shirt", state="armor", category="Armor", ac_bonus=4,
            bonus_type="armor", enhancement_bonus=2,
        )
        bracers = catalog_item("Bracers of Armor +4", id=2)
        modifiers = item_modifiers([armor, bracers])
        result = calculate_combat_statistics("Medium", [], abilities, modifiers, [armor, bracers])
        self.assertEqual(16, result["ac"].total)
        self.assertEqual(10, result["touch_ac"].total)

    def test_amulet_enhances_natural_armor_without_affecting_touch_ac(self) -> None:
        abilities = {
            key: calculate_ability(10, [])
            for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
        }
        modifiers = item_modifiers([catalog_item("Amulet of Natural Armor +2")])
        modifiers["ac"].append(
            StatModifier(None, "ac", "Creature natural armor", "natural armor", 3)
        )
        result = calculate_combat_statistics("Medium", [], abilities, modifiers)
        self.assertEqual(15, result["ac"].total)
        self.assertEqual(10, result["touch_ac"].total)


class ItemPersistenceAndWeaponTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "items.db")
        self.character_id = self.repository.create_character("Items", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_choices_and_state_persist_and_validate(self) -> None:
        automation = automation_for_entry({"name": "Headband of Vast Intelligence +4"})
        item_id = self.repository.add_equipment(
            self.character_id, "Headband of Vast Intelligence +4", "Gear", 1, 1,
            True, 0, "untyped", None, "", slot="Headband", state="worn",
            choices_json=json.dumps({"trained_skill": "spellcraft"}),
            automation_json=automation_json(automation),
        )
        item = self.repository.list_equipment(self.character_id)[0]
        self.assertEqual("worn", item.state)
        self.assertEqual("spellcraft", json.loads(item.choices_json)["trained_skill"])
        with self.assertRaises(ValueError):
            self.repository.set_equipment_choices(
                self.character_id, item_id, json.dumps({"trained_skill": "invalid"})
            )

    def test_linked_weapon_applies_only_to_its_attack_and_unlinks_on_delete(self) -> None:
        weapon_id = self.repository.add_equipment(
            self.character_id, "+2 longsword", "Weapon", 1, 4, True, 0,
            "untyped", None, "", state="wielded", enhancement_bonus=2,
            masterwork=True, weapon_damage_dice="1d8", weapon_damage_type="slashing",
            weapon_critical="19-20/x2", weapon_range="Melee",
        )
        attack_id = self.repository.add_attack(
            self.character_id, "Longsword", "Melee", "strength", 0, "1d6",
            "strength", 1.0, 0, "20/x2", "", equipment_id=weapon_id,
        )
        attack = self.repository.list_attacks(self.character_id)[0]
        service = CharacterCalculationService(self.repository, self.character_id)
        attack_modifiers, damage_modifiers = service.attack_effects(attack, 0)
        result = calculate_attack(
            attack, 0, service.ability_results(), "Medium",
            attack_modifiers, damage_modifiers,
        )
        self.assertEqual(2, result.attack_bonus)
        self.assertEqual(2, result.damage_bonus)
        self.repository.set_equipment_state(self.character_id, weapon_id, "stored")
        inactive_service = CharacterCalculationService(self.repository, self.character_id)
        self.assertEqual(([], []), inactive_service.attack_effects(attack, 0))
        self.repository.delete_equipment(self.character_id, weapon_id)
        self.assertIsNone(self.repository.list_attacks(self.character_id)[0].equipment_id)
        self.repository.delete_attack(self.character_id, attack_id)


if __name__ == "__main__":
    unittest.main()
