from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.class_feature_systems import resolve_class_feature_modules
from app.class_granted_spells import synchronize_class_granted_spells
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.database import CharacterRepository
from app.prepared_spell_rules import prepared_spell_slots
from app.services.character_calculations import CharacterCalculationService
from app.traditional_spellcasting import prepared_caster_capacities


class WizardClericMonkPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "three-classes.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self, name: str, key: str, level: int, *, hit_die: int = 8,
        bab: str = "3/4", fort: str = "Good", reflex: str = "Poor",
        will: str = "Good",
    ) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, bab, fort, reflex, will,
            key, hit_die, max(hit_die, level * max(1, hit_die // 2)),
        )
        return character, class_id

    def test_all_three_base_packages_are_registered(self) -> None:
        self.assertEqual("wizard", class_package("pathfinder-class:wizard").key)
        self.assertEqual("cleric", class_package("pathfinder-class:cleric").key)
        self.assertEqual("monk", class_package("pathfinder-class:monk").key)

    def test_wizard_bonded_object_tracker_is_choice_aware(self) -> None:
        character, _class_id = self.add_class(
            "Wizard", "pathfinder-class:wizard", 7,
            hit_die=6, bab="1/2", fort="Poor", reflex="Poor",
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(
            self.repository, character
        )}
        bond = slots["arcane-bond"]
        familiar = next(option for option in bond.options if option.name == "Familiar")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, bond, (familiar.key,))
        )
        self.assertNotIn(
            "bonded_object_spell",
            {
                resource.key
                for module in resolve_class_feature_modules(self.repository, character)
                for resource in module.resources
            },
        )

        bonded_object = next(
            option for option in bond.options if option.name == "Bonded Object"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, bond, (bonded_object.key,))
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(1, resources["bonded_object_spell"].maximum)

    def test_elemental_wizard_uses_one_elemental_opposition_school(self) -> None:
        character, _class_id = self.add_class(
            "Wizard", "pathfinder-class:wizard", 5,
            hit_die=6, bab="1/2", fort="Poor", reflex="Poor",
        )
        primary = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "arcane-school"
        )
        aether = next(
            option for option in primary.options
            if option.name == "Aether Elemental School"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, primary, (aether.key,))
        )
        opposition = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "opposition-schools"
        )
        self.assertEqual((1, 1), (opposition.minimum, opposition.maximum))
        self.assertTrue(opposition.options)
        self.assertTrue(all(
            "elemental" in option.category.casefold()
            for option in opposition.options
        ))

    def test_cleric_domains_grant_level_gated_domain_spells(self) -> None:
        character, _class_id = self.add_class(
            "Cleric", "pathfinder-class:cleric", 7
        )
        slot = next(
            item for item in resolve_class_choice_slots(self.repository, character)
            if item.key == "cleric-domains"
        )
        selected = tuple(
            option.key for option in slot.options
            if option.name in {"Air Domain", "Fire Domain"}
        )
        self.assertEqual(2, len(selected))
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, slot, selected)
        )
        self.assertTrue(synchronize_class_granted_spells(self.repository, character))
        granted = {
            spell.name for spell in self.repository.list_spells(character)
            if spell.catalog_category == "Class Granted"
        }
        self.assertTrue({"Burning Hands", "Fireball"} <= granted)

    def test_selected_school_and_domain_powers_gain_live_trackers(self) -> None:
        wizard, _wizard_class = self.add_class(
            "Wizard", "pathfinder-class:wizard", 5,
            hit_die=6, bab="1/2", fort="Poor", reflex="Poor",
        )
        self.repository.update_ability_score(wizard, "intelligence", 18)
        school = next(
            slot for slot in resolve_class_choice_slots(self.repository, wizard)
            if slot.key == "arcane-school"
        )
        abjuration = next(
            option for option in school.options if option.name == "Abjuration School"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(wizard, school, (abjuration.key,))
        )
        wizard_resources = {
            resource.name: resource
            for module in resolve_class_feature_modules(self.repository, wizard)
            for resource in module.resources
        }
        self.assertEqual(7, wizard_resources["Protective Ward"].maximum)

        cleric, _cleric_class = self.add_class(
            "Cleric", "pathfinder-class:cleric", 7
        )
        self.repository.update_ability_score(cleric, "wisdom", 18)
        domains = next(
            slot for slot in resolve_class_choice_slots(self.repository, cleric)
            if slot.key == "cleric-domains"
        )
        fire = next(option for option in domains.options if option.name == "Fire Domain")
        air = next(option for option in domains.options if option.name == "Air Domain")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(cleric, domains, (fire.key, air.key))
        )
        cleric_resources = {
            resource.name: resource
            for module in resolve_class_feature_modules(self.repository, cleric)
            for resource in module.resources
        }
        self.assertEqual(7, cleric_resources["Fire Bolt"].maximum)

    def test_cleric_domain_slots_and_cloistered_reduction_are_composed(self) -> None:
        cleric, class_id = self.add_class(
            "Cloistered Cleric", "pathfinder-class:cleric", 7
        )
        self.repository.update_ability_score(cleric, "wisdom", 18)
        self.repository.set_class_archetype_keys(
            cleric,
            class_id,
            ("pathfinder-archetype:pathfinder-class:cleric:cloistered-cleric",),
        )
        domains = next(
            slot for slot in resolve_class_choice_slots(self.repository, cleric)
            if slot.key == "cleric-domains"
        )
        self.assertEqual((1, 1), (domains.minimum, domains.maximum))
        fire = next(option for option in domains.options if option.name == "Fire Domain")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(cleric, domains, (fire.key,))
        )
        capacity = prepared_caster_capacities(self.repository, cleric)[0]
        self.assertEqual(
            prepared_spell_slots(
                "pathfinder-class:cleric", "Cloistered Cleric", 7, "high", 4,
                daily_slot_adjustment=-1,
                bonus_slot_per_spell_level=1,
            ),
            capacity.slots,
        )

    def test_sphere_cleric_does_not_restore_traditional_domain_spells(self) -> None:
        character, class_id = self.add_class(
            "Sphere Cleric", "pathfinder-class:cleric", 7
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("spheres-archetype:pathfinder-class:cleric:sphere-cleric",),
        )
        domains = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "cleric-domains"
        )
        selected = tuple(option.key for option in domains.options[:2])
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, domains, selected)
        )
        synchronize_class_granted_spells(self.repository, character)
        self.assertFalse([
            spell for spell in self.repository.list_spells(character)
            if spell.catalog_category == "Class Granted"
        ])

    def test_wizard_archetype_systems_reuse_shared_modules(self) -> None:
        bomber, bomber_class = self.add_class(
            "Arcane Bomber", "pathfinder-class:wizard", 5,
            hit_die=6, bab="1/2", fort="Poor", reflex="Poor",
        )
        self.repository.update_ability_score(bomber, "intelligence", 18)
        self.repository.set_class_archetype_keys(
            bomber,
            bomber_class,
            ("pathfinder-archetype:pathfinder-class:wizard:arcane-bomber",),
        )
        bomb = next(
            attack for attack in CharacterCalculationService(
                self.repository, bomber
            ).attacks()
            if attack.name == "Bomb"
        )
        self.assertEqual("3d6", bomb.damage_dice)
        self.assertIn("fire", bomb.notes.casefold())

        exploiter, exploiter_class = self.add_class(
            "Exploiter Wizard", "pathfinder-class:wizard", 9,
            hit_die=6, bab="1/2", fort="Poor", reflex="Poor",
        )
        self.repository.update_ability_score(exploiter, "intelligence", 18)
        self.repository.set_class_archetype_keys(
            exploiter,
            exploiter_class,
            ("pathfinder-archetype:pathfinder-class:wizard:exploiter-wizard",),
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, exploiter)
            for resource in module.resources
        }
        self.assertEqual(12, resources["arcane_reservoir"].maximum)
        self.assertIn(
            "exploiter-wizard-exploits",
            {power_set.key for power_set in resolve_class_power_sets(
                self.repository, exploiter
            )},
        )

    def test_scaled_fist_ki_uses_charisma_and_sphere_wizard_has_specialization(self) -> None:
        monk, monk_class = self.add_class(
            "Scaled Fist", "pathfinder-class:monk", 8
        )
        self.repository.update_ability_score(monk, "wisdom", 10)
        self.repository.update_ability_score(monk, "charisma", 18)
        self.repository.set_class_archetype_keys(
            monk,
            monk_class,
            ("pathfinder-archetype:pathfinder-class:monk:scaled-fist",),
        )
        ki = next(
            resource
            for module in resolve_class_feature_modules(self.repository, monk)
            for resource in module.resources
            if resource.key == "ki_pool"
        )
        self.assertEqual(8, ki.maximum)

        wizard, wizard_class = self.add_class(
            "Sphere Wizard", "pathfinder-class:wizard", 5,
            hit_die=6, bab="1/2", fort="Poor", reflex="Poor",
        )
        self.repository.set_class_archetype_keys(
            wizard,
            wizard_class,
            ("spheres-archetype:pathfinder-class:wizard:sphere-wizard",),
        )
        specialization = next(
            slot for slot in resolve_class_choice_slots(self.repository, wizard)
            if slot.key == "sphere-wizard-specialization"
        )
        self.assertEqual((1, 1), (specialization.minimum, specialization.maximum))
        self.assertIn("Weather", {option.name for option in specialization.options})

    def test_monk_live_bonuses_and_resources_respect_armor(self) -> None:
        character, _class_id = self.add_class(
            "Monk", "pathfinder-class:monk", 12
        )
        self.repository.update_ability_score(character, "wisdom", 18)
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(10, resources["ki_pool"].maximum)
        self.assertEqual(12, resources["stunning_fist"].maximum)
        self.assertIn("high_jump", resources)

        unarmored = CharacterCalculationService(self.repository, character)
        self.assertEqual(7, unarmored.automatic_total("armor_class"))
        self.assertEqual(40, unarmored.automatic_total("land_speed"))
        self.assertEqual(3, unarmored.automatic_total("cmb"))

        self.repository.add_equipment(
            character, "Test armor", "Armor", 1, 1, True, 1, "armor",
            None, "", slot="Armor", state="armor",
        )
        armored = CharacterCalculationService(self.repository, character)
        self.assertEqual(0, armored.automatic_total("armor_class"))
        self.assertEqual(0, armored.automatic_total("land_speed"))
        self.assertEqual(3, armored.automatic_total("cmb"))


if __name__ == "__main__":
    unittest.main()
