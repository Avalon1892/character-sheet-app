from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG
from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import build_audit
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.services.advancement import character_advancement_budgets


class DruidPaladinRangerPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "druid-paladin-ranger.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(self, key: str, level: int) -> tuple[int, int]:
        definition = class_entry(key)
        character = self.repository.create_character(
            str(definition["name"]), "Pathfinder 1e"
        )
        class_id = self.repository.add_class_level(
            character,
            str(definition["name"]),
            level,
            str(definition["bab"]),
            str(definition["fort"]),
            str(definition["reflex"]),
            str(definition["will"]),
            key,
            int(definition["hit_die"]),
            max(int(definition["hit_die"]), level * 5),
        )
        return character, class_id

    def test_packages_and_every_imported_archetype_pass_the_coverage_audit(self) -> None:
        for family in ("druid", "paladin", "ranger"):
            self.assertEqual(family, class_package(f"pathfinder-class:{family}").key)
        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        for family, count in (("Druid", 79), ("Paladin", 59), ("Ranger", 72)):
            rows = [row for row in audit["archetypes"] if row["class_name"] == family]
            self.assertEqual(count, len(rows))
            self.assertFalse(
                [row["name"] for row in rows if row["status"] != "fully_automated"]
            )

    def test_reviewed_spheres_profiles_replace_traditional_casting_and_budget_talents(self) -> None:
        cases = (
            (
                "pathfinder-class:druid",
                "spheres-archetype:pathfinder-class:druid:avatar",
                "High",
                frozenset({"magic", "martial"}),
                "1/2",
            ),
            (
                "pathfinder-class:paladin",
                "spheres-archetype:pathfinder-class:paladin:avowed",
                "Low",
                frozenset({"magic", "martial"}),
                "Full",
            ),
            (
                "pathfinder-class:ranger",
                "spheres-archetype:pathfinder-class:ranger:nature-s-blade",
                "",
                frozenset({"martial"}),
                "Full",
            ),
        )
        for class_key, archetype_key, sphere, capabilities, bab in cases:
            profile = resolve_class_profile(
                class_entry(class_key), (archetype_entry(archetype_key),)
            )
            self.assertEqual(sphere, profile.casting.get("sphere_progression", ""))
            self.assertFalse(profile.casting.get("traditional", True))
            self.assertTrue(capabilities <= profile.capabilities)
            self.assertEqual(bab, profile.bab_progression)

    def test_nature_fang_and_wild_whisperer_use_shared_power_picker(self) -> None:
        character, class_id = self.add_class("pathfinder-class:druid", 12)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:druid:nature-fang",),
        )
        slayer = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "nature-fang-slayer-talents"
        )
        self.assertEqual((4, 6, 8, 10, 12), slayer.slot_levels)
        self.assertTrue(slayer.options)

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:druid:wild-whisperer",),
        )
        investigator = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "wild-whisperer-investigator-talent"
        )
        self.assertEqual((8,), investigator.slot_levels)
        self.assertIn("Empathy", {option.name for option in investigator.options})

    def test_druid_nature_bond_restrictions_change_the_exact_shared_picker(self) -> None:
        character, class_id = self.add_class("pathfinder-class:druid", 8)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:druid:ancient-guardian",),
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(
            self.repository, character
        )}
        self.assertEqual(
            {"Druid Domain"}, {option.name for option in slots["nature-bond"].options}
        )
        bond = slots["nature-bond"]
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                character, bond, (bond.options[0].key,)
            )
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(
            self.repository, character
        )}
        self.assertEqual(
            {"Community Domain", "Healing Domain", "Knowledge Domain", "Protection Domain", "Repose Domain"},
            {option.name for option in slots["nature-domain"].options},
        )

    def test_paladin_borrowed_domains_and_grit_are_live(self) -> None:
        servant, servant_id = self.add_class("pathfinder-class:paladin", 8)
        self.repository.set_class_archetype_keys(
            servant,
            servant_id,
            ("pathfinder-archetype:pathfinder-class:paladin:sacred-servant",),
        )
        domain = next(
            item for item in resolve_class_choice_slots(self.repository, servant)
            if item.key == "sacred-servant-domain"
        )
        self.assertTrue(domain.options)
        self.assertEqual((1, 1), (domain.minimum, domain.maximum))

        gun, gun_id = self.add_class("pathfinder-class:paladin", 17)
        self.repository.update_ability_score(gun, "charisma", 18)
        self.repository.set_class_archetype_keys(
            gun,
            gun_id,
            ("pathfinder-archetype:pathfinder-class:paladin:holy-gun",),
        )
        grit = next(
            resource
            for module in resolve_class_feature_modules(self.repository, gun)
            for resource in module.resources
            if resource.key == "grit"
        )
        self.assertEqual(6, grit.maximum)

    def test_wild_stalker_rage_powers_and_sphere_ranger_budget_are_live(self) -> None:
        stalker, stalker_id = self.add_class("pathfinder-class:ranger", 16)
        self.repository.set_class_archetype_keys(
            stalker,
            stalker_id,
            ("pathfinder-archetype:pathfinder-class:ranger:wild-stalker",),
        )
        rage_powers = next(
            item for item in resolve_class_power_sets(self.repository, stalker)
            if item.key == "wild-stalker-rage-powers"
        )
        self.assertEqual(6, rage_powers.maximum)
        self.assertTrue(rage_powers.options)

        sphere, sphere_id = self.add_class("pathfinder-class:ranger", 10)
        self.repository.set_class_archetype_keys(
            sphere,
            sphere_id,
            ("spheres-archetype:pathfinder-class:ranger:sphere-ranger",),
        )
        budgets = {
            item.key: item
            for item in character_advancement_budgets(self.repository, sphere)
        }
        self.assertNotIn("spells", budgets)
        self.assertEqual(7, budgets["talents"].automatic)


if __name__ == "__main__":
    unittest.main()
