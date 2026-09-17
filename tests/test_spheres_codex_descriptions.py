from __future__ import annotations

import html
import re
import unittest

from app.catalogs import DEFAULT_CATALOG
from app.codex_descriptions import (
    normalize_codex_text,
    normalize_spheres_archetype_codex_entry,
    normalize_spheres_class_codex_entry,
)
from app.ui.main_window import CodexDialog


STORE_PRICE = re.compile(r"^\$\d+(?:\.\d{2})?$|^Pay What You Want$", re.I)


class SpheresCodexDescriptionNormalizationTests(unittest.TestCase):
    def test_plain_text_cleanup_only_normalizes_spacing(self) -> None:
        self.assertEqual(
            "The rule keeps its +2 bonus.\nIt also keeps its second paragraph.",
            normalize_codex_text(
                "  The rule\u00a0 keeps\tits +2 bonus.\r\n\r\n"
                " It also keeps its second paragraph.  "
            ),
        )

    def test_class_cleanup_removes_toc_store_card_and_navigation_not_rules(self) -> None:
        source = {
            "key": "spheres-class:test",
            "name": "Test Class",
            "source_url": "https://example.test/class",
            "capabilities": ["magic"],
            "description": "FoldUnfold\n\nTable of Contents\n\nCasting",
            "summary": "FoldUnfold",
            "rules_text": (
                "FoldUnfold\n\nTable of Contents\n\nCasting\n\nSpell Pool\n\n"
                "Ultimate\n\nOriginal\n\nUltimate Spheres of Power\n\n$29.99\n\n"
                "Test classes preserve every actual rule in this introduction.\n\n"
                "Role: Test classes verify imported content.\n\nAlignment: Any\n\n"
                "Casting\n\nThe test class is a Mid-Caster and gains 2 bonus talents.\n\n"
                "Spheres of Power by Drop Dead Studios\n\nClasses\n\nArmorist"
            ),
        }

        cleaned = normalize_spheres_class_codex_entry(source)

        self.assertEqual(source["key"], cleaned["key"])
        self.assertEqual(source["source_url"], cleaned["source_url"])
        self.assertEqual(source["capabilities"], cleaned["capabilities"])
        self.assertEqual(
            "Test classes preserve every actual rule in this introduction.",
            cleaned["description"],
        )
        self.assertIn("The test class is a Mid-Caster and gains 2 bonus talents.", cleaned["rules_text"])
        self.assertNotIn("FoldUnfold", cleaned["rules_text"])
        self.assertNotIn("Table of Contents", cleaned["rules_text"])
        self.assertNotIn("by Drop Dead Studios", cleaned["rules_text"])

    def test_archetype_cleanup_preserves_replacement_rules_and_metadata(self) -> None:
        source = {
            "key": "spheres-archetype:test",
            "class_key": "pathfinder-class:test",
            "class_name": "Test",
            "name": "Focused Test",
            "source_group": "Spheres",
            "source_url": "https://example.test/archetype",
            "replaces_features": ["spells"],
            "summary": "",
            "description": (
                "FoldUnfold\n\nTable of Contents\n\nCasting\n\n"
                "Test Options\n\n$4.99\n\nFocused Test (Test Archetype)\n\n"
                "Focused tests exchange spellcasting for spherecasting.\n\n"
                "Casting: The focused test is a Mid-Caster.\n\n"
                "This replaces the spells class feature.\n\n"
                "Champions of the Spheres by Drop Dead Studios\n\nClasses\n\nProdigy"
            ),
        }

        cleaned = normalize_spheres_archetype_codex_entry(source)

        self.assertEqual(source["key"], cleaned["key"])
        self.assertEqual(["spells"], cleaned["replaces_features"])
        self.assertEqual(
            "Focused tests exchange spellcasting for spherecasting.", cleaned["summary"]
        )
        self.assertIn("This replaces the spells class feature.", cleaned["description"])
        self.assertNotIn("Table of Contents", cleaned["description"])
        self.assertNotIn("by Drop Dead Studios", cleaned["description"])

    def test_cleanup_is_idempotent_when_an_internal_source_card_is_meaningful(self) -> None:
        source = {
            "key": "spheres-archetype:wizard:test",
            "name": "Sphere Test",
            "summary": "",
            "description": (
                "Ultimate\nUltimate Rules\n$29.99\nCasting\n"
                "The first edition grants a complete caster level progression.\n"
                "Original Edition\n$19.99\nCasting\n"
                "The original edition grants a different progression.\n"
                "Spheres of Power by Drop Dead Studios\nClasses"
            ),
        }
        once = normalize_spheres_archetype_codex_entry(source)
        twice = normalize_spheres_archetype_codex_entry(once)
        self.assertEqual(once["description"], twice["description"])
        self.assertIn("first edition", twice["description"])
        self.assertIn("original edition", twice["description"])
        self.assertNotIn("$29.99", twice["description"])
        self.assertNotIn("$19.99", twice["description"])


class BundledSpheresCodexDescriptionTests(unittest.TestCase):
    def test_all_bundled_spheres_classes_have_readable_descriptions(self) -> None:
        entries = DEFAULT_CATALOG.spheres_class_entries()
        self.assertEqual(58, len(entries))
        for entry in entries:
            with self.subTest(entry=entry["name"]):
                self.assertTrue(entry["description"])
                self.assertTrue(entry["summary"])
                self.assertTrue(entry["rules_text"])
                self.assertNotIn("FoldUnfold", entry["description"])
                self.assertNotIn("Table of Contents", entry["description"])
                navigation = {
                    "Spheres of Power by Drop Dead Studios",
                    "Spheres of Might by Drop Dead Studios",
                    "Spheres of Guile by Drop Dead Studios",
                    "Champions of the Spheres by Drop Dead Studios",
                }
                self.assertFalse(navigation.intersection(entry["rules_text"].splitlines()))
                self.assertFalse(
                    any(STORE_PRICE.fullmatch(line) for line in entry["rules_text"].splitlines())
                )

    def test_all_deduplicated_spheres_archetypes_have_clean_readable_text(self) -> None:
        entries = DEFAULT_CATALOG.archetype_entries(source_group="Spheres")
        self.assertEqual(555, len(entries))
        self.assertEqual(555, len({str(entry["key"]) for entry in entries}))
        for entry in entries:
            with self.subTest(entry=entry["name"], parent=entry["class_name"]):
                self.assertTrue(str(entry.get("description") or "").strip())
                self.assertTrue(str(entry.get("summary") or "").strip())
                lines = str(entry["description"]).splitlines()
                self.assertNotIn("FoldUnfold", lines)
                self.assertNotIn("Table of Contents", lines)
                self.assertFalse(any(STORE_PRICE.fullmatch(line) for line in lines))

    def test_detailed_spheres_archetypes_drop_navigation_but_keep_rules(self) -> None:
        bioengineer = next(
            entry
            for entry in DEFAULT_CATALOG.archetype_entries(
                "pathfinder-class:alchemist", "Spheres"
            )
            if entry["name"] == "Bioengineer"
        )
        self.assertIn("This ability replaces bombs and throw anything.", bioengineer["description"])
        self.assertNotIn("Spheres of Might by Drop Dead Studios", bioengineer["description"])
        self.assertTrue(bioengineer["summary"].startswith("The bioengineer is"))

    def test_pathfinder_descriptions_do_not_pass_through_spheres_cleanup(self) -> None:
        raw = DEFAULT_CATALOG.archetype_document["entries"]
        raw_pathfinder = next(entry for entry in raw if entry["source_group"] == "Pathfinder")
        catalog_entry = DEFAULT_CATALOG.archetype_entry(str(raw_pathfinder["key"]))
        self.assertIsNotNone(catalog_entry)
        self.assertEqual(raw_pathfinder["description"], catalog_entry["description"])

    def test_class_codex_html_keeps_multiline_introductions_readable(self) -> None:
        entry = next(
            value
            for value in DEFAULT_CATALOG.spheres_class_entries()
            if value["name"] == "Blacksmith"
        )
        first, second = str(entry["description"]).splitlines()[:2]
        rendered = CodexDialog._class_html(entry)
        self.assertIn(f"{html.escape(first)}<br>{html.escape(second)}", rendered)
        self.assertIn("<h2>Complete imported rules text</h2>", rendered)


if __name__ == "__main__":
    unittest.main()
