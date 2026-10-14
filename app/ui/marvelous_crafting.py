"""Custom Marvelous Item composer; pricing stays in the rules module."""
from html import escape
import json

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QCheckBox, QMessageBox, QDateEdit, QListWidget,
    QScrollArea, QWidget, QSizePolicy, QToolButton, QTabWidget, QAbstractItemView, QDoubleSpinBox)
from app.catalogs import DEFAULT_CATALOG
from app.marvelous_item_rules import quote_marvelous_blueprint, marvelous_remaining_uses, marvelous_price_formula, marvelous_complexity_formula, marvelous_materials_formula
from app.services.crafting import CraftingService
from app.marvelous_base_powers import base_powers, resolve_base_power, automatic_self_effect, RANGES, DURATIONS


def effect_detail_lines(effect):
    """Readable presentation of structured effects, without interpreting rules."""
    lines = []
    for key, value in effect.items():
        if key == 'ongoing_modifiers':
            value = '; '.join(f'{amount:+g} {kind} to {target.replace("_", " ")}' for target, kind, amount in value)
        elif key == 'restore_changes':
            value = '; '.join(('Lessen ' + change['condition'] + ' to ' + change['replacement'])
                if change['operation'] == 'replace' else change['operation'].title() + ' ' + change['condition'] for change in value)
        elif key == 'combined_effects':
            for index, component in enumerate(value, 1):
                lines.append((f'power {index}', component['power']))
                lines.extend(effect_detail_lines(component))
            continue
        elif key in {'damage_rolls', 'healing_rolls'}:
            value = ', '.join(str(number) for number in value)
        lines.append((key.replace('_', ' '), str(value)))
    return lines


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
        self.display_overrides = {}
        self.crafting_tradition = None
        self.drawbacks = []
        self.loading_plan = False
        self.draft_effect = draft_effect
        self.setWindowTitle('Design a Marvelous Item')
        self.resize(1360, 840)
        root = QVBoxLayout(self)
        columns = QHBoxLayout(); root.addLayout(columns, 1)
        self.controls_scroll = QScrollArea(); self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setMinimumWidth(260); self.controls_scroll.setMaximumWidth(420)
        self.controls_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        controls = QWidget(); left = QVBoxLayout(controls)
        self.controls_scroll.setWidget(controls); columns.addWidget(self.controls_scroll, 3)
        self.settings_toggle = QToolButton(); self.settings_toggle.setText('+ Item settings')
        self.settings_toggle.setCheckable(True); left.addWidget(self.settings_toggle)
        self.settings_panel = QWidget(); form = QFormLayout(self.settings_panel); left.addWidget(self.settings_panel)
        self.settings_panel.hide()
        self.settings_toggle.toggled.connect(self.settings_panel.setVisible)
        self.settings_toggle.toggled.connect(lambda checked: self.settings_toggle.setText('− Item settings' if checked else '+ Item settings'))
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.name = QLineEdit('Custom Marvelous Item')
        self.base_weight = QDoubleSpinBox(); self.base_weight.setRange(-1, 1000000000)
        self.base_weight.setDecimals(3); self.base_weight.setValue(-1)
        self.base_weight.setSpecialValueText('Not specified')
        self.base_weight.setToolTip('Ordinary item weight before crafting-tradition adjustments. This sets inventory weight; the item-card weight lock changes displayed text only.')
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
        self.slotless = QCheckBox('Slotless (×2 price)')
        self.slotless.setToolTip('No need to wear or hold the item.')
        self.permanent = QCheckBox('Permanent (+2 complexity)')
        self.permanent.setToolTip('Dispellable; requires CL 10 and a duration measured in hours.')
        self.full_blast = QCheckBox('Full blast damage (+1 complexity)')
        self.full_blast.setToolTip('1d6 damage per item caster level.')
        self.effect_range = QSpinBox(); self.effect_range.setRange(0, 2)
        self.restore_mode = QComboBox()
        for label, key in [('Choose Restore mode…', ''), ('Mind', 'mind'), ('Body', 'body'), ('Soul', 'soul')]:
            self.restore_mode.addItem(label, key)
        self.effect_range.setToolTip('0: close; 1: medium; 2: long. +2 complexity per step. This changes teleport distance or weather radius, not target range.')
        for label, widget in [('Name', self.name), ('Slot', self.slot), ('Base weight (lb)', self.base_weight), ('Base sphere', self.sphere),
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
        self.effects_button = QPushButton('Add effects…'); left.insertWidget(0, self.effects_button)
        self.effects_button.clicked.connect(self.choose_accessible_effects)
        self.tradition_button = QPushButton('Choose a crafting tradition…'); left.insertWidget(0, self.tradition_button)
        self.tradition_button.clicked.connect(self.choose_crafting_tradition)
        self.clear_tradition = QPushButton('Clear tradition'); left.insertWidget(1, self.clear_tradition)
        self.clear_tradition.clicked.connect(self.remove_crafting_tradition)
        self.area_bound = QComboBox()
        for label, value in [('Area-Bound: choose a rule…', ''), ('Area-Bound: distance-limited use', 'distance'),
                             ('Area-Bound: recharge at bonded location', 'recharge')]:
            self.area_bound.addItem(label, value)
        self.area_bound.hide(); left.insertWidget(2, self.area_bound)
        self.area_bound.currentIndexChanged.connect(self.update_preview)
        self.talent = QComboBox(); picker.addWidget(self.talent, 1)
        add = QPushButton('Add effect contribution'); picker.addWidget(add)
        # Retain catalog-backed restoration for saved plans/prerequisites, but new
        # user selections go through the effective-access picker.
        self.talent.hide(); add.hide()
        self.effects_button.setToolTip('Add currently accessible talents for the selected base sphere, including Moldable Talents. Change the base sphere to design a different power.')
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Effect', 'Cost', 'Alt.', 'Group', 'SP', 'Choice'])
        self.table.setMinimumHeight(160); self.table.setMaximumHeight(240)
        self.table.setColumnHidden(5, True)
        self.table.setColumnHidden(3, True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 150); self.table.setWordWrap(True)
        for column, width in ((1, 50), (2, 40), (3, 55), (4, 45)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().moveSection(self.table.horizontalHeader().visualIndex(4), 2)
        left.addWidget(self.table, 1)
        remove = QPushButton('Remove selected contribution'); left.addWidget(remove)
        self.effect_options = QPushButton('Choose affected spheres…'); left.addWidget(self.effect_options)
        self.effect_options.setEnabled(False)
        self.effect_options.hide()
        self.effect_options.clicked.connect(self.choose_selectivity_spheres)
        self.table.itemSelectionChanged.connect(self.refresh_effect_options)
        self.add_prerequisites = QPushButton('Add required talents'); left.addWidget(self.add_prerequisites)
        self.add_prerequisites.setToolTip('Adds only missing reviewed construction prerequisites. Verify additional SP costs and required choices; item caster level is unchanged.')
        self.add_prerequisites.clicked.connect(self.add_required_contributions)
        self.description = QTextEdit(); self.description.setPlaceholderText('Your item description and chosen base power…')
        left.addWidget(QLabel('Base description / inventory notes'))
        self.description.setMaximumHeight(100)
        left.addWidget(self.description, 1)
        effect_controls = QHBoxLayout(); left.addLayout(effect_controls)
        self.extra_picker = QComboBox(); left.addWidget(self.extra_picker)
        self.extra_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.extra_picker.setMinimumContentsLength(12)
        self.mode_picker = QComboBox()
        self.mode_picker.addItem('Separate powers', 'multiple'); self.mode_picker.addItem('Mixed simultaneous power', 'mixed')
        left.addWidget(self.mode_picker)
        self.mode_picker.currentIndexChanged.connect(self.change_combination_mode)
        self.add_power = QPushButton('Add power'); effect_controls.addWidget(self.add_power)
        self.edit_power = QPushButton('Edit'); effect_controls.addWidget(self.edit_power)
        self.remove_power = QPushButton('Remove'); effect_controls.addWidget(self.remove_power)
        self.add_power.clicked.connect(lambda: self.edit_extra_effect())
        self.edit_power.clicked.connect(lambda: self.edit_extra_effect(self.extra_picker.currentIndex()))
        self.remove_power.clicked.connect(self.remove_extra_effect)
        if draft_effect:
            self.extra_picker.hide(); self.add_power.hide(); self.edit_power.hide(); self.remove_power.hide(); self.mode_picker.hide()
            self.tradition_button.hide(); self.clear_tradition.hide()
        center = QVBoxLayout(); columns.addLayout(center, 5)
        heading = QLabel('ITEM DESCRIPTION'); heading.setObjectName('sectionTitle'); center.addWidget(heading)
        hint = QLabel('Lock a field to edit its displayed text. Locked text is preserved; calculated price and activation rules remain unchanged.')
        hint.setWordWrap(True); center.addWidget(hint)
        self.card_tabs = QTabWidget(); center.addWidget(self.card_tabs, 3)
        self.item_preview = QTextBrowser(); self.card_tabs.addTab(self.item_preview, 'Item')
        self.card_editor_toggle = QToolButton(); self.card_editor_toggle.setText('Edit / lock item fields')
        self.card_editor_toggle.setCheckable(True); center.addWidget(self.card_editor_toggle)
        self.card_editor_scroll = QScrollArea(); self.card_editor_scroll.setWidgetResizable(True)
        self.card_editor_scroll.setMinimumHeight(130)
        card_widget = QWidget(); card = QFormLayout(card_widget)
        self.card_editor_scroll.setWidget(card_widget); center.addWidget(self.card_editor_scroll, 2)
        self.card_editor_scroll.hide()
        self.card_editor_toggle.toggled.connect(self.card_editor_scroll.setVisible)
        self.card_edits, self.card_locks = {}, {}
        from app.marvelous_item_presentation import ITEM_FIELDS
        for key in ITEM_FIELDS:
            edit = QTextEdit() if key == 'description' else QLineEdit()
            if key == 'description': edit.setMaximumHeight(130)
            edit.setReadOnly(True)
            lock = QCheckBox('Lock'); lock.setMinimumWidth(55)
            line = QHBoxLayout(); line.addWidget(edit, 1); line.addWidget(lock)
            card.addRow(key.replace('_', ' ').title(), line)
            self.card_edits[key], self.card_locks[key] = edit, lock
            lock.toggled.connect(lambda checked, key=key: self.set_card_lock(key, checked))
            edit.textChanged.connect(lambda *_, key=key: self.edit_card_field(key))
        self.preview = QTextBrowser(); self.card_tabs.addTab(self.preview, 'Construction review')
        self.drawbacks_panel = QWidget(); self.drawbacks_panel.setMinimumWidth(155); self.drawbacks_panel.setMaximumWidth(235)
        right = QVBoxLayout(self.drawbacks_panel); right.setContentsMargins(0, 0, 0, 0)
        columns.addWidget(self.drawbacks_panel, 2)
        heading = QLabel('DRAWBACKS'); heading.setObjectName('sectionTitle'); right.addWidget(heading)
        self.drawbacks_button = QPushButton('Add Drawbacks…'); right.addWidget(self.drawbacks_button)
        self.drawbacks_button.clicked.connect(self.choose_drawbacks)
        self.custom_drawback_button = QPushButton('Custom drawback…'); right.addWidget(self.custom_drawback_button)
        self.custom_drawback_button.clicked.connect(self.add_custom_drawback)
        self.drawbacks_list = QListWidget(); self.drawbacks_list.setWordWrap(True)
        self.drawbacks_list.setMinimumWidth(160); self.drawbacks_list.setMaximumWidth(260)
        right.addWidget(self.drawbacks_list, 1)
        self.edit_drawback_button = QPushButton('Edit drawback'); right.addWidget(self.edit_drawback_button)
        self.edit_drawback_button.setEnabled(False)
        self.drawbacks_list.currentRowChanged.connect(lambda row: self.edit_drawback_button.setEnabled(row >= 0))
        self.edit_drawback_button.clicked.connect(self.edit_selected_drawback)
        self.drawbacks_list.itemDoubleClicked.connect(lambda *_: self.edit_selected_drawback())
        self.remove_drawback_button = QPushButton('Remove drawback'); right.addWidget(self.remove_drawback_button)
        self.remove_drawback_button.setEnabled(False)
        self.drawbacks_list.currentRowChanged.connect(lambda row: self.remove_drawback_button.setEnabled(row >= 0))
        self.remove_drawback_button.clicked.connect(self.remove_drawback)
        drawback_notice = QLabel('Reductions require GM review. Sphere limitations default to −1; crafting drawbacks default to 0. These are not catalog-mandated discounts. Unsupported restrictions make application manual.')
        drawback_notice.setWordWrap(True); drawback_notice.setMaximumWidth(260); right.addWidget(drawback_notice)
        self.review = QCheckBox('Construction prerequisites and sphere-specific costs have been reviewed with the GM')
        root.addWidget(self.review)
        self.result = QLabel(); root.addWidget(self.result)
        self.result.setWordWrap(True)
        self.cost_formula = QLabel(); self.cost_formula.setWordWrap(True)
        self.cost_formula.setToolTip('Market price uses the live rules quote. Complexity includes talents, additional SP, range, duration, activation and reviewed adjustments. Materials are half market price before tradition adjustments.')
        root.addWidget(self.cost_formula)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.feats_button = buttons.addButton('Integrate feats…', QDialogButtonBox.ButtonRole.ActionRole)
        self.feats_button.clicked.connect(self.edit_feat_integrations)
        self.save = buttons.addButton('Add designed item to inventory', QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)
        buttons.rejected.connect(self.reject); self.save.clicked.connect(self.save_item)
        add.clicked.connect(self.add_contribution); remove.clicked.connect(self.remove_contribution)
        self.sphere.currentTextChanged.connect(self.populate_talents)
        self.base_power.currentIndexChanged.connect(self.power_changed)
        self.cl.valueChanged.connect(self.change_item_caster_level)
        for widget in (self.range_steps, self.duration_steps, self.unique, self.base_weight): widget.valueChanged.connect(self.update_preview)
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
        from app.marvelous_item_rules import drawback_complexity
        drawback_complexity(plan.get('drawbacks', []))
        from app.marvelous_item_rules import marvelous_item_weight
        marvelous_item_weight(plan)
        stored_weight = plan.get('base_weight_lb')
        if stored_weight is not None:
            from decimal import Decimal
            decimals = max(3, -Decimal(str(stored_weight)).as_tuple().exponent)
            self.base_weight.setDecimals(min(323, decimals))
            self.base_weight.setMaximum(max(1000000000, float(stored_weight)))
        self.drawbacks = [dict(record) for record in plan.get('drawbacks', [])]
        self.crafting_tradition = plan.get('crafting_tradition')
        saved_bound = plan.get('area_bound_mode', '')
        bound_index = self.area_bound.findData(saved_bound)
        if bound_index < 0:
            self.area_bound.addItem('Unrecognized Area-Bound rule: ' + str(saved_bound), saved_bound)
            bound_index = self.area_bound.count() - 1
        self.area_bound.setCurrentIndex(bound_index)
        from app.marvelous_item_presentation import validate_display_overrides
        validate_display_overrides(plan.get('display_overrides', {}))
        self.display_overrides = {key: dict(record) for key, record in plan.get('display_overrides', {}).items()}
        for key, lock in self.card_locks.items():
            lock.blockSignals(True); lock.setChecked(self.display_overrides.get(key, {}).get('locked', False)); lock.blockSignals(False)
            self.card_edits[key].setReadOnly(not lock.isChecked())
        self.feat_integrations = [dict(feat) for feat in plan.get('feat_integrations', [])]
        self.extra_effects = [dict(extra, effect_id=extra.get('effect_id', f'legacy:{index}'))
                              for index, extra in enumerate(plan.get('extra_effects', []), 1)]
        self.combination_mode = plan.get('combination_mode', 'multiple')
        self.mode_picker.blockSignals(True)
        self.mode_picker.setCurrentIndex(self.mode_picker.findData(self.combination_mode))
        self.mode_picker.blockSignals(False)
        self.table.setRowCount(0)
        self.loading_plan = True
        self.sphere.setCurrentText(plan['sphere'])
        self.base_power.setCurrentIndex(self.base_power.findData(plan['base_power']))
        self.cl.setValue(plan['caster_level'])
        self.base_weight.setValue(-1 if plan.get('base_weight_lb') is None else plan['base_weight_lb'])
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
            saved_choice = contribution.get('effect_choice', '')
            choice_index = choice.findData(saved_choice)
            if choice_index < 0:
                choice.addItem('Unrecognized: ' + str(saved_choice), saved_choice)
                choice_index = choice.count() - 1
                choice.setEnabled(True); self.table.setColumnHidden(5, False)
            choice.setCurrentIndex(choice_index)
            from PySide6.QtCore import Qt
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1, contribution.get('effect_spheres', []))
            self.table.cellWidget(row, 2).setChecked(contribution.get('alternative', False))
            self.table.cellWidget(row, 3).setValue(contribution.get('alternative_group', 1))
        self.loading_plan = False
        self.refresh_extra_picker()

    def change_item_caster_level(self, value):
        if not self.loading_plan:
            for power in self.extra_effects: power['caster_level'] = value
        self.update_preview()

    def refresh_extra_picker(self):
        self.extra_picker.clear()
        for plan in self.extra_effects:
            self.extra_picker.addItem(f"{plan['sphere']} · {plan.get('effect_name', resolve_base_power(plan)['power'])}")
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
            dialog.name.setText(self.extra_effects[index].get('effect_name', resolve_base_power(self.extra_effects[index])['power']))
            dialog.description.setPlainText(self.extra_effects[index].get('effect_description', ''))
        from app.marvelous_item_rules import simple_tradition_reduction
        if simple_tradition_reduction(self.blueprint()):
            dialog.crafting_tradition = self.crafting_tradition
        dialog.cl.setValue(self.cl.value()); dialog.cl.setEnabled(False)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        plan = dialog.blueprint()
        plan.pop('extra_effects', None); plan.pop('combination_mode', None)
        plan.pop('crafting_tradition', None)
        plan['effect_name'] = dialog.name.text() if dialog.name.text() != 'Custom Marvelous Item' else resolve_base_power(plan)['power']
        plan['effect_description'] = dialog.description.toPlainText()
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
        if self.base_power.currentData() == 'warp:beacon' and not self.loading_plan:
            from PySide6.QtCore import Qt
            beacon = 'warp:space-talent:teleport-beacon-space'
            if not any(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == beacon for row in range(self.table.rowCount())):
                index = next((i for i in range(self.talent.count()) if self.talent.itemData(i)['key'] == beacon), -1)
                if index >= 0:
                    self.talent.setCurrentIndex(index); self.add_contribution()
        self.update_preview()

    def choose_drawbacks(self):
        from app.ui.marvelous_effect_picker import MarvelousEffectPicker
        from app.optional_traditions import crafting_drawbacks
        entries = [entry for entry in DEFAULT_CATALOG.magic_entries()
                   if 'drawback' in entry.get('category', '').casefold()
                   and entry['sphere'] in {self.sphere.currentText(), 'Universal'}]
        if not self.draft_effect: entries.extend(crafting_drawbacks())
        dialog = MarvelousEffectPicker(entries, self)
        dialog.setWindowTitle('Add item drawbacks'); dialog.catalog_heading.setText('ITEM DRAWBACKS — GM REVIEW REQUIRED')
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        existing = {record.get('catalog_key') for record in self.drawbacks}
        for entry in dialog.selected_entries:
            if entry['key'] not in existing:
                self.drawbacks.append(dict(source='published', catalog_key=entry['key'], name=entry['name'],
                                           description=entry.get('description', ''), reduction=0 if entry['key'].startswith('crafting:') else 1))
                existing.add(entry['key'])
        self.update_preview()

    def add_custom_drawback(self):
        self.edit_drawback()

    def edit_selected_drawback(self):
        row = self.drawbacks_list.currentRow()
        if row >= 0: self.edit_drawback(row)

    def edit_drawback(self, index=None):
        previous = self.drawbacks[index] if index is not None else None
        dialog = QDialog(self); dialog.setWindowTitle('Edit item drawback' if previous else 'Custom item drawback')
        form = QFormLayout(dialog)
        name = QLineEdit(); description = QTextEdit(); reduction = QSpinBox(); reduction.setRange(0, 100); reduction.setValue(1)
        if previous:
            name.setText(previous['name']); description.setPlainText(previous.get('description', '')); reduction.setValue(previous['reduction'])
            name.setReadOnly(previous['source'] == 'published'); description.setReadOnly(previous['source'] == 'published')
        form.addRow('Name', name); form.addRow('Description / restriction', description); form.addRow('Complexity reduction', reduction)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(name.text().strip()))
        name.textChanged.connect(lambda value: buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(value.strip())))
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        if any(row != index and record['name'].casefold() == name.text().strip().casefold()
               for row, record in enumerate(self.drawbacks)):
            QMessageBox.warning(self, 'Duplicate drawback', 'This drawback is already included.'); return
        updated = dict(previous or {'source': 'custom'}, name=name.text().strip(), description=description.toPlainText(), reduction=reduction.value())
        if index is None: self.drawbacks.append(updated)
        else: self.drawbacks[index] = updated
        self.update_preview()
        self.drawbacks_list.setCurrentRow(len(self.drawbacks) - 1 if index is None else index)

    def remove_drawback(self):
        row = self.drawbacks_list.currentRow()
        if row < 0: return
        self.drawbacks.pop(row); self.update_preview()

    def choose_crafting_tradition(self):
        from app.ui.optional_traditions import OptionalTraditionDialog
        dialog = OptionalTraditionDialog('Crafting', parent=self)
        dialog.confirm.setText('Use for this design')
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_entry is None: return
        self.crafting_tradition = dict(dialog.selected_entry, notes=dialog.notes.toPlainText())
        self.update_preview()

    def remove_crafting_tradition(self):
        self.crafting_tradition = None
        self.update_preview()

    def choose_accessible_effects(self):
        from app.ui.marvelous_effect_picker import MarvelousEffectPicker
        from PySide6.QtCore import Qt
        entries = self.service.accessible_marvelous_effects(self.sphere.currentText())
        dialog = MarvelousEffectPicker(entries, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        existing = {self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(self.table.rowCount())}
        for entry in dialog.selected_entries:
            if entry['key'] in existing: continue
            index = next((i for i in range(self.talent.count()) if self.talent.itemData(i)['key'] == entry['key']), -1)
            if index >= 0:
                self.talent.setCurrentIndex(index); self.add_contribution(); existing.add(entry['key'])
                if entry['key'] == 'warp:space-talent:teleport-beacon-space':
                    self.base_power.setCurrentIndex(self.base_power.findData('warp:beacon'))
                from app.marvelous_base_powers import ANTIMAGIC_AURA_KEYS
                if entry['key'] in ANTIMAGIC_AURA_KEYS:
                    self.base_power.setCurrentIndex(self.base_power.findData('protection:ward'))
        # Required construction talents are part of the same draft; eligibility
        # still checks ownership and CL separately and never grants them to a PC.
        self.add_required_contributions()

    def add_contribution(self):
        entry = self.talent.currentData()
        if not entry: return
        row = self.table.rowCount(); self.table.insertRow(row)
        item = QTableWidgetItem(entry['name'])
        item.setToolTip(entry['name'] + '\n' + entry.get('description', ''))
        from PySide6.QtCore import Qt
        item.setData(Qt.ItemDataRole.UserRole, entry['key'])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, item)
        cost = QSpinBox(); cost.setRange(0, 100)
        cost.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
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
        group.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        group.setToolTip('Alternatives with the same group number are mutually exclusive. Different groups are independent choices.')
        alternative.toggled.connect(group.setEnabled)
        group.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 3, group)
        extra_sp = QSpinBox(); extra_sp.setRange(0, 100)
        extra_sp.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        from app.marvelous_item_rules import talent_construction_spell_points
        extra_sp.setValue(talent_construction_spell_points(entry))
        extra_sp.setToolTip('Additional spell points required by this effect add one complexity each. Confirm the published cost; no description parsing is used.')
        extra_sp.valueChanged.connect(self.update_preview); self.table.setCellWidget(row, 4, extra_sp)
        choice = QComboBox(); choice.addItem('—', '')
        from app.marvelous_base_powers import talent_effect_choices
        if choices := talent_effect_choices(entry['key']):
            for value in choices: choice.addItem(value.title(), value)
            self.table.setColumnHidden(5, False)
        choice.setEnabled(choice.count() > 1)
        choice.currentIndexChanged.connect(self.update_preview); self.table.setCellWidget(row, 5, choice)
        self.table.resizeRowsToContents()
        self.update_preview()

    def refresh_effect_options(self):
        from PySide6.QtCore import Qt
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        self.effect_options.setEnabled(bool(item and item.data(Qt.ItemDataRole.UserRole)
                                       == 'protection:advanced-talent:spell-selectivity-dbh'))
        self.effect_options.setVisible(self.effect_options.isEnabled())

    def choose_selectivity_spheres(self):
        from PySide6.QtCore import Qt
        self.refresh_effect_options()
        if not self.effect_options.isEnabled(): return
        row = self.table.currentRow()
        item = self.table.item(row, 0)
        selected = set(item.data(Qt.ItemDataRole.UserRole + 1) or [])
        maximum = 1 + self.cl.value() // 5
        dialog = QDialog(self); dialog.setWindowTitle('Spell Selectivity — affected spheres'); dialog.resize(460, 560)
        layout = QVBoxLayout(dialog)
        count = QLabel(); layout.addWidget(count)
        picker = QListWidget(); picker.setObjectName('selectivitySpheres')
        picker.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for sphere in sorted(DEFAULT_CATALOG.magic_spheres(), key=lambda entry: entry['name'].casefold()):
            picker.addItem(sphere['name'])
            picker.item(picker.count() - 1).setSelected(sphere['name'] in selected)
        layout.addWidget(picker, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def refresh():
            number = len(picker.selectedItems())
            count.setText(f'{number} selected · choose 1–{maximum} spheres')
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(1 <= number <= maximum)
        picker.itemSelectionChanged.connect(refresh); refresh()
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        names = [entry.text() for entry in picker.selectedItems()]
        if not 1 <= len(names) <= maximum: return
        item.setData(Qt.ItemDataRole.UserRole + 1, names)
        self.update_preview()

    def edit_feat_integrations(self):
        available = [self.service.integration_feats[name] for name in sorted(self.service.integration_feats)]
        dialog = MarvelousFeatDialog(available, self.feat_integrations, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.feat_integrations = dialog.records(); self.update_preview()

    def add_required_contributions(self):
        from app.marvelous_item_rules import missing_construction_prerequisites, missing_construction_alternatives
        from PySide6.QtWidgets import QInputDialog
        catalog = {self.talent.itemData(i)['key']: (i, self.talent.itemData(i)['name']) for i in range(self.talent.count())}
        pending = list(self.blueprint()['contributions']); additions = []
        while True:
            keys = missing_construction_prerequisites(pending)
            additions.extend(keys); pending.extend(dict(catalog_key=key) for key in keys)
            groups = missing_construction_alternatives(pending)
            if not groups: break
            for owner, options in groups:
                if any(row['catalog_key'] in options for row in pending): continue
                if any(key not in catalog for key in options):
                    QMessageBox.warning(self, 'Cannot add prerequisites', 'A required choice is missing from the current catalog. No prerequisites were added.')
                    return
                labels = [catalog[key][1] for key in options]
                selected, accepted = QInputDialog.getItem(self, 'Choose construction prerequisite',
                    catalog.get(owner, (-1, owner))[1] + ': include one of these talents in the item effect.', labels, 0, False)
                if not accepted or selected not in labels: return
                key = options[labels.index(selected)]
                additions.append(key); pending.append(dict(catalog_key=key))
        if any(key not in catalog for key in additions):
            QMessageBox.warning(self, 'Cannot add prerequisites', 'A required talent is not available in the current sphere catalog. No talents were added.')
            return
        selected = self.talent.currentIndex()
        for key in additions:
            self.talent.setCurrentIndex(catalog[key][0]); self.add_contribution()
        self.talent.setCurrentIndex(selected)

    def remove_contribution(self):
        if self.table.currentRow() >= 0: self.table.removeRow(self.table.currentRow())
        self.table.setColumnHidden(5, not any(self.table.cellWidget(r, 5).isEnabled()
                                            for r in range(self.table.rowCount())))
        self.update_preview()

    def set_card_lock(self, key, checked):
        edit = self.card_edits[key]
        text = edit.toPlainText() if isinstance(edit, QTextEdit) else edit.text()
        self.display_overrides[key] = dict(locked=checked, value=text)
        edit.setReadOnly(not checked)
        self.update_preview()

    def edit_card_field(self, key):
        if not self.card_locks[key].isChecked(): return
        edit = self.card_edits[key]
        self.display_overrides[key] = dict(locked=True, value=edit.toPlainText() if isinstance(edit, QTextEdit) else edit.text())
        self.render_item_card()

    def render_item_card(self):
        from app.marvelous_item_presentation import item_card_fields, item_card_html
        try:
            fields = item_card_fields(self.blueprint(), name=self.name.text(), slot=self.slot.currentData(),
                                      description=self.description.toPlainText())
            self.item_preview.setHtml(item_card_html(fields))
        except ValueError:
            self.item_preview.setPlainText('Complete a valid design to preview the item.')

    def refresh_item_card(self):
        from app.marvelous_item_presentation import item_card_fields
        values = item_card_fields(self.blueprint(), name=self.name.text(), slot=self.slot.currentData(),
                                  description=self.description.toPlainText())
        for key, text in values.items():
            edit = self.card_edits[key]
            edit.blockSignals(True)
            edit.setPlainText(text) if isinstance(edit, QTextEdit) else edit.setText(text)
            edit.blockSignals(False)
        self.render_item_card()

    def blueprint(self):
        from PySide6.QtCore import Qt
        contributions = [{'catalog_key': self.table.item(r, 0).data(Qt.ItemDataRole.UserRole),
                          'complexity': self.table.cellWidget(r, 1).value() + self.table.cellWidget(r, 4).value(),
                          'additional_spell_points': self.table.cellWidget(r, 4).value(),
                          'alternative': self.table.cellWidget(r, 2).isChecked(),
                          'alternative_group': self.table.cellWidget(r, 3).value()}
                         for r in range(self.table.rowCount())]
        for r, contribution in enumerate(contributions):
            choice = self.table.cellWidget(r, 5).currentData()
            if choice != '': contribution['effect_choice'] = choice
            if names := self.table.item(r, 0).data(Qt.ItemDataRole.UserRole + 1): contribution['effect_spheres'] = list(names)
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
                    automation_status='rules_only', display_overrides=self.display_overrides,
                    crafting_tradition=self.crafting_tradition, drawbacks=self.drawbacks,
                    area_bound_mode=self.area_bound.currentData(),
                    base_weight_lb=None if self.base_weight.value() < 0 else self.base_weight.value())

    def quotation(self):
        return quote_marvelous_blueprint(self.blueprint())

    def update_preview(self, *_):
        selected_drawback = self.drawbacks_list.currentRow()
        self.drawbacks_list.clear()
        for record in self.drawbacks:
            self.drawbacks_list.addItem(f"{record['name']}\n−{record['reduction']} complexity · {record['source']}")
            self.drawbacks_list.item(self.drawbacks_list.count() - 1).setToolTip(record.get('description', ''))
        if selected_drawback >= 0:
            self.drawbacks_list.setCurrentRow(min(selected_drawback, len(self.drawbacks) - 1))
        self.tradition_button.setText(self.crafting_tradition['name'] if self.crafting_tradition else 'Choose a crafting tradition…')
        self.clear_tradition.setEnabled(self.crafting_tradition is not None)
        from app.marvelous_item_rules import crafting_item_limitations
        self.area_bound.setVisible('crafting:area-bound' in crafting_item_limitations(self.blueprint()))
        self.feats_button.setText(f'Integrate feats… ({len(self.feat_integrations)})')
        from app.marvelous_item_rules import missing_construction_prerequisites, missing_construction_alternatives
        contributions = self.blueprint()['contributions']
        self.table.setColumnHidden(3, not any(row.get('alternative') for row in contributions))
        self.add_prerequisites.setEnabled(bool(missing_construction_prerequisites(contributions) or missing_construction_alternatives(contributions)))
        try:
            complexity, price, quote = self.quotation()
            self.cost_formula.setText('Cost: ' + marvelous_price_formula(self.blueprint())
                                      + '\nComplexity: ' + marvelous_complexity_formula(self.blueprint())
                                      + '\nMaterials: ' + marvelous_materials_formula(self.blueprint()))
            from app.marvelous_item_rules import marvelous_effect_plan
            self.cost_formula.setToolTip('\n'.join(f'Power {index + 1}: {marvelous_complexity_formula(marvelous_effect_plan(self.blueprint(), index))}'
                for index in range(1 + len(self.extra_effects))))
            self.refresh_item_card()
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
            self.result.setText(f'Market price {float(price.market_price_gp):,.2f} gp · Materials {float(quote.cost_gp):,.2f} gp · Craft DC {quote.dc} · Save DC {price.save_dc}')
            self.preview.setHtml(f'<h2>{escape(self.name.text())}</h2><p>{escape(self.sphere.currentText())} · Complexity {complexity}</p>'
                f'<p>{escape(self.description.toPlainText())}</p><h3>Calculated base effect</h3>'
                + (f'<h3>Crafting tradition: {escape(self.crafting_tradition["name"])}</h3><p>{escape(self.crafting_tradition["description"])}</p><p>Cheap pricing and Simple complexity adjustments are automatic where applicable. Other tradition requirements/effects require manual review.</p>' if self.crafting_tradition else '')
                + ''.join(f'<p><b>{escape(key.title())}:</b> {escape(value)}</p>' for key, value in effect_detail_lines(effect))
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
            self.cost_formula.setText('Cost: invalid design — ' + str(error))
            self.render_item_card()
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


class MarvelousFeatDialog(QDialog):
    """Draft-only choices; shared rules price and validate the integrations."""
    def __init__(self, available, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Integrated feats'); self.resize(760, 420)
        root = QVBoxLayout(self)
        notice = QLabel('Base contribution is +1 per feat. Metamagic adds its additional SP cost. Review effect compatibility and minimum CL/MSB; unsupported effects remain manual.')
        notice.setWordWrap(True); root.addWidget(notice)
        picker = QHBoxLayout(); root.addLayout(picker)
        self.feat = QComboBox(); self.feat.addItem('Choose a possessed feat…', '')
        for name in available: self.feat.addItem(name, name)
        picker.addWidget(self.feat, 1)
        add = QPushButton('Add feat'); picker.addWidget(add); add.clicked.connect(self.add_selected)
        self.table = QTableWidget(0, 3); self.table.setHorizontalHeaderLabels(['Feat', 'Metamagic', 'Additional SP'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)
        remove = QPushButton('Remove selected feat'); root.addWidget(remove)
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()) if self.table.currentRow() >= 0 else None)
        for record in records: self.add_record(record)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.confirm); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def add_record(self, record):
        from PySide6.QtCore import Qt
        if any(self.table.item(row, 0).text().casefold() == record['name'].casefold() for row in range(self.table.rowCount())): return
        row = self.table.rowCount(); self.table.insertRow(row)
        name = QTableWidgetItem(record['name']); name.setData(Qt.ItemDataRole.UserRole, dict(record))
        name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable); self.table.setItem(row, 0, name)
        metamagic = QCheckBox(); metamagic.setChecked(record.get('metamagic', False)); self.table.setCellWidget(row, 1, metamagic)
        points = QSpinBox(); points.setRange(0, 100); points.setValue(record.get('additional_spell_points', 0))
        points.setEnabled(metamagic.isChecked()); self.table.setCellWidget(row, 2, points)
        metamagic.toggled.connect(points.setEnabled)
        metamagic.toggled.connect(lambda enabled: points.setValue(0) if not enabled else None)

    def add_selected(self):
        from app.marvelous_item_rules import feat_integration_defaults
        if self.feat.currentData(): self.add_record(feat_integration_defaults(self.feat.currentData()))

    def records(self):
        from PySide6.QtCore import Qt
        return [{**self.table.item(row, 0).data(Qt.ItemDataRole.UserRole),
                 'metamagic':self.table.cellWidget(row, 1).isChecked(),
                 'additional_spell_points':self.table.cellWidget(row, 2).value()}
                for row in range(self.table.rowCount())]

    def confirm(self):
        from app.marvelous_item_rules import feat_integration_complexity
        try: feat_integration_complexity(self.records())
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot integrate feats', str(error)); return
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
        self.recharge = QPushButton('Record special recharge'); self.recharge.setEnabled(False)
        root.addWidget(self.recharge); self.recharge.clicked.connect(self.record_recharge)
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
        self.recharge.setEnabled(bool(item and item.data(Qt.ItemDataRole.UserRole + 3)))

    def record_recharge(self):
        from PySide6.QtCore import Qt
        selected = self.table.item(self.table.currentRow(), 0)
        if selected is None: return
        requirements = selected.data(Qt.ItemDataRole.UserRole + 3)
        if not requirements: return
        if QMessageBox.question(self, 'Confirm special recharge', selected.text() + '\n\n'
                + '\n'.join(requirements) + '\n\nHave these requirements been fulfilled? This restores daily uses; no event, creature or day is tracked automatically.') != QMessageBox.StandardButton.Yes:
            return
        try:
            restored = self.repository.record_marvelous_recharge(self.character_id,
                selected.data(Qt.ItemDataRole.UserRole), confirmed=True)
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot recharge item', str(error)); return
        self.changed = self.changed or bool(restored)
        self.refresh(); self.result.setText(f'Recorded special recharge: restored {restored} daily uses.')

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
                from app.marvelous_item_rules import marvelous_manual_recharge_requirements
                name.setData(Qt.ItemDataRole.UserRole + 3, list(marvelous_manual_recharge_requirements(plan)) if custom else [])
                name.setToolTip('Double-click to edit this custom design.' if custom else 'Published catalog item; custom design controls do not apply.')
                self.table.setItem(row, 0, name)
                self.table.setItem(row, 1, QTableWidgetItem('Unlimited' if remaining is None else str(remaining)))
                detail = QTableWidgetItem(effect['power']); detail.setToolTip('\n'.join(f'{k}: {v}' for k, v in effect_detail_lines(effect)))
                self.table.setItem(row, 2, detail)
                automatic = all(automatic_self_effect(entry[1]) is not None for entry in effects) if mixed else automatic_self_effect(power) is not None
                automatic_label = {'life:cure': 'Cure living recipient', 'life:temporary-hp': 'Apply temporary HP',
                                   'protection:aegis': 'Apply aegis to recipient'}
                button = QPushButton(automatic_label[power['base_power']] if automatic else 'Record use — manual effect')
                from app.marvelous_base_powers import automatic_damage_dice
                if not custom: button.setText('Use — resolve action manually')
                if not mixed and (automatic_damage_dice(power) is not None or (not custom and 'damage_dice' in effect)):
                    button.setText('Use and roll damage')
                if mixed: button.setText(('Apply mixed effects' if automatic else 'Use mixed power — manual') if index == 0 else 'Included in mixed activation')
                available = all(entry[2] != 0 for entry in effects) if mixed else remaining != 0
                usable = metadata.get('marvelous_project', {}).get('status', 'complete') == 'complete'
                target_allowed = not automatic or self.recipient.currentData() == self.character_id or all(entry[3]['range'] != 'Personal' for entry in (effects if mixed else [(index, power, remaining, effect)]))
                button.setEnabled(available and usable and item.quantity == 1 and (not mixed or index == 0) and target_allowed)
                if not target_allowed: button.setToolTip('Personal-range effects can only affect the item user.')
                if not usable: button.setToolTip('Construction has not produced a usable item.')
                if mixed: button.setToolTip('Using the primary control spends one use of every limited component together. ' + ('Supported components apply atomically.' if automatic else 'Apply the combined effect manually.'))
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
        self.result.setText('Activated: ' + ' · '.join(f'{key}: {value}' for key, value in effect_detail_lines(effect))
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
