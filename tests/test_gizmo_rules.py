import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from app.reference_rules import reference_catalog, reference_search_records, reference_index_html
from app.ui.main_window import CodexDialog


class GizmoRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_complete_sources_and_sections(self):
        entries = reference_catalog()['gizmos']
        self.assertEqual(9, sum(e['kind'] == 'Overview' for e in entries))
        self.assertGreater(len(entries), 300)
        self.assertEqual(len(entries), len({e['key'] for e in entries}))
        for e in entries:
            self.assertNotIn('\ufffd', e['description'])
            self.assertNotIn('<script', e['html'])
            self.assertNotIn('Get Spheres of Might on', e['description'])
            self.assertIn('spheresofpower.wikidot.com', e['source_url'])

    def test_core_rules_tables_and_internal_links(self):
        entries = {e['key']: e for e in reference_catalog()['gizmos']}
        self.assertIn('gizmo limit', entries['using-tinker-sphere']['description'].lower())
        self.assertIn('battery', entries['tinker']['description'].lower())
        self.assertIn('<table', entries['mastering-gizmos']['html'])
        self.assertIn('codex:gizmo-reference:', entries['tinker']['html'])
        self.assertIn('Artificial Intelligence', entries['ai-and-mechanoids']['description'])
        self.assertIn('Gizmos &amp;', reference_index_html('gizmos'))

    def test_search_and_codex_routing(self):
        records = reference_search_records()
        self.assertTrue(any(r['target'] == 'gizmo-reference:mastering-gizmos' for r in records))
        dialog = CodexDialog()
        dialog._open_codex_link(QUrl('codex:gizmo-reference:mastering-gizmos'))
        self.assertIn('Prosthetic', dialog.browser.toPlainText())
        dialog._open_codex_link(QUrl('codex:reference-index:gizmos'))
        self.assertIn('AI & Mechanoids', dialog.browser.toPlainText())
        titles = [dialog.tree.topLevelItem(i).text(0) for i in range(dialog.tree.topLevelItemCount())]
        self.assertIn('Gizmos & Tinker Rules', titles)
        dialog.close()


if __name__ == '__main__':
    unittest.main()
