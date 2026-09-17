import unittest
from app.models import SKILLS
from app.reference_rules import (reference_catalog, reference_html, skill_reference,
                                 sequence_reference, reference_search_records)
from app.prodigy_content import UNIVERSAL_PRODIGY_OPTIONS, SPHERE_PRODIGY_OPTIONS, SPHERE_IMBUES

class ReferenceRulesTests(unittest.TestCase):
    def test_all_skills_and_specializations_resolve(self):
        for skill in SKILLS:
            self.assertIsNotNone(skill_reference(skill.key), skill.key)
        for key in ("craft__alchemy", "profession__sailor", "perform__dance"):
            self.assertIsNotNone(skill_reference(key))
        self.assertIsNone(skill_reference("not_a_skill"))

    def test_every_existing_sequence_entry_has_full_rules(self):
        for option in (*UNIVERSAL_PRODIGY_OPTIONS, *SPHERE_PRODIGY_OPTIONS, *SPHERE_IMBUES):
            entry = sequence_reference(option.name, option.sphere)
            self.assertIsNotNone(entry, (option.name, option.sphere))
            self.assertGreater(len(entry["description"]), len(entry["name"]) + 5)

    def test_link_thresholds_and_restrictions_preserved(self):
        text = sequence_reference("Arcane Apocalypse")["description"]
        for token in ("5 link", "7 link", "9 link", "normal casting time"):
            self.assertIn(token, text)

    def test_skill_tables_and_optional_unlocks(self):
        html = reference_html(skill_reference("acrobatics"))
        self.assertIn("<table", html)
        self.assertIn("Signature Skill", html)
        self.assertIn("Ranks alone do not grant", html)
        self.assertIn("Move through", html)

    def test_unique_keys_and_search_targets(self):
        for family in ("skills", "prodigy"):
            keys = [entry["key"] for entry in reference_catalog()[family]]
            self.assertEqual(len(keys), len(set(keys)), family)
        for record in reference_search_records():
            self.assertTrue(record["target"])
            self.assertTrue(record["source_url"].startswith("https://"))

    def test_no_active_or_fixed_color_markup(self):
        for family in ("skills", "prodigy"):
            for entry in reference_catalog()[family]:
                for forbidden in ("<script", "<iframe", "javascript:", "style=", "bgcolor="):
                    self.assertNotIn(forbidden, entry["html"])

if __name__ == "__main__":
    unittest.main()
