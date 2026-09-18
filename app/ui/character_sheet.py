from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from functools import partial
import html
import json
import re
from types import SimpleNamespace
from typing import Callable

from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.database import CharacterRepository
from app.item_containers import (
    carried_inventory_weight,
    is_inventory_container,
    ordered_inventory_items,
)
from app.services.advancement import character_advancement_budgets
from app.class_feature_rules import (
    archetype_granted_features,
    archetype_optional_features,
    resolve_class_features,
    resolved_feature_key,
)
from app.class_choice_rules import (
    class_choice_selection_record,
    projected_class_choice_features,
    resolve_class_choice_slots,
)
from app.class_granted_spells import synchronize_class_granted_spells
from app.class_power_rules import (
    apply_class_power_selection,
    class_power_active_feature_key,
    class_power_activation_record,
    class_power_selection_record,
    decode_class_power_keys,
    encode_class_power_keys,
    projected_class_power_features,
    resolve_class_power_sets,
)
from app.archetype_rules import (
    archetype_choice_selections_from_records,
    archetype_choices,
    decode_archetype_choice_option_keys,
    encode_archetype_choice_option_keys,
)
from app.class_capabilities import ClassCapabilities, resolve_sphere_capabilities
from app.class_proficiencies import resolved_proficiencies
from app.animal_companion_rules import (
    calculate_companion_statistics, companion_catalog, companion_entry,
    companion_progression, resolve_companion_grant,
)
from app.bonded_companion_rules import (
    bonded_companion_grants,
    reconcile_familiar_hit_points,
)
from app.custom_trackers import CustomTrackerResolver, display_number
from app.character_formulas import reference_key
from app.formulas import FormulaError, formula_references
from app.athletics_rules import athletics_packages
from app.drawback_rules import (
    drawback_bonus_feat_names,
    drawback_choice_options,
    drawback_requires_choice,
    incompatible_drawbacks,
    magic_talent_restriction_reason,
    martial_talent_restriction_reason,
    sphere_package_access,
)
from app.content import (
    archetype_entry,
    class_entry,
    entries,
    entry_by_key,
    entry_by_name,
    feat_categories,
    feat_entry,
    feat_entries,
    magic_entry,
    magic_entries,
    magic_sphere,
    magic_spheres,
    martial_entries,
    martial_entry,
    martial_sphere,
    martial_spheres,
    trait_categories,
    trait_entries,
    trait_sources,
    tradition_entry,
)
from app.tradition_rules import resolved_tradition_definition
from app.models import (
    ABILITIES,
    ABILITY_KEYS,
    ALIGNMENTS,
    ATTACK_TYPES,
    BAB_PROGRESSIONS,
    BONUS_TYPES,
    COMBAT_TARGETS,
    CONDITION_PRESETS,
    CONDITION_RULES_TEXT,
    DAMAGE_MULTIPLIERS,
    EQUIPMENT_BONUS_TYPES,
    EQUIPMENT_CATEGORIES,
    MARTIAL_TALENT_TYPES,
    SKILLS,
    SAVE_PROGRESSIONS,
    SEQUENCE_OPTION_TYPES,
    SIZES,
    SPELL_SYSTEMS,
    STAT_TARGETS,
    Attack,
    OngoingEffect,
    AdvancementAdjustment,
    AbilityScoreIncreaseAllocation,
    CastingProfile,
    CharacterDetails,
    CurrencyPurse,
    CustomTracker,
    Feat,
    FeatEffect,
    FavoredClassBonus,
    HitPoints,
    MartialFocus,
    MartialTalent,
    MovementProfile,
    ProdigySequence,
    SequenceOption,
    SkillState,
    Spell,
    SphereStatistic,
    StatModifier,
    Trait,
    SpecialAbilityAdjustment,
    ProficiencyAdjustment,
    ClassFeatureSelection,
    ClassFeatureState,
    AnimalCompanion,
)
from app.rules import (
    CalculationResult,
    automatic_class_casting,
    automatic_sphere_casting,
    automatic_traditional_casting,
    calculate_ability,
    calculate_casting_statistics,
    calculate_combat_statistics,
    calculate_attack,
    calculate_skill,
    calculate_stat,
    condition_modifiers,
    effect_class_skills,
    effect_untrained_skills,
    feat_modifiers,
    feat_attack_modifiers,
    magic_talent_attack_modifiers,
    magic_talent_modifiers,
    martial_talent_attack_modifiers,
    martial_talent_modifiers,
    trait_modifiers,
    trait_attack_modifiers,
    parse_dice,
    prodigy_adaptation_uses,
    prodigy_blended_talents,
    prodigy_caster_level,
    prodigy_inspired_sequence_bonus,
    prodigy_level,
    prodigy_sequence_maximum,
    roll_attack_and_damage,
    race_modifiers,
    recommended_hit_points,
    total_bab,
    total_base_save,
)
from app.prodigy_content import SPHERE_IMBUES, imbue_value, sphere_imbues, sphere_options
from app.exploitant_rules import (
    EXPLOITANT_ARCHETYPE_KEY,
    MOLDABLE_SOURCE_KEY,
    effective_magic_talents,
    effective_martial_talents,
    exploitant_level,
    exploitant_has_moldable_talents,
    moldable_talent_capacity,
    moldable_talent_kinds,
    save_moldable_entries,
    resolve_exploitant_finisher,
    validate_moldable_entries,
)
from app.adaptation_rules import (
    ADAPTATION_SOURCE_KEY,
    adaptation_action_text,
    adaptation_change_cost,
    adaptation_profile,
    validate_adaptation_entries,
)
from app.presentation import (
    FEATURE_TARGET_LABELS,
    effect_display,
    effects_display,
    feature_details_html,
    feature_status,
    feature_summary_text,
    readable_tooltip,
)
from app.spell_rules import (
    spell_record_presentation,
    sphere_spell_point_costs,
    spell_level_for_class,
)
from app.spellbook import SpellBookService
from app.martial_book import MartialBookService
from app.inventory_organization import InventoryOrganizationService
from app.traditional_spellcasting import (
    prepared_caster_capacities as shared_prepared_caster_capacities,
    spontaneous_caster_capacities as shared_spontaneous_caster_capacities,
    traditional_casting_classes as shared_traditional_casting_classes,
)
from app.sphere_rules import (
    base_sphere_choice_options,
    granted_martial_sphere_abilities,
    granted_sphere_abilities,
    martial_base_granted_talent_name,
    martial_base_choice_for_entry,
)
from app.services.character_calculations import CharacterCalculationService
from app.skill_specializations import (
    base_skill_key,
    character_skill_definitions,
    skill_formula_entity_id,
    specialization_for,
)
from app.ui.components import (
    DetailsPanel,
    FormulaLineEdit,
    FormulaNumberEdit,
    SortableTableItem,
    TableColumn,
    action_menu_button,
    configure_columns,
    configure_record_table,
    fit_table_rows,
    forward_editor_wheel_to_page,
    numeric_field,
    populate_record_table,
    section_title,
    sheet_page,
)
from app.ui.race_dialog import RaceCatalogDialog
from app.race_rules import resolved_race, resolved_racial_traits
from app.ui.tracker_blocks import CustomTrackerBlock
from app.ui.spellbook_dialog import SpellBookDialog
from app.ui.martial_book_dialog import MartialBookDialog
from app.ui.moldable_talents_dialog import MoldableTalentsDialog
from app.ui.inventory_dialog import InventoryOrganizerDialog
from app.ui.character_audit_dialog import (
    CharacterAuditStatusBar,
    GuidedLevelUpDialog,
    LevelUpAction,
)
from app.character_audit import build_character_audit
from app.audit_resolution import AuditResolutionOutcome, AuditUndoToken
from app.ui.pages import compose_character_pages
from app.ui.feature_sections import (
    build_feature_details_section,
    build_saved_feature_section,
)
from app.feature_registry import FeatureKind
from app.ui.dialogs import (
    AttackDialog,
    ClassLevelDialog,
    SpecialAbilityDialog,
    ProficiencyDialog,
    ConditionDialog,
    OngoingEffectDialog,
    CustomTrackerDialog,
    EquipmentDialog,
    WornSlotsDialog,
    ItemEnchantmentsDialog,
    ItemCatalogDialog,
    ItemChoiceDialog,
    AnimalCompanionFeatCatalogDialog,
    FeatCatalogDialog,
    FeatChoiceDialog,
    FeatDialog,
    MagicTalentCatalogDialog,
    MagicCatalogChoiceDialog,
    MartialTalentCatalogDialog,
    MartialTalentDialog,
    ModifierDialog,
    SequenceOptionDialog,
    SkillDialog,
    SphereAcquisitionDialog,
    SphereStatisticDialog,
    SpellDialog,
    PreparedSpellDialog,
    TraditionalSpellCatalogDialog,
    StatBreakdownDialog,
    TraitCatalogDialog,
    TraitDialog,
    TraditionCatalogDialog,
    TraditionChoiceDialog,
    ClassFeatureStateDialog,
)
from app.ui.class_choice_dialog import ClassChoiceDialog
from app.ui.class_power_dialog import ClassPowerDialog
from app.class_feature_systems import (
    class_feature_effect_summary,
    resolve_class_feature_modules,
)
from app.ui.sheet_sections import SheetSectionsMixin
from app.prepared_spell_rules import (
    PreparedCasterCapacity,
    bonus_spell_slots,
    validate_preparation_capacity,
)
from app.spontaneous_spell_rules import (
    SpontaneousCasterCapacity,
)
from app.item_effects import (
    automation_from_json,
    automation_for_item,
    automation_summary,
    effective_item_state,
    effect_is_active,
    item_choices,
    item_modifiers,
    preferred_item_state,
)
from app.item_enchantments import (
    effective_enhancement_bonus,
    enchantment_summary,
    item_display_name,
    item_price_breakdown,
)


PRODIGY_SPECIAL_ABILITIES = (
    (1, "Proficiencies", "Proficient with simple weapons, light armor, and bucklers. A first character level may also select a martial tradition."),
    (1, "Casting", "A Prodigy is a Mid-Caster and chooses Intelligence, Wisdom, or Charisma as the casting ability."),
    (1, "Spell Pool", "Spell points equal Prodigy level plus the casting ability modifier, minimum 1; refreshes after roughly 8 hours of rest."),
    (1, "Blended Training", "Gain combat or magic talents from the class progression, plus the two starting magic talents granted by Casting."),
    (1, "Sequence", "Openers begin a sequence, links build it, and finishers spend it. The initial maximum is 4 links."),
    (1, "Integrated Techniques", "Owned martial and skill spheres grant additional openers, links, and finishers automatically."),
    (1, "Inspired Sequence", "While a sequence is active, gain an insight bonus to attack, damage, and caster level equal to half its links, minimum +1."),
    (2, "Adaptation", "Temporarily gain a combat or magic talent you do not possess. Uses per day equal 3 + half Prodigy level."),
    (2, "Imbue Sequence", "When starting a sequence, imbue it with a magic sphere you possess, gaining its imbuement and unlocking its finishers."),
    (3, "Sequence — 5 Links", "The maximum sequence length increases to 5."),
    (3, "Steady Skill", "Choose a Prodigy class skill after resting; you may take 10 under pressure and can expend focus to take 15 a limited number of times."),
    (3, "Skill Attunement", "A suitable skill-sphere attunement may be selected in place of Steady Skill."),
    (4, "Unbroken Sequence", "Expend martial focus to prevent certain incapacitating conditions from ending the sequence for a limited duration."),
    (5, "Improved Adaptation", "Adaptation can grant two talents at once, with faster options when selecting only one talent."),
    (6, "Sequence — 6 Links", "The maximum sequence length increases to 6."),
    (7, "Reflect Spell", "As an immediate action, expend martial focus and make an MSB check against MSD to reflect a spell or sphere effect back at its caster."),
    (8, "Greater Adaptation", "Use Adaptation for two talents as a move action or one talent as a swift action."),
    (9, "Sequence — 7 Links", "The maximum sequence length increases to 7."),
    (10, "Share Adaptation", "Spend two Adaptation uses to grant a qualifying combat or magic talent to a nearby ally for 1 minute."),
    (11, "Variable Skill", "Spend a spell point as a full-round action to change the skill chosen for Steady Skill."),
    (12, "Sequence — 8 Links", "The maximum sequence length increases to 8."),
    (13, "Master Adaptation", "Adaptation can grant up to three talents with action costs based on how many talents are selected."),
    (14, "Flawless Sequence", "The sequence no longer loses a link for failing to add one, and incapacitating conditions no longer require focus to preserve it."),
    (15, "Sequence — 9 Links", "The maximum sequence length increases to 9."),
    (16, "Greater Reflect Spell", "Reflect Spell no longer causes staggered, and a successful reflection automatically restores martial focus."),
    (17, "Grandmaster Adaptation", "Adaptation may grant one talent as an immediate action or three talents as a swift action."),
    (18, "Sequence — 10 Links", "The maximum sequence length increases to 10."),
    (19, "Skill Juggler", "Steady Skill may be changed after one minute of practice, and expending focus can allow taking 20 instead of 15."),
    (20, "Perfected Prodigy", "Sequences begin with half the casting ability modifier in links, and any number of talents may be gained with Adaptation as a swift action."),
)

FEAT_TARGET_LABELS = FEATURE_TARGET_LABELS

SKILL_LABELS = {definition.key: definition.name for definition in SKILLS}



def _sphere_stat_formula_keys(sphere: str) -> dict[str, str]:
    """Translate dialog field names to the shared sphere-stat formula record."""
    slug = reference_key(sphere)[:61]
    return {
        "caster_level_bonus": f"{slug}_cl",
        "dc_bonus": f"{slug}_dc",
    }


def _is_archetype_exchange_selection(selection: ClassFeatureSelection) -> bool:
    """Recognize both current and legacy persisted optional exchanges."""

    feature_key = str(selection.feature_key or "")
    option_type = re.sub(
        r"[^a-z]+", " ", str(selection.option_type or "").casefold()
    ).strip()
    return feature_key.startswith("archetype-option:") or option_type in {
        "archetype exchange",
        "optional exchange",
    }


def _is_archetype_choice_selection(selection: ClassFeatureSelection) -> bool:
    feature_key = str(selection.feature_key or "")
    option_type = re.sub(
        r"[^a-z]+", " ", str(selection.option_type or "").casefold()
    ).strip()
    return feature_key.startswith("archetype-choice:") or option_type == "archetype choice"

def _feat_effect_target_label(target: str) -> str:
    from app.presentation import effect_target_label

    return effect_target_label(target, SKILL_LABELS)


def _feat_effect_display(effect: FeatEffect | dict) -> str:
    return effect_display(effect, SKILL_LABELS)


def _feat_effects_display(feat: Feat | Trait | MartialTalent | Spell) -> str:
    return effects_display(feat, SKILL_LABELS)


class _FormulaStatBreakdownDialog(StatBreakdownDialog):
    """Stat breakdown whose custom modifiers use the shared formula editor."""

    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        target: str,
        title: str,
        result_provider: Callable[[], CalculationResult],
        formula_evaluator: Callable[[str], float],
        formula_suggestions: Callable[[], tuple],
        parent: QWidget | None = None,
    ) -> None:
        self._formula_evaluator = formula_evaluator
        self._formula_suggestions = formula_suggestions
        super().__init__(
            repository, character_id, target, title, result_provider, parent
        )

    def _add_modifier(self) -> None:
        if self.target in ABILITY_KEYS:
            default_type = "enhancement"
        elif self.target in {"fortitude", "reflex", "will"}:
            default_type = "resistance"
        elif self.target == "ac":
            default_type = "armor"
        else:
            default_type = "untyped"
        dialog = ModifierDialog(
            self.title,
            default_type,
            self,
            formulas={},
            formula_evaluator=self._formula_evaluator,
            formula_suggestions=self._formula_suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        modifier_id = self.repository.add_modifier(
            self.character_id,
            self.target,
            dialog.source,
            dialog.bonus_type,
            dialog.value,
        )
        for field_key, expression in dialog.numeric_formulas.items():
            self.repository.set_numeric_formula(
                self.character_id,
                "modifier",
                modifier_id,
                field_key,
                expression,
            )
        self.refresh()

    def _remove_modifier(self) -> None:
        modifier_id = self._selected_modifier_id()
        if modifier_id is None:
            QMessageBox.information(
                self, "Select a modifier", "Select a custom modifier row."
            )
            return
        for (_entity_type, _entity_id, field_key) in tuple(
            self.repository.numeric_formulas(
                self.character_id, "modifier", modifier_id
            )
        ):
            self.repository.set_numeric_formula(
                self.character_id, "modifier", modifier_id, field_key, ""
            )
        self.repository.delete_modifier(self.character_id, modifier_id)
        self.refresh()


class CharacterSheetWidget(SheetSectionsMixin, QWidget):
    custom_sections_changed = Signal()
    formula_values_changed = Signal()

    def __init__(self, repository: CharacterRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id: int | None = None
        self._loading = False
        self._ability_controls: dict[str, tuple[QSpinBox, QLabel, QLabel]] = {}
        self._ability_adjustment_labels: dict[str, QLabel] = {}
        self._ability_summary_labels: dict[str, tuple[QLabel, QLabel, QLabel]] = {}
        self._combat_labels: dict[str, QLabel] = {}
        self._classic_ability_labels: dict[str, tuple[QLabel, QLabel, QLabel]] = {}
        self._classic_combat_labels: dict[str, QLabel] = {}
        self._favored_class_controls: dict[int, tuple[QSpinBox, QSpinBox, QSpinBox, QLineEdit, int]] = {}
        self._advancement_controls: dict[
            str, tuple[FormulaNumberEdit, FormulaLineEdit, QLineEdit]
        ] = {}
        self.sequence_tables: dict[str, QTableWidget] = {}
        self._sequence_active = False
        self._sequence_links = 0
        self._selected_imbue_key = ""
        self._selected_spell_summary_source = ""
        self._spell_book_dialog: SpellBookDialog | None = None
        self._martial_book_dialog: MartialBookDialog | None = None
        self._inventory_dialog: InventoryOrganizerDialog | None = None
        self._equipment_figure_dialog = None
        self._level_up_dialog: GuidedLevelUpDialog | None = None
        self._suppress_open_audit_refresh = False
        self._audit_report = None
        self._displayed_hp_bonus = 0
        self._class_capabilities = ClassCapabilities()
        self._batched_calculator: CharacterCalculationService | None = None
        self.custom_tracker_blocks: dict[str, CustomTrackerBlock] = {}
        self._tracker_block_character_id: int | None = None
        application = QApplication.instance()
        self._event_filter_application = application
        if application is not None:
            application.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.overview_section = self._overview_tab()
        self.favored_class_bonus_section = self._favored_class_bonus_section()
        self.advancement_budget_section = self._advancement_budget_section()
        self.ability_score_increase_section = self._ability_score_increase_section()
        self.abilities_section = self._abilities_tab()
        self.custom_trackers_section = self._custom_trackers_section()
        self.ability_summary_section = self._ability_summary_section()
        self.classic_statistics_section = self._classic_statistics_section()
        self.movement_section = self._movement_section()
        self.special_abilities_section = self._special_abilities_section()
        self.proficiencies_section = self._proficiencies_section()
        self.inquisitor_features_section = self._inquisitor_features_section()
        self.combat_section = self._combat_tab()
        self.skills_section = self._skills_tab()
        self.attacks_section = self._attacks_tab()
        self.equipment_section = self._equipment_tab()
        self.feats_section = self._feats_tab()
        self.traits_section = self._traits_tab()
        self.feature_details_section = self._feature_details_section()
        self.conditions_section = self._conditions_tab()
        self.martial_focus_section = self._martial_focus_section()
        self.martial_talents_section = self._martial_talents_section()
        self.moldable_talents_section = self._moldable_talents_section()
        self.prodigy_section = self._prodigy_section()
        self.prodigy_imbue_section = self._prodigy_imbue_section()
        self.spell_level_overview_section = self._spell_level_overview_section()
        self.spells_known_section = self._spells_known_section()
        self.spells_prepared_section = self._spells_prepared_section()
        self.spells_section = self._spells_section()
        self.spell_point_summary_section = self._spell_point_summary_section()
        self.worn_items_section = self._worn_items_section()
        self.traditions_section = self._traditions_section()
        from app.ui.optional_traditions import OptionalTraditionsSection
        self.optional_traditions_section = OptionalTraditionsSection(self)
        self.load_section = self._load_section()
        self.currency_section = self._currency_section()
        self.traditional_casting_section = self._traditional_casting_section()
        self.casting_profile_section = self._casting_profile_section()
        self.casting_play_section = self._casting_play_section()
        self.sphere_build_section = self._sphere_build_section()
        self.sphere_statistics_section = self._sphere_statistics_section()
        self.magic_range_section = self._magic_range_section()
        self.animal_identity_section = self._animal_identity_section()
        self.animal_statistics_section = self._animal_statistics_section()
        self.animal_training_section = self._animal_training_section()
        self._companion_grant = resolve_companion_grant((), {}, (), {})
        self.audit_status_bar = CharacterAuditStatusBar()
        self.audit_status_bar.review_requested.connect(self._review_advancement)

        compose_character_pages(self, layout)
        self._wire_shared_feature_details()

    def eventFilter(self, watched, event) -> bool:
        if forward_editor_wheel_to_page(self, watched, event):
            return True
        return super().eventFilter(watched, event)

    def dispose(self) -> None:
        """Release the application-wide input hook installed by this sheet."""
        if self._equipment_figure_dialog is not None:
            self._equipment_figure_dialog.close()
            self._equipment_figure_dialog = None

        if self._spell_book_dialog is not None:
            self._spell_book_dialog.close()
            self._spell_book_dialog = None
        if self._martial_book_dialog is not None:
            self._martial_book_dialog.close()
            self._martial_book_dialog = None
        if self._inventory_dialog is not None:
            self._inventory_dialog.close()
            self._inventory_dialog = None
        if self._level_up_dialog is not None:
            self._level_up_dialog.close()
            self._level_up_dialog = None
        application = self._event_filter_application
        if application is not None:
            application.removeEventFilter(self)
            self._event_filter_application = None

    def closeEvent(self, event) -> None:
        if self._equipment_figure_dialog is not None:
            self._equipment_figure_dialog.close()
        self.dispose()
        super().closeEvent(event)


    def load_character(self, character_id: int) -> None:
        if self._equipment_figure_dialog is not None:
            self._equipment_figure_dialog.close()
            self._equipment_figure_dialog = None
        if self._spell_book_dialog is not None:
            self._spell_book_dialog.close()
            self._spell_book_dialog = None
        if self._martial_book_dialog is not None:
            self._martial_book_dialog.close()
            self._martial_book_dialog = None
        if self._inventory_dialog is not None:
            self._inventory_dialog.close()
            self._inventory_dialog = None
        if self._level_up_dialog is not None:
            self._level_up_dialog.close()
            self._level_up_dialog = None
        self.character_id = character_id
        self.feature_details.clear()
        self.refresh_all()

    def refresh_all(self) -> None:
        if self.character_id is None:
            return
        synchronize_class_granted_spells(
            self.repository, self.character_id
        )
        updates_were_enabled = self.updatesEnabled()
        if updates_were_enabled:
            self.setUpdatesEnabled(False)
        try:
            self._refresh_identity()
            self._refresh_classes()
            self._refresh_proficiencies()
            self._refresh_inquisitor_features()
            self._refresh_animal_companion()
            self._refresh_bonded_companions()
            self._refresh_favored_class_bonuses()
            self._refresh_ability_score_increases()
            self._refresh_custom_trackers()
            self._refresh_prodigy_sequence()
            self._refresh_special_abilities()
            self._refresh_abilities()
            self._refresh_combat()
            self._refresh_hit_points()
            self._refresh_movement()
            self._refresh_equipment()
            self._refresh_currency()
            self._refresh_attacks()
            self._refresh_skills()
            self._refresh_conditions()
            self._refresh_feats()
            self._refresh_traits()
            self._refresh_martial_focus()
            self._refresh_martial_talents()
            self._refresh_moldable_talents()
            self._refresh_prodigy_sphere_rules()
            self._refresh_sequence_options()
            self._refresh_prodigy_imbues()
            self._refresh_casting_profile()
            self._refresh_spells()
            self._refresh_sphere_build()
            self._refresh_sphere_statistics()
            self._refresh_advancement_budgets()
            self._refresh_character_audit()
            if self.crafting_section.isVisible():
                self.crafting_section.refresh()
        finally:
            if updates_were_enabled:
                self.setUpdatesEnabled(True)
                self.update()

    def _refresh_character_audit(self) -> None:
        if self.character_id is None:
            return
        self._audit_report = build_character_audit(
            self.repository, self.character_id
        )
        self.audit_status_bar.set_report(self._audit_report)
        if (
            not self._suppress_open_audit_refresh
            and self._level_up_dialog is not None
            and self._level_up_dialog.isVisible()
        ):
            self._level_up_dialog.refresh()

    def _refresh_after_audit_resolution(self) -> None:
        """Refresh the sheet once while the audit refreshes its own model once."""

        self._suppress_open_audit_refresh = True
        try:
            self.refresh_all()
        finally:
            self._suppress_open_audit_refresh = False

    def _refresh_audit_status_from_dialog(self) -> None:
        """Update the global badge without recursively rebuilding the dialog."""

        if self.character_id is None:
            return
        self._audit_report = build_character_audit(self.repository, self.character_id)
        self.audit_status_bar.set_report(self._audit_report)

    def _refresh_formula_dependents(self, *, movement: bool = True) -> None:
        """Refresh every presentation that consumes the shared formula namespace.

        Rules-bearing editors call this after saving their state.  This keeps
        formulas reactive without coupling Movement, custom trackers, or
        Building Blocks to individual abilities, resources, feats, or class
        widgets.
        """

        if self.character_id is None or self._loading:
            return
        with self._calculation_batch():
            calculator = self._calculator()
            if movement:
                self._refresh_movement(calculator)
                self._refresh_load()
            # Conditional attacks use the same named-formula namespace as the
            # other reactive sheet fields.  Rebuild only this small presentation
            # table when a dependency changes; the saved attack records remain
            # untouched.
            self._refresh_attacks(calculator)
            self._refresh_custom_trackers(calculator)
        self.formula_values_changed.emit()






    @staticmethod
    def _readable_tooltip(title: str, description: str) -> str:
        return readable_tooltip(title, description)

    @staticmethod
    def _catalog_dialog_entries(dialog) -> tuple[dict, ...]:
        """Read the new batch contract while retaining older single-entry dialogs."""

        entries = tuple(getattr(dialog, "selected_entries", ()) or ())
        selected = getattr(dialog, "selected_entry", None)
        return entries or ((selected,) if selected is not None else ())

    def _add_catalog_batch(
        self,
        entries: tuple[dict, ...],
        add_one: Callable[[dict], bool],
        refresh: Callable[[], None],
        item_label: str,
    ) -> int:
        """Apply several catalog choices, refreshing once and summarizing failures once."""

        added = 0
        failures: list[str] = []
        for entry in entries:
            try:
                if add_one(entry):
                    added += 1
                else:
                    failures.append(
                        f"{entry.get('name', 'Entry')}: required choices were cancelled "
                        "or the entry is no longer available."
                    )
            except ValueError as error:
                failures.append(f"{entry.get('name', 'Entry')}: {error}")
        if added:
            refresh()
        if failures:
            visible = failures[:10]
            if len(failures) > len(visible):
                visible.append(f"…and {len(failures) - len(visible)} more")
            QMessageBox.warning(
                self,
                f"Some {item_label} were not added",
                "\n".join(visible),
            )
        return added

    def _refresh_special_abilities(self) -> None:
        if self.character_id is None:
            return
        abilities: list[tuple[str, int, str, str, str, bool]] = []
        character_details = self.repository.get_character_details(self.character_id)
        abilities.extend(
            (
                f"race:{trait.get('key') or reference_key(str(trait.get('name') or 'trait'))}",
                1,
                str(trait.get("name") or "Racial Trait"),
                str(trait.get("description") or ""),
                f"Race: {character_details.race or 'Custom'}",
                False,
            )
            for trait in resolved_racial_traits(character_details)
        )
        archetypes_by_level = self.repository.list_class_archetype_keys(self.character_id)
        feature_selections = self.repository.list_class_feature_selections(
            self.character_id
        )
        class_choice_slots = resolve_class_choice_slots(
            self.repository, self.character_id
        )
        class_power_sets = resolve_class_power_sets(self.repository, self.character_id)
        for class_level in self.repository.list_class_levels(self.character_id):
            entry = class_entry(class_level.preset_key)
            if entry is None:
                continue
            selected_archetypes = tuple(
                definition
                for key in archetypes_by_level.get(class_level.id, ())
                if (definition := archetype_entry(key)) is not None
            )
            base_features = (
                tuple(
                    {"level": level, "name": name, "description": description}
                    for level, name, description in PRODIGY_SPECIAL_ABILITIES
                )
                if class_level.preset_key == "prodigy"
                or "prodigy" in class_level.class_name.casefold()
                else entry.get("features", ())
            )
            abilities.extend(
                (resolved_feature_key(class_level.id, feature), feature.level,
                 feature.name, feature.description, feature.source, False)
                for feature in resolve_class_features(
                    base_features,
                    selected_archetypes,
                    class_level.level,
                    class_level.class_name,
                    selected_optional_feature_keys=(
                        selection.feature_key
                        for selection in feature_selections
                        if selection.class_level_id == class_level.id
                        and _is_archetype_exchange_selection(selection)
                    ),
                    selected_archetype_choices=archetype_choice_selections_from_records(
                        feature_selections, class_level.id
                    ),
                )
            )
        abilities.extend(
            (*feature, False)
            for feature in projected_class_choice_features(class_choice_slots)
        )
        abilities.extend(
            (f"class-power:{class_level_id}:{power_name.casefold()}:{level}", level,
             power_name, description, source, False)
            for class_level_id, level, power_name, description, source
            in projected_class_power_features(class_power_sets)
        )
        class_choice_record_keys = {
            (slot.class_level_id, key)
            for slot in class_choice_slots
            for key in (slot.feature_key, *slot.legacy_feature_keys)
        }
        class_power_record_keys = {
            (power_set.class_level_id, power_set.feature_key)
            for power_set in class_power_sets
        }
        class_levels = {item.id: item for item in self.repository.list_class_levels(self.character_id)}
        for selection in feature_selections:
            owner = class_levels.get(selection.class_level_id)
            if owner is None:
                continue
            if (
                _is_archetype_exchange_selection(selection)
                or _is_archetype_choice_selection(selection)
                or (selection.class_level_id, selection.feature_key) in class_choice_record_keys
                or (selection.class_level_id, selection.feature_key) in class_power_record_keys
            ):
                # The selected exchange is already projected by
                # resolve_class_features, including its surrendered features.
                continue
            prefix = f"selection:{selection.class_level_id}:{selection.feature_key}"
            abilities.append((prefix, 1, f"{selection.option_type} — {selection.name}",
                              selection.description, owner.class_name, False))
            if selection.option_type == "Inquisition" and selection.description:
                for granted in archetype_granted_features(
                    {"name": f"{selection.name} Inquisition", "description": selection.description},
                    owner.level,
                ):
                    abilities.append((f"{prefix}:{granted.level}:{granted.name.casefold()}",
                                      granted.level, granted.name, granted.description,
                                      f"{selection.name} Inquisition", False))
        adjustments = {
            item.feature_key: item
            for item in self.repository.list_special_ability_adjustments(self.character_id)
        }
        adjusted = []
        for key, level, name, description, source, custom in abilities:
            overlay = adjustments.get(key)
            if overlay is not None:
                if overlay.hidden:
                    continue
                level, name, description = overlay.level, overlay.name, overlay.description
            adjusted.append((key, level, name, description, source, custom))
        adjusted.extend(
            (item.feature_key, item.level, item.name, item.description, "Custom", True)
            for item in adjustments.values() if item.custom and not item.hidden
        )
        adjusted.sort(key=lambda item: (item[1], item[4].casefold(), item[2].casefold()))
        self.special_ability_table.setRowCount(0)
        for feature_key, ability_level, name, description, class_name, custom in adjusted:
            row = self.special_ability_table.rowCount()
            self.special_ability_table.insertRow(row)
            level_cell = QTableWidgetItem(str(ability_level))
            level_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_cell = QTableWidgetItem(name)
            level_cell.setData(Qt.ItemDataRole.UserRole, feature_key)
            level_cell.setData(Qt.ItemDataRole.UserRole + 1, (ability_level, name, description, custom))
            tooltip = self._readable_tooltip(
                name, f"{class_name} — level {ability_level}\n\n{description}"
            )
            level_cell.setToolTip(tooltip)
            name_cell.setToolTip(tooltip)
            self.special_ability_table.setItem(row, 0, level_cell)
            self.special_ability_table.setItem(row, 1, name_cell)
        row_count = max(1, len(adjusted))
        height = (
            self.special_ability_table.horizontalHeader().sizeHint().height()
            + row_count * self.special_ability_table.verticalHeader().defaultSectionSize()
            + 6
        )
        if not bool(self.special_abilities_section.property("freeformManaged")):
            self.special_ability_table.setFixedHeight(height)
        self._set_section_rule_available("special_abilities", True)

    def _selected_special_ability(self):
        row = self.special_ability_table.currentRow()
        if row < 0:
            return None
        cell = self.special_ability_table.item(row, 0)
        return (cell.data(Qt.ItemDataRole.UserRole), cell.data(Qt.ItemDataRole.UserRole + 1))

    def _add_special_ability(self) -> None:
        if self.character_id is None:
            return
        dialog = SpecialAbilityDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values
        key = f"custom:{self.character_id}:{len(self.repository.list_special_ability_adjustments(self.character_id)) + 1}:{values['name'].casefold()}"
        self.repository.save_special_ability_adjustment(SpecialAbilityAdjustment(
            0, self.character_id, key, custom=True, hidden=False, **values
        ))
        self._refresh_special_abilities()

    def _edit_special_ability(self) -> None:
        selected = self._selected_special_ability()
        if selected is None or self.character_id is None:
            return
        key, (level, name, description, custom) = selected
        dialog = SpecialAbilityDialog(self, level=level, name=name, description=description)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.save_special_ability_adjustment(SpecialAbilityAdjustment(
            0, self.character_id, str(key), custom=bool(custom), hidden=False, **dialog.values
        ))
        self._refresh_special_abilities()

    def _reset_special_ability(self) -> None:
        selected = self._selected_special_ability()
        if selected is None or self.character_id is None:
            return
        key, _values = selected
        self.repository.delete_special_ability_adjustment(self.character_id, str(key))
        self._refresh_special_abilities()

    def _resolved_features_by_class(self) -> dict[int, tuple]:
        if self.character_id is None:
            return {}
        archetypes = self.repository.list_class_archetype_keys(self.character_id)
        selections = self.repository.list_class_feature_selections(self.character_id)
        result = {}
        for class_level in self.repository.list_class_levels(self.character_id):
            definition = class_entry(class_level.preset_key)
            if definition is None:
                continue
            selected = tuple(
                item for key in archetypes.get(class_level.id, ())
                if (item := archetype_entry(key)) is not None
            )
            result[class_level.id] = resolve_class_features(
                definition.get("features", ()),
                selected,
                class_level.level,
                class_level.class_name,
                selected_optional_feature_keys=(
                    item.feature_key
                    for item in selections
                    if item.class_level_id == class_level.id
                    and _is_archetype_exchange_selection(item)
                ),
                selected_archetype_choices=archetype_choice_selections_from_records(
                    selections, class_level.id
                ),
            )
        return result

    def _refresh_proficiencies(self) -> None:
        if self.character_id is None:
            return
        archetypes = self.repository.list_class_archetype_keys(self.character_id)
        feature_selections = self.repository.list_class_feature_selections(
            self.character_id
        )
        adjustments = {
            item.class_level_id: item
            for item in self.repository.list_proficiency_adjustments(self.character_id)
        }
        self.proficiencies_table.setRowCount(0)
        for class_level in self.repository.list_class_levels(self.character_id):
            definition = class_entry(class_level.preset_key)
            if definition is None:
                continue
            selected = tuple(item for key in archetypes.get(class_level.id, ()) if (item := archetype_entry(key)))
            weapons, armor = resolved_proficiencies(
                definition,
                selected,
                archetype_choice_selections_from_records(
                    feature_selections, class_level.id
                ),
            )
            automatic_weapons = ", ".join(weapons) or "None"
            automatic_armor = ", ".join(armor) or "None"
            adjustment = adjustments.get(class_level.id)
            displayed_weapons = adjustment.weapons if adjustment else automatic_weapons
            displayed_armor = adjustment.armor if adjustment else automatic_armor
            row = self.proficiencies_table.rowCount(); self.proficiencies_table.insertRow(row)
            for column, value in enumerate((class_level.class_name, displayed_weapons, displayed_armor)):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, class_level.id)
                    cell.setData(Qt.ItemDataRole.UserRole + 1, automatic_weapons)
                    cell.setData(Qt.ItemDataRole.UserRole + 2, automatic_armor)
                if adjustment and adjustment.notes:
                    cell.setToolTip(self._readable_tooltip("Proficiency notes", adjustment.notes))
                self.proficiencies_table.setItem(row, column, cell)
        fit_table_rows(self.proficiencies_table, self.proficiencies_table.rowCount(), 1, 6)

    def _selected_proficiency_context(self):
        if self.character_id is None or self.proficiencies_table.currentRow() < 0:
            return None
        row = self.proficiencies_table.currentRow()
        class_cell = self.proficiencies_table.item(row, 0)
        if class_cell is None:
            return None
        return (
            int(class_cell.data(Qt.ItemDataRole.UserRole)),
            str(class_cell.data(Qt.ItemDataRole.UserRole + 1) or ""),
            str(class_cell.data(Qt.ItemDataRole.UserRole + 2) or ""),
        )

    def _edit_selected_proficiencies(self) -> None:
        context = self._selected_proficiency_context()
        if context is None or self.character_id is None:
            return
        class_level_id, automatic_weapons, automatic_armor = context
        current = next(
            (item for item in self.repository.list_proficiency_adjustments(self.character_id)
             if item.class_level_id == class_level_id),
            None,
        )
        dialog = ProficiencyDialog(
            self,
            automatic_weapons=automatic_weapons,
            automatic_armor=automatic_armor,
            weapons=current.weapons if current else automatic_weapons,
            armor=current.armor if current else automatic_armor,
            notes=current.notes if current else "",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.save_proficiency_adjustment(
            ProficiencyAdjustment(self.character_id, class_level_id, **dialog.values)
        )
        self._refresh_proficiencies()

    def _reset_selected_proficiencies(self) -> None:
        context = self._selected_proficiency_context()
        if context is None or self.character_id is None:
            return
        self.repository.delete_proficiency_adjustment(self.character_id, context[0])
        self._refresh_proficiencies()

    def _refresh_inquisitor_features(self) -> None:
        if self.character_id is None:
            return
        ability_modifiers = {
            key: value.ability_modifier
            for key, value in self._ability_results().items()
        }
        self._class_feature_modules = resolve_class_feature_modules(
            self.repository, self.character_id, ability_modifiers
        )
        visible_resources = {
            (module.class_level_id, resource.key)
            for module in self._class_feature_modules
            for resource in module.resources
        }
        inquisitor_ids = {
            module.class_level_id for module in self._class_feature_modules
        }
        for state in self.repository.list_class_feature_states(self.character_id):
            if (
                state.active
                and state.class_level_id in inquisitor_ids
                and (state.class_level_id, state.feature_key) not in visible_resources
            ):
                self.repository.save_class_feature_state(replace(state, active=False))
        self.inquisitor_resource_table.setRowCount(0)
        summaries: list[str] = []
        feats = self.repository.list_feats(self.character_id)
        teamwork_owned = sum(
            "teamwork" in " ".join(
                (feat.catalog_category, feat.prerequisites, feat.notes)
            ).casefold()
            for feat in feats
        )
        for module in self._class_feature_modules:
            passive = []
            if "stern-gaze" in module.feature_tokens:
                passive.append("Stern Gaze automated")
            if "cunning-initiative" in module.feature_tokens:
                passive.append(
                    f"Cunning Initiative uses {module.governing_ability.title()}"
                )
            if module.solo_tactics:
                passive.append("Solo Tactics available")
            if module.teamwork_feat_slots:
                passive.append(
                    f"teamwork feats {teamwork_owned}/{module.teamwork_feat_slots}"
                )
            summaries.append(f"{module.class_name} {module.class_level}: " + ", ".join(passive or ["tracked features only"]))
            for resource in module.resources:
                row = self.inquisitor_resource_table.rowCount()
                self.inquisitor_resource_table.insertRow(row)
                effect = class_feature_effect_summary(resource, module)
                values = (
                    resource.name,
                    str(resource.current) if resource.tracks_uses else "—",
                    str(resource.maximum) if resource.tracks_uses else "—",
                    "ACTIVE" if resource.active else "Ready",
                    effect,
                )
                tooltip = self._readable_tooltip(
                    resource.name,
                    f"{module.class_name} {module.class_level}\n\n{resource.description}"
                    + (f"\n\nNotes: {resource.state.notes}" if resource.state.notes else ""),
                )
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setData(
                        Qt.ItemDataRole.UserRole,
                        (module.class_level_id, resource.key),
                    )
                    cell.setToolTip(tooltip)
                    if resource.active:
                        cell.setBackground(QColor("#DAE9F8"))
                    self.inquisitor_resource_table.setItem(row, column, cell)
        self.inquisitor_resource_summary.setText("\n".join(summaries) or "No active class resource trackers.")
        self.inquisitor_teamwork_button.setVisible(
            any(module.teamwork_feat_slots for module in self._class_feature_modules)
        )
        fit_table_rows(
            self.inquisitor_resource_table,
            self.inquisitor_resource_table.rowCount(),
            1,
            8,
        )

        self._class_choice_slots = resolve_class_choice_slots(
            self.repository, self.character_id
        )
        self.inquisitor_choice_table.setRowCount(0)
        for slot in self._class_choice_slots:
            row=self.inquisitor_choice_table.rowCount(); self.inquisitor_choice_table.insertRow(row)
            selection_text = (
                ", ".join(option.name for option in slot.selected_options)
                if slot.selected_options
                else f"Required: choose {slot.minimum}" + (
                    f"–{slot.maximum}" if slot.maximum != slot.minimum else ""
                )
            )
            values=(slot.class_name, slot.label, selection_text)
            details = slot.description
            if slot.selected_options:
                details += "\n\n" + "\n\n".join(
                    f"{option.name}\n{option.description}"
                    for option in slot.selected_options
                )
            for col,value in enumerate(values):
                cell=QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole,(slot.class_level_id, slot.key))
                cell.setToolTip(self._readable_tooltip(slot.label, details))
                self.inquisitor_choice_table.setItem(row,col,cell)
        available = self.inquisitor_choice_table.rowCount() > 0
        for widget in (
            self.inquisitor_domain_title,
            self.inquisitor_choice_table,
            self.inquisitor_domain_actions,
        ):
            widget.setVisible(available)
        self._set_section_rule_available(
            "inquisitor_features", bool(self._class_feature_modules or self._class_choice_slots)
        )
        fit_table_rows(self.inquisitor_choice_table, self.inquisitor_choice_table.rowCount(), 1, 4)

        self._class_power_sets = resolve_class_power_sets(self.repository, self.character_id)
        self.class_power_table.setRowCount(0)
        for power_set in self._class_power_sets:
            row = self.class_power_table.rowCount(); self.class_power_table.insertRow(row)
            active_keys = set(power_set.active_keys)
            selected = ", ".join(
                option.name + (" (active)" if option.key in active_keys else "")
                for option in power_set.selected_options
            ) or "No powers selected"
            values = (power_set.class_name, power_set.label, selected, str(power_set.maximum))
            details = power_set.description
            if power_set.selected_options:
                details += "\n\n" + "\n\n".join(
                    f"Level {level}: {option.name}\n{option.description}"
                    for level, option in zip(power_set.slot_levels, power_set.selected_options)
                )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, (power_set.class_level_id, power_set.key))
                cell.setToolTip(self._readable_tooltip(power_set.label, details))
                self.class_power_table.setItem(row, column, cell)
        powers_available = bool(self._class_power_sets)
        for widget in (self.class_power_title, self.class_power_table, self.class_power_actions):
            widget.setVisible(powers_available)
        self._set_section_rule_available(
            "inquisitor_features",
            bool(self._class_feature_modules or self._class_choice_slots or self._class_power_sets),
        )
        fit_table_rows(self.class_power_table, self.class_power_table.rowCount(), 1, 4)

    def _selected_class_power_set(self):
        row = self.class_power_table.currentRow()
        cell = self.class_power_table.item(row, 0) if row >= 0 else None
        identity = cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None
        if not identity:
            return None
        class_level_id, provider_key = identity
        return next(
            (item for item in getattr(self, "_class_power_sets", ())
             if item.class_level_id == class_level_id and item.key == provider_key),
            None,
        )

    def _choose_class_powers(self, *_args) -> None:
        if self.character_id is None:
            return
        power_set = self._selected_class_power_set()
        if power_set is None:
            return
        dialog = ClassPowerDialog(power_set, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            apply_class_power_selection(
                self.repository, self.character_id, power_set, dialog.selected_keys
            )
        except ValueError as error:
            QMessageBox.warning(self, f"Cannot change {power_set.label}", str(error))
            return
        updated = next(
            (
                item for item in resolve_class_power_sets(self.repository, self.character_id)
                if item.class_level_id == power_set.class_level_id and item.key == power_set.key
            ),
            None,
        )
        if updated is not None:
            desired_active = set(dialog.active_keys)
            for option_key in set(power_set.active_keys) | desired_active:
                self.repository.save_class_feature_state(
                    class_power_activation_record(
                        self.character_id, updated, option_key, option_key in desired_active
                    )
                )
        self._class_power_changed()

    def _clear_class_powers(self) -> None:
        if self.character_id is None:
            return
        power_set = self._selected_class_power_set()
        if power_set is None:
            return
        for option_key in power_set.active_keys:
            self.repository.save_class_feature_state(
                class_power_activation_record(self.character_id, power_set, option_key, False)
            )
        self.repository.delete_class_feature_selection(
            self.character_id, power_set.class_level_id, power_set.feature_key
        )
        self._class_power_changed()

    def _class_power_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_inquisitor_features,
            self._refresh_special_abilities,
            self._refresh_combat,
            self._refresh_formula_dependents,
        )

    def _selected_class_feature_resource(self):
        row = self.inquisitor_resource_table.currentRow()
        if row < 0:
            return None
        cell = self.inquisitor_resource_table.item(row, 0)
        if cell is None:
            return None
        identity = cell.data(Qt.ItemDataRole.UserRole)
        if not identity:
            return None
        class_level_id, feature_key = identity
        for module in getattr(self, "_class_feature_modules", ()):
            if module.class_level_id != class_level_id:
                continue
            for resource in module.resources:
                if resource.key == feature_key:
                    return module, resource
        return None

    def _class_feature_system_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_inquisitor_features,
            self._refresh_martial_focus,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_casting_profile,
            self._refresh_formula_dependents,
        )

    def _configure_class_feature_resource(self, *_args) -> None:
        selected = self._selected_class_feature_resource()
        if selected is None or self.character_id is None:
            return
        _module, resource = selected
        dialog = ClassFeatureStateDialog(resource, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.save_class_feature_state(
            replace(resource.state, **dialog.values)
        )
        self._class_feature_system_changed()

    def _use_class_feature_resource(self) -> None:
        selected = self._selected_class_feature_resource()
        if selected is None:
            return
        module, resource = selected
        linked = next(
            (
                item for item in module.resources
                if item.key == resource.spend_resource_key
            ),
            None,
        )
        external_current = self._external_class_resource_current(
            resource.external_cost_key
        )
        if (
            resource.external_cost_key
            and external_current < resource.use_cost
        ):
            return
        if linked is not None and linked.current < resource.use_cost:
            return
        if resource.use_increases and resource.current >= resource.maximum:
            return
        if (
            resource.tracks_uses
            and not resource.use_increases
            and linked is None
            and resource.current < resource.use_cost
        ):
            return
        if resource.use_requires_active and not resource.active:
            return
        if (resource.choice_options or resource.custom_choice_label) and not resource.choices:
            self._configure_class_feature_resource()
            return
        if resource.external_cost_key:
            self._spend_external_class_resource(
                resource.external_cost_key, resource.use_cost
            )
        if not resource.tracks_uses:
            self._class_feature_system_changed()
            return
        active = resource.active
        if resource.activate_on_spend:
            active = True
        remaining = (
            resource.current + resource.use_cost
            if resource.use_increases
            else resource.current - resource.use_cost
        )
        if not resource.use_increases and remaining <= 0:
            active = False
        if linked is not None:
            self.repository.save_class_feature_state(
                replace(
                    linked.state,
                    current_value=linked.current - resource.use_cost,
                )
            )
        else:
            self.repository.save_class_feature_state(
                replace(
                    resource.state,
                    current_value=remaining,
                    active=active,
                )
            )
        if not active:
            self._set_linked_class_resources(
                module, resource.deactivate_resources_on_end, active=False
            )
        self._set_linked_class_resources(
            module, resource.deactivate_resources_on_use, active=False
        )
        self._class_feature_system_changed()

    def _toggle_class_feature_resource(self) -> None:
        selected = self._selected_class_feature_resource()
        if selected is None:
            return
        module, resource = selected
        if not resource.can_activate:
            return
        if not resource.active and (
            resource.choice_options or resource.custom_choice_label
        ) and not resource.choices:
            self._configure_class_feature_resource()
            return
        if not resource.active and resource.activation_requires:
            required = next(
                (
                    item for item in module.resources
                    if item.key == resource.activation_requires
                ),
                None,
            )
            if required is None or not required.active:
                return
        becoming_active = not resource.active
        current = (
            resource.maximum
            if becoming_active and resource.restore_on_activate
            else resource.current
        )
        self.repository.save_class_feature_state(
            replace(resource.state, current_value=current, active=becoming_active)
        )
        if becoming_active:
            self._set_linked_class_resources(
                module,
                resource.restore_resources_on_activate,
                active=False,
                restore=True,
            )
        else:
            self._set_linked_class_resources(
                module, resource.deactivate_resources_on_end, active=False
            )
        self._class_feature_system_changed()

    def _set_linked_class_resources(
        self,
        module,
        keys: tuple[str, ...],
        *,
        active: bool,
        restore: bool = False,
    ) -> None:
        """Apply declarative transitions between resources in one class module."""

        wanted = set(keys)
        for linked in module.resources:
            if linked.key not in wanted:
                continue
            self.repository.save_class_feature_state(
                replace(
                    linked.state,
                    current_value=linked.maximum if restore else linked.current,
                    active=active,
                )
            )

    def _restore_class_feature_resource(self) -> None:
        selected = self._selected_class_feature_resource()
        if selected is None:
            return
        module, resource = selected
        if not resource.tracks_uses:
            return
        linked = next(
            (
                item for item in module.resources
                if item.key == resource.spend_resource_key
            ),
            None,
        )
        if linked is not None:
            self.repository.save_class_feature_state(
                replace(
                    linked.state,
                    current_value=min(
                        linked.maximum, linked.current + resource.use_cost
                    ),
                )
            )
        else:
            value = (
                max(0, resource.current - resource.use_cost)
                if resource.restore_toward_zero
                else min(resource.maximum, resource.current + resource.use_cost)
            )
            self.repository.save_class_feature_state(
                replace(resource.state, current_value=value)
            )
        self._class_feature_system_changed()

    def _external_class_resource_current(self, key: str) -> int:
        """Read a non-class-module pool used to pay a declarative feature cost."""

        if self.character_id is None or not key:
            return 0
        if key == "martial_focus":
            return self.repository.get_martial_focus(self.character_id).current
        return 0

    def _spend_external_class_resource(self, key: str, amount: int) -> bool:
        if self.character_id is None or amount <= 0:
            return False
        if key == "martial_focus":
            focus = self.repository.get_martial_focus(self.character_id)
            if focus.current < amount:
                return False
            self.repository.update_martial_focus(
                replace(focus, current=focus.current - amount)
            )
            return True
        return False

    def _browse_inquisitor_teamwork_feats(self) -> None:
        if self.character_id is None:
            return
        granted_prefix = "Class Granted · Inquisitor Teamwork"
        maximum = sum(
            module.teamwork_feat_slots
            for module in getattr(self, "_class_feature_modules", ())
        )
        existing = sum(
            str(feat.catalog_category).startswith(granted_prefix)
            for feat in self.repository.list_feats(self.character_id)
        )
        remaining = max(0, maximum - existing)
        if remaining <= 0:
            return
        dialog = FeatCatalogDialog(
            self.repository.list_feats(self.character_id),
            self,
            selection_limit=remaining,
        )
        for row in range(dialog.category_list.count()):
            if dialog.category_list.item(row).data(Qt.ItemDataRole.UserRole) == "Teamwork":
                dialog.category_list.setCurrentRow(row)
                break
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self._add_custom_feat()
            return
        self._add_catalog_batch(
            self._catalog_dialog_entries(dialog),
            lambda entry: self._add_catalog_feat(
                entry, catalog_category_override=granted_prefix
            ),
            self._feats_changed,
            "teamwork feats",
        )

    def _selected_class_choice_slot(self):
        row = self.inquisitor_choice_table.currentRow()
        if row < 0:
            return None
        cell = self.inquisitor_choice_table.item(row, 0)
        identity = cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None
        if not identity:
            return None
        class_level_id, provider_key = identity
        return next(
            (
                slot for slot in getattr(self, "_class_choice_slots", ())
                if slot.class_level_id == class_level_id and slot.key == provider_key
            ),
            None,
        )

    def _class_feature_choice_changed(self) -> None:
        if self.character_id is not None:
            synchronize_class_granted_spells(
                self.repository, self.character_id
            )
        self._refresh_inquisitor_features()
        self._refresh_special_abilities()
        self._refresh_spells()
        self._refresh_animal_companion()
        self._refresh_formula_dependents()

    def _choose_class_feature_choice(self) -> None:
        if self.character_id is None or self.inquisitor_choice_table.currentRow() < 0:
            return
        slot = self._selected_class_choice_slot()
        if slot is None:
            return
        dialog = ClassChoiceDialog(slot, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                self.character_id, slot, dialog.selected_keys
            )
        )
        for legacy_key in slot.legacy_feature_keys:
            self.repository.delete_class_feature_selection(
                self.character_id, slot.class_level_id, legacy_key
            )
        self._class_feature_choice_changed()

    def _clear_class_feature_choice(self) -> None:
        if self.character_id is None:
            return
        slot = self._selected_class_choice_slot()
        if slot is None:
            return
        self.repository.delete_class_feature_selection(
            self.character_id, slot.class_level_id, slot.feature_key
        )
        for legacy_key in slot.legacy_feature_keys:
            self.repository.delete_class_feature_selection(
                self.character_id, slot.class_level_id, legacy_key
            )
        self._class_feature_choice_changed()

    @staticmethod
    def _json_object(text: str) -> dict:
        try:
            value = json.loads(text)
            return dict(value) if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _json_list(text: str) -> list[str]:
        try:
            value = json.loads(text)
            return [str(item) for item in value] if isinstance(value, list) else []
        except (TypeError, ValueError):
            return []

    def _refresh_animal_companion(self) -> None:
        if self.character_id is None:
            return
        classes = self._calculator().resolved_classes()
        features = self._resolved_features_by_class()
        grant = resolve_companion_grant(
            classes, features,
            self.repository.list_martial_talents(self.character_id),
            self.repository.list_skill_states(self.character_id),
            self.repository.list_class_feature_selections(self.character_id),
        )
        self._companion_grant = grant
        record = self.repository.get_animal_companion(self.character_id)
        self._loading = True
        try:
            if self.companion_species.count() <= 1:
                self.companion_species.clear(); self.companion_species.addItem("Custom animal", "")
                for entry in companion_catalog():
                    self.companion_species.addItem(str(entry.get("name")), str(entry.get("key")))
            self.companion_name.setText(record.name)
            details = self._json_object(record.details_json)
            self.companion_sex.setText(str(details.get("sex") or ""))
            self.companion_type.setText(str(details.get("creature_type") or "Animal"))
            self.companion_description.setText(str(details.get("description") or ""))
            index = self.companion_species.findData(record.species_key)
            self.companion_species.setCurrentIndex(max(0, index))
            if index < 0 or not record.species_key:
                self.companion_species.setEditText(
                    str(details.get("custom_species_name") or "Custom animal")
                )
            self.companion_level_adjustment.setValue(record.effective_level_adjustment)
            self.companion_level_override.setText("" if record.effective_level_override is None else str(record.effective_level_override))
            self.companion_hp.setValue(record.current_hp); self.companion_temp_hp.setValue(record.temporary_hp)
            self.companion_notes.setPlainText(record.notes)
        finally:
            self._loading = False
        effective = record.effective_level_override
        if effective is None:
            effective = max(1, grant.effective_level + record.effective_level_adjustment)
        progression = companion_progression(effective)
        entry = companion_entry(record.species_key)
        abilities = self._json_object(record.ability_overrides_json)
        ability_increases = details.get("ability_increases", {})
        if not isinstance(ability_increases, dict):
            ability_increases = {}
        skills = self._json_object(record.skill_ranks_json)
        feats = self._json_list(record.feats_json)
        statistics = calculate_companion_statistics(
            entry, progression, ability_overrides=abilities,
            ability_increases=ability_increases, skill_ranks=skills,
            details=details, feats=feats,
        )
        self._companion_statistics = statistics
        identity = {
            "level": statistics.progression.level,
            "size": statistics.size,
            "size_modifier": f"{statistics.size_modifier:+d}",
            "hit_die": statistics.hit_die,
            "natural_armor": f"{statistics.natural_armor:+d}",
            "spell_resistance": statistics.spell_resistance,
            "damage_reduction": statistics.damage_reduction,
        }
        self.companion_species_rules.setText(
            (f"Species qualities: {statistics.special_qualities or '—'}\n"
             f"Published rules: {entry.get('starting_text','')}"
             if entry else "Choose a published animal; custom values can be layered over the automatic record.")
        )
        self._loading = True
        try:
            for key, value in identity.items():
                control = self.companion_identity_values[key]
                if isinstance(control, QSpinBox):
                    control.setValue(statistics.natural_armor)
                elif isinstance(control, QLineEdit):
                    control.setText("" if str(value) == "—" else str(value))
                else:
                    control.setText(str(value))
            for key, control in self.companion_speed_labels.items():
                control.setValue(int(statistics.speeds.get(key, 0)))
                if key == "fly":
                    control.setToolTip(
                        "Edit the current total fly speed. "
                        + (
                            f"Current maneuverability: {statistics.fly_maneuverability}. "
                            if statistics.fly_maneuverability else ""
                        )
                        + "Reset adjustments returns to the species rules."
                    )
            self.companion_max_hp.setValue(statistics.maximum_hp)

            for row, (key, label) in enumerate((("str","STR"),("dex","DEX"),("con","CON"),("int","INT"),("wis","WIS"),("cha","CHA"))):
                automatic = QTableWidgetItem(str(statistics.automatic_ability_scores[key]))
                automatic.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                automatic.setFlags(automatic.flags() & ~Qt.ItemFlag.ItemIsEditable)
                current = QTableWidgetItem(
                    f"{statistics.ability_scores[key]} "
                    f"({statistics.ability_modifiers[key]:+d})"
                )
                current.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                current.setFlags(current.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.companion_ability_table.setItem(row, 1, automatic)
                self.companion_ability_table.setItem(row, 4, current)
                self.companion_asi_fields[key].setEnabled(
                    statistics.ability_increases > 0
                )
                try:
                    saved_points = max(0, int(ability_increases.get(key, 0) or 0))
                except (TypeError, ValueError):
                    saved_points = 0
                self.companion_asi_fields[key].setValue(saved_points)
                self.companion_ability_override_fields[key].setValue(
                    int(abilities[key]) if key in abilities else -1
                )

            saved_asi_total = 0
            for ability_key in ("str", "dex", "con", "int", "wis", "cha"):
                try:
                    saved_asi_total += max(
                        0, int(ability_increases.get(ability_key, 0) or 0)
                    )
                except (TypeError, ValueError):
                    continue
            applied_asi_total = sum(statistics.ability_increase_allocations.values())
            if statistics.ability_increases:
                self.companion_asi_status.setText(
                    f"Level ability increases: {applied_asi_total} / "
                    f"{statistics.ability_increases} assigned"
                    + (
                        f" · {saved_asi_total - applied_asi_total} saved point(s) "
                        "inactive at this effective level"
                        if saved_asi_total > applied_asi_total else ""
                    )
                )
            else:
                self.companion_asi_status.setText(
                    "First companion ability increase becomes available at effective level 4"
                )

            defense_values = {
                "fortitude": statistics.saves["fortitude"],
                "reflex": statistics.saves["reflex"],
                "will": statistics.saves["will"],
                "armor_class": statistics.armor_class,
                "flat_footed_ac": statistics.flat_footed_ac,
                "touch_ac": statistics.touch_ac,
            }
            for key, field in self.companion_defense_total_fields.items():
                field.setValue(int(defense_values[key]))
            combat_values = {
                "base_attack_bonus": statistics.base_attack_bonus,
                "cmb": statistics.cmb,
                "cmd": statistics.cmd,
            }
            for key, field in self.companion_combat_total_fields.items():
                field.setValue(int(combat_values[key]))
        finally:
            self._loading = False
        fit_table_rows(self.companion_ability_table, 6, 6, 6)
        fit_table_rows(self.companion_defense_table, 3, 3, 3)
        fit_table_rows(self.companion_combat_table, 3, 3, 3)

        self.companion_attack_table.setRowCount(0)
        for attack in statistics.attacks:
            row=self.companion_attack_table.rowCount(); self.companion_attack_table.insertRow(row)
            for column,value in enumerate((attack.name,f"{attack.attack_bonus:+d}",attack.damage,attack.notes)):
                cell=QTableWidgetItem(str(value)); cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 1: cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.companion_attack_table.setItem(row,column,cell)
        fit_table_rows(self.companion_attack_table, len(statistics.attacks), 2, 5)

        automatic_specials = list(progression.special)
        self._loading = True
        try:
            self.companion_skill_table.setRowCount(0)
            self.companion_skill_rank_fields = {}
            for skill in statistics.skills:
                row=self.companion_skill_table.rowCount(); self.companion_skill_table.insertRow(row)
                for column,value in enumerate((f"{skill.total:+d}",skill.name,skill.ability)):
                    cell=QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole,skill.key)
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column in {0,2}: cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.companion_skill_table.setItem(row,column,cell)
                ranks = numeric_field(0, progression.hit_dice, width=56)
                ranks.setValue(skill.ranks)
                ranks.setToolTip(
                    f"Maximum {progression.hit_dice} ranks in one skill; "
                    f"{progression.skill_ranks} total ranks available."
                )
                ranks.editingFinished.connect(
                    lambda skill_key=skill.key, control=ranks: self._save_companion_skill_rank(
                        skill_key, control.value()
                    )
                )
                self.companion_skill_rank_fields[skill.key] = ranks
                self.companion_skill_table.setCellWidget(row, 3, ranks)
        finally:
            self._loading = False
        assigned_ranks = sum(skill.ranks for skill in statistics.skills)
        self.companion_skill_status.setText(
            f"{assigned_ranks} / {progression.skill_ranks} skill ranks assigned"
        )
        self.companion_skill_table.setToolTip(f"Assigned {assigned_ranks} of {progression.skill_ranks} available ranks")
        fit_table_rows(self.companion_skill_table, len(statistics.skills), 9, 9)
        self._populate_companion_training("Feats", feats, progression.feats)
        self._populate_companion_training("Tricks", self._json_list(record.tricks_json), progression.bonus_tricks)
        self._populate_companion_training("Special abilities", automatic_specials + self._json_list(record.special_abilities_json), None, len(automatic_specials))
        self.companion_source.setText(
            f"Effective druid level {effective} · {progression.hit_dice}d8 Hit Dice · "
            f"{progression.skill_ranks} skill ranks · {progression.feats} feats · "
            f"{progression.bonus_tricks} bonus tricks · {applied_asi_total} / "
            f"{statistics.ability_increases} ability increases assigned · "
            + ("; ".join(grant.sources) if grant.sources else "Manual companion record")
        )
        self._set_section_rule_available("animal_identity", grant.available)
        self._set_section_rule_available("animal_statistics", grant.available)
        self._set_section_rule_available("animal_training", grant.available)
        if hasattr(self, "page_tabs"):
            index=self.page_tabs.indexOf(self.companion_scroll)
            if index >= 0: self.page_tabs.setTabVisible(index, grant.available)

    def _refresh_bonded_companions(self) -> None:
        if self.character_id is None or not hasattr(self, "page_tabs"):
            return
        grants = bonded_companion_grants(self.repository, self.character_id)
        classes = self._calculator().resolved_classes()
        familiar_master_statistics = {
            "maximum_hp": self._calculator().hit_point_maximum(),
            "bab": total_bab(classes),
            "character_level": sum(row.level for row in classes),
            "base_saves": {
                key: total_base_save(classes, key)
                for key in ("fortitude", "reflex", "will")
            },
        }
        for key, panel, scroll in (
            ("familiar", self.familiar_panel, self.familiar_scroll),
            ("corpse_puppet", self.corpse_puppet_panel, self.corpse_puppet_scroll),
            ("phantom", self.phantom_panel, self.phantom_scroll),
        ):
            grant = grants.get(key)
            level = int(grant.level if grant is not None else 0)
            index = self.page_tabs.indexOf(scroll)
            if level > 0:
                if key == "familiar":
                    record = self.repository.get_bonded_companion(
                        self.character_id, "familiar"
                    )
                    reconciled = reconcile_familiar_hit_points(
                        record,
                        int(familiar_master_statistics["maximum_hp"]) // 2,
                    )
                    if reconciled != record:
                        self.repository.update_bonded_companion(reconciled)
                if index < 0:
                    title = {
                        "familiar": "PET / FAMILIAR",
                        "corpse_puppet": "CORPSE PUPPET",
                        "phantom": "PHANTOM",
                    }[key]
                    index = self.page_tabs.addTab(
                        scroll, f"{self.page_tabs.count()}   {title}"
                    )
                self.page_tabs.setTabVisible(index, True)
                panel.refresh(
                    self.character_id,
                    level,
                    variant=grant.variant,
                    sources=grant.sources,
                    can_stack_pet=grant.can_stack_pet,
                    stacks_pet=grant.stacks_pet,
                    master_statistics=(
                        familiar_master_statistics if key == "familiar" else None
                    ),
                )
            elif index >= 0:
                self.page_tabs.removeTab(index)

    def _populate_companion_training(self, kind: str, values: list[str], allowance: int | None, automatic=0) -> None:
        table = self.companion_training_tabs[kind]; table.setRowCount(0)
        visible_rows = max(1, len(values), int(allowance or 0))
        for index in range(visible_rows):
            value = values[index] if index < len(values) else ""
            row=table.rowCount(); table.insertRow(row); cell=QTableWidgetItem(value)
            cell.setData(Qt.ItemDataRole.UserRole, index >= automatic)
            if index < automatic: cell.setToolTip("Granted automatically by companion progression")
            if not value and allowance is not None: cell.setToolTip("Available choice slot")
            if kind == "Feats" and value:
                entry = next(
                    (
                        candidate for candidate in feat_entries()
                        if str(candidate.get("name", "")).casefold() == value.casefold()
                    ),
                    None,
                )
                if entry is not None:
                    cell.setToolTip(
                        self._readable_tooltip(value, str(entry.get("description", "")))
                    )
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row,0,cell)
        if allowance is not None:
            table.setToolTip(f"Selected {len(values)} of {allowance} available")
            table.horizontalHeaderItem(0).setText(f"{kind} — {len(values)} / {allowance}")
        fit_table_rows(table, visible_rows, visible_rows, max(visible_rows, 8))

    def _save_animal_companion(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        old=self.repository.get_animal_companion(self.character_id)
        override_text=self.companion_level_override.text().strip()
        try: override=max(1,int(override_text)) if override_text else None
        except ValueError: return
        details = self._json_object(old.details_json)
        details.update({
            "sex": self.companion_sex.text().strip(),
            "creature_type": self.companion_type.text().strip() or "Animal",
            "description": self.companion_description.text().strip(),
        })
        species_key = str(self.companion_species.currentData() or "")
        if species_key:
            details.pop("custom_species_name", None)
        else:
            custom_species = self.companion_species.currentText().strip()
            if custom_species and custom_species != "Custom animal":
                details["custom_species_name"] = custom_species
            else:
                details.pop("custom_species_name", None)
        self.repository.update_animal_companion(replace(
            old, name=self.companion_name.text(), species_key=species_key,
            effective_level_adjustment=self.companion_level_adjustment.value(),
            effective_level_override=override,current_hp=self.companion_hp.value(),
            temporary_hp=self.companion_temp_hp.value(),details_json=json.dumps(details),
            notes=self.companion_notes.toPlainText(),
        ))
        self._refresh_animal_companion()

    def _save_companion_ability_increase(self, key: str, value: int) -> None:
        """Persist one published companion ASI without replacing the base score."""

        if self._loading or self.character_id is None:
            return
        statistics = getattr(self, "_companion_statistics", None)
        if statistics is None or statistics.ability_increases <= 0:
            self._refresh_animal_companion()
            return
        record = self.repository.get_animal_companion(self.character_id)
        details = self._json_object(record.details_json)
        allocations = details.get("ability_increases", {})
        allocations = dict(allocations) if isinstance(allocations, dict) else {}
        if value:
            allocations[key] = int(value)
        else:
            allocations.pop(key, None)
        clean_allocations: dict[str, int] = {}
        for ability in ("str", "dex", "con", "int", "wis", "cha"):
            try:
                points = max(0, int(allocations.get(ability, 0) or 0))
            except (TypeError, ValueError):
                points = 0
            if points:
                clean_allocations[ability] = points
        assigned = sum(clean_allocations.values())
        if assigned > statistics.ability_increases:
            self.companion_asi_status.setText(
                f"Only {statistics.ability_increases} level ability increase(s) "
                "are available at this effective level."
            )
            self._refresh_animal_companion()
            return
        details["ability_increases"] = clean_allocations
        self.repository.update_animal_companion(
            replace(record, details_json=json.dumps(details))
        )
        self._refresh_animal_companion()

    def _save_companion_ability_override(self, key: str, value: int) -> None:
        if self._loading or self.character_id is None:
            return
        record = self.repository.get_animal_companion(self.character_id)
        values = self._json_object(record.ability_overrides_json)
        if value < 0:
            values.pop(key, None)
        else:
            values[key] = int(value)
        self.repository.update_animal_companion(
            replace(record, ability_overrides_json=json.dumps(values))
        )
        self._refresh_animal_companion()

    def _reset_companion_ability_increases(self) -> None:
        if self.character_id is None:
            return
        record = self.repository.get_animal_companion(self.character_id)
        details = self._json_object(record.details_json)
        details.pop("ability_increases", None)
        self.repository.update_animal_companion(
            replace(record, details_json=json.dumps(details))
        )
        self._refresh_animal_companion()

    def _save_companion_skill_rank(self, key: str, value: int) -> None:
        if self._loading or self.character_id is None:
            return
        statistics = getattr(self, "_companion_statistics", None)
        if statistics is None:
            return
        record = self.repository.get_animal_companion(self.character_id)
        values = self._json_object(record.skill_ranks_json)
        values[key] = max(0, int(value))
        assigned = 0
        for stored in values.values():
            try:
                assigned += max(0, int(stored or 0))
            except (TypeError, ValueError):
                continue
        if assigned > statistics.progression.skill_ranks:
            self.companion_skill_status.setText(
                f"Only {statistics.progression.skill_ranks} total skill ranks "
                "are available."
            )
            self._refresh_animal_companion()
            return
        if not value:
            values.pop(key, None)
        self.repository.update_animal_companion(
            replace(record, skill_ranks_json=json.dumps(values))
        )
        self._refresh_animal_companion()

    def _save_companion_stat_total(self, key: str, value: int) -> None:
        """Turn an edited displayed total into a persistent additive adjustment."""

        if self._loading or self.character_id is None:
            return
        statistics = getattr(self, "_companion_statistics", None)
        if statistics is None:
            return
        current_values = {
            "natural_armor": statistics.natural_armor,
            "maximum_hp": statistics.maximum_hp,
            "fortitude": statistics.saves["fortitude"],
            "reflex": statistics.saves["reflex"],
            "will": statistics.saves["will"],
            "armor_class": statistics.armor_class,
            "flat_footed_ac": statistics.flat_footed_ac,
            "touch_ac": statistics.touch_ac,
            "base_attack_bonus": statistics.base_attack_bonus,
            "cmb": statistics.cmb,
            "cmd": statistics.cmd,
        }
        detail_keys = {
            "natural_armor": "natural_armor_misc",
            "maximum_hp": "hp_misc",
            "fortitude": "fortitude_misc",
            "reflex": "reflex_misc",
            "will": "will_misc",
            "armor_class": "ac_misc",
            "flat_footed_ac": "flat_footed_ac_misc",
            "touch_ac": "touch_ac_misc",
            "base_attack_bonus": "bab_misc",
            "cmb": "cmb_misc",
            "cmd": "cmd_misc",
        }
        if key not in current_values or int(value) == int(current_values[key]):
            return
        record = self.repository.get_animal_companion(self.character_id)
        details = self._json_object(record.details_json)
        detail_key = detail_keys[key]
        try:
            old_adjustment = int(details.get(detail_key, 0) or 0)
        except (TypeError, ValueError):
            old_adjustment = 0
        new_adjustment = old_adjustment + int(value) - int(current_values[key])
        if new_adjustment:
            details[detail_key] = new_adjustment
        else:
            details.pop(detail_key, None)
        self.repository.update_animal_companion(
            replace(record, details_json=json.dumps(details))
        )
        self._refresh_animal_companion()

    def _save_companion_speed_total(self, key: str, value: int) -> None:
        if self._loading or self.character_id is None:
            return
        record = self.repository.get_animal_companion(self.character_id)
        details = self._json_object(record.details_json)
        details[f"{key}_speed_override"] = max(0, int(value))
        self.repository.update_animal_companion(
            replace(record, details_json=json.dumps(details))
        )
        self._refresh_animal_companion()

    def _save_companion_text_detail(self, key: str) -> None:
        if self._loading or self.character_id is None:
            return
        control = self.companion_identity_values.get(key)
        if not isinstance(control, QLineEdit):
            return
        record = self.repository.get_animal_companion(self.character_id)
        details = self._json_object(record.details_json)
        value = control.text().strip()
        if value:
            details[key] = value
        else:
            details.pop(key, None)
        self.repository.update_animal_companion(
            replace(record, details_json=json.dumps(details))
        )
        self._refresh_animal_companion()

    def _reset_companion_stat_adjustments(self) -> None:
        if self.character_id is None:
            return
        record = self.repository.get_animal_companion(self.character_id)
        details = self._json_object(record.details_json)
        for key in (
            "natural_armor_misc", "hp_misc", "fortitude_misc", "reflex_misc",
            "will_misc", "ac_misc", "flat_footed_ac_misc", "touch_ac_misc",
            "bab_misc", "cmb_misc", "cmd_misc", "attack_misc",
            "land_speed_override", "swim_speed_override", "fly_speed_override",
            "climb_speed_override", "burrow_speed_override",
            "spell_resistance", "damage_reduction",
        ):
            details.pop(key, None)
        self.repository.update_animal_companion(
            replace(record, details_json=json.dumps(details))
        )
        self._refresh_animal_companion()

    def _save_companion_abilities(self, item: QTableWidgetItem | None = None) -> None:
        if self._loading or self.character_id is None:
            return
        record=self.repository.get_animal_companion(self.character_id)
        if item is None or item.column() != 1:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not key:
            return
        try:
            score = int(item.text())
        except ValueError:
            self._refresh_animal_companion()
            return
        # Store only the explicitly edited score.  Automatic species and
        # companion-level advancement therefore keeps applying to the other
        # five abilities.
        values = self._json_object(record.ability_overrides_json)
        values[key] = score
        self.repository.update_animal_companion(replace(record,ability_overrides_json=json.dumps(values)))
        self._refresh_animal_companion()

    def _reset_companion_abilities(self) -> None:
        if self.character_id is None: return
        record = self.repository.get_animal_companion(self.character_id)
        self.repository.update_animal_companion(replace(record, ability_overrides_json="{}"))
        self._refresh_animal_companion()

    def _add_companion_training(self, kind: str) -> None:
        if self.character_id is None: return
        if kind == "Feats":
            record = self.repository.get_animal_companion(self.character_id)
            values = self._json_list(record.feats_json)
            statistics = getattr(self, "_companion_statistics", None)
            allowance = int(statistics.progression.feats if statistics is not None else 0)
            remaining = max(0, allowance - len(values))
            if not remaining:
                QMessageBox.information(
                    self,
                    "Animal companion feats",
                    "Every currently available companion feat slot is filled.",
                )
                return
            intelligence = int(
                statistics.ability_scores.get("int", 2)
                if statistics is not None else 2
            )
            dialog = AnimalCompanionFeatCatalogDialog(values, intelligence, self)
            dialog.catalog_subtitle.setText(
                dialog.catalog_subtitle.text()
                + f" {remaining} feat slot(s) remain at the current effective level."
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            if dialog.custom_requested:
                value, accepted = QInputDialog.getText(
                    self, "Custom companion feat", "Feat name"
                )
                selected_names = (value.strip(),) if accepted and value.strip() else ()
            else:
                selected_names = tuple(
                    str(entry.get("name", "")).strip()
                    for entry in self._catalog_dialog_entries(dialog)
                    if str(entry.get("name", "")).strip()
                )
            if not selected_names:
                return
            if len(selected_names) > remaining:
                QMessageBox.warning(
                    self,
                    "Too many companion feats",
                    f"Only {remaining} feat slot(s) remain. Remove {len(selected_names) - remaining} "
                    "selection(s) from the addition queue.",
                )
                return
            values.extend(selected_names)
            self.repository.update_animal_companion(
                replace(record, feats_json=json.dumps(values))
            )
            self._refresh_animal_companion()
            return
        elif kind == "Tricks":
            options=["Attack","Come","Defend","Down","Fetch","Guard","Heel","Perform","Seek","Stay","Track","Work","Custom…"]
        else: options=["Custom…"]
        singular = {"Tricks": "Trick", "Special abilities": "Special ability"}.get(kind, kind)
        value,accepted=QInputDialog.getItem(self,f"Add companion {singular.lower()}",singular,options,0,True)
        if not accepted or not value.strip(): return
        if value.strip() == "Custom…":
            value, accepted = QInputDialog.getText(self, f"Custom companion {singular.lower()}", "Name")
            if not accepted or not value.strip(): return
        record=self.repository.get_animal_companion(self.character_id)
        field={"Feats":"feats_json","Tricks":"tricks_json","Special abilities":"special_abilities_json"}[kind]
        values=self._json_list(getattr(record,field)); values.append(value.strip())
        self.repository.update_animal_companion(replace(record,**{field:json.dumps(values)})); self._refresh_animal_companion()

    def _add_companion_skill(self) -> None:
        if self.character_id is None: return
        animal_keys = {"acrobatics","climb","escape_artist","fly","intimidate","perception","stealth","survival","swim"}
        definitions = [definition for definition in SKILLS if definition.key in animal_keys]
        selected = self.companion_skill_table.currentRow()
        current_key = ""
        if selected >= 0 and self.companion_skill_table.item(selected, 1):
            current_key = str(self.companion_skill_table.item(selected,1).data(Qt.ItemDataRole.UserRole) or "")
        default = next((index for index,item in enumerate(definitions) if item.key == current_key), 0)
        name,accepted=QInputDialog.getItem(self,"Companion skill","Skill",[item.name for item in definitions],default,False)
        if not accepted or not name.strip(): return
        definition = next(item for item in definitions if item.name == name)
        record=self.repository.get_animal_companion(self.character_id)
        values=self._json_object(record.skill_ranks_json)
        current = int(values.get(definition.key, values.get(definition.name, 0)) or 0)
        maximum = getattr(
            getattr(self, "_companion_statistics", None), "progression", None
        )
        maximum_ranks = maximum.hit_dice if maximum is not None else 999
        ranks,accepted=QInputDialog.getInt(
            self,"Companion skill",f"Ranks in {name}",current,0,maximum_ranks
        )
        if not accepted: return
        values.pop(definition.name, None)
        if definition.name in self._json_object(record.skill_ranks_json):
            self.repository.update_animal_companion(
                replace(record, skill_ranks_json=json.dumps(values))
            )
        self._save_companion_skill_rank(definition.key, ranks)

    def _remove_companion_skill(self) -> None:
        if self.character_id is None or self.companion_skill_table.currentRow() < 0: return
        item=self.companion_skill_table.item(self.companion_skill_table.currentRow(),1)
        key=str(item.data(Qt.ItemDataRole.UserRole) or "")
        name=item.text()
        record=self.repository.get_animal_companion(self.character_id)
        values=self._json_object(record.skill_ranks_json); values.pop(key,None); values.pop(name,None)
        self.repository.update_animal_companion(replace(record,skill_ranks_json=json.dumps(values))); self._refresh_animal_companion()

    def _remove_companion_training(self, kind: str) -> None:
        if self.character_id is None: return
        table=self.companion_training_tabs[kind]; row=table.currentRow()
        if row < 0: return
        cell=table.item(row,0)
        if cell is None or not cell.text().strip() or not bool(cell.data(Qt.ItemDataRole.UserRole)): return
        record=self.repository.get_animal_companion(self.character_id)
        field={"Feats":"feats_json","Tricks":"tricks_json","Special abilities":"special_abilities_json"}[kind]
        values=self._json_list(getattr(record,field))
        index=sum(
            1 for prior in range(row)
            if bool(table.item(prior,0).data(Qt.ItemDataRole.UserRole))
            and table.item(prior,0).text().strip()
        )
        if 0 <= index < len(values): values.pop(index)
        self.repository.update_animal_companion(replace(record,**{field:json.dumps(values)})); self._refresh_animal_companion()









    @staticmethod
    def _feature_status(record) -> str:
        return feature_status(record)

    def _feature_summary_text(self, kind: str, record) -> str:
        return feature_summary_text(kind, record, SKILL_LABELS)

    def _feature_details_html(self, kind: str, record) -> str:
        return feature_details_html(kind, record, SKILL_LABELS)

    def _show_feature_details(self, kind: str) -> None:
        selectors = {
            "Martial Talent": self._selected_martial_talent,
            "Feat": self._selected_feat,
            "Trait": self._selected_trait,
        }
        record = selectors[kind]()
        if record is not None:
            self.feature_details.setHtml(self._feature_details_html(kind, record))

    def _wire_shared_feature_details(self) -> None:
        """Route row clicks from every record table into the shared detail panel."""

        rich_tables = {
            self.martial_talent_table, self.feat_table, self.trait_table,
        }
        for table in self.findChildren(QTableWidget):
            if table in rich_tables:
                continue
            table.cellClicked.connect(
                lambda row, _column, table=table: self._show_table_row_details(table, row)
            )
        self.skill_table.currentCellChanged.connect(
            lambda row, *_args: self._show_table_row_details(self.skill_table, row)
            if self.skill_table.hasFocus() and not self._loading else None
        )
        self.feature_details.textChanged.connect(
            lambda: setattr(self, "_active_skill_reference", None)
        )

    def _show_table_row_details(self, table: QTableWidget, row: int) -> None:
        if row < 0:
            return
        cells = [table.item(row, column) for column in range(table.columnCount())]
        if table is self.skill_table and cells and cells[0] and self.character_id is not None:
            from app.reference_rules import skill_reference
            from app.ui.reference_details import reference_details_html
            key = cells[0].data(Qt.ItemDataRole.UserRole)
            entry = skill_reference(key)
            summary = "<p><b>Your check:</b> " + html.escape(cells[2].text())
            summary += " · <b>Ranks:</b> " + html.escape(cells[4].text())
            summary += " · " + ("Class skill" if cells[1].text() == "■" else "Not a class skill") + "</p>"
            summary += "<p><b>Ability:</b> " + html.escape(cells[3].text()) + " · <b>Armor check penalty:</b> " + html.escape(cells[6].text()) + "</p>"
            self.feature_details.setHtml(reference_details_html(self, entry, title=cells[0].text().rstrip(" *"), summary=summary))
            self._active_skill_reference = key
            return
        tooltip = next((cell.toolTip() for cell in cells if cell and cell.toolTip()), "")
        if tooltip:
            self.feature_details.setHtml(tooltip)
            return
        fields: list[tuple[str, str]] = []
        for column, cell in enumerate(cells):
            if cell is None or not cell.text().strip() or table.isColumnHidden(column):
                continue
            header = table.horizontalHeaderItem(column)
            fields.append((header.text() if header else f"Column {column + 1}", cell.text()))
        if not fields:
            self.feature_details.clear()
            return
        title = fields[0][1]
        rows = "".join(
            f"<tr><th align='left'>{html.escape(label)}</th>"
            f"<td>{html.escape(value)}</td></tr>" for label, value in fields
        )
        self.feature_details.setHtml(f"<h3>{html.escape(title)}</h3><table>{rows}</table>")






    def _owned_magic_spheres(self) -> set[str]:
        if self.character_id is None:
            return set()
        return {
            spell.school_or_sphere
            for spell in effective_magic_talents(self.repository, self.character_id)
            if spell.catalog_category == "Base Sphere" and spell.school_or_sphere
        }

    def _owned_martial_spheres(self) -> set[str]:
        if self.character_id is None:
            return set()
        return {
            talent.sphere
            for talent in effective_martial_talents(self.repository, self.character_id)
            if talent.catalog_category == "Base Sphere" and talent.sphere
        }

    def _refresh_prodigy_sphere_rules(self) -> None:
        if self.character_id is None:
            return
        spells = effective_magic_talents(self.repository, self.character_id)
        martial = effective_martial_talents(self.repository, self.character_id)
        self.repository.sync_builtin_sphere_sequence_options(
            self.character_id,
            sphere_options(
                self._owned_magic_spheres() | self._owned_martial_spheres(),
                sphere_package_access(spells),
                {item.name for item in martial if item.enabled},
            ),
        )

    def _refresh_prodigy_imbues(self) -> None:
        if self.character_id is None:
            return
        spells = effective_magic_talents(self.repository, self.character_id)
        available = sphere_imbues(
            self._owned_magic_spheres(), sphere_package_access(spells)
        )
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        valid_keys = {item.key for item in available}
        selected_key = sequence.imbue_key if sequence.imbue_key in valid_keys else ""
        self._loading = True
        try:
            self.prodigy_imbue_combo.clear()
            self.prodigy_imbue_combo.addItem("Choose an imbue…", "")
            for item in available:
                self.prodigy_imbue_combo.addItem(
                    f"{item.sphere} — {item.name}", item.key
                )
            self.prodigy_imbue_combo.setCurrentIndex(
                max(0, self.prodigy_imbue_combo.findData(selected_key))
            )
        finally:
            self._loading = False
        if selected_key != sequence.imbue_key:
            self.repository.update_prodigy_sequence(replace(sequence, imbue_key=""))
        self._selected_imbue_key = selected_key
        self._update_imbue_display()
        self._refresh_sequence_options()

    def _imbue_changed(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        self._selected_imbue_key = str(self.prodigy_imbue_combo.currentData() or "")
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        self.repository.update_prodigy_sequence(
            replace(sequence, imbue_key=self._selected_imbue_key)
        )
        self._update_imbue_display()
        self._refresh_sequence_options()
        self._refresh_formula_dependents()
        from app.reference_rules import sequence_reference
        from app.ui.reference_details import reference_details_html
        imbue = next((item for item in SPHERE_IMBUES if item.key == self._selected_imbue_key), None)
        if imbue is not None:
            reference = sequence_reference(imbue.name, imbue.sphere)
            if reference is not None:
                self.feature_details.setHtml(reference_details_html(self, reference))

    def _update_imbue_display(self) -> None:
        item = next(
            (imbue for imbue in SPHERE_IMBUES if imbue.key == self._selected_imbue_key),
            None,
        )
        if item is None:
            self.prodigy_imbue_name.setText("NO IMBUE SELECTED")
            self.prodigy_imbue_value.setText("—")
            self.prodigy_imbue_description.setText(
                "Choose an imbuement granted by one of this Prodigy's magic spheres."
            )
            return
        self.prodigy_imbue_name.setText(f"{item.name.upper()}  ·  {item.sphere.upper()}")
        self.prodigy_imbue_value.setText(
            imbue_value(item, self._sequence_links, self._current_prodigy_level())
        )
        self.prodigy_imbue_description.setText(item.description)


















    def _refresh_currency(self) -> None:
        if self.character_id is None:
            return
        purse = self.repository.get_currency_purse(self.character_id)
        self._loading = True
        try:
            for key, control in self.currency_controls.items():
                control.setValue(int(getattr(purse, key)))
            self.currency_notes.setText(purse.notes)
        finally:
            self._loading = False
        total_gp = purse.platinum * 10 + purse.gold + purse.silver / 10 + purse.copper / 100
        self.currency_total.setText(f"Total value  {total_gp:g} gp")

    def _save_currency(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        self.repository.update_currency_purse(
            CurrencyPurse(
                self.character_id,
                copper=self.currency_controls["copper"].value(),
                silver=self.currency_controls["silver"].value(),
                gold=self.currency_controls["gold"].value(),
                platinum=self.currency_controls["platinum"].value(),
                notes=self.currency_notes.text(),
            )
        )
        self._refresh_currency()

    def _refresh_casting_profile(self) -> None:
        if self.character_id is None:
            return
        profile = self.repository.get_casting_profile(self.character_id)
        calculator = self._calculator()
        effective_profile = calculator.resolved_casting_profile()
        saved_formulas = {
            field_key: expression
            for (_entity_type, _entity_id, field_key), expression
            in self.repository.numeric_formulas(
                self.character_id, "casting", 0
            ).items()
        }
        prodigy_levels = self._current_prodigy_level()
        automatic_casting = self._automatic_class_casting()
        ability_modifier = self._ability_result(effective_profile.casting_ability).ability_modifier
        automatic_modifiers = calculator.automatic_modifier_map()
        automatic_total = lambda target: calculate_stat(
            [], automatic_modifiers.get(target, [])
        ).total
        statistics = calculate_casting_statistics(
            effective_profile,
            ability_modifier,
            caster_level_bonus=(
                self._prodigy_sequence_bonus() + automatic_total("caster_level")
            ),
            dc_bonus=automatic_total("save_dc"),
            msb_bonus=automatic_total("magic_skill_bonus"),
            msd_bonus=automatic_total("magic_skill_defense"),
            concentration_bonus=automatic_total("concentration"),
            spell_point_sources=calculator.spell_point_contributions(),
        )
        self._loading = True
        try:
            self.casting_ability.setCurrentIndex(
                max(0, self.casting_ability.findData(profile.casting_ability))
            )
            for field, control in (
                ("casting_class_levels", self.casting_class_levels),
                ("caster_level", self.caster_level),
                ("msb_misc", self.casting_msb_misc),
                ("dc_misc", self.casting_dc_misc),
                ("concentration_misc", self.casting_concentration_misc),
                ("spell_points_misc", self.spell_points_misc),
            ):
                control.set_expression(
                    saved_formulas.get(field, ""), getattr(profile, field)
                )
            if profile.auto_spell_points:
                self.spell_points_maximum.set_expression("", statistics.spell_points_maximum)
            else:
                self.spell_points_maximum.set_expression(
                    saved_formulas.get("spell_points_maximum", ""),
                    profile.spell_points_maximum,
                )
            self.spell_points_current.setValue(profile.spell_points_current)
            self.spell_points_temporary.setValue(profile.spell_points_temporary)
            self.spell_points_auto.setChecked(profile.auto_spell_points)
            self.spell_points_maximum.setEnabled(not profile.auto_spell_points)
            self.casting_class_levels.setEnabled(prodigy_levels == 0)
            self.caster_level.setEnabled(automatic_casting is None)
            self.spell_points_auto.setEnabled(True)
            self.spell_points_auto.setToolTip(
                "Use the modular class, tradition, ability, and other spell-point sources. "
                "Turn this off to enter a manual maximum."
            )
            if prodigy_levels:
                class_rule_note = "Driven automatically by Prodigy class levels"
                self.casting_class_levels.setToolTip(class_rule_note)
                self.caster_level.setToolTip(class_rule_note)
            elif automatic_casting is not None:
                casting_levels, effective_level, source = automatic_casting
                self.casting_class_levels.setToolTip("")
                self.caster_level.setToolTip(
                    f"Driven automatically by {source} {casting_levels} "
                    f"(effective caster level {effective_level})"
                )
            else:
                self.casting_class_levels.setToolTip("")
                self.caster_level.setToolTip("")
            self.tradition_name.setText(profile.tradition_name)
            self.tradition_boons.setText(profile.tradition_boons)
            self.tradition_drawbacks.setPlainText(profile.tradition_drawbacks)
            self.tradition_notes.setPlainText(profile.tradition_notes)
        finally:
            self._loading = False
        self.casting_cam.setText(f"{statistics.casting_ability_modifier:+d}")
        self.casting_save_dc.setText(str(statistics.save_dc))
        self.casting_msb.setText(f"{statistics.magic_skill_bonus:+d}")
        self.casting_msd.setText(str(statistics.magic_skill_defense))
        tradition_automation = calculator.casting_tradition_automation()
        msd_adjustments = tuple(
            adjustment
            for adjustment in tradition_automation.stat_adjustments
            if adjustment.target == "magic_skill_defense"
        )
        msd_tooltip = "MSD = 11 + MSB + applicable modifiers."
        if msd_adjustments:
            msd_tooltip += "\n\nAutomatic tradition adjustments:\n" + "\n".join(
                f"• {adjustment.source}: {adjustment.value:+d}"
                for adjustment in msd_adjustments
            )
        if tradition_automation.reminders:
            msd_tooltip += "\n\nConditional rules:\n" + "\n".join(
                f"• {reminder}" for reminder in tradition_automation.reminders
            )
        self.casting_msd.setToolTip(msd_tooltip)
        for labels in (
            self._classic_magic_skill_labels,
            self._combat_magic_skill_labels,
        ):
            labels["msb"].setText(f"{statistics.magic_skill_bonus:+d}")
            labels["msd"].setText(str(statistics.magic_skill_defense))
            labels["msd"].setToolTip(msd_tooltip)
        self.casting_concentration.setText(f"{statistics.concentration_bonus:+d}")
        self.spell_points_breakdown.setText(
            "  •  ".join(
                f"{source.source} {source.value:+d}"
                + (f" ({source.note})" if source.note else "")
                for source in statistics.spell_point_contributions
            )
        )
        self.quick_spell_points.setText(
            f"{profile.spell_points_current} / {statistics.spell_points_maximum}"
        )
        self.quick_spell_temp.setText(
            f"+{profile.spell_points_temporary} temporary"
            if profile.spell_points_temporary
            else "No temporary spell points"
        )
        play_values = {
            "caster_level": str(statistics.caster_level),
            "save_dc": str(statistics.save_dc),
            "msb": f"{statistics.magic_skill_bonus:+d}",
            "msd": str(statistics.magic_skill_defense),
            "cam": f"{statistics.casting_ability_modifier:+d}",
            "concentration": f"{statistics.concentration_bonus:+d}",
            "spell_points": (
                f"{profile.spell_points_current} / {statistics.spell_points_maximum}"
                + (
                    f"  (+{profile.spell_points_temporary})"
                    if profile.spell_points_temporary
                    else ""
                )
            ),
        }
        for key, value in play_values.items():
            self._play_casting_labels[key].setText(value)
        self._refresh_selected_spell_save_dc()
        self.spells_section_title.setText(
            f"MAGIC SPHERES  ·  CASTER LEVEL {statistics.caster_level}"
        )
        ranges = (
            25 + 5 * (statistics.caster_level // 2),
            100 + 10 * statistics.caster_level,
            400 + 40 * statistics.caster_level,
        )
        for row, distance in enumerate(ranges):
            self.magic_range_table.item(row, 2).setText(f"{distance} ft")

    def _save_casting_profile(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        prodigy_levels = self._current_prodigy_level()
        automatic_casting = self._automatic_class_casting()
        previous_profile = self.repository.get_casting_profile(self.character_id)
        auto_spell_points = self.spell_points_auto.isChecked()
        casting_ability = str(self.casting_ability.currentData() or "charisma")
        if prodigy_levels and casting_ability not in {"intelligence", "wisdom", "charisma"}:
            casting_ability = "charisma"
        formula_controls = {
            "casting_class_levels": self.casting_class_levels,
            "caster_level": self.caster_level,
            "msb_misc": self.casting_msb_misc,
            "dc_misc": self.casting_dc_misc,
            "concentration_misc": self.casting_concentration_misc,
            "spell_points_maximum": self.spell_points_maximum,
            "spell_points_misc": self.spell_points_misc,
        }
        try:
            resolved = {key: int(control.value()) for key, control in formula_controls.items()}
        except FormulaError:
            return
        for field, control in formula_controls.items():
            if field == "spell_points_maximum" and auto_spell_points:
                continue
            self.repository.set_numeric_formula(
                self.character_id, "casting", 0, field, control.expression
            )
        profile = CastingProfile(
            character_id=self.character_id,
            casting_ability=casting_ability,
            casting_class_levels=(
                prodigy_levels if prodigy_levels else resolved["casting_class_levels"]
            ),
            caster_level=(
                prodigy_caster_level(prodigy_levels)
                if prodigy_levels
                else (
                    automatic_casting[1]
                    if automatic_casting is not None
                    else resolved["caster_level"]
                )
            ),
            msb_misc=resolved["msb_misc"],
            dc_misc=resolved["dc_misc"],
            concentration_misc=resolved["concentration_misc"],
            spell_points_maximum=(
                previous_profile.spell_points_maximum
                if auto_spell_points else resolved["spell_points_maximum"]
            ),
            spell_points_current=self.spell_points_current.value(),
            spell_points_temporary=self.spell_points_temporary.value(),
            spell_points_misc=resolved["spell_points_misc"],
            auto_spell_points=auto_spell_points,
            tradition_name=self.tradition_name.text(),
            tradition_boons=self.tradition_boons.text(),
            tradition_drawbacks=self.tradition_drawbacks.toPlainText(),
            tradition_notes=self.tradition_notes.toPlainText(),
        )
        self.repository.update_casting_profile(profile)
        self._refresh_casting_profile()
        self._refresh_sphere_statistics()
        self._refresh_formula_dependents()

    def _spend_spell_point(self) -> None:
        if self.character_id is None:
            return
        profile = self.repository.get_casting_profile(self.character_id)
        if profile.spell_points_temporary > 0:
            profile = replace(
                profile, spell_points_temporary=profile.spell_points_temporary - 1
            )
        elif profile.spell_points_current > 0:
            profile = replace(
                profile, spell_points_current=profile.spell_points_current - 1
            )
        else:
            return
        self.repository.update_casting_profile(profile)
        self._refresh_casting_profile()
        self._refresh_formula_dependents()

    def _regain_spell_point(self) -> None:
        if self.character_id is None:
            return
        profile = self.repository.get_casting_profile(self.character_id)
        calculator = self._calculator()
        effective_profile = calculator.resolved_casting_profile()
        ability_modifier = self._ability_result(effective_profile.casting_ability).ability_modifier
        maximum = calculate_casting_statistics(
            effective_profile,
            ability_modifier,
            spell_point_sources=calculator.spell_point_contributions(),
        ).spell_points_maximum
        if profile.spell_points_current >= maximum:
            return
        self.repository.update_casting_profile(
            replace(profile, spell_points_current=profile.spell_points_current + 1)
        )
        self._refresh_casting_profile()
        self._refresh_formula_dependents()

    def _reset_spell_points(self) -> None:
        if self.character_id is None:
            return
        profile = self.repository.get_casting_profile(self.character_id)
        calculator = self._calculator()
        effective_profile = calculator.resolved_casting_profile()
        ability_modifier = self._ability_result(effective_profile.casting_ability).ability_modifier
        maximum = calculate_casting_statistics(
            effective_profile,
            ability_modifier,
            spell_point_sources=calculator.spell_point_contributions(),
        ).spell_points_maximum
        self.repository.update_casting_profile(
            replace(
                profile,
                spell_points_current=maximum,
                spell_points_temporary=0,
            )
        )
        self._refresh_casting_profile()
        self._refresh_formula_dependents()

    def _refresh_sphere_statistics(self) -> None:
        if self.character_id is None:
            return
        calculator = self._calculator()
        profile = calculator.resolved_casting_profile()
        ability_modifier = self._ability_result(profile.casting_ability).ability_modifier
        spells = [
            spell
            for spell in self.repository.list_spells(self.character_id)
            if spell.system == "Sphere" and spell.school_or_sphere.strip()
        ]
        saved = {
            item.sphere: item
            for item in self.repository.list_sphere_statistics(self.character_id)
        }
        sphere_names = sorted(
            {spell.school_or_sphere.strip() for spell in spells} | set(saved),
            key=str.casefold,
        )
        global_caster_level_bonus = calculator.automatic_total("caster_level")
        global_dc_bonus = calculator.automatic_total("save_dc")
        self.sphere_stats_table.setRowCount(0)
        for sphere in sphere_names:
            statistic = calculator.resolved_sphere_statistic(
                saved.get(sphere, SphereStatistic(self.character_id, sphere))
            )
            sphere_spells = [spell for spell in spells if spell.school_or_sphere == sphere]
            talents = sum(
                "talent" in spell.catalog_category.casefold() for spell in sphere_spells
            )
            drawbacks = sum(
                "drawback" in spell.catalog_category.casefold() for spell in sphere_spells
            )
            values = calculate_casting_statistics(
                profile,
                ability_modifier,
                statistic.caster_level_bonus
                + self._prodigy_sequence_bonus()
                + global_caster_level_bonus,
                statistic.dc_bonus
                + global_dc_bonus
                + calculator.sphere_dc_bonus(sphere),
            )
            row = self.sphere_stats_table.rowCount()
            self.sphere_stats_table.insertRow(row)
            row_values = (
                sphere,
                str(values.caster_level),
                str(values.save_dc),
                str(talents),
                str(drawbacks),
                f"{statistic.caster_level_bonus:+d}",
                f"{statistic.dc_bonus:+d}",
                statistic.notes,
            )
            for column, value in enumerate(row_values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, sphere)
                self.sphere_stats_table.setItem(row, column, cell)

    def _selected_sphere_name(self) -> str:
        row = self.sphere_stats_table.currentRow()
        if row < 0 or self.sphere_stats_table.item(row, 0) is None:
            return ""
        return str(
            self.sphere_stats_table.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""
        )

    def _edit_sphere_statistic(self, *_args) -> None:
        if self.character_id is None:
            return
        sphere = self._selected_sphere_name()
        if not sphere:
            QMessageBox.information(self, "Select a sphere", "Select a sphere row first.")
            return
        saved = {
            item.sphere: item
            for item in self.repository.list_sphere_statistics(self.character_id)
        }
        statistic = saved.get(sphere, SphereStatistic(self.character_id, sphere))
        field_keys = _sphere_stat_formula_keys(sphere)
        stored_formulas = self._saved_numeric_formulas("sphere_stat", 0)
        dialog = SphereStatisticDialog(
            statistic,
            self,
            formulas={
                dialog_key: stored_formulas.get(storage_key, "")
                for dialog_key, storage_key in field_keys.items()
            },
            formula_evaluator=self._evaluate_character_formula,
            formula_suggestions=self._character_formula_suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.update_sphere_statistic(
            SphereStatistic(self.character_id, sphere, **dialog.values)
        )
        self._save_numeric_formulas(
            "sphere_stat",
            0,
            {
                field_keys[dialog_key]: expression
                for dialog_key, expression in dialog.numeric_formulas.items()
            },
        )
        self._refresh_sphere_statistics()
        self._refresh_formula_dependents()

    def _clear_sphere_statistic(self) -> None:
        if self.character_id is None:
            return
        sphere = self._selected_sphere_name()
        if not sphere:
            QMessageBox.information(self, "Select a sphere", "Select a sphere row first.")
            return
        self._clear_numeric_formulas(
            "sphere_stat", 0, tuple(_sphere_stat_formula_keys(sphere).values())
        )
        self.repository.delete_sphere_statistic(self.character_id, sphere)
        self._refresh_sphere_statistics()
        self._refresh_formula_dependents()

    def _refresh_worn_items(self, items=None, enchantments=None) -> None:
        if self.character_id is None:
            return
        items = self.repository.list_equipment(self.character_id) if items is None else items
        enchantments = (
            self.repository.list_item_enchantments(self.character_id)
            if enchantments is None else enchantments
        )
        slots = list(self.repository.list_worn_slots(self.character_id))
        worn = [
            item for item in items
            if item.slot
            and effective_item_state(item) in {"worn", "armor", "shield"}
            and item.quantity > 0
        ]
        for item in worn:
            if item.slot not in slots:
                slots.append(item.slot)
        by_slot = {item.slot: item for item in worn}
        self.worn_table.setRowCount(0)
        for slot in slots:
            item = by_slot.get(slot)
            details = []
            if item is not None and item.ac_bonus:
                details.append(f"{item.bonus_type.title()} AC {item.ac_bonus:+d}")
            if item is not None and item.notes:
                details.append(item.notes)
            item_enchantment_summary = (
                enchantment_summary(item, enchantments) if item is not None else ""
            )
            if item_enchantment_summary and item_enchantment_summary != "No enchantments":
                details.append(item_enchantment_summary)
            row = self.worn_table.rowCount()
            self.worn_table.insertRow(row)
            values = (
                slot,
                item_display_name(item, enchantments) if item is not None else "Empty",
                self._weight_text(item.weight * item.quantity) if item is not None else "—",
                "; ".join(details) or "—",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(
                    Qt.ItemDataRole.UserRole,
                    item.id if item is not None else None,
                )
                self.worn_table.setItem(row, column, cell)

    def _edit_worn_slots(self) -> None:
        if self.character_id is None:
            return
        dialog = WornSlotsDialog(
            self.repository.list_worn_slots(self.character_id), self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_worn_slots(self.character_id, dialog.slots)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot save slots", str(error))
            return
        self._equipment_usage_changed()

    def _selected_worn_equipment(self):
        if self.character_id is None or self.worn_table.currentRow() < 0:
            return None
        item_id = self.worn_table.item(self.worn_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        if item_id is None:
            return None
        return next(
            (
                item
                for item in self.repository.list_equipment(self.character_id)
                if item.id == item_id
            ),
            None,
        )

    def _edit_worn_equipment(self, *_args) -> None:
        item = self._selected_worn_equipment()
        if item is None or self.character_id is None:
            QMessageBox.information(self, "Select an item", "Select a worn item first.")
            return
        dialog = EquipmentDialog(
            self,
            item,
            worn_slots=self.repository.list_worn_slots(self.character_id),
            **self._formula_dialog_options("equipment", item.id),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.update_equipment(self.character_id, item.id, **dialog.values)
        self._save_numeric_formulas(
            "equipment", item.id, dialog.numeric_formulas
        )
        self._refresh_equipment()
        self._refresh_combat()
        self._refresh_skills()
        self._refresh_formula_dependents()

    def _unequip_worn_equipment(self) -> None:
        item = self._selected_worn_equipment()
        if item is None or self.character_id is None:
            return
        if effective_item_state(item) == "stored":
            return
        self.repository.set_equipment_equipped(self.character_id, item.id, False)
        self._equipment_usage_changed()

    def _refresh_load(self, items=None) -> None:
        if self.character_id is None:
            return
        calculator = self._calculator()
        encumbrance = calculator.encumbrance()
        capacity = encumbrance.capacity
        status = encumbrance.load
        self.load_current.setText(self._weight_text(encumbrance.weight))
        self.load_light.setText(self._weight_text(capacity.light))
        self.load_medium.setText(self._weight_text(capacity.medium))
        self.load_heavy.setText(self._weight_text(capacity.heavy))
        self.load_lift.setText(self._weight_text(capacity.lift_off_ground))
        self.load_drag.setText(self._weight_text(capacity.push_or_drag))
        self.load_max_dex.setText(
            "No limit"
            if encumbrance.maximum_dexterity is None
            else f"+{encumbrance.maximum_dexterity}"
        )
        self.load_check_penalty.setText(
            "—" if not encumbrance.check_penalty else f"−{encumbrance.check_penalty}"
        )
        movement = calculator.movement_results()
        current_speed = int(movement["land_speed"])
        self.load_current_speed.setText(f"{current_speed} ft")
        self.load_run.setText(
            f"×{movement['run_multiplier']} · {movement['run_speed']} ft"
            if movement['run_multiplier'] else "Cannot run"
        )
        self.load_status.setText(f"{status.upper()} LOAD" if status != "Overloaded" else "OVERLOADED")
        object_name = {
            "Light": "loadLight",
            "Medium": "loadMedium",
            "Heavy": "loadHeavy",
            "Overloaded": "loadOverloaded",
        }[status]
        if self.load_status.objectName() != object_name:
            self.load_status.setObjectName(object_name)
            self.load_status.style().unpolish(self.load_status)
            self.load_status.style().polish(self.load_status)

    def _refresh_identity(self) -> None:
        if self.character_id is None:
            return
        summary = next(
            item for item in self.repository.list_characters() if item.id == self.character_id
        )
        self.record_character_name.setText(summary.name)
        details = self.repository.get_character_details(self.character_id)
        self._loading = True
        try:
            self.player_name.setText(details.player_name)
            self.race.setText(details.race)
            self.alignment.setCurrentText(details.alignment)
            self.deity.setText(details.deity)
            self.size.setCurrentText(details.size)
            preset_index = self.race_preset.findData(details.race_key)
            self.race_preset.setCurrentIndex(max(0, preset_index))
            choice_index = self.race_ability_choice.findData(details.race_ability_choice)
            self.race_ability_choice.setCurrentIndex(max(0, choice_index))
            preset = entry_by_key("races", details.race_key)
            profile = resolved_race(details)
            self.race_ability_choice.setEnabled(bool(profile.flexible_bonus))
            self._race_variant_key = details.race_variant_key
            self._race_alternate_trait_keys = details.race_alternate_trait_keys
            self._race_trait_choices = details.race_trait_choices
            self.configure_race.setText(
                f"Race choices ({len(details.race_alternate_trait_keys)})…"
                if details.race_alternate_trait_keys or details.race_variant_key
                else "Choose / configure race…"
            )
        finally:
            self._loading = False

    def _save_identity(self) -> None:
        if self._loading or self.character_id is None:
            return
        self.repository.update_character_details(
            CharacterDetails(
                character_id=self.character_id,
                player_name=self.player_name.text(),
                race=self.race.text(),
                alignment=self.alignment.currentText(),
                deity=self.deity.text(),
                size=self.size.currentText(),
                race_key=str(self.race_preset.currentData() or ""),
                race_ability_choice=(
                    str(self.race_ability_choice.currentData())
                    if self.race_ability_choice.isEnabled()
                    else ""
                ),
                race_variant_key=self._race_variant_key,
                race_alternate_trait_keys=self._race_alternate_trait_keys,
                race_trait_choices=self._race_trait_choices,
            )
        )
        self._refresh_abilities()
        self._refresh_combat()
        self._refresh_attacks()
        self._refresh_skills()
        self._refresh_hit_points()
        self._refresh_movement()
        self._refresh_special_abilities()

    def _race_preset_changed(self) -> None:
        if self._loading:
            return
        preset = entry_by_key("races", str(self.race_preset.currentData() or ""))
        self._loading = True
        try:
            self._race_variant_key = ""
            self._race_alternate_trait_keys = ()
            self._race_trait_choices = ()
            if preset is None:
                self.race_ability_choice.setEnabled(False)
            else:
                self.race.setText(preset["name"])
                self.size.setCurrentText(preset["size"])
                self.race_ability_choice.setEnabled(bool(preset.get("flexible_bonus")))
        finally:
            self._loading = False
        self._save_identity()

    def _configure_race(self) -> None:
        if self.character_id is None:
            return
        dialog = RaceCatalogDialog(self.repository.get_character_details(self.character_id), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selection = dialog.selection()
        if not selection:
            return
        self._loading = True
        try:
            index = self.race_preset.findData(selection["race_key"])
            self.race_preset.setCurrentIndex(max(0, index))
            self.race.setText(selection["race_name"])
            self.size.setCurrentText(selection["size"])
            self._race_variant_key = selection["variant_key"]
            self._race_alternate_trait_keys = tuple(selection["alternate_trait_keys"])
            self._race_trait_choices = tuple(selection["trait_choices"])
            ability_index = self.race_ability_choice.findData(selection["ability_choice"])
            self.race_ability_choice.setCurrentIndex(max(0, ability_index))
            profile = resolved_race(CharacterDetails(
                self.character_id,
                race=selection["race_name"], size=selection["size"],
                race_key=selection["race_key"],
                race_ability_choice=selection["ability_choice"],
                race_variant_key=selection["variant_key"],
                race_alternate_trait_keys=tuple(selection["alternate_trait_keys"]),
                race_trait_choices=tuple(selection["trait_choices"]),
            ))
            self.race_ability_choice.setEnabled(bool(profile.flexible_bonus))
        finally:
            self._loading = False
        self._save_identity()
        self._refresh_identity()

    def _race_name_edited(self) -> None:
        preset = entry_by_key("races", str(self.race_preset.currentData() or ""))
        if preset is not None and self.race.text().strip() != preset["name"]:
            self._loading = True
            try:
                self.race_preset.setCurrentIndex(0)
                self.race_ability_choice.setEnabled(False)
                self._race_variant_key = ""
                self._race_alternate_trait_keys = ()
                self._race_trait_choices = ()
            finally:
                self._loading = False
        self._save_identity()

    def _refresh_classes(self) -> None:
        if self.character_id is None:
            return
        stored_classes = self.repository.list_class_levels(self.character_id)
        classes = self._calculator().resolved_classes()
        archetypes_by_level = self.repository.list_class_archetype_keys(self.character_id)
        self.class_table.setRowCount(0)
        for class_level in classes:
            row = self.class_table.rowCount()
            self.class_table.insertRow(row)
            values = (
                class_level.class_name,
                ", ".join(
                    str(archetype_entry(key)["name"])
                    for key in archetypes_by_level.get(class_level.id, ())
                    if archetype_entry(key) is not None
                ) or "—",
                str(class_level.level),
                "—" if not class_level.hit_die else f"d{class_level.hit_die}",
                str(class_level.hp_gained),
                class_level.bab_progression,
                class_level.fort_progression,
                class_level.reflex_progression,
                class_level.will_progression,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, class_level.id)
                self.class_table.setItem(row, column, item)
        self.level_summary.setText(
            f"Total level {sum(item.level for item in classes)}  ·  BAB {total_bab(classes):+d}"
        )
        self._sync_prodigy_class_rules(stored_classes)
        self._refresh_sphere_capabilities(stored_classes, archetypes_by_level)
        # Capability resolution decides whether this build stacks Spheres caster
        # levels or uses a traditional per-class progression.  Resolve it before
        # synchronizing the persistent casting profile so newly added Spheres
        # classes work on their first refresh, not only the second one.
        self._sync_class_casting_rules(stored_classes)
        self._refresh_proficiencies()
        self._refresh_inquisitor_features()
        self._refresh_animal_companion()

    def _refresh_favored_class_bonuses(self) -> None:
        if self.character_id is None:
            return
        classes = self.repository.list_class_levels(self.character_id)
        saved = self.repository.list_favored_class_bonuses(self.character_id)
        self._favored_class_controls.clear()
        self.favored_class_table.setRowCount(0)
        self._loading = True
        try:
            for class_level in classes:
                allocation = saved.get(
                    class_level.id,
                    FavoredClassBonus(self.character_id, class_level.id),
                )
                values = [
                    allocation.hp_bonus,
                    allocation.skill_point_bonus,
                    allocation.manual_bonus,
                ]
                if sum(values) > class_level.level:
                    overflow = sum(values) - class_level.level
                    for index in (2, 1, 0):
                        removed = min(values[index], overflow)
                        values[index] -= removed
                        overflow -= removed
                    allocation = replace(
                        allocation,
                        hp_bonus=values[0],
                        skill_point_bonus=values[1],
                        manual_bonus=values[2],
                    )
                    self.repository.update_favored_class_bonus(allocation)
                row = self.favored_class_table.rowCount()
                self.favored_class_table.insertRow(row)
                class_item = QTableWidgetItem(class_level.class_name)
                class_item.setData(Qt.ItemDataRole.UserRole, class_level.id)
                self.favored_class_table.setItem(row, 0, class_item)
                self.favored_class_table.setItem(row, 1, QTableWidgetItem(str(class_level.level)))
                controls = []
                for column, (field, value) in enumerate((
                    ("hp", allocation.hp_bonus),
                    ("skill", allocation.skill_point_bonus),
                    ("manual", allocation.manual_bonus),
                ), 2):
                    spin = QSpinBox()
                    spin.setRange(0, class_level.level)
                    spin.setValue(value)
                    spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    spin.valueChanged.connect(
                        partial(self._save_favored_class_bonus, class_level.id, field)
                    )
                    self.favored_class_table.setCellWidget(row, column, spin)
                    controls.append(spin)
                code = QLineEdit(allocation.manual_code)
                code.setPlaceholderText("e.g. race-specific favored-class option")
                code.editingFinished.connect(
                    partial(self._save_favored_class_bonus, class_level.id, "code")
                )
                self.favored_class_table.setCellWidget(row, 5, code)
                self._favored_class_controls[class_level.id] = (
                    controls[0], controls[1], controls[2], code, class_level.level
                )
        finally:
            self._loading = False
        self._update_favored_class_summary()
        fit_table_rows(self.favored_class_table, len(classes), 1, 5)

    def _refresh_advancement_budgets(self) -> None:
        if self.character_id is None:
            return
        saved_adjustments = self.repository.list_advancement_adjustments(
            self.character_id
        )
        advancement_formulas = self._saved_numeric_formulas("advancement", 0)
        budgets = character_advancement_budgets(self.repository, self.character_id)
        skill_budget = next(
            (budget for budget in budgets if budget.key == "skill_points"), None
        )
        if skill_budget is not None and hasattr(self, "skill_budget_label"):
            self.skill_budget_label.setText(
                f"Ranks {skill_budget.used}/{skill_budget.total} · "
                f"{skill_budget.remaining} available"
            )
        self._loading = True
        try:
            self._advancement_controls.clear()
            self.advancement_table.setRowCount(0)
            for budget in budgets:
                row = self.advancement_table.rowCount()
                self.advancement_table.insertRow(row)
                name = QTableWidgetItem(budget.name)
                name.setData(Qt.ItemDataRole.UserRole, budget.key)
                self.advancement_table.setItem(row, 0, name)
                automatic = QTableWidgetItem(
                    "Open" if budget.automatic is None else str(budget.automatic)
                )
                automatic.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.advancement_table.setItem(row, 1, automatic)

                slug = reference_key(budget.key)[:50]
                saved = saved_adjustments.get(budget.key)
                adjustment = FormulaNumberEdit(
                    -999,
                    999,
                    evaluator=self._evaluate_character_formula,
                    suggestion_provider=self._character_formula_suggestions,
                )
                adjustment.preview.setMinimumWidth(48)
                adjustment.set_expression(
                    advancement_formulas.get(f"{slug}_adjustment", ""),
                    saved.adjustment if saved else 0,
                )
                adjustment.editor.editingFinished.connect(
                    partial(self._save_advancement_adjustment, budget.key)
                )
                self.advancement_table.setCellWidget(row, 2, adjustment)

                override = FormulaLineEdit(
                    suggestion_provider=self._character_formula_suggestions,
                    require_equals=True,
                )
                override.setPlaceholderText("Auto, number, or =formula")
                override_expression = advancement_formulas.get(
                    f"{slug}_override", ""
                )
                if override_expression:
                    override.setText(override_expression)
                elif saved is not None and saved.override_total is not None:
                    override.setText(str(saved.override_total))
                override.setAlignment(Qt.AlignmentFlag.AlignCenter)
                override.editingFinished.connect(
                    partial(self._save_advancement_adjustment, budget.key)
                )
                self.advancement_table.setCellWidget(row, 3, override)

                for column, value in ((4, budget.total), (5, budget.used), (6, budget.remaining)):
                    cell = QTableWidgetItem(str(value))
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if column == 6 and value < 0:
                        cell.setForeground(QColor("#B00020"))
                        font = cell.font()
                        font.setBold(True)
                        cell.setFont(font)
                    self.advancement_table.setItem(row, column, cell)

                note = QLineEdit()
                note.setText(saved.note if saved else "")
                note.setPlaceholderText(budget.explanation)
                note.setToolTip(budget.explanation)
                note.editingFinished.connect(
                    partial(self._save_advancement_adjustment, budget.key)
                )
                self.advancement_table.setCellWidget(row, 7, note)
                self._advancement_controls[budget.key] = (adjustment, override, note)
        finally:
            self._loading = False

    def _refresh_ability_score_increases(self) -> None:
        if self.character_id is None:
            return
        allocations = self.repository.list_ability_score_increases(self.character_id)
        base = self.repository.get_ability_scores(self.character_id)
        total_level = sum(
            value.level for value in self.repository.list_class_levels(self.character_id)
        )
        allowance = total_level // 4
        used = sum(value.points for value in allocations.values())
        results = self._ability_results()
        self._loading = True
        try:
            for key, control in self.asi_controls.items():
                control.setValue(
                    allocations.get(
                        key,
                        AbilityScoreIncreaseAllocation(self.character_id, key),
                    ).points
                )
                self.asi_base_labels[key].setText(str(base[key]))
                self.asi_current_labels[key].setText(str(results[key].total))
        finally:
            self._loading = False
        self.asi_summary.setText(
            f"Automatic allowance {allowance}  ·  allocated {used}  ·  "
            f"remaining {allowance - used}. Level increases stay separate from base scores."
        )
        self.asi_summary.setProperty("overBudget", used > allowance)
        self.asi_summary.style().unpolish(self.asi_summary)
        self.asi_summary.style().polish(self.asi_summary)

    def _save_ability_score_increase(self, ability: str, points: int) -> None:
        if self._loading or self.character_id is None:
            return
        self.repository.update_ability_score_increase(
            AbilityScoreIncreaseAllocation(self.character_id, ability, points)
        )
        self._refresh_ability_score_increases()
        self._refresh_abilities()
        self._refresh_combat()
        self._refresh_skills()
        self._refresh_hit_points()
        self._refresh_casting_profile()
        self._refresh_advancement_budgets()
        self._refresh_formula_dependents()

    def _save_advancement_adjustment(self, budget_key: str, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        controls = self._advancement_controls.get(budget_key)
        if controls is None:
            return
        adjustment, override, note = controls
        override_text = override.text().strip()
        slug = reference_key(budget_key)[:50]
        try:
            adjustment_value = int(adjustment.value())
        except FormulaError:
            return
        if override_text:
            try:
                if override_text.startswith("="):
                    value = float(self._evaluate_character_formula(override_text))
                    override_total = round(value)
                    if abs(value - override_total) > 1e-9:
                        raise ValueError
                else:
                    override_total = int(override_text)
                if override_total < 0:
                    raise ValueError
            except (ValueError, FormulaError):
                override.setProperty("invalid", True)
                override.style().unpolish(override)
                override.style().polish(override)
                return
        else:
            override_total = None
        self.repository.set_numeric_formula(
            self.character_id,
            "advancement",
            0,
            f"{slug}_adjustment",
            adjustment.expression,
        )
        self.repository.set_numeric_formula(
            self.character_id,
            "advancement",
            0,
            f"{slug}_override",
            override_text if override_text.startswith("=") else "",
        )
        override.setProperty("invalid", False)
        self.repository.update_advancement_adjustment(AdvancementAdjustment(
            self.character_id,
            budget_key,
            adjustment_value,
            override_total,
            note.text(),
        ))
        self._refresh_advancement_budgets()

    def _update_favored_class_summary(self) -> None:
        if self.character_id is None:
            return
        classes = self.repository.list_class_levels(self.character_id)
        saved = self.repository.list_favored_class_bonuses(self.character_id)
        hp_total = sum(item.hp_bonus for item in saved.values())
        skill_total = sum(item.skill_point_bonus for item in saved.values())
        allocated = sum(
            item.hp_bonus + item.skill_point_bonus + item.manual_bonus
            for item in saved.values()
        )
        self.favored_class_summary.setText(
            f"Totals: +{hp_total} HP  ·  +{skill_total} skill points  ·  "
            f"{max(0, sum(item.level for item in classes) - allocated)} unallocated"
            if classes else "No class levels yet."
        )

    def _save_favored_class_bonus(self, class_level_id: int, changed: str, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        controls = self._favored_class_controls.get(class_level_id)
        if controls is None:
            return
        hp, skill, manual, code, level = controls
        values = {"hp": hp.value(), "skill": skill.value(), "manual": manual.value()}
        overflow = sum(values.values()) - level
        if overflow > 0 and changed in values:
            control = {"hp": hp, "skill": skill, "manual": manual}[changed]
            self._loading = True
            try:
                control.setValue(max(0, control.value() - overflow))
            finally:
                self._loading = False
            values[changed] = control.value()
        self.repository.update_favored_class_bonus(
            FavoredClassBonus(
                self.character_id,
                class_level_id,
                values["hp"],
                values["skill"],
                values["manual"],
                code.text(),
            )
        )
        self._update_favored_class_summary()
        self._refresh_hit_points()
        self._refresh_advancement_budgets()

    def _refresh_custom_trackers(
        self, calculator: CharacterCalculationService | None = None
    ) -> None:
        if self.character_id is None:
            return
        resolved = CustomTrackerResolver(
            self.repository, self.character_id, calculator
        ).resolve_all()
        labels = {
            "calculated": "Calculated",
            "counter": "Counter",
            "pool": "Resource Pool",
        }
        self.custom_tracker_table.setRowCount(0)
        for item in resolved:
            tracker = item.tracker
            row = self.custom_tracker_table.rowCount()
            self.custom_tracker_table.insertRow(row)
            if tracker.tracker_type == "calculated":
                current = display_number(item.value)
            else:
                current = display_number(tracker.current_value)
                if tracker.temporary_value:
                    current += f" ({tracker.temporary_value:+g} temp)"
            reference = f"trackers.{tracker.key}.value"
            values = (
                tracker.name,
                labels.get(tracker.tracker_type, tracker.tracker_type.title()),
                current,
                display_number(item.maximum),
                tracker.unit or "—",
                tracker.formula or f"Manual · {reference}",
            )
            tooltip = self._readable_tooltip(
                tracker.name,
                (
                    f"Reference: {reference}\n"
                    f"Maximum reference: trackers.{tracker.key}.maximum\n"
                    f"Formula: {tracker.formula or 'Manual maximum'}"
                    + (f"\nRecovery: {tracker.recovery_event} → {tracker.recovery_operation}" if tracker.recovery_event != "none" else "")
                    + (f"\n\n{tracker.description}" if tracker.description else "")
                    + (f"\n\nFormula error: {item.error}" if item.error else "")
                ),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, tracker.id)
                cell.setToolTip(tooltip)
                if item.error:
                    cell.setForeground(Qt.GlobalColor.red)
                self.custom_tracker_table.setItem(row, column, cell)
        fit_table_rows(self.custom_tracker_table, len(resolved), 2, 6)
        self._sync_custom_tracker_blocks(resolved)

    def _sync_custom_tracker_blocks(self, resolved) -> None:
        if self.character_id is None:
            return
        if self._tracker_block_character_id != self.character_id:
            for key, block in tuple(self.custom_tracker_blocks.items()):
                self.custom_sections.pop(f"tracker:{key}", None)
                block.setParent(None)
                block.deleteLater()
            self.custom_tracker_blocks.clear()
            self._tracker_block_character_id = self.character_id
        active_keys = {item.tracker.key for item in resolved}
        changed = False
        for key in tuple(self.custom_tracker_blocks):
            if key in active_keys:
                continue
            block = self.custom_tracker_blocks.pop(key)
            self.custom_sections.pop(f"tracker:{key}", None)
            block.setParent(None)
            block.deleteLater()
            changed = True
        for item in resolved:
            key = item.tracker.key
            block = self.custom_tracker_blocks.get(key)
            if block is None:
                block = CustomTrackerBlock(
                    item, self._save_custom_tracker_block, self._edit_custom_tracker_by_id
                )
                self.custom_tracker_blocks[key] = block
                self.custom_sections[f"tracker:{key}"] = block
                insertion = self.builder_layout.indexOf(self.casting_profile_section)
                self.builder_layout.insertWidget(
                    insertion if insertion >= 0 else max(0, self.builder_layout.count() - 1),
                    block,
                )
                changed = True
            else:
                block.update_from(item)
        if changed:
            self.custom_sections_changed.emit()

    def _save_custom_tracker_block(
        self, tracker_id: int, current: float, temporary: float
    ) -> None:
        if self.character_id is None:
            return
        self.repository.set_custom_tracker_values(
            self.character_id,
            tracker_id,
            current_value=current,
            temporary_value=temporary,
        )
        self._refresh_formula_dependents()

    def _edit_custom_tracker_by_id(self, tracker_id: int) -> None:
        if self.character_id is None:
            return
        tracker = next(
            (
                item
                for item in self.repository.list_custom_trackers(self.character_id)
                if item.id == tracker_id
            ),
            None,
        )
        if tracker is None:
            return
        dialog = CustomTrackerDialog(
            self.repository, self.character_id, self, tracker=tracker
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_custom_tracker(
                self.character_id, tracker.id, **dialog.values
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot update tracker", str(error))
            return
        self._refresh_formula_dependents()

    def _selected_custom_tracker(self) -> CustomTracker | None:
        if self.character_id is None or self.custom_tracker_table.currentRow() < 0:
            return None
        tracker_id = self.custom_tracker_table.item(
            self.custom_tracker_table.currentRow(), 0
        ).data(Qt.ItemDataRole.UserRole)
        return next(
            (
                tracker for tracker in self.repository.list_custom_trackers(self.character_id)
                if tracker.id == tracker_id
            ),
            None,
        )

    def _add_custom_tracker(self, tracker_type: str) -> None:
        if self.character_id is None:
            return
        dialog = CustomTrackerDialog(
            self.repository, self.character_id, self, default_type=tracker_type
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.add_custom_tracker(self.character_id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add tracker", str(error))
            return
        self._refresh_formula_dependents()

    def _edit_custom_tracker(self, *_args) -> None:
        tracker = self._selected_custom_tracker()
        if tracker is None or self.character_id is None:
            QMessageBox.information(self, "Select a tracker", "Select a custom tracker first.")
            return
        dialog = CustomTrackerDialog(
            self.repository, self.character_id, self, tracker=tracker
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_custom_tracker(
                self.character_id, tracker.id, **dialog.values
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot update tracker", str(error))
            return
        self._refresh_formula_dependents()

    def _remove_custom_tracker(self) -> None:
        tracker = self._selected_custom_tracker()
        if tracker is None or self.character_id is None:
            QMessageBox.information(self, "Select a tracker", "Select a custom tracker first.")
            return
        reference_prefix = f"trackers.{tracker.key}."
        dependents = []
        for candidate in self.repository.list_custom_trackers(self.character_id):
            if candidate.id == tracker.id or not candidate.formula:
                continue
            try:
                references = formula_references(candidate.formula)
            except FormulaError:
                continue
            if any(reference.startswith(reference_prefix) for reference in references):
                dependents.append(candidate.name)
        if dependents:
            QMessageBox.warning(
                self,
                "Tracker is still referenced",
                f"Remove its references from these formulas first: {', '.join(dependents)}",
            )
            return
        self.repository.delete_custom_tracker(self.character_id, tracker.id)
        self._refresh_formula_dependents()

    def _refresh_sphere_capabilities(self, classes=None, archetypes_by_level=None) -> None:
        if self.character_id is None:
            return
        classes = classes or self.repository.list_class_levels(self.character_id)
        archetypes_by_level = archetypes_by_level or self.repository.list_class_archetype_keys(
            self.character_id
        )
        selected_keys = {
            key for keys in archetypes_by_level.values() for key in keys
        }
        definitions = {
            key: entry
            for key in selected_keys
            if (entry := archetype_entry(key)) is not None
        }
        class_definitions = {str(entry["key"]): entry for entry in entries("classes")}
        for key, entry in tuple(class_definitions.items()):
            if not key.startswith("pathfinder-class:") and not key.startswith("spheres-class:") and key != "prodigy":
                class_definitions[f"pathfinder-class:{key}"] = entry
        capabilities = resolve_sphere_capabilities(
            classes, archetypes_by_level, definitions, class_definitions
        )
        self._class_capabilities = capabilities

        for rows in (
            self._classic_magic_skill_rows,
            self._combat_magic_skill_rows,
        ):
            for row in rows.values():
                row.setVisible(capabilities.magic)

        self._set_section_rule_available("casting_profile", capabilities.magic)
        self._set_section_rule_available(
            "traditional_casting", capabilities.traditional_spells
        )
        self._set_section_rule_available("spells_known", capabilities.traditional_spells)
        self._set_section_rule_available(
            "spell_level_overview", capabilities.traditional_spells
        )
        self._set_section_rule_available(
            "spells_prepared", bool(self._prepared_caster_capacities())
        )
        self.magic_sphere_build_panel.setVisible(capabilities.magic)
        self._set_section_rule_available("spell_points", capabilities.magic)
        self._set_section_rule_available(
            "casting_play", capabilities.any_spellcasting
        )
        self._set_section_rule_available("magic_talents", capabilities.magic)
        self._set_section_rule_available("magic_ranges", capabilities.magic)
        magic_columns = self.custom_layouts.get("magic_columns")
        if magic_columns is not None:
            magic_columns.setStretch(0, 1 if capabilities.any_spellcasting else 0)
            magic_columns.setStretch(1, 4)
        magic_index = self.page_tabs.indexOf(self.magic_scroll)
        if magic_index >= 0:
            current_name = self.page_tabs.tabText(magic_index)
            if current_name in {
                "3   MAGIC & SPHERES",
                "3   SPELLCASTING",
                "3   SPELLCASTING & SPHERES",
            }:
                self.page_tabs.setTabText(
                    magic_index, self.default_sheet_tab_name("magic")
                )
            self.page_tabs.setTabVisible(
                magic_index, capabilities.any_spellcasting
            )

        self.martial_sphere_build_panel.setVisible(capabilities.martial)
        self._set_section_rule_available("martial_focus", capabilities.martial)
        self._set_section_rule_available("martial_talents", capabilities.martial)
        self._set_section_rule_available(
            "sphere_drawbacks", capabilities.magic or capabilities.martial
        )

        self._set_section_rule_available("prodigy_sequence", capabilities.sequence)
        self._set_section_rule_available("imbue", capabilities.sequence)
        self._refresh_traditional_casting_summary(
            classes, archetypes_by_level, definitions, class_definitions
        )
        if capabilities.magic and capabilities.traditional_spells:
            self.casting_play_title.setText("SPELLCASTING & SPHERES SUMMARY")
            self.casting_play_note.setText("Traditional spellcasting and global Spheres values share this play page.")
            self.spells_section_title.setText("MAGIC SPHERES")
            self.spells_section_note.setText("Browse usable sphere talents and effects. Traditional spells are kept in Spells Known.")
            self.add_magic_button.setText("+ Browse sphere magic")
        elif capabilities.traditional_spells:
            self.casting_play_title.setText("SPELLCASTING SUMMARY")
            self.casting_play_note.setText("Traditional caster level and concentration are driven by the selected class progression.")
            self.spells_section_title.setText("MAGIC SPHERES")
            self.spells_section_note.setText(
                "This character uses traditional spellcasting; sphere effects are not enabled."
            )
            self.add_magic_button.setText("+ Add known spell")
        else:
            self.casting_play_title.setText("MAGIC SUMMARY")
            self.casting_play_note.setText("Global spherecasting values. Build-time casting choices and tradition details are kept on Page 0.")
            self.spells_section_title.setText("MAGIC SPHERES")
            self.spells_section_note.setText("Browse usable talents and sphere effects. Base spheres and their initial drawbacks are managed on Page 0.")
            self.add_magic_button.setText("+ Browse magic")
        for key in ("msb", "msd", "cam", "spell_points"):
            self._play_casting_labels[key].parentWidget().setVisible(capabilities.magic)
        self._play_casting_labels["save_dc"].parentWidget().setVisible(
            capabilities.any_spellcasting
        )
        self._play_casting_captions["save_dc"].setText("SELECTED SPELL DC")
        self._refresh_selected_spell_save_dc()

    def default_sheet_tab_name(self, key: str) -> str:
        """Resolve a built-in page name without overwriting a user rename."""

        if key != "magic":
            return ""
        if self._class_capabilities.magic and self._class_capabilities.traditional_spells:
            return "3   SPELLCASTING & SPHERES"
        if self._class_capabilities.traditional_spells:
            return "3   SPELLCASTING"
        return "3   MAGIC & SPHERES"

    def _set_section_rule_available(self, key: str, available: bool) -> None:
        """Combine rules eligibility with the user's per-character placement.

        Building Blocks owns whether a section is placed; class capabilities
        own whether it is meaningful for the current character.  Keeping those
        flags separate prevents a layout reload from resurrecting an irrelevant
        class-system block.
        """
        section = self.custom_sections.get(key)
        if section is None:
            return
        section.setProperty("ruleAvailable", bool(available))
        placed = section.property("blockInstanceVisible")
        section.setVisible(bool(available) and placed is not False)

    def is_sheet_tab_available(self, key: str) -> bool:
        """Return whether character rules currently permit a built-in tab."""
        if key == "magic":
            return self._class_capabilities.any_spellcasting
        if key == "companion":
            return self._companion_grant.available
        return True

    def _refresh_traditional_casting_summary(
        self,
        classes,
        archetypes_by_level,
        archetype_definitions,
        class_definitions,
    ) -> None:
        traditional = []
        for class_level in classes:
            local = resolve_sphere_capabilities(
                (class_level,),
                {class_level.id: archetypes_by_level.get(class_level.id, ())},
                archetype_definitions,
                class_definitions,
            )
            if not local.traditional_spells:
                continue
            definition = class_definitions.get(class_level.preset_key) or class_definitions.get(
                f"pathfinder-class:{class_level.preset_key}"
            )
            casting = (definition or {}).get("casting") or {}
            traditional.append((class_level, casting))
        if not traditional:
            for label in self.traditional_casting_labels.values():
                label.setText("—")
            return
        ability_labels = {
            "str": "STR", "dex": "DEX", "con": "CON", "int": "INT",
            "wis": "WIS", "cha": "CHA", "strength": "STR", "dexterity": "DEX",
            "constitution": "CON", "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA",
        }
        self.traditional_casting_labels["classes"].setText(
            ", ".join(f"{class_level.class_name} {class_level.level}" for class_level, _casting in traditional)
        )
        self.traditional_casting_labels["method"].setText(
            ", ".join(sorted({str(casting.get("type") or "Spellcasting").title() for _class, casting in traditional}))
        )
        self.traditional_casting_labels["ability"].setText(
            ", ".join(sorted({ability_labels.get(str(casting.get("ability") or "").casefold(), "Varies") for _class, casting in traditional}))
        )
        automatic = automatic_traditional_casting(
            [class_level for class_level, _casting in traditional], class_definitions,
            self.repository.list_class_archetype_keys(self.character_id),
            {
                key: entry
                for keys in self.repository.list_class_archetype_keys(self.character_id).values()
                for key in keys
                if (entry := archetype_entry(key)) is not None
            },
            {
                class_level.id: archetype_choice_selections_from_records(
                    self.repository.list_class_feature_selections(self.character_id),
                    class_level.id,
                )
                for class_level, _casting in traditional
            },
        )
        self.traditional_casting_labels["caster_level"].setText(
            str(automatic[1]) if automatic else "—"
        )

    def _automatic_class_casting(self, classes=None):
        if self.character_id is None:
            return None
        classes = classes or self.repository.list_class_levels(self.character_id)
        definitions = {entry["key"]: entry for entry in entries("classes")}
        archetypes_by_level = self.repository.list_class_archetype_keys(self.character_id)
        archetype_definitions = {
            key: entry
            for keys in archetypes_by_level.values()
            for key in keys
            if (entry := archetype_entry(key)) is not None
        }
        selections = self.repository.list_class_feature_selections(self.character_id)
        return automatic_class_casting(
            classes, definitions, archetypes_by_level, archetype_definitions,
            {
                class_level.id: archetype_choice_selections_from_records(
                    selections, class_level.id
                )
                for class_level in classes
            },
        )

    def _sync_class_casting_rules(self, classes=None) -> None:
        if self.character_id is None:
            return
        definitions = {entry["key"]: entry for entry in entries("classes")}
        archetypes_by_level = self.repository.list_class_archetype_keys(self.character_id)
        selected_archetype_definitions = {
            key: entry
            for keys in archetypes_by_level.values()
            for key in keys
            if (entry := archetype_entry(key)) is not None
        }
        automatic = (
            automatic_sphere_casting(
                classes or self.repository.list_class_levels(self.character_id),
                definitions,
                archetypes_by_level,
                selected_archetype_definitions,
                {
                    class_level.id: archetype_choice_selections_from_records(
                        self.repository.list_class_feature_selections(self.character_id),
                        class_level.id,
                    )
                    for class_level in (classes or self.repository.list_class_levels(self.character_id))
                },
            )
            if self._class_capabilities.magic
            else automatic_traditional_casting(
                classes or self.repository.list_class_levels(self.character_id),
                definitions,
                archetypes_by_level,
                selected_archetype_definitions,
                {
                    class_level.id: archetype_choice_selections_from_records(
                        self.repository.list_class_feature_selections(self.character_id),
                        class_level.id,
                    )
                    for class_level in (classes or self.repository.list_class_levels(self.character_id))
                },
            )
        )
        if automatic is None:
            return
        casting_levels, caster_level, _source = automatic
        profile = self.repository.get_casting_profile(self.character_id)
        updated = replace(
            profile,
            caster_level=caster_level,
            casting_class_levels=(casting_levels if self._class_capabilities.magic else profile.casting_class_levels),
        )
        if updated != profile:
            self.repository.update_casting_profile(updated)

    def _current_prodigy_level(self) -> int:
        if self.character_id is None:
            return 0
        return prodigy_level(self.repository.list_class_levels(self.character_id))

    def _prodigy_sequence_bonus(self) -> int:
        return prodigy_inspired_sequence_bonus(
            self._current_prodigy_level(), self._sequence_links, self._sequence_active
        )

    def _sync_prodigy_class_rules(self, classes=None) -> None:
        if self.character_id is None:
            return
        classes = classes or self.repository.list_class_levels(self.character_id)
        level = prodigy_level(classes)
        self.prodigy_section.setVisible(level > 0)
        self.prodigy_imbue_section.setVisible(level > 0)
        if level <= 0:
            return

        sequence = self.repository.get_prodigy_sequence(self.character_id)
        maximum = prodigy_sequence_maximum(level)
        if sequence.maximum != maximum:
            self.repository.update_prodigy_sequence(
                ProdigySequence(
                    self.character_id,
                    sequence.active,
                    min(sequence.current, maximum) if sequence.active else 0,
                    maximum,
                    sequence.imbue_key,
                )
            )

        profile = self.repository.get_casting_profile(self.character_id)
        ability = (
            profile.casting_ability
            if profile.casting_ability in {"intelligence", "wisdom", "charisma"}
            else "charisma"
        )
        first_integration = (
            profile.casting_class_levels == 0
            and profile.caster_level == 0
            and not profile.auto_spell_points
        )
        updated = replace(
            profile,
            casting_ability=ability,
            casting_class_levels=level,
            caster_level=prodigy_caster_level(level),
            auto_spell_points=(True if first_integration else profile.auto_spell_points),
        )
        if first_integration and profile.spell_points_current == 0:
            cam = self._ability_result(ability).ability_modifier
            maximum_points = calculate_casting_statistics(
                updated,
                cam,
                spell_point_sources=self._calculator().spell_point_contributions(),
            ).spell_points_maximum
            updated = replace(updated, spell_points_current=maximum_points)
        if updated != profile:
            self.repository.update_casting_profile(updated)

        self._update_prodigy_class_summary(level, maximum)
        adaptations = prodigy_adaptation_uses(level)
        adaptation_text = f"{adaptations}/day" if adaptations else "unavailable before level 2"
        self.prodigy_feature_summary.setText(
            f"Blended Training: {prodigy_blended_talents(level)} class talents + 2 starting magic talents"
            f"  •  Adaptation: {adaptation_text}  •  Inspired Sequence automatically modifies attacks, damage, and caster level"
        )

    def _update_prodigy_class_summary(
        self, level: int | None = None, maximum: int | None = None
    ) -> None:
        level = self._current_prodigy_level() if level is None else level
        if level <= 0:
            self.prodigy_class_summary.setText("PRODIGY CLASS NOT ADDED")
            return
        maximum = self.sequence_maximum.value() if maximum is None else maximum
        effective_caster_level = prodigy_caster_level(level) + self._prodigy_sequence_bonus()
        self.prodigy_class_summary.setText(
            f"PRODIGY {level}  •  MID-CASTER CL {effective_caster_level}  •  "
            f"SEQUENCE {maximum} LINKS"
        )

    def _add_class(self) -> None:
        if self.character_id is None:
            return
        dialog = ClassLevelDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            class_level_id = self.repository.add_class_level(self.character_id, **dialog.values)
            self.repository.set_class_archetype_keys(
                self.character_id, class_level_id, dialog.archetype_keys
            )
            self._save_optional_archetype_exchanges(
                class_level_id,
                dialog.archetype_keys,
                dialog.selected_optional_feature_keys,
                int(dialog.values["level"]),
            )
            self._save_archetype_choices(
                class_level_id,
                dialog.archetype_keys,
                getattr(dialog, "archetype_choice_values", {}),
                int(dialog.values["level"]),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add class", str(error))
            return
        self.refresh_all()
        self.formula_values_changed.emit()

    def _selected_class(self):
        if self.character_id is None or self.class_table.currentRow() < 0:
            return None
        class_id = self.class_table.item(self.class_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return next(
            item
            for item in self.repository.list_class_levels(self.character_id)
            if item.id == class_id
        )

    def _edit_class(self, *_args) -> None:
        class_level = self._selected_class()
        if class_level is None or self.character_id is None:
            QMessageBox.information(self, "Select a class", "Select a class row first.")
            return
        self._edit_class_with_dialog(class_level, False)

    def _level_up_class(self) -> None:
        class_level = self._selected_class()
        if class_level is None or self.character_id is None:
            QMessageBox.information(self, "Select a class", "Select a class row first.")
            return
        if class_level.level >= 20:
            QMessageBox.information(self, "Maximum level", "This class is already level 20.")
            return
        before = {
            feature.key
            for feature in self._resolved_features_by_class().get(class_level.id, ())
        }
        previous_level = class_level.level
        if not self._edit_class_with_dialog(class_level, True):
            return
        updated = next(
            item
            for item in self.repository.list_class_levels(self.character_id)
            if item.id == class_level.id
        )
        resolved = self._resolved_features_by_class().get(class_level.id, ())
        gained = tuple(feature.name for feature in resolved if feature.key not in before)
        self._open_level_up_review(
            f"{updated.class_name} advanced from level {previous_level} to level {updated.level}.",
            gained,
        )

    def _review_advancement(self) -> None:
        if self.character_id is None:
            return
        self._open_level_up_review(
            "Review all current advancement budgets and unresolved character choices.",
            (),
        )

    def _open_level_up_review(
        self, summary: str, gained_features: tuple[str, ...]
    ) -> None:
        if self.character_id is None:
            return
        current = self._level_up_dialog
        if current is not None and current.isVisible():
            current.refresh()
            current.raise_()
            current.activateWindow()
            return
        def choose_talent() -> None:
            if self._class_capabilities.magic and not self._class_capabilities.martial:
                self._add_spell()
            else:
                self._add_martial_talent()

        def direct(resolver_key: str, label: str) -> LevelUpAction:
            return LevelUpAction(
                label,
                lambda finding, remedy, key=resolver_key:
                self._resolve_audit_interactive(key, finding, remedy),
            )

        actions = {
            "advancement-choice": direct("advancement-choice", "Resolve allocation"),
            "advancement-overage": direct("advancement-overage", "Adjust allocation"),
            "favored-class": direct("favored-class", "Edit allocation"),
            "race-choice": direct("race-choice", "Configure race"),
            "class-choice": direct("class-choice", "Choose options"),
            "archetype-choice": direct("archetype-choice", "Edit archetype choices"),
            "class-power": direct("class-power", "Choose powers"),
            "magic-sphere-choice": direct("magic-sphere-choice", "Choose sphere option"),
            "martial-sphere-choice": direct("martial-sphere-choice", "Choose sphere option"),
            "prepared-overage": direct("prepared-overage", "Edit prepared quantities"),
            "formula": direct("formula", "Edit formula"),
            "feat-choice": direct("feat-choice", "Choose feat option"),
            "invalid-selection": direct("invalid-selection", "Choose remedy"),
            "invalid-class-power": direct("invalid-class-power", "Resolve power"),
            "favored_class": LevelUpAction(
                "Open Page 0",
                lambda: self._focus_advancement_section(
                    self.builder_scroll, self.favored_class_bonus_section
                ),
                True,
            ),
            "ability_score_increases": LevelUpAction(
                "Allocate",
                lambda: self._focus_advancement_section(
                    self.builder_scroll, self.ability_score_increase_section
                ),
                True,
            ),
            "skills": LevelUpAction(
                "Open skills",
                lambda: self._focus_advancement_section(
                    self.core_scroll, self.skills_section
                ),
                True,
            ),
            "feats": LevelUpAction("Choose feat", self._add_feat),
            "talents": LevelUpAction("Choose talent", choose_talent),
            "martial_talents": LevelUpAction(
                "Martial talent", self._add_martial_talent
            ),
            "magic_talents": LevelUpAction("Magic talent", self._add_spell),
            "spells": LevelUpAction("Choose spell", self._add_traditional_spell),
            "spells_prepared": LevelUpAction(
                "Review prepared spells",
                lambda: self._focus_advancement_section(
                    self.magic_scroll, self.spells_prepared_section
                ),
                True,
            ),
            "advancement": LevelUpAction(
                "Review budgets",
                lambda: self._focus_advancement_section(
                    self.builder_scroll, self.advancement_budget_section
                ),
                True,
            ),
            "casting_profile": LevelUpAction(
                "Review casting",
                lambda: self._focus_advancement_section(
                    self.builder_scroll, self.casting_profile_section
                ),
                True,
            ),
            "hit_points": LevelUpAction(
                "Review HP",
                lambda: self._focus_advancement_section(
                    self.core_scroll, self.classic_statistics_section
                ),
                True,
            ),
            "martial_focus": LevelUpAction(
                "Review focus",
                lambda: self._focus_advancement_section(
                    self.core_scroll, self.martial_focus_section
                ),
                True,
            ),
            "prodigy_sequence": LevelUpAction(
                "Review Sequence",
                lambda: self._focus_advancement_section(
                    self.core_scroll, self.prodigy_section
                ),
                True,
            ),
            "formulas": LevelUpAction(
                "Open build page",
                lambda: self.page_tabs.setCurrentWidget(self.builder_scroll),
                True,
            ),
            "class_choices": LevelUpAction(
                "Review features",
                lambda: self._focus_advancement_section(
                    self.core_scroll, self.inquisitor_features_section
                ),
                True,
            ),
        }
        dialog = GuidedLevelUpDialog(
            self.repository,
            self.character_id,
            summary=summary,
            gained_features=gained_features,
            actions=actions,
            parent=self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.audit_changed.connect(self._refresh_audit_status_from_dialog)
        dialog.resolution_applied.connect(self._refresh_after_audit_resolution)
        dialog.finished.connect(lambda *_args: self._refresh_character_audit())
        dialog.destroyed.connect(
            lambda *_args: setattr(self, "_level_up_dialog", None)
        )
        self._level_up_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _resolve_audit_interactive(self, resolver_key, finding, remedy_key):
        """Route one structured finding to its exact existing editor."""

        if self.character_id is None:
            return AuditResolutionOutcome(False, "No character is open.")
        subject = finding.subject
        if resolver_key == "advancement-choice":
            if subject.key == "feats":
                before = {item.id for item in self.repository.list_feats(self.character_id)}
                self._add_feat()
                return self._audit_addition_outcome("feat", before)
            if subject.key == "talents":
                choose_magic = self._class_capabilities.magic and not self._class_capabilities.martial
                if self._class_capabilities.magic and self._class_capabilities.martial:
                    selected, accepted = QInputDialog.getItem(
                        self,
                        "Resolve talent allocation",
                        "Which talent allowance do you want to spend?",
                        ("Martial talent", "Magic talent"),
                        0,
                        False,
                    )
                    if not accepted:
                        return AuditResolutionOutcome(False)
                    choose_magic = selected == "Magic talent"
                if choose_magic:
                    before = {item.id for item in self.repository.list_spells(self.character_id)}
                    self._add_spell(sphere_only=True)
                    return self._audit_addition_outcome("spell", before)
                before = {item.id for item in self.repository.list_martial_talents(self.character_id)}
                self._add_martial_talent()
                return self._audit_addition_outcome("martial-talent", before)
            if subject.key == "spells":
                before = {item.id for item in self.repository.list_spells(self.character_id)}
                self._add_traditional_spell()
                return self._audit_addition_outcome("spell", before)
            if subject.key == "ability_score_increases":
                return self._resolve_audit_ability_increases()
            if subject.key == "skill_points":
                return self._resolve_audit_skill_ranks()
            return AuditResolutionOutcome(False)
        if resolver_key == "advancement-overage":
            if subject.key == "ability_score_increases":
                return self._resolve_audit_ability_increases()
            if subject.key == "skill_points":
                return self._resolve_audit_skill_ranks()
            return self._resolve_audit_acquisition_overage(subject.key)
        if resolver_key == "favored-class":
            return self._resolve_audit_favored_class(subject.class_level_id)
        if resolver_key == "race-choice":
            before = self.repository.get_character_details(self.character_id)
            self._configure_race()
            after = self.repository.get_character_details(self.character_id)
            if after == before:
                return AuditResolutionOutcome(False)

            def restore() -> None:
                self.repository.update_character_details(before)
                self._refresh_identity()

            return AuditResolutionOutcome(
                True, undo=AuditUndoToken("Undo racial choices", restore)
            )
        if resolver_key == "class-choice":
            return self._resolve_audit_class_choice(subject.class_level_id, subject.key)
        if resolver_key == "class-power":
            return self._resolve_audit_class_power(subject.class_level_id, subject.key)
        if resolver_key == "archetype-choice":
            class_level = next(
                (item for item in self.repository.list_class_levels(self.character_id)
                 if item.id == subject.class_level_id), None
            )
            if class_level is None:
                return AuditResolutionOutcome(False, "The affected class level no longer exists.")
            before_class = class_level
            before_archetypes = self.repository.list_class_archetype_keys(
                self.character_id, class_level.id
            ).get(class_level.id, ())
            before_selections = tuple(
                item for item in self.repository.list_class_feature_selections(self.character_id)
                if item.class_level_id == class_level.id
            )
            changed = self._edit_class_with_dialog(
                class_level, False, refresh_after=False
            )
            if not changed:
                return AuditResolutionOutcome(False)

            def restore() -> None:
                self.repository.update_class_level(
                    self.character_id, before_class.id, before_class.class_name,
                    before_class.level, before_class.bab_progression,
                    before_class.fort_progression, before_class.reflex_progression,
                    before_class.will_progression, before_class.preset_key,
                    before_class.hit_die, before_class.hp_gained,
                )
                self.repository.set_class_archetype_keys(
                    self.character_id, before_class.id, before_archetypes
                )
                for item in self.repository.list_class_feature_selections(self.character_id):
                    if item.class_level_id == before_class.id:
                        self.repository.delete_class_feature_selection(
                            self.character_id, before_class.id, item.feature_key
                        )
                for item in before_selections:
                    self.repository.save_class_feature_selection(item)

            return AuditResolutionOutcome(
                True, undo=AuditUndoToken("Undo archetype choices", restore)
            )
        if resolver_key == "magic-sphere-choice":
            spell = next((item for item in self.repository.list_spells(self.character_id) if item.id == subject.record_id), None)
            if spell is None:
                return AuditResolutionOutcome(False, "The affected sphere entry no longer exists.")
            before = self._audit_snapshot_rows(
                "spells", "character_id = ? AND lower(school_or_sphere) = lower(?)",
                (self.character_id, spell.school_or_sphere),
            )
            before_feats = self._audit_snapshot_rows(
                "feats", "character_id = ?", (self.character_id,)
            )
            self._edit_build_drawbacks(sphere_name=spell.school_or_sphere)
            after = self._audit_snapshot_rows(
                "spells", "character_id = ? AND lower(school_or_sphere) = lower(?)",
                (self.character_id, spell.school_or_sphere),
            )
            if before == after:
                return AuditResolutionOutcome(False)

            def restore() -> None:
                self._audit_restore_rows(
                    "spells", "character_id = ? AND lower(school_or_sphere) = lower(?)",
                    (self.character_id, spell.school_or_sphere), before,
                )
                self._audit_restore_rows(
                    "feats", "character_id = ?", (self.character_id,), before_feats,
                )
                self._magic_talents_changed()

            return AuditResolutionOutcome(
                True, undo=AuditUndoToken("Undo sphere choices", restore)
            )
        if resolver_key == "martial-sphere-choice":
            talent = next((item for item in self.repository.list_martial_talents(self.character_id) if item.id == subject.record_id), None)
            if talent is None:
                return AuditResolutionOutcome(False, "The affected sphere entry no longer exists.")
            self._refresh_sphere_build()
            self._select_table_identity(self.martial_sphere_build_table, talent.sphere)
            before = self._audit_snapshot_rows(
                "martial_talents", "character_id = ? AND lower(sphere) = lower(?)",
                (self.character_id, talent.sphere),
            )
            self._edit_martial_build_drawbacks()
            after = self._audit_snapshot_rows(
                "martial_talents", "character_id = ? AND lower(sphere) = lower(?)",
                (self.character_id, talent.sphere),
            )
            if before == after:
                return AuditResolutionOutcome(False)

            def restore() -> None:
                self._audit_restore_rows(
                    "martial_talents", "character_id = ? AND lower(sphere) = lower(?)",
                    (self.character_id, talent.sphere), before,
                )
                self._martial_talents_changed()

            return AuditResolutionOutcome(
                True, undo=AuditUndoToken("Undo sphere choices", restore)
            )
        if resolver_key == "prepared-overage":
            return self._resolve_audit_prepared_overage(
                subject.class_level_id, subject.level
            )
        if resolver_key == "formula":
            return self._resolve_audit_formula(subject)
        if resolver_key == "feat-choice":
            return self._resolve_audit_feat_choice(subject.record_id)
        if resolver_key == "invalid-selection":
            return self._resolve_audit_invalid_selection(finding, remedy_key)
        if resolver_key == "invalid-class-power":
            return self._resolve_audit_invalid_class_power(finding, remedy_key)
        return AuditResolutionOutcome(False, "No interactive handler is available for this issue.")

    @staticmethod
    def _select_table_identity(table: QTableWidget, identity) -> bool:
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == identity:
                    table.setCurrentCell(row, column)
                    table.scrollToItem(item)
                    return True
        return False

    def _audit_addition_outcome(self, kind: str, before_ids: set[int]):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        if kind == "feat":
            records = self.repository.list_feats(self.character_id)
            delete = lambda record_id: self.repository.delete_feat(self.character_id, record_id)
            changed = self._feats_changed
        elif kind == "martial-talent":
            records = self.repository.list_martial_talents(self.character_id)
            delete = lambda record_id: self.repository.delete_martial_talent(self.character_id, record_id)
            changed = self._martial_talents_changed
        else:
            records = self.repository.list_spells(self.character_id)
            delete = lambda record_id: self.repository.delete_spell(self.character_id, record_id)
            changed = self._magic_talents_changed
        created = tuple(item.id for item in records if item.id not in before_ids)
        if not created:
            return AuditResolutionOutcome(False)

        def restore() -> None:
            for record_id in reversed(created):
                delete(record_id)
            changed()

        return AuditResolutionOutcome(
            True,
            f"Added {len(created)} selection(s).",
            AuditUndoToken("Undo audit addition", restore),
        )

    def _audit_snapshot_rows(self, table: str, where: str, parameters: tuple):
        return tuple(
            dict(row) for row in self.repository.sqlite_connection.execute(
                f"SELECT * FROM {table} WHERE {where} ORDER BY rowid", parameters
            ).fetchall()
        )

    def _audit_restore_rows(
        self, table: str, where: str, parameters: tuple, rows: tuple[dict, ...]
    ) -> None:
        connection = self.repository.sqlite_connection
        connection.execute(f"DELETE FROM {table} WHERE {where}", parameters)
        for row in rows:
            columns = tuple(row)
            connection.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
        connection.commit()

    def _resolve_audit_favored_class(self, class_level_id: int):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        class_level = next(
            (item for item in self.repository.list_class_levels(self.character_id)
             if item.id == class_level_id), None
        )
        if class_level is None:
            return AuditResolutionOutcome(False, "The affected class level no longer exists.")
        before = self.repository.list_favored_class_bonuses(self.character_id).get(
            class_level_id, FavoredClassBonus(self.character_id, class_level_id)
        )
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Favored class bonus — {class_level.class_name}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Allocate {class_level.level} favored-class bonus choices."))
        form = QFormLayout()
        controls = []
        for label, value in (
            ("Hit points", before.hp_bonus),
            ("Skill points", before.skill_point_bonus),
            ("Manual options", before.manual_bonus),
        ):
            control = QSpinBox(); control.setRange(0, class_level.level); control.setValue(value)
            form.addRow(label, control); controls.append(control)
        manual_code = QLineEdit(before.manual_code)
        form.addRow("Manual option notes", manual_code)
        layout.addLayout(form)
        status = QLabel(); status.setObjectName("mutedText"); layout.addWidget(status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        ); layout.addWidget(buttons)

        def update_status() -> None:
            total = sum(control.value() for control in controls)
            status.setText(f"Allocated {total} of {class_level.level}.")
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(total <= class_level.level)

        for control in controls:
            control.valueChanged.connect(update_status)
        update_status(); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        after = FavoredClassBonus(
            self.character_id, class_level_id,
            controls[0].value(), controls[1].value(), controls[2].value(), manual_code.text(),
        )
        if after == before:
            return AuditResolutionOutcome(False)
        self.repository.update_favored_class_bonus(after)
        return AuditResolutionOutcome(
            True,
            undo=AuditUndoToken(
                "Undo favored-class allocation",
                lambda: self.repository.update_favored_class_bonus(before),
            ),
        )

    def _resolve_audit_ability_increases(self):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        before = self.repository.list_ability_score_increases(self.character_id)
        allowance = sum(item.level for item in self.repository.list_class_levels(self.character_id)) // 4
        dialog = QDialog(self); dialog.setWindowTitle("Allocate ability-score increases")
        layout = QVBoxLayout(dialog); form = QFormLayout(); controls = {}
        for key, label, _short in ABILITIES:
            control = QSpinBox(); control.setRange(0, allowance)
            control.setValue(before.get(key, AbilityScoreIncreaseAllocation(self.character_id, key)).points)
            form.addRow(label, control); controls[key] = control
        layout.addLayout(form)
        status = QLabel(); status.setObjectName("mutedText"); layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def update_status() -> None:
            total = sum(control.value() for control in controls.values())
            status.setText(f"Allocated {total} of {allowance}.")
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(total <= allowance)

        for control in controls.values(): control.valueChanged.connect(update_status)
        update_status(); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        after = {key: control.value() for key, control in controls.items()}
        if all(before.get(key, AbilityScoreIncreaseAllocation(self.character_id, key)).points == value for key, value in after.items()):
            return AuditResolutionOutcome(False)
        for key, value in after.items():
            self.repository.update_ability_score_increase(
                AbilityScoreIncreaseAllocation(self.character_id, key, value)
            )

        def restore() -> None:
            for key in controls:
                self.repository.update_ability_score_increase(
                    before.get(key, AbilityScoreIncreaseAllocation(self.character_id, key))
                )

        return AuditResolutionOutcome(True, undo=AuditUndoToken("Undo ability allocation", restore))

    def _resolve_audit_skill_ranks(self):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        definitions = character_skill_definitions(self.repository, self.character_id)
        before = self.repository.list_skill_states(self.character_id)
        budget = next(
            (item for item in character_advancement_budgets(self.repository, self.character_id)
             if item.key == "skill_points"), None
        )
        maximum = budget.total if budget is not None else sum(item.ranks for item in before.values())
        dialog = QDialog(self); dialog.setWindowTitle("Allocate skill ranks"); dialog.resize(620, 760)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(definitions), 3); table.setHorizontalHeaderLabels(("Skill", "Ability", "Ranks"))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        controls = {}
        for row, definition in enumerate(definitions):
            state = before[definition.key]
            table.setItem(row, 0, QTableWidgetItem(definition.name))
            table.setItem(row, 1, QTableWidgetItem((state.ability_override or definition.ability).upper()))
            control = QSpinBox(); control.setRange(0, 99); control.setValue(state.ranks)
            table.setCellWidget(row, 2, control); controls[definition.key] = control
        layout.addWidget(table, 1)
        status = QLabel(); status.setObjectName("mutedText"); layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def update_status() -> None:
            total = sum(control.value() for control in controls.values())
            status.setText(f"Purchased ranks {total} of {maximum}.")
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(total <= maximum)

        for control in controls.values(): control.valueChanged.connect(update_status)
        update_status(); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        changed_keys = tuple(key for key, control in controls.items() if control.value() != before[key].ranks)
        if not changed_keys:
            return AuditResolutionOutcome(False)
        for key in changed_keys:
            self.repository.update_skill_state(
                self.character_id, replace(before[key], ranks=controls[key].value())
            )

        def restore() -> None:
            for key in changed_keys:
                self.repository.update_skill_state(self.character_id, before[key])

        return AuditResolutionOutcome(True, undo=AuditUndoToken("Undo skill allocation", restore))

    def _resolve_audit_prepared_overage(self, class_level_id: int, spell_level: int):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        records = tuple(
            item for item in self.repository.list_prepared_spells(self.character_id)
            if item.class_level_id == class_level_id and item.level == spell_level
        )
        caster = next(
            (item for item in self._prepared_caster_capacities() if item.class_level_id == class_level_id), None
        )
        if not records or caster is None:
            return AuditResolutionOutcome(False, "The affected prepared-spell group no longer exists.")
        capacity = caster.slots[spell_level] if 0 <= spell_level < len(caster.slots) else 0
        before = self._audit_snapshot_rows(
            "prepared_spells", "character_id = ? AND class_level_id = ? AND level = ?",
            (self.character_id, class_level_id, spell_level),
        )
        dialog = QDialog(self); dialog.setWindowTitle(f"Prepared level {spell_level} spells — {caster.class_name}")
        layout = QVBoxLayout(dialog); form = QFormLayout(); controls = {}
        for record in records:
            control = QSpinBox(); control.setRange(0, 999); control.setValue(record.prepared_count)
            form.addRow(record.name, control); controls[record.id] = control
        layout.addLayout(form)
        status = QLabel(); status.setObjectName("mutedText"); layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def update_status() -> None:
            total = sum(control.value() for control in controls.values())
            status.setText(f"Prepared {total} of {capacity} available slots. Zero removes an entry.")
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(total <= capacity)

        for control in controls.values(): control.valueChanged.connect(update_status)
        update_status(); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        if all(controls[item.id].value() == item.prepared_count for item in records):
            return AuditResolutionOutcome(False)
        for record in records:
            value = controls[record.id].value()
            if value <= 0:
                self.repository.delete_prepared_spell(self.character_id, record.id)
            else:
                self.repository.update_prepared_spell_counts(
                    self.character_id, record.id, value, min(record.used_count, value)
                )
        self._refresh_spells()

        def restore() -> None:
            self._audit_restore_rows(
                "prepared_spells", "character_id = ? AND class_level_id = ? AND level = ?",
                (self.character_id, class_level_id, spell_level), before,
            )
            self._refresh_spells()

        return AuditResolutionOutcome(True, undo=AuditUndoToken("Undo prepared spells", restore))

    def _resolve_audit_acquisition_overage(self, budget_key: str):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        budget = next(
            (item for item in character_advancement_budgets(self.repository, self.character_id)
             if item.key == budget_key), None
        )
        if budget is None or budget.remaining >= 0:
            return AuditResolutionOutcome(False, "This advancement budget is no longer overspent.")
        required = abs(budget.remaining)
        if budget_key == "feats":
            candidates = tuple(
                ("feat", item.id, item.name, True)
                for item in self.repository.list_feats(self.character_id)
            )
        elif budget_key == "talents":
            candidates = tuple(
                (
                    "martial",
                    item.id,
                    f"{item.name} · {item.sphere}",
                    item.catalog_category != "Base Sphere",
                )
                for item in self.repository.list_martial_talents(self.character_id)
                if item.catalog_category not in {"Drawback", "Tradition"}
            ) + tuple(
                (
                    "magic",
                    item.id,
                    f"{item.name} · {item.school_or_sphere}",
                    item.catalog_category != "Base Sphere",
                )
                for item in self.repository.list_spells(self.character_id)
                if item.system == "Sphere" and item.catalog_category != "Drawback"
            )
        elif budget_key == "spells":
            candidates = tuple(
                ("spell", item.id, f"Level {item.level} · {item.name}", True)
                for item in self.repository.list_spells(self.character_id)
                if item.system != "Sphere" and item.catalog_category != "Base Sphere"
            )
        else:
            self._focus_advancement_section(self.builder_scroll, self.advancement_budget_section)
            return AuditResolutionOutcome(False)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Adjust {budget.name}")
        dialog.resize(760, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            f"This budget is overspent by {required}. Choose what to keep, remove, or replace. "
            "At least that many entries must be removed; replacements preserve a slot and do not reduce the overage."
        ))
        choices = QTableWidget(len(candidates), 3)
        choices.setHorizontalHeaderLabels(("Selection", "Kind", "Action"))
        choices.verticalHeader().setVisible(False)
        choices.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        choices.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        choices.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        choices.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        choices.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        action_controls: list[QComboBox] = []
        labels_by_identity: dict[tuple[str, int], str] = {}
        kind_labels = {
            "feat": "Feat",
            "martial": "Martial talent",
            "magic": "Magic talent",
            "spell": "Spell",
        }
        for row, (kind, record_id, label, replaceable) in enumerate(candidates):
            identity = (kind, record_id)
            labels_by_identity[identity] = label
            name_item = QTableWidgetItem(label)
            name_item.setData(Qt.ItemDataRole.UserRole, identity)
            choices.setItem(row, 0, name_item)
            choices.setItem(row, 1, QTableWidgetItem(kind_labels[kind]))
            action = QComboBox()
            action.addItem("Keep", "keep")
            action.addItem("Remove", "remove")
            if replaceable:
                action.addItem("Replace…", "replace")
            else:
                action.setToolTip(
                    "Base spheres can be removed, but replacement is handled by "
                    "choosing a new base sphere afterward so cascade rules remain exact."
                )
            choices.setCellWidget(row, 2, action)
            action_controls.append(action)
        layout.addWidget(choices, 1)
        status = QLabel()
        status.setObjectName("mutedText")
        layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def selected_actions(action_key: str):
            return tuple(
                choices.item(row, 0).data(Qt.ItemDataRole.UserRole)
                for row, control in enumerate(action_controls)
                if control.currentData() == action_key
            )

        def update_status(*_args) -> None:
            removals = len(selected_actions("remove"))
            replacements = len(selected_actions("replace"))
            status.setText(
                f"Remove {removals} · Replace {replacements} · "
                f"at least {required} removal{'s' if required != 1 else ''} required."
            )
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
                removals >= required
            )

        for control in action_controls:
            control.currentIndexChanged.connect(update_status)
        update_status()
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        removals = selected_actions("remove")
        replacements = selected_actions("replace")
        if len(removals) < required:
            return AuditResolutionOutcome(False)
        preview_lines = [
            *(f"Remove: {labels_by_identity[item]}" for item in removals),
            *(f"Replace: {labels_by_identity[item]}" for item in replacements),
        ]
        if QMessageBox.question(
            self,
            "Confirm advancement adjustment",
            "Apply these changes?\n\n" + "\n".join(preview_lines),
        ) != QMessageBox.StandardButton.Yes:
            return AuditResolutionOutcome(False)
        snapshots = {
            table: self._audit_snapshot_rows(table, "character_id = ?", (self.character_id,))
            for table in ("feats", "martial_talents", "spells", "prepared_spells", "numeric_formulas")
        }

        def restore() -> None:
            # Delete dependents before their referenced spell rows, then restore
            # parents before dependents to satisfy SQLite foreign keys.
            for table in ("prepared_spells", "numeric_formulas", "spells", "martial_talents", "feats"):
                self.repository.sqlite_connection.execute(
                    f"DELETE FROM {table} WHERE character_id = ?", (self.character_id,)
                )
            for table in ("feats", "martial_talents", "spells", "prepared_spells", "numeric_formulas"):
                for row in snapshots[table]:
                    columns = tuple(row)
                    self.repository.sqlite_connection.execute(
                        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                        tuple(row[column] for column in columns),
                    )
            self.repository.sqlite_connection.commit()

        def record_ids(kind: str) -> set[int]:
            if kind == "feat":
                return {item.id for item in self.repository.list_feats(self.character_id)}
            if kind == "martial":
                return {item.id for item in self.repository.list_martial_talents(self.character_id)}
            return {item.id for item in self.repository.list_spells(self.character_id)}

        def choose_replacement(kind: str) -> bool:
            before_ids = record_ids(kind)
            if kind == "feat":
                self._add_feat(selection_limit=1)
            elif kind == "martial":
                self._add_martial_talent(selection_limit=1)
            elif kind == "magic":
                self._add_spell(selection_limit=1, sphere_only=True)
            else:
                self._add_traditional_spell(selection_limit=1)
            return bool(record_ids(kind) - before_ids)

        # Every replacement picker must succeed before any original entry is
        # deleted.  If a later picker is cancelled, restore the exact snapshot
        # so the operation creates neither a partial change nor an undo entry.
        for kind, _record_id in replacements:
            if not choose_replacement(kind):
                restore()
                self.refresh_all()
                return AuditResolutionOutcome(
                    False, "No changes were applied because replacement was cancelled."
                )

        for kind, record_id in (*replacements, *removals):
            if kind == "feat":
                self.repository.delete_feat(self.character_id, record_id)
            elif kind == "martial":
                item = next((value for value in self.repository.list_martial_talents(self.character_id) if value.id == record_id), None)
                if item is not None:
                    if item.catalog_category == "Base Sphere": self._delete_martial_sphere_cascade(item.sphere)
                    else: self.repository.delete_martial_talent(self.character_id, item.id)
            else:
                item = next((value for value in self.repository.list_spells(self.character_id) if value.id == record_id), None)
                if item is not None:
                    if item.catalog_category == "Base Sphere": self._delete_magic_sphere_cascade(item.school_or_sphere)
                    else: self.repository.delete_spell(self.character_id, item.id)
        return AuditResolutionOutcome(
            True,
            f"Removed {len(removals)} and replaced {len(replacements)} selection(s).",
            AuditUndoToken(f"Undo {budget.name.lower()} adjustment", restore),
        )

    def _resolve_audit_class_choice(self, class_level_id: int, provider_key: str):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        slot = next(
            (item for item in resolve_class_choice_slots(self.repository, self.character_id)
             if item.class_level_id == class_level_id and item.key == provider_key), None
        )
        if slot is None:
            return AuditResolutionOutcome(False, "The affected class choice no longer exists.")
        feature_keys = {slot.feature_key, *slot.legacy_feature_keys}
        before = tuple(
            item for item in self.repository.list_class_feature_selections(self.character_id)
            if item.class_level_id == class_level_id and item.feature_key in feature_keys
        )
        dialog = ClassChoiceDialog(slot, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character_id, slot, dialog.selected_keys)
        )
        for legacy_key in slot.legacy_feature_keys:
            self.repository.delete_class_feature_selection(self.character_id, class_level_id, legacy_key)
        self._class_feature_choice_changed()

        def restore() -> None:
            for key in feature_keys:
                self.repository.delete_class_feature_selection(self.character_id, class_level_id, key)
            for item in before:
                self.repository.save_class_feature_selection(item)
            self._class_feature_choice_changed()

        return AuditResolutionOutcome(True, undo=AuditUndoToken("Undo class choice", restore))

    def _resolve_audit_class_power(self, class_level_id: int, provider_key: str):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        power_set = next(
            (item for item in resolve_class_power_sets(self.repository, self.character_id)
             if item.class_level_id == class_level_id and item.key == provider_key), None
        )
        if power_set is None:
            return AuditResolutionOutcome(False, "The affected class-power set no longer exists.")
        before_selection = next(
            (item for item in self.repository.list_class_feature_selections(self.character_id)
             if item.class_level_id == class_level_id and item.feature_key == power_set.feature_key), None
        )
        affected_option_keys = {
            option.key for option in power_set.options
        }
        before_states = tuple(
            item for item in self.repository.list_class_feature_states(self.character_id)
            if item.class_level_id == class_level_id
            and item.feature_key in {
                class_power_active_feature_key(key) for key in affected_option_keys
            }
        )
        dialog = ClassPowerDialog(power_set, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        try:
            application = apply_class_power_selection(
                self.repository, self.character_id, power_set, dialog.selected_keys
            )
        except ValueError as error:
            return AuditResolutionOutcome(False, str(error))
        updated = next(
            (item for item in resolve_class_power_sets(self.repository, self.character_id)
             if item.class_level_id == class_level_id and item.key == provider_key), None
        )
        if updated is not None:
            desired_active = set(dialog.active_keys)
            for option_key in set(power_set.active_keys) | desired_active:
                self.repository.save_class_feature_state(
                    class_power_activation_record(
                        self.character_id, updated, option_key, option_key in desired_active
                    )
                )
        self._class_power_changed()

        def restore() -> None:
            self.repository.delete_class_feature_selection(
                self.character_id, class_level_id, power_set.feature_key
            )
            if before_selection is not None:
                self.repository.save_class_feature_selection(before_selection)
            current_states = self.repository.list_class_feature_states(self.character_id)
            for item in current_states:
                if (
                    item.class_level_id == class_level_id
                    and item.feature_key in {
                        class_power_active_feature_key(key)
                        for key in affected_option_keys
                    }
                ):
                    self.repository.delete_class_feature_state(
                        self.character_id, class_level_id, item.feature_key
                    )
            for item in before_states:
                self.repository.save_class_feature_state(item)
            if application.resource_before is not None:
                self.repository.save_class_feature_state(application.resource_before)
            self._class_power_changed()

        return AuditResolutionOutcome(True, undo=AuditUndoToken("Undo class powers", restore))

    def _resolve_audit_formula(self, subject):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        before = self.repository.numeric_formulas(self.character_id).get(
            (subject.key, subject.record_id, subject.field), ""
        )
        dialog = QDialog(self)
        dialog.setWindowTitle("Repair formula")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{subject.key} · {subject.field}"))
        editor = FormulaLineEdit(
            suggestion_provider=self._character_formula_suggestions,
            require_equals=True,
        )
        editor.setText(before)
        layout.addWidget(editor)
        error_label = QLabel()
        error_label.setObjectName("warningText")
        layout.addWidget(error_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)

        def update_validation() -> bool:
            expression = editor.text().strip()
            try:
                if expression:
                    self._evaluate_character_formula(expression)
            except (FormulaError, ArithmeticError, ValueError) as error:
                error_label.setText(str(error))
                buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
                return False
            error_label.setText("Formula is valid." if expression else "The saved formula will be removed.")
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            return True

        def validate() -> None:
            if not update_validation():
                return
            dialog.accept()

        editor.textChanged.connect(update_validation)
        update_validation()
        buttons.accepted.connect(validate)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        expression = editor.text().strip()
        if expression == before:
            return AuditResolutionOutcome(False)
        self.repository.set_numeric_formula(
            self.character_id, subject.key, subject.record_id, subject.field, expression
        )

        def restore() -> None:
            self.repository.set_numeric_formula(
                self.character_id, subject.key, subject.record_id, subject.field, before
            )

        return AuditResolutionOutcome(True, undo=AuditUndoToken("Undo formula repair", restore))

    def _resolve_audit_feat_choice(self, feat_id: int):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        feat = next(
            (item for item in self.repository.list_feats(self.character_id) if item.id == feat_id),
            None,
        )
        entry = feat_entry(feat.catalog_key) if feat is not None and feat.catalog_key else None
        automation = dict(entry.get("automation", {})) if entry else {}
        choice_type = str(automation.get("choice_type") or "")
        if feat is None or not choice_type:
            return AuditResolutionOutcome(False, "The affected feat choice no longer exists.")
        dialog = FeatChoiceDialog(
            choice_type,
            str(automation.get("choice_label") or "Choice"),
            self.repository.list_attacks(self.character_id),
            self.repository.list_equipment(self.character_id),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return AuditResolutionOutcome(False)
        effects = []
        for source in automation.get("effects", ()):
            effect = dict(source)
            effect["target"] = str(effect.get("target", "")).replace(
                "{choice_key}", dialog.choice_key
            )
            effect["scope"] = str(effect.get("scope", "")).replace(
                "{choice_key}", dialog.choice_key
            )
            effects.append(effect)

        def save(record, *, choice=None, resolved_effects=None) -> None:
            self.repository.update_feat(
                self.character_id,
                record.id,
                record.name,
                record.target,
                record.bonus_type,
                record.value,
                record.notes,
                record.catalog_key,
                record.catalog_category,
                record.prerequisites,
                record.source_url,
                record.choice if choice is None else choice,
                record.effects if resolved_effects is None else resolved_effects,
                record.repeatable,
                record.activation,
                record.activation_note,
            )

        save(feat, choice=dialog.choice, resolved_effects=effects)
        self._feats_changed()
        return AuditResolutionOutcome(
            True,
            undo=AuditUndoToken(
                "Undo feat choice",
                lambda: (save(feat), self._feats_changed()),
            ),
        )

    def _resolve_audit_invalid_selection(self, finding, remedy_key: str):
        if self.character_id is None:
            return AuditResolutionOutcome(False)
        subject = finding.subject
        if subject.kind == "magic-talent":
            records = self.repository.list_spells(self.character_id)
            record = next((item for item in records if item.id == subject.record_id), None)
            set_enabled = lambda value: self.repository.set_spell_enabled(self.character_id, record.id, value)
            delete = lambda: self.repository.delete_spell(self.character_id, record.id)
            add = lambda: self._add_spell(selection_limit=1, sphere_only=True)
            current_ids = lambda: {item.id for item in self.repository.list_spells(self.character_id)}
            changed = self._magic_talents_changed
            table = "spells"
        elif subject.kind == "martial-talent":
            records = self.repository.list_martial_talents(self.character_id)
            record = next((item for item in records if item.id == subject.record_id), None)
            set_enabled = lambda value: self.repository.set_martial_talent_enabled(self.character_id, record.id, value)
            delete = lambda: self.repository.delete_martial_talent(self.character_id, record.id)
            add = lambda: self._add_martial_talent(selection_limit=1)
            current_ids = lambda: {item.id for item in self.repository.list_martial_talents(self.character_id)}
            changed = self._martial_talents_changed
            table = "martial_talents"
        elif subject.kind == "feat":
            records = self.repository.list_feats(self.character_id)
            record = next((item for item in records if item.id == subject.record_id), None)
            set_enabled = lambda value: self.repository.set_feat_enabled(
                self.character_id, record.id, value
            )
            delete = lambda: self.repository.delete_feat(self.character_id, record.id)
            add = lambda: self._add_feat(selection_limit=1)
            current_ids = lambda: {
                item.id for item in self.repository.list_feats(self.character_id)
            }
            changed = self._feats_changed
            table = "feats"
        elif subject.kind in {"spell", "traditional-spell"}:
            records = self.repository.list_spells(self.character_id)
            record = next((item for item in records if item.id == subject.record_id), None)
            set_enabled = lambda value: self.repository.set_spell_enabled(
                self.character_id, record.id, value
            )
            delete = lambda: self.repository.delete_spell(self.character_id, record.id)
            add = lambda: self._add_traditional_spell(selection_limit=1)
            current_ids = lambda: {
                item.id for item in self.repository.list_spells(self.character_id)
            }
            changed = self._magic_talents_changed
            table = "spells"
        else:
            return AuditResolutionOutcome(False, "This selection type has no safe direct remedy.")
        if record is None:
            return AuditResolutionOutcome(False, "The affected selection no longer exists.")
        if remedy_key == "deactivate":
            before_enabled = record.enabled
            set_enabled(False)
            changed()
            return AuditResolutionOutcome(
                True,
                undo=AuditUndoToken(
                    "Undo deactivation",
                    lambda: (set_enabled(before_enabled), changed()),
                ),
            )
        row = dict(self.repository.sqlite_connection.execute(
            f"SELECT * FROM {table} WHERE id = ? AND character_id = ?",
            (record.id, self.character_id),
        ).fetchone())
        before_ids = current_ids()
        if remedy_key == "replace":
            add()
            created = tuple(sorted(current_ids() - before_ids))
            if not created:
                return AuditResolutionOutcome(False)
        else:
            created = ()
        delete()
        changed()

        def restore() -> None:
            connection = self.repository.sqlite_connection
            for record_id in created:
                connection.execute(
                    f"DELETE FROM {table} WHERE id = ? AND character_id = ?",
                    (record_id, self.character_id),
                )
            columns = tuple(row)
            connection.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
            connection.commit()
            changed()

        return AuditResolutionOutcome(
            True,
            undo=AuditUndoToken(
                "Undo replacement" if remedy_key == "replace" else "Undo removal",
                restore,
            ),
        )

    def _resolve_audit_invalid_class_power(self, finding, remedy_key: str):
        """Resolve one exact invalid saved class-power selection.

        Replacement reuses the validated class-power picker.  Removal edits
        only the owning selection record and its matching activation state, so
        unrelated class choices are never included in the undo snapshot.
        """

        if self.character_id is None:
            return AuditResolutionOutcome(False)
        subject = finding.subject
        power_set = next(
            (
                item for item in resolve_class_power_sets(
                    self.repository, self.character_id
                )
                if item.class_level_id == subject.class_level_id
                and item.key == subject.key
            ),
            None,
        )
        if power_set is None:
            return AuditResolutionOutcome(
                False, "The affected class-power set no longer exists."
            )
        if remedy_key == "replace":
            return self._resolve_audit_class_power(
                subject.class_level_id, subject.key
            )
        if remedy_key != "remove":
            return AuditResolutionOutcome(False, "Unsupported class-power remedy.")
        before = next(
            (
                item for item in self.repository.list_class_feature_selections(
                    self.character_id
                )
                if item.class_level_id == subject.class_level_id
                and item.feature_key == power_set.feature_key
            ),
            None,
        )
        if before is None:
            return AuditResolutionOutcome(
                False, "The affected class-power selection no longer exists."
            )
        stored_keys = list(decode_class_power_keys(before.option_key))
        index = subject.level
        if not (0 <= index < len(stored_keys) and stored_keys[index] == subject.field):
            index = next(
                (i for i, value in enumerate(stored_keys) if value == subject.field),
                -1,
            )
        if index < 0:
            return AuditResolutionOutcome(
                False, "The affected class power is no longer selected."
            )
        stored_keys.pop(index)
        option_map = {item.key: item for item in power_set.options}
        remaining_options = tuple(option_map.get(key) for key in stored_keys)
        after = replace(
            before,
            option_key=encode_class_power_keys(stored_keys),
            name=", ".join(
                option.name if option is not None else key
                for key, option in zip(stored_keys, remaining_options)
            ),
            description="\n\n".join(
                f"{option.name}\n{option.description}"
                for option in remaining_options
                if option is not None
            ),
        )
        active_key = class_power_active_feature_key(subject.field)
        before_state = next(
            (
                item for item in self.repository.list_class_feature_states(
                    self.character_id
                )
                if item.class_level_id == subject.class_level_id
                and item.feature_key == active_key
            ),
            None,
        )
        self.repository.save_class_feature_selection(after)
        if before_state is not None:
            self.repository.delete_class_feature_state(
                self.character_id, subject.class_level_id, active_key
            )

        def restore() -> None:
            self.repository.save_class_feature_selection(before)
            if before_state is not None:
                self.repository.save_class_feature_state(before_state)

        return AuditResolutionOutcome(
            True,
            f"Removed {finding.title.removesuffix(' is not currently available')}.",
            AuditUndoToken("Undo class-power removal", restore),
        )

    def _focus_advancement_section(self, page, section) -> None:
        self.page_tabs.setCurrentWidget(page)
        page.ensureWidgetVisible(section, 20, 20)

    def _edit_class_with_dialog(
        self, class_level, level_up: bool, *, refresh_after: bool = True
    ) -> bool:
        if self.character_id is None:
            return False
        selected = self.repository.list_class_archetype_keys(
            self.character_id, class_level.id
        ).get(class_level.id, ())
        selected_optional = tuple(
            selection.feature_key
            for selection in self.repository.list_class_feature_selections(
                self.character_id
            )
            if selection.class_level_id == class_level.id
            and _is_archetype_exchange_selection(selection)
        )
        selected_choices = {
            selection.feature_key: decode_archetype_choice_option_keys(selection.option_key)
            for selection in self.repository.list_class_feature_selections(
                self.character_id
            )
            if selection.class_level_id == class_level.id
            and _is_archetype_choice_selection(selection)
        }
        dialog = ClassLevelDialog(
            self,
            class_level,
            level_up,
            selected,
            selected_optional,
            selected_choices,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.repository.update_class_level(
            self.character_id, class_level.id, **dialog.values
        )
        self.repository.set_class_archetype_keys(
            self.character_id, class_level.id, dialog.archetype_keys
        )
        self._save_optional_archetype_exchanges(
            class_level.id,
            dialog.archetype_keys,
            dialog.selected_optional_feature_keys,
            int(dialog.values["level"]),
        )
        self._save_archetype_choices(
            class_level.id,
            dialog.archetype_keys,
            getattr(dialog, "archetype_choice_values", {}),
            int(dialog.values["level"]),
        )
        if refresh_after:
            self.refresh_all()
            self.formula_values_changed.emit()
        return True

    def _save_optional_archetype_exchanges(
        self,
        class_level_id: int,
        archetype_keys: tuple[str, ...],
        selected_feature_keys: tuple[str, ...],
        maximum_level: int,
    ) -> None:
        """Synchronize generic opt-in archetype exchanges for one class row."""

        if self.character_id is None:
            return
        selected = frozenset(selected_feature_keys)
        existing = {
            item.feature_key: item
            for item in self.repository.list_class_feature_selections(
                self.character_id
            )
            if item.class_level_id == class_level_id
            and _is_archetype_exchange_selection(item)
        }
        available = {}
        for archetype_key in archetype_keys:
            definition = archetype_entry(archetype_key)
            if definition is None:
                continue
            for option in archetype_optional_features(definition, maximum_level):
                available[option.key] = (archetype_key, option)
        valid_selected = selected.intersection(available)
        for feature_key in existing.keys() - valid_selected:
            self.repository.delete_class_feature_selection(
                self.character_id, class_level_id, feature_key
            )
        for feature_key in valid_selected:
            archetype_key, option = available[feature_key]
            self.repository.save_class_feature_selection(
                ClassFeatureSelection(
                    self.character_id,
                    class_level_id,
                    feature_key,
                    "Archetype exchange",
                    archetype_key,
                    option.name,
                    option.description,
                )
            )

    def _save_archetype_choices(
        self,
        class_level_id: int,
        archetype_keys: tuple[str, ...],
        selected_values: dict[str, tuple[str, ...]],
        maximum_level: int,
    ) -> None:
        """Synchronize all declarative archetype choice groups for one class row."""

        if self.character_id is None:
            return
        existing = {
            item.feature_key: item
            for item in self.repository.list_class_feature_selections(self.character_id)
            if item.class_level_id == class_level_id
            and _is_archetype_choice_selection(item)
        }
        available = {}
        for archetype_key in archetype_keys:
            definition = archetype_entry(archetype_key)
            if definition is None:
                continue
            for choice in archetype_choices(definition, maximum_level):
                available[choice.key] = (definition, choice)
        valid = {
            key: tuple(value for value in values if value)
            for key, values in selected_values.items()
            if key in available and values
        }
        for feature_key in existing.keys() - valid.keys():
            self.repository.delete_class_feature_selection(
                self.character_id, class_level_id, feature_key
            )
        for feature_key, values in valid.items():
            owner, choice = available[feature_key]
            options = {option.key: option for option in choice.options}
            chosen = [options[key] for key in values if key in options]
            if not chosen:
                continue
            self.repository.save_class_feature_selection(
                ClassFeatureSelection(
                    self.character_id,
                    class_level_id,
                    feature_key,
                    "Archetype choice",
                    encode_archetype_choice_option_keys(option.key for option in chosen),
                    ", ".join(option.name for option in chosen),
                    "\n\n".join(option.description for option in chosen if option.description),
                )
            )

    def _remove_class(self) -> None:
        if self.character_id is None or self.class_table.currentRow() < 0:
            QMessageBox.information(self, "Select a class", "Select a class row first.")
            return
        class_id = self.class_table.item(self.class_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        self.repository.delete_class_level(self.character_id, class_id)
        self.refresh_all()
        self.formula_values_changed.emit()

    def _refresh_abilities(self) -> None:
        if self.character_id is None:
            return
        scores = self.repository.get_ability_scores(self.character_id)
        self._loading = True
        try:
            for key, _, _ in ABILITIES:
                base, total, modifier = self._ability_controls[key]
                base.setValue(scores.get(key, 10))
                result = self._ability_result(key)
                total.setText(str(result.total))
                modifier.setText(f"{result.ability_modifier:+d}")
                applied = [
                    contribution
                    for contribution in result.contributions
                    if contribution.applied and contribution.source != "Base score"
                ]
                self._ability_adjustment_labels[key].setText(
                    "  •  ".join(
                        f"{item.source} {item.value:+d}" for item in applied
                    )
                    or "Base score only"
                )
                summary_score, summary_modifier, summary_adjustments = (
                    self._ability_summary_labels[key]
                )
                summary_score.setText(str(result.total))
                summary_modifier.setText(f"{result.ability_modifier:+d}")
                adjustment_text = (
                    "  •  ".join(f"{item.source} {item.value:+d}" for item in applied)
                    or "—"
                )
                summary_adjustments.setText(adjustment_text)
                summary_adjustments.setToolTip(adjustment_text)
                classic_score, classic_modifier, classic_adjustments = (
                    self._classic_ability_labels[key]
                )
                classic_score.setText(str(result.total))
                classic_modifier.setText(f"{result.ability_modifier:+d}")
                classic_adjustments.setText(adjustment_text)
                classic_adjustments.setToolTip(adjustment_text)
        finally:
            self._loading = False
        self._refresh_load()
        self._refresh_casting_profile()

    def _base_score_changed(self, ability: str, value: int) -> None:
        if self._loading or self.character_id is None:
            return
        self.repository.update_ability_score(self.character_id, ability, value)
        self._refresh_calculation_views(
            self._refresh_abilities,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_hit_points,
            self._refresh_formula_dependents,
        )

    def _ability_result(self, ability: str) -> CalculationResult:
        if self.character_id is None:
            raise RuntimeError("No character selected")
        return self._calculator().ability_result(ability)

    def _calculator(self) -> CharacterCalculationService:
        if self.character_id is None:
            raise RuntimeError("No character selected")
        if self._batched_calculator is not None:
            return self._batched_calculator
        return CharacterCalculationService(
            self.repository,
            self.character_id,
            sequence_active=self._sequence_active,
            sequence_links=self._sequence_links,
        )

    @contextmanager
    def _calculation_batch(self):
        """Reuse one immutable rules snapshot during a coordinated UI refresh."""

        outermost = self._batched_calculator is None
        if outermost:
            self._batched_calculator = CharacterCalculationService(
                self.repository,
                self.character_id,
                sequence_active=self._sequence_active,
                sequence_links=self._sequence_links,
            )
        try:
            yield
        finally:
            if outermost:
                self._batched_calculator = None

    def _refresh_calculation_views(self, *refreshers: Callable[[], None]) -> None:
        """Refresh several dependent presenters from one character snapshot."""

        if self.character_id is None:
            return
        with self._calculation_batch():
            for refresh in refreshers:
                refresh()

    def _saved_numeric_formulas(
        self, entity_type: str, entity_id: int
    ) -> dict[str, str]:
        if self.character_id is None:
            return {}
        return {
            field_key: expression
            for (_stored_type, _stored_id, field_key), expression
            in self.repository.numeric_formulas(
                self.character_id, entity_type, entity_id
            ).items()
        }

    def _formula_dialog_options(
        self, entity_type: str, entity_id: int
    ) -> dict[str, object]:
        return {
            "formulas": self._saved_numeric_formulas(entity_type, entity_id),
            "formula_evaluator": self._evaluate_character_formula,
            "formula_suggestions": self._character_formula_suggestions,
        }

    def _save_numeric_formulas(
        self, entity_type: str, entity_id: int, formulas: dict[str, str]
    ) -> None:
        if self.character_id is None:
            return
        for field_key, expression in formulas.items():
            self.repository.set_numeric_formula(
                self.character_id,
                entity_type,
                entity_id,
                field_key,
                expression,
            )

    def _clear_numeric_formulas(
        self,
        entity_type: str,
        entity_id: int,
        field_keys: tuple[str, ...] | None = None,
    ) -> None:
        if self.character_id is None:
            return
        keys = field_keys or tuple(
            self._saved_numeric_formulas(entity_type, entity_id)
        )
        for field_key in keys:
            self.repository.set_numeric_formula(
                self.character_id, entity_type, entity_id, field_key, ""
            )

    def _evaluate_character_formula(self, expression: str) -> float:
        return self._calculator().formula_context().evaluate(expression)

    def _evaluate_hp_max_formula(self, expression: str) -> float:
        """Present a formula-defined HP base with active HP bonuses included."""

        return self._evaluate_character_formula(expression) + self._displayed_hp_bonus

    def _character_formula_suggestions(self):
        return self._calculator().formula_context().suggestions()

    def _automatic_modifier_map(self):
        if self.character_id is None:
            return {}
        return self._calculator().automatic_modifier_map()

    def _ability_results(self) -> dict[str, CalculationResult]:
        return self._calculator().ability_results()

    def _combat_results(self) -> dict[str, CalculationResult]:
        if self.character_id is None:
            raise RuntimeError("No character selected")
        return self._calculator().combat_results()

    def _refresh_combat(self) -> None:
        if self.character_id is None:
            return
        for target, result in self._combat_results().items():
            display = (
                str(result.total)
                if target in {"ac", "touch_ac", "flat_footed_ac", "cmd"}
                else f"{result.total:+d}"
            )
            self._combat_labels[target].setText(display)
            self._classic_combat_labels[target].setText(display)

    def _refresh_hit_points(self) -> None:
        if self.character_id is None:
            return
        hp = self.repository.get_hit_points(self.character_id)
        calculator = self._calculator()
        modifiers = calculator.resolved_modifiers(
            self.repository.list_modifiers(self.character_id, "hp")
        )
        modifiers += self._automatic_modifier_map().get("hp", [])
        self._displayed_hp_bonus = calculate_stat([], modifiers).total
        formula = self.repository.numeric_formulas(
            self.character_id, "hit_points", 0
        ).get(("hit_points", 0, "maximum"), "")
        displayed_maximum = calculator.hit_point_maximum()
        if hp.auto_calculate:
            if hp.maximum != displayed_maximum:
                hp = HitPoints(
                    hp.character_id,
                    displayed_maximum,
                    hp.current,
                    hp.temporary,
                    hp.nonlethal,
                    True,
                )
                self.repository.update_hit_points(hp)
        self._loading = True
        try:
            self.hp_maximum.set_expression(formula, displayed_maximum)
            self.hp_current.setValue(hp.current)
            self.hp_temporary.setValue(hp.temporary)
            self.hp_nonlethal.setValue(hp.nonlethal)
            self.hp_auto.setChecked(hp.auto_calculate)
            self.hp_maximum.setEnabled(not hp.auto_calculate)
            self.classic_hp_maximum.setValue(displayed_maximum)
            self.classic_hp_current.setValue(hp.current)
            self.classic_hp_temporary.setValue(hp.temporary)
            self.classic_hp_nonlethal.setValue(hp.nonlethal)
            self.classic_hp_auto.setChecked(hp.auto_calculate)
            self.classic_hp_maximum.setEnabled(not hp.auto_calculate)
        finally:
            self._loading = False
        if displayed_maximum == 0:
            status = "No HP entered"
        elif hp.current < 0:
            status = "Dying"
        elif hp.current == 0:
            status = "Disabled"
        elif hp.nonlethal > hp.current:
            status = "Unconscious (nonlethal)"
        elif hp.nonlethal == hp.current:
            status = "Staggered (nonlethal)"
        else:
            status = f"{hp.current}/{displayed_maximum} HP"
            if hp.temporary:
                status += f"  +{hp.temporary} temporary"
        self.hp_status.setText(status)
        self.classic_hp_status.setText(status)
        self._update_health_bars(
            hp.current, displayed_maximum, hp.temporary, hp.nonlethal, status
        )

    def _update_health_bars(
        self, current: int, maximum: int, temporary: int,
        nonlethal: int, status: str,
    ) -> None:
        """Refresh every built-in HP bar from the same live resource state."""

        for bar in (self.hp_bar, self.classic_hp_bar):
            bar.set_health(current, maximum, temporary, nonlethal)
            bar.setToolTip(status)

    def _apply_hp_adjustment(self, amount_control, *, healing: bool) -> None:
        """Apply damage or healing using the shared Pathfinder HP rules.

        Healing restores current HP and removes an equal amount of nonlethal
        damage; damage continues to consume temporary HP first.
        """

        if self.character_id is None:
            return
        amount = int(amount_control.value())
        if amount <= 0:
            return
        hit_points = self.repository.get_hit_points(self.character_id)
        if healing:
            try:
                displayed_maximum = max(0, int(self.hp_maximum.value()))
            except FormulaError:
                displayed_maximum = max(0, hit_points.maximum)
            current = min(displayed_maximum, hit_points.current + amount)
            updated = replace(
                hit_points,
                current=current,
                nonlethal=max(0, hit_points.nonlethal - amount),
            )
        else:
            absorbed = min(max(0, hit_points.temporary), amount)
            remaining = amount - absorbed
            updated = replace(
                hit_points,
                temporary=hit_points.temporary - absorbed,
                current=max(-9999, hit_points.current - remaining),
            )
        self.repository.update_hit_points(updated)
        amount_control.setValue(0)
        self._refresh_calculation_views(
            self._refresh_hit_points,
            self._refresh_formula_dependents,
        )

    def _save_hit_points(self) -> None:
        self._save_hit_points_from(
            self.hp_maximum,
            self.hp_current,
            self.hp_temporary,
            self.hp_nonlethal,
            self.hp_auto,
        )

    def _save_classic_hit_points(self, *_args) -> None:
        self._save_hit_points_from(
            self.classic_hp_maximum,
            self.classic_hp_current,
            self.classic_hp_temporary,
            self.classic_hp_nonlethal,
            self.classic_hp_auto,
        )

    def _save_hit_points_from(
        self, maximum, current, temporary, nonlethal, automatic
    ) -> None:
        if self._loading or self.character_id is None:
            return
        try:
            maximum_value = int(maximum.value())
        except FormulaError:
            return
        if maximum is self.hp_maximum:
            self.repository.set_numeric_formula(
                self.character_id,
                "hit_points",
                0,
                "maximum",
                maximum.expression,
            )
            stored_maximum = (
                maximum_value
                if automatic.isChecked()
                else max(0, maximum_value - self._displayed_hp_bonus)
            )
        else:
            # Directly typing into the compact paper-style duplicate is an
            # intentional literal override of a previously saved formula.
            self.repository.set_numeric_formula(
                self.character_id, "hit_points", 0, "maximum", ""
            )
            stored_maximum = (
                maximum_value
                if automatic.isChecked()
                else max(0, maximum_value - self._displayed_hp_bonus)
            )
        self.repository.update_hit_points(
            HitPoints(
                self.character_id,
                stored_maximum,
                current.value(),
                temporary.value(),
                nonlethal.value(),
                automatic.isChecked(),
            )
        )
        self._refresh_calculation_views(
            self._refresh_hit_points,
            self._refresh_formula_dependents,
        )

    def _refresh_movement(
        self, calculator: CharacterCalculationService | None = None
    ) -> None:
        if self.character_id is None:
            return
        profile = self.repository.get_movement_profile(self.character_id)
        formulas = {
            field_key: expression
            for (_entity_type, _entity_id, field_key), expression
            in self.repository.numeric_formulas(
                self.character_id, "movement", 0
            ).items()
        }
        self._loading = True
        try:
            for key, control in self.movement_controls.items():
                control.set_expression(
                    formulas.get(key, ""), int(getattr(profile, key))
                )
            self.fly_maneuverability.setCurrentText(profile.fly_maneuverability)
            self.movement_notes.setText(profile.notes)
        finally:
            self._loading = False
        calculator = calculator or self._calculator()
        totals = calculator.movement_results()
        armor_weight, armor_name = calculator.worn_armor_movement()
        encumbrance = calculator.encumbrance()
        for key, label in self.movement_totals.items():
            value = int(totals[key])
            label.setText(f"{value} ft" if value else "—")
            automatic = calculator.automatic_total(key)
            expression = formulas.get(key, "")
            literal = int(getattr(profile, key))
            if expression:
                source = expression
            elif literal:
                source = f"Base {literal} ft"
            elif key == "land_speed":
                source = "Racial / automatic"
            elif key == "armor_speed":
                source = (
                    f"{armor_weight.title()} armor · {armor_name}"
                    if armor_weight and armor_weight != "unknown"
                    else f"Manual armor rule · {armor_name}"
                    if armor_name and literal
                    else "Uses land speed"
                )
            else:
                source = "Automatic movement" if value else "Unavailable"
            if totals.get(key + "_source"):
                source = str(totals[key + "_source"])
            if key == "fly_speed" and value and profile.fly_maneuverability:
                source += f" · {profile.fly_maneuverability}"
            if automatic:
                source += f" · {automatic:+d} automatic"
            if key == "land_speed" and (
                armor_weight in {"medium", "heavy"}
                or bool(armor_name and int(getattr(profile, "armor_speed")))
            ):
                source += f" · wearing {armor_name}"
            if key == "land_speed" and encumbrance.load != "Light":
                source += f" · {encumbrance.load.casefold()} load"
            self.movement_sources[key].setText(source)
            self.movement_sources[key].setToolTip(
                f"{key.replace('_', ' ').title()}: {source}"
            )
            label.setToolTip(
                f"Current {key.replace('_', ' ')}: {value} ft"
                + (f" ({automatic:+d} automatic)" if automatic else "")
            )

    def _save_movement(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        previous = self.repository.get_movement_profile(self.character_id)
        values = {}
        for key, control in self.movement_controls.items():
            expression = control.expression
            self.repository.set_numeric_formula(
                self.character_id, "movement", 0, key, expression
            )
            try:
                values[key] = int(control.value())
            except FormulaError:
                values[key] = int(getattr(previous, key))
        self.repository.update_movement_profile(MovementProfile(
            character_id=self.character_id,
            **values,
            fly_maneuverability=self.fly_maneuverability.currentText(),
            notes=self.movement_notes.text(),
        ))
        self._refresh_calculation_views(
            self._refresh_movement,
            partial(self._refresh_formula_dependents, movement=False),
        )

    def _refresh_skills(self) -> None:
        active_reference = getattr(self, "_active_skill_reference", None)
        if self.character_id is None:
            return
        states = self.repository.list_skill_states(self.character_id)
        calculator = self._calculator()
        rule_items = (
            list(self.repository.list_feats(self.character_id))
            + list(self.repository.list_traits(self.character_id))
            + list(self.repository.list_martial_talents(self.character_id))
            + list(self.repository.list_spells(self.character_id))
        )
        resolved_class_skills = (
            calculator.resolved_class_skills() | effect_class_skills(rule_items)
        )
        ability_abbreviations = {key: abbreviation for key, _, abbreviation in ABILITIES}
        effective_ranks = calculator.effective_skill_ranks()
        definitions = character_skill_definitions(
            self.repository, self.character_id
        )
        blocker = QSignalBlocker(self.skill_table)
        self.skill_table.setUpdatesEnabled(False)
        try:
            self.skill_table.setRowCount(0)
            for definition in definitions:
                state = states[definition.key]
                root_skill_key = base_skill_key(definition.key)
                resolved_class_skill = (
                    state.class_skill
                    or definition.key in resolved_class_skills
                    or root_skill_key in resolved_class_skills
                )
                if state.class_skill_override is not None:
                    resolved_class_skill = state.class_skill_override
                effective_state = SkillState(
                    state.skill_key,
                    state.ranks,
                    resolved_class_skill,
                    state.misc_bonus,
                    state.notes,
                    state.ability_override,
                    state.class_skill_override,
                )
                effective_ability = state.ability_override or definition.ability
                result = calculator.skill_result(definition.key)
                row = self.skill_table.rowCount()
                self.skill_table.insertRow(row)
                applied_acp = abs(next(
                    (
                        contribution.value
                        for contribution in result.contributions
                        if contribution.source == "Armor check penalty"
                    ),
                    0,
                ))
                shown_ranks = effective_ranks.get(definition.key, state.ranks)
                values = (
                    definition.name + (" *" if definition.trained_only else ""),
                    "■" if effective_state.class_skill else "□",
                    f"{result.total:+d}" if result.usable else "—",
                    ability_abbreviations[effective_ability],
                    str(shown_ranks),
                    f"{state.misc_bonus:+d}",
                    f"-{applied_acp}" if applied_acp else "—",
                    state.notes,
                )
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setData(Qt.ItemDataRole.UserRole, definition.key)
                    if column in {1, 2, 3, 4, 5, 6}:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if column == 2:
                        font = cell.font()
                        font.setBold(True)
                        font.setPointSize(font.pointSize() + 1)
                        cell.setFont(font)
                    if column == 1:
                        cell.setToolTip(
                            "Class skill" if effective_state.class_skill else "Not a class skill"
                        )
                    if column == 3 and state.ability_override:
                        cell.setToolTip("Custom ability modifier; double-click to change")
                    if column == 4 and shown_ranks > state.ranks:
                        cell.setToolTip(
                            f"{state.ranks} purchased; Athletics grants an effective minimum of {shown_ranks}."
                        )
                    self.skill_table.setItem(row, column, cell)
        finally:
            self.skill_table.setUpdatesEnabled(True)
            del blocker
        skill_height = (
            self.skill_table.horizontalHeader().sizeHint().height()
            + len(definitions) * self.skill_table.verticalHeader().defaultSectionSize()
            + 6
        )
        if bool(self.skills_section.property("freeformManaged")):
            self.skill_table.setMinimumHeight(44)
            self.skill_table.setMaximumHeight(16777215)
            self.skill_table.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
        else:
            self.skill_table.setFixedHeight(skill_height)
        if active_reference:
            for row in range(self.skill_table.rowCount()):
                if self.skill_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == active_reference:
                    scroll = self.feature_details.verticalScrollBar().value()
                    self._show_table_row_details(self.skill_table, row)
                    self.feature_details.verticalScrollBar().setValue(scroll)
                    break

    def _selected_skill(self):
        if self.skill_table.currentRow() < 0:
            return None
        key = self.skill_table.item(self.skill_table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        if self.character_id is None:
            return None
        return next(
            definition
            for definition in character_skill_definitions(
                self.repository, self.character_id
            )
            if definition.key == key
        )

    def _edit_skill(self, *_args) -> None:
        definition = self._selected_skill()
        if definition is None or self.character_id is None:
            QMessageBox.information(self, "Select a skill", "Select a skill row first.")
            return
        state = self.repository.list_skill_states(self.character_id)[definition.key]
        entity_id = skill_formula_entity_id(definition.key)
        root_skill_key = base_skill_key(definition.key)
        rule_items = (
            list(self.repository.list_feats(self.character_id))
            + list(self.repository.list_traits(self.character_id))
            + list(self.repository.list_martial_talents(self.character_id))
            + list(self.repository.list_spells(self.character_id))
        )
        resolved_class_skills = (
            self._calculator().resolved_class_skills()
            | effect_class_skills(rule_items)
        )
        effective_class_skill = (
            state.class_skill
            or definition.key in resolved_class_skills
            or root_skill_key in resolved_class_skills
        )
        if state.class_skill_override is not None:
            effective_class_skill = state.class_skill_override
        dialog = SkillDialog(
            definition.name,
            state,
            self,
            effective_class_skill=effective_class_skill,
            specialty=specialization_for(
                self.repository, self.character_id, definition.key
            ),
            base_skill_key=(
                root_skill_key
                if root_skill_key in {"craft", "perform", "profession"}
                else ""
            ),
            **self._formula_dialog_options("skill", entity_id),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.update_skill_state(self.character_id, dialog.state)
        if getattr(dialog, "base_skill_key", ""):
            self.repository.update_skill_specialization(
                self.character_id,
                definition.key,
                dialog.base_skill_key,
                getattr(dialog, "specialization", ""),
            )
        self._save_numeric_formulas("skill", entity_id, dialog.numeric_formulas)
        self._refresh_skills()
        self._refresh_animal_companion()
        self._refresh_advancement_budgets()
        self._refresh_formula_dependents()

    def _refresh_feats(self) -> None:
        if self.character_id is None:
            return
        feats = populate_record_table(
            self.feat_table,
            self.repository.list_feats(self.character_id),
            lambda feat: (
                f"{feat.name} — {feat.choice}" if feat.choice else feat.name,
                feat.catalog_category or "Custom",
            ),
            lambda feat: self._readable_tooltip(
                feat.name, self._feature_summary_text("Feat", feat)
            ),
        )
        self._fit_feature_table(self.feat_table, len(feats), 4, 8)

    def _selected_feat(self) -> Feat | None:
        if self.character_id is None or self.feat_table.currentRow() < 0:
            return None
        feat_id = self.feat_table.item(self.feat_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return next(
            feat for feat in self.repository.list_feats(self.character_id) if feat.id == feat_id
        )

    def _add_feat(self, *, selection_limit: int = 0) -> None:
        if self.character_id is None:
            return
        dialog = FeatCatalogDialog(
            self.repository.list_feats(self.character_id),
            self,
            selection_limit=selection_limit,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self._add_custom_feat()
            return
        self._add_catalog_batch(
            self._catalog_dialog_entries(dialog),
            self._add_catalog_feat,
            self._feats_changed,
            "feats",
        )

    def _add_custom_feat(self) -> None:
        if self.character_id is None:
            return
        dialog = FeatDialog(
            self,
            formulas={},
            formula_evaluator=self._evaluate_character_formula,
            formula_suggestions=self._character_formula_suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            feat_id = self.repository.add_feat(self.character_id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add feat", str(error))
            return
        self._save_numeric_formulas("feat", feat_id, dialog.numeric_formulas)
        self._feats_changed()

    def _add_catalog_feat(
        self,
        entry: dict,
        *,
        catalog_category_override: str = "",
    ) -> bool:
        if self.character_id is None:
            return False
        automation = dict(entry.get("automation", {}))
        choice = ""
        choice_key = ""
        choice_type = str(automation.get("choice_type", ""))
        if choice_type:
            choice_dialog = FeatChoiceDialog(
                choice_type,
                str(automation.get("choice_label", "Choice")),
                self.repository.list_attacks(self.character_id),
                self.repository.list_equipment(self.character_id),
                self,
            )
            if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            choice = choice_dialog.choice
            choice_key = choice_dialog.choice_key
        effects: list[dict] = []
        for source_effect in automation.get("effects", []):
            effect = dict(source_effect)
            effect["target"] = str(effect.get("target", "")).replace(
                "{choice_key}", choice_key
            )
            effect["scope"] = str(effect.get("scope", "")).replace(
                "{choice_key}", choice_key
            )
            effects.append(effect)
        categories = tuple(str(value) for value in entry.get("categories", ()))
        category = ", ".join(categories) or "General"
        catalog_category = (
            f"{catalog_category_override} · {category}"
            if catalog_category_override
            else f"{entry['source_group']} · {category}"
        )
        feat_id = self.repository.add_feat(
            self.character_id,
            name=str(entry["name"]),
            notes=str(entry.get("description", "")),
            catalog_key=str(entry["key"]),
            catalog_category=catalog_category,
            prerequisites=str(entry.get("prerequisites", "")),
            source_url=str(entry.get("source_url", "")),
            choice=choice,
            effects=effects,
            repeatable=bool(entry.get("repeatable", False)),
            activation=str(automation.get("activation", "always")),
            activation_note=str(automation.get("activation_note", "")),
        )
        if automation and not bool(automation.get("default_enabled", True)):
            self.repository.set_feat_enabled(self.character_id, feat_id, False)
        return True

    def _edit_feat(self, *_args) -> None:
        feat = self._selected_feat()
        if feat is None or self.character_id is None:
            QMessageBox.information(self, "Select a feat", "Select a feat row first.")
            return
        dialog = FeatDialog(
            self,
            feat,
            **self._formula_dialog_options("feat", feat.id),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_feat(self.character_id, feat.id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit feat", str(error))
            return
        self._save_numeric_formulas("feat", feat.id, dialog.numeric_formulas)
        self._feats_changed()

    def _toggle_feat(self) -> None:
        feat = self._selected_feat()
        if feat is None or self.character_id is None:
            QMessageBox.information(self, "Select a feat", "Select a feat row first.")
            return
        self.repository.set_feat_enabled(self.character_id, feat.id, not feat.enabled)
        self._feats_changed()

    def _remove_feat(self) -> None:
        feat = self._selected_feat()
        if feat is None or self.character_id is None:
            QMessageBox.information(self, "Select a feat", "Select a feat row first.")
            return
        self._clear_numeric_formulas("feat", feat.id)
        self.repository.delete_feat(self.character_id, feat.id)
        self._feats_changed()

    def _feats_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_feats,
            self._refresh_inquisitor_features,
            self._refresh_abilities,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_hit_points,
            self._refresh_casting_profile,
            self._refresh_sphere_statistics,
            self._refresh_advancement_budgets,
            self._refresh_formula_dependents,
        )

    def _refresh_traits(self) -> None:
        if self.character_id is None:
            return
        traits = populate_record_table(
            self.trait_table,
            self.repository.list_traits(self.character_id),
            lambda trait: (
                f"{trait.name} — {trait.choice}" if trait.choice else trait.name,
                trait.catalog_category or "Custom",
            ),
            lambda trait: self._readable_tooltip(
                trait.name, self._feature_summary_text("Trait", trait)
            ),
        )
        self._fit_feature_table(self.trait_table, len(traits), 2, 3)

    def _selected_trait(self) -> Trait | None:
        if self.character_id is None or self.trait_table.currentRow() < 0:
            return None
        trait_id = self.trait_table.item(self.trait_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return next(
            trait
            for trait in self.repository.list_traits(self.character_id)
            if trait.id == trait_id
        )

    def _add_trait(self) -> None:
        if self.character_id is None:
            return
        dialog = TraitCatalogDialog(self.repository.list_traits(self.character_id), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self._add_custom_trait()
            return
        self._add_catalog_batch(
            self._catalog_dialog_entries(dialog),
            self._add_catalog_trait,
            self._traits_changed,
            "traits",
        )

    def _add_custom_trait(self) -> None:
        if self.character_id is None:
            return
        dialog = TraitDialog(
            self,
            formulas={},
            formula_evaluator=self._evaluate_character_formula,
            formula_suggestions=self._character_formula_suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            trait_id = self.repository.add_trait(self.character_id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add trait", str(error))
            return
        self._save_numeric_formulas("trait", trait_id, dialog.numeric_formulas)
        self._traits_changed()

    def _add_catalog_trait(self, entry: dict) -> bool:
        if self.character_id is None:
            return False
        automation = dict(entry.get("automation", {}))
        choice = ""
        choice_key = ""
        choice_type = str(automation.get("choice_type", ""))
        if choice_type:
            choice_dialog = FeatChoiceDialog(
                choice_type,
                str(automation.get("choice_label", "Choice")),
                self.repository.list_attacks(self.character_id),
                self.repository.list_equipment(self.character_id),
                self,
            )
            if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            choice = choice_dialog.choice
            choice_key = choice_dialog.choice_key
        effects: list[dict] = []
        for source_effect in automation.get("effects", []):
            effect = dict(source_effect)
            effect["target"] = str(effect.get("target", "")).replace(
                "{choice_key}", choice_key
            )
            effect["scope"] = str(effect.get("scope", "")).replace(
                "{choice_key}", choice_key
            )
            effects.append(effect)
        categories = tuple(str(value) for value in entry.get("categories", ()))
        category = ", ".join(categories) or "General"
        trait_id = self.repository.add_trait(
            self.character_id,
            name=str(entry["name"]),
            notes=str(entry.get("description", "")),
            catalog_key=str(entry["key"]),
            catalog_category=f"{entry['source_group']} · {category}",
            prerequisites=str(entry.get("prerequisites", "")),
            source_url=str(entry.get("source_url", "")),
            choice=choice,
            effects=effects,
            repeatable=bool(entry.get("repeatable", False)),
            activation=str(automation.get("activation", "always")),
            activation_note=str(automation.get("activation_note", "")),
        )
        if automation and not bool(automation.get("default_enabled", True)):
            self.repository.set_trait_enabled(self.character_id, trait_id, False)
        return True

    def _edit_trait(self, *_args) -> None:
        trait = self._selected_trait()
        if trait is None or self.character_id is None:
            QMessageBox.information(self, "Select a trait", "Select a trait row first.")
            return
        dialog = TraitDialog(
            self,
            trait,
            **self._formula_dialog_options("trait", trait.id),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_trait(self.character_id, trait.id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit trait", str(error))
            return
        self._save_numeric_formulas("trait", trait.id, dialog.numeric_formulas)
        self._traits_changed()

    def _toggle_trait(self) -> None:
        trait = self._selected_trait()
        if trait is None or self.character_id is None:
            QMessageBox.information(self, "Select a trait", "Select a trait row first.")
            return
        self.repository.set_trait_enabled(self.character_id, trait.id, not trait.enabled)
        self._traits_changed()

    def _remove_trait(self) -> None:
        trait = self._selected_trait()
        if trait is None or self.character_id is None:
            QMessageBox.information(self, "Select a trait", "Select a trait row first.")
            return
        self._clear_numeric_formulas("trait", trait.id)
        self.repository.delete_trait(self.character_id, trait.id)
        self._traits_changed()

    def _traits_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_traits,
            self._refresh_abilities,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_hit_points,
            self._refresh_formula_dependents,
        )

    def _refresh_martial_focus(self) -> None:
        if self.character_id is None:
            return
        focus = self.repository.get_martial_focus(self.character_id)
        formula = self.repository.numeric_formulas(
            self.character_id, "martial_focus", 0
        ).get(("martial_focus", 0, "maximum"), "")
        maximum = int(self._calculator().numeric_formula_value(
            "martial_focus", 0, "maximum", focus.maximum,
            minimum=1, maximum=99,
        ))
        self._loading = True
        try:
            self.martial_focus_maximum.set_expression(formula, focus.maximum)
            self.martial_focus_current.setMaximum(maximum)
            self.martial_focus_current.setValue(min(focus.current, maximum))
            self.martial_focus_recovery.setText(focus.recovery_method)
            self.martial_focus_notes.setText(focus.notes)
            self._update_martial_focus_status()
            self._refresh_martial_book_dialog()
        finally:
            self._loading = False

    def _save_martial_focus(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        try:
            maximum = int(self.martial_focus_maximum.value())
        except FormulaError:
            return
        self.repository.set_numeric_formula(
            self.character_id,
            "martial_focus",
            0,
            "maximum",
            self.martial_focus_maximum.expression,
        )
        self.martial_focus_current.setMaximum(maximum)
        self.repository.update_martial_focus(
            MartialFocus(
                character_id=self.character_id,
                current=self.martial_focus_current.value(),
                maximum=maximum,
                recovery_method=self.martial_focus_recovery.text(),
                notes=self.martial_focus_notes.text(),
            )
        )
        self._update_martial_focus_status()
        self._refresh_martial_book_dialog()
        self._refresh_formula_dependents()

    def _martial_focus_maximum_changed(self, *_args) -> None:
        if self._loading:
            return
        try:
            maximum = int(self.martial_focus_maximum.value())
        except FormulaError:
            return
        self.martial_focus_current.setMaximum(maximum)
        if self.martial_focus_current.value() > maximum:
            self.martial_focus_current.setValue(maximum)
        self._save_martial_focus()

    def _spend_martial_focus(self) -> None:
        current = self.martial_focus_current.value()
        if current == 0:
            return
        self.martial_focus_current.setValue(current - 1)

    def _regain_martial_focus(self) -> None:
        self.martial_focus_current.setValue(self.martial_focus_maximum.value())

    def _update_martial_focus_status(self) -> None:
        current = self.martial_focus_current.value()
        maximum = self.martial_focus_maximum.value()
        focused = current > 0
        self.martial_focus_status.setText("FOCUSED" if focused else "EXPENDED")
        self.martial_focus_status.setObjectName("focusReady" if focused else "focusSpent")
        self.martial_focus_status.style().unpolish(self.martial_focus_status)
        self.martial_focus_status.style().polish(self.martial_focus_status)
        self.martial_focus_counter.setText(f"{current} / {maximum}")
        visible = min(maximum, 12)
        pips = "●" * min(current, visible) + "○" * max(0, visible - current)
        if maximum > visible:
            pips += f"  +{maximum - visible}"
        self.martial_focus_pips.setText(pips or "○")
        recovery = self.martial_focus_recovery.text().strip()
        tooltip = f"{current} of {maximum} focus available."
        if recovery:
            tooltip += f"\nRegain: {recovery}"
        self.martial_focus_status.setToolTip(tooltip)
        self.martial_focus_pips.setToolTip(tooltip)

    def _refresh_martial_talents(self) -> None:
        if self.character_id is None:
            return
        saved_talents = self.repository.list_martial_talents(self.character_id)
        display_talents = granted_martial_sphere_abilities(saved_talents)
        talents = populate_record_table(
            self.martial_talent_table,
            display_talents,
            lambda talent: (
                f"{talent.name} — {talent.choice}" if talent.choice else talent.name,
                talent.sphere or "—",
                talent.catalog_category or talent.talent_type,
            ),
            lambda talent: self._readable_tooltip(
                talent.name,
                self._feature_summary_text("Martial Talent", talent),
            ),
        )
        for row in range(self.martial_talent_table.rowCount()):
            for column in range(self.martial_talent_table.columnCount()):
                cell = self.martial_talent_table.item(row, column)
                if cell is not None:
                    cell.setBackground(QColor("#FBE2D5"))
        self._fit_feature_table(self.martial_talent_table, len(talents), 4, 9)

    def _refresh_moldable_talents(self) -> None:
        if self.character_id is None:
            return
        moldable = exploitant_has_moldable_talents(self.repository, self.character_id)
        profile = adaptation_profile(self.repository, self.character_id)
        available = moldable or profile.available
        source_key = MOLDABLE_SOURCE_KEY if moldable else ADAPTATION_SOURCE_KEY
        capacity = (
            moldable_talent_capacity(self.repository, self.character_id)
            if moldable else profile.capacity
        )
        records = self.repository.list_flexible_talent_selections(
            self.character_id, source_key
        )[:capacity]
        resource = None if moldable else self._adaptation_resource_view()
        remaining = resource.current if resource is not None else 0
        change_available = (
            self.repository.flexible_talent_change_available(
                self.character_id, MOLDABLE_SOURCE_KEY
            ) or len(records) < capacity
            if moldable else bool(records or remaining > 0)
        )
        self._set_section_rule_available("moldable_talents", available)
        if not available:
            self.moldable_talent_title.setText("TEMPORARY TALENTS")
            self.moldable_talent_table.setRowCount(0)
            self.moldable_talent_summary.setText("No temporary talent feature available.")
            self.moldable_talent_change_button.setEnabled(False)
            return
        if moldable:
            self.moldable_talent_title.setText("MOLDABLE TALENTS")
            self.moldable_talent_summary.setText(
                f"{len(records)} selected · {capacity} available · "
                + ("ready to change" if change_available else "refreshes after a full rest")
            )
            self.moldable_talent_change_button.setText("Choose / change talents")
        elif profile.alternative_kind == "rogue":
            self.moldable_talent_title.setText(profile.name.upper())
            self.moldable_talent_summary.setText(
                "Rogue talents are selected in the class-power area; active Adaptation uses "
                f"remain {remaining}."
            )
            self.moldable_talent_change_button.setText("Choose rogue adaptation")
            change_available = False
        else:
            self.moldable_talent_title.setText(profile.name.upper())
            action = adaptation_action_text(profile.level, max(1, len(records)))
            self.moldable_talent_summary.setText(
                f"{len(records)} active of {capacity} · {remaining} daily uses remain · {action}"
            )
            self.moldable_talent_change_button.setText("Use / end adaptation")
        self.moldable_talent_change_button.setEnabled(change_available)
        self.moldable_talent_table.setRowCount(0)
        for record in records:
            row = self.moldable_talent_table.rowCount()
            self.moldable_talent_table.insertRow(row)
            values = (
                f"{record.name} — {record.choice}" if record.choice else record.name,
                record.sphere or "—",
                record.talent_kind.title(),
            )
            tooltip = self._readable_tooltip(record.name, record.description)
            background = QColor(
                "#FBE2D5" if record.talent_kind == "martial" else "#DAE9F8"
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(tooltip)
                cell.setBackground(background)
                cell.setForeground(QColor("#252C35"))
                self.moldable_talent_table.setItem(row, column, cell)
        self._fit_feature_table(
            self.moldable_talent_table, len(records), 1, max(1, capacity)
        )

    def _change_moldable_talents(self) -> None:
        if self.character_id is None:
            return
        moldable = exploitant_has_moldable_talents(self.repository, self.character_id)
        profile = adaptation_profile(self.repository, self.character_id)
        if not moldable and (not profile.available or not profile.allowed_kinds):
            return
        source_key = MOLDABLE_SOURCE_KEY if moldable else ADAPTATION_SOURCE_KEY
        capacity = (
            moldable_talent_capacity(self.repository, self.character_id)
            if moldable else profile.capacity
        )
        if capacity <= 0:
            return
        existing = self.repository.list_flexible_talent_selections(
            self.character_id, source_key
        )[:capacity]
        can_replace = (
            self.repository.flexible_talent_change_available(
                self.character_id, MOLDABLE_SOURCE_KEY
            ) if moldable else True
        )
        if len(existing) >= capacity and not can_replace:
            return
        dialog = MoldableTalentsDialog(
            self.repository,
            self.character_id,
            capacity,
            self,
            locked_count=0 if can_replace else len(existing),
            source_key=source_key,
            validator=validate_moldable_entries if moldable else validate_adaptation_entries,
            feature_name="Moldable Talents" if moldable else profile.name,
            instructions=(
                "Slots resolve from top to bottom. Adaptation can only grant talents "
                "from base spheres you already possess; every newly gained or replaced "
                "slot spends one daily use. Clearing a slot costs nothing."
                if not moldable else ""
            ),
            allowed_kinds=(moldable_talent_kinds(self.repository, self.character_id)
                           if moldable else profile.allowed_kinds),
            allow_base_spheres=moldable,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            validator = validate_moldable_entries if moldable else validate_adaptation_entries
            selections = validator(self.repository, self.character_id, dialog.selections)
            if not moldable:
                resource = self._adaptation_resource_view()
                if resource is None:
                    raise ValueError("Adaptation is no longer available.")
                cost = adaptation_change_cost(existing, selections)
                if cost > resource.current:
                    raise ValueError(
                        f"This change costs {cost} Adaptation use(s), but only "
                        f"{resource.current} remain."
                    )
            if moldable:
                if not save_moldable_entries(self.repository, self.character_id, selections):
                    return
            else:
                self.repository.replace_flexible_talent_selections(
                    self.character_id, source_key, selections
                )
            if not moldable and cost:
                self.repository.save_class_feature_state(
                    replace(resource.state, current_value=resource.current - cost)
                )
        except ValueError as error:
            QMessageBox.warning(
                self,
                "Cannot change temporary talents",
                str(error),
            )
            return
        self._refresh_calculation_views(
            self._refresh_moldable_talents,
            self._refresh_inquisitor_features,
            self._refresh_martial_book_dialog,
            self._refresh_spell_book_dialog,
            self._refresh_prodigy_sphere_rules,
            self._refresh_prodigy_imbues,
            self._refresh_sequence_options,
            self._refresh_abilities,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_movement,
            self._refresh_attacks,
            self._refresh_formula_dependents,
        )

    def _adaptation_resource_view(self):
        """Return the resolved Adaptation resource without coupling UI to storage."""

        if self.character_id is None:
            return None
        ability_modifiers = {
            key: value.ability_modifier
            for key, value in self._ability_results().items()
        }
        for module in resolve_class_feature_modules(
            self.repository, self.character_id, ability_modifiers
        ):
            for resource in module.resources:
                if resource.key == "adaptation":
                    return resource
        return None

    def _selected_martial_talent(self) -> MartialTalent | None:
        if self.character_id is None or self.martial_talent_table.currentRow() < 0:
            return None
        talent_id = self.martial_talent_table.item(
            self.martial_talent_table.currentRow(), 0
        ).data(Qt.ItemDataRole.UserRole)
        return next(
            talent
            for talent in self.repository.list_martial_talents(self.character_id)
            if talent.id == talent_id
        )

    def _add_martial_talent(self, *, selection_limit: int = 0) -> None:
        if self.character_id is None:
            return
        dialog = MartialTalentCatalogDialog(
            self.repository.list_martial_talents(self.character_id),
            self,
            selection_limit=selection_limit,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self._add_custom_martial_talent()
            return
        selected = self._catalog_dialog_entries(dialog)
        ordered = tuple(
            sorted(
                selected,
                key=lambda entry: 0 if entry.get("category") == "Base Sphere" else 1,
            )
        )
        self._add_catalog_batch(
            ordered,
            self._add_catalog_martial_entry,
            self._martial_talents_changed,
            "martial talents",
        )

    def _add_custom_martial_talent(self) -> None:
        if self.character_id is None:
            return
        dialog = MartialTalentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.add_martial_talent(self.character_id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add talent", str(error))
            return
        self._martial_talents_changed()

    def _add_catalog_martial_entry(
        self,
        entry: dict,
        preset_choice: str = "",
        skip_base_choice_prompt: bool = False,
    ) -> bool:
        if self.character_id is None:
            return False
        automation = dict(entry.get("automation", {}))
        choice = preset_choice.strip()
        choice_key = ""
        choice_type = str(automation.get("choice_type", ""))
        if choice_type and not choice:
            choice_dialog = FeatChoiceDialog(
                choice_type,
                str(automation.get("choice_label", "Choice")),
                self.repository.list_attacks(self.character_id),
                self.repository.list_equipment(self.character_id),
                self,
                excluded_choices=(
                    athletics_packages(
                        self.repository.list_martial_talents(self.character_id)
                    )
                    if choice_type == "athletics_packages_two"
                    else ()
                ),
            )
            if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            choice = choice_dialog.choice
            choice_key = choice_dialog.choice_key
        effects: list[dict] = []
        for source_effect in automation.get("effects", []):
            effect = dict(source_effect)
            effect["target"] = str(effect.get("target", "")).replace(
                "{choice_key}", choice_key
            )
            effect["scope"] = str(effect.get("scope", "")).replace(
                "{choice_key}", choice_key
            )
            effects.append(effect)
        owned = self.repository.list_martial_talents(self.character_id)
        owned_keys = {talent.catalog_key for talent in owned if talent.catalog_key}
        repeatable = bool(automation.get("repeatable"))
        repeat_limit = int(automation.get("repeat_limit") or 0)
        if repeat_limit and sum(
            1 for talent in owned if talent.catalog_key == entry["key"]
        ) >= repeat_limit:
            raise ValueError(
                f"{entry['name']} can be selected no more than {repeat_limit} times."
            )
        if entry["key"] in owned_keys and not repeatable:
            raise ValueError("This sphere or talent is already on the character.")
        category = str(entry["category"])
        sphere_name = str(entry["sphere"])
        restriction = martial_talent_restriction_reason(entry, owned)
        if restriction:
            raise ValueError(restriction)
        if (
            category == "Base Sphere"
            and base_sphere_choice_options(sphere_name, "martial")
            and not choice
            and not skip_base_choice_prompt
        ):
            acquisition = SphereAcquisitionDialog(
                set(), self, fixed_sphere=sphere_name, sphere_kind="martial"
            )
            if acquisition.exec() != QDialog.DialogCode.Accepted:
                return False
            self._acquire_martial_sphere(
                sphere_name,
                acquisition.drawback_selections,
                acquisition.base_sphere_choice,
            )
            return True
        if category != "Base Sphere":
            sphere = martial_sphere(sphere_name)
            if sphere is not None:
                base_key = f"{sphere['slug']}:base"
                has_base = base_key in owned_keys or any(
                    talent.sphere.casefold() == sphere_name.casefold()
                    and talent.talent_type == "Base Sphere"
                    for talent in owned
                )
                if not has_base:
                    inferred_choice = martial_base_choice_for_entry(entry)
                    if inferred_choice:
                        self._acquire_martial_sphere(
                            sphere_name, base_choice=inferred_choice
                        )
                    elif base_sphere_choice_options(sphere_name, "martial"):
                        acquisition = SphereAcquisitionDialog(
                            set(), self, fixed_sphere=sphere_name, sphere_kind="martial"
                        )
                        if acquisition.exec() != QDialog.DialogCode.Accepted:
                            return False
                        self._acquire_martial_sphere(
                            sphere_name,
                            acquisition.drawback_selections,
                            acquisition.base_sphere_choice,
                        )
                    else:
                        self.repository.add_martial_talent(
                            self.character_id,
                            f"{sphere_name} Sphere",
                            sphere_name,
                            "Base Sphere",
                            sphere["description"],
                            base_key,
                            "Base Sphere",
                            "",
                            sphere["source_url"],
                        )
                    owned = self.repository.list_martial_talents(self.character_id)
                    if any(item.catalog_key == entry["key"] for item in owned):
                        return True
                    restriction = martial_talent_restriction_reason(entry, owned)
                    if restriction:
                        raise ValueError(restriction)
        talent_type = (
            "Base Sphere"
            if category == "Base Sphere"
            else "Drawback" if category == "Drawback" else "Talent"
        )
        talent_id = self.repository.add_martial_talent(
            self.character_id,
            name=str(entry["name"]),
            sphere=sphere_name,
            talent_type=talent_type,
            notes=str(entry["description"]),
            catalog_key=str(entry["key"]),
            catalog_category=category,
            prerequisites=str(entry.get("prerequisites", "")),
            source_url=str(entry.get("source_url", "")),
            choice=choice,
            effects=effects,
            activation=str(automation.get("activation", "always")),
            activation_note=str(automation.get("activation_note", "")),
            allow_duplicate_catalog=repeatable,
        )
        if automation and not bool(automation.get("default_enabled", True)):
            self.repository.set_martial_talent_enabled(
                self.character_id, talent_id, False
            )
        return True

    def _edit_martial_talent(self, *_args) -> None:
        talent = self._selected_martial_talent()
        if talent is None or self.character_id is None:
            QMessageBox.information(self, "Select a talent", "Select a martial talent row first.")
            return
        dialog = MartialTalentDialog(self, talent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_martial_talent(
                self.character_id, talent.id, **dialog.values
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit talent", str(error))
            return
        self._martial_talents_changed()

    def _toggle_martial_talent(self) -> None:
        talent = self._selected_martial_talent()
        if talent is None or self.character_id is None:
            QMessageBox.information(
                self, "Select a talent", "Select a martial talent row first."
            )
            return
        self.repository.set_martial_talent_enabled(
            self.character_id, talent.id, not talent.enabled
        )
        self._martial_talents_changed()

    def _remove_martial_talent(self) -> None:
        talent = self._selected_martial_talent()
        if talent is None or self.character_id is None:
            QMessageBox.information(self, "Select a talent", "Select a martial talent row first.")
            return
        if talent.talent_type == "Base Sphere":
            self._delete_martial_sphere_cascade(talent.sphere)
        else:
            self.repository.delete_martial_talent(self.character_id, talent.id)
        self._martial_talents_changed()

    def _martial_talents_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_martial_talents,
            self._refresh_martial_book_dialog,
            self._refresh_sphere_build,
            self._refresh_prodigy_sphere_rules,
            self._refresh_sequence_options,
            self._refresh_abilities,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_hit_points,
            self._refresh_advancement_budgets,
            self._refresh_animal_companion,
            self._refresh_bonded_companions,
            self._refresh_formula_dependents,
        )

    def _refresh_prodigy_sequence(self) -> None:
        if self.character_id is None:
            return
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        self._loading = True
        try:
            self._sequence_active = sequence.active
            self._sequence_links = sequence.current
            self._selected_imbue_key = sequence.imbue_key
            self.sequence_maximum.setValue(sequence.maximum)
            self.sequence_maximum.setEnabled(self._current_prodigy_level() == 0)
            self._update_sequence_display()
        finally:
            self._loading = False

    def _store_prodigy_sequence(self, active: bool, current: int) -> None:
        if self.character_id is None:
            return
        maximum = self.sequence_maximum.value()
        current = min(maximum, max(0, current)) if active else 0
        active = active and current > 0
        self.repository.update_prodigy_sequence(
            ProdigySequence(
                self.character_id,
                active,
                current,
                maximum,
                self._selected_imbue_key,
            )
        )
        self._sequence_active = active
        self._sequence_links = current
        self._update_sequence_display()
        self._update_imbue_display()
        self._refresh_sequence_options()
        self._refresh_casting_profile()
        self._refresh_spells()
        self._refresh_sphere_statistics()
        self._refresh_formula_dependents()

    def _sequence_maximum_changed(self, maximum: int) -> None:
        if self._loading or self.character_id is None:
            return
        self._store_prodigy_sequence(
            self._sequence_active, min(self._sequence_links, maximum)
        )

    def _start_prodigy_sequence(self) -> None:
        self._store_prodigy_sequence(True, 1)

    def _add_prodigy_link(self) -> None:
        if not self._sequence_active:
            self._start_prodigy_sequence()
            return
        if self._sequence_links >= self.sequence_maximum.value():
            return
        self._store_prodigy_sequence(True, self._sequence_links + 1)

    def _lose_prodigy_link(self) -> None:
        if not self._sequence_active:
            return
        if self._sequence_links <= 1:
            self._store_prodigy_sequence(False, 0)
        else:
            self._store_prodigy_sequence(True, self._sequence_links - 1)

    def _end_prodigy_sequence(self) -> None:
        self._store_prodigy_sequence(False, 0)

    def _update_sequence_display(self) -> None:
        maximum = self.sequence_maximum.value()
        self.sequence_current.setText(f"{self._sequence_links} / {maximum}")
        self.sequence_status.setText(
            "SEQUENCE ACTIVE" if self._sequence_active else "NO ACTIVE SEQUENCE"
        )
        self.sequence_status.setObjectName(
            "sequenceActive" if self._sequence_active else "sequenceInactive"
        )
        self.sequence_status.style().unpolish(self.sequence_status)
        self.sequence_status.style().polish(self.sequence_status)
        bonus = self._prodigy_sequence_bonus()
        effective_caster_level = prodigy_caster_level(self._current_prodigy_level()) + bonus
        self.sequence_effect.setText(
            f"INSPIRED +{bonus} ATTACK / DAMAGE  •  EFFECTIVE CL {effective_caster_level}"
            if self._sequence_active
            else f"INSPIRED SEQUENCE INACTIVE  •  BASE CL {effective_caster_level}"
        )
        self._update_prodigy_class_summary()
        if hasattr(self, "prodigy_imbue_name"):
            self._update_imbue_display()

    def _refresh_sequence_options(self) -> None:
        if self.character_id is None:
            return
        active_imbue = next(
            (item for item in SPHERE_IMBUES if item.key == self._selected_imbue_key),
            None,
        )
        active_imbue_sphere = (
            active_imbue.sphere if self._sequence_active and active_imbue is not None else ""
        )
        imbue_spheres = {item.sphere.casefold() for item in SPHERE_IMBUES}
        for option_type, table in self.sequence_tables.items():
            table.setRowCount(0)
            options = self.repository.list_sequence_options(self.character_id, option_type)
            options = [
                option
                for option in options
                if not (
                    option_type == "Finisher"
                    and option.sphere
                    and option.sphere.casefold() in imbue_spheres
                    and option.sphere.casefold() != active_imbue_sphere.casefold()
                )
            ]
            options.sort(
                key=lambda option: (
                    0 if option.built_in and not option.sphere else 1 if option.sphere else 2,
                    option.sphere.casefold(),
                    option.name.casefold(),
                )
            )
            for option in options:
                row = table.rowCount()
                table.insertRow(row)
                action = option.action or "—"
                if (
                    option_type == "Finisher"
                    and option.minimum_links
                    and exploitant_level(self.repository, self.character_id) > 0
                ):
                    action = f"{option.minimum_links} links · {action}"
                values = (option.name, action)
                description = option.notes or "No description entered."
                tooltip = self._readable_tooltip(option.name, description)
                from app.reference_rules import sequence_reference
                from app.ui.reference_details import reference_details_html
                reference = sequence_reference(option.name, option.sphere)
                if reference is not None and option.built_in:
                    tooltip = reference_details_html(self, reference)
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setData(Qt.ItemDataRole.UserRole, option.id)
                    cell.setData(Qt.ItemDataRole.UserRole + 1, option.built_in)
                    cell.setToolTip(tooltip)
                    if option.built_in:
                        font = cell.font()
                        font.setBold(True)
                        cell.setFont(font)
                    if option.sphere:
                        magic_sphere_names = {item.sphere.casefold() for item in SPHERE_IMBUES}
                        cell.setBackground(
                            QColor("#DAE9F8")
                            if option.sphere.casefold() in magic_sphere_names
                            else QColor("#FBE2D5")
                        )
                    table.setItem(row, column, cell)
            fit_table_rows(table, len(options), 2, max(2, len(options)))

    def _selected_sequence_option(self, option_type: str) -> SequenceOption | None:
        if self.character_id is None:
            return None
        table = self.sequence_tables[option_type]
        if table.currentRow() < 0:
            return None
        option_id = table.item(table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        return next(
            option
            for option in self.repository.list_sequence_options(
                self.character_id, option_type
            )
            if option.id == option_id
        )

    def _add_sequence_option(self, option_type: str, *_args) -> None:
        if self.character_id is None:
            return
        dialog = SequenceOptionDialog(option_type, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.add_sequence_option(self.character_id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add sequence option", str(error))
            return
        self._refresh_sequence_options()

    def _edit_sequence_option(self, option_type: str, *_args) -> None:
        option = self._selected_sequence_option(option_type)
        if option is None or self.character_id is None:
            return
        if option.built_in:
            return
        dialog = SequenceOptionDialog(option_type, self, option)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_sequence_option(
                self.character_id, option.id, **dialog.values
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit sequence option", str(error))
            return
        self._refresh_sequence_options()

    def _remove_sequence_option(self, option_type: str, *_args) -> None:
        option = self._selected_sequence_option(option_type)
        if option is None or self.character_id is None:
            return
        if option.built_in:
            return
        self.repository.delete_sequence_option(self.character_id, option.id)
        self._refresh_sequence_options()

    def _use_sequence_option(self, option_type: str, *_args) -> None:
        option = self._selected_sequence_option(option_type)
        if option is None:
            return
        if option_type == "Opener":
            if self._sequence_active:
                self._add_prodigy_link()
            else:
                self._start_prodigy_sequence()
            return
        if option_type == "Link":
            self._add_prodigy_link()
            return
        if not self._sequence_active:
            return
        result = resolve_exploitant_finisher(
            self._sequence_links,
            option.minimum_links,
            incremental=(
                self.character_id is not None
                and exploitant_level(self.repository, self.character_id) > 0
            ),
        )
        if not result.allowed:
            return
        self._store_prodigy_sequence(result.active, result.links)

    def _refresh_sphere_build(self) -> None:
        if self.character_id is None:
            return
        self.tradition_table.setRowCount(0)
        for tradition in self.repository.list_character_traditions(self.character_id):
            if tradition.kind not in {'Casting', 'Martial'}:
                continue
            row = self.tradition_table.rowCount()
            self.tradition_table.insertRow(row)
            choices = json.loads(tradition.choices_json or "{}")
            choice_text = "; ".join(
                f"{key}: {', '.join(values)}" for key, values in choices.items()
            )
            source = resolved_tradition_definition(tradition)
            if source.get("custom") and not choice_text:
                choice_text = f"Custom · {len(source.get('fixed_grants', ()))} grants"
            for column, value in enumerate((tradition.kind, tradition.name, choice_text or "—")):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, tradition.id)
                if source:
                    cell.setToolTip(self._readable_tooltip(tradition.name, str(source.get("description", ""))))
                self.tradition_table.setItem(row, column, cell)
        spells = self.repository.list_spells(self.character_id)
        bases = sorted(
            (spell for spell in spells if spell.catalog_category == "Base Sphere"),
            key=lambda spell: spell.school_or_sphere.casefold(),
        )
        self.sphere_build_table.setRowCount(0)
        for base in bases:
            sphere_name = base.school_or_sphere or base.name.removesuffix(" Sphere")
            drawbacks = [
                f"{spell.name} — {spell.choice}" if spell.choice else spell.name
                for spell in spells
                if spell.school_or_sphere.casefold() == sphere_name.casefold()
                and spell.catalog_category == "Drawback"
            ]
            row = self.sphere_build_table.rowCount()
            self.sphere_build_table.insertRow(row)
            for column, value in enumerate(
                (sphere_name, ", ".join(drawbacks) if drawbacks else "None")
            ):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, sphere_name)
                self.sphere_build_table.setItem(row, column, cell)
        talents = self.repository.list_martial_talents(self.character_id)
        bases = sorted(
            (item for item in talents if item.catalog_category == "Base Sphere"),
            key=lambda item: item.sphere.casefold(),
        )
        self.martial_sphere_build_table.setRowCount(0)
        for base in bases:
            sphere_name = base.sphere or base.name.removesuffix(" Sphere")
            drawbacks = [
                f"{item.name} — {item.choice}" if item.choice else item.name
                for item in talents
                if item.sphere.casefold() == sphere_name.casefold()
                and item.catalog_category == "Drawback"
            ]
            row = self.martial_sphere_build_table.rowCount()
            self.martial_sphere_build_table.insertRow(row)
            rules = []
            if base.choice:
                rules.append(f"Starting package: {base.choice}")
            if drawbacks:
                rules.append(", ".join(drawbacks))
            for column, value in enumerate((sphere_name, " · ".join(rules) if rules else "None")):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, sphere_name)
                self.martial_sphere_build_table.setItem(row, column, cell)

    def _add_tradition(self, kind: str) -> None:
        if self.character_id is None:
            return
        catalog_dialog = TraditionCatalogDialog(kind, self)
        if catalog_dialog.exec() != QDialog.DialogCode.Accepted or catalog_dialog.selected_entry is None:
            return
        entry = catalog_dialog.selected_entry
        if any(
            item.catalog_key == entry["key"]
            for item in self.repository.list_character_traditions(self.character_id)
        ):
            return
        choice_dialog = TraditionChoiceDialog(entry, self)
        if entry.get("choice_groups"):
            if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            choices = choice_dialog.choices
            grants = choice_dialog.grants
        else:
            choices = {}
            grants = tuple(entry.get("fixed_grants", ()))
        created_keys: list[dict] = []
        try:
            if kind == "Martial":
                before = {
                    item.catalog_key for item in self.repository.list_martial_talents(self.character_id)
                    if item.catalog_key
                }
                ordered = sorted(grants, key=lambda item: item.get("category") != "Base Sphere")
                for grant in ordered:
                    if grant.get("kind") == "feat":
                        catalog_feat = feat_entry(str(grant.get("catalog_key", "")))
                        feat_keys = {
                            item.catalog_key for item in self.repository.list_feats(self.character_id)
                            if item.catalog_key
                        }
                        if catalog_feat is not None and catalog_feat["key"] not in feat_keys:
                            self._add_catalog_feat(catalog_feat)
                            created_keys.append({"kind": "feat", "catalog_key": catalog_feat["key"], "created": True})
                        elif catalog_feat is None and str(grant.get("catalog_key", "")) not in feat_keys:
                            self.repository.add_feat(
                                self.character_id,
                                name=str(grant.get("name", "Tradition bonus feat")),
                                notes=f"Granted by the {entry['name']} martial tradition.",
                                catalog_key=str(grant.get("catalog_key", "")),
                                catalog_category="Tradition Bonus Feat",
                                source_url=str(entry.get("source_url", "")),
                            )
                            created_keys.append({"kind": "feat", "catalog_key": str(grant.get("catalog_key", "")), "created": True})
                        else:
                            created_keys.append({"kind": "feat", "catalog_key": str(grant.get("catalog_key", "")), "created": False})
                        continue
                    if grant.get("kind") != "martial":
                        continue
                    catalog_item = martial_entry(str(grant.get("catalog_key", "")))
                    if catalog_item is None:
                        continue
                    if catalog_item["key"] in before:
                        created_keys.append({"kind": "martial", "catalog_key": catalog_item["key"], "created": False})
                        continue
                    self._add_catalog_martial_entry(catalog_item)
                    after = {
                        item.catalog_key for item in self.repository.list_martial_talents(self.character_id)
                        if item.catalog_key
                    }
                    for key in sorted(after - before):
                        created_keys.append({"kind": "martial", "catalog_key": key, "created": True})
                    before = after
            else:
                before = {
                    item.catalog_key for item in self.repository.list_spells(self.character_id)
                    if item.catalog_key
                }
                ordered = sorted(
                    grants,
                    key=lambda item: {
                        "Base Sphere": 0, "Drawback": 1,
                    }.get(str(item.get("category", "")), 2),
                )
                for grant in ordered:
                    if grant.get("kind") != "magic":
                        continue
                    catalog_item = magic_entry(str(grant.get("catalog_key", "")))
                    if catalog_item is None:
                        continue
                    if catalog_item["key"] in before:
                        created_keys.append({
                            "kind": "magic", "catalog_key": catalog_item["key"],
                            "created": False,
                        })
                        continue
                    if not self._add_magic_catalog_entry(
                        catalog_item, allow_build_entry=True
                    ):
                        raise ValueError(
                            f"The required choice for {catalog_item['name']} was cancelled."
                        )
                    after = {
                        item.catalog_key
                        for item in self.repository.list_spells(self.character_id)
                        if item.catalog_key
                    }
                    for key in sorted(after - before):
                        created_keys.append({
                            "kind": "magic", "catalog_key": key, "created": True,
                        })
                    before = after
                ability_grant = next(
                    (grant for grant in grants if grant.get("kind") == "casting_ability"),
                    None,
                )
                abilities = list(entry.get("casting_ability_options", ()))
                casting_ability = str(
                    ability_grant.get("name") if ability_grant else abilities[0] if abilities else "charisma"
                ).casefold()
                profile = self.repository.get_casting_profile(self.character_id)
                self.repository.update_casting_profile(
                    replace(
                        profile,
                        casting_ability=casting_ability,
                        auto_spell_points=True,
                        tradition_name=str(entry["name"]),
                        tradition_boons=str(entry.get("boons", "")),
                        tradition_drawbacks=str(entry.get("drawbacks", "")),
                        tradition_notes=str(entry.get("description", "")),
                    )
                )
            self.repository.add_character_tradition(
                self.character_id,
                str(entry["key"]),
                str(entry["name"]),
                kind,
                json.dumps(choices, ensure_ascii=False),
                json.dumps(created_keys, ensure_ascii=False),
                (
                    json.dumps(entry, ensure_ascii=False)
                    if bool(entry.get("custom")) else "{}"
                ),
            )
        except ValueError as error:
            self._rollback_tradition_grants(created_keys)
            QMessageBox.warning(self, "Cannot add tradition", str(error))
            return
        self._refresh_sphere_build()
        self._refresh_martial_talents()
        self._refresh_spells()
        self._refresh_casting_profile()
        self._refresh_advancement_budgets()

    def _rollback_tradition_grants(self, grants: list[dict]) -> None:
        """Remove only records created during an unfinished package application."""

        if self.character_id is None:
            return
        for grant in reversed(grants):
            if not grant.get("created", True):
                continue
            key = str(grant.get("catalog_key", ""))
            if grant.get("kind") == "martial":
                item = next(
                    (
                        value for value in self.repository.list_martial_talents(self.character_id)
                        if value.catalog_key == key
                    ),
                    None,
                )
                if item is not None:
                    self.repository.delete_martial_talent(self.character_id, item.id)
            elif grant.get("kind") == "magic":
                item = next(
                    (
                        value for value in self.repository.list_spells(self.character_id)
                        if value.catalog_key == key
                    ),
                    None,
                )
                if item is not None:
                    self.repository.delete_spell(self.character_id, item.id)
            elif grant.get("kind") == "feat":
                item = next(
                    (
                        value for value in self.repository.list_feats(self.character_id)
                        if value.catalog_key == key
                    ),
                    None,
                )
                if item is not None:
                    self.repository.delete_feat(self.character_id, item.id)

    def _remove_selected_tradition(self) -> None:
        if self.character_id is None or self.tradition_table.currentRow() < 0:
            return
        tradition_id = self.tradition_table.item(
            self.tradition_table.currentRow(), 0
        ).data(Qt.ItemDataRole.UserRole)
        tradition = next(
            (item for item in self.repository.list_character_traditions(self.character_id) if item.id == tradition_id),
            None,
        )
        if tradition is None:
            return
        other_grants = {
            str(grant.get("catalog_key", ""))
            for item in self.repository.list_character_traditions(self.character_id)
            if item.id != tradition.id
            for grant in json.loads(item.grants_json or "[]")
        }
        owned_grants = json.loads(tradition.grants_json or "[]")
        removable_keys = {
            str(grant.get("catalog_key", ""))
            for grant in owned_grants
            if grant.get("created", True)
            and str(grant.get("catalog_key", "")) not in other_grants
        }
        for grant in owned_grants:
            key = str(grant.get("catalog_key", ""))
            if not key or key in other_grants or not bool(grant.get("created", True)):
                continue
            if grant.get("kind") == "martial":
                talent = next(
                    (item for item in self.repository.list_martial_talents(self.character_id) if item.catalog_key == key),
                    None,
                )
                if talent is not None:
                    if talent.catalog_category == "Base Sphere" and any(
                        item.sphere.casefold() == talent.sphere.casefold()
                        and item.catalog_key not in removable_keys
                        for item in self.repository.list_martial_talents(self.character_id)
                    ):
                        continue
                    self.repository.delete_martial_talent(self.character_id, talent.id)
            elif grant.get("kind") == "feat":
                feat = next(
                    (item for item in self.repository.list_feats(self.character_id) if item.catalog_key == key),
                    None,
                )
                if feat is not None:
                    self.repository.delete_feat(self.character_id, feat.id)
            elif grant.get("kind") == "magic":
                spell = next(
                    (
                        item for item in self.repository.list_spells(self.character_id)
                        if item.catalog_key == key
                    ),
                    None,
                )
                if spell is not None:
                    if spell.catalog_category == "Base Sphere" and any(
                        item.school_or_sphere.casefold()
                        == spell.school_or_sphere.casefold()
                        and item.catalog_key not in removable_keys
                        for item in self.repository.list_spells(self.character_id)
                    ):
                        continue
                    self.repository.delete_spell(self.character_id, spell.id)
        self.repository.delete_character_tradition(self.character_id, tradition.id)
        if tradition.kind == "Casting":
            profile = self.repository.get_casting_profile(self.character_id)
            if profile.tradition_name == tradition.name:
                self.repository.update_casting_profile(
                    replace(profile, tradition_name="", tradition_boons="", tradition_drawbacks="", tradition_notes="")
                )
        self._refresh_sphere_build()
        self._martial_talents_changed()
        self._magic_talents_changed()
        self._refresh_casting_profile()

    def _selected_martial_build_sphere(self) -> str:
        row = self.martial_sphere_build_table.currentRow()
        if row < 0 or self.martial_sphere_build_table.item(row, 0) is None:
            return ""
        return str(self.martial_sphere_build_table.item(row, 0).data(Qt.ItemDataRole.UserRole) or "")

    def _add_martial_build_sphere(self) -> None:
        if self.character_id is None:
            return
        owned = {name.casefold() for name in self._owned_martial_spheres()}
        dialog = SphereAcquisitionDialog(owned, self, sphere_kind="martial")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._acquire_martial_sphere(
                dialog.sphere_name,
                dialog.drawback_selections,
                dialog.base_sphere_choice,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot gain sphere", str(error))
            return
        self._martial_talents_changed()

    def _acquire_martial_sphere(
        self, sphere_name: str, selections=(), base_choice: str = ""
    ) -> None:
        sphere = martial_sphere(sphere_name)
        if self.character_id is None or sphere is None:
            raise ValueError("Choose a valid martial sphere.")
        owned = self.repository.list_martial_talents(self.character_id)
        if any(item.catalog_category == "Base Sphere" and item.sphere.casefold() == sphere_name.casefold() for item in owned):
            raise ValueError(f"The {sphere_name} sphere is already on this character.")
        available = {str(item["key"]): item for item in martial_entries(sphere_name) if item["category"] == "Drawback"}
        if any(str(key).endswith(":limited-athleticism") for key, _choice in selections):
            base_choice = ""
        self._add_catalog_martial_entry(
            next(item for item in martial_entries(sphere_name) if item["category"] == "Base Sphere"),
            preset_choice=base_choice,
            skip_base_choice_prompt=True,
        )
        granted_name = martial_base_granted_talent_name(sphere_name, base_choice)
        if granted_name:
            granted = next(
                (
                    item for item in martial_entries(sphere_name)
                    if str(item.get("name", "")).casefold() == granted_name.casefold()
                    and item.get("category") not in {"Base Sphere", "Drawback", "Legendary Talent"}
                ),
                None,
            )
            if granted is not None:
                self._add_catalog_martial_entry(granted)
        for key, choice in selections:
            entry = available.get(key)
            if entry is None:
                raise ValueError("Choose drawbacks belonging to this sphere.")
            self._add_catalog_martial_entry(entry, preset_choice=choice)

    def _edit_martial_build_drawbacks(self) -> None:
        if self.character_id is None:
            return
        sphere_name = self._selected_martial_build_sphere()
        if not sphere_name:
            return
        talents = self.repository.list_martial_talents(self.character_id)
        existing = tuple((item.catalog_key, item.choice) for item in talents if item.sphere.casefold() == sphere_name.casefold() and item.catalog_category == "Drawback")
        base = next(
            (item for item in talents if item.sphere.casefold() == sphere_name.casefold() and item.catalog_category == "Base Sphere"),
            None,
        )
        dialog = SphereAcquisitionDialog(
            set(), self, fixed_sphere=sphere_name, existing_drawbacks=existing,
            sphere_kind="martial", existing_base_choice=base.choice if base else "",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entries = {str(item["key"]): item for item in martial_entries(sphere_name) if item["category"] == "Drawback"}
        selected_choice = dialog.base_sphere_choice
        if any(str(key).endswith(":limited-athleticism") for key, _ in dialog.drawback_selections):
            selected_choice = ""
        old_granted_name = martial_base_granted_talent_name(
            sphere_name, base.choice if base else ""
        )
        new_granted_name = martial_base_granted_talent_name(sphere_name, selected_choice)
        prospective_drawbacks = [
            SimpleNamespace(
                catalog_category="Drawback",
                sphere=sphere_name,
                name=str(entries[key]["name"]),
                choice=choice,
            )
            for key, choice in dialog.drawback_selections
        ]
        prospective = [
            item for item in talents
            if not (
                item.sphere.casefold() == sphere_name.casefold()
                and item.catalog_category == "Drawback"
            )
            and not (
                old_granted_name
                and old_granted_name.casefold() != new_granted_name.casefold()
                and item.sphere.casefold() == sphere_name.casefold()
                and item.name.casefold() == old_granted_name.casefold()
            )
        ] + prospective_drawbacks
        conflicts = []
        for item in prospective:
            if (
                getattr(item, "sphere", "").casefold() != sphere_name.casefold()
                or getattr(item, "catalog_category", "") in {"Base Sphere", "Drawback"}
                or not getattr(item, "catalog_key", "")
            ):
                continue
            entry = next(
                (
                    candidate for candidate in martial_entries(sphere_name)
                    if candidate["key"] == item.catalog_key
                ),
                None,
            )
            if entry is not None:
                reason = martial_talent_restriction_reason(entry, prospective)
                if reason:
                    conflicts.append(f"{item.name}: {reason}")
        if conflicts:
            QMessageBox.warning(
                self,
                "Existing talents conflict",
                "Remove these talents before changing the starting package or drawbacks:\n\n"
                + "\n".join(conflicts),
            )
            return
        for item in talents:
            if item.sphere.casefold() == sphere_name.casefold() and item.catalog_category == "Drawback":
                self.repository.delete_martial_talent(self.character_id, item.id)
        for key, choice in dialog.drawback_selections:
            self._add_catalog_martial_entry(entries[key], preset_choice=choice)
        if base is not None:
            self.repository.update_martial_talent(
                self.character_id,
                base.id,
                name=base.name,
                sphere=base.sphere,
                talent_type=base.talent_type,
                notes=base.notes,
                catalog_key=base.catalog_key,
                catalog_category=base.catalog_category,
                prerequisites=base.prerequisites,
                source_url=base.source_url,
                choice=selected_choice,
                effects=base.effects,
                activation=base.activation,
                activation_note=base.activation_note,
            )
        if old_granted_name.casefold() != new_granted_name.casefold():
            old_grant = next(
                (
                    item for item in talents
                    if old_granted_name
                    and item.sphere.casefold() == sphere_name.casefold()
                    and item.name.casefold() == old_granted_name.casefold()
                    and item.catalog_category not in {"Base Sphere", "Drawback"}
                ),
                None,
            )
            if old_grant is not None:
                self.repository.delete_martial_talent(self.character_id, old_grant.id)
            if new_granted_name:
                new_grant = next(
                    (
                        item for item in martial_entries(sphere_name)
                        if str(item.get("name", "")).casefold() == new_granted_name.casefold()
                        and item.get("category") not in {"Base Sphere", "Drawback", "Legendary Talent"}
                    ),
                    None,
                )
                if new_grant is not None:
                    self._add_catalog_martial_entry(new_grant)
        self._martial_talents_changed()

    def _remove_martial_build_sphere(self) -> None:
        if self.character_id is None:
            return
        sphere_name = self._selected_martial_build_sphere()
        if not sphere_name:
            return
        self._delete_martial_sphere_cascade(sphere_name)
        self._martial_talents_changed()

    def _delete_martial_sphere_cascade(self, sphere_name: str) -> None:
        """Remove a martial base sphere and every record owned by that sphere."""

        if self.character_id is None:
            return
        for item in self.repository.list_martial_talents(self.character_id):
            if item.sphere.casefold() == sphere_name.casefold():
                self.repository.delete_martial_talent(self.character_id, item.id)

    def _selected_build_sphere(self) -> str:
        row = self.sphere_build_table.currentRow()
        if row < 0 or self.sphere_build_table.item(row, 0) is None:
            return ""
        return str(
            self.sphere_build_table.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""
        )

    def _add_build_sphere(self) -> None:
        if self.character_id is None:
            return
        owned = {
            spell.school_or_sphere.casefold()
            for spell in self.repository.list_spells(self.character_id)
            if spell.catalog_category == "Base Sphere"
        }
        current_spells = self.repository.list_spells(self.character_id)
        dialog = SphereAcquisitionDialog(
            owned,
            self,
            owned_catalog_keys={spell.catalog_key for spell in current_spells if spell.catalog_key},
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._acquire_magic_sphere(
                dialog.sphere_name,
                drawback_selections=dialog.drawback_selections,
                base_choice=dialog.base_sphere_choice,
                drawback_granted_talents=dialog.drawback_granted_talents,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot gain sphere", str(error))
            return
        self._magic_talents_changed()

    def _acquire_magic_sphere(
        self,
        sphere_name: str,
        drawback_key: str = "",
        drawback_selections: tuple[tuple[str, str], ...] | None = None,
        base_choice: str = "",
        drawback_granted_talents: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        if self.character_id is None:
            raise ValueError("No character is open.")
        sphere = magic_sphere(sphere_name)
        if sphere is None:
            raise ValueError("Choose a valid magic sphere.")
        owned = self.repository.list_spells(self.character_id)
        if any(
            spell.catalog_category == "Base Sphere"
            and spell.school_or_sphere.casefold() == sphere_name.casefold()
            for spell in owned
        ):
            raise ValueError(f"The {sphere_name} sphere is already on this character.")
        selections = (
            drawback_selections
            if drawback_selections is not None
            else ((drawback_key, ""),) if drawback_key else ()
        )
        available_drawbacks = {
            str(entry["key"]): entry
            for entry in magic_entries(sphere_name)
            if entry["category"] == "Drawback"
        }
        drawbacks: list[tuple[dict, str]] = []
        for key, choice in selections:
            drawback = available_drawbacks.get(key)
            if drawback is None:
                raise ValueError("Choose drawbacks belonging to this sphere.")
            drawbacks.append((drawback, choice.strip()))
        self.repository.add_spell(
            self.character_id,
            name=f"{sphere_name} Sphere",
            system="Sphere",
            school_or_sphere=sphere_name,
            notes=str(sphere["description"]),
            catalog_key=f"{sphere['slug']}:base",
            catalog_category="Base Sphere",
            source_url=str(sphere["source_url"]),
            choice=base_choice,
        )
        for drawback, choice in drawbacks:
            self._add_magic_catalog_entry(
                drawback,
                allow_build_entry=True,
                preset_choice=choice,
            )
            self._add_magic_drawback_grants(
                drawback,
                (drawback_granted_talents or {}).get(str(drawback["key"]), ()),
            )

    def _add_magic_drawback_grants(
        self, drawback: dict, talent_keys: tuple[str, ...]
    ) -> None:
        """Persist constrained drawback grants through the normal feature paths."""

        if self.character_id is None:
            return
        owned_magic = {
            spell.catalog_key
            for spell in self.repository.list_spells(self.character_id)
            if spell.catalog_key
        }
        entries_by_key = {str(entry["key"]): entry for entry in magic_entries()}
        for key in talent_keys:
            entry = entries_by_key.get(str(key))
            if entry is not None and str(key) not in owned_magic:
                self._add_magic_catalog_entry(entry)
                owned_magic.add(str(key))
        owned_feat_names = {
            feat.name.casefold() for feat in self.repository.list_feats(self.character_id)
        }
        for name in drawback_bonus_feat_names(drawback):
            if name.casefold() in owned_feat_names:
                continue
            entry = next(
                (
                    candidate for candidate in feat_entries()
                    if str(candidate.get("name", "")).casefold() == name.casefold()
                ),
                None,
            )
            if entry is not None:
                self._add_catalog_feat(entry)
                owned_feat_names.add(name.casefold())

    def _edit_build_drawbacks(self, *_args, sphere_name: str = "") -> None:
        if self.character_id is None:
            return
        sphere_name = sphere_name or self._selected_build_sphere()
        if not sphere_name:
            return
        spells = self.repository.list_spells(self.character_id)
        existing = tuple(
            (spell.catalog_key, spell.choice)
            for spell in spells
            if spell.school_or_sphere.casefold() == sphere_name.casefold()
            and spell.catalog_category == "Drawback"
        )
        base_sphere_record = next(
            (
                spell
                for spell in spells
                if spell.school_or_sphere.casefold() == sphere_name.casefold()
                and spell.catalog_category == "Base Sphere"
            ),
            None,
        )
        dialog = SphereAcquisitionDialog(
            set(),
            self,
            fixed_sphere=sphere_name,
            existing_drawbacks=existing,
            existing_base_choice=(base_sphere_record.choice if base_sphere_record else ""),
            owned_catalog_keys={spell.catalog_key for spell in spells if spell.catalog_key},
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entries = {
            str(entry["key"]): entry
            for entry in magic_entries(sphere_name)
            if entry["category"] == "Drawback"
        }
        proposed_drawbacks = [
            SimpleNamespace(
                catalog_category="Drawback",
                school_or_sphere=sphere_name,
                name=str(entries[key]["name"]),
                choice=choice,
            )
            for key, choice in dialog.drawback_selections
        ]
        other_spells = [
            spell
            for spell in spells
            if not (
                spell.school_or_sphere.casefold() == sphere_name.casefold()
                and spell.catalog_category == "Drawback"
            )
        ]
        prospective = other_spells + proposed_drawbacks
        conflicts = []
        for spell in other_spells:
            if (
                spell.school_or_sphere.casefold() != sphere_name.casefold()
                or spell.catalog_category in {"Base Sphere", "Drawback"}
                or not spell.catalog_key
            ):
                continue
            entry = next(
                (item for item in magic_entries(sphere_name) if item["key"] == spell.catalog_key),
                None,
            )
            if entry is not None:
                reason = magic_talent_restriction_reason(entry, prospective)
                if reason:
                    conflicts.append(f"{spell.name}: {reason}")
        if conflicts:
            QMessageBox.warning(
                self,
                "Existing talents conflict",
                "Remove these talents before applying the new drawbacks:\n\n"
                + "\n".join(conflicts),
            )
            return
        for spell in spells:
            if (
                spell.school_or_sphere.casefold() == sphere_name.casefold()
                and spell.catalog_category == "Drawback"
            ):
                self.repository.delete_spell(self.character_id, spell.id)
        if base_sphere_record is not None and dialog.base_sphere_choice != base_sphere_record.choice:
            self.repository.update_spell(
                self.character_id,
                base_sphere_record.id,
                name=base_sphere_record.name,
                system=base_sphere_record.system,
                level=base_sphere_record.level,
                school_or_sphere=base_sphere_record.school_or_sphere,
                uses_max=base_sphere_record.uses_max,
                uses_used=base_sphere_record.uses_used,
                casting_time=base_sphere_record.casting_time,
                range=base_sphere_record.range,
                duration=base_sphere_record.duration,
                save=base_sphere_record.save,
                spell_resistance=base_sphere_record.spell_resistance,
                notes=base_sphere_record.notes,
                catalog_key=base_sphere_record.catalog_key,
                catalog_category=base_sphere_record.catalog_category,
                prerequisites=base_sphere_record.prerequisites,
                source_url=base_sphere_record.source_url,
                choice=dialog.base_sphere_choice,
                effects=base_sphere_record.effects,
                activation=base_sphere_record.activation,
                activation_note=base_sphere_record.activation_note,
            )
        for key, choice in dialog.drawback_selections:
            self._add_magic_catalog_entry(
                entries[key], allow_build_entry=True, preset_choice=choice
            )
            self._add_magic_drawback_grants(
                entries[key], dialog.drawback_granted_talents.get(key, ())
            )
        self._magic_talents_changed()

    def _remove_build_sphere(self) -> None:
        if self.character_id is None:
            return
        sphere_name = self._selected_build_sphere()
        if not sphere_name:
            return
        self._delete_magic_sphere_cascade(sphere_name)
        self._magic_talents_changed()

    def _delete_magic_sphere_cascade(self, sphere_name: str) -> None:
        """Remove one magic sphere, including talents, drawbacks and derived state."""

        if self.character_id is None:
            return
        related = tuple(
            spell for spell in self.repository.list_spells(self.character_id)
            if spell.system == "Sphere"
            and spell.school_or_sphere.casefold() == sphere_name.casefold()
        )
        bonus_feat_names = {
            feat_name.casefold()
            for drawback in related
            if drawback.catalog_category == "Drawback"
            for feat_name in drawback_bonus_feat_names({
                "sphere": drawback.school_or_sphere,
                "name": drawback.name,
            })
        }
        for spell in related:
            self.repository.delete_spell(self.character_id, spell.id)
        for feat in self.repository.list_feats(self.character_id):
            if feat.name.casefold() in bonus_feat_names:
                self.repository.delete_feat(self.character_id, feat.id)
        self._clear_numeric_formulas(
            "sphere_stat",
            0,
            tuple(_sphere_stat_formula_keys(sphere_name).values()),
        )
        self.repository.delete_sphere_statistic(self.character_id, sphere_name)

    def _refresh_spells(self) -> None:
        if self.character_id is None:
            return
        sorting = self.spell_table.isSortingEnabled()
        sort_column = self.spell_table.horizontalHeader().sortIndicatorSection()
        sort_order = self.spell_table.horizontalHeader().sortIndicatorOrder()
        self.spell_table.setSortingEnabled(False)
        self.spell_table.setRowCount(0)
        saved_spells = self.repository.list_spells(self.character_id)
        display_rows = [
            *granted_sphere_abilities(saved_spells),
            *(
                spell
                for spell in saved_spells
                if spell.system == "Sphere"
                and spell.catalog_category not in {"Base Sphere", "Drawback"}
            ),
        ]
        for spell in display_rows:
            row = self.spell_table.rowCount()
            self.spell_table.insertRow(row)
            presentation = spell_record_presentation(spell, saved_spells)
            effects = _feat_effects_display(spell)
            if not spell.enabled:
                effects = f"Inactive — {effects}"
            values = presentation.values()
            tooltip_details = "\n\n".join(
                value
                for value in (
                    f"Sphere / system: {presentation.sphere}",
                    f"Spell cost: {presentation.cost}",
                    f"Casting: {presentation.action}; Range: {presentation.range}; Duration: {presentation.duration}",
                    f"Save: {presentation.save}; Spell resistance: {presentation.spell_resistance}",
                    f"Choice: {spell.choice}" if spell.choice else "",
                    f"Prerequisites: {spell.prerequisites}" if spell.prerequisites else "",
                    f"Automatic effects: {_feat_effects_display(spell)}",
                    spell.notes,
                )
                if value
            )
            tooltip = self._readable_tooltip(spell.name, tooltip_details)
            for column, value in enumerate(values):
                sort_value = value.casefold()
                if column == 1:
                    match = next(iter(re.findall(r"\d+", value)), "999999")
                    sort_value = int(match)
                cell = SortableTableItem(value, sort_value)
                cell.setData(
                    Qt.ItemDataRole.UserRole,
                    getattr(spell, "id", None)
                    or getattr(spell, "source_id", None)
                    or getattr(spell, "key", ""),
                )
                cell.setData(
                    Qt.ItemDataRole.UserRole + 1,
                    bool(getattr(spell, "source_id", 0)),
                )
                cell.setToolTip(tooltip)
                if not spell.enabled:
                    cell.setForeground(Qt.GlobalColor.gray)
                if spell.system == "Sphere":
                    cell.setBackground(QColor("#DAE9F8"))
                self.spell_table.setItem(row, column, cell)
        self.spell_table.setSortingEnabled(sorting)
        if sorting and 0 <= sort_column < self.spell_table.columnCount():
            self.spell_table.sortItems(sort_column, sort_order)
        self._refresh_spells_known(saved_spells)
        self._refresh_prepared_spells()
        self._refresh_spell_level_overview(saved_spells)
        self._refresh_selected_spell_save_dc()
        self._refresh_spell_book_dialog()

    def _refresh_spell_level_overview(
        self, saved_spells: tuple[Spell, ...] | list[Spell]
    ) -> None:
        """Render existing repertoire and prepared-slot calculations without new state."""

        known_by_level = {level: 0 for level in range(10)}
        for spell in saved_spells:
            if (
                spell.system != "Sphere"
                and spell.catalog_category not in {"Base Sphere", "Drawback"}
                and 0 <= int(spell.level) <= 9
            ):
                known_by_level[int(spell.level)] += 1

        casting_ability_aliases = {
            "int": "intelligence",
            "intelligence": "intelligence",
            "wis": "wisdom",
            "wisdom": "wisdom",
            "cha": "charisma",
            "charisma": "charisma",
        }
        casting_modifiers = [
            self._ability_result(
                casting_ability_aliases.get(
                    str(casting.get("ability") or "").casefold(), "intelligence"
                )
            ).ability_modifier
            for _class_level, casting in self._traditional_casting_classes()
        ]
        best_casting_modifier = max(casting_modifiers, default=None)
        prepared_casters = self._prepared_caster_capacities()
        spontaneous_casters = self._spontaneous_caster_capacities()

        table = self.spell_level_overview_table
        for level in range(10):
            total_slots = sum(
                caster.slots[level]
                for caster in prepared_casters
                if level < len(caster.slots)
            ) + sum(
                caster.total_slots[level]
                for caster in spontaneous_casters
                if level < len(caster.total_slots)
            )
            bonus_slots = sum(
                bonus_spell_slots(
                    self._ability_result(caster.casting_ability).ability_modifier,
                    level,
                )
                for caster in prepared_casters
                if level < len(caster.slots) and caster.slots[level] > 0
            ) + sum(
                caster.bonus_slots[level]
                for caster in spontaneous_casters
                if level < len(caster.bonus_slots)
            )
            values = (
                str(known_by_level[level]),
                str(10 + level + best_casting_modifier)
                if best_casting_modifier is not None
                else "—",
                "0" if level == 0 else self._ordinal_spell_level(level),
                str(total_slots) if total_slots else "—",
                str(bonus_slots) if level > 0 and bonus_slots else "—",
            )
            tooltip = self._readable_tooltip(
                f"Spell level {level}",
                "This read-only row summarizes the existing Spells Known and "
                "prepared-caster slot calculations. Save DC uses the highest "
                "applicable casting-ability modifier when the character has "
                "multiple traditional casting classes.",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setToolTip(tooltip)
                table.setItem(level, column, cell)
        self._refresh_spontaneous_slots(spontaneous_casters)

    @staticmethod
    def _ordinal_spell_level(level: int) -> str:
        if level == 1:
            return "1st"
        if level == 2:
            return "2nd"
        if level == 3:
            return "3rd"
        return f"{level}th"

    def _refresh_spells_known(self, saved_spells: tuple[Spell, ...] | list[Spell]) -> None:
        table = self.spells_known_table
        sorting = table.isSortingEnabled()
        sort_column = table.horizontalHeader().sortIndicatorSection()
        sort_order = table.horizontalHeader().sortIndicatorOrder()
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for spell in saved_spells:
            if spell.system == "Sphere" or spell.catalog_category in {"Base Sphere", "Drawback"}:
                continue
            row = table.rowCount()
            table.insertRow(row)
            tooltip_details = "\n\n".join(
                value
                for value in (
                    f"Spell level: {spell.level}",
                    f"School: {spell.school_or_sphere or '—'}",
                    f"Casting time: {spell.casting_time or '—'}; Range: {spell.range or '—'}; Duration: {spell.duration or '—'}",
                    f"Save: {spell.save or '—'}; Spell resistance: {spell.spell_resistance or '—'}",
                    spell.notes,
                )
                if value
            )
            tooltip = self._readable_tooltip(spell.name, tooltip_details)
            values = (
                (spell.name, spell.name.casefold()),
                (str(spell.level), int(spell.level)),
                (spell.school_or_sphere or "—", (spell.school_or_sphere or "").casefold()),
                (spell.casting_time or "—", (spell.casting_time or "").casefold()),
                (spell.range or "—", (spell.range or "").casefold()),
            )
            for column, (value, sort_value) in enumerate(values):
                cell = SortableTableItem(value, sort_value)
                cell.setData(Qt.ItemDataRole.UserRole, spell.id)
                cell.setToolTip(tooltip)
                if not spell.enabled:
                    cell.setForeground(Qt.GlobalColor.gray)
                table.setItem(row, column, cell)
        table.setSortingEnabled(sorting)
        if sorting and 0 <= sort_column < table.columnCount():
            table.sortItems(sort_column, sort_order)

    def _prepared_caster_capacities(self) -> tuple[PreparedCasterCapacity, ...]:
        if self.character_id is None:
            return ()
        return shared_prepared_caster_capacities(
            self.repository, self.character_id
        )

    def _spontaneous_caster_capacities(
        self,
    ) -> tuple[SpontaneousCasterCapacity, ...]:
        if self.character_id is None:
            return ()
        return shared_spontaneous_caster_capacities(
            self.repository, self.character_id
        )

    def _refresh_spontaneous_slots(
        self,
        casters: tuple[SpontaneousCasterCapacity, ...] | None = None,
    ) -> None:
        if self.character_id is None:
            return
        casters = casters if casters is not None else self._spontaneous_caster_capacities()
        self.spontaneous_slot_usage_panel.setVisible(bool(casters))
        table = self.spontaneous_slot_table
        table.setRowCount(0)
        used_by_key = {
            (item.class_level_id, item.spell_level): item.used_count
            for item in self.repository.list_spontaneous_slot_uses(self.character_id)
        }
        for caster in casters:
            for level, maximum in enumerate(caster.total_slots):
                if level == 0 or maximum <= 0:
                    continue
                used = used_by_key.get((caster.class_level_id, level), 0)
                row = table.rowCount()
                table.insertRow(row)
                values = (
                    caster.class_name,
                    str(level),
                    str(maximum),
                    str(used),
                    str(max(0, maximum - used)),
                )
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setData(
                        Qt.ItemDataRole.UserRole,
                        (caster.class_level_id, level, maximum),
                    )
                    if column > 0:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, column, cell)

    def _selected_spontaneous_slot(self) -> tuple[int, int, int] | None:
        row = self.spontaneous_slot_table.currentRow()
        if row < 0:
            return None
        cell = self.spontaneous_slot_table.item(row, 0)
        value = cell.data(Qt.ItemDataRole.UserRole) if cell is not None else None
        if not isinstance(value, tuple) or len(value) != 3:
            return None
        return int(value[0]), int(value[1]), int(value[2])

    def _use_spontaneous_slot(self) -> None:
        if self.character_id is None or (selected := self._selected_spontaneous_slot()) is None:
            return
        class_level_id, level, maximum = selected
        current = next(
            (
                item.used_count
                for item in self.repository.list_spontaneous_slot_uses(self.character_id)
                if item.class_level_id == class_level_id and item.spell_level == level
            ),
            0,
        )
        if current >= maximum:
            return
        self.repository.set_spontaneous_slot_uses(
            self.character_id, class_level_id, level, current + 1
        )
        self._refresh_spells()

    def _restore_spontaneous_slot(self) -> None:
        if self.character_id is None or (selected := self._selected_spontaneous_slot()) is None:
            return
        class_level_id, level, _maximum = selected
        current = next(
            (
                item.used_count
                for item in self.repository.list_spontaneous_slot_uses(self.character_id)
                if item.class_level_id == class_level_id and item.spell_level == level
            ),
            0,
        )
        if current <= 0:
            return
        self.repository.set_spontaneous_slot_uses(
            self.character_id, class_level_id, level, current - 1
        )
        self._refresh_spells()

    def _prepared_counts_by_level(self) -> dict[tuple[int, int], int]:
        if self.character_id is None:
            return {}
        result: dict[tuple[int, int], int] = {}
        for spell in self.repository.list_prepared_spells(self.character_id):
            key = (spell.class_level_id, spell.level)
            result[key] = result.get(key, 0) + spell.prepared_count
        return result

    def _refresh_prepared_spells(self) -> None:
        if self.character_id is None:
            return
        casters = self._prepared_caster_capacities()
        caster_by_id = {caster.class_level_id: caster for caster in casters}
        prepared = self.repository.list_prepared_spells(self.character_id)
        counts = self._prepared_counts_by_level()
        self.spell_slot_table.setRowCount(0)
        for caster in casters:
            for level, capacity in enumerate(caster.slots):
                if capacity <= 0:
                    continue
                used = counts.get((caster.class_level_id, level), 0)
                row = self.spell_slot_table.rowCount()
                self.spell_slot_table.insertRow(row)
                for column, value in enumerate(
                    (caster.class_name, str(level), str(capacity), str(used), str(max(0, capacity - used)))
                ):
                    cell = QTableWidgetItem(value)
                    if column > 0:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.spell_slot_table.setItem(row, column, cell)
        table = self.spells_prepared_table
        sorting = table.isSortingEnabled()
        sort_column = table.horizontalHeader().sortIndicatorSection()
        sort_order = table.horizontalHeader().sortIndicatorOrder()
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for spell in prepared:
            caster = caster_by_id.get(spell.class_level_id)
            class_name = caster.class_name if caster else "Unavailable class"
            row = table.rowCount()
            table.insertRow(row)
            values = (
                (spell.name, spell.name.casefold()),
                (class_name, class_name.casefold()),
                (str(spell.level), spell.level),
                (str(spell.prepared_count), spell.prepared_count),
                ("At will" if spell.level == 0 else str(spell.remaining), spell.remaining),
                ("Custom" if spell.custom else "Known", int(spell.custom)),
            )
            for column, (value, sort_value) in enumerate(values):
                cell = SortableTableItem(value, sort_value)
                cell.setData(Qt.ItemDataRole.UserRole, spell.id)
                cell.setToolTip(
                    self._readable_tooltip(
                        spell.name,
                        f"{class_name} · spell level {spell.level}\n\n"
                        f"Prepared {spell.prepared_count}; remaining {spell.remaining}; "
                        f"expended {spell.used_count}.\n\n"
                        + ("Custom catalog preparation for a special rule." if spell.custom else "Prepared from Spells Known."),
                    )
                )
                table.setItem(row, column, cell)
        table.setSortingEnabled(sorting)
        if sorting and 0 <= sort_column < table.columnCount():
            table.sortItems(sort_column, sort_order)

    def _selected_prepared_spell(self):
        if self.character_id is None or self.spells_prepared_table.currentRow() < 0:
            return None
        spell_id = self.spells_prepared_table.item(
            self.spells_prepared_table.currentRow(), 0
        ).data(Qt.ItemDataRole.UserRole)
        return next(
            (spell for spell in self.repository.list_prepared_spells(self.character_id) if spell.id == spell_id),
            None,
        )

    def _store_prepared_dialog(self, dialog: PreparedSpellDialog) -> None:
        if self.character_id is None or not dialog.values:
            return
        values = dialog.values
        caster = next(
            item for item in self._prepared_caster_capacities()
            if item.class_level_id == values["class_level_id"]
        )
        level = int(values.get("level", -1))
        if level < 0 and values.get("known_spell_id") is not None:
            known = next(
                spell for spell in self.repository.list_spells(self.character_id)
                if spell.id == values["known_spell_id"]
            )
            level = known.level
        counts = self._prepared_counts_by_level()
        counts[(caster.class_level_id, level)] = counts.get((caster.class_level_id, level), 0) + int(values["prepared_count"])
        validate_preparation_capacity(
            caster.slots,
            {spell_level: count for (class_id, spell_level), count in counts.items() if class_id == caster.class_level_id},
        )
        existing = next(
            (
                spell
                for spell in self.repository.list_prepared_spells(self.character_id)
                if spell.class_level_id == caster.class_level_id
                and (
                    (not values.get("custom") and spell.known_spell_id == values.get("known_spell_id"))
                    or (
                        values.get("custom") and spell.custom
                        and spell.catalog_key == values.get("catalog_key")
                    )
                )
            ),
            None,
        )
        if existing is not None:
            self.repository.update_prepared_spell_counts(
                self.character_id,
                existing.id,
                existing.prepared_count + int(values["prepared_count"]),
                existing.used_count,
            )
        else:
            self.repository.add_prepared_spell(self.character_id, **values)
        self._refresh_prepared_spells()

    def _prepare_known_spell(self) -> None:
        if self.character_id is None:
            return
        known = tuple(spell for spell in self.repository.list_spells(self.character_id) if spell.system != "Sphere")
        dialog = PreparedSpellDialog(
            self._prepared_caster_capacities(), known, self._prepared_counts_by_level(), parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._store_prepared_dialog(dialog)
            except ValueError as error:
                QMessageBox.warning(self, "Cannot prepare spell", str(error))

    def _prepare_custom_spell(self) -> None:
        if self.character_id is None:
            return
        casters = self._prepared_caster_capacities()
        browser = TraditionalSpellCatalogDialog(
            tuple(caster.class_name for caster in casters),
            self,
            multi_select=False,
        )
        if browser.exec() != QDialog.DialogCode.Accepted or browser.selected_entry is None:
            return
        dialog = PreparedSpellDialog(
            casters, (), self._prepared_counts_by_level(), browser.selected_entry, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._store_prepared_dialog(dialog)
            except ValueError as error:
                QMessageBox.warning(self, "Cannot prepare custom spell", str(error))

    def _use_prepared_spell(self) -> None:
        spell = self._selected_prepared_spell()
        if spell is None or self.character_id is None or spell.level == 0 or spell.remaining <= 0:
            return
        self.repository.update_prepared_spell_counts(
            self.character_id, spell.id, spell.prepared_count, spell.used_count + 1
        )
        self._refresh_prepared_spells()

    def _restore_prepared_spell(self) -> None:
        spell = self._selected_prepared_spell()
        if spell is None or self.character_id is None or spell.used_count <= 0:
            return
        self.repository.update_prepared_spell_counts(
            self.character_id, spell.id, spell.prepared_count, spell.used_count - 1
        )
        self._refresh_prepared_spells()

    def _change_prepared_spell_count(self) -> None:
        spell = self._selected_prepared_spell()
        if spell is None or self.character_id is None:
            return
        caster = next(
            (item for item in self._prepared_caster_capacities() if item.class_level_id == spell.class_level_id),
            None,
        )
        if caster is None or spell.level >= len(caster.slots):
            return
        other = self._prepared_counts_by_level().get((spell.class_level_id, spell.level), 0) - spell.prepared_count
        maximum = max(1, caster.slots[spell.level] - other)
        value, accepted = QInputDialog.getInt(
            self, "Prepared copies", f"How many copies of {spell.name}?", spell.prepared_count, 1, maximum
        )
        if not accepted:
            return
        self.repository.update_prepared_spell_counts(
            self.character_id, spell.id, value, min(spell.used_count, value)
        )
        self._refresh_prepared_spells()

    def _remove_prepared_spell(self) -> None:
        spell = self._selected_prepared_spell()
        if spell is None or self.character_id is None:
            return
        self.repository.delete_prepared_spell(self.character_id, spell.id)
        self._refresh_prepared_spells()

    def _selected_spell(self, table: QTableWidget | None = None) -> Spell | None:
        table = table or self.spell_table
        if self.character_id is None or table.currentRow() < 0:
            return None
        spell_id = table.item(table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return next(
            (
                spell
                for spell in self.repository.list_spells(self.character_id)
                if spell.id == spell_id
            ),
            None,
        )

    def _select_spell_for_summary(self, source: str) -> None:
        self._selected_spell_summary_source = source
        self._refresh_selected_spell_save_dc()

    def _refresh_selected_spell_save_dc(self) -> None:
        """Show the save DC of the last traditional or Sphere spell clicked."""

        label = getattr(self, "_play_casting_labels", {}).get("save_dc")
        if label is None or self.character_id is None:
            return
        source = self._selected_spell_summary_source
        prepared = self._selected_prepared_spell() if source == "prepared" else None
        table = self.spells_known_table if source == "traditional" else self.spell_table
        spell = None if source == "prepared" else self._selected_spell(table)
        if spell is None and prepared is None:
            label.setText("—")
            label.setToolTip("Click a spell or sphere effect to display its save DC.")
            return
        calculator = self._calculator()
        if prepared is not None or source == "traditional" or spell.system != "Sphere":
            spell_name = prepared.name if prepared is not None else spell.name
            spell_level = prepared.level if prepared is not None else spell.level
            ability_aliases = {
                "str": "strength", "dex": "dexterity", "con": "constitution",
                "int": "intelligence", "wis": "wisdom", "cha": "charisma",
            }
            abilities = []
            for class_level, casting in self._traditional_casting_classes():
                if prepared is not None and class_level.id != prepared.class_level_id:
                    continue
                ability = str(casting.get("ability") or "").casefold()
                ability = ability_aliases.get(ability, ability)
                if ability in ABILITY_KEYS:
                    abilities.append(ability)
            if not abilities:
                abilities.append(calculator.resolved_casting_profile().casting_ability)
            ability = max(
                abilities,
                key=lambda key: calculator.ability_result(key).ability_modifier,
            )
            modifier = calculator.ability_result(ability).ability_modifier
            value = 10 + int(spell_level) + modifier + calculator.automatic_total("save_dc")
            label.setText(str(value))
            label.setToolTip(
                f"{spell_name}: 10 + spell level {spell_level} + "
                f"{ability.title()} modifier {modifier:+d}."
            )
            return

        profile = calculator.resolved_casting_profile()
        ability_modifier = calculator.ability_result(
            profile.casting_ability
        ).ability_modifier
        statistic = calculator.resolved_sphere_statistic(
            next(
                (
                    item for item in self.repository.list_sphere_statistics(self.character_id)
                    if item.sphere.casefold() == spell.school_or_sphere.casefold()
                ),
                SphereStatistic(self.character_id, spell.school_or_sphere),
            )
        )
        value = calculate_casting_statistics(
            profile,
            ability_modifier,
            statistic.caster_level_bonus
            + self._prodigy_sequence_bonus()
            + calculator.automatic_total("caster_level"),
            statistic.dc_bonus
            + calculator.automatic_total("save_dc")
            + calculator.sphere_dc_bonus(spell.school_or_sphere),
        ).save_dc
        label.setText(str(value))
        label.setToolTip(
            f"{spell.name}: current {spell.school_or_sphere or 'Sphere'} save DC."
        )

    def _add_spell(
        self,
        *,
        selection_limit: int = 0,
        sphere_only: bool = False,
    ) -> None:
        if self.character_id is None:
            return
        choice = "spheres"
        if (
            not sphere_only
            and self._class_capabilities.traditional_spells
            and self._class_capabilities.magic
        ):
            chooser = MagicCatalogChoiceDialog(self)
            if chooser.exec() != QDialog.DialogCode.Accepted:
                return
            choice = chooser.choice
        elif not sphere_only and self._class_capabilities.traditional_spells:
            choice = "traditional"
        if choice == "traditional":
            self._add_traditional_spell(selection_limit=selection_limit)
            return
        dialog = MagicTalentCatalogDialog(
            self.repository.list_spells(self.character_id),
            self,
            play_mode=True,
            selection_limit=selection_limit,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self._add_custom_spell()
            return
        self._add_catalog_batch(
            self._catalog_dialog_entries(dialog),
            self._add_magic_catalog_entry,
            self._magic_talents_changed,
            "magic talents",
        )

    def _open_spell_book(self) -> None:
        if self.character_id is None:
            return
        dialog = self._spell_book_dialog
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog = SpellBookDialog(
            SpellBookService(self.repository, self.character_id), self
        )
        dialog.resources_changed.connect(self._spell_book_resources_changed)
        dialog.destroyed.connect(self._forget_spell_book_dialog)
        self._spell_book_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_martial_book(self) -> None:
        if self.character_id is None:
            return
        dialog = self._martial_book_dialog
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog = MartialBookDialog(
            MartialBookService(self.repository, self.character_id), self
        )
        dialog.resources_changed.connect(self._martial_book_resources_changed)
        dialog.destroyed.connect(self._forget_martial_book_dialog)
        self._martial_book_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_martial_book_dialog(self, *_args) -> None:
        self._martial_book_dialog = None

    def _refresh_martial_book_dialog(self) -> None:
        dialog = self._martial_book_dialog
        if (
            dialog is not None
            and dialog.isVisible()
            and dialog.service.character_id == self.character_id
        ):
            dialog.refresh()

    def _martial_book_resources_changed(self) -> None:
        self._refresh_martial_focus()
        self._refresh_formula_dependents()

    def _open_inventory(self) -> None:
        if self.character_id is None:
            return
        dialog = self._inventory_dialog
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog = InventoryOrganizerDialog(
            InventoryOrganizationService(self.repository, self.character_id),
            self,
            edit_item=self._edit_equipment_by_id,
        )
        dialog.destroyed.connect(self._forget_inventory_dialog)
        dialog.organization_changed.connect(self._inventory_organization_changed)
        self._inventory_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_equipment_figure(self):
        if self.character_id is None:
            return
        if self._equipment_figure_dialog is None:
            from app.equipment_wearing import EquipmentWearService
            from app.ui.equipment_figure import EquipmentFigureDialog
            dialog = EquipmentFigureDialog(EquipmentWearService(self.repository, self.character_id), self)
            dialog.equipment_changed.connect(self._equipment_usage_changed)
            dialog.destroyed.connect(lambda: setattr(self, "_equipment_figure_dialog", None)
                                     if self._equipment_figure_dialog is dialog else None)
            self._equipment_figure_dialog = dialog
        self._equipment_figure_dialog.refresh()
        self._equipment_figure_dialog.show()
        self._equipment_figure_dialog.raise_()

    def _drop_equipment(self, item_id, slot):
        if self.character_id is None:
            return
        from app.equipment_wearing import EquipmentWearService
        service = EquipmentWearService(self.repository, self.character_id)
        try:
            if slot: service.equip(item_id, slot)
            else: service.unequip(item_id)
        except ValueError as error:
            self.worn_table.setToolTip(str(error))
            return
        self._equipment_usage_changed()

    def _inventory_organization_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_equipment,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_movement,
            self._refresh_formula_dependents,
        )

    def _forget_inventory_dialog(self, *_args) -> None:
        self._inventory_dialog = None

    def _refresh_inventory_dialog(self) -> None:
        dialog = self._inventory_dialog
        if (
            dialog is not None
            and dialog.isVisible()
            and dialog.service.character_id == self.character_id
        ):
            dialog.refresh()

    def _forget_spell_book_dialog(self, *_args) -> None:
        self._spell_book_dialog = None

    def _refresh_spell_book_dialog(self) -> None:
        dialog = self._spell_book_dialog
        if (
            dialog is not None
            and dialog.isVisible()
            and dialog.service.character_id == self.character_id
        ):
            dialog.refresh()

    def _spell_book_resources_changed(self) -> None:
        self._refresh_spells()
        self._refresh_casting_profile()

    def _traditional_casting_classes(self) -> tuple[tuple[object, dict], ...]:
        if self.character_id is None:
            return ()
        return shared_traditional_casting_classes(
            self.repository, self.character_id
        )

    def _add_traditional_spell(self, *, selection_limit: int = 0) -> None:
        if self.character_id is None:
            return
        traditional_classes = self._traditional_casting_classes()
        preferred_names = tuple(str(class_level.class_name) for class_level, _casting in traditional_classes)
        dialog = TraditionalSpellCatalogDialog(
            preferred_names,
            self,
            multi_select=selection_limit != 1,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self._add_custom_spell()
            return
        entries = self._catalog_dialog_entries(dialog)
        self._add_catalog_batch(
            entries,
            lambda entry: self._add_traditional_catalog_entry(
                entry, traditional_classes
            ),
            self._refresh_spells,
            "spells",
        )

    def _add_traditional_catalog_entry(
        self,
        entry: dict,
        traditional_classes: tuple[tuple[object, dict], ...],
    ) -> bool:
        if self.character_id is None:
            return False
        selected_level = int(entry.get("level") or 0)
        selected_method = "Prepared"
        for class_level, casting in traditional_classes:
            matched = spell_level_for_class(entry, str(class_level.class_name))
            if matched is not None:
                selected_level = int(matched)
                method = str(casting.get("type") or "prepared").casefold()
                selected_method = "Spontaneous" if method == "spontaneous" else "Prepared"
                break
        self.repository.add_spell(
            self.character_id,
            name=str(entry["name"]),
            system=selected_method,
            level=selected_level,
            school_or_sphere=str(entry.get("school") or ""),
            casting_time=str(entry.get("casting_time") or ""),
            range=str(entry.get("range") or ""),
            duration=str(entry.get("duration") or ""),
            save=str(entry.get("saving_throw") or ""),
            spell_resistance=str(entry.get("spell_resistance") or ""),
            notes=str(entry.get("description") or ""),
            catalog_key=str(entry["key"]),
            catalog_category=f"{entry.get('source_group', 'Pathfinder')} Traditional Spell",
            source_url=str(entry.get("source_url") or ""),
        )
        return True

    def _add_custom_spell(self) -> None:
        if self.character_id is None:
            return
        dialog = SpellDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.add_spell(self.character_id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add spell", str(error))
            return
        self._magic_talents_changed()

    def _add_magic_catalog_entry(
        self,
        entry: dict,
        allow_build_entry: bool = False,
        preset_choice: str = "",
    ) -> bool:
        if self.character_id is None:
            return False
        automation = dict(entry.get("automation", {}))
        choice = preset_choice.strip()
        choice_key = ""
        choice_type = str(automation.get("choice_type", ""))
        if choice_type:
            choice_dialog = FeatChoiceDialog(
                choice_type,
                str(automation.get("choice_label", "Choice")),
                self.repository.list_attacks(self.character_id),
                self.repository.list_equipment(self.character_id),
                self,
            )
            if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            choice = choice_dialog.choice
            choice_key = choice_dialog.choice_key
        effects: list[dict] = []
        for source_effect in automation.get("effects", []):
            effect = dict(source_effect)
            effect["target"] = str(effect.get("target", "")).replace(
                "{choice_key}", choice_key
            )
            effect["scope"] = str(effect.get("scope", "")).replace(
                "{choice_key}", choice_key
            )
            effects.append(effect)
        owned = self.repository.list_spells(self.character_id)
        owned_keys = {spell.catalog_key for spell in owned if spell.catalog_key}
        if entry["key"] in owned_keys:
            raise ValueError("This magic sphere, talent, or drawback is already on the character.")
        category = str(entry["category"])
        sphere_name = str(entry["sphere"])
        if category in {"Base Sphere", "Drawback"} and not allow_build_entry:
            raise ValueError(
                "Base spheres and their sphere-specific drawbacks are chosen on Page 0."
            )
        if category == "Base Sphere" and allow_build_entry and not choice:
            options = base_sphere_choice_options(sphere_name, "magic")
            if options:
                selected, accepted = QInputDialog.getItem(
                    self,
                    f"{sphere_name} starting choice",
                    base_sphere_choice_label(sphere_name, "magic"),
                    list(options),
                    0,
                    False,
                )
                if not accepted:
                    return False
                choice = str(selected)
        if category != "Base Sphere" and sphere_name != "Universal":
            sphere = magic_sphere(sphere_name)
            if sphere is not None:
                base_key = f"{sphere['slug']}:base"
                has_base = base_key in owned_keys or any(
                    spell.school_or_sphere.casefold() == sphere_name.casefold()
                    and (
                        spell.catalog_category == "Base Sphere"
                        or (
                            spell.system == "Sphere"
                            and spell.name.casefold() == f"{sphere_name} sphere".casefold()
                        )
                    )
                    for spell in owned
                )
                if not has_base:
                    raise ValueError(
                        f"Gain the {sphere_name} base sphere and choose its sphere "
                        "drawbacks on Page 0 before adding talents."
                    )
        if category not in {"Base Sphere", "Drawback"}:
            restriction = magic_talent_restriction_reason(entry, owned)
            if restriction:
                raise ValueError(restriction)
        spell_id = self.repository.add_spell(
            self.character_id,
            name=str(entry["name"]),
            system="Sphere",
            school_or_sphere=sphere_name,
            notes=str(entry["description"]),
            catalog_key=str(entry["key"]),
            catalog_category=category,
            prerequisites=str(entry.get("prerequisites", "")),
            source_url=str(entry.get("source_url", "")),
            choice=choice,
            effects=effects,
            activation=str(automation.get("activation", "always")),
            activation_note=str(automation.get("activation_note", "")),
        )
        if automation and not bool(automation.get("default_enabled", True)):
            self.repository.set_spell_enabled(self.character_id, spell_id, False)
        return True

    def _edit_spell(self, *_args) -> None:
        if (
            self.spell_table.currentRow() >= 0
            and bool(
                self.spell_table.item(self.spell_table.currentRow(), 0).data(
                    Qt.ItemDataRole.UserRole + 1
                )
            )
        ):
            spell = self._selected_spell()
            if spell is not None:
                self._edit_build_drawbacks(
                    sphere_name=spell.school_or_sphere
                )
            return
        spell = self._selected_spell()
        if spell is None or self.character_id is None:
            QMessageBox.information(self, "Select a spell", "Select a spell or magic ability row first.")
            return
        dialog = SpellDialog(self, spell)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_spell(self.character_id, spell.id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit spell", str(error))
            return
        self._magic_talents_changed()

    def _edit_spell_duration(self, *_args) -> None:
        """Edit the duration for saved and generated Sphere table rows."""

        spell = self._selected_spell()
        if spell is None or self.character_id is None:
            QMessageBox.information(
                self,
                "Select a sphere effect",
                "Select a spell or magic ability row first.",
            )
            return
        displayed = self.spell_table.item(self.spell_table.currentRow(), 5)
        current = displayed.text() if displayed is not None else spell.duration
        value, accepted = QInputDialog.getText(
            self,
            "Edit duration",
            f"Duration for {self.spell_table.item(self.spell_table.currentRow(), 0).text()}",
            text=current if current != "/" else "",
        )
        if not accepted:
            return
        try:
            self.repository.update_spell_duration(
                self.character_id, spell.id, value
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit duration", str(error))
            return
        self._magic_talents_changed()

    def _edit_known_spell(self, *_args) -> None:
        spell = self._selected_spell(self.spells_known_table)
        if spell is None or self.character_id is None:
            QMessageBox.information(self, "Select a spell", "Select a known spell row first.")
            return
        dialog = SpellDialog(self, spell)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update_spell(self.character_id, spell.id, **dialog.values)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot edit spell", str(error))
            return
        self._magic_talents_changed()

    def _toggle_spell(self) -> None:
        spell = self._selected_spell()
        if spell is None or self.character_id is None:
            QMessageBox.information(
                self, "Select a spell", "Select a spell or magic ability row first."
            )
            return
        self.repository.set_spell_enabled(
            self.character_id, spell.id, not spell.enabled
        )
        self._magic_talents_changed()

    def _use_spell(self) -> None:
        spell = self._selected_spell()
        if spell is None or self.character_id is None:
            QMessageBox.information(self, "Select a spell", "Select a spell or magic ability row first.")
            return
        if spell.uses_max == 0:
            QMessageBox.information(self, spell.name, "This entry is at will and does not consume uses.")
            return
        if spell.uses_used >= spell.uses_max:
            QMessageBox.information(self, spell.name, "This entry has no uses remaining.")
            return
        self.repository.set_spell_uses_used(self.character_id, spell.id, spell.uses_used + 1)
        self._refresh_spells()

    def _reset_spell_uses(self) -> None:
        spell = self._selected_spell()
        if spell is None or self.character_id is None:
            QMessageBox.information(self, "Select a spell", "Select a spell or magic ability row first.")
            return
        if spell.uses_max:
            self.repository.set_spell_uses_used(self.character_id, spell.id, 0)
            self._refresh_spells()

    def _remove_spell(self) -> None:
        spell = self._selected_spell()
        if spell is None or self.character_id is None:
            QMessageBox.information(self, "Select a spell", "Select a spell or magic ability row first.")
            return
        if spell.catalog_category == "Base Sphere":
            self._delete_magic_sphere_cascade(spell.school_or_sphere)
        else:
            self.repository.delete_spell(self.character_id, spell.id)
        self._magic_talents_changed()

    def _remove_known_spell(self) -> None:
        spell = self._selected_spell(self.spells_known_table)
        if spell is None or self.character_id is None:
            QMessageBox.information(self, "Select a spell", "Select a known spell row first.")
            return
        self.repository.delete_spell(self.character_id, spell.id)
        self._magic_talents_changed()

    def _magic_talents_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_spells,
            self._refresh_sphere_build,
            self._refresh_prodigy_sphere_rules,
            self._refresh_sequence_options,
            self._refresh_prodigy_imbues,
            self._refresh_abilities,
            self._refresh_casting_profile,
            self._refresh_sphere_statistics,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_hit_points,
            self._refresh_advancement_budgets,
            self._refresh_formula_dependents,
        )

    def _refresh_conditions(self) -> None:
        if self.character_id is None:
            return
        conditions = self.repository.list_conditions(self.character_id)
        ongoing_effects = self._calculator().resolved_ongoing_effects()
        self.condition_table.setRowCount(0)
        for condition in conditions:
            row = self.condition_table.rowCount()
            self.condition_table.insertRow(row)
            effects = ", ".join(
                f"{target.replace('_', ' ').title()} {value:+d}"
                for target, value in CONDITION_PRESETS[condition.name]
            )
            values = (condition.name, effects or "No calculated effect")
            tooltip = self._readable_tooltip(
                condition.name,
                f"Effects: {effects or 'None'}"
                + (f"\n\n{condition.notes}" if condition.notes else ""),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, ("condition", condition.id))
                cell.setToolTip(tooltip)
                if not condition.enabled:
                    cell.setForeground(Qt.GlobalColor.gray)
                self.condition_table.setItem(row, column, cell)
        for effect in ongoing_effects:
            row = self.condition_table.rowCount()
            self.condition_table.insertRow(row)
            modifier = (
                f"{effect.target.replace('_', ' ').title()} {effect.value:+d} "
                f"({effect.bonus_type})"
                if effect.target
                else "Tracked effect"
            )
            effect_summary = " · ".join(
                value for value in (effect.source_type, effect.duration, modifier) if value
            )
            tooltip = self._readable_tooltip(
                effect.name,
                effect_summary + (f"\n\n{effect.notes}" if effect.notes else ""),
            )
            for column, value in enumerate((effect.name, effect_summary)):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, ("ongoing_effect", effect.id))
                cell.setToolTip(tooltip)
                if not effect.enabled:
                    cell.setForeground(Qt.GlobalColor.gray)
                self.condition_table.setItem(row, column, cell)
        fit_table_rows(
            self.condition_table, len(conditions) + len(ongoing_effects), 2, 5
        )

    def _selected_condition_or_effect(self):
        if self.character_id is None or self.condition_table.currentRow() < 0:
            return None
        item = self.condition_table.item(self.condition_table.currentRow(), 0)
        if item is None:
            return None
        identity = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(identity, (tuple, list)) or len(identity) != 2:
            # Migration-friendly fallback for rows created by an older view.
            identity = ("condition", identity)
        kind, record_id = str(identity[0]), int(identity[1])
        records = (
            self.repository.list_conditions(self.character_id)
            if kind == "condition"
            else self.repository.list_ongoing_effects(self.character_id)
        )
        record = next((entry for entry in records if entry.id == record_id), None)
        return (kind, record) if record is not None else None

    def _selected_condition(self):
        selected = self._selected_condition_or_effect()
        return selected[1] if selected is not None and selected[0] == "condition" else None

    def _add_condition(self) -> None:
        if self.character_id is None:
            return
        dialog = ConditionDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.add_condition(self.character_id, dialog.name, dialog.notes)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add condition", str(error))
            return
        self._conditions_changed()

    def _toggle_condition(self) -> None:
        self._toggle_condition_or_effect()

    def _add_ongoing_effect(self) -> None:
        if self.character_id is None:
            return
        dialog = OngoingEffectDialog(
            self,
            formula_evaluator=self._evaluate_character_formula,
            formula_suggestions=self._character_formula_suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            effect_id = self.repository.add_ongoing_effect(
                self.character_id, **dialog.values
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add effect", str(error))
            return
        self._save_numeric_formulas(
            "ongoing_effect", effect_id, dialog.numeric_formulas
        )
        self._conditions_changed()

    def _edit_condition_or_effect(self, *_args) -> None:
        selected = self._selected_condition_or_effect()
        if selected is None or self.character_id is None:
            QMessageBox.information(
                self, "Select an entry", "Select a condition or ongoing effect first."
            )
            return
        kind, record = selected
        if kind == "condition":
            dialog = ConditionDialog(self)
            dialog.condition.setCurrentText(record.name)
            dialog.notes_input.setText(record.notes)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            # Conditions are preset-backed. Replacing the visual record keeps
            # the repository API small and preserves the enabled state.
            self.repository.delete_condition(self.character_id, record.id)
            new_id = self.repository.add_condition(
                self.character_id, dialog.name, dialog.notes
            )
            if not record.enabled:
                self.repository.set_condition_enabled(
                    self.character_id, new_id, False
                )
        else:
            dialog = OngoingEffectDialog(
                self,
                record,
                formulas=self._saved_numeric_formulas(
                    "ongoing_effect", record.id
                ),
                formula_evaluator=self._evaluate_character_formula,
                formula_suggestions=self._character_formula_suggestions,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            self.repository.update_ongoing_effect(
                self.character_id, record.id, **dialog.values
            )
            self._save_numeric_formulas(
                "ongoing_effect", record.id, dialog.numeric_formulas
            )
        self._conditions_changed()

    def _toggle_condition_or_effect(self) -> None:
        selected = self._selected_condition_or_effect()
        if selected is None or self.character_id is None:
            QMessageBox.information(
                self, "Select an entry", "Select a condition or ongoing effect first."
            )
            return
        kind, record = selected
        if kind == "condition":
            self.repository.set_condition_enabled(
                self.character_id, record.id, not record.enabled
            )
        else:
            self.repository.set_ongoing_effect_enabled(
                self.character_id, record.id, not record.enabled
            )
        self._conditions_changed()

    def _remove_condition(self) -> None:
        selected = self._selected_condition_or_effect()
        if selected is None or self.character_id is None:
            QMessageBox.information(
                self, "Select an entry", "Select a condition or ongoing effect first."
            )
            return
        kind, record = selected
        if kind == "condition":
            self.repository.delete_condition(self.character_id, record.id)
        else:
            self.repository.delete_ongoing_effect(self.character_id, record.id)
        self._conditions_changed()

    def _conditions_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_conditions,
            self._refresh_abilities,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_formula_dependents,
        )

    def _refresh_equipment(self) -> None:
        if self.character_id is None:
            return
        items = self.repository.list_equipment(self.character_id)
        placements = self.repository.list_inventory_placements(self.character_id)
        display_items = ordered_inventory_items(items, placements)
        enchantments = self.repository.list_item_enchantments(self.character_id)
        resolved_item_modifiers = item_modifiers(items)
        self.equipment_table.setRowCount(0)
        inventory_value = 0.0
        for item, parent_id, depth in display_items:
            price_breakdown = item_price_breakdown(item, enchantments)
            item_price = price_breakdown.total_gp
            inventory_value += item_price * item.quantity
            state = effective_item_state(item)
            automation = automation_for_item(item)
            choices = item_choices(item)
            resolved_effects = []
            for effect in automation.effects:
                active, reason = effect_is_active(item, effect.activation)
                if active and effect.operation in {"add", "set"}:
                    choice_target = choices.get(effect.choice_group, "") if effect.choice_group else effect.target
                    breakdown = calculate_stat(
                        [], resolved_item_modifiers.get(choice_target, [])
                    )
                    source = f"Item: {item.name} — {effect.label or effect.key}"
                    contribution = next(
                        (value for value in breakdown.contributions if value.source == source),
                        None,
                    )
                    if contribution is not None:
                        active = contribution.applied
                        reason = contribution.reason
                resolved_effects.append(
                    f"{'Active' if active else 'Inactive'} — "
                    f"{effect.label or effect.key}: {reason}"
                )
            row = self.equipment_table.rowCount()
            self.equipment_table.insertRow(row)
            values = (
                item_display_name(item, enchantments),
                " · ".join(
                    value for value in (state.title(), item.slot) if value
                ),
                str(item.quantity),
                " · ".join(
                    value
                    for value in (
                        (
                            f"{item_price * item.quantity:g} gp"
                            if item_price else ""
                        ),
                        f"{item.weight * item.quantity:g} lb",
                    )
                    if value
                ),
                "; ".join(
                    value
                    for value in (
                        (
                            f"AC {item.ac_bonus:+d} {item.bonus_type}"
                            if item.ac_bonus else ""
                        ),
                        (
                            f"Max Dex +{item.max_dex_bonus}"
                            if item.max_dex_bonus is not None else ""
                        ),
                        (
                            f"ACP -{item.armor_check_penalty}"
                            if item.armor_check_penalty else ""
                        ),
                        item.notes,
                    )
                    if value
                ) or "—",
            )
            tooltip = self._readable_tooltip(
                item.name,
                "\n\n".join(
                    value
                    for value in (
                        f"{item.category}; slot: {item.slot or 'None'}; quantity: {item.quantity}",
                        (
                            f"Weight: {item.weight * item.quantity:g} lb; "
                            f"market value: {item_price * item.quantity:g} gp"
                        ),
                        (
                            "Price: "
                            + "; ".join(
                                value for value in (
                                    f"base {price_breakdown.base_value_gp:g} gp",
                                    (
                                        f"masterwork +{price_breakdown.masterwork_gp:g} gp"
                                        if price_breakdown.masterwork_gp else ""
                                    ),
                                    (
                                        f"magic {price_breakdown.enhancement_gp:+g} gp"
                                        if price_breakdown.enhancement_gp else ""
                                    ),
                                    (
                                        f"flat properties +{price_breakdown.flat_properties_gp:g} gp"
                                        if price_breakdown.flat_properties_gp else ""
                                    ),
                                ) if value
                            )
                        ),
                        f"Armor bonus: {item.ac_bonus:+d} {item.bonus_type}" if item.ac_bonus else "",
                        (
                            f"Enhancement bonus: {effective_enhancement_bonus(item):+d}"
                            if effective_enhancement_bonus(item) else ""
                        ),
                        f"Enchantments: {enchantment_summary(item, enchantments)}",
                        "Masterwork weapon" if item.masterwork else "",
                        f"Weapon: {item.weapon_damage_dice}; {item.weapon_critical}; {item.weapon_range}" if item.weapon_damage_dice else "",
                        f"Automation: {'Requires Choice' if automation.status == 'choice' else automation.status.replace('_', ' ').title()}",
                        f"Resolved effects: {automation_summary(automation)}",
                        "\n".join(resolved_effects),
                        (
                            "Choices: "
                            + ", ".join(f"{key.replace('_', ' ').title()} = {value}" for key, value in choices.items())
                            if choices else ""
                        ),
                        item.notes,
                    )
                    if value
                ),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.id)
                cell.setToolTip(tooltip)
                if parent_id is not None:
                    cell.setBackground(self.equipment_table.palette().alternateBase())
                    font = cell.font()
                    font.setItalic(True)
                    cell.setFont(font)
                    if column == 0:
                        cell.setIcon(
                            self.style().standardIcon(
                                QStyle.StandardPixmap.SP_ArrowRight
                            )
                        )
                elif is_inventory_container(item):
                    font = cell.font()
                    font.setBold(True)
                    cell.setFont(font)
                    if column == 0:
                        cell.setIcon(
                            self.style().standardIcon(
                                QStyle.StandardPixmap.SP_DirOpenIcon
                            )
                        )
                self.equipment_table.setItem(row, column, cell)
            if depth:
                self.equipment_table.setRowHeight(row, max(28, self.equipment_table.rowHeight(row)))
        weight = carried_inventory_weight(items, placements)
        self.weight_summary.setText(f"Total weight {weight:g} lb")
        value_text = f"{inventory_value:,.2f}".rstrip("0").rstrip(".")
        self.inventory_value_summary.setText(f"Inventory value {value_text} gp")
        self._refresh_worn_items(items, enchantments)
        self.optional_traditions_section.refresh()
        self._refresh_load(items)
        self._update_equipment_action_buttons()
        self._refresh_inventory_dialog()
        if self._equipment_figure_dialog is not None:
            self._equipment_figure_dialog.refresh()

    def _selected_equipment(self):
        if self.character_id is None or self.equipment_table.currentRow() < 0:
            return None
        item_id = self.equipment_table.item(self.equipment_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return next(
            item for item in self.repository.list_equipment(self.character_id) if item.id == item_id
        )

    def _add_equipment(self) -> None:
        if self.character_id is None:
            return
        browser = ItemCatalogDialog(self)
        if browser.exec() != QDialog.DialogCode.Accepted:
            return
        numeric_formulas: dict[str, str] = {}
        if browser.custom_requested:
            dialog = EquipmentDialog(
                self,
                worn_slots=self.repository.list_worn_slots(self.character_id),
                formulas={},
                formula_evaluator=self._evaluate_character_formula,
                formula_suggestions=self._character_formula_suggestions,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            values = dialog.values
            numeric_formulas = dialog.numeric_formulas
            item_id = self.repository.add_equipment(self.character_id, **values)
            self._save_numeric_formulas("equipment", item_id, numeric_formulas)
            self._refresh_calculation_views(
                self._refresh_equipment,
                self._refresh_combat,
                self._refresh_skills,
                self._refresh_formula_dependents,
            )
            return

        added = 0
        failures: list[str] = []
        for entry in self._catalog_dialog_entries(browser):
            values = browser.values_for_entry(entry)
            automation = automation_from_json(
                str(values.get("automation_json") or "")
            )
            if automation.choices:
                choice_dialog = ItemChoiceDialog(
                    str(values["name"]), automation, "{}", self
                )
                if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                    failures.append(
                        f"{values['name']}: required item choices were cancelled."
                    )
                    continue
                values["choices_json"] = choice_dialog.choices_json
            try:
                self.repository.add_equipment(self.character_id, **values)
                added += 1
            except ValueError as error:
                failures.append(f"{values['name']}: {error}")

        if added:
            self._refresh_calculation_views(
                self._refresh_equipment,
                self._refresh_combat,
                self._refresh_skills,
                self._refresh_formula_dependents,
            )
        if failures:
            visible = failures[:10]
            if len(failures) > len(visible):
                visible.append(f"…and {len(failures) - len(visible)} more")
            QMessageBox.warning(
                self,
                "Some items were not added",
                "\n".join(visible),
            )

    def _edit_equipment(self, *_args) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None:
            QMessageBox.information(self, "Select an item", "Select an equipment row first.")
            return
        self._edit_equipment_record(item)

    def _edit_equipment_by_id(self, item_id: int) -> None:
        if self.character_id is None:
            return
        item = next(
            (
                value
                for value in self.repository.list_equipment(self.character_id)
                if value.id == int(item_id)
            ),
            None,
        )
        if item is not None:
            self._edit_equipment_record(item)

    def _edit_equipment_record(self, item) -> None:
        if self.character_id is None:
            return
        organization = InventoryOrganizationService(
            self.repository, self.character_id
        )
        dialog = EquipmentDialog(
            self,
            item,
            worn_slots=self.repository.list_worn_slots(self.character_id),
            enchantments=tuple(
                value for value in self.repository.list_item_enchantments(
                    self.character_id, item.id
                )
            ),
            contained_items=organization.contents(item.id),
            **self._formula_dialog_options("equipment", item.id),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.update_equipment(self.character_id, item.id, **dialog.values)
        self._save_numeric_formulas(
            "equipment", item.id, dialog.numeric_formulas
        )
        self._refresh_equipment()
        self._refresh_combat()
        self._refresh_skills()
        self._refresh_formula_dependents()

    def _toggle_equipment(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None:
            return
        self.repository.set_equipment_equipped(
            self.character_id,
            item.id,
            effective_item_state(item) == "stored",
        )
        self._equipment_usage_changed()

    def _update_equipment_action_buttons(self) -> None:
        if not hasattr(self, "wear_item_button"):
            return
        item = self._selected_equipment()
        if item is None:
            self.wear_item_button.setEnabled(False)
            self.remove_item_button.setEnabled(False)
            return
        current = effective_item_state(item)
        preferred = preferred_item_state(item)
        self.wear_item_button.setEnabled(item.quantity > 0 and current != preferred)
        self.remove_item_button.setEnabled(item.quantity > 0 and current != "stored")

    def _wear_equipment(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None or item.quantity <= 0:
            return
        if effective_item_state(item) == preferred_item_state(item):
            return
        self.repository.set_equipment_equipped(self.character_id, item.id, True)
        self._equipment_usage_changed()

    def _remove_equipment_from_use(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None or item.quantity <= 0:
            return
        if effective_item_state(item) == "stored":
            return
        self.repository.set_equipment_equipped(self.character_id, item.id, False)
        self._equipment_usage_changed()

    def _equipment_usage_changed(self) -> None:
        self._refresh_calculation_views(
            self._refresh_equipment,
            self._refresh_combat,
            self._refresh_skills,
            self._refresh_formula_dependents,
        )

    def _change_equipment_state(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None:
            QMessageBox.information(self, "Select an item", "Select an equipment row first.")
            return
        labels = {
            "stored": "Stored / inactive", "carried": "Carried", "worn": "Worn",
            "wielded": "Wielded", "armor": "Equipped armor", "shield": "Equipped shield",
        }
        options = list(labels)
        selected, accepted = QInputDialog.getItem(
            self, "Item state", f"How is {item.name} currently used?",
            [labels[value] for value in options], options.index(item.state), False,
        )
        if not accepted:
            return
        state = next(value for value, label in labels.items() if label == selected)
        self.repository.set_equipment_state(self.character_id, item.id, state)
        self.refresh_all()

    def _edit_equipment_choices(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None:
            QMessageBox.information(self, "Select an item", "Select an equipment row first.")
            return
        automation = automation_for_item(item)
        if not automation.choices:
            QMessageBox.information(self, "No choices", "This item has no catalog-defined choices.")
            return
        dialog = ItemChoiceDialog(item.name, automation, item.choices_json, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.set_equipment_choices(self.character_id, item.id, dialog.choices_json)
        self.refresh_all()

    def _enchant_equipment(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None:
            QMessageBox.information(
                self, "Select an item", "Select an equipment row first."
            )
            return
        dialog = ItemEnchantmentsDialog(
            self.repository, self.character_id, item, self
        )
        dialog.exec()
        if dialog.changed:
            self.refresh_all()

    def _remove_equipment(self) -> None:
        item = self._selected_equipment()
        if item is None or self.character_id is None:
            QMessageBox.information(self, "Select an item", "Select an equipment row first.")
            return
        self._clear_numeric_formulas("equipment", item.id)
        self.repository.delete_equipment(self.character_id, item.id)
        self._refresh_equipment()
        self._refresh_combat()
        self._refresh_skills()
        self._refresh_formula_dependents()

    def _automatic_attack_effects(
        self, attack: Attack, bab: int
    ) -> tuple[list, list]:
        if self.character_id is None:
            return [], []
        return self._calculator().attack_effects(attack, bab)

    def _refresh_attacks(
        self, calculator: CharacterCalculationService | None = None
    ) -> None:
        if self.character_id is None:
            return
        calculator = calculator or self._calculator()
        attacks = calculator.attacks()
        equipment = calculator.resolved_equipment()
        bab = total_bab(calculator.resolved_classes())
        size = calculator.state.details.size
        abilities = calculator.ability_results()
        automatic_modifiers = calculator.automatic_modifier_map()
        blocker = QSignalBlocker(self.attack_table)
        self.attack_table.setUpdatesEnabled(False)
        try:
            self.attack_table.setRowCount(0)
            for attack in attacks:
                if not calculator.attack_is_visible(attack):
                    continue
                weapon = next(
                    (item for item in equipment if item.id == attack.equipment_id), None
                )
                profile = calculator.resolve_attack_profile(attack)
                resolved_attack = profile.attack
                feat_attack, feat_damage = calculator.attack_effects(attack, bab)
                result = calculate_attack(
                    resolved_attack,
                    bab,
                    abilities,
                    size,
                    automatic_modifiers.get("attack", []) + feat_attack,
                    automatic_modifiers.get("damage", []) + feat_damage,
                    extra_damage=profile.extra_damage,
                )
                row = self.attack_table.rowCount()
                self.attack_table.insertRow(row)
                values = (
                    attack.name,
                    resolved_attack.attack_type,
                    f"{result.attack_bonus:+d}",
                    result.damage_display,
                    resolved_attack.critical,
                    "\n".join(value for value in (attack.notes, *profile.conditional_effects) if value),
                )
                tooltip = self._readable_tooltip(
                    attack.name,
                    f"{resolved_attack.attack_type}; attack {result.attack_bonus:+d}; "
                    f"damage {result.damage_display}; critical {resolved_attack.critical}"
                    + (
                        f"\nLinked inventory weapon: {weapon.name} ({effective_item_state(weapon)})"
                        if weapon is not None else ""
                    )
                    + (
                        "\n\nRules:\n" + "\n".join(profile.sources)
                        if profile.sources else ""
                    )
                    + (
                        "\n\nConditional enchantment rules:\n"
                        + "\n".join(profile.conditional_effects)
                        if profile.conditional_effects else ""
                    )
                    + (f"\n\n{attack.notes}" if attack.notes else ""),
                )
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setData(Qt.ItemDataRole.UserRole, attack.id)
                    cell.setToolTip(tooltip)
                    self.attack_table.setItem(row, column, cell)
        finally:
            self.attack_table.setUpdatesEnabled(True)
            del blocker

    def _selected_attack(self) -> Attack | None:
        if self.character_id is None or self.attack_table.currentRow() < 0:
            return None
        attack_id = self.attack_table.item(self.attack_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return next(
            (item for item in self._calculator().attacks() if item.id == attack_id),
            None,
        )

    def _add_attack(self) -> None:
        if self.character_id is None:
            return
        calculator = self._calculator()
        formula_context = calculator.formula_context()
        dialog = AttackDialog(
            self,
            equipment=self.repository.list_equipment(self.character_id),
            formula_evaluator=formula_context.evaluate,
            damage_formula_evaluator=formula_context.evaluate_symbolic_dice,
            formula_suggestions=formula_context.suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        attack_id = self.repository.add_attack(self.character_id, **dialog.values)
        for field_key, expression in dialog.numeric_formulas.items():
            self.repository.set_numeric_formula(
                self.character_id, "attack", attack_id, field_key, expression
            )
        self._refresh_attacks()

    def _add_conditional_attack(self) -> None:
        if self.character_id is None:
            return
        formula_context = self._calculator().formula_context()
        dialog = AttackDialog(
            self,
            equipment=self.repository.list_equipment(self.character_id),
            formula_evaluator=formula_context.evaluate,
            damage_formula_evaluator=formula_context.evaluate_symbolic_dice,
            formula_suggestions=formula_context.suggestions,
            conditional=True,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        attack_id = self.repository.add_attack(self.character_id, **dialog.values)
        self._save_numeric_formulas(
            "attack", attack_id, dialog.numeric_formulas
        )
        self._refresh_attacks()

    def _manage_conditional_attacks(self) -> None:
        """Open a saved conditional attack even while its live row is hidden."""

        if self.character_id is None:
            return
        attacks = tuple(
            attack for attack in self.repository.list_attacks(self.character_id)
            if attack.visibility_condition.strip()
        )
        if not attacks:
            return
        calculator = self._calculator()
        labels = [
            f"{'Visible' if calculator.attack_is_visible(attack) else 'Hidden'} — {attack.name}"
            for attack in attacks
        ]
        label, accepted = QInputDialog.getItem(
            self,
            "Conditional attacks",
            "Choose an attack to edit",
            labels,
            0,
            False,
        )
        if not accepted:
            return
        attack = attacks[labels.index(label)]
        formulas = {
            field_key: expression
            for (_entity_type, _entity_id, field_key), expression
            in self.repository.numeric_formulas(
                self.character_id, "attack", attack.id
            ).items()
        }
        formula_context = calculator.formula_context()
        dialog = AttackDialog(
            self,
            attack,
            self.repository.list_equipment(self.character_id),
            formulas=formulas,
            formula_evaluator=formula_context.evaluate,
            damage_formula_evaluator=formula_context.evaluate_symbolic_dice,
            formula_suggestions=formula_context.suggestions,
            conditional=True,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.update_attack(
            self.character_id, attack.id, **dialog.values
        )
        self._save_numeric_formulas(
            "attack", attack.id, dialog.numeric_formulas
        )
        self._refresh_attacks()

    def _edit_attack(self, *_args) -> None:
        attack = self._selected_attack()
        if attack is None or self.character_id is None:
            QMessageBox.information(self, "Select an attack", "Select an attack row first.")
            return
        if attack.id < 0:
            return
        formulas = {
            field_key: expression
            for (_entity_type, _entity_id, field_key), expression
            in self.repository.numeric_formulas(
                self.character_id, "attack", attack.id
            ).items()
        }
        formula_context = self._calculator().formula_context()
        dialog = AttackDialog(
            self,
            attack,
            self.repository.list_equipment(self.character_id),
            formulas=formulas,
            formula_evaluator=formula_context.evaluate,
            damage_formula_evaluator=formula_context.evaluate_symbolic_dice,
            formula_suggestions=formula_context.suggestions,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.update_attack(self.character_id, attack.id, **dialog.values)
        for field_key, expression in dialog.numeric_formulas.items():
            self.repository.set_numeric_formula(
                self.character_id, "attack", attack.id, field_key, expression
            )
        self._refresh_attacks()

    def _remove_attack(self) -> None:
        attack = self._selected_attack()
        if attack is None or self.character_id is None:
            QMessageBox.information(self, "Select an attack", "Select an attack row first.")
            return
        if attack.id < 0:
            return
        self.repository.delete_attack(self.character_id, attack.id)
        self._refresh_attacks()

    def _roll_attack(self) -> None:
        attack = self._selected_attack()
        if attack is None or self.character_id is None:
            QMessageBox.information(self, "Select an attack", "Select an attack row first.")
            return
        automatic_modifiers = self._automatic_modifier_map()
        weapon = next(
            (
                item
                for item in self.repository.list_equipment(self.character_id)
                if item.id == attack.equipment_id
            ),
            None,
        )
        calculator = self._calculator()
        profile = calculator.resolve_attack_profile(attack)
        resolved_attack = profile.attack
        bab = total_bab(calculator.resolved_classes())
        feat_attack, feat_damage = calculator.attack_effects(attack, bab)
        result = calculate_attack(
            resolved_attack,
            bab,
            self._ability_results(),
            self.repository.get_character_details(self.character_id).size,
            automatic_modifiers.get("attack", []) + feat_attack,
            automatic_modifiers.get("damage", []) + feat_damage,
            extra_damage=profile.extra_damage,
        )
        natural, attack_total, damage_total, damage_rolls = roll_attack_and_damage(
            result, resolved_attack.damage_dice
        )
        threat_match = re.match(r"(?:(\d+)-)?20", resolved_attack.critical)
        threat_start = int(threat_match.group(1) or 20) if threat_match else 20
        special = "\nCritical threat!" if natural >= threat_start else ""
        if natural == 1:
            special = "\nNatural 1 — automatic miss."
        QMessageBox.information(
            self,
            f"{attack.name} roll",
            f"Attack: d20 ({natural}) {result.attack_bonus:+d} = {attack_total}"
            f"\nDamage: {result.damage_display}"
            f"\nRolled dice: {list(damage_rolls)} {result.damage_bonus:+d} = {damage_total}"
            f"\nCritical: {resolved_attack.critical}{special}",
        )

    def _show_ability_breakdown(self, ability: str, title: str) -> None:
        self._show_breakdown(ability, title, partial(self._ability_result, ability))

    def _show_combat_breakdown(self, target: str, title: str) -> None:
        self._show_breakdown(target, title, lambda: self._combat_results()[target])

    def _show_breakdown(
        self, target: str, title: str, result_provider: Callable[[], CalculationResult]
    ) -> None:
        if self.character_id is None:
            return
        dialog = _FormulaStatBreakdownDialog(
            self.repository,
            self.character_id,
            target,
            title,
            result_provider,
            self._evaluate_character_formula,
            self._character_formula_suggestions,
            self,
        )
        dialog.exec()
        self._refresh_abilities()
        self._refresh_combat()
        self._refresh_skills()
        self._refresh_formula_dependents()
