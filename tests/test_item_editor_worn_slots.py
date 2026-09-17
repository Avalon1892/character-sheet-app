from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView

from app.content import item_entries
from app.models import EquipmentItem
from app.ui.components import TranslucentReorderListWidget
from app.ui.dialogs import EquipmentDialog, WornSlotsDialog


class ItemEditorAndWornSlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_existing_item_editor_has_context_title_and_catalog_description(self) -> None:
        entry = next(value for value in item_entries() if value.get("description"))
        item = EquipmentItem(
            1,
            str(entry["name"]),
            "Gear",
            1,
            float(entry.get("weight_lb") or 0),
            False,
            0,
            "untyped",
            None,
            catalog_key=str(entry["key"]),
            catalog_source=str(entry.get("source_group") or ""),
        )
        dialog = EquipmentDialog(item=item)
        try:
            self.assertEqual(f"Edit Item — {item.name}", dialog.windowTitle())
            self.assertGreaterEqual(dialog.width(), 1000)
            self.assertEqual(2, dialog.item_editor_splitter.count())
            self.assertIn(
                str(entry["description"])[:80],
                dialog.item_description.toPlainText(),
            )
        finally:
            dialog.close()

    def test_new_item_editor_uses_create_item_title(self) -> None:
        dialog = EquipmentDialog()
        try:
            self.assertEqual("Create Item", dialog.windowTitle())
        finally:
            dialog.close()

    def test_new_slots_sort_alphabetically_then_remain_freely_reorderable(self) -> None:
        dialog = WornSlotsDialog(("Neck", "Belt"))
        try:
            self.assertIsInstance(dialog.slot_list, TranslucentReorderListWidget)
            self.assertEqual(
                QAbstractItemView.DragDropMode.InternalMove,
                dialog.slot_list.dragDropMode(),
            )
            self.assertEqual(Qt.DropAction.MoveAction, dialog.slot_list.defaultDropAction())
            dialog.slot_name.setText("Arms")
            dialog._add_slot()
            self.assertEqual(("Arms", "Belt", "Neck"), dialog.slots)

            moved = dialog.slot_list.takeItem(2)
            dialog.slot_list.insertItem(0, moved)
            self.assertEqual(("Neck", "Arms", "Belt"), dialog.slots)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
