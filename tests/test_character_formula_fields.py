from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from app.character_formulas import CharacterFormulaContext
from app.database import CharacterRepository
from app.models import (
    CastingProfile,
    CharacterDetails,
    HitPoints,
    MartialFocus,
    ProdigySequence,
    RaceTraitChoice,
    SkillState,
    SphereStatistic,
)
from app.services.character_calculations import CharacterCalculationService
from app.transfer import export_character, import_character
from app.ui.dialogs import AttackDialog, CustomTrackerDialog


class CharacterFormulaFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "formulas.db")
        self.character_id = self.repository.create_character("Formula Fighter", "Pathfinder 1e")
        self.repository.add_class_level(
            self.character_id,
            "Fighter",
            6,
            "Full",
            "Good",
            "Poor",
            "Poor",
            preset_key="pathfinder-class:fighter",
            hit_die=10,
            hp_gained=46,
        )
        self.repository.update_skill_state(
            self.character_id,
            SkillState("acrobatics", ranks=5),
        )
        self.feat_id = self.repository.add_feat(
            self.character_id,
            "Power Attack",
            activation="toggle",
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _service(self) -> CharacterCalculationService:
        return CharacterCalculationService(self.repository, self.character_id)

    def test_formula_namespace_exposes_bab_skills_focus_and_feat_boole(self) -> None:
        context = CharacterFormulaContext(self._service())
        self.assertEqual(6, context.evaluate("bab"))
        self.assertEqual(5, context.evaluate("skillranks.acrobatics"))
        self.assertEqual(5, context.evaluate("skills.acrobatics.ranks"))
        self.assertEqual(1, context.evaluate("martial_focus"))
        self.assertEqual(1, context.evaluate("feats.power_attack"))
        self.assertEqual(0, context.evaluate("feats.piranha_strike"))
        suggestions = {item.reference: item for item in context.suggestions()}
        self.assertEqual("6", suggestions["bab"].value)
        self.assertEqual("5", suggestions["skillranks.acrobatics"].value)
        self.assertEqual("Yes", suggestions["feats.power_attack"].value)
        self.assertIn("base attack bonus", suggestions["bab"].description)
        self.assertIn("floor()", suggestions)

    def test_formula_namespace_exposes_race_traits_senses_and_resistance(self) -> None:
        trait_key = "race-alt-trait:tiefling:scaled-skin"
        self.repository.update_character_details(CharacterDetails(
            self.character_id,
            race="Tiefling",
            race_key="tiefling",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=(RaceTraitChoice(trait_key, "energy", ("fire",)),),
        ))
        context = CharacterFormulaContext(self._service())
        self.assertEqual(1, context.evaluate("race.tiefling"))
        self.assertEqual(1, context.evaluate("race_trait.scaled_skin"))
        self.assertEqual(60, context.evaluate("sense.darkvision"))
        self.assertEqual(5, context.evaluate("resistance.fire"))
        self.assertEqual(0, context.evaluate("resistance.cold"))

    def test_racial_class_skill_choice_reaches_live_skill_calculation(self) -> None:
        trait_key = "race-alt-trait:human:fey-thoughts"
        self.repository.update_character_details(CharacterDetails(
            self.character_id,
            race="Human",
            race_key="human",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=(RaceTraitChoice(
                trait_key, "class_skills", ("use_magic_device", "perception")
            ),),
        ))
        self.repository.update_skill_state(
            self.character_id, SkillState("use_magic_device", ranks=1)
        )
        service = self._service()
        self.assertIn("use_magic_device", service.resolved_class_skills())
        self.assertEqual(4, service.skill_result("use_magic_device").total)

    def test_racial_natural_attack_is_live_and_not_persisted(self) -> None:
        self.repository.update_character_details(CharacterDetails(
            self.character_id,
            race="Half-Orc",
            race_key="half-orc",
            race_alternate_trait_keys=("race-alt-trait:half-orc:toothy",),
        ))
        self.assertEqual([], self.repository.list_attacks(self.character_id))
        attacks = self._service().attacks()
        self.assertEqual("Bite", attacks[0].name)
        self.assertEqual("1d4", attacks[0].damage_dice)
        self.assertLess(attacks[0].id, 0)

    def test_saved_attack_formula_recalculates_from_live_character_state(self) -> None:
        attack_id = self.repository.add_attack(
            self.character_id,
            "Formula strike",
            "Melee",
            "strength",
            0,
            "1d6",
            "strength",
            1.0,
            0,
            "20/x2",
            "",
        )
        expression = (
            "=skillranks.acrobatics + (2 if martial_focus else 0) "
            "+ (1 if feats.power_attack else 0)"
        )
        self.repository.set_numeric_formula(
            self.character_id, "attack", attack_id, "attack_bonus", expression
        )
        attack = self.repository.list_attacks(self.character_id)[0]
        resolved = self._service().resolve_attack_profile(attack)
        self.assertEqual(8, resolved.attack.attack_bonus)
        self.assertTrue(any("= 8" in source for source in resolved.sources))

        self.repository.update_martial_focus(
            MartialFocus(self.character_id, current=0, maximum=1)
        )
        self.repository.set_feat_enabled(self.character_id, self.feat_id, False)
        resolved = self._service().resolve_attack_profile(attack)
        self.assertEqual(5, resolved.attack.attack_bonus)

    def test_saved_formulas_feed_live_sheet_calculations(self) -> None:
        modifier_id = self.repository.add_modifier(
            self.character_id, "strength", "Formula enhancement", "enhancement", 1
        )
        feat_id = self.repository.add_feat(
            self.character_id, "Formula Reflex", "reflex", "untyped", 0
        )
        trait_id = self.repository.add_trait(
            self.character_id, "Formula Initiative", "initiative", "trait", 0
        )
        armor_id = self.repository.add_equipment(
            self.character_id,
            "Formula armor",
            "Armor",
            1,
            20.0,
            True,
            1,
            "armor",
            None,
            "",
            state="armor",
        )
        self.repository.update_casting_profile(
            CastingProfile(self.character_id, casting_class_levels=1, caster_level=1)
        )
        self.repository.update_sphere_statistic(
            SphereStatistic(self.character_id, "Warp", 0, 0, "")
        )
        self.repository.update_hit_points(
            HitPoints(self.character_id, maximum=10, current=10)
        )

        formulas = (
            ("modifier", modifier_id, "value", "=bab"),
            ("feat", feat_id, "value", "=floor(bab / 2)"),
            ("trait", trait_id, "value", "=2"),
            ("equipment", armor_id, "ac_bonus", "=bab"),
            ("skill", 1, "misc_bonus", "=bab"),
            ("casting", 0, "casting_class_levels", "=bab + 1"),
            ("casting", 0, "caster_level", "=bab"),
            ("sphere_stat", 0, "warp_cl", "=floor(bab / 2)"),
            ("sphere_stat", 0, "warp_dc", "=2"),
            ("hit_points", 0, "maximum", "=bab * 10"),
            ("martial_focus", 0, "maximum", "=floor(bab / 2)"),
        )
        for entity_type, entity_id, field_key, expression in formulas:
            self.repository.set_numeric_formula(
                self.character_id, entity_type, entity_id, field_key, expression
            )

        service = self._service()
        self.assertEqual(16, service.ability_result("strength").total)
        combat = service.combat_results()
        self.assertEqual(16, combat["ac"].total)
        self.assertEqual(11, service.skill_result("acrobatics").total)
        self.assertTrue(any(
            item.source == "Feat: Formula Reflex" and item.value == 3
            for item in combat["reflex"].contributions
        ))
        self.assertEqual(2, combat["initiative"].total)
        self.assertEqual(7, service.resolved_casting_profile().casting_class_levels)
        self.assertEqual(6, service.resolved_casting_profile().caster_level)
        sphere = service.resolved_sphere_statistic(
            self.repository.list_sphere_statistics(self.character_id)[0]
        )
        self.assertEqual((3, 2), (sphere.caster_level_bonus, sphere.dc_bonus))
        self.assertEqual(60, service.resolved_hit_points().maximum)
        self.assertEqual(3, service.resolved_martial_focus().maximum)

    def test_entity_formula_ids_remap_during_character_round_trip(self) -> None:
        modifier_id = self.repository.add_modifier(
            self.character_id, "initiative", "Formula modifier", "untyped", 0
        )
        equipment_id = self.repository.add_equipment(
            self.character_id, "Formula gear", "Gear", 1, 1.0, False,
            0, "untyped", None, "",
        )
        trait_id = self.repository.add_trait(
            self.character_id, "Formula trait", "initiative", "trait", 0
        )
        for entity_type, entity_id, field_key in (
            ("modifier", modifier_id, "value"),
            ("equipment", equipment_id, "weight"),
            ("feat", self.feat_id, "value"),
            ("trait", trait_id, "value"),
        ):
            self.repository.set_numeric_formula(
                self.character_id, entity_type, entity_id, field_key, "=bab"
            )

        export_path = Path(self.directory.name) / "all-formulas.character.json"
        export_character(self.repository, self.character_id, export_path)
        imported_id = import_character(self.repository, export_path)
        imported = self.repository.numeric_formulas(imported_id)
        imported_modifier = self.repository.list_modifiers(imported_id)[0]
        imported_equipment = self.repository.list_equipment(imported_id)[0]
        imported_feat = self.repository.list_feats(imported_id)[0]
        imported_trait = self.repository.list_traits(imported_id)[0]
        self.assertEqual(
            "=bab", imported[("modifier", int(imported_modifier.id), "value")]
        )
        self.assertEqual(
            "=bab", imported[("equipment", imported_equipment.id, "weight")]
        )
        self.assertEqual("=bab", imported[("feat", imported_feat.id, "value")])
        self.assertEqual("=bab", imported[("trait", imported_trait.id, "value")])

    def test_sphere_drawback_item_and_ampersand_references(self) -> None:
        self.repository.add_martial_talent(
            self.character_id,
            "Brute Sphere",
            "Brute",
            "Base Sphere",
            catalog_key="test:brute-base",
            catalog_category="Base Sphere",
        )
        self.repository.add_martial_talent(
            self.character_id,
            "Armed Combatant",
            "Brute",
            "Drawback",
            catalog_key="test:armed-combatant",
            catalog_category="Drawback",
        )
        self.repository.add_spell(
            self.character_id,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="test:warp-base",
            catalog_category="Base Sphere",
        )
        self.repository.add_spell(
            self.character_id,
            "Limited Warp",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="test:limited-warp",
            catalog_category="Drawback",
        )
        self.repository.add_equipment(
            self.character_id,
            "Belt of Giant Strength",
            "Gear",
            2,
            1.0,
            True,
            0,
            "untyped",
            None,
            "",
            slot="Belt",
            state="worn",
        )
        context = self._service().formula_context()
        self.assertEqual(1, context.evaluate("sphere.brute"))
        self.assertEqual(1, context.evaluate("sphere.warp"))
        self.assertEqual(1, context.evaluate("drawback.brute.armed_combatant"))
        self.assertEqual(1, context.evaluate("drawback.warp.limited_warp"))
        self.assertEqual(1, context.evaluate("item.belt_of_giant_strength"))
        self.assertEqual(1, context.evaluate("item.belt_of_giant_strength.equipped"))
        self.assertEqual(2, context.evaluate("item.belt_of_giant_strength.quantity"))
        self.assertEqual(0, context.evaluate("sphere.time"))
        self.assertEqual(0, context.evaluate("drawback.time.limited_time"))
        self.assertEqual(0, context.evaluate("item.missing_item.owned"))
        self.assertEqual(0, context.evaluate("item.missing_item.quantity"))
        self.assertEqual(
            12,
            context.evaluate(
                "IF(martial_focus & sphere.brute & "
                "drawback.brute.armed_combatant & "
                "item.belt_of_giant_strength.equipped, bab * 2, 0)"
            ),
        )
        suggestions = {item.reference: item for item in context.suggestions()}
        self.assertEqual("Yes", suggestions["sphere.brute"].value)
        self.assertEqual(
            "Yes", suggestions["drawback.warp.limited_warp"].value
        )
        self.assertEqual(
            "2", suggestions["item.belt_of_giant_strength.quantity"].value
        )

    def test_martial_and_magic_talents_have_generic_and_scoped_references(self) -> None:
        self.repository.add_martial_talent(
            self.character_id,
            "Brutal Strike",
            "Brute",
            "Talent",
            catalog_key="test:brutal-strike",
            catalog_category="Talent",
        )
        self.repository.add_spell(
            self.character_id,
            "Create Gap",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="test:create-gap",
            catalog_category="Talent",
        )
        context = self._service().formula_context()
        self.assertEqual(1, context.evaluate("talent.brutal_strike"))
        self.assertEqual(1, context.evaluate("talent.brute.brutal_strike"))
        self.assertEqual(1, context.evaluate("martial_talent.brute.brutal_strike"))
        self.assertEqual(1, context.evaluate("talent.create_gap"))
        self.assertEqual(1, context.evaluate("magic_talent.warp.create_gap"))
        self.assertEqual(0, context.evaluate("talent.unknown_talent"))
        suggestions = {item.reference: item for item in context.suggestions()}
        self.assertEqual("Yes", suggestions["talent.brutal_strike"].value)
        self.assertEqual("Yes", suggestions["magic_talent.warp.create_gap"].value)

    def test_prodigy_sequence_and_imbue_references_are_live(self) -> None:
        self.repository.add_class_level(
            self.character_id,
            "Prodigy",
            5,
            "3/4",
            "Poor",
            "Good",
            "Good",
            preset_key="prodigy",
            hit_die=8,
            hp_gained=30,
        )
        self.repository.update_prodigy_sequence(
            ProdigySequence(
                self.character_id, True, 3, 5, "warp_step_between"
            )
        )
        context = self._service().formula_context()
        self.assertEqual(1, context.evaluate("prodigy.sequence.active"))
        self.assertEqual(3, context.evaluate("sequence.links"))
        self.assertEqual(2, context.evaluate("prodigy.sequence.remaining"))
        self.assertEqual(1, context.evaluate("prodigy.imbue.warp_step_between.active"))
        self.assertEqual(20, context.evaluate("prodigy.imbue.teleport_distance"))
        self.assertEqual(20, context.evaluate("prodigy.imbue.value"))
        self.assertGreater(
            context.evaluate("prodigy.sequence.effective_caster_level"), 0
        )

        self.repository.update_prodigy_sequence(
            ProdigySequence(
                self.character_id, False, 0, 5, "warp_step_between"
            )
        )
        inactive = self._service().formula_context()
        self.assertEqual(0, inactive.evaluate("prodigy.imbue.warp_step_between.active"))
        self.assertEqual(1, inactive.evaluate("prodigy.imbue.warp_step_between.selected"))
        self.assertEqual(0, inactive.evaluate("prodigy.imbue.teleport_distance"))

    def test_attack_formulas_round_trip_and_remap_attack_ids(self) -> None:
        attack_id = self.repository.add_attack(
            self.character_id, "Exported", "Ranged", "dexterity", 0,
            "1d8", None, 0.0, 0, "20/x3", "",
        )
        self.repository.set_numeric_formula(
            self.character_id, "attack", attack_id, "damage_bonus", "=floor(bab / 2)"
        )
        export_path = Path(self.directory.name) / "formula.character.json"
        export_character(self.repository, self.character_id, export_path)
        imported_id = import_character(self.repository, export_path)
        imported_attack = self.repository.list_attacks(imported_id)[0]
        formulas = self.repository.numeric_formulas(imported_id, "attack", imported_attack.id)
        self.assertEqual(
            "=floor(bab / 2)",
            formulas[("attack", imported_attack.id, "damage_bonus")],
        )

    def test_attack_editor_accepts_literals_and_live_formulas(self) -> None:
        context = self._service().formula_context()
        dialog = AttackDialog(
            formula_evaluator=context.evaluate,
            formula_suggestions=context.suggestions,
        )
        dialog.name.setText("Configured attack")
        dialog.attack_bonus.set_expression("=bab + skillranks.acrobatics")
        dialog.damage_bonus.set_expression("=2 if martial_focus else 0")
        self.assertEqual(11, dialog.values["attack_bonus"])
        self.assertEqual(2, dialog.values["damage_bonus"])
        self.assertEqual(
            {
                "attack_bonus": "=bab + skillranks.acrobatics",
                "damage_bonus": "=2 if martial_focus else 0",
            },
            dialog.numeric_formulas,
        )
        self.assertGreaterEqual(dialog.width(), 850)
        dialog.close()

    def test_formula_number_shows_only_result_until_selected(self) -> None:
        context = self._service().formula_context()
        dialog = AttackDialog(
            formula_evaluator=context.evaluate,
            formula_suggestions=context.suggestions,
        )
        dialog.show()
        dialog.attack_bonus.set_expression("=bab + 2")
        dialog.name.setFocus()
        self.app.processEvents()
        self.assertIs(
            dialog.attack_bonus._display_stack.currentWidget(),
            dialog.attack_bonus.preview,
        )
        self.assertEqual("8", dialog.attack_bonus.preview.text())
        QTest.mouseClick(dialog.attack_bonus.preview, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertIs(
            dialog.attack_bonus._display_stack.currentWidget(),
            dialog.attack_bonus.editor,
        )
        self.assertEqual("=bab + 2", dialog.attack_bonus.editor.text())
        dialog.close()

    def test_formula_autocomplete_filters_and_inserts_references_and_functions(self) -> None:
        context = self._service().formula_context()
        dialog = AttackDialog(
            formula_evaluator=context.evaluate,
            formula_suggestions=context.suggestions,
        )
        editor = dialog.attack_bonus.editor
        editor.setFocus()
        editor.setText("=skillranks.acr")
        editor.setCursorPosition(len(editor.text()))
        editor._update_formula_completions(force=True)
        self.assertGreater(editor.completion_popup.topLevelItemCount(), 0)
        self.assertEqual(
            "skillranks.acrobatics",
            editor.completion_popup.topLevelItem(0).text(0),
        )
        editor._insert_selected_completion()
        self.assertEqual("=skillranks.acrobatics", editor.text())

        editor.setText("=flo")
        editor.setCursorPosition(len(editor.text()))
        editor._update_formula_completions(force=True)
        self.assertEqual("floor()", editor.completion_popup.topLevelItem(0).text(0))
        editor._insert_selected_completion()
        self.assertEqual("=floor()", editor.text())
        self.assertEqual(len("=floor("), editor.cursorPosition())
        dialog.close()

        tracker_dialog = CustomTrackerDialog(self.repository, self.character_id)
        tracker_editor = tracker_dialog.formula
        tracker_editor.setFocus()
        tracker_editor.setText("skillranks.acr")
        tracker_editor.setCursorPosition(len(tracker_editor.text()))
        tracker_editor._update_formula_completions(force=True)
        tracker_editor._insert_selected_completion()
        self.assertEqual("skillranks.acrobatics", tracker_editor.text())
        tracker_dialog.close()

    def test_autocomplete_popup_never_steals_typing_focus(self) -> None:
        context = self._service().formula_context()
        dialog = AttackDialog(
            formula_evaluator=context.evaluate,
            formula_suggestions=context.suggestions,
        )
        dialog.show()
        self.app.processEvents()
        editor = dialog.attack_bonus.editor
        editor.clear()
        editor.setFocus()
        self.app.processEvents()
        QTest.keyClicks(editor, "=skill")
        self.app.processEvents()
        self.assertTrue(editor.hasFocus())
        self.assertTrue(editor.completion_popup.isVisible())
        QTest.keyClicks(editor, "ranks.acr")
        self.app.processEvents()
        self.assertEqual("=skillranks.acr", editor.text())
        self.assertTrue(editor.hasFocus())
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.app.processEvents()
        self.assertEqual("=skillranks.acrobatics", editor.text())
        self.assertTrue(editor.hasFocus())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
