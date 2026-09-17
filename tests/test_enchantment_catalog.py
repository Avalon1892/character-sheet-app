from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.catalogs import DEFAULT_CATALOG
from app.codex_index import build_codex_search_records
from app.database import CharacterRepository
from app.item_enchantments import AGILE, available_enchantments
from app.models import EquipmentItem
from app.ui.dialogs import EquipmentDialog, ItemEnchantmentsDialog


def item(category: str, name: str, **values) -> EquipmentItem:
    defaults = dict(
        id=1, name=name, category=category, quantity=1, weight=0.0,
        equipped=True, ac_bonus=0, bonus_type="untyped", max_dex_bonus=None,
        enhancement_bonus=1,
    )
    defaults.update(values)
    return EquipmentItem(**defaults)


class EnchantmentCatalogTests(unittest.TestCase):
    def test_complete_catalog_and_codex_projection(self) -> None:
        entries = DEFAULT_CATALOG.enchantment_entries()
        self.assertEqual(335, len(entries))
        self.assertEqual(199, len(DEFAULT_CATALOG.enchantment_entries("Weapon")))
        self.assertEqual(136, len(DEFAULT_CATALOG.enchantment_entries("Armor & Shield")))
        self.assertEqual("+1 bonus", DEFAULT_CATALOG.enchantment_entry(AGILE.key)["price_text"])
        records = build_codex_search_records(DEFAULT_CATALOG)
        agile = next(record for record in records if record.get("target") == f"enchantment:{AGILE.key}")
        self.assertIn("Enchantments · Weapon · Melee", agile["category"])

    def test_item_family_filtering(self) -> None:
        sword = available_enchantments(item("Weapon", "Longsword", weapon_damage_type="slashing"))
        armor = available_enchantments(item("Armor", "Full Plate"))
        shield = available_enchantments(item("Shield", "Heavy Steel Shield"))
        amulet = available_enchantments(item(
            "Gear", "Amulet of Mighty Fists",
            catalog_key="reviewed:amulet-of-mighty-fists:customizable",
            enhancement_bonus=0,
        ))
        self.assertIn("Agile", {entry.name for entry in sword})
        self.assertNotIn("Agile", {entry.name for entry in armor})
        self.assertTrue(armor and all("armor" in entry.applies_to for entry in armor))
        self.assertTrue(shield and all("shield" in entry.applies_to for entry in shield))
        self.assertIn("Agile", {entry.name for entry in amulet})


class EnchantmentDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_searchable_property_browser_filters_without_rebuilding_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = CharacterRepository(Path(directory) / "test.db")
            try:
                character_id = repository.create_character("Enchanter", "Pathfinder 1e")
                item_id = repository.add_equipment(
                    character_id, "Longsword", "Weapon", 1, 4, True, 0,
                    "untyped", None, "", state="wielded", enhancement_bonus=1,
                    weapon_damage_type="slashing",
                )
                weapon = next(value for value in repository.list_equipment(character_id) if value.id == item_id)
                dialog = ItemEnchantmentsDialog(repository, character_id, weapon)
                try:
                    self.assertGreater(dialog.available_table.rowCount(), 50)
                    dialog.property_search.setText("agile")
                    self.assertEqual(1, dialog.available_table.rowCount())
                    self.assertEqual("Agile", dialog.available_table.item(0, 0).text())
                finally:
                    dialog.close()
            finally:
                repository.close()

    def test_equipment_editor_previews_masterwork_and_magic_price_live(self) -> None:
        dialog = EquipmentDialog(
            item=item(
                "Weapon",
                "Longsword",
                enhancement_bonus=0,
                masterwork=False,
                value_gp=15,
            )
        )
        try:
            self.assertTrue(dialog.market_price.text().startswith("15 gp"))
            dialog.masterwork.setChecked(True)
            self.assertTrue(dialog.market_price.text().startswith("315 gp"))
            dialog.enhancement_bonus.set_value(1)
            self.assertTrue(dialog.market_price.text().startswith("2315 gp"))
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
