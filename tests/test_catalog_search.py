import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.catalog_search import CatalogSearchIndex
from app.ui.dialogs import ItemCatalogDialog


class CatalogSearchIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = (
            {"key": "sword", "name": "Longsword", "description": "A martial blade."},
            {"key": "headband", "name": "Headband", "description": "Enhances Wisdom."},
            {"key": "manual", "name": "Manual", "description": "Describes a longsword."},
        )
        self.index = CatalogSearchIndex(self.records)

    def test_modes_search_only_the_requested_fields(self) -> None:
        self.assertEqual(
            ("sword",),
            tuple(item["key"] for item in self.index.search("longsword", "name").records),
        )
        self.assertEqual(
            ("manual",),
            tuple(item["key"] for item in self.index.search("longsword", "description").records),
        )
        self.assertEqual(
            ("sword", "manual"),
            tuple(item["key"] for item in self.index.search("longsword", "both").records),
        )

    def test_result_limit_reports_total_without_rendering_every_match(self) -> None:
        result = self.index.search("", limit=2)
        self.assertEqual(3, result.total)
        self.assertEqual(2, len(result.records))
        self.assertTrue(result.limited)


class ItemCatalogSearchUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_item_browser_defaults_to_fast_name_search_and_bounded_rows(self) -> None:
        dialog = ItemCatalogDialog()
        try:
            self.assertEqual("name", dialog.search_mode.currentData())
            self.assertLessEqual(dialog.results.rowCount(), dialog.RESULT_LIMIT)
            self.assertIn("first", dialog.result_status.text().casefold())
            dialog.search.setText("Headband of Inspired Wisdom +6")
            self.assertTrue(dialog.search_debounce.timer.isActive())
            dialog.search_debounce.flush()
            self.assertGreater(dialog.results.rowCount(), 0)
            self.assertTrue(
                all(
                    "headband of inspired wisdom +6"
                    in dialog.results.item(row, 0).text().casefold()
                    for row in range(dialog.results.rowCount())
                )
            )
        finally:
            dialog.close()

    def test_item_browser_filters_by_optional_gold_range(self) -> None:
        dialog = ItemCatalogDialog()
        try:
            dialog.price_range.minimum.setValue(1_000)
            dialog.price_range.maximum.setValue(2_000)
            result = dialog._filtered()
            self.assertGreater(result.total, 0)
            self.assertTrue(
                all(
                    1_000 <= float(entry.get("price_gp") or 0) <= 2_000
                    for entry in result.records
                )
            )
            dialog.price_range.minimum.setValue(0)
            dialog.price_range.maximum.setValue(0)
            self.assertGreater(dialog._filtered().total, result.total)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
