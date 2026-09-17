from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.components import sheet_page
from app.ui.bonded_companion_page import BondedCompanionPanel
from app.ui.crafting import CraftingPanel


def build_masthead() -> QFrame:
    masthead = QFrame()
    masthead.setObjectName("sheetMasthead")
    layout = QHBoxLayout(masthead)
    layout.setContentsMargins(16, 10, 16, 10)
    brand = QVBoxLayout()
    name = QLabel("PATHFINDER 1E  ·  SPHERES")
    name.setObjectName("sheetBrand")
    subtitle = QLabel("INTERACTIVE PATHFINDER CHARACTER RECORD")
    subtitle.setObjectName("sheetBrandSubtitle")
    brand.addWidget(name)
    brand.addWidget(subtitle)
    layout.addLayout(brand)
    layout.addStretch()
    return masthead


def compose_build_page(sheet, layout: QVBoxLayout) -> None:
    sheet.custom_layouts["build_main"] = layout
    layout.addWidget(sheet.sheet_masthead)
    layout.addWidget(sheet.overview_section)
    layout.addWidget(sheet.advancement_budget_section)

    progress = QHBoxLayout()
    sheet.custom_layouts["build_progress"] = progress
    progress.setSpacing(10)
    progress.setAlignment(Qt.AlignmentFlag.AlignTop)
    progress.addWidget(sheet.favored_class_bonus_section, 3)
    progress.addWidget(sheet.ability_score_increase_section, 2)
    layout.addLayout(progress)

    columns = QHBoxLayout()
    sheet.custom_layouts["build_columns"] = columns
    columns.setSpacing(10)
    columns.setAlignment(Qt.AlignmentFlag.AlignTop)
    fundamentals = QVBoxLayout()
    sheet.custom_layouts["build_fundamentals"] = fundamentals
    fundamentals.setSpacing(10)
    fundamentals.addWidget(sheet.abilities_section)
    fundamentals.addWidget(sheet.proficiencies_section)
    fundamentals.addWidget(sheet.custom_trackers_section)
    fundamentals.addStretch()
    columns.addLayout(fundamentals, 3)

    systems = QVBoxLayout()
    sheet.custom_layouts["build_systems"] = systems
    systems.setSpacing(10)
    systems.addWidget(sheet.traditional_casting_section)
    systems.addWidget(sheet.casting_profile_section)
    systems.addWidget(sheet.traditions_section)
    systems.addWidget(sheet.optional_traditions_section)
    systems.addWidget(sheet.sphere_build_section)
    systems.addStretch()
    columns.addLayout(systems, 4)
    layout.addLayout(columns)
    layout.addStretch()


def compose_core_page(sheet, layout: QVBoxLayout) -> None:
    sheet.custom_layouts["core_main"] = layout
    # The permanent play hierarchy is intentionally different from the build
    # page: derived combat values first, then the long skill reference beside
    # the frequently changed trackers and actions.  Every section keeps its
    # stable key, so Build Mode layouts and saved characters remain compatible.
    layout.addWidget(sheet.classic_statistics_section)

    columns = QHBoxLayout()
    sheet.custom_layouts["core_columns"] = columns
    columns.setSpacing(10)
    columns.setAlignment(Qt.AlignmentFlag.AlignTop)

    left = QVBoxLayout()
    sheet.custom_layouts["core_left"] = left
    left.setSpacing(10)
    left.addWidget(sheet.skills_section)
    left.addStretch()
    columns.addLayout(left, 5)

    right = QVBoxLayout()
    sheet.custom_layouts["core_right"] = right
    right.setSpacing(10)
    right.addWidget(sheet.movement_section)
    resources = QHBoxLayout()
    sheet.custom_layouts["core_resources"] = resources
    resources.setSpacing(10)
    resources.addWidget(sheet.martial_focus_section, 1)
    resources.addWidget(sheet.spell_point_summary_section, 1)
    right.addLayout(resources)
    right.addWidget(sheet.inquisitor_features_section)
    right.addWidget(sheet.attacks_section)

    secondary = QHBoxLayout()
    sheet.custom_layouts["core_secondary"] = secondary
    secondary.setSpacing(10)
    secondary.addWidget(sheet.special_abilities_section, 3)
    secondary.addWidget(sheet.conditions_section, 2)
    right.addLayout(secondary)
    right.addWidget(sheet.prodigy_imbue_section)
    right.addWidget(sheet.prodigy_section)
    right.addStretch()
    columns.addLayout(right, 7)

    layout.addLayout(columns)

    # Retain the previous independent blocks as opt-in building blocks.  Their
    # registry defaults are hidden, but existing character layouts continue to
    # own their visibility and may place either block freely in Build Mode.
    alternatives = QHBoxLayout()
    sheet.custom_layouts["core_alternatives"] = alternatives
    alternatives.addWidget(sheet.ability_summary_section)
    alternatives.addWidget(sheet.combat_section)
    layout.addLayout(alternatives)
    layout.addStretch()


def compose_inventory_page(sheet, layout: QVBoxLayout) -> None:
    sheet.custom_layouts["inventory_main"] = layout
    columns = QHBoxLayout()
    sheet.custom_layouts["inventory_columns"] = columns
    columns.setSpacing(10)
    columns.setAlignment(Qt.AlignmentFlag.AlignTop)

    inventory = QVBoxLayout()
    sheet.custom_layouts["inventory_items"] = inventory
    inventory.setSpacing(10)
    inventory.addWidget(sheet.equipment_section)
    inventory.addWidget(sheet.worn_items_section)
    resources = QHBoxLayout()
    sheet.custom_layouts["inventory_resources"] = resources
    resources.setSpacing(10)
    resources.addWidget(sheet.load_section, 1)
    resources.addWidget(sheet.currency_section, 1)
    inventory.addLayout(resources)
    inventory.addStretch()
    columns.addLayout(inventory, 4)

    talents = QVBoxLayout()
    sheet.custom_layouts["inventory_talents"] = talents
    talents.setSpacing(10)
    talents.addWidget(sheet.moldable_talents_section)
    talents.addWidget(sheet.martial_talents_section)
    features = QHBoxLayout()
    sheet.custom_layouts["inventory_features"] = features
    features.setSpacing(10)
    features.addWidget(sheet.feats_section)
    features.addWidget(sheet.traits_section)
    talents.addLayout(features)
    talents.addWidget(sheet.feature_details_section)
    talents.addStretch()
    columns.addLayout(talents, 6)

    layout.addLayout(columns)
    layout.addStretch()


def compose_magic_page(sheet, layout: QVBoxLayout) -> None:
    sheet.custom_layouts["magic_main"] = layout
    columns = QHBoxLayout()
    sheet.custom_layouts["magic_columns"] = columns
    columns.setSpacing(10)
    columns.setAlignment(Qt.AlignmentFlag.AlignTop)

    summary = QVBoxLayout()
    sheet.custom_layouts["magic_summary"] = summary
    summary.setSpacing(10)
    sheet.casting_play_section.setMaximumWidth(350)
    sheet.spell_level_overview_section.setMaximumWidth(350)
    sheet.magic_range_section.setMaximumWidth(350)
    summary.addWidget(sheet.casting_play_section)
    summary.addWidget(sheet.spell_level_overview_section)
    summary.addWidget(sheet.magic_range_section)
    summary.addStretch()
    columns.addLayout(summary, 1)
    records = QVBoxLayout()
    sheet.custom_layouts["magic_records"] = records
    records.setSpacing(10)
    records.addWidget(sheet.spells_known_section, 2)
    records.addWidget(sheet.spells_prepared_section, 3)
    records.addWidget(sheet.spells_section, 3)
    records.addStretch()
    columns.addLayout(records, 4)
    layout.addLayout(columns)
    layout.addStretch()


def compose_companion_page(sheet, layout: QVBoxLayout) -> None:
    sheet.custom_layouts["companion_main"] = layout
    layout.addWidget(sheet.animal_identity_section)
    columns = QHBoxLayout()
    columns.setSpacing(10)
    columns.setAlignment(Qt.AlignmentFlag.AlignTop)
    left = QVBoxLayout(); left.setSpacing(10)
    left.addWidget(sheet.animal_statistics_section)
    left.addStretch()
    right = QVBoxLayout(); right.setSpacing(10)
    right.addWidget(sheet.animal_training_section)
    right.addStretch()
    columns.addLayout(left, 3)
    columns.addLayout(right, 2)
    layout.addLayout(columns)
    layout.addStretch()


def compose_character_pages(sheet, root_layout: QVBoxLayout) -> QTabWidget:
    """Compose the four records while retaining the historic sheet attributes."""
    sheet.sheet_masthead = build_masthead()
    sheet.page_tabs = QTabWidget()
    sheet.page_tabs.setObjectName("sheetPages")
    sheet.page_tabs.setDocumentMode(True)
    sheet.custom_layouts = {}

    sheet.builder_scroll, sheet.builder_canvas, sheet.builder_layout = sheet_page(
        "builderPage"
    )
    sheet.core_scroll, sheet.core_canvas, core_layout = sheet_page("corePage")
    sheet.inventory_scroll, sheet.inventory_canvas, inventory_layout = sheet_page(
        "inventoryPage"
    )
    sheet.magic_scroll, sheet.magic_canvas, magic_layout = sheet_page("magicPage")
    sheet.crafting_scroll, sheet.crafting_canvas, crafting_layout = sheet_page("craftingPage")
    sheet.crafting_section = CraftingPanel(sheet)
    crafting_layout.addWidget(sheet.crafting_section)
    crafting_layout.addStretch()
    sheet.companion_scroll, sheet.companion_canvas, companion_layout = sheet_page(
        "companionPage"
    )
    sheet.familiar_scroll, sheet.familiar_canvas, familiar_layout = sheet_page(
        "familiarPage"
    )
    sheet.corpse_puppet_scroll, sheet.corpse_puppet_canvas, corpse_layout = sheet_page(
        "corpsePuppetPage"
    )
    sheet.phantom_scroll, sheet.phantom_canvas, phantom_layout = sheet_page(
        "phantomPage"
    )
    sheet.sheet_scroll = sheet.core_scroll
    sheet.sheet_canvas = sheet.core_canvas

    compose_build_page(sheet, sheet.builder_layout)
    compose_core_page(sheet, core_layout)
    compose_inventory_page(sheet, inventory_layout)
    compose_magic_page(sheet, magic_layout)
    compose_companion_page(sheet, companion_layout)
    sheet.familiar_panel = BondedCompanionPanel(sheet.repository, "familiar")
    sheet.familiar_panel.grant_changed.connect(sheet._refresh_bonded_companions)
    familiar_layout.addWidget(sheet.familiar_panel)
    sheet.corpse_puppet_panel = BondedCompanionPanel(
        sheet.repository, "corpse_puppet"
    )
    corpse_layout.addWidget(sheet.corpse_puppet_panel)
    sheet.phantom_panel = BondedCompanionPanel(sheet.repository, "phantom")
    phantom_layout.addWidget(sheet.phantom_panel)

    sheet.custom_sections = {
        "crafting": sheet.crafting_section,
        "overview": sheet.overview_section,
        "favored_class_bonuses": sheet.favored_class_bonus_section,
        "advancement_budgets": sheet.advancement_budget_section,
        "ability_score_increases": sheet.ability_score_increase_section,
        "base_abilities": sheet.abilities_section,
        "custom_trackers": sheet.custom_trackers_section,
        "traditional_casting": sheet.traditional_casting_section,
        "casting_profile": sheet.casting_profile_section,
        "sphere_drawbacks": sheet.sphere_build_section,
        "proficiencies": sheet.proficiencies_section,
        "inquisitor_features": sheet.inquisitor_features_section,
        "special_abilities": sheet.special_abilities_section,
        "classic_statistics": sheet.classic_statistics_section,
        "movement": sheet.movement_section,
        "combat_defense": sheet.combat_section,
        "abilities": sheet.ability_summary_section,
        "imbue": sheet.prodigy_imbue_section,
        "skills": sheet.skills_section,
        "conditions": sheet.conditions_section,
        "attacks": sheet.attacks_section,
        "martial_focus": sheet.martial_focus_section,
        "spell_points": sheet.spell_point_summary_section,
        "prodigy_sequence": sheet.prodigy_section,
        "equipment": sheet.equipment_section,
        "worn_items": sheet.worn_items_section,
        "optional_traditions": sheet.optional_traditions_section,
        "traditions": sheet.traditions_section,
        "load": sheet.load_section,
        "currency": sheet.currency_section,
        "martial_talents": sheet.martial_talents_section,
        "moldable_talents": sheet.moldable_talents_section,
        "feats": sheet.feats_section,
        "traits": sheet.traits_section,
        "feature_details": sheet.feature_details_section,
        "casting_play": sheet.casting_play_section,
        "spell_level_overview": sheet.spell_level_overview_section,
        "spells_known": sheet.spells_known_section,
        "spells_prepared": sheet.spells_prepared_section,
        "magic_talents": sheet.spells_section,
        "magic_ranges": sheet.magic_range_section,
        "animal_identity": sheet.animal_identity_section,
        "animal_statistics": sheet.animal_statistics_section,
        "animal_training": sheet.animal_training_section,
    }

    sheet.page_tabs.addTab(sheet.builder_scroll, "0   CHARACTER BUILD")
    sheet.page_tabs.addTab(sheet.core_scroll, "1   CORE")
    sheet.page_tabs.addTab(sheet.inventory_scroll, "2   INVENTORY & FEATURES")
    sheet.page_tabs.addTab(sheet.magic_scroll, "3   MAGIC & SPHERES")
    sheet.page_tabs.addTab(sheet.companion_scroll, "4   ANIMAL COMPANION")
    sheet.page_tabs.addTab(sheet.crafting_scroll, "Crafting")
    root_layout.addWidget(sheet.audit_status_bar)
    root_layout.addWidget(sheet.page_tabs, 1)
    return sheet.page_tabs
