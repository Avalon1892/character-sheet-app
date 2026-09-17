from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app.database import CharacterRepository
from app.recovery import FullRestEngine
from app.spellbook import SpellBookService
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.spellbook_dialog import SpellBookDialog


class SpellBookServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "spellbook.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_prepared_casting_never_changes_preparation_and_full_rest_restores_it(self) -> None:
        character = self.repository.create_character("Prepared", "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            preset_key="wizard", hit_die=6, hp_gained=18,
        )
        spell_id = self.repository.add_spell(
            character, "Fireball", system="Prepared", level=3,
            school_or_sphere="Evocation", notes="A bright explosive burst.",
        )
        self.repository.add_prepared_spell(
            character, class_id, spell_id, prepared_count=2
        )
        service = SpellBookService(self.repository, character)
        key = f"traditional:spell:{spell_id}"

        self.assertEqual("2 / 2 prepared", service.traditional_entries()[0].usage_text)
        self.assertTrue(service.cast_traditional(key).changed)
        self.assertTrue(service.cast_traditional(key).changed)
        self.assertFalse(service.cast_traditional(key).changed)
        prepared = self.repository.list_prepared_spells(character)[0]
        self.assertEqual((2, 2, 0), (prepared.prepared_count, prepared.used_count, prepared.remaining))
        self.assertTrue(service.set_traditional_remaining(key, 1).changed)
        prepared = self.repository.list_prepared_spells(character)[0]
        self.assertEqual((2, 1, 1), (prepared.prepared_count, prepared.used_count, prepared.remaining))

        FullRestEngine(self.repository, character).perform({"prepared_spells": True})
        prepared = self.repository.list_prepared_spells(character)[0]
        self.assertEqual((2, 0, 2), (prepared.prepared_count, prepared.used_count, prepared.remaining))

    def test_spontaneous_spells_share_their_level_resource_and_stop_at_zero(self) -> None:
        character = self.repository.create_character("Spontaneous", "Pathfinder 1e")
        self.repository.update_ability_score(character, "charisma", 18)
        self.repository.add_class_level(
            character, "Sorcerer", 6, "1/2", "Poor", "Poor", "Good",
            preset_key="sorcerer", hit_die=6, hp_gained=18,
        )
        first_id = self.repository.add_spell(
            character, "Fireball", system="Spontaneous", level=3,
            school_or_sphere="Evocation",
        )
        second_id = self.repository.add_spell(
            character, "Haste", system="Spontaneous", level=3,
            school_or_sphere="Transmutation",
        )
        service = SpellBookService(self.repository, character)
        entries = {entry.spell_id: entry for entry in service.traditional_entries()}
        maximum = entries[first_id].maximum
        self.assertGreater(maximum, 0)

        self.assertTrue(service.cast_traditional(entries[first_id].key).changed)
        refreshed = {entry.spell_id: entry for entry in service.traditional_entries()}
        self.assertEqual(maximum - 1, refreshed[first_id].current)
        self.assertEqual(maximum - 1, refreshed[second_id].current)
        for _ in range(maximum - 1):
            self.assertTrue(service.cast_traditional(refreshed[second_id].key).changed)
            refreshed = {entry.spell_id: entry for entry in service.traditional_entries()}
        self.assertFalse(service.cast_traditional(refreshed[first_id].key).changed)
        self.assertEqual(0, service.traditional_entries()[0].current)

    def test_sphere_use_spends_temporary_points_first_and_obeys_cost(self) -> None:
        character = self.repository.create_character("Spherecaster", "Spheres")
        profile = self.repository.get_casting_profile(character)
        self.repository.update_casting_profile(
            replace(profile, spell_points_current=2, spell_points_temporary=1)
        )
        self.repository.add_spell(
            character,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            notes=(
                "Teleport\nYou may teleport nearby at no cost. You may spend "
                "1 spell point to increase the range."
            ),
            catalog_key="warp:base",
            catalog_category="Base Sphere",
        )
        service = SpellBookService(self.repository, character)
        teleport = next(
            entry for entry in service.sphere_entries() if entry.name == "Teleport"
        )
        self.assertEqual((0, 1), teleport.costs)
        self.assertTrue(service.use_sphere(teleport.key, 1).changed)
        profile = self.repository.get_casting_profile(character)
        self.assertEqual((2, 0), (profile.spell_points_current, profile.spell_points_temporary))
        self.assertFalse(service.use_sphere(teleport.key, 4).changed)
        self.assertEqual(2, self.repository.get_casting_profile(character).spell_points_current)
        self.assertTrue(service.use_sphere(teleport.key, 1).changed)
        self.assertTrue(service.use_sphere(teleport.key, 1).changed)
        self.assertFalse(service.use_sphere(teleport.key, 1).changed)
        profile = self.repository.get_casting_profile(character)
        self.assertEqual((0, 0), (profile.spell_points_current, profile.spell_points_temporary))


class SpellBookUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "spellbook-ui.db")
        self.character = self.repository.create_character("Book UI", "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            self.character, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            preset_key="wizard", hit_die=6, hp_gained=18,
        )
        self.fireball = self.repository.add_spell(
            self.character, "Fireball", system="Prepared", level=3,
            school_or_sphere="Evocation",
            notes="A unique crimson explosion fills the target area.",
        )
        self.repository.add_prepared_spell(
            self.character, class_id, self.fireball, prepared_count=2
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_wide_dialog_searches_current_entries_with_400ms_debounce_and_casts(self) -> None:
        dialog = SpellBookDialog(SpellBookService(self.repository, self.character))
        dialog.show()
        self.application.processEvents()
        key = f"traditional:spell:{self.fireball}"
        self.assertGreaterEqual(dialog.width(), 1080)
        self.assertEqual(400, dialog.search_debounce.timer.interval())
        self.assertIn(key, dialog.entry_cards)
        self.assertIn("crimson explosion", dialog.entry_cards[key].toolTip())
        self.assertTrue(
            dialog.tabs.isTabVisible(dialog.tabs.indexOf(dialog.traditional_scroll))
        )
        self.assertFalse(
            dialog.tabs.isTabVisible(dialog.tabs.indexOf(dialog.sphere_scroll))
        )
        level_headings = {
            label.text()
            for label in dialog.traditional_canvas.findChildren(QLabel)
            if label.objectName() == "spellBookSectionTitle"
        }
        self.assertEqual(
            {"LEVEL 0", "LEVEL 1", "LEVEL 2", "LEVEL 3"}, level_headings
        )

        dialog.search.setText("evocation")
        dialog.search_debounce.flush()
        self.assertIn(key, dialog.entry_cards)
        dialog.search.setText("crimson")
        dialog.search_debounce.flush()
        self.assertIn(key, dialog.entry_cards)
        dialog.search.setText("not in this character")
        dialog.search_debounce.flush()
        self.assertNotIn(key, dialog.entry_cards)

        dialog.search.clear()
        dialog.search_debounce.flush()
        dialog.cast_buttons[key].click()
        self.application.processEvents()
        self.assertEqual("1 / 2 prepared", dialog.usage_labels[key].text())
        self.assertEqual(1, dialog.usage_editors[key].value())
        dialog.close()

    def test_existing_sheet_keeps_tables_and_opens_one_modeless_spell_book(self) -> None:
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        self.assertEqual(1, sheet.spells_known_table.rowCount())
        sheet.open_spell_book_button.click()
        self.application.processEvents()
        first = sheet._spell_book_dialog
        self.assertIsNotNone(first)
        self.assertTrue(first.isVisible())
        key = f"traditional:spell:{self.fireball}"
        first.cast_buttons[key].click()
        self.application.processEvents()
        self.assertEqual("1 / 2 prepared", first.usage_labels[key].text())
        FullRestEngine(self.repository, self.character).perform(
            {"prepared_spells": True}
        )
        sheet.refresh_all()
        self.application.processEvents()
        self.assertEqual("2 / 2 prepared", first.usage_labels[key].text())
        sheet.open_spell_book_button.click()
        self.assertIs(first, sheet._spell_book_dialog)
        self.assertEqual(1, sheet.spells_known_table.rowCount())
        sheet.close()

    def test_sphere_cards_use_one_button_per_positive_cost_and_no_zero_cost_button(self) -> None:
        profile = self.repository.get_casting_profile(self.character)
        self.repository.update_casting_profile(
            replace(profile, spell_points_current=3)
        )
        self.repository.add_spell(
            self.character,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="warp:base",
            catalog_category="Base Sphere",
            notes=(
                "Teleport\nTeleport nearby without spending spell points. "
                "You may spend 1 spell point to increase the range."
            ),
        )
        self.repository.add_spell(
            self.character,
            "Harmless Spatial Mark",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="warp:mark",
            catalog_category="Talent",
            notes="Place a harmless spatial mark without spending spell points.",
        )
        dialog = SpellBookDialog(SpellBookService(self.repository, self.character))
        dialog.show()
        self.application.processEvents()
        teleport = next(
            entry
            for entry in dialog.service.sphere_entries()
            if entry.name == "Teleport"
        )
        mark = next(
            entry
            for entry in dialog.service.sphere_entries()
            if entry.name == "Harmless Spatial Mark"
        )

        self.assertEqual({1}, set(dialog.sphere_use_buttons[teleport.key]))
        self.assertNotIn(0, dialog.sphere_use_buttons[teleport.key])
        self.assertEqual(
            "At Will · 0 SP", dialog.sphere_at_will_labels[teleport.key].text()
        )
        self.assertNotIn(mark.key, dialog.sphere_use_buttons)
        self.assertNotIn(mark.key, dialog.sphere_at_will_labels)
        self.assertTrue(
            dialog.tabs.isTabVisible(dialog.tabs.indexOf(dialog.traditional_scroll))
        )
        self.assertTrue(
            dialog.tabs.isTabVisible(dialog.tabs.indexOf(dialog.sphere_scroll))
        )
        dialog.tabs.setCurrentWidget(dialog.sphere_scroll)
        dialog.sphere_use_buttons[teleport.key][1].click()
        self.application.processEvents()
        self.assertEqual(
            2, self.repository.get_casting_profile(self.character).spell_points_current
        )
        self.assertIs(dialog.sphere_scroll, dialog.tabs.currentWidget())
        dialog.close()

    def test_sphere_only_book_opens_sphere_page_and_hides_traditional_page(self) -> None:
        character = self.repository.create_character("Sphere only", "Spheres")
        self.repository.add_spell(
            character,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_key="warp:base",
            catalog_category="Base Sphere",
            notes="Teleport nearby without spending spell points.",
        )
        dialog = SpellBookDialog(SpellBookService(self.repository, character))
        dialog.show()
        self.application.processEvents()

        self.assertFalse(
            dialog.tabs.isTabVisible(dialog.tabs.indexOf(dialog.traditional_scroll))
        )
        self.assertTrue(
            dialog.tabs.isTabVisible(dialog.tabs.indexOf(dialog.sphere_scroll))
        )
        self.assertIs(dialog.sphere_scroll, dialog.tabs.currentWidget())
        dialog.close()

    def test_empty_book_hides_both_pages(self) -> None:
        character = self.repository.create_character("No magic", "Pathfinder 1e")
        dialog = SpellBookDialog(SpellBookService(self.repository, character))
        dialog.show()
        self.application.processEvents()

        self.assertFalse(dialog.tabs.isVisible())
        self.assertFalse(dialog.empty_book.isHidden())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
