import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QPushButton

from app.content import magic_entries
from app.database import CharacterRepository
from app.drawback_rules import drawback_talent_grant, magic_talent_restriction_reason
from app.sphere_rules import granted_sphere_abilities
from app.ui.character_sheet import (
    MagicTalentCatalogDialog,
    SphereAcquisitionDialog,
    sphere_spell_point_costs,
)
from app.ui.dialogs import DrawbackTalentChoiceDialog
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class MagicCatalogUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "characters.db"
        self.repository = CharacterRepository(database_path)
        self.character_id = self.repository.create_character("Spherecaster", "Spheres")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    def test_magic_browser_groups_and_filters_the_full_catalog(self) -> None:
        dialog = MagicTalentCatalogDialog([], self.sheet)
        self.addCleanup(dialog.close)
        dialog.show()
        dialog.resize(1400, 900)
        QTest.qWait(150)
        self.assertEqual(25, dialog.sphere_list.count())
        self.assertEqual(1696, dialog.results.rowCount())
        self.assertGreaterEqual(dialog.results.columnWidth(1), 360)
        self.assertTrue(dialog.results.wordWrap())
        self.assertEqual(Qt.TextElideMode.ElideNone, dialog.results.textElideMode())

        destruction_row = next(
            row
            for row in range(dialog.sphere_list.count())
            if dialog.sphere_list.item(row).data(Qt.ItemDataRole.UserRole) == "Destruction"
        )
        dialog.sphere_list.setCurrentRow(destruction_row)
        dialog.category.setCurrentIndex(dialog.category.findData("Drawback"))
        self.assertGreater(dialog.results.rowCount(), 0)
        self.assertTrue(
            all(
                dialog.results.item(row, 3).text() == "Destruction"
                for row in range(dialog.results.rowCount())
            )
        )
        dialog.sphere_list.setCurrentRow(0)
        dialog.category.setCurrentIndex(0)
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("toggle")
        )
        self.assertEqual(4, dialog.results.rowCount())
        dialog.close()

    def test_weather_uses_only_reviewed_drawbacks_and_resolves_bonus_talents(self) -> None:
        entries = magic_entries("Weather")
        drawbacks = {
            entry["name"]: entry
            for entry in entries
            if entry["category"] == "Drawback"
        }
        self.assertEqual(
            {
                "Atmospheric Brew", "Limited Weather", "Localized Weather",
                "Personal Mantle", "Small Weather",
            },
            set(drawbacks),
        )
        limited = drawback_talent_grant(drawbacks["Limited Weather"], entries, "Cold")
        self.assertEqual(["Severe Weather"], [entry["name"] for entry in limited.candidates])
        localized = drawback_talent_grant(drawbacks["Localized Weather"], entries)
        self.assertGreater(len(localized.candidates), 1)
        self.assertTrue(
            all(
                entry["category"] in {"Mantle Talent", "Shroud Talent"}
                for entry in localized.candidates
            )
        )
        personal = drawback_talent_grant(drawbacks["Personal Mantle"], entries)
        self.assertEqual(("Mantled Caster",), personal.feat_names)
        self.assertEqual(0, personal.count)

    def test_weather_drawback_editor_stores_direct_granted_talent_choice(self) -> None:
        dialog = SphereAcquisitionDialog(set(), self.sheet, fixed_sphere="Weather")
        localized = next(
            dialog.drawbacks.item(row)
            for row in range(dialog.drawbacks.count())
            if dialog.drawbacks.item(row).text() == "Localized Weather"
        )

        def choose_first(picker) -> int:
            picker.selected_entries = (picker._all[0],)
            return QDialog.DialogCode.Accepted

        localized.setCheckState(Qt.CheckState.Checked)
        with patch.object(DrawbackTalentChoiceDialog, "exec", choose_first):
            dialog._drawback_clicked(localized)
        selected = dialog.drawback_granted_talents["weather:drawback:localized-weather"]
        self.assertEqual(1, len(selected))
        self.assertIn("Granted now:", dialog.drawback_grant.text())
        dialog.close()

    def test_removing_magic_base_sphere_cascades_talents_and_drawbacks(self) -> None:
        entries = magic_entries("Weather")
        limited = next(entry for entry in entries if entry["name"] == "Limited Weather")
        severe = next(entry for entry in entries if entry["name"] == "Severe Weather")
        self.sheet._acquire_magic_sphere(
            "Weather",
            drawback_selections=((limited["key"], "Cold"),),
            drawback_granted_talents={limited["key"]: (severe["key"],)},
        )
        self.assertEqual(3, len([
            spell for spell in self.repository.list_spells(self.character_id)
            if spell.school_or_sphere == "Weather"
        ]))
        self.sheet._refresh_sphere_build()
        table = self.sheet.sphere_build_table
        table.selectRow(next(row for row in range(table.rowCount()) if table.item(row, 0).text() == "Weather"))
        button = next(button for button in self.sheet.magic_sphere_build_panel.findChildren(QPushButton)
                      if button.text() == "Remove selected sphere")
        self.assertTrue(button.isEnabled())
        button.click()
        self.assertFalse(any(
            spell.school_or_sphere == "Weather"
            for spell in self.repository.list_spells(self.character_id)
        ))
        self.sheet._acquire_magic_sphere("Weather")
        self.sheet._refresh_sphere_build()
        table.selectRow(next(row for row in range(table.rowCount()) if table.item(row, 0).text() == "Weather"))
        button.click()
        self.assertFalse(any(
            spell.school_or_sphere == "Weather"
            for spell in self.repository.list_spells(self.character_id)
        ))

    def test_movement_formula_updates_immediately_from_sequence_and_imbue(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.repository.add_spell(
            self.character_id,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="warp:base",
            catalog_category="Base Sphere",
            choice="Teleport",
        )
        self.repository.set_numeric_formula(
            self.character_id,
            "movement",
            0,
            "teleport_speed",
            "=IF(prodigy.imbue.warp_step_between.active, "
            "prodigy.imbue.teleport_distance, sequence.links * 10)",
        )
        self.sheet.refresh_all()
        self.assertEqual(0, self.sheet._calculator().movement_results()["teleport_speed"])

        imbue_index = self.sheet.prodigy_imbue_combo.findData("warp_step_between")
        self.assertGreaterEqual(imbue_index, 0)
        self.sheet.prodigy_imbue_combo.setCurrentIndex(imbue_index)
        self.sheet._store_prodigy_sequence(True, 3)
        self.assertEqual("20 ft", self.sheet.movement_totals["teleport_speed"].text())

        self.sheet._end_prodigy_sequence()
        self.assertEqual("—", self.sheet.movement_totals["teleport_speed"].text())

    def test_magic_browser_and_sheet_add_multiple_talents_in_one_batch(self) -> None:
        dialog = MagicTalentCatalogDialog([], self.sheet)
        self.assertEqual(
            QAbstractItemView.SelectionMode.SingleSelection,
            dialog.results.selectionMode(),
        )
        for row in (0, 1):
            dialog.results.setCurrentCell(row, 1)
            dialog._queue_current_entry()
        self.assertEqual("Add Selected (2)", dialog.add_button.text())
        dialog._accept_selected()
        self.assertEqual(2, len(dialog.selected_entries))

        self.sheet._acquire_magic_sphere("Destruction")
        owned = self.repository.list_spells(self.character_id)
        candidates = tuple(
            entry
            for entry in magic_entries("Destruction")
            if entry["category"] not in {"Base Sphere", "Drawback"}
            and not entry.get("automation", {}).get("choice_type")
            and not magic_talent_restriction_reason(entry, owned)
        )[:2]
        self.assertEqual(2, len(candidates))
        added = self.sheet._add_catalog_batch(
            candidates,
            self.sheet._add_magic_catalog_entry,
            self.sheet._magic_talents_changed,
            "magic talents",
        )
        self.assertEqual(2, added)
        self.assertEqual(3, len(self.repository.list_spells(self.character_id)))

    def test_page_zero_acquires_sphere_and_drawback_before_magic_talent(self) -> None:
        talent = next(
            entry
            for entry in magic_entries("Destruction")
            if entry["category"] == "Blast Type Talent"
        )
        drawback = next(
            entry
            for entry in magic_entries("Destruction")
            if entry["category"] == "Drawback"
        )
        with self.assertRaises(ValueError):
            self.sheet._add_magic_catalog_entry(talent)
        self.sheet._acquire_magic_sphere("Destruction", drawback["key"])
        self.sheet._add_magic_catalog_entry(talent)
        spells = self.repository.list_spells(self.character_id)
        self.assertEqual(3, len(spells))
        self.assertEqual(
            {"Base Sphere", "Drawback", "Blast Type Talent"},
            {spell.catalog_category for spell in spells},
        )
        self.assertTrue(all(spell.source_url for spell in spells))
        with self.assertRaises(ValueError):
            self.sheet._add_magic_catalog_entry(talent)

    def test_magic_talent_toggle_changes_represented_sheet_statistics(self) -> None:
        resolve = next(
            entry for entry in magic_entries("War") if entry["name"] == "Resolve (mandate)"
        )
        self.sheet._acquire_magic_sphere("War")
        self.assertTrue(self.sheet._add_magic_catalog_entry(resolve))
        stored = next(
            spell
            for spell in self.repository.list_spells(self.character_id)
            if spell.catalog_key == resolve["key"]
        )
        self.assertFalse(stored.enabled)
        self.assertEqual("toggle", stored.activation)
        self.repository.set_spell_enabled(self.character_id, stored.id, True)
        self.sheet._magic_talents_changed()
        combat = self.sheet._combat_results()
        self.assertEqual(14, combat["ac"].total)
        self.assertEqual(4, combat["will"].total)

    def test_multiple_drawbacks_store_choices_and_restrict_packages(self) -> None:
        limited = next(
            entry for entry in magic_entries("Warp") if entry["name"] == "Limited Warp"
        )
        personal = next(
            entry for entry in magic_entries("Warp") if entry["name"] == "Personal Warp"
        )
        space_talent = next(
            entry for entry in magic_entries("Warp") if entry["category"] == "Space Talent"
        )
        teleport_talent = next(
            entry for entry in magic_entries("Warp") if entry["name"] == "Distant Teleport"
        )
        self.sheet._acquire_magic_sphere(
            "Warp",
            drawback_selections=(
                (limited["key"], "Teleport — Dim light or darkness"),
                (personal["key"], ""),
            ),
        )
        self.sheet._magic_talents_changed()
        drawbacks = [
            spell
            for spell in self.repository.list_spells(self.character_id)
            if spell.catalog_category == "Drawback"
        ]
        self.assertEqual(2, len(drawbacks))
        self.assertEqual(
            "Teleport — Dim light or darkness",
            next(spell for spell in drawbacks if spell.name == "Limited Warp").choice,
        )
        with self.assertRaisesRegex(ValueError, "retain only Teleport"):
            self.sheet._add_magic_catalog_entry(space_talent)
        self.assertTrue(self.sheet._add_magic_catalog_entry(teleport_talent))
        combo_keys = {
            self.sheet.prodigy_imbue_combo.itemData(index)
            for index in range(self.sheet.prodigy_imbue_combo.count())
        }
        self.assertIn("warp_step_between", combo_keys)
        self.assertNotIn("warp_warping_presence", combo_keys)
        sphere_finishers = {
            option.name
            for option in self.repository.list_sequence_options(self.character_id, "Finisher")
            if option.sphere == "Warp"
        }
        self.assertEqual({"Sudden Shuffle"}, sphere_finishers)

    def test_sphere_acquisition_editor_checks_multiple_drawbacks_and_choices(self) -> None:
        dialog = SphereAcquisitionDialog(set(), self.sheet, fixed_sphere="Warp")
        limited_row = next(
            row
            for row in range(dialog.drawbacks.count())
            if dialog.drawbacks.item(row).text() == "Limited Warp"
        )
        personal_row = next(
            row
            for row in range(dialog.drawbacks.count())
            if dialog.drawbacks.item(row).text() == "Personal Warp"
        )
        limited_item = dialog.drawbacks.item(limited_row)
        personal_item = dialog.drawbacks.item(personal_row)
        limited_item.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(8, dialog.drawback_choice.count())
        dialog.drawback_choice.setCurrentText("Bend Space — Body of water")
        personal_item.setCheckState(Qt.CheckState.Checked)
        selections = dict(dialog.drawback_selections)
        self.assertEqual(2, len(selections))
        self.assertEqual(
            "Bend Space — Body of water",
            selections[str(limited_item.data(Qt.ItemDataRole.UserRole))],
        )
        dialog.close()

    def test_base_sphere_projects_granted_abilities_and_package_choices(self) -> None:
        self.sheet._acquire_magic_sphere("Nature", base_choice="Fire")
        self.sheet._magic_talents_changed()
        names = [
            self.sheet.spell_table.item(row, 0).text()
            for row in range(self.sheet.spell_table.rowCount())
        ]
        self.assertIn("Geomancing: Fire", names)
        self.assertNotIn("Geomancing: Air", names)
        self.assertNotIn("Nature Sphere", names)

    def test_generated_sphere_ability_duration_is_editable_and_persistent(self) -> None:
        self.sheet._acquire_magic_sphere("Warp")
        base = next(
            spell
            for spell in self.repository.list_spells(self.character_id)
            if spell.catalog_category == "Base Sphere"
            and spell.school_or_sphere == "Warp"
        )
        self.repository.update_spell_duration(
            self.character_id, base.id, "Concentration"
        )
        self.sheet._refresh_spells()
        row = next(
            row
            for row in range(self.sheet.spell_table.rowCount())
            if self.sheet.spell_table.item(row, 0).text() == "Teleport"
        )
        self.sheet.spell_table.setCurrentCell(row, 5)
        self.assertEqual("Concentration", self.sheet.spell_table.item(row, 5).text())

        with patch(
            "app.ui.character_sheet.QInputDialog.getText",
            return_value=("1 minute per caster level", True),
        ):
            self.sheet._edit_spell_duration()

        saved = next(
            spell
            for spell in self.repository.list_spells(self.character_id)
            if spell.id == base.id
        )
        self.assertEqual("1 minute per caster level", saved.duration)
        refreshed_row = next(
            row
            for row in range(self.sheet.spell_table.rowCount())
            if self.sheet.spell_table.item(row, 0).text() == "Teleport"
        )
        self.assertEqual(
            "1 minute per caster level",
            self.sheet.spell_table.item(refreshed_row, 5).text(),
        )

    def test_generated_sphere_edit_and_duration_are_distinct_actions(self) -> None:
        self.sheet._acquire_magic_sphere("Warp")
        self.sheet._refresh_spells()
        row = next(
            row
            for row in range(self.sheet.spell_table.rowCount())
            if self.sheet.spell_table.item(row, 0).text() == "Teleport"
        )
        self.sheet.spell_table.setCurrentCell(row, 0)
        with (
            patch.object(self.sheet, "_edit_build_drawbacks") as edit_sphere,
            patch.object(self.sheet, "_edit_spell_duration") as edit_duration,
        ):
            self.sheet._edit_spell()
        edit_sphere.assert_called_once_with(sphere_name="Warp")
        edit_duration.assert_not_called()

    def test_drawbacks_filter_projected_base_abilities_and_prohibited_talents(self) -> None:
        base = SimpleNamespace(
            catalog_category="Base Sphere",
            school_or_sphere="Warp",
            notes="Teleport\nAt will or spend a spell point.\nWarp Talent Types\nBend Space\nFold space.",
            source_url="",
            choice="",
        )
        drawback_entry = next(
            entry for entry in magic_entries("Warp") if entry["name"] == "Limited Warp"
        )
        drawback = SimpleNamespace(
            catalog_category="Drawback",
            school_or_sphere="Warp",
            name="Limited Warp",
            choice="Teleport — Dim light or darkness",
            catalog_key=drawback_entry["key"],
            notes=drawback_entry["description"],
        )
        self.assertEqual(
            ["Teleport"],
            [ability.name for ability in granted_sphere_abilities((base, drawback))],
        )
        space = next(
            entry for entry in magic_entries("Warp") if entry["category"] == "Space Talent"
        )
        self.assertIn(
            "retain only Teleport",
            magic_talent_restriction_reason(space, (base, drawback)),
        )

    def test_sphere_finishers_are_below_base_and_visible_only_during_imbue(self) -> None:
        self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.sheet._acquire_magic_sphere("Warp")
        self.sheet.refresh_all()
        table = self.sheet.sequence_tables["Finisher"]
        self.assertNotIn(
            "Sudden Shuffle",
            {table.item(row, 0).text() for row in range(table.rowCount())},
        )
        self.sheet.prodigy_imbue_combo.setCurrentIndex(
            self.sheet.prodigy_imbue_combo.findData("warp_step_between")
        )
        self.assertNotIn(
            "Sudden Shuffle",
            {table.item(row, 0).text() for row in range(table.rowCount())},
        )
        self.sheet._start_prodigy_sequence()
        names = [table.item(row, 0).text() for row in range(table.rowCount())]
        self.assertIn("Sudden Shuffle", names)
        self.assertGreater(names.index("Sudden Shuffle"), names.index("Resilience"))
        self.sheet._end_prodigy_sequence()
        self.assertNotIn(
            "Sudden Shuffle",
            {table.item(row, 0).text() for row in range(table.rowCount())},
        )

    def test_play_browser_excludes_build_entries_and_cost_parser_handles_choices(self) -> None:
        self.sheet._acquire_magic_sphere("Warp")
        self.sheet._magic_talents_changed()
        warp_row = next(
            row
            for row in range(self.sheet.spell_table.rowCount())
            if self.sheet.spell_table.item(row, 0).text() == "Teleport"
        )
        self.assertEqual("0 / 1", self.sheet.spell_table.item(warp_row, 1).text())
        self.assertEqual("Standard", self.sheet.spell_table.item(warp_row, 2).text())
        self.assertIn("Close", self.sheet.spell_table.item(warp_row, 6).text())
        self.assertNotIn(
            "Warp Sphere",
            [
                self.sheet.spell_table.item(row, 0).text()
                for row in range(self.sheet.spell_table.rowCount())
            ],
        )
        owned = self.repository.list_spells(self.character_id)
        dialog = MagicTalentCatalogDialog(owned, self.sheet, play_mode=True)
        self.assertTrue(dialog._entries)
        self.assertTrue(
            all(
                entry["sphere"] == "Warp"
                and entry["category"] not in {"Base Sphere", "Drawback"}
                for entry in dialog._entries
            )
        )
        dialog.close()
        self.assertEqual(
            (0, 1),
            sphere_spell_point_costs(
                "Use the effect normally. Alternatively, spend 1 spell point for the upgrade."
            ),
        )
        self.assertEqual(
            (2,),
            sphere_spell_point_costs("You must spend two spell points to use this effect."),
        )
        self.assertEqual(
            (1,),
            sphere_spell_point_costs(
                "Cure\nAs a standard action, you may spend a spell point to heal.",
                base_sphere=True,
            ),
        )
        self.assertEqual(
            (1, 2),
            sphere_spell_point_costs(
                "Create\nAs a standard action, spend a spell point to create an object. "
                "You may spend an additional spell point to sustain it.",
                base_sphere=True,
            ),
        )

        self.sheet.spell_table.sortItems(0, Qt.SortOrder.DescendingOrder)
        sorted_names = [
            self.sheet.spell_table.item(row, 0).text()
            for row in range(self.sheet.spell_table.rowCount())
        ]
        self.assertEqual(sorted(sorted_names, reverse=True), sorted_names)


if __name__ == "__main__":
    unittest.main()
