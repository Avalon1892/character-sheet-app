"""Default presentation upgrades must never overwrite customized characters."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from app.database import CharacterRepository
from app.presentation_storage import StyleBlockRepository
from app.building_blocks.registry import BlockRegistry, register_builtin_blocks
from app.ui.refined.layout_migrations import migrate_skills_reference_layout


class RefinedLayoutMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.repo=CharacterRepository(Path(self.temp.name)/"layout.db")
        self.cid=self.repo.create_character("Existing layout","Pathfinder 1e")
        self.blocks=StyleBlockRepository(self.repo,"refined",(
            ("skills","Skills"),("abilities","Abilities"),("core","Overview")))
        registry=BlockRegistry()
        for definition in register_builtin_blocks().all():
            if definition.section_key in ("skills","special_abilities"):
                registry.register(replace(definition,default_tab=(
                    "skills" if definition.section_key=="skills" else "abilities")))
        self.blocks.ensure_character(self.cid,registry)
        self.ids={i.template_snapshot["section_key"]:i.id for i in self.blocks.list_instances(self.cid)}

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def special(self):
        return next(i for i in self.blocks.list_instances(self.cid) if i.id==self.ids["special_abilities"])

    def migrate(self,state=None):
        migrate_skills_reference_layout(self.blocks,self.cid,state or {})

    def test_untouched_default_moves_once_and_retains_records(self):
        original=self.special()
        self.migrate({"density":"compact","layout":{"colors/special_abilities":"#abcdef"}})
        migrated=self.special()
        self.assertEqual("skills",migrated.tab_key)
        self.assertEqual("skills",migrated.template_snapshot["default_tab"])
        self.assertEqual(original.id,migrated.id)
        self.assertEqual(original.instance_key,migrated.instance_key)
        before=self.repo.sqlite_connection.total_changes
        self.migrate()
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)

    def test_manual_geometry_on_either_panel_retains_previous_default(self):
        for key in ("skills","special_abilities"):
            with self.subTest(key=key):
                self.blocks.connection.execute("DELETE FROM sheet_presentation_migrations")
                self.migrate({"layout":{"freeform":json.dumps({key:{"page":"skills","x":30,"y":40}})}})
                self.assertEqual("abilities",self.special().tab_key)
                self.assertEqual("abilities",self.special().template_snapshot["default_tab"])

    def test_explicit_move_and_resize_are_not_replaced(self):
        self.blocks.move_instance(self.ids["special_abilities"],"core")
        self.blocks.update_instance_geometry(self.ids["special_abilities"],30,80,700,500)
        before=self.special()
        self.migrate()
        self.assertEqual(before,self.special())

    def test_hidden_block_is_not_restored(self):
        self.blocks.set_instance_visible(self.ids["special_abilities"],False)
        self.migrate()
        self.assertFalse(self.special().visible)
        self.assertEqual("abilities",self.special().tab_key)

    def test_malformed_layout_is_left_alone(self):
        self.migrate({"layout":{"freeform":"invalid"}})
        self.assertEqual("abilities",self.special().tab_key)

    def test_saved_explicit_size_is_preserved(self):
        self.migrate({"layout":{"sizes/skills":"[800,1200]"}})
        self.assertEqual("abilities",self.special().tab_key)


if __name__=="__main__":
    unittest.main()
