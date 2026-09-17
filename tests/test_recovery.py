from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from app.database import CharacterRepository
from app.models import HitPoints, ProdigySequence
from app.recovery import FullRestEngine


class FullRestEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "characters.db")
        self.character_id = self.repository.create_character("Resting Monk", "Spheres")
        self.repository.add_class_level(
            self.character_id,
            "Monk",
            8,
            "3/4",
            "Good",
            "Good",
            "Good",
            preset_key="monk",
            hit_die=8,
            hp_gained=40,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_full_rest_applies_built_in_and_custom_recovery(self) -> None:
        self.repository.update_hit_points(
            HitPoints(self.character_id, 50, 40, 5, 30, False)
        )
        profile = self.repository.get_casting_profile(self.character_id)
        self.repository.update_casting_profile(
            replace(
                profile,
                spell_points_maximum=7,
                spell_points_current=1,
                spell_points_temporary=2,
            )
        )
        focus = self.repository.get_martial_focus(self.character_id)
        self.repository.update_martial_focus(replace(focus, current=0))
        self.repository.update_prodigy_sequence(
            ProdigySequence(self.character_id, True, 3, 5, "life")
        )
        pool_id = self.repository.add_custom_tracker(
            self.character_id,
            "house_spell_points",
            "House Spell Points",
            "pool",
            formula="floor(character.level / 3)",
            current_value=0,
            temporary_value=1,
        )
        counter_id = self.repository.add_custom_tracker(
            self.character_id,
            "daily_uses",
            "Daily Uses",
            "counter",
            manual_maximum=5,
            current_value=4,
        )
        engine = FullRestEngine(self.repository, self.character_id)
        preferences = engine.effective_preferences()
        preferences["martial_focus"] = False
        preferences["tracker.house_spell_points"] = True
        preferences["tracker.daily_uses"] = True
        results = engine.perform(preferences)

        hp = self.repository.get_hit_points(self.character_id)
        self.assertEqual((48, 0, 0), (hp.current, hp.temporary, hp.nonlethal))
        profile = self.repository.get_casting_profile(self.character_id)
        self.assertEqual((7, 0), (profile.spell_points_current, profile.spell_points_temporary))
        self.assertEqual(0, self.repository.get_martial_focus(self.character_id).current)
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        self.assertEqual((False, 0, ""), (sequence.active, sequence.current, sequence.imbue_key))
        trackers = {item.id: item for item in self.repository.list_custom_trackers(self.character_id)}
        self.assertEqual((2, 0), (trackers[pool_id].current_value, trackers[pool_id].temporary_value))
        self.assertEqual(0, trackers[counter_id].current_value)
        self.assertTrue(any(item.key == "spell_points" for item in results))

    def test_preferences_are_per_character_and_survive_storage(self) -> None:
        self.repository.save_rest_preferences(
            self.character_id,
            {"spell_points": False, "hit_points.natural_healing": True},
        )
        self.assertEqual(
            {"spell_points": False, "hit_points.natural_healing": True},
            self.repository.get_rest_preferences(self.character_id),
        )
        other = self.repository.create_character("Other", "Pathfinder 1e")
        self.assertEqual({}, self.repository.get_rest_preferences(other))

    def test_full_rest_restores_expended_prepared_spell_copies(self) -> None:
        class_id = self.repository.list_class_levels(self.character_id)[0].id
        spell_id = self.repository.add_spell(
            self.character_id, "Shield", system="Prepared", level=1
        )
        prepared_id = self.repository.add_prepared_spell(
            self.character_id, class_id, spell_id, prepared_count=3, used_count=2
        )
        engine = FullRestEngine(self.repository, self.character_id)
        self.assertTrue(any(target.key == "prepared_spells" for target in engine.targets()))
        results = engine.perform({"prepared_spells": True})
        prepared = self.repository.list_prepared_spells(self.character_id)[0]
        self.assertEqual(prepared_id, prepared.id)
        self.assertEqual((3, 0, 3), (prepared.prepared_count, prepared.used_count, prepared.remaining))
        self.assertTrue(any(result.key == "prepared_spells" for result in results))

    def test_full_rest_restores_spontaneous_spell_slots(self) -> None:
        class_id = self.repository.list_class_levels(self.character_id)[0].id
        self.repository.set_spontaneous_slot_uses(
            self.character_id, class_id, 2, 3
        )
        engine = FullRestEngine(self.repository, self.character_id)
        self.assertTrue(
            any(target.key == "spontaneous_spell_slots" for target in engine.targets())
        )
        results = engine.perform({"spontaneous_spell_slots": True})
        usage = self.repository.list_spontaneous_slot_uses(self.character_id)[0]
        self.assertEqual(0, usage.used_count)
        self.assertTrue(
            any(result.key == "spontaneous_spell_slots" for result in results)
        )

    def test_full_rest_includes_automatic_spell_point_feature_sources(self) -> None:
        self.repository.update_ability_score(self.character_id, "wisdom", 16)
        profile = self.repository.get_casting_profile(self.character_id)
        self.repository.update_casting_profile(
            replace(
                profile,
                casting_ability="wisdom",
                casting_class_levels=8,
                auto_spell_points=True,
                spell_points_current=0,
            )
        )
        self.repository.add_feat(
            self.character_id,
            "Extra Spell Points",
            catalog_key="test:extra-spell-points",
            effects=({"target": "spell_points", "value": 2},),
        )

        FullRestEngine(self.repository, self.character_id).perform(
            {"spell_points": True}
        )

        self.assertEqual(
            13,
            self.repository.get_casting_profile(self.character_id).spell_points_current,
        )


if __name__ == "__main__":
    unittest.main()
