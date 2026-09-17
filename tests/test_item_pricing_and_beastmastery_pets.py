from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.animal_companion_rules import resolve_companion_grant
from app.bonded_companion_rules import (
    beastmastery_pet_progression,
    bonded_companion_grants,
)
from app.database import CharacterRepository
from app.item_enchantments import item_price_breakdown
from app.models import (
    BondedCompanion,
    ClassLevel,
    EquipmentItem,
    ItemEnchantment,
    MartialTalent,
    SkillState,
)
from app.talent_automation import martial_automation


def equipment(**overrides) -> EquipmentItem:
    values = dict(
        id=1,
        name="Longsword",
        category="Weapon",
        quantity=1,
        weight=4.0,
        equipped=False,
        ac_bonus=0,
        bonus_type="untyped",
        max_dex_bonus=None,
        value_gp=15.0,
    )
    values.update(overrides)
    return EquipmentItem(**values)


class DerivedItemPriceTests(unittest.TestCase):
    def test_masterwork_and_modified_bonus_update_weapon_price(self) -> None:
        mundane = equipment()
        self.assertEqual(15, item_price_breakdown(mundane).total_gp)
        self.assertEqual(
            315,
            item_price_breakdown(equipment(masterwork=True)).total_gp,
        )
        magic = equipment(enhancement_bonus=1, masterwork=True)
        self.assertEqual(2315, item_price_breakdown(magic).total_gp)
        keen = ItemEnchantment(
            1,
            magic.id,
            "pathfinder:enchantment:weapon:melee:keen",
            "Keen",
            1,
        )
        price = item_price_breakdown(magic, (keen,))
        self.assertEqual(2, price.modified_bonus)
        self.assertEqual(8315, price.total_gp)

    def test_armor_and_imported_amulet_use_their_own_progressions(self) -> None:
        armor = equipment(
            name="Full Plate",
            category="Armor",
            value_gp=1500,
            masterwork=True,
            enhancement_bonus=1,
        )
        self.assertEqual(2650, item_price_breakdown(armor).total_gp)
        amulet = equipment(
            name="Amulet of Mighty Fists +1",
            category="Gear",
            value_gp=4000,
            enhancement_bonus=1,
        )
        self.assertEqual(4000, item_price_breakdown(amulet).total_gp)
        self.assertEqual(
            16000,
            item_price_breakdown(
                equipment(
                    name="Amulet of Mighty Fists +1",
                    category="Gear",
                    value_gp=4000,
                    enhancement_bonus=2,
                )
            ).total_gp,
        )


class BeastmasteryCompanionTests(unittest.TestCase):
    def test_animal_companion_talent_stacks_and_is_limited_to_two_copies(self) -> None:
        classes = (
            ClassLevel(1, "Druid", 4, "3/4", "Good", "Poor", "Good"),
            ClassLevel(2, "Fighter", 4, "Full", "Good", "Poor", "Poor"),
        )
        companion_feature = SimpleNamespace(
            name="Animal Companion",
            description="The druid forms a bond with an animal companion.",
        )
        talent = MartialTalent(
            1,
            "Animal Companion",
            "Beastmastery",
            catalog_key="beastmastery:talent:animal-companion",
        )
        grant = resolve_companion_grant(
            classes,
            {1: (companion_feature,)},
            (talent,),
            {
                "handle_animal": SkillState("handle_animal"),
                "ride": SkillState("ride"),
            },
        )
        self.assertEqual(8, grant.effective_level)
        automation = martial_automation("Animal Companion")
        self.assertTrue(automation["repeatable"])
        self.assertEqual(2, automation["repeat_limit"])

    def test_beastmastery_pet_grants_filtered_familiar_and_optional_stacking(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = CharacterRepository(Path(folder) / "characters.db")
            try:
                character = repository.create_character("Handler", "Spheres")
                repository.add_class_level(
                    character,
                    "Witch",
                    3,
                    "1/2",
                    "Poor",
                    "Poor",
                    "Good",
                    "pathfinder-class:witch",
                    6,
                    18,
                )
                repository.add_class_level(
                    character,
                    "Fighter",
                    3,
                    "Full",
                    "Good",
                    "Poor",
                    "Poor",
                    "pathfinder-class:fighter",
                    10,
                    30,
                )
                repository.add_martial_talent(
                    character,
                    "Pet",
                    "Beastmastery",
                    "Talent",
                    catalog_key="beastmastery:talent:pet",
                    catalog_category="Talent",
                )
                grant = bonded_companion_grants(repository, character)["familiar"]
                self.assertEqual(3, grant.level)
                self.assertTrue(grant.can_stack_pet)
                self.assertFalse(grant.stacks_pet)

                current = repository.get_bonded_companion(character, "familiar")
                repository.update_bonded_companion(
                    BondedCompanion(
                        current.character_id,
                        current.companion_key,
                        current.name,
                        current.species,
                        current.current_hp,
                        current.temporary_hp,
                        json.dumps({"beastmastery_pet_stack": True}),
                        current.notes,
                    )
                )
                stacked = bonded_companion_grants(repository, character)["familiar"]
                self.assertEqual(6, stacked.level)
                self.assertTrue(stacked.stacks_pet)

                pet = beastmastery_pet_progression(13)
                self.assertIsNone(pet.intelligence)
                for removed in (
                    "Deliver Touch Spells",
                    "Scry on Familiar",
                    "Share Spells",
                    "Speak with Animals of Its Kind",
                    "Spell Resistance",
                ):
                    self.assertNotIn(removed, pet.specials)
                self.assertIn("Speak with Master", pet.specials)
            finally:
                repository.close()


if __name__ == "__main__":
    unittest.main()
