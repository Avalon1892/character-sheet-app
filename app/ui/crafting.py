"""Crafting UI adapters; plans are read-only and calculations live in rules."""
from html import escape
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QTextBrowser, QSplitter, QFormLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QDialogButtonBox)
from app.catalogs import DEFAULT_CATALOG
from app.crafting_catalog import crafting_document, mundane_entries, spell_recipes
from app.crafting_rules import (mundane_dc, mundane_quote, magic_quote,
    recommended_craft_specialties, crafting_calendar_days, composite_bow_price)
from app.services.crafting import CraftingService
from app.ui.components import DebouncedCallback
from app.crafting_equipment import property_for_recipe, compatible_bases, configured_property_cost


class CraftingCatalogDialog(QDialog):
    def __init__(self, repository, character_id, feat=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Crafting — ' + (feat or 'Mundane items'))
        self.resize(1400, 840)
        self.service = CraftingService(repository, character_id)
        self.feat = feat
        self.entries = ({e['key']: e for e in crafting_document()['entries']} if feat else {})
        self.records = ([r for r in crafting_document()['recipes'] if feat in r['feats']]
                        if feat else list(mundane_entries(DEFAULT_CATALOG)))
        if feat: self.records.extend(spell_recipes(feat))
        if feat: self.records = [self.service.planning_defaults(r) for r in self.records]
        self.current = None
        self._selecting = False
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText('Search item names…')
        self.filter = QComboBox(); self.filter.addItems(['All items', 'Listed requirements met', 'Missing requirements', 'Needs review'])
        self.filter.setVisible(bool(feat))
        bar.addWidget(self.search, 1); bar.addWidget(self.filter)
        root.addLayout(bar)
        split = QSplitter(); root.addWidget(split, 1)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Item', 'Market price', 'Requirements' if feat else 'Craft DC'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 110); self.table.setColumnWidth(2, 190)
        split.addWidget(self.table)
        right = QWidget(); formroot = QVBoxLayout(right); split.addWidget(right)
        self.details = QTextBrowser(); self.details.setOpenExternalLinks(True)
        formroot.addWidget(self.details, 1)
        form = QFormLayout(); form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows); formroot.addLayout(form)
        self.dc = QSpinBox(); self.dc.setRange(1, 200); self.dc.setValue(10)
        self.check = QSpinBox(); self.check.setRange(-100, 500); self.check.setValue(20)
        self.price = QDoubleSpinBox(); self.price.setRange(0, 1e10); self.price.setDecimals(2)
        self.cost = QDoubleSpinBox(); self.cost.setRange(0, 1e10); self.cost.setDecimals(2)
        self.cl = QSpinBox(); self.cl.setRange(0, 100)
        self.masterwork = QComboBox(); self.masterwork.addItem('None', 0); self.masterwork.addItem('Weapon (+300 gp)', 300); self.masterwork.addItem('Armor / shield (+150 gp)', 150)
        self.accelerated = QCheckBox('Accelerated crafting (+5 DC)')
        self.waive = QCheckBox('Bypass eligible missing prerequisites (+5 DC each)')
        self.components = QDoubleSpinBox(); self.components.setRange(0, 1e9); self.components.setDecimals(2)
        self.skill = QComboBox()
        self.quantity = QSpinBox(); self.quantity.setRange(1, 9999)
        self.adventuring = QCheckBox('Craft while adventuring (2 hours of progress per day)')
        self.rating = QSpinBox(); self.rating.setRange(0, 100)
        self.base_item = QComboBox(); self.base_item.setMinimumContentsLength(18)
        self.enhancement = QSpinBox(); self.enhancement.setRange(1,5); self.enhancement.setPrefix('+')
        self.property_spec = None
        if feat:
            if feat == 'Craft Magic Arms and Armor':
                form.addRow('Base item for property',self.base_item)
                form.addRow('Enhancement bonus',self.enhancement)
            form.addRow('Magical base price (gp)', self.price)
            form.addRow('Construction cost (gp)', self.cost)
            form.addRow('Item caster level', self.cl)
            form.addRow('Additional components (gp)', self.components)
            form.addRow(self.accelerated)
            form.addRow(self.waive)
            form.addRow(self.adventuring)
            self.discount = QCheckBox('Apply crafting trait reduction (5%)')
            self.discount.setChecked(bool(self.service.cost_traits))
            self.discount.setEnabled(bool(self.service.cost_traits))
            self.discount.setToolTip(', '.join(self.service.cost_traits) or 'Requires Hedge Magician or Spark of Creation')
            self.discount.toggled.connect(self.update_quote)
            form.addRow(self.discount)
        else:
            from app.skill_specializations import character_skill_definitions
            from app.services.character_calculations import CharacterCalculationService
            calculations = CharacterCalculationService(repository, character_id)
            for skill in character_skill_definitions(repository, character_id):
                if skill.key == 'craft' or skill.key.startswith('craft__'):
                    total = calculations.skill_result(skill.key).total
                    self.skill.addItem(f'{skill.name} ({total:+})', total)
            form.addRow('Craft skill (take 10 estimate)', self.skill)
            form.addRow('Market price (gp)', self.price)
            form.addRow('Craft DC / GM override', self.dc)
            form.addRow('Expected total Craft check', self.check)
            form.addRow('Masterwork component', self.masterwork)
            self.accelerated.setText('Faster crafting (+10 DC)')
            form.addRow(self.accelerated)
            form.addRow('Composite bow Strength rating', self.rating)
            self.rating.setEnabled(False)
        form.addRow('Quantity', self.quantity)
        self.result = QLabel(); self.result.setWordWrap(True); formroot.addWidget(self.result)
        self.notice = QLabel('Planning only — no gold is spent and no items are added.'); self.notice.setWordWrap(True)
        formroot.addWidget(self.notice)
        split.setSizes([760, 600])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.debounce = DebouncedCallback(self.refresh_results, 400, self)
        self.search.textChanged.connect(self.debounce.schedule); self.filter.currentIndexChanged.connect(self.refresh_results)
        self.table.itemSelectionChanged.connect(self.select_item)
        for box in (self.dc, self.check, self.price, self.cost, self.cl): box.valueChanged.connect(self.update_quote)
        self.masterwork.currentIndexChanged.connect(self.update_quote); self.accelerated.toggled.connect(self.update_quote)
        self.waive.toggled.connect(self.update_quote); self.components.valueChanged.connect(self.update_quote)
        self.cl.valueChanged.connect(self.update_spell_price)
        self.skill.currentIndexChanged.connect(lambda _:self.check.setValue(10 + (self.skill.currentData() or 0)))
        self.quantity.valueChanged.connect(self.update_quote)
        self.adventuring.toggled.connect(self.update_quote)
        self.rating.valueChanged.connect(self.update_bow_dc)
        self.base_item.currentIndexChanged.connect(self.update_property_cost)
        self.enhancement.valueChanged.connect(self.update_property_cost)
        if not feat: self.check.setValue(10 + (self.skill.currentData() or 0))
        self.refresh_results()

    def update_property_cost(self, *_):
        if self._selecting or self.property_spec is None: return
        if self.base_item.currentData() is None:
            self.price.setValue(0); self.cost.setValue(0); return
        try:
            price,cost = configured_property_cost(self.base_item.currentData(),self.property_spec.key,self.enhancement.value())
        except ValueError as error:
            self.price.setValue(0); self.cost.setValue(0)
            self.result.setText(str(error)); return
        self.price.setValue(price); self.cost.setValue(cost)
        self.cl.setValue(max(self.current.get('caster_level') or 0,3*self.enhancement.value()))
        self.update_quote()

    def update_bow_dc(self, *_):
        if self._selecting: return
        if self.current and not self.feat and 'composite' in self.current['name'].casefold():
            self.dc.setValue(mundane_dc(self.current, strength_rating=self.rating.value()))
            price = composite_bow_price(self.current, self.rating.value())
            if price is not None: self.price.setValue(price)

    def update_spell_price(self, *_):
        if self._selecting: return
        if self.current and self.current.get('price_per_cl'):
            price = self.current['price_per_cl'] * self.cl.value()
            self.price.setValue(price); self.cost.setValue(price / 2)

    def refresh_results(self):
        query = self.search.text().strip().casefold()
        self.visible_records = []
        for record in self.records:
            if query not in record['name'].casefold(): continue
            if self.feat and self.filter.currentIndex() and self.service.requirements(record).status != self.filter.currentText(): continue
            self.visible_records.append(record)
        self.visible_records = sorted(self.visible_records, key=lambda r:r['name'].casefold())[:500]
        self.table.blockSignals(True); self.table.setRowCount(len(self.visible_records))
        for row, record in enumerate(self.visible_records):
            price = record.get('price_gp')
            status = self.service.requirements(record).status if self.feat else str(mundane_dc(record) or 'Choose complexity')
            for col, text in enumerate((record['name'], f'{price:,.2f} gp' if price is not None else 'Variable', status)):
                item = QTableWidgetItem(text); item.setToolTip(text); self.table.setItem(row, col, item)
        self.table.clearSelection(); self.table.setCurrentCell(-1, -1); self.table.blockSignals(False)
        self.current = None; self.details.setHtml('<h2>Select an item</h2><p>Showing up to 500 matching items. Search to narrow the catalog.</p>'); self.result.clear()

    def select_item(self):
        row = self.table.currentRow()
        if row < 0: return
        record = self.current = self.visible_records[row]
        self._selecting = True
        self.property_spec = property_for_recipe(record) if self.feat == 'Craft Magic Arms and Armor' else None
        self.base_item.clear(); self.base_item.addItem('Choose a compatible base item…',None)
        self.base_item.setEnabled(self.property_spec is not None); self.enhancement.setEnabled(self.property_spec is not None)
        if self.property_spec:
            for base in compatible_bases(self.property_spec.key): self.base_item.addItem(base.name,base)
        entry = self.entries.get(record.get('item_key'), record)
        self.components.setValue(0); self.quantity.setValue(1)
        self.masterwork.setCurrentIndex(0); self.rating.setValue(0)
        self.price.setValue((record.get('base_price_gp') if self.feat else record.get('price_gp')) or 0)
        extra = ''
        if self.feat:
            self.waive.setChecked(False)
            self.waive.setEnabled(not any(f in self.current['feats'] for f in ('Brew Potion', 'Scribe Scroll', 'Craft Wand', 'Craft Staff')))
            self.cost.setValue(record.get('creation_cost_gp') or 0); self.cl.setValue(record.get('caster_level') or 0)
            req = self.service.requirements(record)
            extra = '<h3>Construction requirements</h3><p>' + escape(record['requirements']) + '</p><p>' + escape(req.status) + '</p>'
            if req.missing_feats: extra += '<p>Missing required feats: ' + escape(', '.join(req.missing_feats)) + '.</p>'
            if req.missing_conditions: extra += '<p>' + escape('; '.join(req.missing_conditions)) + '.</p>'
            if req.missing_spells: extra += '<p>Not listed on this character: ' + escape(', '.join(req.missing_spells)) + '. A collaborating caster or spell item may supply these.</p>'
            if req.review: extra += '<p>Confirm special conditions: ' + escape(req.review) + '</p>'
            if record.get('cost_text'): extra += '<p>Published construction cost: ' + escape(record['cost_text']) + '</p>'
            extra += '<p>Magical base price is derived from the published market and construction costs. Published item CL is not automatically a creator-level prerequisite.</p>'
            levels = self.service.spell_crafting_levels(record)
            if levels: extra += '<p>Supported class progression: ' + escape('; '.join(f'{name}: minimum item CL {minimum}, standard current CL {maximum}' for name,minimum,maximum in levels)) + '.</p>'
            if record.get('creation_cost_gp') is None: extra += '<p><b>Variable construction cost: enter the applicable cost before using this estimate.</b></p>'
            if self.property_spec: extra += '<p>Choose a compatible base item to calculate this property automatically. Cost includes purchasing the masterwork base; crafting that base yourself is a separate mundane project. Creator caster-level requirement for the enhancement is three times its enhancement bonus.</p>'
        else:
            self.rating.setEnabled('composite' in record['name'].casefold())
            specialties = recommended_craft_specialties(record)
            match = next((i for i in range(self.skill.count()) if any(f'({s})' in self.skill.itemText(i).casefold() for s in specialties)), None)
            if match is not None: self.skill.setCurrentIndex(match)
            dc = mundane_dc(record); self.dc.setValue(dc or 10)
            extra = '<p>' + ('Published standard Craft DC.' if dc else 'Choose the appropriate complexity or special-rule DC; 10 is an editable planning starting point, not a verified item DC.') + '</p>'
            if specialties and match is None: extra += '<p>Select an appropriate Craft specialty: ' + escape(' / '.join(specialties)) + '.</p>'
        self.details.setHtml('<h2>' + escape(record['name']) + '</h2>' + extra + '<p>' + escape(entry.get('description', '')).replace('\n','<br>') + '</p><p><a href="' + escape(record.get('source_url', ''), quote=True) + '">Rules source</a></p>')
        self._selecting = False
        self.update_quote()

    def update_quote(self, *_):
        if self.current is None or self._selecting: return
        if self.feat:
            if self.price.value() <= 0 or self.cost.value() <= 0 or self.cl.value() <= 0:
                self.result.setText('Enter the applicable magical base price, construction cost, and caster level to calculate an estimate. Variable-price properties must include the chosen item’s full configuration.')
                return
            requirements = self.service.requirements(self.current)
            missing = len(requirements.missing_spells) + len(requirements.missing_conditions) if self.waive.isChecked() and self.waive.isEnabled() else 0
            quote = magic_quote(self.price.value(), self.cost.value() + self.components.value(), self.cl.value(), missing=missing, accelerated=self.accelerated.isChecked(), consumable=self.feat in {'Brew Potion', 'Scribe Scroll'})
            prefix = 'Standard estimate; prerequisites must be supplied. '
        else:
            quote = mundane_quote(self.price.value(), self.dc.value(), self.check.value(), masterwork_gp=self.masterwork.currentData(), faster=self.accelerated.isChecked())
            prefix = ''
        quantity = self.quantity.value()
        days = crafting_calendar_days(quote, adventuring=self.adventuring.isChecked(), quantity=quantity, magical=bool(self.feat))
        duration = f'{days:,.2f} crafting days' if days is not None else 'No progress'
        cost = quote.cost_gp * quantity
        if self.feat and self.discount.isChecked(): cost *= .95
        funds = 'Enough carried currency' if self.service.gold >= cost else f'Short by {cost-self.service.gold:,.2f} gp in carried currency'
        warning = ''
        if self.feat and len(self.service.cost_traits) > 1:
            warning += '\nMultiple cost-reduction traits: only one 5% reduction is applied automatically; confirm any permitted stacking with the GM.'
        levels = self.service.spell_crafting_levels(self.current) if self.feat else ()
        if levels and not any(low <= self.cl.value() <= high for _,low,high in levels):
            warning += '\nSelected CL is outside the supported character progression; an external provider or custom rule is required.'
        self.result.setText(f'{prefix}Materials: {cost:,.2f} gp • DC {quote.dc} • {duration}\n{funds}\n{quote.note}{warning}')


class CraftingPanel(QWidget):
    def __init__(self, sheet):
        super().__init__(); self.sheet = sheet; self.signature = None
        self.setObjectName('sheetSection'); self.layout_ = QVBoxLayout(self)
        self.layout_.addWidget(sheet._section_title('CRAFTING'))
        self.mundane = QPushButton('Plan mundane crafting'); self.mundane.clicked.connect(lambda:self.open_catalog())
        self.layout_.addWidget(self.mundane)
        self.engineering = QPushButton('Open Engineering Workbench — Tech & Tinker')
        self.engineering.clicked.connect(self.open_engineering)
        self.layout_.addWidget(self.engineering)
        self.magic = QWidget(); self.magic_layout = QVBoxLayout(self.magic); self.layout_.addWidget(self.magic)

    def refresh(self):
        if self.sheet.character_id is None: return
        from app.services.engineering import EngineeringService
        service=EngineeringService(self.sheet.repository,self.sheet.character_id)
        self.engineering.setVisible(any(service.available(s) for s in ('Tech','Tinker')))
        feats = CraftingService(self.sheet.repository, self.sheet.character_id).available_feats()
        if feats == self.signature: return
        self.signature = feats
        while self.magic_layout.count():
            child = self.magic_layout.takeAt(0).widget()
            if child: child.deleteLater()
        for feat in feats:
            button = QPushButton(feat + ' — Browse craftable items')
            button.clicked.connect(lambda checked=False, f=feat:self.open_catalog(f)); self.magic_layout.addWidget(button)
        self.magic.setVisible(bool(feats))

    def showEvent(self, event):
        super().showEvent(event); self.refresh()

    def open_catalog(self, feat=None):
        if self.sheet.character_id is not None:
            CraftingCatalogDialog(self.sheet.repository, self.sheet.character_id, feat, self).exec()

    def open_engineering(self):
        from app.ui.engineering import EngineeringDialog
        if self.sheet.character_id is not None:
            EngineeringDialog(self.sheet).exec()
