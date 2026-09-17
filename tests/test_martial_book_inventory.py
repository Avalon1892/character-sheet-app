from __future__ import annotations

from dataclasses import replace
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from app.database import CharacterRepository
from app.inventory_organization import InventoryOrganizationService
from app.martial_book import (
    FOCUS_EXPEND,
    FOCUS_MAINTAIN,
    MartialBookService,
    martial_focus_usage,
)
from app.transfer import export_character, import_character
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.inventory_dialog import InventoryOrganizerDialog
from app.ui.martial_book_dialog import MartialBookDialog


class MartialBookAndInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "book-inventory.db")
        self.character = self.repository.create_character("Organizer", "Spheres")

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def _item(self, name: str, category: str, catalog_key: str = "") -> int:
        return self.repository.add_equipment(
            self.character,
            name,
            category,
            1,
            1.0,
            False,
            0,
            "untyped",
            None,
            "Useful item details.",
            catalog_key=catalog_key,
            state="carried",
        )

    def test_focus_classifier_distinguishes_maintained_and_expended_focus(self) -> None:
        self.assertEqual(
            FOCUS_MAINTAIN,
            martial_focus_usage("While you have martial focus, increase your reach."),
        )
        self.assertEqual(
            FOCUS_EXPEND,
            martial_focus_usage("You may expend your martial focus to reroll."),
        )
        self.assertEqual(
            FOCUS_EXPEND,
            martial_focus_usage("You may spend a move action and your martial focus to improve the effect."),
        )
        self.assertEqual(
            FOCUS_MAINTAIN,
            martial_focus_usage("So long as you have martial focus, this benefit applies."),
        )
        self.assertNotEqual(
            FOCUS_EXPEND,
            martial_focus_usage("You may spend a move action to regain your martial focus."),
        )

    def test_martial_book_groups_owned_talents_and_spends_focus(self) -> None:
        expend_id = self.repository.add_martial_talent(
            self.character,
            "Explosive Counter",
            "Shield",
            notes="You may expend your martial focus to use this counter.",
            catalog_category="Counter Talent",
        )
        self.repository.add_martial_talent(
            self.character,
            "Focused Guard",
            "Shield",
            notes="While you possess martial focus, gain this benefit.",
            catalog_category="Talent",
        )
        self.repository.add_martial_talent(
            self.character,
            "Shield Sphere",
            "Shield",
            talent_type="Base Sphere",
            catalog_category="Base Sphere",
        )
        service = MartialBookService(self.repository, self.character)
        entries = service.entries()
        self.assertEqual(2, len(entries))
        expend = next(item for item in entries if item.name == "Explosive Counter")
        maintained = next(item for item in entries if item.name == "Focused Guard")
        self.assertEqual(FOCUS_EXPEND, expend.focus_usage)
        self.assertEqual(FOCUS_MAINTAIN, maintained.focus_usage)

        result = service.use_talent(f"martial:{expend_id}")
        self.assertTrue(result.changed)
        self.assertEqual(0, self.repository.get_martial_focus(self.character).current)
        self.assertFalse(service.use_talent(f"martial:{expend_id}").changed)

    def test_martial_book_dialog_is_wide_searchable_and_live(self) -> None:
        talent_id = self.repository.add_martial_talent(
            self.character,
            "Meteoric Throw",
            "Brute",
            notes="Expend your martial focus to throw the target with tremendous force.",
            catalog_category="Talent",
        )
        dialog = MartialBookDialog(MartialBookService(self.repository, self.character))
        dialog.show()
        self.application.processEvents()
        key = f"martial:{talent_id}"
        self.assertGreaterEqual(dialog.width(), 1080)
        self.assertEqual(400, dialog.search_debounce.timer.interval())
        self.assertIn(key, dialog.entry_cards)
        self.assertIn("tremendous force", dialog.entry_cards[key].toolTip())
        dialog.use_buttons[key].click()
        self.application.processEvents()
        self.assertEqual(0, self.repository.get_martial_focus(self.character).current)
        self.assertFalse(dialog.use_buttons[key].isEnabled())
        dialog.search.setText("not owned")
        dialog.search_debounce.flush()
        self.assertNotIn(key, dialog.entry_cards)
        dialog.close()

    def test_inventory_automatic_groups_custom_move_undo_and_reset(self) -> None:
        sword = self._item(
            "Longsword",
            "Weapon",
            "pathfinder:weapons-and-ammo:zWRlna42PMJVX6un",
        )
        self._item(
            "Leather armor",
            "Armor",
            "pathfinder:armors-and-shields:6YCQkebsf4vR508H",
        )
        self._item(
            "Acid",
            "Consumable",
            "pathfinder:items:qozwdcnkxulxsepe",
        )
        service = InventoryOrganizationService(self.repository, self.character)
        automatic = {
            (group.category, subcategory)
            for group in service.groups()
            for subcategory, _items in group.subcategories
        }
        self.assertIn(("Weapons", "Martial"), automatic)
        self.assertIn(("Armor", "Light"), automatic)
        self.assertTrue(any(category == "Alchemical Items" for category, _ in automatic))

        service.add_custom_group("Field Kit", "Ready")
        dialog = InventoryOrganizerDialog(service)
        dialog.show()
        self.application.processEvents()
        self.assertIn(("Field Kit", "Ready"), dialog.drop_lists)
        dialog._move_item(sword, "Field Kit", "Ready")
        self.assertEqual("Field Kit", service.snapshot().placements[0].category)
        dialog._reset_item(sword)
        self.assertFalse(service.snapshot().placements)
        self.assertIn(("Weapons", "Martial"), dialog.drop_lists)
        dialog._move_item(sword, "Field Kit", "Ready")
        dialog.drop_lists[("Field Kit", "Ready")].setFocus()
        QTest.keyClick(
            dialog,
            Qt.Key.Key_Z,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.application.processEvents()
        self.assertFalse(service.snapshot().placements)
        self.assertIn(("Weapons", "Martial"), dialog.drop_lists)

        service.move_item(sword, "Field Kit", "Ready")
        service.reset()
        self.assertFalse(service.snapshot().placements)
        self.assertFalse(service.snapshot().custom_groups)
        dialog.close()

    def test_inventory_search_wraps_long_names_and_organization_transfers(self) -> None:
        item_id = self._item(
            "A deliberately extremely long adventuring item name that must wrap in its row",
            "Gear",
        )
        service = InventoryOrganizationService(self.repository, self.character)
        service.add_custom_group("Expedition", "Pack")
        service.move_item(item_id, "Expedition", "Pack")
        dialog = InventoryOrganizerDialog(service)
        target = dialog.drop_lists[("Expedition", "Pack")]
        self.assertGreater(target.item(0).sizeHint().height(), 36)
        dialog.search.setText("useful item details")
        dialog.search_debounce.flush()
        self.assertIn(("Expedition", "Pack"), dialog.drop_lists)
        dialog.close()

        export_path = Path(self.root.name) / "character.json"
        export_character(self.repository, self.character, export_path)
        imported = import_character(self.repository, export_path)
        imported_snapshot = InventoryOrganizationService(
            self.repository, imported
        ).snapshot()
        self.assertEqual("Expedition", imported_snapshot.placements[0].category)
        self.assertEqual("Pack", imported_snapshot.custom_groups[0].subcategory)

    def test_sheet_keeps_existing_tables_and_opens_one_of_each_window(self) -> None:
        self.repository.add_martial_talent(
            self.character, "Fast Draw", "Equipment", catalog_category="Talent"
        )
        self._item("Rope", "Gear")
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        martial_rows = sheet.martial_talent_table.rowCount()
        equipment_rows = sheet.equipment_table.rowCount()
        sheet.open_martial_book_button.click()
        sheet.open_inventory_button.click()
        self.application.processEvents()
        martial = sheet._martial_book_dialog
        inventory = sheet._inventory_dialog
        self.assertIsNotNone(martial)
        self.assertIsNotNone(inventory)
        sheet.open_martial_book_button.click()
        sheet.open_inventory_button.click()
        self.assertIs(martial, sheet._martial_book_dialog)
        self.assertIs(inventory, sheet._inventory_dialog)
        self.assertEqual(martial_rows, sheet.martial_talent_table.rowCount())
        self.assertEqual(equipment_rows, sheet.equipment_table.rowCount())
        sheet.close()


if __name__ == "__main__":
    unittest.main()
