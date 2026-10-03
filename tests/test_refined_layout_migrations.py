"""Default presentation upgrades must never overwrite customized characters."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from app.database import CharacterRepository
from app.presentation_storage import StyleBlockRepository
from app.building_blocks.registry import BlockRegistry, register_builtin_blocks
from app.ui.refined.layout_migrations import migrate_skills_reference_layout, migrate_character_page_split


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

    def test_character_split_moves_defaults_but_preserves_custom_blocks(self):
        self.blocks.default_tabs += (("build","Character"),("advancement","Advancement"),
                                    ("traditions_casting","Traditions & Casting"))
        registry=BlockRegistry()
        for definition in register_builtin_blocks().all():
            if definition.section_key in ("base_abilities","traditions","custom_trackers","proficiencies"):
                registry.register(replace(definition,default_tab="build",default_visible=True))
        self.blocks.ensure_character(self.cid,registry)
        original={i.template_snapshot["section_key"]:i for i in self.blocks.list_instances(self.cid)}
        self.blocks.move_instance(original["proficiencies"].id,"core")
        migrate_character_page_split(self.blocks,self.cid,{})
        result={i.template_snapshot["section_key"]:i for i in self.blocks.list_instances(self.cid)}
        self.assertEqual("advancement",result["base_abilities"].tab_key)
        self.assertEqual("traditions_casting",result["traditions"].tab_key)
        self.assertEqual("core",result["proficiencies"].tab_key)
        self.assertFalse(result["custom_trackers"].visible)
        self.assertEqual(original["custom_trackers"].id,result["custom_trackers"].id)
        before=self.repo.sqlite_connection.total_changes
        migrate_character_page_split(self.blocks,self.cid,{})
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)

    def test_character_split_keeps_saved_geometry_and_hidden_state(self):
        self.blocks.default_tabs += (("build","Character"),)
        registry=BlockRegistry()
        definition=next(d for d in register_builtin_blocks().all()
                        if d.section_key=="base_abilities")
        registry.register(replace(definition,default_tab="build",default_visible=True))
        self.blocks.ensure_character(self.cid,registry)
        instance=next(i for i in self.blocks.list_instances(self.cid)
                      if i.template_snapshot["section_key"]=="base_abilities")
        for state in ({"layout":{"freeform":json.dumps({"base_abilities":{"x":90}})}},
                      {"layout":{"sizes/base_abilities":"700,400"}}):
            with self.subTest(state=state):
                self.blocks.connection.execute("DELETE FROM sheet_presentation_migrations")
                migrate_character_page_split(self.blocks,self.cid,state)
                self.assertEqual(instance,next(i for i in self.blocks.list_instances(self.cid) if i.id==instance.id))
        self.blocks.connection.execute("DELETE FROM sheet_presentation_migrations")
        self.blocks.set_instance_visible(instance.id,False)
        migrate_character_page_split(self.blocks,self.cid,{})
        hidden=next(i for i in self.blocks.list_instances(self.cid) if i.id==instance.id)
        self.assertFalse(hidden.visible)
        self.assertEqual("build",hidden.tab_key)

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
