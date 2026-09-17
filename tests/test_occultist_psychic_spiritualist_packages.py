from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.bonded_companion_rules import (
    bonded_companion_grants,
    bonded_companion_progression,
)
from app.catalogs import DEFAULT_CATALOG
from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.class_feature_systems import resolve_class_feature_modules
from app.class_granted_spells import synchronize_class_granted_spells
from app.class_mechanics_audit import build_audit
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


class OccultistPsychicSpiritualistPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "occult-classes.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self,
        key: str,
        level: int,
        *,
        intelligence: int = 10,
        wisdom: int = 10,
        charisma: int = 10,
        archetypes: tuple[str, ...] = (),
    ) -> tuple[int, int]:
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
            level * 6,
        )
        for ability, score in (
            ("intelligence", intelligence),
            ("wisdom", wisdom),
            ("charisma", charisma),
        ):
            self.repository.update_ability_score(character, ability, score)
        if archetypes:
            self.repository.set_class_archetype_keys(
                character, class_id, archetypes
            )
        return character, class_id

    def resources(self, character: int) -> dict[str, object]:
        calculator = CharacterCalculationService(self.repository, character)
        modifiers = {
            key: value.ability_modifier
            for key, value in calculator.ability_results().items()
        }
        return {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, modifiers
            )
            for resource in module.resources
        }

    def test_all_58_archetypes_pass_the_coverage_audit(self) -> None:
        for key in ("occultist", "psychic", "spiritualist"):
            self.assertEqual(
                key, class_package(f"pathfinder-class:{key}").key
            )
        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        targets = {
            "pathfinder-class:occultist": 23,
            "pathfinder-class:psychic": 9,
            "pathfinder-class:spiritualist": 26,
        }
        for class_key, count in targets.items():
            rows = [
                row for row in audit["archetypes"]
                if row.get("class_key") == class_key
            ]
            self.assertEqual(count, len(rows))
            self.assertEqual(
                {"fully_automated"}, {row["status"] for row in rows}
            )

    def test_occultist_implements_focus_powers_and_archetype_schedules(self) -> None:
        occultist, _ = self.add_class("pathfinder-class:occultist", 18)
        implement = next(
            slot for slot in resolve_class_choice_slots(self.repository, occultist)
            if slot.key == "occultist-implements"
        )
        self.assertEqual((7, 7), (implement.minimum, implement.maximum))
        self.assertEqual(8, len(implement.options))

        powers = next(
            row for row in resolve_class_power_sets(self.repository, occultist)
            if row.key == "occultist-focus-powers"
        )
        self.assertEqual(9, powers.maximum)
        self.assertEqual(53, len(powers.options))

        battle, _ = self.add_class(
            "pathfinder-class:occultist",
            18,
            archetypes=(
                "pathfinder-archetype:pathfinder-class:occultist:battle-host",
            ),
        )
        battle_implement = next(
            slot for slot in resolve_class_choice_slots(self.repository, battle)
            if slot.key == "occultist-implements"
        )
        self.assertEqual((5, 5), (battle_implement.minimum, battle_implement.maximum))

    def test_silksworn_focus_uses_both_mental_abilities(self) -> None:
        character, _ = self.add_class(
            "pathfinder-class:occultist",
            10,
            intelligence=18,
            charisma=16,
            archetypes=(
                "pathfinder-archetype:pathfinder-class:occultist:silksworn",
            ),
        )
        self.assertEqual(17, self.resources(character)["mental_focus"].maximum)

    def test_psychic_discipline_drives_pool_and_grants_spells(self) -> None:
        psychic, _ = self.add_class(
            "pathfinder-class:psychic", 10, wisdom=18, charisma=12
        )
        discipline = next(
            slot for slot in resolve_class_choice_slots(self.repository, psychic)
            if slot.key == "psychic-discipline"
        )
        bleaching = next(
            option for option in discipline.options
            if option.name == "Bleaching Discipline"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(psychic, discipline, (bleaching.key,))
        )
        self.assertEqual(9, self.resources(psychic)["phrenic_pool"].maximum)
        synchronize_class_granted_spells(self.repository, psychic)
        granted = [
            spell for spell in self.repository.list_spells(psychic)
            if spell.catalog_category == "Class Granted"
        ]
        self.assertEqual(5, len(granted))
        self.assertIn("Pessimism", {spell.name for spell in granted})

        powers = next(
            row for row in resolve_class_power_sets(self.repository, psychic)
            if row.key == "psychic-phrenic-amplifications"
        )
        self.assertEqual(3, powers.maximum)
        self.assertEqual(31, len(powers.options))
        self.assertEqual(
            9,
            sum(option.category == "Major Amplification" for option in powers.options),
        )

    def test_spiritualist_phantom_progression_and_ward_variant(self) -> None:
        spiritualist, _ = self.add_class("pathfinder-class:spiritualist", 12)
        grant = bonded_companion_grants(self.repository, spiritualist)["phantom"]
        self.assertEqual(12, grant.level)
        progression = bonded_companion_progression("phantom", 12, grant.variant)
        self.assertEqual("9d10", progression.hit_dice)
        self.assertEqual("9", progression.bab)
        self.assertEqual(10, progression.natural_armor)
        self.assertEqual("1d10", progression.natural_attack_damage)
        self.assertIn("Deliver Touch Spells (50 ft.)", progression.specials)

        ward, _ = self.add_class(
            "pathfinder-class:spiritualist",
            12,
            archetypes=(
                "pathfinder-archetype:pathfinder-class:spiritualist:ward-spiritualist",
            ),
        )
        ward_grant = bonded_companion_grants(self.repository, ward)["phantom"]
        self.assertEqual("kami_phantom", ward_grant.variant)
        ward_progression = bonded_companion_progression(
            "phantom", 12, ward_grant.variant
        )
        self.assertEqual("9d8", ward_progression.hit_dice)
        self.assertEqual("6", ward_progression.bab)
        self.assertTrue(
            any("ectoplasmic" in value.casefold() for value in ward_progression.specials)
        )

    def test_spheres_profiles_replace_only_the_authored_systems(self) -> None:
        reliquary = resolve_class_profile(
            class_entry("pathfinder-class:occultist"),
            (
                archetype_entry(
                    "spheres-archetype:pathfinder-class:occultist:reliquary-keeper"
                ),
            ),
        )
        self.assertFalse(reliquary.casting["traditional"])
        self.assertEqual("Mid", reliquary.casting["sphere_progression"])
        self.assertEqual("Low", reliquary.advancement["talent_progression"])

        ascendant = resolve_class_profile(
            class_entry("pathfinder-class:psychic"),
            (
                archetype_entry(
                    "spheres-archetype:pathfinder-class:psychic:ascendant-mind"
                ),
            ),
        )
        self.assertFalse(ascendant.casting["traditional"])
        self.assertNotIn("magic", ascendant.capabilities)

        psychomancer = resolve_class_profile(
            class_entry("pathfinder-class:spiritualist"),
            (
                archetype_entry(
                    "spheres-archetype:pathfinder-class:spiritualist:psychomancer"
                ),
            ),
        )
        self.assertFalse(psychomancer.casting["traditional"])
        self.assertEqual("Mid", psychomancer.casting["sphere_progression"])
        self.assertEqual("Mid", psychomancer.advancement["talent_progression"])


if __name__ == "__main__":
    unittest.main()
