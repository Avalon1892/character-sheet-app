"""Compact Overview statistics using the existing sheet's live bindings."""
from functools import partial
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QCheckBox, QVBoxLayout, QHBoxLayout, QGridLayout
from app.models import ABILITIES
from .components import card, ResponsiveRow
from .stat_cards import MetricCard, metric_group


def statistic(title, value=None, callback=None):
    box = QWidget()
    box.setObjectName("refinedStat")
    root = QVBoxLayout(box)
    root.setContentsMargins(3, 3, 3, 3)
    root.setSpacing(2)
    label = QLabel(title)
    label.setObjectName("refinedMuted")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    number = QPushButton("—") if callback else QLabel("—")
    number.setObjectName("refinedNumber")
    if callback:
        number.clicked.connect(callback)
    else:
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
    root.addWidget(label)
    root.addWidget(number)
    return box, number


def build_statistics(sheet):
    section = QWidget()
    root = QVBoxLayout(section)
    root.setContentsMargins(0,0,0,0)
    root.setSpacing(12)
    health = card("Health")
    barrow = QHBoxLayout()
    sheet.classic_hp_bar = sheet._health_bar()
    barrow.addWidget(sheet.classic_hp_bar,1)
    init = MetricCard("Initiative", partial(sheet._show_combat_breakdown,"initiative","Initiative"))
    sheet._classic_combat_labels["initiative"] = init.value
    sheet.refined_stat_cards = {"initiative":init}
    barrow.addWidget(init)
    health.layout().addLayout(barrow)
    actions = sheet._hp_adjustment_row(classic=True)
    adjust = QPushButton("Edit HP…")
    actions.addWidget(adjust)
    health.layout().addLayout(actions)
    controls = QWidget()
    grid = QGridLayout(controls)
    grid.setContentsMargins(0,0,0,0)
    for column, (key,title,minimum) in enumerate((("maximum","Maximum",0),("current","Current",-9999),("temporary","Temporary",0),("nonlethal","Nonlethal",0))):
        field = sheet._hp_spin(minimum,99999)
        setattr(sheet,"classic_hp_"+key,field)
        grid.addWidget(QLabel(title),0,column)
        grid.addWidget(field,1,column)
        field.valueChanged.connect(sheet._save_classic_hit_points)
    sheet.classic_hp_auto = QCheckBox("Automatic maximum")
    sheet.classic_hp_auto.toggled.connect(sheet._save_classic_hit_points)
    grid.addWidget(sheet.classic_hp_auto,2,0,1,4)
    sheet.classic_hp_status = QLabel()
    sheet.classic_hp_status.hide()
    health.layout().addWidget(controls)
    controls.hide()
    adjust.clicked.connect(lambda: controls.setVisible(controls.isHidden()))
    sheet.refined_hp_controls = controls
    abilities = card("Abilities")
    row = QHBoxLayout()
    for key,name,abbreviation in ABILITIES:
        tile, score = statistic(abbreviation, callback=partial(sheet._show_ability_breakdown,key,name))
        modifier = QLabel("+0")
        modifier.setAlignment(Qt.AlignmentFlag.AlignCenter)
        modifier.setObjectName("refinedModifier")
        modifier.setToolTip(name + " modifier")
        tile.layout().addWidget(modifier)
        summary = QLabel()
        summary.hide()
        sheet._classic_ability_labels[key] = (score,modifier,summary)
        row.addWidget(tile,1)
    abilities.layout().addLayout(row)
    root.addWidget(ResponsiveRow(health, abilities, breakpoint=1100))
    armor = metric_group("Armor Class")
    saves = metric_group("Saving Throws")
    maneuvers = metric_group("Combat Maneuvers")
    sheet.refined_defense_groups = (armor,saves,maneuvers)

    def combat(key,title,**options):
        tile=MetricCard(title,partial(sheet._show_combat_breakdown,key,title),**options)
        sheet.refined_stat_cards[key]=tile
        sheet._classic_combat_labels[key]=tile.value
        return tile

    armor.layout().addWidget(combat("ac","Total AC",primary=True))
    secondary=QHBoxLayout()
    secondary.addWidget(combat("touch_ac","Touch",compact=True),1)
    secondary.addWidget(combat("flat_footed_ac","Flat-footed",compact=True),1)
    armor.layout().addLayout(secondary)
    save_row=QHBoxLayout()
    for key,title,hint in (("fortitude","Fortitude","CON"),("reflex","Reflex","DEX"),("will","Will","WIS")):
        save_row.addWidget(combat(key,title,hint=hint),1)
    saves.layout().addLayout(save_row)
    physical=QHBoxLayout()
    physical.addWidget(combat("cmb","CMB"),1)
    physical.addWidget(combat("cmd","CMD"),1)
    maneuvers.layout().addLayout(physical)
    magic=metric_group("Magic Maneuvers",magic=True)
    magic.layout().setContentsMargins(7,6,7,6)
    magic_row=QHBoxLayout()
    sheet._classic_magic_skill_rows = {}
    sheet._classic_magic_skill_labels = {}
    for key in ("msb","msd"):
        tile=MetricCard(key.upper(),partial(sheet._show_magic_metric,key),compact=True)
        sheet._classic_magic_skill_rows[key]=tile
        sheet._classic_magic_skill_labels[key]=tile.value
        sheet.refined_stat_cards[key]=tile
        magic_row.addWidget(tile,1)
        tile.hide()
    magic.layout().addLayout(magic_row)
    maneuvers.layout().addWidget(magic)
    sheet.refined_magic_maneuvers=magic
    root.addWidget(ResponsiveRow(armor,saves,maneuvers,breakpoint=950))
    return section
