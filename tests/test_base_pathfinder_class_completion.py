from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import build_audit
from app.class_power_rules import resolve_class_power_sets
from app.database import CharacterRepository
from app.models import Attack, ClassFeatureState
from app.recovery import FullRestEngine
from app.services.character_calculations import CharacterCalculationService


class BasePathfinderClassCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _character(self, key: str, level: int, **abilities: int) -> tuple[int, int]:
        character = self.repository.create_character(key, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character,
            key.rsplit(":", 1)[-1].replace("-", " ").title(),
            level,
            "3/4",
            "Good",
            "Good",
            "Good",
            key,
            8,
            40,
        )
        for ability, score in abilities.items():
            self.repository.update_ability_score(character, ability, score)
        return character, class_id

    def _module(self, character: int, key: str):
        return next(
            item
            for item in resolve_class_feature_modules(self.repository, character)
            if item.key == key
        )

    def test_paladin_linked_channel_uses_follow_lay_on_hands(self) -> None:
        character, class_id = self._character(
            "pathfinder-class:paladin", 10, charisma=18
        )
        resources = {item.key: item for item in self._module(character, "paladin").resources}
        self.assertEqual(4, resources["smite"].maximum)
        self.assertEqual(9, resources["lay_on_hands"].maximum)
        self.assertEqual(4, resources["channel_energy"].current)

        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "lay_on_hands", 3)
        )
        resources = {item.key: item for item in self._module(character, "paladin").resources}
        self.assertEqual(1, resources["channel_energy"].current)

    def test_accumulating_burn_clears_on_full_rest(self) -> None:
        character, class_id = self._character(
            "pathfinder-class:kineticist", 9, constitution=18
        )
        burn = self._module(character, "kineticist").resources[0]
        self.assertEqual(7, burn.maximum)
        self.assertEqual(0, burn.current)
        self.assertTrue(burn.use_increases)
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "burn", 4)
        )
        FullRestEngine(self.repository, character).perform(
            {"class_feature_resources": True}
        )
        self.assertEqual(0, self._module(character, "kineticist").resources[0].current)

    def test_sneak_attack_and_studied_target_feed_attack_profile(self) -> None:
        rogue, rogue_class = self._character("pathfinder-class:rogue", 7)
        self.repository.save_class_feature_state(
            ClassFeatureState(rogue, rogue_class, "sneak_attack", 1, active=True)
        )
        attack = Attack(0, "Short sword", "Melee", "strength", 0, "1d6", "strength", 1.0, 0, "19-20/x2")
        profile = CharacterCalculationService(self.repository, rogue).resolve_attack_profile(attack)
        self.assertEqual("4d6", profile.extra_damage[-1].dice)

        slayer, slayer_class = self._character("pathfinder-class:slayer", 10)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                slayer,
                slayer_class,
                "studied_target",
                1,
                active=True,
                choices_json=json.dumps(["Ogre mage"]),
            )
        )
        attack_modifiers, damage_modifiers = CharacterCalculationService(
            self.repository, slayer
        ).attack_effects(attack, 0)
        self.assertEqual(3, sum(item.value for item in attack_modifiers))
        self.assertEqual(3, sum(item.value for item in damage_modifiers))

    def test_skald_gets_raging_song_and_rage_power_slots(self) -> None:
        character, _class_id = self._character(
            "pathfinder-class:skald", 9, charisma=16
        )
        song = self._module(character, "skald").resources[0]
        self.assertEqual(22, song.maximum)
        powers = next(
            item
            for item in resolve_class_power_sets(self.repository, character)
            if item.key == "skald-rage-powers"
        )
        self.assertEqual((3, 6, 9), powers.slot_levels)

    def test_fighter_hunter_and_swashbuckler_live_effects_feed_calculations(self) -> None:
        attack = Attack(0, "Rapier", "Melee", "strength", 0, "1d6", "strength", 1.0, 0, "18-20/x2")

        fighter, fighter_class = self._character("pathfinder-class:fighter", 9)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                fighter, fighter_class, "weapon_training", 2, active=True,
                choices_json=json.dumps(["Heavy blades"]),
            )
        )
        attack_modifiers, damage_modifiers = CharacterCalculationService(
            self.repository, fighter
        ).attack_effects(attack, 0)
        self.assertEqual(2, sum(item.value for item in attack_modifiers))
        self.assertEqual(2, sum(item.value for item in damage_modifiers))

        hunter, hunter_class = self._character("pathfinder-class:hunter", 8)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                hunter, hunter_class, "animal_focus", 8, active=True,
                choices_json=json.dumps(["Bull"]),
            )
        )
        modifiers = CharacterCalculationService(self.repository, hunter).automatic_modifier_map()
        self.assertEqual(4, max(item.value for item in modifiers.get("strength", ())))

        swashbuckler, swash_class = self._character("pathfinder-class:swashbuckler", 9)
        self.repository.save_class_feature_state(
            ClassFeatureState(swashbuckler, swash_class, "weapon_training", 2, active=True)
        )
        attack_modifiers, damage_modifiers = CharacterCalculationService(
            self.repository, swashbuckler
        ).attack_effects(attack, 0)
        self.assertEqual(2, sum(item.value for item in attack_modifiers))
        self.assertEqual(2, sum(item.value for item in damage_modifiers))

    def test_new_choice_catalogs_cover_first_level_class_decisions(self) -> None:
        from app.class_choice_rules import resolve_class_choice_slots

        cases = (
            ("pathfinder-class:oracle", "oracle-curse", "Lame Curse"),
            ("pathfinder-class:witch", "witch-patron", "Time Patron"),
            ("pathfinder-class:psychic", "psychic-discipline", "Pain Discipline"),
        )
        for key, slot_key, expected in cases:
            character, _class_id = self._character(key, 1)
            slot = next(
                item for item in resolve_class_choice_slots(self.repository, character)
                if item.key == slot_key
            )
            self.assertIn(expected, {option.name for option in slot.options})

    def test_dynamic_class_choices_follow_their_level_progressions(self) -> None:
        from app.class_choice_rules import resolve_class_choice_slots

        shifter, _ = self._character("pathfinder-class:shifter", 20)
        shifter_slot = next(
            item for item in resolve_class_choice_slots(self.repository, shifter)
            if item.key == "shifter-aspects"
        )
        self.assertEqual(4, shifter_slot.maximum)

        kineticist, _ = self._character("pathfinder-class:kineticist", 15)
        kineticist_slot = next(
            item for item in resolve_class_choice_slots(self.repository, kineticist)
            if item.key == "kineticist-elements"
        )
        self.assertEqual(3, kineticist_slot.maximum)

        warpriest, _ = self._character("pathfinder-class:warpriest", 1)
        blessing_slot = next(
            item for item in resolve_class_choice_slots(self.repository, warpriest)
            if item.key == "warpriest-blessings"
        )
        self.assertEqual((2, 2), (blessing_slot.minimum, blessing_slot.maximum))

    def test_all_original_pathfinder_classes_have_no_audited_runtime_gap(self) -> None:
        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        pathfinder = [
            row for row in audit["classes"] if row["source_group"] == "Pathfinder"
        ]
        self.assertEqual(44, len(pathfinder))
        self.assertTrue(all(row["status"] == "fully_automated" for row in pathfinder))
        self.assertFalse(
            [row for row in pathfinder if row["missing_interactive_mechanics"]]
        )


if __name__ == "__main__":
    unittest.main()
