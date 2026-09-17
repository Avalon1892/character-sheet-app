from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.class_power_rules import resolve_class_power_sets
from app.class_modifications import resolve_class_profile
from app.content import class_entry, archetype_entry, archetype_entries
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.recovery import FullRestEngine
from app.services.character_calculations import CharacterCalculationService


class CrimsonMountebankReaperTests(unittest.TestCase):
    def test_generator_can_limit_work_to_selected_class_families(self):
        from tools.build_target_class_packages import build
        output = Path(self.temp.name) / "generated"
        generated = build(output, ("crimson-dancer",))
        self.assertEqual(["crimson-dancer.json"], [p.name for p in generated])
        self.assertEqual(["crimson-dancer.json"], [p.name for p in output.iterdir()])
        with self.assertRaises(ValueError):
            build(output, ("not-a-class",))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.temp.name) / "characters.db")

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def character(self, family, level=20, archetype=""):
        entry = class_entry("spheres-class:" + family)
        character = self.repo.create_character(family, "Spheres")
        class_id = self.repo.add_class_level(character, entry["name"], level,
            entry["bab"], entry["fort"], entry["reflex"], entry["will"],
            entry["key"], entry["hit_die"], level * 6)
        self.repo.update_ability_score(character, "charisma", 20)
        if archetype:
            self.repo.set_class_archetype_keys(character, class_id,
                (f"spheres-archetype:spheres-class:{family}:{archetype}",))
        return character, class_id

    def resources(self, character):
        return {r.key: r for m in resolve_class_feature_modules(self.repo, character,
            {"charisma": 5, "intelligence": 2, "wisdom": 3, "casting": 5}) for r in m.resources}

    def slots(self, character):
        return {s.key: s for s in resolve_class_choice_slots(self.repo, character)}

    def test_crimson_choices_have_rules_and_level_gated_arts(self):
        c, _ = self.character("crimson-dancer", 3)
        slots = self.slots(c)
        self.assertEqual(2, len(slots["crimson-path"].options))
        self.assertTrue(all(len(o.granted_features) == 7 for o in slots["crimson-path"].options))
        self.assertTrue(all(o.minimum_level <= 3 for o in slots["hemolytic-arts"].options))
        self.assertFalse(any("Blood Pool" in o.name for o in slots["hemolytic-arts"].options))
        self.assertTrue(all(o.description for o in slots["hemolytic-arts"].options))

    def test_vitae_starts_empty_and_rest_empties_instead_of_filling(self):
        c, class_id = self.character("crimson-dancer")
        resources = self.resources(c)
        self.assertEqual((25, 0, 0), (resources["vitae"].maximum, resources["vitae"].current, resources["vitae"].recovery_value))
        self.repo.save_class_feature_state(ClassFeatureState(c, class_id, "vitae", 12))
        FullRestEngine(self.repo, c).perform()
        self.assertEqual(0, self.resources(c)["vitae"].current)

    def test_mountebank_mark_and_social_talents_are_available(self):
        c, class_id = self.character("mountebank")
        resources = self.resources(c)
        self.assertEqual(5, resources["thiefs_mark_bonus"].maximum)
        powers = resolve_class_power_sets(self.repo, c)
        self.assertTrue(next(p for p in powers if p.key == "mountebank-social-talents").options)
        before = CharacterCalculationService(self.repo, c).automatic_total("attack")
        self.repo.save_class_feature_state(ClassFeatureState(c, class_id, "thiefs_mark", 1, active=True))
        self.assertEqual(before + 5, CharacterCalculationService(self.repo, c).automatic_total("attack"))

    def test_reaper_cult_and_technique_descriptions_are_populated(self):
        c, _ = self.character("reaper")
        slots = self.slots(c)
        self.assertEqual(10, len(slots["reaper-cult"].options))
        self.assertTrue(all(len(o.granted_features) == 5 for o in slots["reaper-cult"].options))
        self.assertEqual(28, len(slots["reaper-techniques"].options))
        self.assertEqual(10, slots["reaper-techniques"].maximum)
        self.assertTrue(all(o.description for o in slots["reaper-techniques"].options))

    def test_noncasting_reaper_archetypes_have_only_martial_progression(self):
        for archetype in ("chem-dog", "hunt-master"):
            with self.subTest(archetype=archetype):
                c, _ = self.character("reaper", archetype=archetype)
                profile = resolve_class_profile(class_entry("spheres-class:reaper"),
                    (archetype_entry(f"spheres-archetype:spheres-class:reaper:{archetype}"),))
                self.assertFalse(profile.casting.get("sphere_progression"))
                self.assertEqual(["martial"], profile.advancement["talent_kinds"])
                self.assertNotIn("prey_casting_bonus", self.resources(c))
                slot = self.slots(c)["reaper-casting-ability"]
                choice = next(o for o in slot.options if o.name == "Intelligence")
                self.repo.save_class_feature_selection(class_choice_selection_record(c, slot, (choice.key,)))
                pool = self.resources(c)[archetype.replace("-", "_") + "_points"]
                self.assertEqual(22, pool.maximum)
                self.assertTrue(all(s.options for s in self.slots(c).values()))

    def test_embedded_crimson_archetypes_and_replacements(self):
        self.assertEqual({"Crimson Tempest", "Primeval"}, {a["name"] for a in archetype_entries("spheres-class:crimson-dancer")})
        c, _ = self.character("crimson-dancer", archetype="primeval")
        self.assertNotIn("voracity", self.resources(c))
        self.assertEqual("Rot Points on Current Target", self.resources(c)["bloodletting"].name)
        self.assertEqual(["Path of the Lost Ravager"], [o.name for o in self.slots(c)["crimson-path"].options])

    def test_commanded_creature_bonuses_do_not_modify_owners_attack(self):
        c, _ = self.character("mountebank", archetype="mental-manipulator")
        resources = self.resources(c)
        self.assertEqual(5, resources["controlling_attack_bonus"].maximum)
        self.assertEqual(10, resources["controlling_damage_bonus"].maximum)
        self.assertFalse(any("Controlling Enhancement" in str(x) for values in
            CharacterCalculationService(self.repo, c).automatic_modifier_map().values()
            for x in values))


if __name__ == "__main__":
    unittest.main()
