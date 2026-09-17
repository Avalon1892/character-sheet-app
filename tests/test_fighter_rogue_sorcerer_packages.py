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
from app.models import ClassFeatureState
from app.services.advancement import character_advancement_budgets
from app.services.character_calculations import CharacterCalculationService
from app.traditional_spellcasting import prepared_caster_capacities


class FighterRogueSorcererPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "three-more-classes.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(self, key: str, level: int) -> tuple[int, int]:
        definition = class_entry(key)
        character = self.repository.create_character(
            key.rsplit(":", 1)[-1].title(), "Pathfinder 1e"
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
        self.assertEqual("fighter", class_package("pathfinder-class:fighter").key)
        self.assertEqual("rogue", class_package("pathfinder-class:rogue").key)
        self.assertEqual("sorcerer", class_package("pathfinder-class:sorcerer").key)
        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        for family, count in (("Fighter", 76), ("Rogue", 84), ("Sorcerer", 15)):
            rows = [row for row in audit["archetypes"] if row["class_name"] == family]
            self.assertEqual(count, len(rows))
            self.assertFalse(
                [row["name"] for row in rows if row["status"] != "fully_automated"]
            )

    def test_fighter_bravery_and_bonus_combat_feat_budget_are_live(self) -> None:
        character, class_id = self.add_class("pathfinder-class:fighter", 9)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "bravery_applies", 1, active=True
            )
        )
        self.assertEqual(
            2,
            CharacterCalculationService(
                self.repository, character
            ).automatic_total("will"),
        )
        feats = next(
            item for item in character_advancement_budgets(
                self.repository, character
            ) if item.key == "feats"
        )
        self.assertEqual(10, feats.automatic)  # 5 general + 5 Fighter bonus feats

    def test_mutation_warrior_reuses_mutagen_and_discovery_engines(self) -> None:
        character, class_id = self.add_class("pathfinder-class:fighter", 11)
        self.repository.update_ability_score(character, "intelligence", 18)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:fighter:mutation-warrior",),
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(1, resources["mutagen"].maximum)
        discoveries = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "mutation-warrior-discoveries"
        )
        self.assertEqual((7, 11), discoveries.slot_levels)
        self.assertIn("Feral Mutagen", {option.name for option in discoveries.options})

    def test_runesinger_and_soldier_have_exact_permanent_choices(self) -> None:
        runesinger, class_id = self.add_class("pathfinder-class:fighter", 8)
        self.repository.set_class_archetype_keys(
            runesinger,
            class_id,
            ("spheres-archetype:pathfinder-class:fighter:runesinger",),
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(
            self.repository, runesinger
        )}
        self.assertEqual((2, 2), (
            slots["runesinger-runes"].minimum,
            slots["runesinger-runes"].maximum,
        ))
        self.assertEqual(16, len(slots["runesinger-runes"].options))
        talents = next(
            item for item in character_advancement_budgets(
                self.repository, runesinger
            ) if item.key == "talents"
        )
        self.assertEqual(8, talents.automatic)

        soldier, soldier_id = self.add_class("pathfinder-class:fighter", 14)
        self.repository.set_class_archetype_keys(
            soldier,
            soldier_id,
            ("spheres-archetype:pathfinder-class:fighter:soldier",),
        )
        soldier_slots = {slot.key: slot for slot in resolve_class_choice_slots(
            self.repository, soldier
        )}
        self.assertEqual(3, soldier_slots["soldier-conditioning"].maximum)
        self.assertEqual(1, soldier_slots["soldier-sphere-specialization"].maximum)

    def test_rogue_archetypes_change_casting_resources_and_power_slots(self) -> None:
        scoundrel, class_id = self.add_class("pathfinder-class:rogue", 12)
        self.repository.set_class_archetype_keys(
            scoundrel,
            class_id,
            ("pathfinder-archetype:pathfinder-class:rogue:eldritch-scoundrel",),
        )
        capacities = prepared_caster_capacities(self.repository, scoundrel)
        self.assertEqual(1, len(capacities))
        self.assertEqual("intelligence", capacities[0].casting_ability)
        profile = resolve_class_profile(
            class_entry("pathfinder-class:rogue"),
            (archetype_entry(
                "pathfinder-archetype:pathfinder-class:rogue:eldritch-scoundrel"
            ),),
        )
        self.assertEqual(4, profile.skill_points)
        self.assertEqual("prepared", profile.casting["type"])

        snoop, snoop_id = self.add_class("pathfinder-class:rogue", 10)
        self.repository.update_ability_score(snoop, "intelligence", 18)
        self.repository.set_class_archetype_keys(
            snoop,
            snoop_id,
            ("pathfinder-archetype:pathfinder-class:rogue:snoop",),
        )
        inspiration = next(
            resource
            for module in resolve_class_feature_modules(self.repository, snoop)
            for resource in module.resources
            if resource.key == "inspiration"
        )
        self.assertEqual(9, inspiration.maximum)
        options = next(
            item for item in resolve_class_power_sets(self.repository, snoop)
            if item.key == "snoop-investigator-talents"
        ).options
        self.assertTrue(options)

    def test_crossblooded_and_sphere_sorcerer_apply_their_real_progressions(self) -> None:
        crossblooded, class_id = self.add_class("pathfinder-class:sorcerer", 5)
        self.repository.set_class_archetype_keys(
            crossblooded,
            class_id,
            ("pathfinder-archetype:pathfinder-class:sorcerer:crossblooded",),
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(
            self.repository, crossblooded
        )}
        self.assertEqual((2, 2), (
            slots["sorcerer-bloodline"].minimum,
            slots["sorcerer-bloodline"].maximum,
        ))
        bloodlines = slots["sorcerer-bloodline"]
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                crossblooded,
                bloodlines,
                tuple(option.key for option in bloodlines.options[:2]),
            )
        )
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, crossblooded)
        }
        self.assertIn("crossblooded-bonus-spell-5", slots)
        self.assertEqual(
            -2,
            CharacterCalculationService(
                self.repository, crossblooded
            ).automatic_total("will"),
        )
        spell_budget = next(
            item for item in character_advancement_budgets(
                self.repository, crossblooded
            ) if item.key == "spells"
        )
        self.assertEqual(9, spell_budget.automatic)  # 12 normal, -1 at 0th/1st/2nd

        sphere, sphere_id = self.add_class("pathfinder-class:sorcerer", 5)
        self.repository.set_class_archetype_keys(
            sphere,
            sphere_id,
            ("spheres-archetype:pathfinder-class:sorcerer:sphere-sorcerer",),
        )
        budget_keys = {
            item.key: item
            for item in character_advancement_budgets(self.repository, sphere)
        }
        self.assertNotIn("spells", budget_keys)
        self.assertEqual(7, budget_keys["talents"].automatic)
        self.assertEqual(
            5,
            CharacterCalculationService(
                self.repository, sphere
            ).automatic_total("spell_points"),
        )


if __name__ == "__main__":
    unittest.main()
