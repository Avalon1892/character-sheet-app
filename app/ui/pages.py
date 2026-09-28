from __future__ import annotations

from PySide6.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
)

from app.ui.components import sheet_page
from app.ui.bonded_companion_page import BondedCompanionPanel
from app.ui.crafting import CraftingPanel




def compose_character_pages(sheet, root_layout: QVBoxLayout) -> QTabWidget:
    """Initialize shared sections and companion panels for Refined."""
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

    # Sections must belong to the sheet before shared detail/formula wiring
    # discovers their controls. Refined assigns their final layouts afterwards.
    for section in sheet.custom_sections.values():
        if section.parent() is None:
            section.setParent(sheet)
    root_layout.addWidget(sheet.audit_status_bar)
    root_layout.addWidget(sheet.page_tabs, 1)
    return sheet.page_tabs
