from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.animal_companion_rules import (
    calculate_companion_statistics, companion_catalog, companion_entry,
    companion_progression, resolve_companion_grant,
)
from app.class_feature_rules import resolve_class_features
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureSelection, SpecialAbilityAdjustment


class InquisitorCompanionTests(unittest.TestCase):
    def test_champion_replaces_traditional_spell_features_without_importing_site_navigation(self):
        base = class_entry("pathfinder-class:inquisitor")
        champion = archetype_entry("spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor")
        features = resolve_class_features(base["features"], (champion,), 5, "Inquisitor")
        names = {item.name for item in features}
        self.assertTrue({"Casting", "Spell Pool", "Blended Training"} <= names)
        self.assertNotIn("Inquisitor Spells", names)
        self.assertNotIn("Orisons", names)
        self.assertNotIn("Greater Training", names)  # optional exchange, not automatic
        self.assertNotIn("Bestiary", names)

    def test_published_companion_progression_is_cumulative(self):
        row = companion_progression(9)
        self.assertEqual((row.hit_dice, row.bab, row.feats, row.bonus_tricks), (8, 6, 4, 4))
        self.assertEqual(row.special, ("Link", "Share Spells", "Evasion", "Devotion", "Multiattack"))
        self.assertGreaterEqual(len(companion_catalog()), 200)

    def test_play_statistics_apply_species_advancement_and_progression(self):
        statistics = calculate_companion_statistics(
            companion_entry("cat-big-lion-tiger"),
            companion_progression(7),
            skill_ranks={"perception": 2},
        )
        self.assertEqual("Large", statistics.size)
        self.assertEqual({"str": 23, "dex": 17, "con": 17}, {
            key: statistics.ability_scores[key] for key in ("str", "dex", "con")
        })
        self.assertEqual(7, statistics.natural_armor)
        self.assertEqual((19, 16, 12), (
            statistics.armor_class, statistics.flat_footed_ac, statistics.touch_ac
        ))
        self.assertEqual({"fortitude": 8, "reflex": 8, "will": 4}, statistics.saves)
        self.assertEqual((11, 24, 45), (statistics.cmb, statistics.cmd, statistics.maximum_hp))
        self.assertEqual(("bite", "2 claws"), tuple(item.name for item in statistics.attacks))
        self.assertEqual(("1d8+6", "1d6+6"), tuple(item.damage for item in statistics.attacks))
        perception = next(item for item in statistics.skills if item.key == "perception")
        self.assertEqual(7, perception.total)
        self.assertIn("pounce", statistics.special_qualities)

        overridden = calculate_companion_statistics(
            companion_entry("cat-big-lion-tiger"),
            companion_progression(7),
            ability_overrides={"str": 30},
        )
        self.assertEqual(30, overridden.ability_scores["str"])
        self.assertEqual(17, overridden.ability_scores["dex"])

    def test_sacred_huntsmaster_grants_full_inquisitor_level(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = CharacterRepository(Path(folder) / "characters.db")
            character = repo.create_character("Hunter", "Pathfinder 1e")
            class_id = repo.add_class_level(
                character, "Inquisitor", 7, "3/4", "Good", "Poor", "Good",
                "pathfinder-class:inquisitor", 8, 50,
            )
            archetype = archetype_entry("pathfinder-archetype:pathfinder-class:inquisitor:sacred-huntsmaster")
            features = resolve_class_features(
                class_entry("pathfinder-class:inquisitor")["features"], (archetype,), 7, "Inquisitor"
            )
            grant = resolve_companion_grant(
                repo.list_class_levels(character), {class_id: features}, (),
                repo.list_skill_states(character), (),
            )
            self.assertTrue(grant.available)
            self.assertEqual(grant.effective_level, 7)
            repo.close()

    def test_new_character_overlays_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = CharacterRepository(Path(folder) / "characters.db")
            character = repo.create_character("Editor", "Pathfinder 1e")
            class_id = repo.add_class_level(character, "Inquisitor", 1, "3/4", "Good", "Poor", "Good")
            repo.save_special_ability_adjustment(
                SpecialAbilityAdjustment(0, character, "custom:test", 1, "Adjusted", "Rules", custom=True)
            )
            repo.save_class_feature_selection(
                ClassFeatureSelection(character, class_id, "domain", "Inquisition", "anger", "Anger", "Power")
            )
            self.assertEqual(repo.list_special_ability_adjustments(character)[0].name, "Adjusted")
            self.assertEqual(repo.list_class_feature_selections(character)[0].name, "Anger")
            repo.close()


if __name__ == "__main__":
    unittest.main()
