import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.bestiary import BestiaryFilters, BestiaryIndex, creature_html
from app.catalogs import RulesCatalog
from app.encounters import EncounterRepository, average_party_level, encounter_budget
from app.ui.bestiary_dialog import BestiaryDialog
from tools.import_bestiary import canonical_url, parse_creature, parse_index


STATBLOCK = '''<span id="MainContent_DataListFeats_Label1_0">
<h1>Example</h1><i>Not imported narrative.</i><h2>Example CR 1/3</h2>
<b>Source</b><i>Bestiary pg. 1</i><br><b>XP</b>135<br>
N Small humanoid (goblinoid)<br><b>Init</b>+2
<h3>Defense</h3><b>AC</b>15<br><b>hp</b>6<br><b>Resist</b>fire 5
<h3>Offense</h3><b>Speed</b>30 ft., climb 20 ft.<br>
<b>Melee</b>sword +2 (1d4)<br><b>Ranged</b>bow +2 (1d4)<br>
<b>Spell-Like Abilities</b>at will—light<br><b>Special Attacks</b>poison
<h3>Special Abilities</h3><b>Poison (Ex)</b>DC 12<br>
<h3>Ecology</h3><b>Environment</b>temperate forests
<h3>Description</h3>Narrative lore excluded from mechanical catalog.
<h1>Creatures in "Example" Category</h1>Not the creature</span>'''
SEED = {"key": "creature:test", "name": "Example", "cr": "1/3", "type": "humanoid",
        "environment": "forest", "kinds": ["Monster"], "source_url": "https://aonprd.com/MonsterDisplay.aspx?ItemName=Example"}


def sample():
    first = parse_creature(STATBLOCK, SEED)
    second = {**first, "key": "creature:second", "name": "Wolf", "cr": "2", "cr_value": 2,
              "xp": 600, "roles": ["Melee"], "type": "animal"}
    return [first, second]


class BestiaryTests(unittest.TestCase):
    def test_ability_tags_include_hp_senses_auras_and_defenses_without_prose_matches(self):
        document = STATBLOCK.replace('<b>hp</b>6', '<b>hp</b>1,234 (16 HD; 6d8+10d6+138); regeneration 5 (acid or fire); fast healing 2')
        document = document.replace('<b>Init</b>+2', '<b>Init</b>+2<br><b>Senses</b>darkvision 60 ft., scent; Perception +8<br><b>Aura</b>fear (30 ft.)')
        document = document.replace('<b>Resist</b>fire 5', '<b>Resist</b>fire 5<br><b>DR</b>5/cold iron<br><b>SR</b>20<br><b>Immune</b>poison<br><b>Defensive Abilities</b>evasion')
        entry = parse_creature(document, SEED)
        for query in ('regen', 'fast healing', 'darkvision', 'scent', 'fear', 'evasion', 'damage reduction', 'spell resistance', 'poison'):
            self.assertTrue(BestiaryFilters(abilities=query).matches(entry), query)
        self.assertTrue(BestiaryFilters(defenses='regen').matches(entry))
        self.assertIn('regeneration 5 (acid or fire)', entry['ability_tags']['Recovery'])
        self.assertEqual(entry['ability_tags']['Recovery'], ['regeneration 5 (acid or fire)', 'fast healing 2'])
        self.assertNotIn('regeneration', sample()[0]['special_abilities'])
        self.assertFalse(BestiaryFilters(abilities='Perception +8').matches(entry))

    def test_spell_tags_keep_casting_names_and_exclude_prose_and_equipment(self):
        document = STATBLOCK.replace('at will—light', 'at will—<i>light</i>, <i>detect magic</i>')
        document = document.replace('DC 12<br>', 'DC 12; ineffective against regeneration.<br><b>Gear</b><i>cloak of resistance</i><br>')
        entry = parse_creature(document, SEED)
        self.assertIn('detect magic', entry['ability_tags']['Spellcasting'])
        self.assertFalse(BestiaryFilters(abilities='regeneration').matches(entry))
        self.assertFalse(BestiaryFilters(abilities='cloak of resistance').matches(entry))
        self.assertIn('Ability tags', creature_html(entry))

    def test_importer_preserves_mechanics_and_parses_npc_and_monster_indexes(self):
        entry = sample()[0]
        self.assertEqual(entry["roles"], ["Melee", "Ranged", "Caster"])
        self.assertEqual(entry["subtypes"], ["goblinoid"])
        self.assertEqual(entry["cr_value"], 1 / 3)
        self.assertEqual(entry["xp"], 135)
        self.assertIn("Poison (Ex)", entry["special_abilities"])
        self.assertNotIn("Narrative lore", entry["statblock_html"])
        self.assertNotIn("Not imported narrative", entry["description"])
        self.assertNotIn("Not the creature", entry["description"])
        npc = parse_creature(STATBLOCK.replace("DataListFeats", "DataListNPCs"), SEED)
        self.assertEqual(npc["xp"], 135)
        rows = parse_index('<table><tr><td><a href="NPCDisplay.aspx?ItemName=Test">Test</a></td><td>1/2</td><td>Human adept 1</td></tr></table>', "NPC")
        self.assertEqual(rows[0]["class_levels"], "Human adept 1")
        self.assertEqual(canonical_url("MonsterDisplay.aspx?ItemName=A%20B"), canonical_url("MonsterDisplay.aspx?ItemName=A+B"))

    def test_importer_rejects_missing_stats_and_removes_active_html(self):
        with self.assertRaises(ValueError):
            parse_creature("<h1>Not found</h1>", SEED)
        entry = parse_creature(STATBLOCK.replace("<b>AC</b>", '<script>bad()</script><img src="file:///secret"><b onclick="bad()">AC</b>'), SEED)
        self.assertNotIn("script", entry["statblock_html"])
        self.assertNotIn("onclick", entry["statblock_html"])
        self.assertNotIn("file://", entry["statblock_html"])

    def test_filters_are_combined_and_cr_sort_is_numeric(self):
        index = BestiaryIndex(sample())
        filters = BestiaryFilters(minimum_cr=.25, maximum_cr=.5, roles=("Melee", "Caster"), environment="FOREST", abilities="poison", defenses="fire", subtype="goblinoid")
        self.assertEqual(index.search(filters=filters).total, 1)
        self.assertEqual([e["name"] for e in index.search(sort="cr_desc").records], ["Wolf", "Example"])
        self.assertEqual(index.search("DC 12", "description").total, 2)
        self.assertEqual(index.search("DC 12", "name").total, 0)
        self.assertEqual(index.search(filters=BestiaryFilters(minimum_cr=3, maximum_cr=1)).total, 0)
        self.assertTrue(index.search(limit=1).limited)

    def test_encounter_budget_uses_published_xp_and_party_adjustments(self):
        entries = {e["key"]: e for e in sample()}
        budget = encounter_budget(entries, {"creature:second": 2}, (4, 4, 5, 5), "Average")
        self.assertEqual((budget.apl, budget.xp, budget.equivalent_cr, budget.target_xp), (5, 1200, "CR 4", 1600))
        self.assertEqual(average_party_level((4, 4, 5, 5, 5, 5)), 6)
        self.assertEqual(average_party_level((5, 5, 5)), 4)
        self.assertEqual(encounter_budget(entries, {"creature:test": 2}, (2, 2, 2, 2), "Hard").equivalent_cr, "Between CR 1/2 and 1")
        self.assertEqual(encounter_budget(entries, {"missing": 1}, (1, 1, 1, 1), "Average").unknown, ("missing",))
        with self.assertRaises(ValueError):
            encounter_budget(entries, {"creature:test": 0}, (1, 1), "Average")

    def test_persistence_is_explicit_validated_and_independent_of_characters(self):
        with sqlite3.connect(":memory:") as connection:
            repository = EncounterRepository(connection)
            self.assertEqual(repository.list(), [])
            key = repository.save("Forest", {"creature:test": 2}, (1, 1, 1, 1), "Average", "Notes")
            self.assertEqual(repository.load(key)["members"], {"creature:test": 2})
            repository.save("Forest revised", {"creature:test": 3}, (2, 2, 2, 2), "Hard", "", key)
            self.assertEqual(repository.list(), [(key, "Forest revised")])
            with self.assertRaises(ValueError):
                repository.save("", {}, (), "Average", "")
            self.assertEqual(repository.load(key)["members"], {"creature:test": 3})
            repository.delete(key)
            self.assertEqual(repository.list(), [])


class BestiaryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        Path(self.folder.name, "bestiary.json").write_text(json.dumps({"entries": sample()}), encoding="utf-8")
        self.connection = sqlite3.connect(":memory:")
        self.repo = EncounterRepository(self.connection)
        self.dialog = BestiaryDialog(self.repo, catalog=RulesCatalog(Path(self.folder.name)))

    def tearDown(self):
        self.dialog._dirty = False
        self.dialog.close()
        self.connection.close()
        self.folder.cleanup()

    def test_search_selection_quantity_and_cancel_have_no_implicit_writes(self):
        dialog = self.dialog
        self.assertIsNone(dialog.results.currentItem())
        self.assertFalse(dialog.add_button.isEnabled())
        self.assertEqual(dialog.debounce.timer.interval(), 400)
        dialog.results.setCurrentItem(dialog.results.topLevelItem(0))
        self.assertIn("Poison", dialog.details.toPlainText())
        self.assertEqual(dialog.members, {})
        dialog._add()
        dialog._add()
        self.assertEqual(dialog.members, {"creature:test": 2})
        dialog.search.setText("Wolf")
        dialog.debounce.flush()
        self.assertEqual(dialog.members, {"creature:test": 2})
        self.assertIsNone(dialog.results.currentItem())
        self.assertEqual(self.repo.list(), [])
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
            dialog.reject()
        self.assertEqual(self.repo.list(), [])

    def test_confirm_save_and_quantity_updates_budget(self):
        dialog = self.dialog
        dialog.results.setCurrentItem(dialog.results.topLevelItem(0))
        dialog._add()
        dialog.member_quantity.setValue(4)
        self.assertIn("540 XP", dialog.budget.text())
        self.assertTrue(dialog._save())
        self.assertEqual(self.repo.load(dialog.encounter_id)["members"], {"creature:test": 4})
        dialog._remove()
        self.assertFalse(dialog.remove_button.isEnabled())
        self.assertEqual(dialog.members, {})

    def test_layout_and_keyboard_activation_in_all_themes(self):
        from app.ui.dialog_theme import dialog_stylesheet
        dialog = self.dialog
        for theme in ("classic", "light", "dark"):
            dialog.setStyleSheet(dialog_stylesheet(theme))
            dialog.show()
            self.application.processEvents()
            self.assertGreater(dialog.details.width(), 300)
            self.assertGreater(dialog.results.columnWidth(0), 150)
        dialog.results.setCurrentItem(dialog.results.topLevelItem(0))
        QTest.keyClick(dialog.results, Qt.Key.Key_Return)
        self.assertEqual(dialog.members, {"creature:test": 1})
        self.assertEqual(self.repo.list(), [])


class BundledBestiaryTests(unittest.TestCase):
    def test_regular_troll_regeneration_and_other_statline_abilities_are_searchable(self):
        from app.catalogs import DEFAULT_CATALOG
        index = BestiaryIndex(DEFAULT_CATALOG.bestiary_entries())
        trolls = index.search('Troll', filters=BestiaryFilters(abilities='regen')).records
        self.assertTrue(any(e['name'] == 'Troll' and 'Monster' in e['kinds'] for e in trolls))
        regular = next(e for e in trolls if e['name'] == 'Troll' and 'Monster' in e['kinds'])
        self.assertEqual(regular['ability_tags']['Recovery'], ['regeneration 5 (acid or fire)'])
        self.assertTrue(BestiaryFilters(abilities='scent').matches(regular))
        for entry in DEFAULT_CATALOG.bestiary_entries():
            self.assertIn('ability_tags', entry)
            for values in entry['ability_tags'].values():
                for value in values:
                    self.assertIn(value.casefold(), entry['special_abilities'].casefold())

    def test_import_coverage_and_representative_statblocks(self):
        from app.catalogs import DEFAULT_CATALOG
        data = DEFAULT_CATALOG.bestiary
        self.assertTrue(data["complete"], data.get("failures"))
        self.assertEqual(data["indexed_unique_pages"], data["imported_pages"])
        entries = DEFAULT_CATALOG.bestiary_entries()
        self.assertEqual(len(entries), data["imported_pages"])
        self.assertGreater(len(entries), 3500)
        self.assertEqual(len({e["key"] for e in entries}), len(entries))
        for name, kind in (("Goblin", "Monster"), ("Acolyte", "NPC"), ("Aboleth", "Mythic")):
            entry = next(e for e in entries if e["name"] == name and kind in e["kinds"])
            self.assertIn("Defense", creature_html(entry))
            self.assertIn("Offense", creature_html(entry))
            self.assertIsNotNone(entry["xp"])
        legacy = next(e for e in entries if e["name"] == "Achaekek, the Mantis God")
        self.assertTrue(legacy["legacy_35"])
        self.assertIsNone(legacy["xp"])

    def test_codex_has_searchable_creatures_and_direct_local_links(self):
        from app.catalogs import DEFAULT_CATALOG
        from app.codex_index import build_codex_search_records
        from app.ui.main_window import CodexDialog
        application = QApplication.instance() or QApplication([])
        goblin = next(e for e in DEFAULT_CATALOG.bestiary_entries() if e["name"] == "Goblin")
        target = "bestiary:" + goblin["key"]
        self.assertTrue(any(r["target"] == target for r in build_codex_search_records(DEFAULT_CATALOG)))
        dialog = CodexDialog(target)
        try:
            self.assertIn("Goblin", dialog.browser.toPlainText())
            self.assertIn("Defense", dialog.browser.toPlainText())
            self.assertTrue(dialog.tree.findItems("Bestiary", Qt.MatchFlag.MatchExactly))
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
