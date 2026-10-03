"""Refined character panels; reuse existing controls and equipment services."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from app.models import ABILITIES
from .pages import clear_layout
from .components import ResponsiveRow


def combine_ability_advancement(sheet):
    # Retain the old presentation widgets as owned, hidden objects. All live
    # editors and their existing save/refresh connections move into one grid.
    retired = QWidget(sheet)
    retired.hide()
    sheet._retired_ability_panels = retired
    for old in (sheet.abilities_section, sheet.ability_score_increase_section):
        old.setParent(retired)
    section = QWidget()
    section.setObjectName('sheetSection')
    layout = QVBoxLayout(section)
    layout.addWidget(sheet._section_title('ABILITY SCORES & ADVANCEMENT'))
    layout.addWidget(sheet.asi_summary)
    groups = []
    for _ in range(2):
        group = QWidget()
        grid = QGridLayout(group)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for column, text in enumerate(('Ability', 'Base', 'Level +', 'Total', 'Mod', 'Adjustments', '')):
            label = QLabel(text)
            label.setObjectName('refinedMuted')
            grid.addWidget(label, 0, column)
        grid.setColumnStretch(5, 1)
        groups.append(group)
    for index, (key, name, abbreviation) in enumerate(ABILITIES):
        grid = groups[index // 3].layout()
        row = index % 3 + 1
        base, total, modifier = sheet._ability_controls[key]
        buttons = base.parentWidget().findChildren(QPushButton)
        code = QLabel(abbreviation)
        code.setToolTip(name)
        code.setObjectName('refinedAbilityCode')
        allocation = sheet.asi_controls[key]
        for control in (base, allocation):
            control.setFixedWidth(72)
            control.setMinimumHeight(38)
        for label in (total, modifier):
            label.setMinimumSize(58, 38)
            label.setMaximumSize(75, 48)
            label.setObjectName('refinedNumber')
        for column, widget in enumerate((code, base, allocation, total, modifier, sheet._ability_adjustment_labels[key])):
            grid.addWidget(widget, row, column)
        if buttons:
            buttons[0].setToolTip('Edit adjustments and view ' + name + ' calculation')
            grid.addWidget(buttons[0], row, 6)
    layout.addWidget(ResponsiveRow(*groups, breakpoint=1250))
    section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    sheet.abilities_section = section
    sheet.ability_score_increase_section = section
    sheet.custom_sections['base_abilities'] = section
    sheet.custom_sections.pop('ability_score_increases', None)


def compact_martial_focus(sheet):
    section = sheet.custom_sections['martial_focus']
    title = section.findChild(QLabel, 'refinedSectionTitle')
    buttons = {button.text(): button for button in section.findChildren(QPushButton)}
    clear_layout(section.layout())
    heading = QHBoxLayout()
    heading.addWidget(title, 1)
    sheet.martial_focus_setup_toggle.setText('Settings')
    sheet.martial_focus_setup_toggle.setMaximumWidth(100)
    heading.addWidget(sheet.martial_focus_setup_toggle)
    section.layout().addLayout(heading)
    row = QHBoxLayout()
    readout = QVBoxLayout()
    sheet.martial_focus_counter.setObjectName('refinedNumber')
    sheet.martial_focus_counter.setMinimumWidth(100)
    readout.addWidget(sheet.martial_focus_counter)
    readout.addWidget(sheet.martial_focus_pips)
    row.addLayout(readout)
    sheet.martial_focus_status.setMaximumHeight(32)
    sheet.martial_focus_status.setProperty('refinedFocusState', True)
    sheet.martial_focus_status.setMinimumWidth(110)
    row.addWidget(sheet.martial_focus_status)
    row.addStretch()
    for key in ('Spend', 'Regain'):
        button = buttons[key]
        button.setMinimumHeight(36)
        row.addWidget(button)
    section.layout().addLayout(row)
    section.layout().addWidget(sheet.martial_focus_setup)
    sheet.martial_focus_setup.setVisible(sheet.martial_focus_setup_toggle.isChecked())
    sheet._refined_focus_buttons = (buttons['Spend'], buttons['Regain'])


def create_equipment_figure_section(sheet):
    section = QWidget()
    section.setObjectName('sheetSection')
    layout = QVBoxLayout(section)
    layout.addWidget(sheet._section_title('EQUIPMENT FIGURE'))
    sheet.refined_equipment_figure = None
    sheet.custom_sections['equipment_figure'] = section


def refresh_equipment_figure(sheet):
    if sheet.character_id is None or 'equipment_figure' not in sheet.custom_sections:
        return
    from app.equipment_wearing import EquipmentWearService
    from app.ui.equipment_figure import EquipmentFigurePanel
    panel = sheet.refined_equipment_figure
    if panel is None or panel.service.character_id != sheet.character_id:
        if panel is not None:
            panel.setParent(None)
            panel.deleteLater()
        section = sheet.custom_sections['equipment_figure']
        panel = EquipmentFigurePanel(EquipmentWearService(sheet.repository, sheet.character_id), section)
        panel.equipment_changed.connect(sheet._equipment_usage_changed)
        section.layout().addWidget(panel)
        sheet.refined_equipment_figure = panel
    else:
        panel.refresh()


def separate_class_levels(sheet):
    """Reuse the existing class controls and signals in an independent block."""
    identity = sheet.overview_section.layout()
    section = QWidget()
    section.setObjectName("sheetSection")
    layout = QVBoxLayout(section)
    layout.setContentsMargins(9, 9, 9, 9)
    start = next(i for i in range(identity.count())
                 if identity.itemAt(i).layout() is not None
                 and identity.itemAt(i).layout().indexOf(sheet.level_summary) >= 0)
    while identity.count() > start:
        item = identity.takeAt(start)
        if item.widget() is not None:
            layout.addWidget(item.widget())
        elif item.layout() is not None:
            layout.addLayout(item.layout())
        else:
            layout.addItem(item)
    sheet.custom_sections["class_levels"] = section
