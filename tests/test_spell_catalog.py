from __future__ import annotations

import unittest

from app.catalogs import DEFAULT_CATALOG
from app.spell_rules import normalized_spell_class_name, spell_level_for_class


class TraditionalSpellCatalogTests(unittest.TestCase):
    def test_first_and_third_party_catalog_counts_and_sources(self) -> None:
        entries = DEFAULT_CATALOG.spell_entries()
        self.assertEqual(6437, len(entries))
        self.assertEqual(3028, len(DEFAULT_CATALOG.spell_entries("Pathfinder")))
        self.assertEqual(3409, len(DEFAULT_CATALOG.spell_entries("Third Party")))
        self.assertEqual(40, len(DEFAULT_CATALOG.spell_publishers("Third Party")))
        self.assertEqual(len(entries), len({entry["key"] for entry in entries}))
        self.assertTrue(all(entry["description"] for entry in entries))
        self.assertTrue(all(entry["source_url"] for entry in entries))

    def test_known_spells_keep_ruleset_publisher_and_class_levels(self) -> None:
        fireball = next(entry for entry in DEFAULT_CATALOG.spell_entries() if entry["name"] == "Fireball")
        self.assertEqual("Pathfinder", fireball["source_group"])
        self.assertEqual("Paizo", fireball["publisher"])
        self.assertEqual(3, spell_level_for_class(fireball, "Wizard"))
        aberrant = next(
            entry for entry in DEFAULT_CATALOG.spell_entries()
            if entry["name"] == "Aberrant Essence"
        )
        self.assertEqual("Third Party", aberrant["source_group"])
        self.assertEqual("Kobold Press/Open Design", aberrant["publisher"])
        self.assertEqual(3, spell_level_for_class(aberrant, "Sorcerer"))

    def test_class_name_normalization_handles_catalog_punctuation(self) -> None:
        self.assertEqual(
            normalized_spell_class_name("Summoner (Unchained)"),
            normalized_spell_class_name("Summoner Unchained"),
        )


if __name__ == "__main__":
    unittest.main()
