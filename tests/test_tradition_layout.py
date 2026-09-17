import json
import tempfile
import unittest
from pathlib import Path
from app.database import CharacterRepository
from app.presentation_storage import StyleBlockRepository
from app.building_blocks.registry import register_builtin_blocks
from app.ui.refined.pages import DEFAULT_TABS, PLACEMENTS
from app.ui.refined.layout_migrations import migrate_traditions_character_page


class TraditionLayoutTests(unittest.TestCase):
    def test_new_and_existing_default_traditions_belong_on_character(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = CharacterRepository(Path(folder) / 'test.db')
            cid = repo.create_character('Traditions', 'Spheres')
            presentation = StyleBlockRepository(repo, 'refined', DEFAULT_TABS)
            presentation.ensure_character(cid, register_builtin_blocks())
            selected = [i for i in presentation.list_instances(cid)
                        if i.template_snapshot.get('section_key') in ('traditions', 'optional_traditions')]
            self.assertEqual(2, len(selected))
            for item in selected:
                self.assertEqual('build', item.tab_key)
                snapshot = {**item.template_snapshot, 'default_tab': 'inventory'}
                presentation.connection.execute(
                    'UPDATE sheet_block_instances SET tab_key=?,template_snapshot_json=? WHERE id=?',
                    ('inventory', json.dumps(snapshot), item.id))
            migrate_traditions_character_page(presentation, cid)
            migrate_traditions_character_page(presentation, cid)
            for item in presentation.list_instances(cid):
                if item.id in {i.id for i in selected}:
                    self.assertEqual('build', item.tab_key)
                    self.assertEqual('build', item.template_snapshot['default_tab'])
            self.assertNotIn('traditions', PLACEMENTS['inventory'])
            self.assertEqual(PLACEMENTS['build'].index('traditions') + 1,
                             PLACEMENTS['build'].index('optional_traditions'))
            repo.close()


if __name__ == '__main__':
    unittest.main()
