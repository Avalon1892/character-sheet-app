from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG
from app.archetype_rules import (
    archetype_choices,
    encode_archetype_choice_option_keys,
)
from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_systems import (
    class_feature_extra_damage,
    resolve_class_feature_modules,
)
from app.class_mechanics_audit import build_audit
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureSelection, ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


class HunterMediumMesmeristPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "hunter-medium-mesmerist.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self,
        key: str,
        level: int,
        *,
        wisdom: int = 10,
        charisma: int = 10,
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
            max(int(definition["hit_die"]), level * 5),
        )
        self.repository.update_ability_score(character, "wisdom", wisdom)
        self.repository.update_ability_score(character, "charisma", charisma)
        return character, class_id

    def resources(self, character: int) -> dict[str, object]:
        calculations = CharacterCalculationService(self.repository, character)
        modifiers = {
            ability: result.ability_modifier
            for ability, result in calculations.ability_results().items()
        }
        return {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, modifiers
            )
            for resource in module.resources
        }

    def test_packages_and_all_73_archetypes_pass_the_coverage_audit(self) -> None:
        for family in ("hunter", "medium", "mesmerist"):
            self.assertEqual(
                family, class_package(f"pathfinder-class:{family}").key
            )
        root = (
            Path(__file__).resolve().parent.parent
            / "app" / "class_packages" / "definitions" / "archetypes"
        )
        for family, count in (("hunter", 27), ("medium", 20), ("mesmerist", 26)):
            document = json.loads((root / f"{family}.json").read_text("utf-8"))
            self.assertEqual(count, len(document["entries"]))

        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        keys = {
            "pathfinder-class:hunter",
            "pathfinder-class:medium",
            "pathfinder-class:mesmerist",
        }
        entries = [
            row for row in audit["archetypes"] if row.get("class_key") in keys
        ]
        self.assertEqual(73, len(entries))
        self.assertEqual({"fully_automated"}, {row["status"] for row in entries})

    def test_hunter_focus_uses_published_stag_and_ability_tiers(self) -> None:
        hunter, class_id = self.add_class(
            "pathfinder-class:hunter", 5, wisdom=16
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                hunter, class_id, "animal_focus", 5,
                active=True, choices_json='["Stag"]',
            )
        )
        calculations = CharacterCalculationService(self.repository, hunter)
        self.assertEqual(5, calculations.automatic_total("speed"))

        hunter_8, class_id_8 = self.add_class(
            "pathfinder-class:hunter", 8, wisdom=16
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                hunter_8, class_id_8, "animal_focus", 8,
                active=True, choices_json='["Bull", "Stag"]',
            )
        )
        resources = self.resources(hunter_8)
        self.assertEqual(2, resources["animal_focus"].maximum_choices)
        calculations = CharacterCalculationService(self.repository, hunter_8)
        self.assertEqual(4, calculations.automatic_total("strength"))
        self.assertEqual(10, calculations.automatic_total("speed"))

    def test_medium_influence_and_archetype_domain_choices_are_live(self) -> None:
        medium, _ = self.add_class(
            "pathfinder-class:medium", 10, charisma=18
        )
        influence = self.resources(medium)["influence"]
        self.assertEqual(5, influence.maximum)
        self.assertEqual(
            {"Archmage", "Champion", "Guardian", "Hierophant", "Marshal", "Trickster"},
            set(influence.choice_options),
        )

        storm, class_id = self.add_class(
            "pathfinder-class:medium", 12, charisma=18
        )
        self.repository.set_class_archetype_keys(
            storm,
            class_id,
            ("pathfinder-archetype:pathfinder-class:medium:storm-dreamer",),
        )
        domain = next(
            slot for slot in resolve_class_choice_slots(self.repository, storm)
            if slot.key == "storm-dreamer-domain"
        )
        self.assertEqual(
            {"Air Domain", "Animal Domain", "Plant Domain", "Water Domain", "Weather Domain"},
            {option.name for option in domain.options},
        )

    def test_medium_archetype_resource_adjustments_and_rivethun_ability_choice(self) -> None:
        reanimated, class_id = self.add_class(
            "pathfinder-class:medium", 8, charisma=18
        )
        self.repository.set_class_archetype_keys(
            reanimated,
            class_id,
            ("pathfinder-archetype:pathfinder-class:medium:reanimated-medium",),
        )
        influence = self.resources(reanimated)["influence"]
        self.assertEqual(6, influence.maximum)
        self.assertEqual(3, influence.current)
        self.assertFalse(influence.use_increases)

        rivethun, rivethun_class_id = self.add_class(
            "pathfinder-class:medium", 8, wisdom=20, charisma=12
        )
        archetype_key = (
            "pathfinder-archetype:pathfinder-class:medium:"
            "rivethun-spirit-channeler"
        )
        self.repository.set_class_archetype_keys(
            rivethun, rivethun_class_id, (archetype_key,)
        )
        archetype = archetype_entry(archetype_key)
        choice = archetype_choices(archetype)[0]
        self.repository.save_class_feature_selection(
            ClassFeatureSelection(
                rivethun,
                rivethun_class_id,
                choice.key,
                "Archetype choice",
                encode_archetype_choice_option_keys(("wisdom",)),
                "Wisdom",
                choice.description,
            )
        )
        profile = resolve_class_profile(
            class_entry("pathfinder-class:medium"),
            (archetype,),
            {choice.key: ("wisdom",)},
        )
        self.assertEqual("wisdom", profile.casting["ability"])
        module = next(
            module
            for module in resolve_class_feature_modules(
                self.repository,
                rivethun,
                {"wisdom": 5, "charisma": 1},
            )
            if module.key == "medium"
        )
        self.assertEqual("wisdom", module.governing_ability)

    def test_mesmerist_tricks_stares_touch_treatment_and_stare_damage(self) -> None:
        mesmerist, class_id = self.add_class(
            "pathfinder-class:mesmerist", 12, charisma=18
        )
        resources = self.resources(mesmerist)
        self.assertEqual(10, resources["mesmerist_tricks"].maximum)
        self.assertEqual(7, resources["touch_treatment"].maximum)

        powers = {
            power.key: power
            for power in resolve_class_power_sets(self.repository, mesmerist)
        }
        tricks = powers["mesmerist-tricks"]
        stares = powers["mesmerist-bold-stares"]
        self.assertEqual(7, tricks.maximum)
        self.assertEqual(3, stares.maximum)
        self.assertGreaterEqual(len(tricks.options), 44)
        self.assertEqual(24, len(stares.options))
        self.assertIn("Masterful Trick", {option.category for option in tricks.options})

        self.repository.save_class_feature_state(
            ClassFeatureState(
                mesmerist, class_id, "hypnotic_stare", 1,
                active=True, choices_json='["Target"]',
            )
        )
        extra = class_feature_extra_damage(self.repository, mesmerist)
        painful = next(item for item in extra if "Painful Stare" in item.source)
        self.assertEqual("4d6+6", painful.dice)

    def test_spheres_profiles_remove_spells_and_keep_exact_progressions(self) -> None:
        cases = (
            (
                "pathfinder-class:hunter",
                "spheres-archetype:pathfinder-class:hunter:beast-bender",
                "Mid", "High", {"magic", "martial"},
            ),
            (
                "pathfinder-class:medium",
                "spheres-archetype:pathfinder-class:medium:sphere-medium",
                "Low", "Low", {"magic"},
            ),
            (
                "pathfinder-class:mesmerist",
                "spheres-archetype:pathfinder-class:mesmerist:champion-mesmerist",
                "Mid", "Mid", {"magic", "martial"},
            ),
        )
        for class_key, archetype_key, caster, talents, capabilities in cases:
            profile = resolve_class_profile(
                class_entry(class_key), (archetype_entry(archetype_key),)
            )
            self.assertFalse(profile.casting.get("traditional", True))
            self.assertEqual(caster, profile.casting["sphere_progression"])
            self.assertEqual(talents, profile.advancement["talent_progression"])
            self.assertTrue(capabilities <= profile.capabilities)


if __name__ == "__main__":
    unittest.main()
