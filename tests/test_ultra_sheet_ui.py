from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app.database import CharacterRepository
from app.ui.sheet_types import SHEET_TYPE_REGISTRY
from app.ui.ultra_modules import UltraModuleDescriptor, UltraModuleRegistry
from app.ui.ultra_sheet import UltraSheetWidget


class _ProbePanel(QLabel):
    def __init__(self, _owner: object) -> None:
        super().__init__("Extension probe")
        self.refresh_count = 0
        self.last_character_id: int | None = None

    def refresh_from_context(self, context: object) -> None:
        self.refresh_count += 1
        self.last_character_id = int(getattr(context, "character_id"))


class UltraSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.directory.name) / "characters.db"
        )
        self.fighter_id = self.repository.create_character(
            "Core Fighter", "Pathfinder 1e"
        )
        self.repository.add_class_level(
            self.fighter_id,
            "Fighter",
            5,
            "Full",
            "Good",
            "Poor",
            "Poor",
            preset_key="fighter",
            hit_die=10,
            hp_gained=50,
        )
        self.prodigy_id = self.repository.create_character(
            "Sphere Prodigy", "Spheres"
        )
        self.repository.add_class_level(
            self.prodigy_id,
            "Prodigy",
            5,
            "3/4",
            "Poor",
            "Good",
            "Good",
            preset_key="prodigy",
            hit_die=8,
            hp_gained=40,
        )
        self.widgets: list[UltraSheetWidget] = []

    def tearDown(self) -> None:
        for widget in self.widgets:
            widget.close()
        self.application.processEvents()
        self.repository.close()
        self.directory.cleanup()

    def _widget(
        self, registry: UltraModuleRegistry | None = None
    ) -> UltraSheetWidget:
        widget = UltraSheetWidget(self.repository, module_registry=registry)
        self.widgets.append(widget)
        return widget

    @staticmethod
    def _module_is_enabled(widget: UltraSheetWidget, key: str) -> bool:
        return not widget.module_widgets[key].isHidden()

    def test_ultra_is_registered_as_the_fixed_third_sheet_type(self) -> None:
        self.assertEqual(
            ["customizable", "original_spheres", "ultra", "refined"],
            list(SHEET_TYPE_REGISTRY),
        )
        descriptor = SHEET_TYPE_REGISTRY["ultra"]
        self.assertEqual("Ultra Sheet", descriptor.label)
        self.assertFalse(descriptor.supports_customization)

        widget = self._widget()
        self.assertFalse(hasattr(widget, "custom_layouts"))
        self.assertFalse(hasattr(widget, "set_build_mode"))

    def test_pathfinder_fighter_hides_spheres_prodigy_and_companion_modules(self) -> None:
        widget = self._widget()
        widget.load_character(self.fighter_id)

        for key in (
            "play.focus",
            "play.sequence",
            "features.martial",
            "features.magic",
            "magic.summary",
            "magic.traditional",
            "magic.spheres",
            "companion.record",
        ):
            self.assertFalse(self._module_is_enabled(widget, key), key)
        self.assertFalse(
            widget.page_tabs.isTabVisible(widget.page_indices["magic"])
        )
        self.assertFalse(
            widget.page_tabs.isTabVisible(widget.page_indices["companion"])
        )
        self.assertTrue(self._module_is_enabled(widget, "features.special"))
        self.assertEqual(1, widget.pages["features"]._column_count)

    def test_prodigy_reveals_its_spheres_and_sequence_modules(self) -> None:
        widget = self._widget()
        widget.load_character(self.prodigy_id)

        for key in (
            "play.focus",
            "play.sequence",
            "features.martial",
            "features.magic",
            "magic.summary",
            "magic.spheres",
        ):
            self.assertTrue(self._module_is_enabled(widget, key), key)
        self.assertTrue(
            widget.page_tabs.isTabVisible(widget.page_indices["magic"])
        )
        self.assertFalse(self._module_is_enabled(widget, "companion.record"))
        self.assertFalse(
            widget.page_tabs.isTabVisible(widget.page_indices["companion"])
        )
        self.assertEqual(2, widget.pages["features"]._column_count)

    def test_module_registry_accepts_an_independent_extension_panel(self) -> None:
        registry = UltraModuleRegistry()
        registry.register(
            UltraModuleDescriptor(
                "play.extension_probe",
                "play",
                999,
                _ProbePanel,
                requires=frozenset({"universal"}),
            )
        )
        widget = self._widget(registry)
        widget.load_character(self.fighter_id)

        self.assertIn("play.extension_probe", widget.module_widgets)
        probe = widget.module_widgets["play.extension_probe"]
        self.assertIsInstance(probe, _ProbePanel)
        self.assertEqual(1, probe.refresh_count)
        self.assertEqual(self.fighter_id, probe.last_character_id)
        self.assertTrue(self._module_is_enabled(widget, "play.extension_probe"))

    def test_extension_registry_can_replace_a_builtin_panel_by_stable_key(self) -> None:
        registry = UltraModuleRegistry()
        registry.register(
            UltraModuleDescriptor(
                "play.core",
                "play",
                10,
                _ProbePanel,
                requires=frozenset({"universal"}),
                full_width=True,
            )
        )
        widget = self._widget(registry)
        widget.load_character(self.prodigy_id)

        probe = widget.module_widgets["play.core"]
        self.assertIsInstance(probe, _ProbePanel)
        self.assertEqual(1, probe.refresh_count)


if __name__ == "__main__":
    unittest.main()
