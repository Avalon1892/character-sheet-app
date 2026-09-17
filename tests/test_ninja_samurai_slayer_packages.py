from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.animal_companion_rules import resolve_companion_grant
from app.catalogs import DEFAULT_CATALOG
from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_context import resolved_class_features_for_level
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import build_audit
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.models import Attack
from app.services.character_calculations import CharacterCalculationService


class NinjaSamuraiSlayerPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "martial-classes.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self,
        key: str,
        level: int,
        *,
        charisma: int = 10,
        intelligence: int = 10,
        wisdom: int = 10,
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
            level * 8,
        )
        for ability, score in (
            ("charisma", charisma),
            ("intelligence", intelligence),
            ("wisdom", wisdom),
        ):
            self.repository.update_ability_score(character, ability, score)
        if archetypes:
            self.repository.set_class_archetype_keys(
                character, class_id, archetypes
            )
        return character, class_id

    def resources(self, character: int) -> dict[str, object]:
        return {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character
            )
            for resource in module.resources
        }

    def test_all_49_archetypes_pass_the_coverage_audit(self) -> None:
        for key in ("ninja", "samurai", "slayer"):
            self.assertEqual(key, class_package(f"pathfinder-class:{key}").key)
        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        targets = {
            "pathfinder-class:ninja": 8,
            "pathfinder-class:samurai": 11,
            "pathfinder-class:slayer": 30,
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

    def test_ninja_ki_tricks_and_no_trace_are_live(self) -> None:
        character, class_id = self.add_class(
            "pathfinder-class:ninja", 12, charisma=18
        )
        resources = self.resources(character)
        self.assertEqual(10, resources["ki_pool"].maximum)
        tricks = next(
            row for row in resolve_class_power_sets(self.repository, character)
            if row.key == "ninja-tricks"
        )
        self.assertEqual(6, tricks.maximum)
        self.assertGreaterEqual(len(tricks.options), 200)

        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "no_trace_stationary", 1, active=True
            )
        )
        modifiers = CharacterCalculationService(
            self.repository, character
        ).automatic_modifier_map()
        self.assertEqual(
            4,
            max(item.value for item in modifiers["skill:disguise"]),
        )
        self.assertEqual(
            4,
            max(item.value for item in modifiers["skill:stealth"]),
        )

    def test_samurai_order_resolve_expertise_banner_and_mount(self) -> None:
        character, class_id = self.add_class(
            "pathfinder-class:samurai", 16, charisma=18
        )
        resources = self.resources(character)
        self.assertEqual(6, resources["challenge"].maximum)
        self.assertEqual(8, resources["resolve"].maximum)
        self.assertEqual(2, resources["honorable_stand"].maximum)
        choices = {
            row.key: row
            for row in resolve_class_choice_slots(self.repository, character)
        }
        self.assertEqual(36, len(choices["samurai-order"].options))
        self.assertEqual(
            {"Katana", "Longbow", "Naginata", "Wakizashi"},
            {option.name for option in choices["samurai-weapon-expertise"].options},
        )

        class_level = self.repository.list_class_levels(character)[0]
        grant = resolve_companion_grant(
            (class_level,),
            {
                class_id: resolved_class_features_for_level(
                    self.repository, character, class_level
                )
            },
            (),
            {},
        )
        self.assertTrue(grant.available)
        self.assertEqual(16, grant.effective_level)

    def test_slayer_talents_studied_target_track_and_quarry(self) -> None:
        character, class_id = self.add_class(
            "pathfinder-class:slayer", 19, intelligence=18
        )
        resources = self.resources(character)
        self.assertEqual(4, resources["studied_target"].maximum_choices)
        self.assertEqual(1, resources["quarry"].maximum)
        talents = next(
            row for row in resolve_class_power_sets(self.repository, character)
            if row.key == "slayer-talents"
        )
        self.assertEqual(9, talents.maximum)
        self.assertGreaterEqual(len(talents.options), 80)

        self.repository.save_class_feature_state(
            ClassFeatureState(
                character,
                class_id,
                "studied_target",
                1,
                active=True,
                choices_json=json.dumps(["Ancient dragon"]),
            )
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character,
                class_id,
                "quarry",
                1,
                active=True,
                choices_json=json.dumps(["Ancient dragon"]),
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        attack = Attack(
            0, "Longsword", "Melee", "strength", 0, "1d8",
            "strength", 1.0, 0, "19-20/x2",
        )
        attack_modifiers, _damage_modifiers = calculator.attack_effects(attack, 0)
        self.assertEqual(4, sum(item.value for item in attack_modifiers))
        self.assertEqual(4, calculator.automatic_total("attack"))
        self.assertEqual(13, calculator.automatic_total("skill:survival"))

    def test_reviewed_spheres_profiles_and_archetype_resources(self) -> None:
        shrouded = resolve_class_profile(
            class_entry("pathfinder-class:ninja"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:ninja:shrouded-operative"
            ),),
        )
        self.assertEqual("Mid", shrouded.casting["sphere_progression"])
        self.assertEqual("Expert", shrouded.advancement["talent_progression"])
        self.assertEqual({"magic", "martial"}, set(shrouded.capabilities))

        honorbound = resolve_class_profile(
            class_entry("pathfinder-class:samurai"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:samurai:honorbound"
            ),),
        )
        self.assertEqual("Adept", honorbound.advancement["talent_progression"])
        self.assertIn("martial", honorbound.capabilities)

        mercenary = resolve_class_profile(
            class_entry("pathfinder-class:slayer"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:slayer:mercenary"
            ),),
        )
        self.assertEqual("Expert", mercenary.advancement["talent_progression"])

        bombardier, _ = self.add_class(
            "pathfinder-class:ninja",
            9,
            charisma=16,
            archetypes=(
                "pathfinder-archetype:pathfinder-class:ninja:gunpowder-bombardier",
            ),
        )
        bomb_resources = self.resources(bombardier)
        self.assertEqual(7, bomb_resources["ki_pool"].maximum)
        bomb = bomb_resources["gunpowder_bomb"]
        self.assertEqual(4, sum(level <= 9 for level in bomb.extra_damage_levels))
        self.assertEqual("d6", bomb.extra_damage_die)

        toxic, _ = self.add_class(
            "pathfinder-class:slayer",
            10,
            wisdom=18,
            archetypes=(
                "pathfinder-archetype:pathfinder-class:slayer:toxic-sniper",
            ),
        )
        toxic_resources = self.resources(toxic)
        self.assertEqual(4, toxic_resources["grit"].maximum)
        self.assertEqual(9, toxic_resources["toxic_shots"].maximum)


if __name__ == "__main__":
    unittest.main()
