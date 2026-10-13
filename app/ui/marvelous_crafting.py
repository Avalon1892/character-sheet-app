"""Custom Marvelous Item composer; pricing stays in the rules module."""
from html import escape
import json

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QCheckBox, QMessageBox)
from app.catalogs import DEFAULT_CATALOG
from app.marvelous_item_rules import quote_marvelous_blueprint, marvelous_remaining_uses
from app.services.crafting import CraftingService
from app.marvelous_base_powers import base_powers, resolve_base_power, automatic_self_effect, RANGES, DURATIONS


class MarvelousCraftingDialog(QDialog):
    def __init__(self, repository, character_id, parent=None, *, item_id=None):
        super().__init__(parent)
        self.repository, self.character_id = repository, character_id
        self.service = CraftingService(repository, character_id)
        self.crafting_access = self.service.permanent_marvelous_access()
        self.item_id = None
        self.setWindowTitle('Design a Marvelous Item')
        self.resize(1280, 820)
        root = QVBoxLayout(self)
        columns = QHBoxLayout(); root.addLayout(columns, 1)
        left = QVBoxLayout(); columns.addLayout(left, 3)
        form = QFormLayout(); left.addLayout(form)
        self.name = QLineEdit('Custom Marvelous Item')
        self.slot = QComboBox(); self.slot.addItem('Held / carried', '')
        for slot in repository.list_worn_slots(character_id): self.slot.addItem(slot, slot)
        self.sphere = QComboBox()
        for sphere in DEFAULT_CATALOG.magic_spheres(): self.sphere.addItem(sphere['name'])
        self.base_power = QComboBox()
        self.cl = QSpinBox(); self.cl.setRange(1, 100); self.cl.setValue(1)
        self.activation = QComboBox()
        for label, key in [('Standard action', 'standard'), ('Full-round action', 'full-round'),
                           ('Move action', 'move'), ('Swift action', 'swift')]:
            self.activation.addItem(label, key)
        self.uses = QComboBox()
        for count in range(1, 5): self.uses.addItem(f'{count} / day', count)
        self.uses.addItem('Unlimited', 5); self.uses.addItem('50 total activations', 50)
        self.range_steps = QSpinBox(); self.range_steps.setRange(-4, 4)
        self.duration_steps = QSpinBox(); self.duration_steps.setRange(-3, 3)
        self.unique = QSpinBox(); self.unique.setRange(-50, 50)
        self.slotless = QCheckBox('No need to wear or hold the item (×2 price)')
        self.permanent = QCheckBox('Permanent, dispellable effect (+2 complexity; CL 10; hours duration)')
        for label, widget in [('Name', self.name), ('Slot', self.slot), ('Base sphere', self.sphere),
                              ('Base power', self.base_power),
                              ('Item caster level', self.cl), ('Activation', self.activation),
                              ('Uses', self.uses), ('Range steps', self.range_steps),
                              ('Duration steps', self.duration_steps), ('Unique changes / limitations', self.unique)]:
            form.addRow(label, widget)
        form.addRow(self.slotless); form.addRow(self.permanent)
        picker = QHBoxLayout(); left.addLayout(picker)
        self.talent = QComboBox(); picker.addWidget(self.talent, 1)
        add = QPushButton('Add effect contribution'); picker.addWidget(add)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Talent / effect', 'Verified complexity contribution', 'Alternative', 'Choice group'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 235); left.addWidget(self.table, 1)
        remove = QPushButton('Remove selected contribution'); left.addWidget(remove)
        self.description = QTextEdit(); self.description.setPlaceholderText('Your item description and chosen base power…')
        left.addWidget(self.description, 1)
        self.preview = QTextBrowser(); columns.addWidget(self.preview, 2)
        self.review = QCheckBox('Construction prerequisites and sphere-specific costs have been reviewed with the GM')
        root.addWidget(self.review)
        self.result = QLabel(); root.addWidget(self.result)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.save = buttons.addButton('Add designed item to inventory', QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)
        buttons.rejected.connect(self.reject); self.save.clicked.connect(self.save_item)
        add.clicked.connect(self.add_contribution); remove.clicked.connect(self.remove_contribution)
        self.sphere.currentTextChanged.connect(self.populate_talents)
        self.base_power.currentIndexChanged.connect(self.power_changed)
        for widget in (self.cl, self.range_steps, self.duration_steps, self.unique): widget.valueChanged.connect(self.update_preview)
        for widget in (self.activation, self.uses, self.slot): widget.currentIndexChanged.connect(self.update_preview)
        self.name.textChanged.connect(self.update_preview); self.description.textChanged.connect(self.update_preview)
        self.review.toggled.connect(self.update_preview)
        self.slotless.toggled.connect(self.update_preview); self.permanent.toggled.connect(self.update_preview)
        self.populate_talents()
        if item_id is not None:
            self.load_design(item_id)

    def load_design(self, item_id):
        item = next((item for item in self.repository.list_equipment(self.character_id) if item.id == item_id), None)
        if item is None: raise ValueError('Unknown character item.')
        metadata = json.loads(item.automation_json or '{}')
        if metadata.get('provider') != 'marvelous-composer': raise ValueError('Not a custom Marvelous design.')
        plan = metadata['marvelous_blueprint']
        self.item_id = item_id
        self.sphere.setCurrentText(plan['sphere'])
        self.base_power.setCurrentIndex(self.base_power.findData(plan['base_power']))
        self.cl.setValue(plan['caster_level'])
        self.activation.setCurrentIndex(self.activation.findData(plan['activation']))
        self.uses.setCurrentIndex(self.uses.findData(plan['uses']))
        self.range_steps.setValue(plan['range_steps']); self.duration_steps.setValue(plan['duration_steps'])
        self.unique.setValue(plan['unique_changes'])
        self.slotless.setChecked(plan.get('no_space_limitation', False))
        self.permanent.setChecked(plan.get('permanent', False))
        for contribution in plan['contributions']:
            index = next((i for i in range(self.talent.count()) if self.talent.itemData(i)['key'] == contribution['catalog_key']), -1)
            if index < 0: raise ValueError('A saved talent is no longer available; editing cannot safely continue.')
            self.talent.setCurrentIndex(index); self.add_contribution()
            row = self.table.rowCount() - 1
            self.table.cellWidget(row, 1).setValue(contribution['complexity'])
            self.table.cellWidget(row, 2).setChecked(contribution.get('alternative', False))
            self.table.cellWidget(row, 3).setValue(contribution.get('alternative_group', 1))
        self.name.setText(item.name); self.description.setPlainText(item.notes)
        self.slot.setCurrentIndex(self.slot.findData(item.slot))
        self.setWindowTitle('Edit Marvelous Item Design'); self.save.setText('Save design changes')

    def populate_talents(self, *_):
        self.table.setRowCount(0)
        self.base_power.blockSignals(True)
        self.base_power.clear()
        for power in base_powers(self.sphere.currentText()): self.base_power.addItem(power.name, power.key)
        self.base_power.blockSignals(False)
        self.talent.clear()
        for entry in DEFAULT_CATALOG.magic_entries(self.sphere.currentText()):
            if entry.get('category') not in {'Base Sphere', 'Drawback', 'Sphere-Specific Drawback'}:
                self.talent.addItem(entry['name'], entry)
        self.power_changed()

    def power_changed(self, *_):
        powers = base_powers(self.sphere.currentText())
        power = next((p for p in powers if p.key == self.base_power.currentData()), None)
        if power:
            self.range_steps.setRange(-RANGES.index(power.range), len(RANGES) - RANGES.index(power.range) - 1)
            self.duration_steps.setEnabled(power.duration in DURATIONS)
            if power.duration in DURATIONS:
                index = DURATIONS.index(power.duration)
                self.duration_steps.setRange(-index, len(DURATIONS) - index - 1)
            else: self.duration_steps.setRange(0, 0)
        self.update_preview()

    def add_contribution(self):
        entry = self.talent.currentData()
        if not entry: return
        row = self.table.rowCount(); self.table.insertRow(row)
        item = QTableWidgetItem(entry['name'])
        from PySide6.QtCore import Qt
        item.setData(Qt.ItemDataRole.UserRole, entry['key'])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, item)
        cost = QSpinBox(); cost.setRange(0, 100)
        cost.setValue(2 if 'advanced' in entry.get('category', '').casefold() else 1)
        cost.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 1, cost)
        alternative = QCheckBox(); alternative.setToolTip('Mutually exclusive option in the same alternative group. Most expensive costs full; other options cost half.')
        alternative.toggled.connect(self.update_preview); self.table.setCellWidget(row, 2, alternative)
        group = QSpinBox(); group.setRange(1, 100); group.setEnabled(False)
        group.setToolTip('Alternatives with the same group number are mutually exclusive. Different groups are independent choices.')
        alternative.toggled.connect(group.setEnabled)
        group.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 3, group)
        self.update_preview()

    def remove_contribution(self):
        if self.table.currentRow() >= 0: self.table.removeRow(self.table.currentRow())
        self.update_preview()

    def blueprint(self):
        from PySide6.QtCore import Qt
        contributions = [{'catalog_key': self.table.item(r, 0).data(Qt.ItemDataRole.UserRole),
                          'complexity': self.table.cellWidget(r, 1).value(),
                          'alternative': self.table.cellWidget(r, 2).isChecked(),
                          'alternative_group': self.table.cellWidget(r, 3).value()}
                         for r in range(self.table.rowCount())]
        return dict(schema_version=1, sphere=self.sphere.currentText(), caster_level=self.cl.value(),
                    base_power=self.base_power.currentData(),
                    activation=self.activation.currentData(), uses=self.uses.currentData(),
                    range_steps=self.range_steps.value(), duration_steps=self.duration_steps.value(),
                    unique_changes=self.unique.value(), contributions=contributions,
                    no_space_limitation=self.slotless.isChecked(), permanent=self.permanent.isChecked(),
                    automation_status='rules_only')

    def quotation(self):
        return quote_marvelous_blueprint(self.blueprint())

    def update_preview(self, *_):
        try:
            complexity, price, quote = self.quotation()
            effect = resolve_base_power(self.blueprint())
            automatic = automatic_self_effect(self.blueprint())
            automation_notice = ('Activation can heal a living self, including nonlethal damage.' if automatic == 'cure'
                else 'Activation can apply temporary HP to self; expiration remains manual.' if automatic == 'temporary_hp'
                else 'This effect currently requires manual application; item uses are tracked automatically.')
            requirements = self.service.marvelous_plan_requirements(self.blueprint(), access=self.crafting_access)
            self.result.setText(f'Market price {float(price.market_price_gp):,.2f} gp · Materials {float(quote.cost_gp):,.2f} gp · Craft DC {quote.dc} · {quote.days} days · Save DC {price.save_dc}')
            self.preview.setHtml(f'<h2>{escape(self.name.text())}</h2><p>{escape(self.sphere.currentText())} · Complexity {complexity}</p>'
                f'<p>{escape(self.description.toPlainText())}</p><h3>Calculated base effect</h3>'
                + ''.join(f'<p><b>{escape(key.replace("_", " ").title())}:</b> {escape(str(value))}</p>' for key, value in effect.items())
                + '<h3>Construction review</h3>'
                + '<p><b>Automatic baseline check:</b> '
                + escape('; '.join(requirements.blockers + requirements.bypassed) or 'Baseline class/sphere/talent access is present.')
                + f'</p><p>Eligible bypasses add +{requirements.dc_increase} to crafting DC. '
                + 'Additional permanent bonuses, cooperating providers, tradition restrictions and advanced-talent prerequisites require review. Saving a design does not complete crafting.</p>'
                '<p>Contribution defaults are general talent costs, not verified sphere-specific costs. Include additional spell-point costs and exceptions. Range/duration changes must fit the published base power.</p>'
                f'<p>{escape(automation_notice)}</p><p>Saving a design does not spend gold or advance crafting time.</p>')
            feats = self.service.feats
            permitted = bool(feats.intersection({'craft marvelous item', 'craft wondrous item'}))
            self.save.setEnabled(permitted and self.review.isChecked() and bool(self.name.text().strip()))
        except ValueError as error:
            self.result.setText(str(error)); self.save.setEnabled(False)

    def save_item(self):
        if not self.save.isEnabled(): return
        try:
            self.item_id = self.service.save_marvelous_design(self.blueprint(),
                name=self.name.text(), slot=self.slot.currentData(), description=self.description.toPlainText(), item_id=self.item_id)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot save design', str(error))
            return
        self.accept()


class MarvelousItemUseDialog(QDialog):
    """Activation adapter for custom blueprints; unsupported effects stay explicit."""
    def __init__(self, repository, character_id, parent=None):
        super().__init__(parent)
        self.repository, self.character_id = repository, character_id
        self.service = CraftingService(repository, character_id)
        self.changed = False
        self.setWindowTitle('Marvelous Items'); self.resize(1040, 650)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Item', 'Remaining uses', 'Base effect', 'Activate'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 140); self.table.setColumnWidth(2, 260); self.table.setColumnWidth(3, 220)
        self.table.cellDoubleClicked.connect(self.edit_design)
        root.addWidget(self.table, 1)
        self.result = QLabel('Effect durations must be tracked manually. Other targets and modified effects are manual.')
        self.result.setWordWrap(True); root.addWidget(self.result)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for item in self.repository.list_equipment(self.character_id):
            try:
                metadata = json.loads(item.automation_json or '{}')
                plan = metadata.get('marvelous_blueprint')
                if not plan: continue
                remaining = marvelous_remaining_uses(metadata)
                effect = resolve_base_power(plan)
            except (ValueError, KeyError, TypeError):
                continue
            row = self.table.rowCount(); self.table.insertRow(row)
            name = QTableWidgetItem(item.name)
            from PySide6.QtCore import Qt
            name.setData(Qt.ItemDataRole.UserRole, item.id)
            name.setToolTip('Double-click to edit this custom design.')
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem('Unlimited' if remaining is None else str(remaining)))
            detail = QTableWidgetItem(effect['power']); detail.setToolTip('\n'.join(f'{k}: {v}' for k, v in effect.items()))
            self.table.setItem(row, 2, detail)
            automatic = automatic_self_effect(plan) is not None
            button = QPushButton(('Cure living self' if plan['base_power'] == 'life:cure' else 'Apply temporary HP to self') if automatic else 'Record use — manual effect')
            button.setEnabled(remaining != 0 and item.quantity == 1)
            if item.quantity > 1: button.setToolTip('Separate these devices into individual records to track independent uses.')
            button.clicked.connect(lambda checked=False, iid=item.id, auto=automatic:self.activate(iid, auto))
            self.table.setCellWidget(row, 3, button)

    def edit_design(self, row, column):
        from PySide6.QtCore import Qt
        try:
            dialog = MarvelousCraftingDialog(self.repository, self.character_id, self,
                item_id=self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot edit design', str(error)); return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.changed = True; self.refresh()

    def activate(self, item_id, automatic):
        if not automatic and QMessageBox.question(self, 'Record item use',
            'Apply this effect manually? Confirming consumes one item activation.') != QMessageBox.StandardButton.Yes:
            return
        try:
            effect = self.service.activate_marvelous_item(item_id, apply_to_self=automatic)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot activate item', str(error)); return
        self.changed = True
        self.result.setText('Activated: ' + ' · '.join(f'{key.replace("_", " ")}: {value}' for key, value in effect.items())
                            + '. Track the effect duration manually.')
        self.refresh()
