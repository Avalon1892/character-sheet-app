import json
import os
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.optional_traditions import OptionalTraditionService, catalog
from app.catalogs import DEFAULT_CATALOG
from app.codex_index import build_codex_search_records
from app.ui.optional_traditions import OptionalTraditionDialog
from app.ui.main_window import CodexDialog


class OptionalTraditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.temp.name) / 'test.db')
        self.cid = self.repo.create_character('Crafter', 'Spheres')
        self.service = OptionalTraditionService(self.repo, self.cid)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_complete_catalog_and_clean_source(self):
        self.assertEqual(10, len(DEFAULT_CATALOG.tradition_entries('Crafting')))
        self.assertEqual(11, len(DEFAULT_CATALOG.tradition_entries('Tinker')))
        for entry in catalog()['entries'] + catalog()['rules']:
            self.assertNotIn('\ufffd', entry['description'])
            self.assertNotIn('<script', entry['html'])
            self.assertNotIn('Get Spheres of Might on', entry['description'])
            self.assertTrue(entry['source_url'].startswith('https://spheresofpower.wikidot.com/'))
        records = build_codex_search_records(DEFAULT_CATALOG)
        self.assertTrue(any(r['name'] == 'Clockwork' and r['category'] == 'Traditions · Tinker' for r in records))
        self.assertTrue(DEFAULT_CATALOG.tradition_rule_entries('Crafting', 'Quality'))

    def test_select_edit_remove_and_duplicate_protection(self):
        entry = DEFAULT_CATALOG.tradition_entries('Tinker')[0]
        tid = self.service.add(entry['key'], 'Dominant; Profession (gardener)')
        with self.assertRaises(ValueError):
            self.service.add(entry['key'])
        self.service.edit(tid, 'Profession (herbalist)')
        self.assertEqual(['Profession (herbalist)'], json.loads(self.service.selections()[0].choices_json)['Notes'])
        self.assertEqual([], self.repo.list_martial_talents(self.cid))
        self.assertEqual([], self.repo.list_spells(self.cid))
        self.service.remove(tid)
        self.assertFalse(self.service.selections())

    def test_character_scope(self):
        tid = self.service.add(DEFAULT_CATALOG.tradition_entries('Crafting')[0]['key'])
        other = self.repo.create_character('Other', 'Spheres')
        with self.assertRaises(ValueError):
            OptionalTraditionService(self.repo, other).remove(tid)
        self.assertEqual(1, len(self.service.selections()))

    def test_export_import_preserves_selection_and_choices(self):
        from app.transfer import export_character, import_character
        self.service.add('tinker:clockwork', 'Dominant tradition')
        path = Path(self.temp.name) / 'character.json'
        export_character(self.repo, self.cid, path)
        imported = import_character(self.repo, path)
        records = OptionalTraditionService(self.repo, imported).selections()
        self.assertEqual(1, len(records))
        self.assertEqual('tinker:clockwork', records[0].catalog_key)
        self.assertEqual(['Dominant tradition'], json.loads(records[0].choices_json)['Notes'])

    def test_picker_no_initial_selection_search_and_cancel(self):
        dialog = OptionalTraditionDialog('Tinker')
        self.assertEqual(-1, dialog.list.currentRow())
        self.assertFalse(dialog.confirm.isEnabled())
        dialog.search.setText('Clockwork')
        self.assertEqual(1, dialog.list.count())
        self.assertEqual(-1, dialog.list.currentRow())
        dialog.list.setCurrentRow(0)
        self.assertIn('Associated Skill', dialog.details.toPlainText())
        dialog.reject()
        self.assertIsNone(dialog.selected_entry)
        self.assertFalse(self.service.selections())

    def test_formatted_codex_description(self):
        entry = DEFAULT_CATALOG.tradition_entries('Tinker')[0]
        rendered = CodexDialog._tradition_html(entry)
        self.assertIn('Associated Skill', rendered)
        self.assertNotIn('Casting ability:', rendered)

    def test_optional_selections_do_not_change_audit(self):
        from app.character_audit import build_character_audit
        before = build_character_audit(self.repo, self.cid)
        self.service.add(DEFAULT_CATALOG.tradition_entries('Tinker')[0]['key'])
        self.service.add(DEFAULT_CATALOG.tradition_entries('Crafting')[0]['key'])
        after = build_character_audit(self.repo, self.cid)
        self.assertEqual([f.key for f in before.findings], [f.key for f in after.findings])

    def test_legacy_constraint_migration_preserves_records(self):
        import sqlite3
        from app.tradition_schema import widen_tradition_kinds
        connection = sqlite3.connect(':memory:')
        connection.execute("CREATE TABLE character_traditions (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT CHECK (kind IN ('Casting', 'Martial')))")
        connection.execute("INSERT INTO character_traditions VALUES (7, 'Casting')")
        widen_tradition_kinds(connection)
        widen_tradition_kinds(connection)
        connection.execute("INSERT INTO character_traditions(kind) VALUES ('Tinker')")
        self.assertEqual([(7, 'Casting'), (8, 'Tinker')], connection.execute('SELECT * FROM character_traditions').fetchall())
        connection.close()


if __name__ == '__main__':
    unittest.main()
