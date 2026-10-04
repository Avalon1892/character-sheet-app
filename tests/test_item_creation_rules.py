import os
import json
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from app.catalogs import DEFAULT_CATALOG
from app.item_creation_rules import item_creation_catalog, enriched_feats
from app.reference_rules import reference_catalog, reference_index_html, reference_search_records
from app.ui.main_window import CodexDialog


class ItemCreationRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_existing_item_creation_feats_have_full_rules(self):
        feats = DEFAULT_CATALOG.feat_entries()
        for e in feats:
            if e.get('source_group') == 'Pathfinder' and 'Item Creation' in e['categories']:
                self.assertTrue(e.get('full_rules'), e['name'])
                self.assertGreater(len(e['description']), 100, e['name'])
        wondrous = DEFAULT_CATALOG.feat_entry('aon:craft-wondrous-item')
        self.assertIn('1 day for each 1,000 gp', wondrous['description'])
        self.assertIn('half of its base price', wondrous['description'])
        self.assertIsNotNone(DEFAULT_CATALOG.feat_entry('spheres:forge-construct'))

    def test_stable_keys_no_duplicate_or_automation_change(self):
        base = DEFAULT_CATALOG.feat_document['entries']
        enriched = enriched_feats(base)
        self.assertEqual(len(enriched), len({e['key'] for e in enriched}))
        self.assertTrue({e['key'] for e in base}.issubset({e['key'] for e in enriched}))
        before = next(e for e in base if e['key'] == 'aon:craft-wondrous-item')
        after = next(e for e in enriched if e['key'] == before['key'])
        for field in ('key', 'name', 'prerequisites', 'repeatable'):
            self.assertEqual(before[field], after[field])

    def test_complete_tables_and_clean_import(self):
        rules = reference_catalog()['crafting']
        core = next(e for e in rules if e['key'] == 'pf-401')
        self.assertIn('Creating Scrolls', core['description'])
        self.assertIn('Adding New Abilities', core['description'])
        self.assertIn('<table', core['html'])
        self.assertTrue(any(e['key'] == 'pf-974' for e in rules))
        self.assertTrue(any(e['sphere'] == 'Spheres' for e in rules))
        for e in [*rules, *item_creation_catalog()['feats']]:
            self.assertNotIn('\ufffd', e['description'])
            self.assertNotIn('<script', e.get('html', e.get('rules_html', '')))

    def test_codex_links_full_feat_and_search(self):
        self.assertIn('codex:feature:feat:aon:craft-wondrous-item', reference_index_html('crafting'))
        self.assertTrue(any(r['target'] == 'crafting-reference:pf-401' for r in reference_search_records()))
        dialog = CodexDialog()
        dialog._open_codex_link(QUrl('codex:feature:feat:aon:craft-wondrous-item'))
        self.assertIn('mend a broken wondrous item', dialog.browser.toPlainText())
        dialog._open_codex_link(QUrl('codex:crafting-reference:pf-401'))
        self.assertIn('Creating Scrolls', dialog.browser.toPlainText())
        dialog.close()

    def test_tech_graft_creation_feats_are_shared_catalog_and_codex_entries(self):
        dialog=CodexDialog()
        try:
            for key,name in (("spheres:craft-appliances-and-contraptions","Craft Appliances And Contraptions"),
                             ("spheres:craft-augment-graft","Craft Augment Graft")):
                entry=DEFAULT_CATALOG.feat_entry(key)
                self.assertIsNotNone(entry)
                self.assertEqual(name,entry["name"])
                self.assertIn("Item Creation",entry["categories"])
                self.assertEqual("Tech",entry["sphere"])
                self.assertIn("Craft (mechanical) 3 ranks",entry["prerequisites"])
                self.assertEqual(1,sum(e["key"]==key for e in DEFAULT_CATALOG.feat_entries()))
                dialog._open_codex_link(QUrl("codex:feature:feat:"+key))
                self.assertIn(name,dialog.browser.toPlainText())
            self.assertIn("Remote Control",dialog.browser.toPlainText())
            self.assertIn("Fortitude",dialog.browser.toPlainText())
        finally:dialog.close()


if __name__ == '__main__':
    unittest.main()
