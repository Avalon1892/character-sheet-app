from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.inventory_organization import InventoryOrganizationService
from app.item_containers import (
    EXTRADIMENSIONAL_STORAGE_TAG,
    INVENTORY_CONTAINER_TAG,
    carried_inventory_weight,
    item_container_tags,
)
from app.services.character_calculations import CharacterCalculationService
from app.transfer import export_character, import_character
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.dialogs import EquipmentDialog
from app.ui.inventory_dialog import InventoryOrganizerDialog


class InventoryContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "containers.db")
        self.character_id = self.repository.create_character("Porter", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _item(
        self, name: str, weight: float, *, catalog_key: str = "", category: str = "Gear"
    ) -> int:
        return self.repository.add_equipment(
            self.character_id,
            name,
            category,
            1,
            weight,
            False,
            0,
            "untyped",
            None,
            "Description",
            catalog_key=catalog_key,
            state="carried",
        )

    def test_container_tags_grouping_and_fixed_weight(self) -> None:
        bag_id = self._item(
            "Bag of Holding (Type I)",
            15,
            catalog_key="pathfinder:items:K1PJo4dWwVcYbTp7",
        )
        anvil_id = self._item("Anvil", 100)
        service = InventoryOrganizationService(self.repository, self.character_id)
        service.move_item(anvil_id, container_equipment_id=bag_id)

        placement = next(
            value for value in service.snapshot().placements
            if value.equipment_id == anvil_id
        )
        self.assertEqual(bag_id, placement.container_equipment_id)
        self.assertEqual("Adventuring Gear", placement.category)
        container_group = service.container_groups()[0]
        self.assertEqual(bag_id, container_group.container.item.id)
        self.assertEqual("Adventuring Gear", container_group.categories[0].category)
        self.assertEqual("General", container_group.categories[0].subcategories[0][0])
        self.assertEqual(100, container_group.contents_weight)
        self.assertEqual(250, container_group.capacity_lb)
        self.assertFalse(
            any(
                value.item.id == anvil_id
                for group in service.groups()
                for _subcategory, values in group.subcategories
                for value in values
            )
        )

        equipment = self.repository.list_equipment(self.character_id)
        bag = next(value for value in equipment if value.id == bag_id)
        self.assertIn(INVENTORY_CONTAINER_TAG, item_container_tags(bag))
        self.assertIn(EXTRADIMENSIONAL_STORAGE_TAG, item_container_tags(bag))
        self.assertEqual(15, carried_inventory_weight(equipment, service.snapshot().placements))
        self.assertEqual(
            15,
            CharacterCalculationService(
                self.repository, self.character_id
            ).encumbrance().weight,
        )

    def test_ordinary_container_keeps_contents_weight_and_moving_out_clears_parent(self) -> None:
        pack_id = self._item(
            "Backpack, common",
            2,
            catalog_key="pathfinder:items:lSCPUK5Ea6R0t4fz",
        )
        rope_id = self._item("Rope", 10)
        service = InventoryOrganizationService(self.repository, self.character_id)
        service.move_item(rope_id, container_equipment_id=pack_id)
        self.assertEqual(
            12,
            carried_inventory_weight(
                self.repository.list_equipment(self.character_id),
                service.snapshot().placements,
            ),
        )
        service.move_item(rope_id, "Tools & Skill Kits", "Climbing")
        placement = next(
            value for value in service.snapshot().placements
            if value.equipment_id == rope_id
        )
        self.assertIsNone(placement.container_equipment_id)

    def test_self_and_cycle_containment_are_rejected(self) -> None:
        first = self._item("Backpack, common", 2)
        second = self._item("Backpack, masterwork", 4)
        service = InventoryOrganizationService(self.repository, self.character_id)
        with self.assertRaises(ValueError):
            service.move_item(first, container_equipment_id=first)
        service.move_item(first, container_equipment_id=second)
        with self.assertRaises(ValueError):
            service.move_item(second, container_equipment_id=first)

    def test_export_import_remaps_container_equipment_id(self) -> None:
        bag_id = self._item("Backpack, common", 2)
        child_id = self._item("Chalk", 1)
        service = InventoryOrganizationService(self.repository, self.character_id)
        service.move_item(child_id, container_equipment_id=bag_id)
        path = Path(self.directory.name) / "container.character.json"
        export_character(self.repository, self.character_id, path)
        imported_id = import_character(self.repository, path)
        imported = InventoryOrganizationService(self.repository, imported_id)
        placement = imported.snapshot().placements[0]
        self.assertNotEqual(bag_id, placement.container_equipment_id)
        imported_ids = {
            value.id for value in self.repository.list_equipment(imported_id)
        }
        self.assertIn(placement.container_equipment_id, imported_ids)

    def test_organizer_double_click_edits_and_container_editor_lists_contents(self) -> None:
        bag_id = self._item("Backpack, common", 2)
        child_id = self._item("Trail rations", 1)
        service = InventoryOrganizationService(self.repository, self.character_id)
        service.move_item(child_id, container_equipment_id=bag_id)
        opened: list[int] = []
        dialog = InventoryOrganizerDialog(service, edit_item=opened.append)
        dialog.show()
        self.application.processEvents()
        normal_row = next(
            target.item(index)
            for target in dialog.drop_lists.values()
            for index in range(target.count())
            if target.item(index).data(Qt.ItemDataRole.UserRole) == bag_id
        )
        dialog._item_double_clicked(normal_row)
        self.assertEqual([bag_id], opened)
        self.assertIn(bag_id, dialog.container_columns)

        bag = next(
            value for value in self.repository.list_equipment(self.character_id)
            if value.id == bag_id
        )
        editor = EquipmentDialog(
            item=bag, contained_items=service.contents(bag_id)
        )
        self.assertIn("Trail rations", editor.item_description.toPlainText())
        editor.close()
        dialog.close()

    def test_regular_inventory_visually_nests_children_below_container(self) -> None:
        bag_id = self._item("Backpack, common", 2)
        child_id = self._item("Torch", 1)
        InventoryOrganizationService(
            self.repository, self.character_id
        ).move_item(child_id, container_equipment_id=bag_id)
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character_id)
        ids = [
            int(sheet.equipment_table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            for row in range(sheet.equipment_table.rowCount())
        ]
        bag_row = ids.index(bag_id)
        child_row = ids.index(child_id)
        self.assertEqual(bag_row + 1, child_row)
        self.assertFalse(sheet.equipment_table.item(bag_row, 0).icon().isNull())
        self.assertFalse(sheet.equipment_table.item(child_row, 0).icon().isNull())
        self.assertTrue(sheet.equipment_table.item(child_row, 0).font().italic())
        sheet.close()


if __name__ == "__main__":
    unittest.main()
