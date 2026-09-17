from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.advancement_rules import calculate_advancement_budgets
from app.archetype_rules import (
    archetype_choice_selections_from_records,
    archetype_choices,
    decode_archetype_choice_option_keys,
    encode_archetype_choice_option_keys,
)
from app.class_feature_rules import resolve_class_features
from app.class_modifications import resolve_class_level, resolve_class_profile
from app.class_proficiencies import resolved_proficiencies
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureSelection, ClassLevel
from app.rules import automatic_sphere_casting, automatic_traditional_casting


EXPLOITANT = "spheres-archetype:prodigy:exploitant"
BRUTAL_NECROMANCER = "spheres-archetype:spheres-class:necros:brutal-necromancer"


class ArchetypeModificationAndChoiceTests(unittest.TestCase):
    def test_exploitant_declares_reusable_required_choice(self) -> None:
        entry = archetype_entry(EXPLOITANT)
        choices = archetype_choices(entry)
        self.assertEqual(1, len(choices))
        self.assertEqual((1, 1), (choices[0].minimum, choices[0].maximum))
        self.assertEqual(
            {"Moldable Talents", "Spontaneous Technique"},
            {option.name for option in choices[0].options},
        )

    def test_only_selected_exploitant_insight_is_projected(self) -> None:
        archetype = archetype_entry(EXPLOITANT)
        choice = archetype_choices(archetype)[0]
        base = class_entry("prodigy")
        resolved = resolve_class_features(
            base.get("features", ()), (archetype,), 5, "Prodigy",
            selected_archetype_choices={choice.key: ("moldable-talents",)},
        )
        names = {feature.name for feature in resolved}
        self.assertIn("Moldable Talents", names)
        self.assertNotIn("Spontaneous Technique", names)
        self.assertIn("Exploitant’s Insights", names)

    def test_brutal_necromancer_overrides_shared_class_profile(self) -> None:
        base = class_entry("spheres-class:necros")
        archetype = archetype_entry(BRUTAL_NECROMANCER)
        profile = resolve_class_profile(base, (archetype,))
        self.assertEqual((10, "Full", "Low"), (
            profile.hit_die, profile.bab_progression,
            profile.casting["sphere_progression"],
        ))
        class_level = ClassLevel(
            1, "Necros", 5, "3/4", "Good", "Poor", "Good",
            "spheres-class:necros", 8, 28,
        )
        resolved = resolve_class_level(class_level, base, (archetype,))
        self.assertEqual((10, "Full", 34), (
            resolved.hit_die, resolved.bab_progression, resolved.hp_gained,
        ))

    def test_archetype_casting_progression_can_replace_base_progression(self) -> None:
        level = ClassLevel(
            4, "Necros", 5, "3/4", "Good", "Poor", "Good",
            "spheres-class:necros", 8, 28,
        )
        classes = {"spheres-class:necros": class_entry("spheres-class:necros")}
        archetype = archetype_entry(BRUTAL_NECROMANCER)
        result = automatic_sphere_casting(
            [level], classes, {level.id: (BRUTAL_NECROMANCER,)},
            {BRUTAL_NECROMANCER: archetype},
        )
        self.assertEqual((5, 2, "Necros"), result)

    def test_sphere_conversion_profiles_replace_traditional_casting(self) -> None:
        cases = (
            (
                "pathfinder-class:bard",
                "spheres-archetype:pathfinder-class:bard:champion-bard",
                "Mid",
                "charisma",
            ),
            (
                "pathfinder-class:inquisitor",
                "spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor",
                "Mid",
                "wisdom",
            ),
            (
                "pathfinder-class:oracle",
                "spheres-archetype:pathfinder-class:oracle:sphere-oracle",
                "High",
                "charisma",
            ),
        )
        for class_key, archetype_key, progression, ability in cases:
            base = class_entry(class_key)
            archetype = archetype_entry(archetype_key)
            profile = resolve_class_profile(base, (archetype,))
            self.assertEqual(progression, profile.casting["sphere_progression"])
            self.assertEqual(ability, profile.casting["ability"])
            self.assertFalse(profile.casting["traditional"])
            level = ClassLevel(
                1, str(base["name"]), 8, str(base["bab"]), str(base["fort"]),
                str(base["reflex"]), str(base["will"]), class_key,
                int(base["hit_die"]), 48,
            )
            self.assertIsNone(automatic_traditional_casting(
                [level], {class_key: base}, {1: (archetype_key,)},
                {archetype_key: archetype},
            ))
            self.assertIsNotNone(automatic_sphere_casting(
                [level], {class_key: base}, {1: (archetype_key,)},
                {archetype_key: archetype},
            ))

    def test_battle_born_removes_casting_and_changes_core_statistics(self) -> None:
        base = class_entry("prodigy")
        archetype_key = "spheres-archetype:prodigy:battle-born"
        archetype = archetype_entry(archetype_key)
        profile = resolve_class_profile(base, (archetype,))
        self.assertEqual((10, "Full", ""), (
            profile.hit_die,
            profile.bab_progression,
            profile.casting["sphere_progression"],
        ))
        level = ClassLevel(
            1, "Prodigy", 8, "3/4", "Poor", "Good", "Good",
            "prodigy", 8, 46,
        )
        self.assertIsNone(automatic_sphere_casting(
            [level], {"prodigy": base}, {1: (archetype_key,)},
            {archetype_key: archetype},
        ))

    def test_structured_proficiency_changes_and_dwarven_choice(self) -> None:
        bard = class_entry("pathfinder-class:bard")
        arrowsong = archetype_entry(
            "pathfinder-archetype:pathfinder-class:bard:arrowsong-minstrel"
        )
        weapons, _armor = resolved_proficiencies(bard, (arrowsong,))
        self.assertIn("Longbows", weapons)
        self.assertNotIn("Rapier", weapons)

        scholar = archetype_entry(
            "pathfinder-archetype:pathfinder-class:bard:dwarven-scholar"
        )
        choice = archetype_choices(scholar)[0]
        self.assertEqual("Dwarven Weapon Proficiency", choice.name)
        self.assertIn("Dwarven Waraxe", {option.name for option in choice.options})
        waraxe = next(
            option for option in choice.options if option.name == "Dwarven Waraxe"
        )
        scholar_weapons, scholar_armor = resolved_proficiencies(
            bard, (scholar,), {choice.key: (waraxe.key,)}
        )
        self.assertIn("Dwarven Waraxe", scholar_weapons)
        self.assertFalse(any("Shield" in value for value in scholar_armor))

    def test_choice_record_is_backward_compatible_and_drives_talent_budget(self) -> None:
        archetype = archetype_entry(EXPLOITANT)
        choice = archetype_choices(archetype)[0]
        record = ClassFeatureSelection(
            1, 7, choice.key, "Archetype choice",
            encode_archetype_choice_option_keys(("moldable-talents",)),
            "Moldable Talents", "",
        )
        self.assertEqual(("moldable-talents",), decode_archetype_choice_option_keys(record.option_key))
        self.assertEqual(
            {choice.key: ("moldable-talents",)},
            archetype_choice_selections_from_records((record,), 7),
        )
        level = ClassLevel(7, "Prodigy", 8, "3/4", "Poor", "Good", "Good", "prodigy", 8, 46)
        base_inputs = dict(
            classes=(level,), class_lookup=class_entry, intelligence_modifier=0,
            race="", skill_ranks=0, favored_skill_points=0, feats=(),
            martial_talents=(), spells=(), traditions=(), adjustments={},
            archetype_keys_by_class_level={7: (EXPLOITANT,)},
            archetype_lookup=archetype_entry,
        )
        without = calculate_advancement_budgets(**base_inputs)
        with_choice = calculate_advancement_budgets(**base_inputs, feature_selections=(record,))
        normal = next(item.total for item in without if item.key == "talents")
        moldable = next(item.total for item in with_choice if item.key == "talents")
        self.assertEqual(3, moldable - normal)  # levels 2, 5, and 8

    def test_choice_selection_persists_without_schema_changes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = CharacterRepository(Path(folder) / "characters.db")
            character = repository.create_character("Exploitant", "Spheres")
            class_id = repository.add_class_level(
                character, "Prodigy", 2, "3/4", "Poor", "Good", "Good",
                preset_key="prodigy", hit_die=8, hp_gained=13,
            )
            choice = archetype_choices(archetype_entry(EXPLOITANT))[0]
            repository.save_class_feature_selection(ClassFeatureSelection(
                character, class_id, choice.key, "Archetype choice",
                encode_archetype_choice_option_keys(("spontaneous-technique",)),
                "Spontaneous Technique", "Rules",
            ))
            saved = repository.list_class_feature_selections(character)
            self.assertEqual(
                ("spontaneous-technique",),
                archetype_choice_selections_from_records(saved, class_id)[choice.key],
            )
            repository.close()


if __name__ == "__main__":
    unittest.main()
