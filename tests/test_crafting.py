import os, tempfile, unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.crafting_rules import mundane_quote, magic_quote, mundane_dc
from app.crafting_catalog import crafting_document, mundane_entries, spell_recipes
from app.catalogs import DEFAULT_CATALOG
from app.ui.crafting import CraftingCatalogDialog
from app.services.crafting import CraftingService
from app.crafting_rules import magical_base_price, crafting_calendar_days, composite_bow_price
from tools.build_crafting_automation import compile_recipe
from app.crafting_equipment import compatible_bases, configured_property_cost


class CraftingRulesTests(unittest.TestCase):
    def test_magical_base_excludes_independent_costs(self):
        self.assertEqual(2000,magical_base_price(2315,1315))
        self.assertEqual(25,magical_base_price(525,512.5))
        self.assertIsNone(magical_base_price(None,100))
        self.assertIsNone(magical_base_price(100,200))

    def test_calendar_days_and_faster_mundane_work(self):
        quote = magic_quote(250,125,1,consumable=True)
        self.assertEqual(3,crafting_calendar_days(quote,quantity=3))
        quote = magic_quote(2000,1000,3)
        self.assertEqual(8,crafting_calendar_days(quote,adventuring=True))
        self.assertEqual(25,mundane_quote(30,15,30,faster=True).dc)

    def test_composite_bow_rating(self):
        entry = {'name':'Composite Longbow','family':'Weapons & Ammunition','price_gp':100}
        self.assertEqual(21,mundane_dc(entry,strength_rating=3))
        self.assertEqual(400,composite_bow_price(entry,3))

    def test_compiler_only_accepts_unambiguous_alternatives(self):
        recipe = {'review':'or','spells':['light','darkness'],'requirements':'Craft Wondrous Item, light or darkness'}
        self.assertEqual([['light','darkness']],compile_recipe(recipe)['spell_any'])
        recipe['requirements'] = 'Craft Wondrous Item or Craft Rod, light, darkness'
        self.assertNotIn('spell_any',compile_recipe(recipe))

    def test_property_uses_shared_equipment_pricing(self):
        key = 'pathfinder:enchantment:weapon:melee:keen'
        bases = compatible_bases(key)
        sword = next(i for i in bases if i.name == 'Longsword')
        self.assertEqual((8000,4315),configured_property_cost(sword,key,1))
    def test_mundane_weekly_progress(self):
        quote = mundane_quote(30, 15, 20)
        self.assertEqual(10, quote.cost_gp); self.assertEqual(7, quote.days)

    def test_masterwork_is_separate_component(self):
        quote = mundane_quote(30, 15, 20, masterwork_gp=300)
        self.assertEqual(110, quote.cost_gp); self.assertEqual(59.5, quote.days)
        self.assertIsNone(mundane_quote(30, 15, 14).days)

    def test_magic_rounding_prerequisites_and_acceleration(self):
        quote = magic_quote(2500, 1250, 9, missing=2)
        self.assertEqual((24, 3), (quote.dc, quote.days))
        self.assertEqual(1.5, magic_quote(2500,1250,9,accelerated=True).days)
        self.assertEqual(.25, magic_quote(250,125,1,consumable=True).days)

    def test_dc_categories_and_unknowns(self):
        self.assertEqual(15, mundane_dc({'name':'Acid'}))
        self.assertIsNone(mundane_dc({'name':'Tent'}))

    def test_catalog_integrity(self):
        document = crafting_document()
        self.assertFalse(document['failures'])
        keys = {e['key'] for e in document['entries']}
        self.assertGreater(len(keys), 4000)
        self.assertTrue(all(r['item_key'] in keys for r in document['recipes']))
        self.assertGreater(len(mundane_entries(DEFAULT_CATALOG)), 500)
        self.assertGreater(len(spell_recipes('Craft Wand')), 500)


class CraftingDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.repo = CharacterRepository(Path(self.tmp.name)/'test.db')
        self.cid = self.repo.create_character('Crafter', 'Spheres')
    def tearDown(self): self.repo.close(); self.tmp.cleanup()

    def test_mundane_search_preview_no_writes(self):
        before = self.repo._connection.total_changes
        dialog = CraftingCatalogDialog(self.repo, self.cid)
        self.assertEqual(-1, dialog.table.currentRow())
        dialog.search.setText('Dagger'); dialog.debounce.flush()
        self.assertGreater(dialog.table.rowCount(), 0)
        dialog.table.selectRow(0)
        self.assertIn('Materials', dialog.result.text())
        dialog.reject()
        self.assertEqual(before, self.repo._connection.total_changes)

    def test_magic_filter_and_nonwaivable_scroll(self):
        dialog = CraftingCatalogDialog(self.repo, self.cid, 'Scribe Scroll')
        dialog.table.selectRow(0)
        self.assertFalse(dialog.waive.isEnabled())
        dialog.filter.setCurrentText('Listed requirements met')
        self.assertEqual(0, dialog.table.rowCount())
        dialog.reject()

    def test_creation_feat_visibility_and_character_scope(self):
        self.assertNotIn('Craft Wondrous Item', CraftingService(self.repo,self.cid).available_feats())
        self.repo.add_feat(self.cid, 'Craft Wondrous Item')
        self.assertIn('Craft Wondrous Item', CraftingService(self.repo,self.cid).available_feats())
        other = self.repo.create_character('Other', 'Spheres')
        self.assertNotIn('Craft Wondrous Item', CraftingService(self.repo,other).available_feats())

    def test_variable_property_never_displays_free_crafting(self):
        dialog = CraftingCatalogDialog(self.repo,self.cid,'Craft Magic Arms and Armor')
        dialog.search.setText('Keen'); dialog.debounce.flush(); dialog.table.selectRow(0)
        self.assertIn('Enter the applicable', dialog.result.text())
        dialog.reject()

    def test_alternative_counts_once_and_checks_alignment(self):
        service = CraftingService(self.repo,self.cid)
        recipe = {'feats':[],'spells':['light','darkness'],'spell_any':[['light','darkness']],
                  'price_gp':100,'creation_cost_gp':50,'caster_level':1,'alignment':'good'}
        check = service.requirements(recipe)
        self.assertEqual(('light or darkness',),check.missing_spells)
        service.spells.add('light')
        self.assertFalse(service.requirements(recipe).missing_spells)
        self.assertIn('alignment',service.requirements(recipe).review)

    def test_spell_level_default_uses_actual_progression(self):
        self.repo.add_class_level(self.cid,'Sorcerer',6,'1/2','Poor','Poor','Good','sorcerer',6,24)
        service = CraftingService(self.repo,self.cid)
        recipe = {'spell_level':2,'spell_classes':['Sorcerer'],'price_per_cl':50,'price_gp':50,'creation_cost_gp':25,'caster_level':1}
        self.assertEqual(4,service.planning_defaults(recipe)['caster_level'])
        self.assertEqual(200,service.planning_defaults(recipe)['base_price_gp'])

    def test_selection_resets_additional_cost_and_quantity(self):
        dialog = CraftingCatalogDialog(self.repo,self.cid,'Craft Wondrous Item')
        dialog.table.selectRow(0); dialog.components.setValue(500); dialog.quantity.setValue(3)
        dialog.table.selectRow(1)
        self.assertEqual(0,dialog.components.value()); self.assertEqual(1,dialog.quantity.value())
        dialog.reject()

    def test_property_configuration_updates_quote(self):
        dialog = CraftingCatalogDialog(self.repo,self.cid,'Craft Magic Arms and Armor')
        dialog.search.setText('Keen'); dialog.debounce.flush(); dialog.table.selectRow(0)
        index = dialog.base_item.findText('Longsword')
        self.assertGreater(index,0)
        dialog.base_item.setCurrentIndex(index)
        self.assertEqual(8000,dialog.price.value()); self.assertEqual(4315,dialog.cost.value())
        self.assertIn('8.00 crafting days',dialog.result.text())
        dialog.base_item.setCurrentIndex(0)
        self.assertEqual(0,dialog.price.value())
        dialog.reject()

    def test_cost_trait_and_batch_are_automatic(self):
        self.repo.add_trait(self.cid,'Hedge Magician')
        dialog = CraftingCatalogDialog(self.repo,self.cid,'Craft Wondrous Item')
        dialog.search.setText('Bag of Holding (Type I)'); dialog.debounce.flush(); dialog.table.selectRow(0)
        self.assertTrue(dialog.discount.isChecked())
        self.assertIn('1,187.50 gp',dialog.result.text())
        dialog.quantity.setValue(2)
        self.assertIn('2,375.00 gp',dialog.result.text())
        dialog.reject()


if __name__ == '__main__': unittest.main()
