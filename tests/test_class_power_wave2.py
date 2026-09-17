from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG
from app.class_power_rules import (
    class_power_activation_record,
    class_power_reference_values,
    class_power_selection_record,
    resolve_class_power_sets,
)
from app.database import CharacterRepository
from app.recovery import FullRestEngine
from app.services.character_calculations import CharacterCalculationService


class ClassPowerWaveTwoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def character_with_class(self, name: str, key: str, level: int) -> tuple[int, int]:
        character_id = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character_id, name, level, "Full", "Good", "Good", "Good", key, 10, 50
        )
        return character_id, class_id

    def test_all_wave_two_providers_use_their_native_progressions(self) -> None:
        cases = (
            ("Rogue", "pathfinder-class:rogue", "rogue-talents", tuple(range(2, 21, 2))),
            ("Rogue (Unchained)", "pathfinder-class:rogue-unchained", "rogue-talents", tuple(range(2, 21, 2))),
            ("Slayer", "pathfinder-class:slayer", "slayer-talents", tuple(range(2, 21, 2))),
            ("Investigator", "pathfinder-class:investigator", "investigator-talents", tuple(range(3, 20, 2))),
            ("Witch", "pathfinder-class:witch", "witch-hexes", (1, 2, *tuple(range(4, 21, 2)))),
            ("Magus", "pathfinder-class:magus", "magus-arcana", tuple(range(3, 21, 3))),
            ("Arcanist", "pathfinder-class:arcanist", "arcanist-exploits", tuple(range(1, 20, 2))),
            ("Ninja", "pathfinder-class:ninja", "ninja-tricks", tuple(range(2, 21, 2))),
        )
        for name, key, provider_key, levels in cases:
            with self.subTest(name=name):
                character_id, _ = self.character_with_class(name, key, 20)
                power_sets = resolve_class_power_sets(self.repository, character_id)
                self.assertEqual(1, len(power_sets))
                self.assertEqual(provider_key, power_sets[0].key)
                self.assertEqual(levels, power_sets[0].slot_levels)

        alchemist_id, _ = self.character_with_class(
            "Alchemist", "pathfinder-class:alchemist", 20
        )
        alchemist_sets = {
            power_set.key: power_set
            for power_set in resolve_class_power_sets(self.repository, alchemist_id)
        }
        self.assertEqual(
            (*tuple(range(2, 21, 2)), 20, 20),
            alchemist_sets["alchemist-discoveries"].slot_levels,
        )
        self.assertEqual((20,), alchemist_sets["alchemist-grand-discovery"].slot_levels)
        self.assertEqual(
            {"Grand Discovery"},
            {option.category for option in alchemist_sets["alchemist-grand-discovery"].options},
        )

    def test_tiered_options_unlock_at_their_acquisition_level(self) -> None:
        character_id, _ = self.character_with_class("Rogue", "pathfinder-class:rogue", 10)
        power_set = resolve_class_power_sets(self.repository, character_id)[0]
        advanced = next(
            option for option in power_set.options
            if option.category == "Advanced" and not option.prerequisite_names
        )
        self.assertEqual(10, advanced.minimum_level)
        self.assertIn(advanced.key, power_set.unavailable_reasons)

        standards = [
            option for option in power_set.options
            if option.category == "Standard" and not option.prerequisite_names and not option.repeatable
        ][:4]
        self.repository.save_class_feature_selection(
            class_power_selection_record(
                character_id, power_set, (*[option.key for option in standards], advanced.key)
            )
        )
        resolved = resolve_class_power_sets(self.repository, character_id)[0]
        self.assertEqual(5, len(resolved.selected_options))
        self.assertEqual(advanced.key, resolved.selected_keys[-1])

    def test_power_prerequisites_and_repeatable_choices_share_one_validator(self) -> None:
        witch_id, _ = self.character_with_class("Witch", "pathfinder-class:witch", 4)
        witch_set = resolve_class_power_sets(self.repository, witch_id)[0]
        gift = next(option for option in witch_set.options if option.name == "Gift of Consumption")
        greater = next(option for option in witch_set.options if option.name == "Greater Gift of Consumption")
        invalid = class_power_selection_record(witch_id, witch_set, (greater.key,))
        self.repository.save_class_feature_selection(invalid)
        self.assertEqual((), resolve_class_power_sets(self.repository, witch_id)[0].selected_keys)
        valid = class_power_selection_record(witch_id, witch_set, (gift.key, greater.key))
        self.repository.save_class_feature_selection(valid)
        self.assertEqual(
            (gift.key, greater.key),
            resolve_class_power_sets(self.repository, witch_id)[0].selected_keys,
        )

        rogue_id, _ = self.character_with_class("Rogue", "pathfinder-class:rogue", 4)
        rogue_set = resolve_class_power_sets(self.repository, rogue_id)[0]
        focusing = next(option for option in rogue_set.options if option.name == "Focusing Attack")
        self.assertTrue(focusing.repeatable)
        self.repository.save_class_feature_selection(
            class_power_selection_record(rogue_id, rogue_set, (focusing.key, focusing.key))
        )
        resolved = resolve_class_power_sets(self.repository, rogue_id)[0]
        self.assertEqual((focusing.key, focusing.key), resolved.selected_keys)

    def test_archetype_exchanges_remove_only_the_named_slots(self) -> None:
        alchemist_id, alchemist_class_id = self.character_with_class(
            "Alchemist", "pathfinder-class:alchemist", 6
        )
        self.repository.set_class_archetype_keys(
            alchemist_id,
            alchemist_class_id,
            ("pathfinder-archetype:pathfinder-class:alchemist:aquachymist",),
        )
        self.assertEqual(
            (4, 6), resolve_class_power_sets(self.repository, alchemist_id)[0].slot_levels
        )

        arcanist_id, arcanist_class_id = self.character_with_class(
            "Arcanist", "pathfinder-class:arcanist", 11
        )
        self.repository.set_class_archetype_keys(
            arcanist_id,
            arcanist_class_id,
            ("pathfinder-archetype:pathfinder-class:arcanist:blade-adept",),
        )
        self.assertEqual(
            (5, 7, 11), resolve_class_power_sets(self.repository, arcanist_id)[0].slot_levels
        )

    def test_catalog_metadata_codex_labels_and_formula_references_are_shared(self) -> None:
        self.assertEqual("Witch Hexes", DEFAULT_CATALOG.class_power_family_label("witch_hex"))
        self.assertGreaterEqual(len(DEFAULT_CATALOG.class_power_entries("rogue_talent")), 250)
        self.assertGreaterEqual(len(DEFAULT_CATALOG.class_power_entries("alchemist_discovery")), 170)

        character_id, _ = self.character_with_class("Magus", "pathfinder-class:magus", 3)
        power_set = resolve_class_power_sets(self.repository, character_id)[0]
        arcana = next(
            option for option in power_set.options
            if not option.prerequisite_names and option.minimum_level <= 3
        )
        self.repository.save_class_feature_selection(
            class_power_selection_record(character_id, power_set, (arcana.key,))
        )
        resolved = resolve_class_power_sets(self.repository, character_id)[0]
        references = class_power_reference_values((resolved,))
        prefix = "class_power.magus.magus_arcana"
        self.assertEqual(1, references[f"{prefix}.count"])
        self.assertTrue(any(key.startswith(prefix) and value is True for key, value in references.items()))

    def test_situational_power_state_is_formula_visible_and_ends_on_full_rest(self) -> None:
        character_id, _ = self.character_with_class("Witch", "pathfinder-class:witch", 1)
        power_set = resolve_class_power_sets(self.repository, character_id)[0]
        evil_eye = next(option for option in power_set.options if option.name == "Evil Eye")
        self.assertTrue(evil_eye.activatable)
        self.repository.save_class_feature_selection(
            class_power_selection_record(character_id, power_set, (evil_eye.key,))
        )
        selected = resolve_class_power_sets(self.repository, character_id)[0]
        self.repository.save_class_feature_state(
            class_power_activation_record(character_id, selected, evil_eye.key, True)
        )
        active = resolve_class_power_sets(self.repository, character_id)[0]
        prefix = "class_power.witch.witch_hexes.evil_eye"
        references = class_power_reference_values((active,))
        self.assertTrue(references[prefix])
        self.assertTrue(references[f"{prefix}.selected"])
        self.assertTrue(references[f"{prefix}.active"])

        FullRestEngine(self.repository, character_id).perform({"class_feature_resources": True})
        rested = resolve_class_power_sets(self.repository, character_id)[0]
        self.assertFalse(class_power_reference_values((rested,))[f"{prefix}.active"])

    def test_reviewed_passive_effects_feed_the_shared_calculation_stack(self) -> None:
        witch_id, _ = self.character_with_class("Witch", "pathfinder-class:witch", 1)
        witch_set = resolve_class_power_sets(self.repository, witch_id)[0]
        iceplant = next(option for option in witch_set.options if option.name == "Iceplant")
        before_ac = CharacterCalculationService(
            self.repository, witch_id
        ).combat_results()["ac"].total
        self.repository.save_class_feature_selection(
            class_power_selection_record(witch_id, witch_set, (iceplant.key,))
        )
        after_ac = CharacterCalculationService(
            self.repository, witch_id
        ).combat_results()["ac"].total
        self.assertEqual(before_ac + 2, after_ac)

        alchemist_id, _ = self.character_with_class(
            "Alchemist", "pathfinder-class:alchemist", 20
        )
        grand = next(
            item for item in resolve_class_power_sets(self.repository, alchemist_id)
            if item.key == "alchemist-grand-discovery"
        )
        awakened = next(option for option in grand.options if option.name == "Awakened Intellect")
        before_int = CharacterCalculationService(
            self.repository, alchemist_id
        ).ability_result("intelligence").total
        self.repository.save_class_feature_selection(
            class_power_selection_record(alchemist_id, grand, (awakened.key,))
        )
        after_int = CharacterCalculationService(
            self.repository, alchemist_id
        ).ability_result("intelligence").total
        self.assertEqual(before_int + 2, after_int)


if __name__ == "__main__":
    unittest.main()
