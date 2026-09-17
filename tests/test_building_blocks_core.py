from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from app.building_blocks.actions import ACTIONS, ActionContext
from app.building_blocks.bindings import BINDINGS
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import (
    BUILTIN_BLOCK_REGISTRY,
    CELL_TYPE_REGISTRY,
    BlockRegistry,
    CellTypeDescriptor,
    register_builtin_blocks,
)
from app.building_blocks.schemas import (
    BlockDefinition,
    CellDefinition,
    CellOverride,
)
from app.database import CharacterRepository


class BuildingBlocksCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.path = Path(self.root.name) / "characters.db"
        self.characters = CharacterRepository(self.path)
        self.character_id = self.characters.create_character("Builder", "Pathfinder 1e")
        self.presentation = BuildingBlockRepository(self.path)
        self.registry = register_builtin_blocks()
        self.presentation.ensure_character(self.character_id, self.registry)

    def tearDown(self) -> None:
        self.presentation.close()
        self.characters.close()
        self.root.cleanup()

    def custom_definition(self, key: str = "user:test") -> BlockDefinition:
        return BlockDefinition(
            key, "Test Block", "Custom", width=420, height=220,
            cells=(
                CellDefinition("title", "label", "TEST", 10, 10, 390, 30),
                CellDefinition("value", "number", "Value", 20, 60, 120, 32, binding="hit_points.current"),
            ),
        )

    def test_registries_are_extensible_without_ui_changes(self) -> None:
        self.assertEqual(8, len(CELL_TYPE_REGISTRY.all()))
        registry = BlockRegistry()
        sample = self.custom_definition("future:sample")
        registry.register(sample)
        self.assertIs(sample, registry.get("future:sample"))
        with self.assertRaises(ValueError):
            registry.register(sample)
        future_type = CellTypeDescriptor(
            "future.badge", "Future badge", 50, 20,
            runtime_factory=lambda parent, cell, context: __import__(
                "PySide6.QtWidgets", fromlist=["QLabel"]
            ).QLabel(cell.label, parent),
        )
        CELL_TYPE_REGISTRY.register(future_type)
        try:
            self.assertIs(future_type, CELL_TYPE_REGISTRY.get("future.badge"))
        finally:
            CELL_TYPE_REGISTRY.unregister("future.badge")

    def test_default_tabs_and_builtin_instances_are_seeded(self) -> None:
        tabs = self.presentation.list_tabs(self.character_id)
        self.assertEqual(
            ["build", "core", "inventory", "magic", "companion", "crafting"],
            [tab.key for tab in tabs],
        )
        instances = self.presentation.list_instances(self.character_id)
        self.assertEqual(len(self.registry.all()), len(instances))
        self.assertTrue(all(item.template_snapshot for item in instances))
        visibility = {item.template_key: item.visible for item in instances}
        self.assertTrue(visibility["builtin:classic_statistics"])
        self.assertTrue(visibility["builtin:movement"])
        self.assertFalse(visibility["builtin:abilities"])
        self.assertFalse(visibility["builtin:combat_defense"])

    def test_legacy_default_migrates_to_classic_stats_without_touching_custom_layouts(self) -> None:
        legacy = BlockRegistry()
        for section in ("abilities", "combat_defense"):
            legacy.register(BlockDefinition(
                key=f"builtin:{section}",
                name=section.replace("_", " ").title(),
                category="Legacy",
                builtin=True,
                section_key=section,
                default_tab="core",
            ))
        old_character = self.characters.create_character("Legacy", "Spheres")
        self.presentation.ensure_character(old_character, legacy)
        self.characters.save_character_sheet_layout(
            old_character,
            {
                "freeform": (
                    '{"magic_talents":{"page":"magic","x":372,"y":12,'
                    '"width":1536,"height":412}}'
                )
            },
        )
        self.presentation.ensure_character(old_character, self.registry)
        visible = {
            item.instance_key: item.visible
            for item in self.presentation.list_instances(old_character)
        }
        self.assertTrue(visible["builtin:classic_statistics"])
        self.assertFalse(visible["builtin:abilities"])
        self.assertFalse(visible["builtin:combat_defense"])

        custom_character = self.characters.create_character("Custom Legacy", "Spheres")
        self.presentation.ensure_character(custom_character, legacy)
        ability = next(
            item for item in self.presentation.list_instances(custom_character)
            if item.instance_key == "builtin:abilities"
        )
        self.presentation.update_instance_geometry(ability.id, 80, 90, 640, 360)
        self.presentation.ensure_character(custom_character, self.registry)
        custom_visible = {
            item.instance_key: item.visible
            for item in self.presentation.list_instances(custom_character)
        }
        self.assertFalse(custom_visible["builtin:classic_statistics"])
        self.assertTrue(custom_visible["builtin:abilities"])
        self.assertTrue(custom_visible["builtin:combat_defense"])

    def test_templates_instances_and_deletion_preserve_snapshots(self) -> None:
        definition = self.custom_definition()
        self.presentation.save_user_template(definition)
        instance_id = self.presentation.add_instance(self.character_id, definition, "core")
        self.presentation.delete_user_template(definition.key)
        self.assertEqual((), self.presentation.list_user_templates())
        instance = next(item for item in self.presentation.list_instances(self.character_id) if item.id == instance_id)
        self.assertEqual("Test Block", instance.template_snapshot["name"])

    def test_user_template_catalogue_persists_globally(self) -> None:
        definition = self.custom_definition("user:persistent")
        self.presentation.save_user_template(definition)
        second_connection = BuildingBlockRepository(self.path)
        try:
            self.assertEqual(
                ["user:persistent"],
                [item.key for item in second_connection.list_user_templates()],
            )
        finally:
            second_connection.close()

    def test_tabs_reorder_hide_duplicate_and_move_without_rules_loss(self) -> None:
        custom = self.presentation.add_tab(self.character_id, "Notes")
        duplicate = self.presentation.add_tab(self.character_id, "Notes Copy", source_key=custom)
        self.presentation.rename_tab(self.character_id, custom, "Campaign Notes")
        self.presentation.set_tab_visible(self.character_id, duplicate, False)
        keys = [tab.key for tab in self.presentation.list_tabs(self.character_id)]
        self.presentation.reorder_tabs(self.character_id, list(reversed(keys)))
        self.presentation.remove_tab(self.character_id, custom, move_to="core")
        self.assertEqual("Builder", self.characters.list_characters()[0].name)
        self.assertNotIn(custom, [tab.key for tab in self.presentation.list_tabs(self.character_id)])

    def test_cell_overrides_group_anchor_reparent_and_portable_state(self) -> None:
        definition = self.custom_definition()
        instance_id = self.presentation.add_instance(self.character_id, definition, "core")
        self.presentation.save_cell_override(CellOverride(
            0, instance_id, "value", 45, 70, 180, 42, True, False,
            "group:a", "hit_points.current", "", "", {}, {"background": "#123456"},
        ))
        state = self.presentation.export_character_state(self.character_id)
        other = self.characters.create_character("Imported", "Pathfinder 1e")
        self.presentation.import_character_state(other, state)
        imported = next(item for item in self.presentation.list_instances(other) if item.template_key == definition.key)
        override = self.presentation.list_cell_overrides(imported.id)[0]
        self.assertEqual((False, "group:a", "hit_points.current"), (override.anchored, override.group_id, override.binding))
        self.presentation.move_instance(imported.id, "magic")
        self.assertEqual("magic", next(item for item in self.presentation.list_instances(other) if item.id == imported.id).tab_key)

    def test_bindings_and_allowlisted_actions(self) -> None:
        BINDINGS.write(self.characters, self.character_id, "hit_points.current", 12)
        self.assertEqual(12, BINDINGS.resolve(self.characters, self.character_id, "hit_points.current"))
        context = ActionContext(
            self.characters, self.character_id, {"binding": "hit_points.current"}, {}
        )
        ACTIONS.execute("increment", context)
        self.assertEqual(13, self.characters.get_hit_points(self.character_id).current)
        BINDINGS.write(self.characters, self.character_id, "skills.perception.ranks", 4)
        self.assertEqual(4, BINDINGS.resolve(self.characters, self.character_id, "skills.perception.ranks"))
        self.assertIsInstance(BINDINGS.resolve(self.characters, self.character_id, "combat.ac"), int)
        with self.assertRaises(ValueError):
            ACTIONS.execute("arbitrary_python", context)

    def test_hiding_visuals_never_deletes_bound_rules_data(self) -> None:
        self.characters.update_hit_points(
            replace(self.characters.get_hit_points(self.character_id), current=27)
        )
        definition = self.custom_definition()
        instance_id = self.presentation.add_instance(self.character_id, definition, "core")
        self.presentation.set_instance_visible(instance_id, False)
        self.presentation.save_cell_override(CellOverride(
            0, instance_id, "value", 20, 60, 120, 32, False, True,
            "", "hit_points.current", "", "", {}, {},
        ))
        self.assertEqual(27, self.characters.get_hit_points(self.character_id).current)


if __name__ == "__main__":
    unittest.main()
