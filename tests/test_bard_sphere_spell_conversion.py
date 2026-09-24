import json
import tempfile
import unittest
from pathlib import Path

from app.advancement_rules import calculate_advancement_budgets
from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.class_granted_spells import resolve_class_granted_spells, synchronize_class_granted_spells
from app.class_feature_systems import resolve_class_feature_modules
from app.class_modifications import sphere_bonus_spell_conversions
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState, SkillState
from app.services.character_calculations import CharacterCalculationService


SPHERE = "spheres-archetype:pathfinder-class:bard:sphere-bard"
PREFIX = "pathfinder-archetype:pathfinder-class:bard:"


class BardSphereSpellConversionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.folder.name) / "test.db")
        self.character = self.repository.create_character("Bard", "Pathfinder 1e")

    def tearDown(self):
        self.repository.close()
        self.folder.cleanup()

    def add_bard(self, level, archetypes=()):
        class_id = self.repository.add_class_level(
            self.character, "Bard", level, "3/4", "Poor", "Good", "Good",
            "pathfinder-class:bard", 8, level * 5)
        self.repository.set_class_archetype_keys(self.character, class_id, archetypes)
        return class_id

    def budget(self):
        return next(item for item in calculate_advancement_budgets(
            classes=self.repository.list_class_levels(self.character),
            class_lookup=class_entry, intelligence_modifier=0, race="", skill_ranks=0,
            favored_skill_points=0, feats=(), martial_talents=(), spells=(), traditions=(),
            adjustments={}, archetype_lookup=archetype_entry,
            archetype_keys_by_class_level=self.repository.list_class_archetype_keys(self.character),
        ) if item.key == "talents")

    def test_one_talent_per_group_not_per_spell_or_later_spell_level(self):
        definition = class_entry("bard")
        for name, first in (("animal-speaker", 1), ("brazen-deceiver", 2),
                            ("flame-dancer", 8), ("flamesinger", 4),
                            ("magician", 2), ("mute-musician", 2)):
            archetypes = [archetype_entry(SPHERE), archetype_entry(PREFIX + name)]
            with self.subTest(name=name):
                self.assertEqual((), sphere_bonus_spell_conversions(definition, archetypes, first - 1))
                self.assertEqual(1, len(sphere_bonus_spell_conversions(definition, archetypes, first)))
                self.assertEqual(1, len(sphere_bonus_spell_conversions(definition, archetypes, 20)))
                self.assertEqual((), sphere_bonus_spell_conversions(definition, archetypes[1:], 20))

    def test_conversion_reaches_budget_and_removes_with_archetype(self):
        class_id = self.add_bard(8, (SPHERE, PREFIX + "flame-dancer"))
        converted = self.budget()
        self.assertIn("Fan the Flames", converted.explanation)
        self.repository.set_class_archetype_keys(self.character, class_id, (SPHERE,))
        self.assertEqual(self.budget().total + 1, converted.total)

    def test_shared_conversion_handles_other_spontaneous_classes(self):
        cases = (("bloodrager", "sphere-bloodrager", "ancestral-harbinger", 5),
                 ("bloodrager", "sphere-bloodrager", "greenrager", 6),
                 ("bloodrager", "sphere-bloodrager", "urban-bloodrager", 7),
                 ("spiritualist", "psychomancer", "fated-guide", 1))
        for family, sphere, bonus, level in cases:
            with self.subTest(family=family, bonus=bonus):
                definition = class_entry(family)
                archetypes = [archetype_entry(f"spheres-archetype:pathfinder-class:{family}:{sphere}"),
                              archetype_entry(f"pathfinder-archetype:pathfinder-class:{family}:{bonus}")]
                self.assertEqual(1, len(sphere_bonus_spell_conversions(definition, archetypes, level)))
                self.assertEqual((), sphere_bonus_spell_conversions(
                    {**definition, "casting": {"type": "prepared"}}, archetypes, level))

    def test_list_additions_and_replacement_spells_do_not_award_talents(self):
        definition = class_entry("bard")
        for name in ("arrowsong-minstrel", "fortune-teller"):
            self.assertEqual((), sphere_bonus_spell_conversions(
                definition, [archetype_entry(SPHERE), archetype_entry(PREFIX + name)], 20))
        self.add_bard(7, (SPHERE, PREFIX + "voice-of-the-wild"))
        self.assertFalse(any(slot.key.startswith("voice-wild") for slot in
                             resolve_class_choice_slots(self.repository, self.character)))

    def test_conversion_suppresses_stale_spell_choices_and_owned_grants_only(self):
        class_id = self.add_bard(7, (PREFIX + "voice-of-the-wild",))
        slot = next(slot for slot in resolve_class_choice_slots(self.repository, self.character)
                    if slot.key == "voice-wild-nature-magic-1")
        option = next(option for option in slot.options if option.name == "Entangle")
        self.repository.save_class_feature_selection(class_choice_selection_record(
            self.character, slot, (option.key,)))
        old_slots = resolve_class_choice_slots(self.repository, self.character)
        self.assertTrue(synchronize_class_granted_spells(self.repository, self.character))
        self.repository.set_class_archetype_keys(self.character, class_id,
                                                 (SPHERE, PREFIX + "voice-of-the-wild"))
        self.assertEqual((), resolve_class_granted_spells(self.repository, self.character, old_slots))
        self.assertTrue(synchronize_class_granted_spells(self.repository, self.character))
        self.assertFalse(self.repository.list_spells(self.character))
        self.assertTrue(self.repository.list_class_feature_selections(self.character))
        self.repository.set_class_archetype_keys(self.character, class_id,
                                                 (PREFIX + "voice-of-the-wild",))
        self.assertTrue(synchronize_class_granted_spells(self.repository, self.character))
        self.assertEqual("Entangle", self.repository.list_spells(self.character)[0].name)

    def test_versatile_performance_requires_each_earned_choice(self):
        self.add_bard(18)
        choice = next(slot for slot in resolve_class_choice_slots(self.repository, self.character)
                      if slot.key == "bard-versatile-performance")
        self.assertEqual((5, 5), (choice.minimum, choice.maximum))

    def test_heroics_dodge_applies_to_touch_not_flat_footed(self):
        class_id = self.add_bard(15)
        self.repository.save_class_feature_state(ClassFeatureState(
            self.character, class_id, "bardic_performance", 10,
            active=True, choices_json=json.dumps(["Inspire Heroics"])))
        calculator = CharacterCalculationService(self.repository, self.character)
        self.assertEqual(4, calculator.automatic_total("armor_class"))
        self.assertEqual(4, calculator.automatic_total("touch_ac"))
        self.assertEqual(0, calculator.automatic_total("flat_footed_ac"))

    def test_ineligible_saved_performance_gives_no_bonus(self):
        class_id = self.add_bard(1)
        for name in ("Inspire Heroics", "inspire heroics"):
            self.repository.save_class_feature_state(ClassFeatureState(
                self.character, class_id, "bardic_performance", 10,
                active=True, choices_json=json.dumps([name])))
            self.assertEqual(0, CharacterCalculationService(
                self.repository, self.character).automatic_total("armor_class"))

    def test_well_versed_does_not_have_spendable_uses(self):
        self.add_bard(2)
        resource = next(resource for module in resolve_class_feature_modules(
            self.repository, self.character) for resource in module.resources
                        if resource.key == "well_versed")
        self.assertFalse(resource.tracks_uses)

    def test_lore_master_take_ten_requires_knowledge_ranks_and_retained_feature(self):
        class_id = self.add_bard(5)
        self.repository.update_skill_state(self.character, SkillState("knowledge_arcana", 1, True))
        calculator = CharacterCalculationService(self.repository, self.character)
        self.assertTrue(calculator.skill_take_ten_allowed("knowledge_arcana"))
        self.assertFalse(calculator.skill_take_ten_allowed("knowledge_history"))
        self.assertFalse(calculator.skill_take_ten_allowed("perform"))
        self.assertTrue(calculator.skill_result("knowledge_history").usable)
        self.assertFalse(calculator.skill_result("disable_device").usable)
        self.repository.set_class_archetype_keys(self.character, class_id,
                                                 (PREFIX + "arcane-duelist",))
        self.assertFalse(CharacterCalculationService(self.repository, self.character)
                         .skill_take_ten_allowed("knowledge_arcana"))


if __name__ == "__main__":
    unittest.main()
