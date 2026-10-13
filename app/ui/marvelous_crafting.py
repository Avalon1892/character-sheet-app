"""Custom Marvelous Item composer; pricing stays in the rules module."""
from html import escape
import json

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QCheckBox, QMessageBox, QDateEdit)
from app.catalogs import DEFAULT_CATALOG
from app.marvelous_item_rules import quote_marvelous_blueprint, marvelous_remaining_uses
from app.services.crafting import CraftingService
from app.marvelous_base_powers import base_powers, resolve_base_power, automatic_self_effect, RANGES, DURATIONS


class MarvelousCraftingDialog(QDialog):
    def __init__(self, repository, character_id, parent=None, *, item_id=None, draft_effect=False):
        super().__init__(parent)
        self.repository, self.character_id = repository, character_id
        self.service = CraftingService(repository, character_id)
        self.crafting_access = self.service.permanent_marvelous_access()
        self.item_id = None
        self.extra_effects = []
        self.feat_integrations = []
        self.combination_mode = 'multiple'
        self.draft_effect = draft_effect
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
        self.full_blast = QCheckBox('Full blast damage: 1d6 per caster level (+1 complexity)')
        self.effect_range = QSpinBox(); self.effect_range.setRange(0, 2)
        self.restore_mode = QComboBox()
        for label, key in [('Choose Restore mode…', ''), ('Mind', 'mind'), ('Body', 'body'), ('Soul', 'soul')]:
            self.restore_mode.addItem(label, key)
        self.effect_range.setToolTip('0: close; 1: medium; 2: long. +2 complexity per step. This changes teleport distance or weather radius, not target range.')
        for label, widget in [('Name', self.name), ('Slot', self.slot), ('Base sphere', self.sphere),
                              ('Base power', self.base_power),
                              ('Item caster level', self.cl), ('Activation', self.activation),
                              ('Uses', self.uses), ('Range steps', self.range_steps),
                              ('Duration steps', self.duration_steps), ('Unique changes / limitations', self.unique)]:
            form.addRow(label, widget)
        form.addRow(self.slotless); form.addRow(self.permanent)
        form.addRow(self.full_blast)
        self.effect_range_label = QLabel('Distance / area steps')
        form.addRow(self.effect_range_label, self.effect_range)
        self.restore_label = QLabel('Restore mode'); form.addRow(self.restore_label, self.restore_mode)
        picker = QHBoxLayout(); left.addLayout(picker)
        self.talent = QComboBox(); picker.addWidget(self.talent, 1)
        add = QPushButton('Add effect contribution'); picker.addWidget(add)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Talent / effect', 'Base contribution', 'Alternative', 'Choice group', 'Extra SP', 'Effect choice'])
        self.table.setMinimumHeight(150)
        self.table.setColumnHidden(5, True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 130); self.table.setColumnWidth(4, 75); left.addWidget(self.table, 1)
        remove = QPushButton('Remove selected contribution'); left.addWidget(remove)
        self.add_prerequisites = QPushButton('Add required talents'); left.addWidget(self.add_prerequisites)
        self.add_prerequisites.setToolTip('Adds only missing reviewed construction prerequisites. Verify additional SP costs and required choices; item caster level is unchanged.')
        self.add_prerequisites.clicked.connect(self.add_required_contributions)
        self.description = QTextEdit(); self.description.setPlaceholderText('Your item description and chosen base power…')
        left.addWidget(self.description, 1)
        effect_controls = QHBoxLayout(); left.addLayout(effect_controls)
        self.extra_picker = QComboBox(); effect_controls.addWidget(self.extra_picker, 1)
        self.mode_picker = QComboBox()
        self.mode_picker.addItem('Separate powers', 'multiple'); self.mode_picker.addItem('Mixed simultaneous power', 'mixed')
        left.addWidget(self.mode_picker)
        self.mode_picker.currentIndexChanged.connect(self.change_combination_mode)
        self.add_power = QPushButton('Add another power'); effect_controls.addWidget(self.add_power)
        self.edit_power = QPushButton('Edit power'); effect_controls.addWidget(self.edit_power)
        self.remove_power = QPushButton('Remove power'); effect_controls.addWidget(self.remove_power)
        self.add_power.clicked.connect(lambda: self.edit_extra_effect())
        self.edit_power.clicked.connect(lambda: self.edit_extra_effect(self.extra_picker.currentIndex()))
        self.remove_power.clicked.connect(self.remove_extra_effect)
        if draft_effect:
            self.extra_picker.hide(); self.add_power.hide(); self.edit_power.hide(); self.remove_power.hide(); self.mode_picker.hide()
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
        self.full_blast.toggled.connect(self.update_preview)
        self.effect_range.valueChanged.connect(self.update_preview)
        self.restore_mode.currentIndexChanged.connect(self.update_preview)
        self.populate_talents()
        self.refresh_extra_picker()
        if draft_effect:
            self.setWindowTitle('Design additional power'); self.save.setText('Use this power')
        if item_id is not None:
            self.load_design(item_id)

    def load_design(self, item_id):
        item = next((item for item in self.repository.list_equipment(self.character_id) if item.id == item_id), None)
        if item is None: raise ValueError('Unknown character item.')
        metadata = json.loads(item.automation_json or '{}')
        if metadata.get('provider') != 'marvelous-composer': raise ValueError('Not a custom Marvelous design.')
        plan = metadata['marvelous_blueprint']
        self.item_id = item_id
        self.load_plan(plan)
        self.name.setText(item.name); self.description.setPlainText(item.notes)
        self.slot.setCurrentIndex(self.slot.findData(item.slot))
        self.setWindowTitle('Edit Marvelous Item Design'); self.save.setText('Save design changes')

    def load_plan(self, plan):
        self.feat_integrations = [dict(feat) for feat in plan.get('feat_integrations', [])]
        self.extra_effects = [dict(extra, effect_id=extra.get('effect_id', f'legacy:{index}'))
                              for index, extra in enumerate(plan.get('extra_effects', []), 1)]
        self.combination_mode = plan.get('combination_mode', 'multiple')
        self.mode_picker.blockSignals(True)
        self.mode_picker.setCurrentIndex(self.mode_picker.findData(self.combination_mode))
        self.mode_picker.blockSignals(False)
        self.table.setRowCount(0)
        self.sphere.setCurrentText(plan['sphere'])
        self.base_power.setCurrentIndex(self.base_power.findData(plan['base_power']))
        self.cl.setValue(plan['caster_level'])
        self.activation.setCurrentIndex(self.activation.findData(plan['activation']))
        self.uses.setCurrentIndex(self.uses.findData(plan['uses']))
        self.range_steps.setValue(plan['range_steps']); self.duration_steps.setValue(plan['duration_steps'])
        self.unique.setValue(plan['unique_changes'])
        self.slotless.setChecked(plan.get('no_space_limitation', False))
        self.permanent.setChecked(plan.get('permanent', False))
        self.full_blast.setChecked(plan.get('full_blast_damage', False))
        self.effect_range.setValue(plan.get('effect_range_steps', 0))
        self.restore_mode.setCurrentIndex(max(0, self.restore_mode.findData(plan.get('restore_mode', ''))))
        for contribution in plan['contributions']:
            index = next((i for i in range(self.talent.count()) if self.talent.itemData(i)['key'] == contribution['catalog_key']), -1)
            if index < 0: raise ValueError('A saved talent is no longer available; editing cannot safely continue.')
            self.talent.setCurrentIndex(index); self.add_contribution()
            row = self.table.rowCount() - 1
            extra_sp = contribution.get('additional_spell_points', 0)
            self.table.cellWidget(row, 1).setValue(contribution['complexity'] - extra_sp)
            self.table.cellWidget(row, 4).setValue(extra_sp)
            choice = self.table.cellWidget(row, 5)
            choice.setCurrentIndex(max(0, choice.findData(contribution.get('effect_choice', ''))))
            self.table.cellWidget(row, 2).setChecked(contribution.get('alternative', False))
            self.table.cellWidget(row, 3).setValue(contribution.get('alternative_group', 1))
        self.refresh_extra_picker()

    def refresh_extra_picker(self):
        self.extra_picker.clear()
        for plan in self.extra_effects:
            self.extra_picker.addItem(f"{plan['sphere']} · {resolve_base_power(plan)['power']}")
        self.edit_power.setEnabled(bool(self.extra_effects))
        self.remove_power.setEnabled(bool(self.extra_effects))
        self.update_preview()

    def change_combination_mode(self):
        self.combination_mode = self.mode_picker.currentData()
        self.update_preview()

    def edit_extra_effect(self, index=None):
        dialog = MarvelousCraftingDialog(self.repository, self.character_id, self, draft_effect=True)
        if index is not None and index >= 0:
            dialog.load_plan(self.extra_effects[index])
        dialog.cl.setValue(self.cl.value()); dialog.cl.setEnabled(False)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        plan = dialog.blueprint()
        plan.pop('extra_effects', None); plan.pop('combination_mode', None)
        if index is None or index < 0:
            from uuid import uuid4
            plan['effect_id'] = str(uuid4()); self.extra_effects.append(plan)
        else:
            plan['effect_id'] = self.extra_effects[index]['effect_id']; self.extra_effects[index] = plan
        self.refresh_extra_picker()

    def remove_extra_effect(self):
        index = self.extra_picker.currentIndex()
        if index < 0: return
        power = self.extra_picker.currentText()
        if QMessageBox.question(self, 'Remove additional power',
            f'Remove {power}? Saving will remove this power and its usage counter. Other powers retain their spent uses.') != QMessageBox.StandardButton.Yes:
            return
        self.extra_effects.pop(index); self.refresh_extra_picker()

    def populate_talents(self, *_):
        self.table.setRowCount(0)
        self.table.setColumnHidden(5, True)
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
        restore = self.base_power.currentData() == 'life:restore'
        self.restore_mode.setVisible(restore); self.restore_label.setVisible(restore)
        if not restore: self.restore_mode.setCurrentIndex(0)
        effect_range = self.base_power.currentData() in {'warp:teleport', 'weather:control'}
        self.effect_range.setVisible(effect_range); self.effect_range_label.setVisible(effect_range)
        if not effect_range: self.effect_range.setValue(0)
        blast = self.base_power.currentData() == 'destruction:blast'
        self.full_blast.setVisible(blast)
        if not blast: self.full_blast.setChecked(False)
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
        from app.marvelous_item_rules import talent_construction_cost
        mythic = 'mythic crafter' in self.service.feats
        cost.setValue(talent_construction_cost(entry, mythic_crafter=mythic))
        if mythic and 'advanced' in entry.get('category', '').casefold():
            cost.setToolTip('Mythic Crafter reduces the advanced talent base contribution to +1. Additional spell points still add complexity.')
        if entry['key'] == 'destruction:talent:admixture':
            cost.setToolTip('Admixture adds no complexity. Pay for each included blast type separately.')
        cost.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 1, cost)
        alternative = QCheckBox(); alternative.setToolTip('Mutually exclusive option in the same alternative group. Most expensive costs full; other options cost half.')
        alternative.toggled.connect(self.update_preview); self.table.setCellWidget(row, 2, alternative)
        group = QSpinBox(); group.setRange(1, 100); group.setEnabled(False)
        group.setToolTip('Alternatives with the same group number are mutually exclusive. Different groups are independent choices.')
        alternative.toggled.connect(group.setEnabled)
        group.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 3, group)
        extra_sp = QSpinBox(); extra_sp.setRange(0, 100)
        extra_sp.setToolTip('Additional spell points required by this effect add one complexity each. Confirm the published cost; no description parsing is used.')
        extra_sp.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 4, extra_sp)
        choice = QComboBox(); choice.addItem('—', '')
        if entry['key'] == 'protection:aegis-ward-talent:armored-magic-aegis':
            choice.addItem('Armor', 'armor'); choice.addItem('Shield', 'shield')
            self.table.setColumnHidden(5, False)
        choice.setEnabled(choice.count() > 1)
        choice.currentIndexChanged.connect(self.update_preview); self.table.setCellWidget(row, 5, choice)
        self.update_preview()

    def add_required_contributions(self):
        from app.marvelous_item_rules import missing_construction_prerequisites
        keys = missing_construction_prerequisites(self.blueprint()['contributions'])
        indices = [next((i for i in range(self.talent.count()) if self.talent.itemData(i)['key'] == key), -1) for key in keys]
        if -1 in indices:
            QMessageBox.warning(self, 'Cannot add prerequisites', 'A required talent is not available in the current sphere catalog. No talents were added.')
            return
        selected = self.talent.currentIndex()
        for index in indices:
            self.talent.setCurrentIndex(index); self.add_contribution()
        self.talent.setCurrentIndex(selected)

    def remove_contribution(self):
        if self.table.currentRow() >= 0: self.table.removeRow(self.table.currentRow())
        self.table.setColumnHidden(5, not any(self.table.cellWidget(r, 5).isEnabled()
                                            for r in range(self.table.rowCount())))
        self.update_preview()

    def blueprint(self):
        from PySide6.QtCore import Qt
        contributions = [{'catalog_key': self.table.item(r, 0).data(Qt.ItemDataRole.UserRole),
                          'complexity': self.table.cellWidget(r, 1).value() + self.table.cellWidget(r, 4).value(),
                          'additional_spell_points': self.table.cellWidget(r, 4).value(),
                          'alternative': self.table.cellWidget(r, 2).isChecked(),
                          'alternative_group': self.table.cellWidget(r, 3).value()}
                         for r in range(self.table.rowCount())]
        for r, contribution in enumerate(contributions):
            if choice := self.table.cellWidget(r, 5).currentData(): contribution['effect_choice'] = choice
        return dict(schema_version=1, sphere=self.sphere.currentText(), caster_level=self.cl.value(),
                    base_power=self.base_power.currentData(),
                    activation=self.activation.currentData(), uses=self.uses.currentData(),
                    range_steps=self.range_steps.value(), duration_steps=self.duration_steps.value(),
                    unique_changes=self.unique.value(), contributions=contributions,
                    no_space_limitation=self.slotless.isChecked(), permanent=self.permanent.isChecked(),
                    full_blast_damage=self.full_blast.isChecked(),
                    effect_range_steps=self.effect_range.value(),
                    restore_mode=self.restore_mode.currentData(),
                    extra_effects=self.extra_effects, combination_mode=self.combination_mode,
                    feat_integrations=self.feat_integrations,
                    automation_status='rules_only')

    def quotation(self):
        return quote_marvelous_blueprint(self.blueprint())

    def update_preview(self, *_):
        from app.marvelous_item_rules import missing_construction_prerequisites
        self.add_prerequisites.setEnabled(bool(missing_construction_prerequisites(self.blueprint()['contributions'])))
        try:
            complexity, price, quote = self.quotation()
            effect = resolve_base_power(self.blueprint())
            automatic = automatic_self_effect(self.blueprint())
            automation_notice = ('Activation can heal a living self, including nonlethal damage.' if automatic == 'cure'
                else 'Activation can apply temporary HP to self; expiration remains manual.' if automatic == 'temporary_hp'
                else 'Activation adds the supported aegis to ongoing effects; expiration remains manual.' if automatic == 'aegis'
                else 'This effect currently requires manual application; item uses are tracked automatically.')
            requirements = self.service.marvelous_plan_requirements(self.blueprint(), access=self.crafting_access)
            extra_review = ''
            for plan in self.extra_effects:
                extra = self.service.marvelous_plan_requirements(plan, access=self.crafting_access)
                extra_review += f'<p><b>{escape(plan["sphere"])} — {escape(resolve_base_power(plan)["power"])}:</b> ' + escape('; '.join(extra.blockers + extra.bypassed) or 'Baseline access present.') + '</p>'
            self.result.setText(f'Market price {float(price.market_price_gp):,.2f} gp · Materials {float(quote.cost_gp):,.2f} gp · Craft DC {quote.dc} · {quote.days} days · Save DC {price.save_dc}')
            self.preview.setHtml(f'<h2>{escape(self.name.text())}</h2><p>{escape(self.sphere.currentText())} · Complexity {complexity}</p>'
                f'<p>{escape(self.description.toPlainText())}</p><h3>Calculated base effect</h3>'
                + ''.join(f'<p><b>{escape(key.replace("_", " ").title())}:</b> {escape(str(value))}</p>' for key, value in effect.items())
                + '<h3>Additional powers</h3>' + extra_review + '<h3>Construction review</h3>'
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
        if self.draft_effect:
            self.accept(); return
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
        recipients = QHBoxLayout(); root.addLayout(recipients)
        recipients.addWidget(QLabel('Recipient for supported effects'))
        self.recipient = QComboBox(); recipients.addWidget(self.recipient, 1)
        for character in repository.list_characters(): self.recipient.addItem(character.name, character.id)
        self.recipient.setCurrentIndex(self.recipient.findData(character_id))
        self.recipient.currentIndexChanged.connect(self.refresh)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 140); self.table.setColumnWidth(2, 260); self.table.setColumnWidth(3, 220)
        self.table.cellDoubleClicked.connect(self.edit_design)
        root.addWidget(self.table, 1)
        self.construction = QPushButton('Construction project'); self.construction.setEnabled(False)
        root.addWidget(self.construction)
        self.shards = QPushButton('Record applied Flask Shards'); self.shards.setEnabled(False)
        root.addWidget(self.shards); self.shards.clicked.connect(self.record_shards)
        self.table.itemSelectionChanged.connect(self.update_construction_selection)
        self.construction.clicked.connect(self.open_construction)
        self.result = QLabel('Supported effects can affect the selected saved character. Confirm range and eligibility; durations and unsupported effects remain manual.')
        self.result.setWordWrap(True); root.addWidget(self.result)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.refresh()

    def update_construction_selection(self):
        from PySide6.QtCore import Qt
        item = self.table.item(self.table.currentRow(), 0)
        self.construction.setEnabled(bool(item and item.data(Qt.ItemDataRole.UserRole + 1)))
        self.shards.setEnabled(bool(item and item.data(Qt.ItemDataRole.UserRole + 2)))

    def record_shards(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QInputDialog
        from app.named_marvelous_items import named_marvelous_effect
        selected = self.table.item(self.table.currentRow(), 0)
        if not selected or not selected.data(Qt.ItemDataRole.UserRole + 2): return
        item = next(i for i in self.repository.list_equipment(self.character_id) if i.id == selected.data(Qt.ItemDataRole.UserRole))
        metadata = json.loads(item.automation_json or '{}')
        count, accepted = QInputDialog.getInt(self, 'Record applied Flask Shards',
            'Number already applied (recording does not consume inventory shards):', metadata.get('marvelous_flask_shards', 0), 0, 4)
        if not accepted: return
        proposed = named_marvelous_effect(item.catalog_key, {**metadata, 'marvelous_flask_shards': count})
        if QMessageBox.question(self, 'Confirm recorded upgrades',
            f'{item.name}: CL {proposed["caster_level"]}, {proposed["damage"]}, DC {proposed["save_dc"]}, {proposed["daily_uses"]}/day. Preserve spent uses and record this configuration? Verify the shards were applied in order; inventory is unchanged.') != QMessageBox.StandardButton.Yes: return
        try: self.repository.record_marvelous_flask_shards(self.character_id, item.id, count)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot record upgrades', str(error)); return
        self.changed = True; self.refresh()

    def open_construction(self):
        from PySide6.QtCore import Qt
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1): return
        dialog = MarvelousProjectDialog(self.repository, self.character_id,
            self.table.item(row, 0).data(Qt.ItemDataRole.UserRole), self)
        dialog.exec()
        if dialog.changed:
            self.changed = True; self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for item in self.repository.list_equipment(self.character_id):
            try:
                metadata = json.loads(item.automation_json or '{}')
                plan = metadata.get('marvelous_blueprint')
                custom = bool(plan)
                if custom:
                    effects = [(index, power, marvelous_remaining_uses(metadata, index), resolve_base_power(power))
                               for index, power in enumerate([plan, *plan.get('extra_effects', [])])]
                else:
                    from app.named_marvelous_items import named_marvelous_effect, named_marvelous_remaining
                    effect = named_marvelous_effect(item.catalog_key, metadata)
                    if effect is None: continue
                    plan = {}
                    effects = [(0, {}, named_marvelous_remaining(item.catalog_key, metadata), effect)]
            except (ValueError, KeyError, TypeError):
                continue
            mixed = bool(plan.get('extra_effects')) and plan.get('combination_mode') == 'mixed'
            for index, power, remaining, effect in effects:
                row = self.table.rowCount(); self.table.insertRow(row)
                name = QTableWidgetItem(item.name if index == 0 else f'↳ {item.name}')
                from PySide6.QtCore import Qt
                name.setData(Qt.ItemDataRole.UserRole, item.id)
                name.setData(Qt.ItemDataRole.UserRole + 1, custom)
                name.setData(Qt.ItemDataRole.UserRole + 2, not custom and item.catalog_key == 'spheres:marvelous-items:thunderbolt-ring')
                name.setToolTip('Double-click to edit this custom design.' if custom else 'Published catalog item; custom design controls do not apply.')
                self.table.setItem(row, 0, name)
                self.table.setItem(row, 1, QTableWidgetItem('Unlimited' if remaining is None else str(remaining)))
                detail = QTableWidgetItem(effect['power']); detail.setToolTip('\n'.join(f'{k}: {v}' for k, v in effect.items()))
                self.table.setItem(row, 2, detail)
                automatic = automatic_self_effect(power) is not None and not mixed
                automatic_label = {'life:cure': 'Cure living recipient', 'life:temporary-hp': 'Apply temporary HP',
                                   'protection:aegis': 'Apply aegis to recipient'}
                button = QPushButton(automatic_label[power['base_power']] if automatic else 'Record use — manual effect')
                from app.marvelous_base_powers import automatic_damage_dice
                if not custom: button.setText('Use — resolve action manually')
                if not mixed and (automatic_damage_dice(power) is not None or (not custom and 'damage_dice' in effect)):
                    button.setText('Use and roll damage')
                if mixed: button.setText('Use mixed power — manual' if index == 0 else 'Included in mixed activation')
                available = all(entry[2] != 0 for entry in effects) if mixed else remaining != 0
                usable = metadata.get('marvelous_project', {}).get('status', 'complete') == 'complete'
                target_allowed = not automatic or self.recipient.currentData() == self.character_id or effect['range'] != 'Personal'
                button.setEnabled(available and usable and item.quantity == 1 and (not mixed or index == 0) and target_allowed)
                if not target_allowed: button.setToolTip('Personal-range effects can only affect the item user.')
                if not usable: button.setToolTip('Construction has not produced a usable item.')
                if mixed: button.setToolTip('Using the primary control spends one use of every limited component together. Apply the combined effect manually.')
                elif item.quantity > 1: button.setToolTip('Separate these devices into individual records to track independent uses.')
                button.clicked.connect(lambda checked=False, iid=item.id, auto=automatic, ei=index:self.activate(iid, auto, ei))
                self.table.setCellWidget(row, 3, button)

    def edit_design(self, row, column):
        from PySide6.QtCore import Qt
        if not self.table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1): return
        try:
            dialog = MarvelousCraftingDialog(self.repository, self.character_id, self,
                item_id=self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot edit design', str(error)); return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.changed = True; self.refresh()

    def activate(self, item_id, automatic, effect_index=0):
        recipient = self.recipient.currentData() if automatic else None
        if automatic and recipient != self.character_id and QMessageBox.question(self, 'Apply crafted effect',
            f'Apply to {self.recipient.currentText()}? Confirm range, willingness, spell resistance and recipient eligibility. This spends the item owner’s activation.') != QMessageBox.StandardButton.Yes:
            return
        if not automatic and QMessageBox.question(self, 'Record item use',
            'Apply this effect manually? Confirming consumes one activation of this power (every component for a mixed power).') != QMessageBox.StandardButton.Yes:
            return
        try:
            effect = self.service.activate_marvelous_item(item_id, apply_to_self=automatic, effect_index=effect_index,
                                                        target_character_id=recipient)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot activate item', str(error)); return
        self.changed = True
        self.result.setText('Activated: ' + ' · '.join(f'{key.replace("_", " ")}: {value}' for key, value in effect.items())
                            + '. Track the effect duration manually.')
        self.refresh()


class MarvelousProjectDialog(QDialog):
    """Explicit work/payment UI; project transitions remain in shared rules."""
    def __init__(self, repository, character_id, item_id, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import QDate
        self.repository, self.character_id, self.item_id = repository, character_id, item_id
        self.changed = False
        self.setWindowTitle('Marvelous construction project'); self.resize(700, 480)
        root = QVBoxLayout(self)
        self.summary = QLabel(); self.summary.setWordWrap(True); root.addWidget(self.summary)
        self.start = QPushButton('Start construction — pay materials'); root.addWidget(self.start)
        form = QFormLayout(); root.addLayout(form)
        self.day = QDateEdit(QDate.currentDate()); self.day.setCalendarPopup(True); self.day.setDisplayFormat('yyyy-MM-dd')
        self.hours = QSpinBox(); self.hours.setRange(4, 8); self.hours.setValue(8)
        self.distracting = QCheckBox('Distracting surroundings (half progress)')
        self.adventuring = QCheckBox('Adventuring day (two effective hours)')
        form.addRow('Work date', self.day); form.addRow('Hours worked', self.hours)
        form.addRow(self.distracting); form.addRow(self.adventuring)
        self.work = QPushButton('Record work'); root.addWidget(self.work)
        self.check = QSpinBox(); self.check.setRange(-1000, 1000)
        form.addRow('Final Spellcraft / approved Craft check total', self.check)
        self.finish = QPushButton('Resolve final construction check'); root.addWidget(self.finish)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.start.clicked.connect(self.start_construction)
        self.work.clicked.connect(self.record_work); self.finish.clicked.connect(self.finish_construction)
        self.adventuring.toggled.connect(self.change_work_mode)
        self.refresh()

    def change_work_mode(self, checked):
        self.hours.setRange(2, 2) if checked else self.hours.setRange(4, 8)
        self.distracting.setEnabled(not checked)

    def refresh(self):
        self.start.setEnabled(False); self.work.setEnabled(False); self.finish.setEnabled(False)
        item = next((item for item in self.repository.list_equipment(self.character_id) if item.id == self.item_id), None)
        if item is None:
            self.summary.setText('The item no longer exists.'); return
        metadata = json.loads(item.automation_json or '{}')
        self.project = metadata.get('marvelous_project')
        if self.project:
            p = self.project
            self.summary.setText(f'{item.name}\nStatus: {p["status"]}\nProgress: {p["worked_hours"]:g} / {p["required_hours"]:g} effective hours\nMaterials paid: {p["materials_gp"]} gp · Final check DC {p["dc"]}')
            active = p['status'] == 'crafting'
            self.work.setEnabled(active and p['worked_hours'] < p['required_hours'])
            self.finish.setEnabled(active and p['worked_hours'] >= p['required_hours'])
            return
        try:
            from app.marvelous_projects import start_project
            service = CraftingService(self.repository, self.character_id)
            plan = metadata['marvelous_blueprint']
            self.proposed = start_project(plan, service.marvelous_plan_requirements(plan))
            p = self.proposed
            self.summary.setText(f'{item.name}\nMaterials: {p["materials_gp"]} gp · Work: {p["required_hours"]:g} hours · Final check DC {p["dc"]}\nStarting pays materials from your purse and locks the design. Currency may be exchanged to make change. Additional permanent bonuses, tradition restrictions and advanced prerequisites still require review.')
            self.start.setEnabled(item.quantity == 1)
        except (ValueError, KeyError) as error:
            self.summary.setText(f'{item.name}\nCannot start: {error}')

    def start_construction(self):
        if QMessageBox.question(self, 'Pay construction materials',
            f'Pay {self.proposed["materials_gp"]} gp and start this project? Materials are spent even if the final check fails. Confirm that remaining construction requirements have been reviewed.') != QMessageBox.StandardButton.Yes: return
        try:
            CraftingService(self.repository, self.character_id).start_marvelous_construction(self.item_id)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot start construction', str(error)); return
        self.changed = True; self.refresh()

    def record_work(self):
        try:
            self.repository.advance_marvelous_project(self.character_id, self.item_id,
                day=self.day.date().toString('yyyy-MM-dd'), hours=self.hours.value(),
                distracting=self.distracting.isChecked(), adventuring=self.adventuring.isChecked())
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot record work', str(error)); return
        self.changed = True; self.refresh()

    def finish_construction(self):
        from app.marvelous_projects import finish_project
        day = self.day.date().toString('yyyy-MM-dd')
        try:
            result = finish_project(self.project, self.check.value(), day=day)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot finish construction', str(error)); return
        if QMessageBox.question(self, 'Resolve construction',
            f'On {day}: check total {self.check.value()} versus DC {self.project["dc"]}: {result["status"]}. Confirm this final result?') != QMessageBox.StandardButton.Yes: return
        try:
            self.repository.advance_marvelous_project(self.character_id, self.item_id, day=day, check_total=self.check.value())
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot finish construction', str(error)); return
        self.changed = True; self.refresh()
