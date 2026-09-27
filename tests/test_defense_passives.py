import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.feat_automation import feat_automation
from app.services.character_calculations import CharacterCalculationService


class DefensePassiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.directory.name) / "test.db")
        self.cid = self.repo.create_character("Defense check", "Pathfinder 1e")

    def tearDown(self):
        self.repo.close()
        self.directory.cleanup()

    def combat(self):
        return {key: value.total for key, value in CharacterCalculationService(self.repo, self.cid).combat_results().items()}

    def test_shield_focus_changes_total_and_flat_footed_but_not_touch(self):
        self.repo.add_equipment(self.cid, "Heavy shield", "Shield", 1, 0, True, 2, "shield", None, "")
        before = self.combat()
        self.repo.add_feat(self.cid, "Shield Focus", catalog_key="aon:shield-focus", effects=feat_automation("Shield Focus")["effects"])
        after = self.combat()
        self.assertEqual((1, 0, 1), tuple(after[key] - before[key] for key in ("ac", "touch_ac", "flat_footed_ac")))

    def test_divine_grace_adds_positive_charisma_to_all_saves(self):
        self.repo.update_ability_score(self.cid, "charisma", 18)
        self.repo.add_class_level(self.cid, "Paladin", 2, "Full", "Good", "Poor", "Good", "pathfinder-class:paladin", 10, 16)
        result = self.combat()
        self.assertEqual((7, 4, 7), tuple(result[key] for key in ("fortitude", "reflex", "will")))

    def test_shield_feats_stack_only_on_an_equipped_shield(self):
        shield = self.repo.add_equipment(self.cid, "Heavy shield +1", "Shield", 1, 0, True, 2, "shield", None, "", enhancement_bonus=1)
        for name in ("Shield Focus", "Greater Shield Focus"):
            feat = self.repo.add_feat(self.cid, name, effects=feat_automation(name)["effects"])
        self.assertEqual(15, self.combat()["ac"])
        self.repo.set_feat_enabled(self.cid, feat, False)
        self.assertEqual(14, self.combat()["ac"])
        self.repo.set_equipment_equipped(self.cid, shield, False)
        self.assertEqual(10, self.combat()["ac"])

    def test_shield_focus_does_not_increase_a_separate_spell_shield_bonus(self):
        self.repo.add_equipment(self.cid, "Buckler", "Shield", 1, 0, True, 1, "shield", None, "")
        self.repo.add_feat(self.cid, "Shield Focus", effects=feat_automation("Shield Focus")["effects"])
        self.repo.add_modifier(self.cid, "ac", "Shield spell", "shield", 4)
        result = self.combat()
        self.assertEqual((14, 10, 14), tuple(result[key] for key in ("ac", "touch_ac", "flat_footed_ac")))

    def test_divine_grace_uses_effective_charisma_and_respects_replacement(self):
        self.repo.update_ability_score(self.cid, "charisma", 14)
        level = self.repo.add_class_level(self.cid, "Paladin", 2, "Full", "Good", "Poor", "Good", "pathfinder-class:paladin", 10, 16)
        self.repo.add_modifier(self.cid, "charisma", "Charisma enhancement", "enhancement", 4)
        self.assertEqual(7, self.combat()["fortitude"])
        self.repo.set_class_archetype_keys(self.cid, level, ("pathfinder-archetype:pathfinder-class:paladin:martyr",))
        self.assertEqual(3, self.combat()["fortitude"])

    def test_divine_grace_requires_level_two_and_never_penalizes_saves(self):
        self.repo.update_ability_score(self.cid, "charisma", 18)
        level = self.repo.add_class_level(self.cid, "Paladin", 1, "Full", "Good", "Poor", "Good", "pathfinder-class:paladin", 10, 10)
        self.assertEqual(2, self.combat()["fortitude"])
        self.repo.update_class_level(self.cid, level, "Paladin", 2, "Full", "Good", "Poor", "Good", "pathfinder-class:paladin", 10, 16)
        self.repo.update_ability_score(self.cid, "charisma", 8)
        self.assertEqual(3, self.combat()["fortitude"])

    def test_spheres_paladin_retains_divine_grace(self):
        self.repo.update_ability_score(self.cid, "charisma", 18)
        level = self.repo.add_class_level(self.cid, "Paladin", 2, "Full", "Good", "Poor", "Good", "pathfinder-class:paladin", 10, 16)
        self.repo.set_class_archetype_keys(self.cid, level, ("spheres-archetype:pathfinder-class:paladin:avowed",))
        self.assertEqual(7, self.combat()["fortitude"])
