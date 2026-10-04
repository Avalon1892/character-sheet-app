from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import (
    class_choice_reference_values,
    class_choice_selection_record,
    projected_class_choice_features,
    resolve_class_choice_slots,
)
from app.database import CharacterRepository
from app.services.character_calculations import CharacterCalculationService
from app.animal_companion_rules import resolve_companion_grant


class ClassChoiceRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character = self.repository.create_character("Choices", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def add_class(self, name: str, preset: str, level: int = 1) -> int:
        return self.repository.add_class_level(
            self.character, name, level, "1/2", "Poor", "Poor", "Good", preset, 8, 8
        )

    def test_cleric_domains_are_a_two_choice_catalog_slot(self) -> None:
        self.add_class("Cleric", "pathfinder-class:cleric")
        slot = next(item for item in resolve_class_choice_slots(self.repository, self.character) if item.key == "cleric-domains")
        self.assertEqual((2, 2), (slot.minimum, slot.maximum))
        names = {option.name for option in slot.options}
        self.assertIn("Fire Domain", names)
        self.assertIn("Ash Subdomain", names)

    def test_machinehead_custom_graft_repeatability_uses_real_prowess_slots(self):
        class_id=self.add_class("Armiger","spheres-class:armiger",6)
        self.repository.set_class_archetype_keys(self.character,class_id,("spheres-archetype:spheres-class:armiger:machinehead",))
        slot=next(s for s in resolve_class_choice_slots(self.repository,self.character) if s.key=="machinehead-prowesses")
        self.assertTrue(all(s.maximum==0 for s in resolve_class_choice_slots(self.repository,self.character) if s.key=="armiger-prowesses"))
        self.assertEqual(2,slot.maximum)
        custom=next(o for o in slot.options if o.name=="Custom Graft")
        self.assertTrue(custom.repeatable)
        self.assertTrue(any(o.name=="Armored Armiger" for o in slot.options))
        record=class_choice_selection_record(self.character,slot,(custom.key,custom.key,custom.key))
        self.repository.save_class_feature_selection(record)
        restored=next(s for s in resolve_class_choice_slots(self.repository,self.character) if s.key==slot.key)
        self.assertEqual((custom.key,custom.key),restored.selected_keys)
        ordinary=next(o for o in slot.options if o.name=="Armored Armiger")
        record=class_choice_selection_record(self.character,slot,(ordinary.key,ordinary.key,custom.key))
        self.repository.save_class_feature_selection(record)
        restored=next(s for s in resolve_class_choice_slots(self.repository,self.character) if s.key==slot.key)
        self.assertEqual(2,len(restored.selected_keys))

    def test_inquisitor_can_choose_domain_or_inquisition(self) -> None:
        self.add_class("Inquisitor", "pathfinder-class:inquisitor")
        slot = next(item for item in resolve_class_choice_slots(self.repository, self.character) if item.key == "inquisitor-domain")
        families = {option.family for option in slot.options}
        self.assertEqual({"domain", "inquisition"}, families)
        fire = next(option for option in slot.options if option.name == "Fire Domain")
        self.assertIn("does not grant domain spells", fire.description)
        self.assertNotIn("Burning Hands", fire.description)
        self.assertIn("does not gain its domain spells", slot.description)

    def test_abolisher_alters_domain_choice_to_its_seven_legal_domains(self) -> None:
        class_id = self.add_class("Inquisitor", "pathfinder-class:inquisitor")
        self.repository.set_class_archetype_keys(
            self.character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:abolisher",),
        )
        slot = next(
            item for item in resolve_class_choice_slots(self.repository, self.character)
            if item.key == "inquisitor-domain"
        )
        self.assertEqual(
            {"Air Domain", "Animal Domain", "Earth Domain", "Fire Domain", "Plant Domain", "Water Domain", "Weather Domain"},
            {option.name for option in slot.options},
        )

    def test_wizard_school_drives_opposition_and_universalist_removes_it(self) -> None:
        self.add_class("Wizard", "pathfinder-class:wizard")
        slots = {item.key: item for item in resolve_class_choice_slots(self.repository, self.character)}
        self.assertIn("arcane-school", slots)
        self.assertNotIn("opposition-schools", slots)
        primary = slots["arcane-school"]
        universalist = next(option for option in primary.options if option.name == "Universalist School")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, primary, (universalist.key,))
        )
        keys = {item.key for item in resolve_class_choice_slots(self.repository, self.character)}
        self.assertNotIn("opposition-schools", keys)

        specialist = next(option for option in primary.options if option.name == "Evocation School")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, primary, (specialist.key,))
        )
        opposition = next(item for item in resolve_class_choice_slots(self.repository, self.character) if item.key == "opposition-schools")
        self.assertEqual((2, 2), (opposition.minimum, opposition.maximum))
        self.assertNotIn(specialist.key, {option.key for option in opposition.options})

    def test_bonds_are_feature_specific_and_nature_domain_is_conditional(self) -> None:
        self.add_class("Druid", "pathfinder-class:druid")
        slots = {item.key: item for item in resolve_class_choice_slots(self.repository, self.character)}
        self.assertIn("nature-bond", slots)
        self.assertNotIn("nature-domain", slots)
        bond = slots["nature-bond"]
        domain = next(option for option in bond.options if option.name == "Druid Domain")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, bond, (domain.key,))
        )
        slots = {item.key: item for item in resolve_class_choice_slots(self.repository, self.character)}
        self.assertIn("nature-domain", slots)
        names = {option.name for option in slots["nature-domain"].options}
        self.assertIn("Animal Domain", names)
        self.assertNotIn("Artifice Domain", names)

    def test_selected_bond_form_drives_animal_companion_availability(self) -> None:
        self.add_class("Ranger", "pathfinder-class:ranger", 7)
        slot = next(
            item for item in resolve_class_choice_slots(self.repository, self.character)
            if item.key == "hunters-bond"
        )
        companion = next(
            option for option in slot.options if option.name == "Animal Companion"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, slot, (companion.key,))
        )
        grant = resolve_companion_grant(
            self.repository.list_class_levels(self.character),
            {},
            (),
            self.repository.list_skill_states(self.character),
            self.repository.list_class_feature_selections(self.character),
        )
        self.assertTrue(grant.available)
        self.assertEqual(4, grant.effective_level)

    def test_multi_choice_round_trip_uses_one_backward_compatible_record(self) -> None:
        self.add_class("Cleric", "pathfinder-class:cleric")
        slot = next(item for item in resolve_class_choice_slots(self.repository, self.character) if item.key == "cleric-domains")
        selected = tuple(option.key for option in slot.options[:2])
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, slot, selected)
        )
        resolved = next(item for item in resolve_class_choice_slots(self.repository, self.character) if item.key == "cleric-domains")
        self.assertEqual(selected, resolved.selected_keys)
        self.assertEqual(1, len(self.repository.list_class_feature_selections(self.character)))

    def test_domain_choice_projects_granted_powers_and_formula_references(self) -> None:
        self.add_class("Cleric", "pathfinder-class:cleric", 8)
        slot = next(
            item for item in resolve_class_choice_slots(self.repository, self.character)
            if item.key == "cleric-domains"
        )
        selected = tuple(
            option.key
            for option in slot.options
            if option.name in {"Air Domain", "Fire Domain"}
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, slot, selected)
        )
        resolved = resolve_class_choice_slots(self.repository, self.character)
        names = {feature[2] for feature in projected_class_choice_features(resolved)}
        self.assertIn("Lightning Arc", names)
        references = class_choice_reference_values(resolved)
        prefix = "class_choice.cleric.cleric_domains"
        self.assertEqual(2, references[f"{prefix}.count"])
        self.assertTrue(references[f"{prefix}.fire_domain"])
        formula_context = CharacterCalculationService(
            self.repository, self.character
        ).formula_context()
        self.assertEqual(
            2,
            formula_context.evaluate(
                "IF(class_choice.cleric.cleric_domains.fire_domain, "
                "class_choice.cleric.cleric_domains.count, 0)"
            ),
        )


if __name__ == "__main__":
    unittest.main()
