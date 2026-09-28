import os
import tempfile
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.content import archetype_entries, spell_entries, DEFAULT_CATALOG
from app.models import (
    CastingProfile, CurrencyPurse, FavoredClassBonus, MovementProfile,
    HitPoints, ProficiencyAdjustment, SkillState, SphereStatistic, ProdigySequence,
)
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.services.character_calculations import CharacterCalculationService
from app.services.sheet_presentation import build_character_sheet_snapshot
from app.building_blocks.bindings import BINDINGS
from app.recovery import FullRestEngine


class SheetPagesUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary_directory.name) / "characters.db"
        )
        self.character_id = self.repository.create_character("Three Page Hero", "Spheres")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    def test_hp_consumers_share_effective_classes_and_preserve_manual_values(self) -> None:
        archetype = "spheres-archetype:spheres-class:necros:brutal-necromancer"
        cases = (
            # Archetype, stored class HP, automatic maximum, formula, expected base.
            (True, 28, True, "", 34),
            (False, 28, True, "", 28),
            (True, 31, True, "", 31),  # Custom class HP must survive resolution.
            (True, 28, False, "", 70),
            (True, 28, False, "=10 * 6", 60),
        )
        for selected, class_hp, automatic, formula, base in cases:
            with self.subTest(archetype=selected, class_hp=class_hp,
                              automatic=automatic, formula=formula):
                cid = self.repository.create_character("HP regression", "Spheres")
                row_id = self.repository.add_class_level(
                    cid, "Necros", 5, "3/4", "Good", "Poor", "Good",
                    "spheres-class:necros", 8, class_hp,
                )
                if selected:
                    self.repository.set_class_archetype_keys(cid, row_id, (archetype,))
                self.repository.update_ability_score(cid, "constitution", 14)
                self.repository.add_modifier(cid, "hp", "HP regression bonus", "untyped", 3)
                self.repository.update_hit_points(HitPoints(cid, 70, 12, 4, 2, automatic))
                self.repository.set_numeric_formula(cid, "hit_points", 0, "maximum", formula)
                expected = base + (10 if automatic else 0) + 3

                calculator = CharacterCalculationService(self.repository, cid)
                self.assertEqual(34 if selected and class_hp == 28 else class_hp,
                                 calculator.resolved_classes()[0].hp_gained)
                self.assertEqual(10 if selected else 8, calculator.resolved_classes()[0].hit_die)
                snapshot = build_character_sheet_snapshot(self.repository, cid)
                self.assertEqual(expected, snapshot.displayed_hit_point_maximum)
                self.assertEqual(expected, calculator.hit_point_maximum())
                self.assertEqual(70, self.repository.get_hit_points(cid).maximum)

                self.sheet.character_id = cid
                self.sheet._refresh_hit_points()
                with self.sheet._calculation_batch():
                    self.sheet._refresh_hit_points()
                self.assertEqual(expected, self.sheet.hp_maximum.value())
                self.assertEqual(expected, self.sheet.classic_hp_maximum.value())
                stored = self.repository.get_hit_points(cid)
                self.assertEqual(HitPoints(cid, expected if automatic else 70,
                                          12, 4, 2, automatic), stored)
                self.assertEqual(class_hp, self.repository.list_class_levels(cid)[0].hp_gained)
                self.assertEqual(stored.maximum, BINDINGS.get("hit_points.maximum").getter(
                    self.repository, cid))
                self.assertEqual(stored.maximum, CharacterCalculationService(
                    self.repository, cid).formula_context().evaluate("hit_points.maximum"))
                self.assertEqual(expected, build_character_sheet_snapshot(
                    self.repository, cid).displayed_hit_point_maximum)

    def test_effective_casting_bindings_include_formulas_traditions_and_sequence(self) -> None:
        cid = self.character_id
        self.repository.add_class_level(
            cid, "Prodigy", 6, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=33,
        )
        self.repository.update_ability_score(cid, "intelligence", 18)
        profile = CastingProfile(cid, casting_ability="intelligence",
                                 casting_class_levels=6, caster_level=2, auto_spell_points=True)
        self.repository.update_casting_profile(profile)
        self.repository.update_prodigy_sequence(ProdigySequence(cid, True, 4, 6, ""))
        self.sheet._sequence_active, self.sheet._sequence_links = True, 4
        self.repository.set_numeric_formula(cid, "casting", 0, "caster_level",
                                            "=casting.caster_level + 2")
        entry = next(item for item in DEFAULT_CATALOG.tradition_entries("Casting")
                     if item["name"] == "Traditional Magic")
        self.repository.add_character_tradition(cid, entry["key"], entry["name"],
                                                "Casting", "{}", "[]")
        self.repository.add_feat(cid, "Casting regression", effects=(
            {"target": "caster_level", "value": 1},
            {"target": "spell_points", "value": 2},
        ))
        self.sheet._refresh_casting_profile()
        snapshot = build_character_sheet_snapshot(self.repository, cid)
        self.assertEqual(7, snapshot.casting.caster_level)
        self.assertEqual(18, snapshot.casting.spell_points_maximum)
        self.assertEqual((6, 17, 17), (snapshot.casting.magic_skill_bonus,
                                     snapshot.casting.magic_skill_defense,
                                     snapshot.casting.save_dc))
        self.assertEqual("+6", self.sheet.casting_msb.text())
        self.assertEqual("17", self.sheet.casting_msd.text())
        self.assertEqual("17", self.sheet.casting_save_dc.text())
        self.assertEqual("7", self.sheet._play_casting_labels["caster_level"].text())
        self.assertEqual(18, self.sheet.spell_points_maximum.value())
        self.assertEqual((7, 18), (
            BINDINGS.get("casting.caster_level").getter(self.repository, cid),
            BINDINGS.get("spell_points.maximum").getter(self.repository, cid),
        ))
        baseline = CharacterCalculationService(self.repository, cid).formula_context()
        self.assertEqual(2, baseline.evaluate("casting.caster_level"))
        self.assertEqual(10, baseline.evaluate("spell_points.maximum"))
        FullRestEngine(self.repository, cid).perform({"spell_points": True})
        self.assertEqual(18, self.repository.get_casting_profile(cid).spell_points_current)
        self.assertEqual(2, self.repository.get_casting_profile(cid).caster_level)
        self.repository.set_numeric_formula(cid, "casting", 0, "casting_class_levels",
                                            "=casting.class_levels + 2")
        self.sheet._refresh_casting_profile()
        self.assertEqual(22, self.sheet.spell_points_maximum.value())
        self.assertEqual(22, BINDINGS.get("spell_points.maximum").getter(self.repository, cid))
        FullRestEngine(self.repository, cid).perform({"spell_points": True})
        self.assertEqual(22, self.repository.get_casting_profile(cid).spell_points_current)
        self.assertEqual(6, self.repository.get_casting_profile(cid).casting_class_levels)
        self.repository.update_prodigy_sequence(ProdigySequence(cid, False, 0, 6, ""))
        self.sheet._sequence_active, self.sheet._sequence_links = False, 0
        self.sheet._refresh_casting_profile()
        self.assertEqual("5", self.sheet._play_casting_labels["caster_level"].text())
        self.assertEqual(5, BINDINGS.get("casting.caster_level").getter(self.repository, cid))

    def test_spell_point_recovery_uses_formula_maximum_without_replacing_literal(self) -> None:
        cid = self.character_id
        for formula, maximum in (("", 7), ("=spell_points.maximum + 5", 12)):
            with self.subTest(formula=formula):
                profile = CastingProfile(cid, caster_level=3, spell_points_maximum=7,
                                         spell_points_current=1, spell_points_temporary=2,
                                         auto_spell_points=False)
                self.repository.update_casting_profile(profile)
                self.repository.set_numeric_formula(cid, "casting", 0,
                                                    "spell_points_maximum", formula)
                self.sheet._refresh_casting_profile()
                self.assertEqual(maximum, self.sheet.spell_points_maximum.value())
                self.assertEqual(maximum, build_character_sheet_snapshot(
                    self.repository, cid).casting.spell_points_maximum)
                FullRestEngine(self.repository, cid).perform({"spell_points": True})
                self.assertEqual(replace(profile, spell_points_current=maximum,
                                         spell_points_temporary=0),
                                 self.repository.get_casting_profile(cid))
                self.assertEqual(maximum, BINDINGS.get("spell_points.maximum").getter(
                    self.repository, cid))
                self.assertEqual(3, BINDINGS.get("casting.caster_level").getter(
                    self.repository, cid))
                self.assertEqual(7, CharacterCalculationService(self.repository, cid)
                                 .formula_context().evaluate("spell_points.maximum"))

    def test_sheet_is_split_into_named_pages(self) -> None:
        from app.ui.refined.pages import DEFAULT_TABS
        self.assertEqual([title for _, title in DEFAULT_TABS],
                         [self.sheet.page_tabs.tabText(i) for i in range(len(DEFAULT_TABS))])
        companion = self.sheet.page_tabs.indexOf(self.sheet.companion_scroll)
        self.assertFalse(self.sheet.page_tabs.isTabVisible(companion))
        self.assertEqual("Three Page Hero", self.sheet.record_character_name.text())
        self.assertFalse(self.sheet.skill_table.showGrid())
        self.assertIn("strength", self.sheet._classic_ability_labels)
        self.assertIn("land_speed", self.sheet.movement_controls)
        self.assertEqual(Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
                         self.sheet.core_scroll.horizontalScrollBarPolicy())

    def test_beastmastery_pet_adds_the_shared_pet_familiar_page(self) -> None:
        self.repository.add_class_level(
            self.character_id,
            "Fighter",
            4,
            "Full",
            "Good",
            "Poor",
            "Poor",
            "pathfinder-class:fighter",
            10,
            40,
        )
        self.repository.add_martial_talent(
            self.character_id,
            "Pet",
            "Beastmastery",
            "Talent",
            catalog_key="beastmastery:talent:pet",
            catalog_category="Talent",
        )
        self.sheet.refresh_all()
        tabs = [
            self.sheet.page_tabs.tabText(index)
            for index in range(self.sheet.page_tabs.count())
        ]
        self.assertTrue(any("PET / FAMILIAR" in value for value in tabs))
        automatic = " ".join(
            self.sheet.familiar_panel.progression.item(row, 1).text()
            for row in range(self.sheet.familiar_panel.progression.rowCount())
            if self.sheet.familiar_panel.progression.item(row, 0).text()
            == "Automatic abilities"
        )
        self.assertNotIn("Share Spells", automatic)

    def test_freeform_skills_table_consumes_resized_section_height(self) -> None:
        layout = self.sheet.skills_section.layout()
        self.assertEqual(1, layout.stretch(layout.indexOf(self.sheet.skill_table)))
        self.sheet.skill_table.setFixedHeight(80)
        self.sheet.skills_section.setProperty("freeformManaged", True)
        self.sheet._refresh_skills()
        self.assertEqual(44, self.sheet.skill_table.minimumHeight())
        self.assertGreater(self.sheet.skill_table.maximumHeight(), 80)

    def test_conditions_panel_is_compact_and_rule_focused(self) -> None:
        self.assertEqual(2, self.sheet.condition_table.columnCount())
        self.assertEqual("Condition", self.sheet.condition_table.horizontalHeaderItem(0).text())
        self.assertEqual("Effect", self.sheet.condition_table.horizontalHeaderItem(1).text())
        self.assertLessEqual(self.sheet.condition_table.maximumHeight(), 170)

    def test_formula_dependent_refresh_reuses_one_rules_snapshot(self) -> None:
        for batched in (False, True):
            with (
                self.subTest(batched=batched),
                patch(
                    "app.ui.character_sheet.CharacterCalculationService",
                    wraps=CharacterCalculationService,
                ) as service,
                patch.object(
                    self.sheet, "_refresh_attacks", wraps=self.sheet._refresh_attacks
                ) as attacks,
            ):
                batch = self.sheet._calculation_batch() if batched else nullcontext()
                with batch:
                    existing = self.sheet._batched_calculator
                    self.sheet._refresh_formula_dependents()
                    self.assertEqual(1, service.call_count)
                    self.assertEqual(1, attacks.call_count)
                    if batched:
                        self.assertIs(existing, self.sheet._calculator())
                        self.assertIs(existing, attacks.call_args.args[0])
                self.assertIsNone(self.sheet._batched_calculator)

    def test_core_health_bar_and_compact_skill_rank_column_follow_live_hp(self) -> None:
        self.assertEqual("Rk.", self.sheet.skill_table.horizontalHeaderItem(4).text())
        self.assertEqual(250, self.sheet.classic_hp_bar.TRANSITION_MS)

        self.sheet.classic_hp_bar.set_health(10, 20, animate=False)
        self.sheet.classic_hp_bar.set_health(10, 20)
        self.assertEqual(
            self.sheet.classic_hp_bar._animation.State.Stopped,
            self.sheet.classic_hp_bar._animation.state(),
        )

        self.sheet.show()
        self.sheet.page_tabs.setCurrentIndex(0)
        self.application.processEvents()
        QTest.mouseClick(
            self.sheet.classic_hp_adjustment, Qt.MouseButton.LeftButton
        )
        self.application.processEvents()
        self.assertEqual(
            "0", self.sheet.classic_hp_adjustment.lineEdit().selectedText()
        )
        QTest.keyClicks(self.sheet.classic_hp_adjustment, "15")
        self.assertEqual(15, self.sheet.classic_hp_adjustment.value())
        self.sheet.classic_hp_adjustment.setValue(0)

        for current, expected_state in ((40, "healthy"), (19, "warning"), (9, "critical")):
            self.repository.update_hit_points(HitPoints(
                self.character_id, maximum=40, current=current,
            ))
            self.sheet._refresh_hit_points()
            self.assertEqual(f"{current} / 40 HP", self.sheet.classic_hp_bar.format())
            self.assertEqual(expected_state, self.sheet.classic_hp_bar.property("healthState"))
            self.assertEqual(expected_state, self.sheet.hp_bar.property("healthState"))

        self.repository.update_hit_points(HitPoints(
            self.character_id, maximum=40, current=30, temporary=5, nonlethal=8,
        ))
        self.sheet._refresh_hit_points()
        self.assertEqual(5, self.sheet.classic_hp_bar.temporary_hit_points)
        self.assertEqual(8, self.sheet.classic_hp_bar.nonlethal_damage)
        self.sheet.classic_hp_adjustment.setValue(7)
        self.sheet.classic_hp_damage_button.click()
        damaged = self.repository.get_hit_points(self.character_id)
        self.assertEqual(28, damaged.current)
        self.assertEqual(0, damaged.temporary)
        self.assertEqual(0, self.sheet.classic_hp_adjustment.value())

        self.sheet.classic_hp_adjustment.setValue(6)
        self.sheet.classic_hp_heal_button.click()
        partially_healed = self.repository.get_hit_points(self.character_id)
        self.assertEqual(34, partially_healed.current)
        self.assertEqual(2, partially_healed.nonlethal)

        self.sheet.classic_hp_adjustment.setValue(30)
        self.sheet.classic_hp_heal_button.click()
        healed = self.repository.get_hit_points(self.character_id)
        self.assertEqual(40, healed.current)
        self.assertEqual(0, healed.nonlethal)
        self.assertEqual("40 / 40 HP", self.sheet.classic_hp_bar.format())

    def test_custom_pool_and_calculated_value_render_from_safe_formulas(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Monk", 8, "3/4", "Good", "Good", "Good",
            preset_key="monk", hit_die=8, hp_gained=43,
        )
        self.repository.add_custom_tracker(
            self.character_id, "spell_points", "Spell Points", "pool",
            formula="floor(classes.monk.level / 3)", current_value=1, unit="SP",
            recovery_event="full_rest", recovery_operation="set_to_max",
        )
        self.repository.add_custom_tracker(
            self.character_id, "daily_allowance", "Daily Allowance", "calculated",
            formula="trackers.spell_points.maximum + 1",
        )
        self.sheet.refresh_all()
        self.assertIs(
            self.sheet.custom_trackers_section.parent(), self.sheet.builder_canvas
        )
        self.assertEqual(2, self.sheet.custom_tracker_table.rowCount())
        self.assertEqual("1", self.sheet.custom_tracker_table.item(0, 2).text())
        self.assertEqual("2", self.sheet.custom_tracker_table.item(0, 3).text())
        self.assertEqual("3", self.sheet.custom_tracker_table.item(1, 2).text())
        self.assertIn(
            "trackers.spell_points.value",
            self.sheet.custom_tracker_table.item(0, 0).toolTip(),
        )
        self.assertIn("spell_points", self.sheet.custom_tracker_blocks)
        self.assertIn("daily_allowance", self.sheet.custom_tracker_blocks)
        self.assertEqual(
            "trackers.spell_points.value",
            self.sheet.custom_tracker_blocks["spell_points"].reference.text(),
        )

    def test_prodigy_base_options_are_ready_and_invalid_actions_are_silent(self) -> None:
        options = self.repository.list_sequence_options(self.character_id)
        self.assertEqual(26, len(options))
        self.assertTrue(all(option.built_in for option in options))
        names = {option.name for option in options}
        self.assertIn("Attack", names)
        self.assertIn("Counting Coup", names)
        self.assertIn("Disengage", names)
        self.assertIn("Preparation", names)
        self.assertIn("Save", names)
        self.assertIn("Swift Heal", names)
        self.assertIn("Steel Mind", names)
        self.assertIn("Resilience", names)

        with patch("app.ui.character_sheet.QMessageBox.information") as information:
            self.sheet._add_prodigy_link()
            self.sheet._use_sequence_option("Finisher")
        information.assert_not_called()
        self.assertTrue(self.repository.get_prodigy_sequence(self.character_id).active)

    def test_prodigy_class_preset_drives_casting_sequence_and_inspired_bonus(self) -> None:
        self.repository.update_ability_score(self.character_id, "charisma", 14)
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
        self.sheet.refresh_all()

        profile = self.repository.get_casting_profile(self.character_id)
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        self.assertEqual(5, profile.casting_class_levels)
        self.assertEqual(3, profile.caster_level)
        self.assertTrue(profile.auto_spell_points)
        self.assertEqual(7, profile.spell_points_current)
        self.assertEqual(5, sequence.maximum)
        self.assertFalse(self.sheet.prodigy_section.isHidden())
        self.assertIn("PRODIGY 5", self.sheet.prodigy_class_summary.text())
        opener_table = self.sheet.sequence_tables["Opener"]
        self.assertEqual(2, opener_table.columnCount())
        self.assertEqual("Name", opener_table.horizontalHeaderItem(0).text())
        self.assertEqual("Action", opener_table.horizontalHeaderItem(1).text())
        self.assertTrue(opener_table.item(0, 0).toolTip())

        special_names = {
            self.sheet.special_ability_table.item(row, 1).text()
            for row in range(self.sheet.special_ability_table.rowCount())
        }
        self.assertIn("Improved Adaptation", special_names)
        self.assertNotIn("Sequence — 6 Links", special_names)
        improved_row = next(
            row
            for row in range(self.sheet.special_ability_table.rowCount())
            if self.sheet.special_ability_table.item(row, 1).text() == "Improved Adaptation"
        )
        self.assertIn("Improved Adaptation", self.sheet.special_ability_table.item(improved_row, 1).toolTip())

        self.sheet._store_prodigy_sequence(True, 4)
        inspired = self.sheet._automatic_modifier_map()["attack"]
        self.assertTrue(
            any(item.source == "Prodigy: Inspired Sequence" and item.value == 2 for item in inspired)
        )
        self.assertIn("EFFECTIVE CL 5", self.sheet.sequence_effect.text())
        self.assertIn("MID-CASTER CL 5", self.sheet.prodigy_class_summary.text())
        self.assertFalse(self.sheet._classic_magic_skill_rows["msb"].isHidden())
        self.assertFalse(self.sheet._classic_magic_skill_rows["msd"].isHidden())
        self.assertEqual(
            self.sheet.casting_msb.text(),
            self.sheet._classic_magic_skill_labels["msb"].text(),
        )
        self.assertEqual(
            self.sheet.casting_msd.text(),
            self.sheet._classic_magic_skill_labels["msd"].text(),
        )

    def test_spheres_proficiencies_are_automatic_and_character_editable(self) -> None:
        class_level_id = self.repository.add_class_level(
            self.character_id, "Prodigy", 1, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=8,
        )
        self.sheet.refresh_all()
        self.assertIn("Simple weapons", self.sheet.proficiencies_table.item(0, 1).text())
        self.assertIn("Light armor", self.sheet.proficiencies_table.item(0, 2).text())
        self.repository.save_proficiency_adjustment(
            ProficiencyAdjustment(
                self.character_id, class_level_id, "Custom weapon", "Custom armor", "GM rule"
            )
        )
        self.sheet._refresh_proficiencies()
        self.assertEqual("Custom weapon", self.sheet.proficiencies_table.item(0, 1).text())
        self.assertIn("GM rule", self.sheet.proficiencies_table.item(0, 1).toolTip())
        self.sheet.proficiencies_table.setCurrentCell(0, 0)
        self.sheet._reset_selected_proficiencies()
        self.assertIn("Simple weapons", self.sheet.proficiencies_table.item(0, 1).text())

    def test_automatic_spell_point_maximum_displays_effective_value_and_can_be_disabled(self) -> None:
        self.repository.update_ability_score(self.character_id, "wisdom", 16)
        self.repository.update_casting_profile(
            CastingProfile(self.character_id, casting_ability="wisdom")
        )
        self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.sheet.refresh_all()
        profile = self.repository.get_casting_profile(self.character_id)
        self.assertNotEqual(profile.spell_points_maximum, self.sheet.spell_points_maximum.value())
        self.assertEqual(8, self.sheet.spell_points_maximum.value())
        self.assertTrue(self.sheet.spell_points_auto.isEnabled())
        self.sheet.spell_points_auto.setChecked(False)
        self.application.processEvents()
        self.assertFalse(self.repository.get_casting_profile(self.character_id).auto_spell_points)
        self.assertTrue(self.sheet.spell_points_maximum.isEnabled())

    def test_selected_feature_details_start_empty_and_follow_general_table_clicks(self) -> None:
        self.assertEqual("", self.sheet.feature_details.toPlainText())
        self.repository.add_class_level(
            self.character_id, "Prodigy", 1, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=8,
        )
        self.sheet.refresh_all()
        self.sheet.proficiencies_table.cellClicked.emit(0, 0)
        self.application.processEvents()
        detail = self.sheet.feature_details.toPlainText()
        self.assertIn("Prodigy", detail)
        self.assertIn("Simple weapons", detail)

    def test_spell_point_and_sphere_focus_feats_feed_shared_casting_rules(self) -> None:
        self.repository.update_ability_score(self.character_id, "intelligence", 18)
        self.repository.add_class_level(
            self.character_id,
            "Incanter",
            6,
            "1/2",
            "Poor",
            "Poor",
            "Good",
            preset_key="spheres-class:incanter",
            hit_die=6,
            hp_gained=24,
        )
        profile = self.repository.get_casting_profile(self.character_id)
        self.repository.update_casting_profile(
            CastingProfile(
                self.character_id,
                casting_ability="intelligence",
                casting_class_levels=profile.casting_class_levels,
                caster_level=profile.caster_level,
                auto_spell_points=True,
            )
        )
        for suffix in ("one", "two"):
            self.repository.add_feat(
                self.character_id,
                "Extra Spell Points",
                catalog_key=f"test:extra-spell-points:{suffix}",
                effects=({"target": "spell_points", "value": 2},),
                repeatable=True,
            )
        self.repository.add_feat(
            self.character_id,
            "Sphere Focus",
            catalog_key="test:sphere-focus",
            choice="Warp",
            effects=({"target": "sphere_save_dc:warp", "value": 1},),
            repeatable=True,
        )
        self.repository.add_spell(
            self.character_id,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="warp:base",
            catalog_category="Base Sphere",
        )

        self.sheet.refresh_all()

        self.assertEqual("0 / 14", self.sheet.quick_spell_points.text())
        self.assertIn("Extra Spell Points", self.sheet.spell_points_breakdown.text())
        warp_row = next(
            row
            for row in range(self.sheet.sphere_stats_table.rowCount())
            if self.sheet.sphere_stats_table.item(row, 0).text() == "Warp"
        )
        self.assertEqual("18", self.sheet.sphere_stats_table.item(warp_row, 2).text())

    def test_pathfinder_class_populates_special_abilities_and_caster_level(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            preset_key="wizard", hit_die=6, hp_gained=18,
        )
        known_spell_id = self.repository.add_spell(
            self.character_id,
            "Fireball",
            system="Prepared",
            level=3,
            school_or_sphere="Evocation",
            casting_time="1 standard action",
            range="Long",
        )
        wizard_class_id = self.repository.list_class_levels(self.character_id)[0].id
        self.repository.add_prepared_spell(
            self.character_id, wizard_class_id, known_spell_id, prepared_count=1
        )
        self.sheet.refresh_all()
        self.assertGreater(self.sheet.special_ability_table.rowCount(), 0)
        tooltips = [
            self.sheet.special_ability_table.item(row, 1).toolTip()
            for row in range(self.sheet.special_ability_table.rowCount())
        ]
        self.assertTrue(any("Wizard" in tooltip for tooltip in tooltips))
        self.assertEqual(5, self.repository.get_casting_profile(self.character_id).caster_level)
        self.assertEqual("5", self.sheet._play_casting_labels["caster_level"].text())
        self.assertFalse(self.sheet.caster_level.isEnabled())
        self.assertTrue(self.sheet.page_tabs.isTabVisible(3))
        self.assertTrue(self.sheet.casting_profile_section.isHidden())
        self.assertFalse(self.sheet.traditional_casting_section.isHidden())
        self.assertEqual("5", self.sheet.traditional_casting_labels["caster_level"].text())
        self.assertFalse(self.sheet.spells_known_section.isHidden())
        self.assertTrue(self.sheet.spells_section.isHidden())
        self.assertIs(self.sheet.spells_known_section.parent(), self.sheet.magic_canvas)
        self.assertEqual(1, self.sheet.spells_known_table.rowCount())
        self.assertEqual("Fireball", self.sheet.spells_known_table.item(0, 0).text())
        self.assertEqual("3", self.sheet.spells_known_table.item(0, 1).text())
        self.assertEqual(
            ["Spell", "Spell Level", "School", "Casting Time", "Range"],
            [
                self.sheet.spells_known_table.horizontalHeaderItem(column).text()
                for column in range(self.sheet.spells_known_table.columnCount())
            ],
        )
        self.assertFalse(self.sheet.spells_prepared_section.isHidden())
        self.assertEqual("Fireball", self.sheet.spells_prepared_table.item(0, 0).text())
        self.assertEqual("3", self.sheet.spells_prepared_table.item(0, 2).text())
        self.assertEqual("1", self.sheet.spells_prepared_table.item(0, 3).text())
        self.assertEqual("1", self.sheet.spells_prepared_table.item(0, 4).text())
        self.assertFalse(self.sheet.spell_level_overview_section.isHidden())
        self.assertEqual(
            ["Known", "Save DC", "Level", "Per Day", "Bonus"],
            [
                self.sheet.spell_level_overview_table.horizontalHeaderItem(column).text()
                for column in range(self.sheet.spell_level_overview_table.columnCount())
            ],
        )
        self.assertEqual(10, self.sheet.spell_level_overview_table.rowCount())
        self.assertEqual("1", self.sheet.spell_level_overview_table.item(3, 0).text())
        self.assertEqual("13", self.sheet.spell_level_overview_table.item(3, 1).text())
        self.assertEqual("3rd", self.sheet.spell_level_overview_table.item(3, 2).text())
        self.assertEqual("1", self.sheet.spell_level_overview_table.item(3, 3).text())
        self.assertEqual("—", self.sheet.spell_level_overview_table.item(3, 4).text())
        self.assertEqual("—", self.sheet._play_casting_labels["save_dc"].text())
        self.sheet.spells_known_table.setCurrentCell(0, 0)
        self.sheet.spells_known_table.cellClicked.emit(0, 0)
        self.assertEqual("13", self.sheet._play_casting_labels["save_dc"].text())
        self.assertIn("Fireball", self.sheet._play_casting_labels["save_dc"].toolTip())

    def test_sorcerer_daily_slots_use_charisma_and_track_expenditure(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Sorcerer", 6, "1/2", "Poor", "Poor", "Good",
            preset_key="pathfinder-class:sorcerer", hit_die=6, hp_gained=21,
        )
        self.repository.update_ability_score(self.character_id, "charisma", 18)
        self.repository.add_spell(
            self.character_id, "Fireball", system="Spontaneous", level=3
        )
        self.sheet.refresh_all()

        self.assertTrue(self.sheet.spells_prepared_section.isHidden())
        self.assertFalse(self.sheet.spontaneous_slot_usage_panel.isHidden())
        self.assertEqual("4", self.sheet.spell_level_overview_table.item(3, 3).text())
        self.assertEqual("1", self.sheet.spell_level_overview_table.item(3, 4).text())

        row = next(
            row
            for row in range(self.sheet.spontaneous_slot_table.rowCount())
            if self.sheet.spontaneous_slot_table.item(row, 1).text() == "3"
        )
        self.sheet.spontaneous_slot_table.selectRow(row)
        self.sheet._use_spontaneous_slot()
        self.assertEqual("1", self.sheet.spontaneous_slot_table.item(row, 3).text())
        self.assertEqual("3", self.sheet.spontaneous_slot_table.item(row, 4).text())

    def test_traditional_spells_can_be_added_in_one_batch(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            preset_key="wizard", hit_die=6, hp_gained=18,
        )
        self.sheet.refresh_all()
        wanted = {"Fireball", "Magic Missile"}
        selected = tuple(
            entry for entry in spell_entries()
            if entry["name"] in wanted
            and "Wizard" in (entry.get("class_levels") or {})
        )
        selected = tuple({entry["name"]: entry for entry in selected}.values())
        self.assertEqual(2, len(selected))
        casters = self.sheet._traditional_casting_classes()

        added = self.sheet._add_catalog_batch(
            selected,
            lambda entry: self.sheet._add_traditional_catalog_entry(entry, casters),
            self.sheet._refresh_spells,
            "spells",
        )

        self.assertEqual(2, added)
        self.assertEqual(
            wanted,
            {spell.name for spell in self.repository.list_spells(self.character_id)},
        )

    def test_archetype_special_abilities_replace_base_class_features(self) -> None:
        class_id = self.repository.add_class_level(
            self.character_id, "Fighter", 2, "Full", "Good", "Poor", "Poor",
            preset_key="fighter", hit_die=10, hp_gained=20,
        )
        aerial = next(
            entry for entry in archetype_entries("fighter")
            if entry["name"] == "Aerial Assaulter"
        )
        self.repository.set_class_archetype_keys(
            self.character_id, class_id, (str(aerial["key"]),)
        )
        self.sheet.refresh_all()
        names = {
            self.sheet.special_ability_table.item(row, 1).text()
            for row in range(self.sheet.special_ability_table.rowCount())
        }
        self.assertNotIn("Bravery", names)
        self.assertIn("Aerial Expertise", names)
        self.assertIn("Take the High Ground", names)
        self.assertIn("Bonus Feats (FGT)", names)

    def test_spheres_archetype_enables_only_its_declared_sheet_modules(self) -> None:
        class_id = self.repository.add_class_level(
            self.character_id, "Fighter", 5, "Full", "Good", "Poor", "Poor",
            preset_key="fighter", hit_die=10, hp_gained=35,
        )
        self.repository.set_class_archetype_keys(
            self.character_id,
            class_id,
            ("spheres-archetype:pathfinder-class:fighter:coiled-blade",),
        )
        self.sheet.refresh_all()
        self.assertFalse(self.sheet.martial_talents_section.isHidden())
        self.assertFalse(self.sheet.martial_sphere_build_panel.isHidden())
        self.assertTrue(self.sheet.magic_sphere_build_panel.isHidden())
        self.assertFalse(self.sheet.page_tabs.isTabVisible(3))

    def test_imported_spherecaster_enables_spheres_tier_without_traditional_tier(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Incanter", 7, "1/2", "Poor", "Poor", "Good",
            preset_key="spheres-class:incanter", hit_die=6, hp_gained=25,
        )
        self.sheet.refresh_all()
        self.assertTrue(self.sheet.page_tabs.isTabVisible(3))
        self.assertFalse(self.sheet.casting_profile_section.isHidden())
        self.assertFalse(self.sheet.magic_sphere_build_panel.isHidden())
        self.assertTrue(self.sheet.traditional_casting_section.isHidden())
        self.assertEqual(7, self.repository.get_casting_profile(self.character_id).caster_level)

    def test_battle_born_keeps_sequence_and_martial_modules_but_removes_magic(self) -> None:
        class_id = self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=28,
        )
        self.repository.set_class_archetype_keys(
            self.character_id,
            class_id,
            ("spheres-archetype:prodigy:battle-born",),
        )
        self.sheet.refresh_all()
        self.assertFalse(self.sheet.prodigy_section.isHidden())
        self.assertFalse(self.sheet.martial_talents_section.isHidden())
        self.assertTrue(self.sheet.casting_profile_section.isHidden())
        self.assertFalse(self.sheet.page_tabs.isTabVisible(3))

    def test_sphere_options_imbues_ranges_and_number_wheel_are_dynamic(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.repository.add_spell(
            self.character_id, "Life Sphere", "Sphere", school_or_sphere="Life",
            catalog_key="life:base", catalog_category="Base Sphere",
        )
        self.repository.add_spell(
            self.character_id, "Warp Sphere", "Sphere", school_or_sphere="Warp",
            catalog_key="warp:base", catalog_category="Base Sphere",
        )
        self.sheet.refresh_all()
        finishers = {
            item.name for item in self.repository.list_sequence_options(self.character_id, "Finisher")
        }
        self.assertIn("Healing Burst", finishers)
        self.assertIn("Private Battlefield", finishers)
        self.assertIn("Sudden Shuffle", finishers)
        combo_values = {
            self.sheet.prodigy_imbue_combo.itemData(index)
            for index in range(self.sheet.prodigy_imbue_combo.count())
        }
        self.assertIn("life_regenerate", combo_values)
        self.assertIn("warp_step_between", combo_values)
        self.sheet.prodigy_imbue_combo.setCurrentIndex(
            self.sheet.prodigy_imbue_combo.findData("life_regenerate")
        )
        self.sheet._store_prodigy_sequence(True, 4)
        self.assertEqual("Fast Healing 4", self.sheet.prodigy_imbue_value.text())
        self.assertEqual("35 ft", self.sheet.magic_range_table.item(0, 2).text())
        self.assertEqual("150 ft", self.sheet.magic_range_table.item(1, 2).text())
        self.assertEqual("600 ft", self.sheet.magic_range_table.item(2, 2).text())
        self.sheet.page_tabs.setCurrentIndex(0)
        self.sheet.resize(900, 600)
        self.sheet.show()
        self.application.processEvents()
        scroll = self.sheet.builder_scroll.verticalScrollBar()
        scroll.setValue(min(20, scroll.maximum()))
        before_scroll = scroll.value()
        before_ability = self.sheet.casting_ability.currentIndex()
        wheel = QWheelEvent(
            QPointF(4, 4),
            QPointF(4, 4),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        self.assertTrue(
            self.sheet.eventFilter(self.sheet.casting_ability, wheel)
        )
        self.assertEqual(before_ability, self.sheet.casting_ability.currentIndex())
        self.assertGreaterEqual(scroll.value(), before_scroll)

    def test_skill_class_marker_and_ability_override_are_visible_and_persistent(self) -> None:
        self.repository.update_ability_score(self.character_id, "intelligence", 18)
        self.repository.update_skill_state(
            self.character_id,
            SkillState("acrobatics", 2, True, 0, "Uses Intelligence", "intelligence"),
        )
        self.sheet.refresh_all()
        row = next(
            row
            for row in range(self.sheet.skill_table.rowCount())
            if self.sheet.skill_table.item(row, 0).text() == "Acrobatics"
        )
        self.assertEqual("■", self.sheet.skill_table.item(row, 1).text())
        self.assertEqual("INT", self.sheet.skill_table.item(row, 3).text())
        self.assertEqual("+9", self.sheet.skill_table.item(row, 2).text())
        self.assertFalse(self.sheet.skill_table.verticalScrollBar().isVisible())

    def test_favored_class_and_movement_blocks_are_live(self) -> None:
        class_id = self.repository.add_class_level(
            self.character_id, "Fighter", 2, "Full", "Good", "Poor", "Poor",
            preset_key="fighter", hit_die=10, hp_gained=16,
        )
        self.repository.update_favored_class_bonus(
            FavoredClassBonus(self.character_id, class_id, hp_bonus=1, skill_point_bonus=1)
        )
        self.repository.update_movement_profile(
            MovementProfile(self.character_id, land_speed=40, fly_speed=60)
        )
        self.sheet.refresh_all()
        self.assertEqual(1, self.sheet.favored_class_table.rowCount())
        self.assertIn("+1 HP", self.sheet.favored_class_summary.text())
        self.assertEqual("40 ft", self.sheet.movement_totals["land_speed"].text())
        self.assertEqual("60 ft", self.sheet.movement_totals["fly_speed"].text())
        self.sheet.movement_controls["land_speed"].set_expression(
            "=abilities.dexterity.score * 5"
        )
        self.sheet._save_movement()
        self.assertEqual("50 ft", self.sheet.movement_totals["land_speed"].text())
        self.assertEqual(
            "=abilities.dexterity.score * 5",
            self.repository.numeric_formulas(
                self.character_id, "movement", 0
            )[("movement", 0, "land_speed")],
        )

    def test_movement_formula_start_replaces_literal_and_opens_autocomplete(self) -> None:
        from PySide6.QtTest import QTest

        self.sheet.show()
        self.sheet.movement_edit_toggle.setChecked(True)
        self.application.processEvents()
        editor = self.sheet.movement_controls["land_speed"].editor
        editor.setText("30")
        editor.setCursorPosition(len(editor.text()))
        editor.setFocus()
        QTest.keyClicks(editor, "=skill")
        self.application.processEvents()
        self.assertEqual("=skill", editor.text())
        self.assertTrue(editor.completion_popup.isVisible())
        self.assertGreater(editor.completion_popup.topLevelItemCount(), 0)

    def test_inventory_worn_slots_load_and_currency_share_live_data(self) -> None:
        self.repository.add_equipment(
            self.character_id,
            "Chain shirt",
            "Armor",
            1,
            25,
            True,
            4,
            "armor",
            4,
            "Light armor",
            2,
            "Armor",
            100,
        )
        self.repository.add_equipment(
            self.character_id,
            "Adventuring gear",
            "Gear",
            1,
            20,
            False,
            0,
            "untyped",
            None,
            "",
        )
        self.repository.update_currency_purse(
            CurrencyPurse(self.character_id, copper=5, silver=7, gold=25, platinum=1)
        )

        self.sheet._refresh_equipment()
        self.sheet._refresh_currency()

        self.assertEqual(
            ("Item", "State / Slot", "Qty", "Value / Weight", "Defense / Notes"),
            tuple(
                self.sheet.equipment_table.horizontalHeaderItem(column).text()
                for column in range(self.sheet.equipment_table.columnCount())
            ),
        )
        self.assertGreaterEqual(self.sheet.worn_table.rowCount(), 1)
        armor_row = next(
            row for row in range(self.sheet.worn_table.rowCount())
            if self.sheet.worn_table.item(row, 0).text() == "Armor"
        )
        self.assertNotEqual("Empty", self.sheet.worn_table.item(armor_row, 1).text())
        self.assertEqual("loadMedium", self.sheet.load_status.objectName())
        self.assertEqual("Inventory value 100 gp", self.sheet.inventory_value_summary.text())
        self.assertEqual("25", self.sheet.currency_controls["gold"].text())
        self.assertEqual("Total value  35.75 gp", self.sheet.currency_total.text())

    def test_inventory_has_quiet_direct_wear_and_remove_actions(self) -> None:
        self.assertEqual("Wear", self.sheet.wear_item_button.text())
        self.assertEqual("Remove", self.sheet.remove_item_button.text())
        self.assertFalse(self.sheet.wear_item_button.isEnabled())
        self.assertFalse(self.sheet.remove_item_button.isEnabled())
        with patch("app.ui.character_sheet.QMessageBox.information") as information:
            self.sheet._wear_equipment()
            self.sheet._remove_equipment_from_use()
            self.sheet._unequip_worn_equipment()
        information.assert_not_called()

        item_id = self.repository.add_equipment(
            self.character_id,
            "Chain shirt",
            "Armor",
            1,
            25,
            False,
            4,
            "armor",
            4,
            "",
            slot="Armor",
            state="stored",
        )
        self.sheet._refresh_equipment()
        self.sheet.equipment_table.selectRow(0)
        self.application.processEvents()
        self.assertTrue(self.sheet.wear_item_button.isEnabled())
        self.assertFalse(self.sheet.remove_item_button.isEnabled())

        self.sheet.wear_item_button.click()
        item = self.repository.list_equipment(self.character_id)[0]
        self.assertEqual(item_id, item.id)
        self.assertEqual("armor", item.state)
        armor_row = next(
            row for row in range(self.sheet.worn_table.rowCount())
            if self.sheet.worn_table.item(row, 0).text() == "Armor"
        )
        self.assertNotEqual("Empty", self.sheet.worn_table.item(armor_row, 1).text())

        self.sheet.equipment_table.selectRow(0)
        self.application.processEvents()
        self.assertFalse(self.sheet.wear_item_button.isEnabled())
        self.assertTrue(self.sheet.remove_item_button.isEnabled())
        self.sheet.remove_item_button.click()
        item = self.repository.list_equipment(self.character_id)[0]
        self.assertEqual("stored", item.state)
        armor_row = next(
            row for row in range(self.sheet.worn_table.rowCount())
            if self.sheet.worn_table.item(row, 0).text() == "Armor"
        )
        self.assertEqual("Empty", self.sheet.worn_table.item(armor_row, 1).text())
        self.assertEqual(1, len(self.repository.list_equipment(self.character_id)))

    def test_feature_records_are_compact_and_expose_hover_and_selected_details(self) -> None:
        self.repository.add_martial_talent(
            self.character_id,
            "Fleet Foot",
            "Athletics",
            "Talent",
            "Move swiftly across the battlefield.",
            catalog_category="Talent",
            prerequisites="Athletics sphere",
        )
        for index in range(5):
            self.repository.add_feat(
                self.character_id,
                f"Feat {index + 1}",
                notes=f"Complete feat description {index + 1}.",
                catalog_category="Pathfinder · Combat",
            )
        for name in ("Reactionary", "Seeker"):
            self.repository.add_trait(
                self.character_id,
                name,
                notes=f"Complete description for {name}.",
                catalog_category="Pathfinder · Trait",
            )
        self.sheet.refresh_all()
        self.assertEqual(3, self.sheet.martial_talent_table.columnCount())
        self.assertEqual(2, self.sheet.feat_table.columnCount())
        self.assertEqual(2, self.sheet.trait_table.columnCount())
        self.assertNotIn(
            "Status",
            {
                self.sheet.martial_talent_table.horizontalHeaderItem(column).text()
                for column in range(self.sheet.martial_talent_table.columnCount())
            },
        )
        self.assertLess(self.sheet.trait_table.height(), self.sheet.feat_table.height())
        self.assertIn(
            "Complete description for Reactionary",
            self.sheet.trait_table.item(0, 0).toolTip(),
        )
        self.sheet.trait_table.setCurrentCell(0, 0)
        self.sheet.trait_table.cellClicked.emit(0, 0)
        self.application.processEvents()
        self.assertIn("Reactionary", self.sheet.feature_details.toPlainText())
        self.assertIn("Automatic effects", self.sheet.feature_details.toPlainText())

    def test_casting_profile_spell_pool_and_per_sphere_dc_are_live(self) -> None:
        self.repository.update_ability_score(self.character_id, "intelligence", 18)
        self.repository.update_casting_profile(
            CastingProfile(
                self.character_id,
                casting_ability="intelligence",
                casting_class_levels=5,
                caster_level=6,
                spell_points_current=9,
                auto_spell_points=True,
                tradition_name="Traditional Magic",
            )
        )
        self.repository.add_spell(
            self.character_id,
            "Destruction Sphere",
            system="Sphere",
            school_or_sphere="Destruction",
            catalog_key="destruction:base",
            catalog_category="Base Sphere",
        )
        self.repository.add_spell(
            self.character_id,
            "Searing Blast",
            system="Sphere",
            school_or_sphere="Destruction",
            catalog_key="destruction:talent:searing-blast",
            catalog_category="Talent",
        )
        self.repository.update_sphere_statistic(
            SphereStatistic(self.character_id, "Destruction", 1, 2, "Implement")
        )

        self.sheet.refresh_all()

        self.assertEqual("17", self.sheet.casting_save_dc.text())
        self.assertEqual("9 / 9", self.sheet.quick_spell_points.text())
        self.assertEqual("6", self.sheet._play_casting_labels["caster_level"].text())
        self.assertEqual("—", self.sheet._play_casting_labels["save_dc"].text())
        headers = [
            self.sheet.spell_table.horizontalHeaderItem(column).text()
            for column in range(self.sheet.spell_table.columnCount())
        ]
        self.assertEqual(
            ["Name", "Spell Cost", "ACTION", "Description", "Sphere", "Duration", "Range", "Save", "SR"],
            headers,
        )
        for removed in ("Active", "Level", "CL", "DC", "Category", "Uses", "Choice", "Prerequisites"):
            self.assertNotIn(removed, headers)
        talent_row = next(
            row
            for row in range(self.sheet.spell_table.rowCount())
            if self.sheet.spell_table.item(row, 0).text() == "Searing Blast"
        )
        self.sheet.spell_table.setCurrentCell(talent_row, 0)
        self.sheet.spell_table.cellClicked.emit(talent_row, 0)
        self.assertEqual("19", self.sheet._play_casting_labels["save_dc"].text())
        self.assertIs(self.sheet.sphere_statistics_section.parent(), self.sheet.magic_canvas)

        self.sheet._spend_spell_point()
        self.assertEqual(8, self.repository.get_casting_profile(self.character_id).spell_points_current)
        self.assertEqual("8 / 9", self.sheet.quick_spell_points.text())


if __name__ == "__main__":
    unittest.main()
