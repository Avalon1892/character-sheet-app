from __future__ import annotations

import json
import math
import re
import sqlite3
from app.engineering_rules import is_battery, TECH_BATTERY_KEY, tech_battery_capacity,device_condition,JET_BOOSTERS_KEY,JET_MODES
from datetime import datetime
from pathlib import Path

from app.models import (
    ABILITY_KEYS,
    ALIGNMENTS,
    ATTACK_TYPES,
    BAB_PROGRESSIONS,
    BONUS_TYPES,
    CHARACTER_TYPES,
    SAVE_PROGRESSIONS,
    SIZES,
    STAT_TARGETS,
    DYNAMIC_EFFECT_TARGET_PREFIXES,
    CharacterDetails,
    RaceTraitChoice,
    CharacterSummary,
    ClassLevel,
    ProficiencyAdjustment,
    SpecialAbilityAdjustment,
    ClassFeatureSelection,
    ClassFeatureState,
    AnimalCompanion,
    BondedCompanion,
    DAMAGE_MULTIPLIERS,
    DAMAGE_ABILITY_MODES,
    EQUIPMENT_BONUS_TYPES,
    EQUIPMENT_CATEGORIES,
    EQUIPMENT_STATES,
    WORN_SLOTS,
    CONDITION_PRESETS,
    ONGOING_EFFECT_SOURCE_TYPES,
    MARTIAL_TALENT_TYPES,
    SKILLS,
    SEQUENCE_OPTION_TYPES,
    SPELL_SYSTEMS,
    Attack,
    AbilityScoreIncreaseAllocation,
    AdvancementAdjustment,
    CastingProfile,
    CharacterTradition,
    Condition,
    OngoingEffect,
    CurrencyPurse,
    CustomTracker,
    Feat,
    FeatEffect,
    EquipmentItem,
    InventoryPlacement,
    InventoryCustomGroup,
    FavoredClassBonus,
    ItemEnchantment,
    HitPoints,
    MartialFocus,
    MartialTalent,
    FlexibleTalentSelection,
    MovementProfile,
    PreparedSpell,
    SpontaneousSlotUse,
    ProdigySequence,
    SequenceOption,
    SkillState,
    SkillSpecialization,
    SheetNote,
    Spell,
    SphereStatistic,
    StatModifier,
    Trait,
    CUSTOM_TRACKER_TYPES,
    TRACKER_RECOVERY_EVENTS,
    TRACKER_RECOVERY_OPERATIONS,
)
from app.prodigy_content import UNIVERSAL_PRODIGY_OPTIONS
from app.formulas import FormulaError, parse_formula
from app.item_effects import (
    automation_from_json,
    preferred_item_state,
    validate_item_choices,
)


BASE_PRODIGY_OPTIONS = tuple(option.database_tuple() for option in UNIVERSAL_PRODIGY_OPTIONS)


class CharacterRepository:
    """Owns local character persistence and keeps SQL out of the UI."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    @property
    def sqlite_connection(self) -> sqlite3.Connection:
        """Shared connection for additive repositories stored in this database.

        Feature-specific repositories remain separate Python components, while
        sharing the transaction boundary avoids competing SQLite writers in the
        desktop process (particularly on Windows).
        """
        return self._connection

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                character_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_sheet_layouts (
                character_id INTEGER PRIMARY KEY
                    REFERENCES characters(id) ON DELETE CASCADE,
                state_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS special_ability_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                feature_key TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                hidden INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0, 1)),
                custom INTEGER NOT NULL DEFAULT 0 CHECK (custom IN (0, 1)),
                UNIQUE(character_id, feature_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS class_feature_selections (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_level_id INTEGER NOT NULL REFERENCES class_levels(id) ON DELETE CASCADE,
                feature_key TEXT NOT NULL,
                option_type TEXT NOT NULL DEFAULT '',
                option_key TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(character_id, class_level_id, feature_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS class_feature_states (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_level_id INTEGER NOT NULL REFERENCES class_levels(id) ON DELETE CASCADE,
                feature_key TEXT NOT NULL,
                current_value INTEGER,
                maximum_adjustment INTEGER NOT NULL DEFAULT 0,
                maximum_override INTEGER,
                active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
                choices_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(character_id, class_level_id, feature_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS animal_companions (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT '',
                species_key TEXT NOT NULL DEFAULT '',
                effective_level_adjustment INTEGER NOT NULL DEFAULT 0,
                effective_level_override INTEGER,
                current_hp INTEGER NOT NULL DEFAULT 0,
                temporary_hp INTEGER NOT NULL DEFAULT 0,
                ability_overrides_json TEXT NOT NULL DEFAULT '{}',
                skill_ranks_json TEXT NOT NULL DEFAULT '{}',
                feats_json TEXT NOT NULL DEFAULT '[]',
                tricks_json TEXT NOT NULL DEFAULT '[]',
                special_abilities_json TEXT NOT NULL DEFAULT '[]',
                details_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bonded_companions (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                companion_key TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                species TEXT NOT NULL DEFAULT '',
                current_hp INTEGER NOT NULL DEFAULT 0,
                temporary_hp INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(character_id, companion_key)
            )
            """
        )
        self._ensure_column("animal_companions", "details_json", "TEXT NOT NULL DEFAULT '{}'")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_rest_settings (
                character_id INTEGER PRIMARY KEY
                    REFERENCES characters(id) ON DELETE CASCADE,
                enabled_targets_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_audit_ignores (
                character_id INTEGER NOT NULL
                    REFERENCES characters(id) ON DELETE CASCADE,
                finding_key TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                PRIMARY KEY(character_id, finding_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_traditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                catalog_key TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('Casting', 'Martial', 'Crafting', 'Tinker')),
                choices_json TEXT NOT NULL DEFAULT '{}',
                grants_json TEXT NOT NULL DEFAULT '[]',
                definition_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(character_id, catalog_key)
            )
            """
        )
        self._ensure_column(
            "character_traditions", "definition_json", "TEXT NOT NULL DEFAULT '{}'"
        )
        from app.tradition_schema import widen_tradition_kinds
        widen_tradition_kinds(self._connection)
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_character_traditions_character "
            "ON character_traditions(character_id, kind)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS numeric_formulas (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                expression TEXT NOT NULL,
                PRIMARY KEY (character_id, entity_type, entity_id, field_key)
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_numeric_formulas_entity "
            "ON numeric_formulas(character_id, entity_type, entity_id)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS hit_points (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                maximum INTEGER NOT NULL DEFAULT 0 CHECK (maximum BETWEEN 0 AND 99999),
                current INTEGER NOT NULL DEFAULT 0 CHECK (current BETWEEN -9999 AND 99999),
                temporary INTEGER NOT NULL DEFAULT 0 CHECK (temporary BETWEEN 0 AND 99999),
                nonlethal INTEGER NOT NULL DEFAULT 0 CHECK (nonlethal BETWEEN 0 AND 99999),
                auto_calculate INTEGER NOT NULL DEFAULT 0 CHECK (auto_calculate IN (0, 1))
            )
            """
        )
        self._ensure_column(
            "hit_points", "auto_calculate", "INTEGER NOT NULL DEFAULT 0"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity BETWEEN 0 AND 9999),
                weight REAL NOT NULL DEFAULT 0 CHECK (weight >= 0),
                equipped INTEGER NOT NULL DEFAULT 0 CHECK (equipped IN (0, 1)),
                ac_bonus INTEGER NOT NULL DEFAULT 0,
                bonus_type TEXT NOT NULL DEFAULT 'untyped',
                max_dex_bonus INTEGER,
                armor_check_penalty INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                slot TEXT NOT NULL DEFAULT '',
                value_gp REAL NOT NULL DEFAULT 0 CHECK (value_gp >= 0)
            )
            """
        )
        self._ensure_column(
            "equipment", "armor_check_penalty", "INTEGER NOT NULL DEFAULT 0"
        )
        self._ensure_column("equipment", "slot", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "equipment", "value_gp", "REAL NOT NULL DEFAULT 0 CHECK (value_gp >= 0)"
        )
        self._ensure_column("equipment", "catalog_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "catalog_source", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "state", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "choices_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("equipment", "automation_json", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "enhancement_bonus", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("equipment", "masterwork", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("equipment", "weapon_damage_dice", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "weapon_damage_type", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "weapon_critical", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("equipment", "weapon_range", "TEXT NOT NULL DEFAULT ''")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worn_slot_catalogs (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                slots_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_item_placements (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                category TEXT NOT NULL CHECK (length(trim(category)) > 0),
                subcategory TEXT NOT NULL DEFAULT 'General',
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (character_id, equipment_id)
            )
            """
        )
        self._ensure_column(
            "inventory_item_placements", "container_equipment_id", "INTEGER"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_custom_groups (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                category TEXT NOT NULL CHECK (length(trim(category)) > 0),
                subcategory TEXT NOT NULL DEFAULT 'General',
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (character_id, category, subcategory)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment_enchantments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
                enchantment_key TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                bonus_equivalent INTEGER NOT NULL DEFAULT 0 CHECK (bonus_equivalent >= 0),
                notes TEXT NOT NULL DEFAULT '',
                UNIQUE (equipment_id, enchantment_key)
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_equipment_enchantments_item "
            "ON equipment_enchantments(equipment_id)"
        )
        # Properties require a +1 host. Repair records created before the
        # enchantment workflow supplied that prerequisite automatically.
        self._connection.execute(
            """
            UPDATE equipment
            SET enhancement_bonus = 1,
                masterwork = 1
            WHERE category IN ('Weapon', 'Armor', 'Shield')
              AND enhancement_bonus < 1
              AND EXISTS (
                  SELECT 1 FROM equipment_enchantments AS enchantment
                  WHERE enchantment.equipment_id = equipment.id
              )
            """
        )
        self._connection.execute(
            """
            UPDATE equipment
            SET masterwork = 1
            WHERE category IN ('Weapon', 'Armor', 'Shield')
              AND enhancement_bonus > 0
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS currency_purses (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                copper INTEGER NOT NULL DEFAULT 0 CHECK (copper >= 0),
                silver INTEGER NOT NULL DEFAULT 0 CHECK (silver >= 0),
                gold INTEGER NOT NULL DEFAULT 0 CHECK (gold >= 0),
                platinum INTEGER NOT NULL DEFAULT 0 CHECK (platinum >= 0),
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS attacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                attack_type TEXT NOT NULL,
                ability TEXT NOT NULL,
                attack_bonus INTEGER NOT NULL DEFAULT 0,
                damage_dice TEXT NOT NULL,
                damage_ability TEXT,
                damage_multiplier REAL NOT NULL DEFAULT 1,
                damage_bonus INTEGER NOT NULL DEFAULT 0,
                critical TEXT NOT NULL DEFAULT '20/x2',
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._ensure_column("attacks", "equipment_id", "INTEGER")
        self._ensure_column("attacks", "profile_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "attacks", "damage_ability_mode", "TEXT NOT NULL DEFAULT 'manual'"
        )
        self._ensure_column(
            "attacks", "visibility_condition", "TEXT NOT NULL DEFAULT ''"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                skill_key TEXT NOT NULL,
                ranks INTEGER NOT NULL DEFAULT 0 CHECK (ranks BETWEEN 0 AND 999),
                class_skill INTEGER NOT NULL DEFAULT 0 CHECK (class_skill IN (0, 1)),
                misc_bonus INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                ability_override TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (character_id, skill_key)
            )
            """
        )
        self._ensure_column("skills", "ability_override", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("skills", "class_skill_override", "INTEGER")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_specializations (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                skill_key TEXT NOT NULL,
                base_skill_key TEXT NOT NULL,
                specialty TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (character_id, skill_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sheet_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                page_key TEXT NOT NULL DEFAULT '',
                x INTEGER NOT NULL DEFAULT 80,
                y INTEGER NOT NULL DEFAULT 100,
                width INTEGER NOT NULL DEFAULT 360,
                height INTEGER NOT NULL DEFAULT 260,
                pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
                content_html TEXT NOT NULL DEFAULT '',
                toolbar_expanded INTEGER NOT NULL DEFAULT 0 CHECK (toolbar_expanded IN (0, 1)),
                visible INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1)),
                pages_json TEXT NOT NULL DEFAULT '[]',
                current_page INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._ensure_column("sheet_notes", "visible", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("sheet_notes", "pages_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("sheet_notes", "current_page", "INTEGER NOT NULL DEFAULT 0")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ongoing_effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                source_type TEXT NOT NULL DEFAULT 'Spell',
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                duration TEXT NOT NULL DEFAULT '',
                target TEXT NOT NULL DEFAULT '',
                bonus_type TEXT NOT NULL DEFAULT 'untyped',
                value INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                target TEXT NOT NULL DEFAULT '',
                bonus_type TEXT NOT NULL DEFAULT 'untyped',
                value INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                catalog_key TEXT NOT NULL DEFAULT '',
                catalog_category TEXT NOT NULL DEFAULT '',
                prerequisites TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                choice TEXT NOT NULL DEFAULT '',
                effects_json TEXT NOT NULL DEFAULT '[]',
                repeatable INTEGER NOT NULL DEFAULT 0 CHECK (repeatable IN (0, 1)),
                activation TEXT NOT NULL DEFAULT 'always',
                activation_note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._ensure_column("feats", "catalog_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("feats", "catalog_category", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("feats", "prerequisites", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("feats", "source_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("feats", "choice", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("feats", "effects_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(
            "feats", "repeatable", "INTEGER NOT NULL DEFAULT 0 CHECK (repeatable IN (0, 1))"
        )
        self._ensure_column("feats", "activation", "TEXT NOT NULL DEFAULT 'always'")
        self._ensure_column("feats", "activation_note", "TEXT NOT NULL DEFAULT ''")
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_feats_catalog ON feats(character_id, catalog_key)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS traits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                target TEXT NOT NULL DEFAULT '',
                bonus_type TEXT NOT NULL DEFAULT 'trait',
                value INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                catalog_key TEXT NOT NULL DEFAULT '',
                catalog_category TEXT NOT NULL DEFAULT '',
                prerequisites TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                choice TEXT NOT NULL DEFAULT '',
                effects_json TEXT NOT NULL DEFAULT '[]',
                repeatable INTEGER NOT NULL DEFAULT 0 CHECK (repeatable IN (0, 1)),
                activation TEXT NOT NULL DEFAULT 'always',
                activation_note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._ensure_column("traits", "catalog_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("traits", "catalog_category", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("traits", "prerequisites", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("traits", "source_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("traits", "choice", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("traits", "effects_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(
            "traits", "repeatable", "INTEGER NOT NULL DEFAULT 0 CHECK (repeatable IN (0, 1))"
        )
        self._ensure_column("traits", "activation", "TEXT NOT NULL DEFAULT 'always'")
        self._ensure_column("traits", "activation_note", "TEXT NOT NULL DEFAULT ''")
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_traits_catalog ON traits(character_id, catalog_key)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS martial_focus (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                current INTEGER NOT NULL DEFAULT 1 CHECK (current >= 0),
                maximum INTEGER NOT NULL DEFAULT 1 CHECK (maximum BETWEEN 1 AND 99),
                recovery_method TEXT NOT NULL DEFAULT 'Take a full-round action',
                notes TEXT NOT NULL DEFAULT '',
                CHECK (current <= maximum)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS casting_profiles (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                casting_ability TEXT NOT NULL DEFAULT 'charisma',
                casting_class_levels INTEGER NOT NULL DEFAULT 0 CHECK (casting_class_levels BETWEEN 0 AND 999),
                caster_level INTEGER NOT NULL DEFAULT 0 CHECK (caster_level BETWEEN 0 AND 999),
                msb_misc INTEGER NOT NULL DEFAULT 0,
                dc_misc INTEGER NOT NULL DEFAULT 0,
                concentration_misc INTEGER NOT NULL DEFAULT 0,
                spell_points_maximum INTEGER NOT NULL DEFAULT 0 CHECK (spell_points_maximum BETWEEN 0 AND 99999),
                spell_points_current INTEGER NOT NULL DEFAULT 0 CHECK (spell_points_current BETWEEN 0 AND 99999),
                spell_points_temporary INTEGER NOT NULL DEFAULT 0 CHECK (spell_points_temporary BETWEEN 0 AND 99999),
                spell_points_misc INTEGER NOT NULL DEFAULT 0,
                auto_spell_points INTEGER NOT NULL DEFAULT 0 CHECK (auto_spell_points IN (0, 1)),
                tradition_name TEXT NOT NULL DEFAULT '',
                tradition_boons TEXT NOT NULL DEFAULT '',
                tradition_drawbacks TEXT NOT NULL DEFAULT '',
                tradition_notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._ensure_column("casting_profiles", "spell_points_misc", "INTEGER NOT NULL DEFAULT 0")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sphere_statistics (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                sphere TEXT NOT NULL CHECK (length(trim(sphere)) > 0),
                caster_level_bonus INTEGER NOT NULL DEFAULT 0,
                dc_bonus INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (character_id, sphere)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS martial_talents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                sphere TEXT NOT NULL DEFAULT '',
                talent_type TEXT NOT NULL DEFAULT 'Talent',
                notes TEXT NOT NULL DEFAULT '',
                catalog_key TEXT NOT NULL DEFAULT '',
                catalog_category TEXT NOT NULL DEFAULT '',
                prerequisites TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                choice TEXT NOT NULL DEFAULT '',
                effects_json TEXT NOT NULL DEFAULT '[]',
                activation TEXT NOT NULL DEFAULT 'always',
                activation_note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._ensure_column("martial_talents", "catalog_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "martial_talents", "catalog_category", "TEXT NOT NULL DEFAULT ''"
        )
        self._ensure_column("martial_talents", "prerequisites", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("martial_talents", "source_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "martial_talents", "enabled", "INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))"
        )
        self._ensure_column("martial_talents", "choice", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "martial_talents", "effects_json", "TEXT NOT NULL DEFAULT '[]'"
        )
        self._ensure_column(
            "martial_talents", "activation", "TEXT NOT NULL DEFAULT 'always'"
        )
        self._ensure_column(
            "martial_talents", "activation_note", "TEXT NOT NULL DEFAULT ''"
        )
        # Most catalog talents remain unique through the repository API.  A
        # small number of published talents (for example Athletics' Expanded
        # Training) are explicitly repeatable, so persistence must not impose
        # a stricter rule than the catalog provider.
        self._connection.execute("DROP INDEX IF EXISTS idx_martial_talents_catalog")
        self._connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_martial_talents_catalog_lookup
               ON martial_talents(character_id, catalog_key)"""
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS flexible_talent_selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                slot_index INTEGER NOT NULL CHECK (slot_index >= 0),
                talent_kind TEXT NOT NULL CHECK (talent_kind IN ('martial', 'magic')),
                catalog_key TEXT NOT NULL,
                name TEXT NOT NULL,
                sphere TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Talent',
                description TEXT NOT NULL DEFAULT '',
                choice TEXT NOT NULL DEFAULT '',
                choice_key TEXT NOT NULL DEFAULT '',
                UNIQUE(character_id, source_key, slot_index)
            )
            """
        )
        self._connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_flexible_talent_source
               ON flexible_talent_selections(character_id, source_key, slot_index)"""
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS flexible_talent_source_states (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL,
                change_available INTEGER NOT NULL DEFAULT 1
                    CHECK (change_available IN (0, 1)),
                PRIMARY KEY (character_id, source_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS spells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                system TEXT NOT NULL DEFAULT 'Prepared',
                level INTEGER NOT NULL DEFAULT 0 CHECK (level BETWEEN 0 AND 9),
                school_or_sphere TEXT NOT NULL DEFAULT '',
                uses_max INTEGER NOT NULL DEFAULT 0 CHECK (uses_max BETWEEN 0 AND 999),
                uses_used INTEGER NOT NULL DEFAULT 0 CHECK (uses_used BETWEEN 0 AND 999),
                casting_time TEXT NOT NULL DEFAULT '',
                range TEXT NOT NULL DEFAULT '',
                duration TEXT NOT NULL DEFAULT '',
                save TEXT NOT NULL DEFAULT '',
                spell_resistance TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                catalog_key TEXT NOT NULL DEFAULT '',
                catalog_category TEXT NOT NULL DEFAULT '',
                prerequisites TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                choice TEXT NOT NULL DEFAULT '',
                effects_json TEXT NOT NULL DEFAULT '[]',
                activation TEXT NOT NULL DEFAULT 'always',
                activation_note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._ensure_column("spells", "catalog_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("spells", "catalog_category", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("spells", "prerequisites", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("spells", "source_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "spells", "enabled", "INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))"
        )
        self._ensure_column("spells", "choice", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("spells", "effects_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("spells", "activation", "TEXT NOT NULL DEFAULT 'always'")
        self._ensure_column("spells", "activation_note", "TEXT NOT NULL DEFAULT ''")
        self._connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_spells_catalog
            ON spells(character_id, catalog_key)
            WHERE catalog_key <> ''
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prepared_spells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_level_id INTEGER NOT NULL REFERENCES class_levels(id) ON DELETE CASCADE,
                known_spell_id INTEGER REFERENCES spells(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT '',
                level INTEGER NOT NULL DEFAULT 0 CHECK (level BETWEEN 0 AND 9),
                prepared_count INTEGER NOT NULL DEFAULT 1 CHECK (prepared_count BETWEEN 1 AND 999),
                used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count BETWEEN 0 AND 999),
                catalog_key TEXT NOT NULL DEFAULT '',
                custom INTEGER NOT NULL DEFAULT 0 CHECK (custom IN (0, 1)),
                CHECK (used_count <= prepared_count),
                CHECK ((custom = 0 AND known_spell_id IS NOT NULL) OR (custom = 1 AND length(trim(name)) > 0))
            )
            """
        )
        self._connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_prepared_known_spell
            ON prepared_spells(character_id, class_level_id, known_spell_id)
            WHERE custom = 0
            """
        )
        self._connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_prepared_custom_spell
            ON prepared_spells(character_id, class_level_id, catalog_key)
            WHERE custom = 1 AND catalog_key <> ''
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS spontaneous_spell_slots (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_level_id INTEGER NOT NULL REFERENCES class_levels(id) ON DELETE CASCADE,
                spell_level INTEGER NOT NULL CHECK (spell_level BETWEEN 1 AND 9),
                used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count BETWEEN 0 AND 999),
                PRIMARY KEY (character_id, class_level_id, spell_level)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prodigy_sequence (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
                current INTEGER NOT NULL DEFAULT 0 CHECK (current BETWEEN 0 AND 99),
                maximum INTEGER NOT NULL DEFAULT 4 CHECK (maximum BETWEEN 1 AND 99),
                imbue_key TEXT NOT NULL DEFAULT '',
                CHECK (current <= maximum)
            )
            """
        )
        self._ensure_column("prodigy_sequence", "imbue_key", "TEXT NOT NULL DEFAULT ''")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sequence_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                option_type TEXT NOT NULL,
                sphere TEXT NOT NULL DEFAULT '',
                minimum_links INTEGER NOT NULL DEFAULT 0 CHECK (minimum_links BETWEEN 0 AND 99),
                action TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                built_in INTEGER NOT NULL DEFAULT 0 CHECK (built_in IN (0, 1))
            )
            """
        )
        self._ensure_column("sequence_options", "built_in", "INTEGER NOT NULL DEFAULT 0")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_details (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                player_name TEXT NOT NULL DEFAULT '',
                race TEXT NOT NULL DEFAULT '',
                alignment TEXT NOT NULL DEFAULT '',
                deity TEXT NOT NULL DEFAULT '',
                size TEXT NOT NULL DEFAULT 'Medium',
                race_key TEXT NOT NULL DEFAULT '',
                race_ability_choice TEXT NOT NULL DEFAULT '',
                race_variant_key TEXT NOT NULL DEFAULT '',
                race_alternate_trait_keys TEXT NOT NULL DEFAULT '[]',
                race_trait_choices TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self._ensure_column("character_details", "race_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            "character_details", "race_ability_choice", "TEXT NOT NULL DEFAULT ''"
        )
        self._ensure_column(
            "character_details", "race_variant_key", "TEXT NOT NULL DEFAULT ''"
        )
        self._ensure_column(
            "character_details", "race_alternate_trait_keys", "TEXT NOT NULL DEFAULT '[]'"
        )
        self._ensure_column(
            "character_details", "race_trait_choices", "TEXT NOT NULL DEFAULT '[]'"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS class_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_name TEXT NOT NULL CHECK (length(trim(class_name)) > 0),
                level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 20),
                bab_progression TEXT NOT NULL,
                fort_progression TEXT NOT NULL,
                reflex_progression TEXT NOT NULL,
                will_progression TEXT NOT NULL,
                preset_key TEXT NOT NULL DEFAULT '',
                hit_die INTEGER NOT NULL DEFAULT 0,
                hp_gained INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._ensure_column("class_levels", "preset_key", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("class_levels", "hit_die", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("class_levels", "hp_gained", "INTEGER NOT NULL DEFAULT 0")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS proficiency_adjustments (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_level_id INTEGER PRIMARY KEY REFERENCES class_levels(id) ON DELETE CASCADE,
                weapons TEXT NOT NULL DEFAULT '',
                armor TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS favored_class_bonuses (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                class_level_id INTEGER PRIMARY KEY REFERENCES class_levels(id) ON DELETE CASCADE,
                hp_bonus INTEGER NOT NULL DEFAULT 0 CHECK (hp_bonus BETWEEN 0 AND 999),
                skill_point_bonus INTEGER NOT NULL DEFAULT 0 CHECK (skill_point_bonus BETWEEN 0 AND 999),
                manual_bonus INTEGER NOT NULL DEFAULT 0 CHECK (manual_bonus BETWEEN 0 AND 999),
                manual_code TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS advancement_adjustments (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                budget_key TEXT NOT NULL CHECK (length(trim(budget_key)) > 0),
                adjustment INTEGER NOT NULL DEFAULT 0,
                override_total INTEGER,
                note TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (character_id, budget_key),
                CHECK (override_total IS NULL OR override_total >= 0)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ability_score_increases (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                ability TEXT NOT NULL,
                points INTEGER NOT NULL DEFAULT 0 CHECK (points BETWEEN 0 AND 999),
                PRIMARY KEY (character_id, ability)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS movement_profiles (
                character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                land_speed INTEGER NOT NULL DEFAULT 0 CHECK (land_speed BETWEEN 0 AND 9999),
                armor_speed INTEGER NOT NULL DEFAULT 0 CHECK (armor_speed BETWEEN 0 AND 9999),
                fly_speed INTEGER NOT NULL DEFAULT 0 CHECK (fly_speed BETWEEN 0 AND 9999),
                swim_speed INTEGER NOT NULL DEFAULT 0 CHECK (swim_speed BETWEEN 0 AND 9999),
                climb_speed INTEGER NOT NULL DEFAULT 0 CHECK (climb_speed BETWEEN 0 AND 9999),
                burrow_speed INTEGER NOT NULL DEFAULT 0 CHECK (burrow_speed BETWEEN 0 AND 9999),
                teleport_speed INTEGER NOT NULL DEFAULT 0 CHECK (teleport_speed BETWEEN 0 AND 9999),
                fly_maneuverability TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS class_level_archetypes (
                class_level_id INTEGER NOT NULL REFERENCES class_levels(id) ON DELETE CASCADE,
                archetype_key TEXT NOT NULL CHECK (length(trim(archetype_key)) > 0),
                selection_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (class_level_id, archetype_key)
            )
            """
        )
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS engineering_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                sphere TEXT NOT NULL CHECK (sphere IN ('Tech','Tinker')),
                catalog_key TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 0,
                modifier INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'inactive',
                charges INTEGER NOT NULL DEFAULT 0,
                minor INTEGER NOT NULL DEFAULT 0,
                advanced INTEGER NOT NULL DEFAULT 0,
                host_id INTEGER REFERENCES engineering_devices(id) ON DELETE SET NULL
            )
        """)
        self._ensure_column("engineering_devices", "host_id", "INTEGER REFERENCES engineering_devices(id) ON DELETE SET NULL")
        self._ensure_column("engineering_devices", "damage", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("engineering_devices", "configuration", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("engineering_devices", "applied_to_character", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("engineering_devices", "function_mode", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("engineering_devices", "effect_rounds", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("engineering_devices", "worn_slot", "TEXT NOT NULL DEFAULT ''")
        self._connection.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS engineering_tech_battery_host
            ON engineering_devices(host_id)
            WHERE sphere='Tech' AND catalog_key='{TECH_BATTERY_KEY}' AND host_id IS NOT NULL
        """)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_trackers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                tracker_key TEXT NOT NULL,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                tracker_type TEXT NOT NULL CHECK (tracker_type IN ('calculated', 'counter', 'pool')),
                formula TEXT NOT NULL DEFAULT '',
                manual_maximum REAL NOT NULL DEFAULT 0,
                current_value REAL NOT NULL DEFAULT 0,
                temporary_value REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                recovery_event TEXT NOT NULL DEFAULT 'none',
                recovery_operation TEXT NOT NULL DEFAULT 'none',
                UNIQUE (character_id, tracker_key)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ability_scores (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                ability TEXT NOT NULL,
                base_value INTEGER NOT NULL DEFAULT 10 CHECK (base_value BETWEEN 0 AND 999),
                PRIMARY KEY (character_id, ability)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS modifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                target TEXT NOT NULL,
                source TEXT NOT NULL CHECK (length(trim(source)) > 0),
                bonus_type TEXT NOT NULL,
                value INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
            )
            """
        )
        character_ids = self._connection.execute("SELECT id FROM characters").fetchall()
        for row in character_ids:
            character_id = int(row["id"])
            self._seed_abilities(character_id)
            self._seed_details(character_id)
            self._seed_hit_points(character_id)
            self._seed_currency(character_id)
            self._seed_martial_focus(character_id)
            self._seed_casting_profile(character_id)
            self._seed_prodigy_sequence(character_id)
            self._seed_sequence_options(character_id)
            self._seed_skills(character_id)
            self._seed_movement(character_id)
        self._connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            str(row["name"]) for row in self._connection.execute(f"PRAGMA table_info({table})")
        }
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _seed_abilities(self, character_id: int) -> None:
        self._connection.executemany(
            """
            INSERT OR IGNORE INTO ability_scores (character_id, ability, base_value)
            VALUES (?, ?, 10)
            """,
            ((character_id, ability) for ability in ABILITY_KEYS),
        )

    def _seed_details(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO character_details (character_id) VALUES (?)",
            (character_id,),
        )

    def _seed_hit_points(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO hit_points (character_id) VALUES (?)", (character_id,)
        )

    def _seed_currency(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO currency_purses (character_id) VALUES (?)",
            (character_id,),
        )

    def _seed_martial_focus(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO martial_focus (character_id) VALUES (?)", (character_id,)
        )

    def _seed_casting_profile(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO casting_profiles (character_id) VALUES (?)",
            (character_id,),
        )

    def _seed_prodigy_sequence(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO prodigy_sequence (character_id) VALUES (?)", (character_id,)
        )

    def _seed_sequence_options(self, character_id: int) -> None:
        for name, option_type, sphere, minimum_links, action, notes in BASE_PRODIGY_OPTIONS:
            existing = self._connection.execute(
                """
                SELECT id, option_type, sphere, minimum_links, action, notes
                FROM sequence_options
                WHERE character_id = ? AND name = ? AND built_in = 1
                  AND COALESCE(sphere, '') = ''
                """,
                (character_id, name),
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO sequence_options
                        (character_id, name, option_type, sphere, minimum_links,
                         action, notes, built_in)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (character_id, name, option_type, sphere, minimum_links, action, notes),
                )
            elif (
                str(existing["option_type"]),
                str(existing["sphere"]),
                int(existing["minimum_links"]),
                str(existing["action"]),
                str(existing["notes"]),
            ) != (option_type, sphere, minimum_links, action, notes):
                # Built-in rules text is application-owned. Keep existing
                # characters aligned with corrections to the canonical
                # catalog while leaving custom sequence entries untouched.
                self._connection.execute(
                    """
                    UPDATE sequence_options
                    SET option_type = ?, sphere = ?, minimum_links = ?,
                        action = ?, notes = ?
                    WHERE id = ? AND character_id = ? AND built_in = 1
                    """,
                    (
                        option_type,
                        sphere,
                        minimum_links,
                        action,
                        notes,
                        int(existing["id"]),
                        character_id,
                    ),
                )

    def _seed_skills(self, character_id: int) -> None:
        self._connection.executemany(
            "INSERT OR IGNORE INTO skills (character_id, skill_key) VALUES (?, ?)",
            ((character_id, skill.key) for skill in SKILLS),
        )

    def _seed_movement(self, character_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO movement_profiles (character_id) VALUES (?)",
            (character_id,),
        )

    def list_characters(self) -> list[CharacterSummary]:
        rows = self._connection.execute(
            """
            SELECT id, name, character_type, updated_at
            FROM characters
            ORDER BY updated_at DESC, name COLLATE NOCASE
            """
        ).fetchall()
        return [self._to_summary(row) for row in rows]

    def character_exists(self, character_id: int) -> bool:
        """Return whether a character is still present without materializing the roster."""

        return self._connection.execute(
            "SELECT 1 FROM characters WHERE id = ?", (character_id,)
        ).fetchone() is not None

    def create_character(self, name: str, character_type: str) -> int:
        clean_name = self._validate_name(name)
        if character_type not in CHARACTER_TYPES:
            raise ValueError(f"Unsupported character type: {character_type}")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        cursor = self._connection.execute(
            """
            INSERT INTO characters (name, character_type, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (clean_name, character_type, now, now),
        )
        character_id = int(cursor.lastrowid)
        self._seed_abilities(character_id)
        self._seed_details(character_id)
        self._seed_hit_points(character_id)
        self._seed_currency(character_id)
        self._seed_martial_focus(character_id)
        self._seed_casting_profile(character_id)
        self._seed_prodigy_sequence(character_id)
        self._seed_sequence_options(character_id)
        self._seed_skills(character_id)
        self._seed_movement(character_id)
        self._connection.commit()
        return character_id

    def rename_character(self, character_id: int, name: str) -> None:
        clean_name = self._validate_name(name)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        self._connection.execute(
            "UPDATE characters SET name = ?, updated_at = ? WHERE id = ?",
            (clean_name, now, character_id),
        )
        self._connection.commit()

    def delete_character(self, character_id: int) -> None:
        self._connection.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        self._connection.commit()

    def get_character_sheet_layout(self, character_id: int) -> dict[str, str]:
        row = self._connection.execute(
            "SELECT state_json FROM character_sheet_layouts WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if row is None:
            return {}
        try:
            state = json.loads(str(row["state_json"]))
        except (TypeError, ValueError):
            return {}
        return {
            str(key): str(value)
            for key, value in state.items()
        } if isinstance(state, dict) else {}

    def save_character_sheet_layout(
        self, character_id: int, state: dict[str, str]
    ) -> None:
        if self._connection.execute(
            "SELECT 1 FROM characters WHERE id = ?", (character_id,)
        ).fetchone() is None:
            raise KeyError(f"Unknown character: {character_id}")
        clean_state = {str(key): str(value) for key, value in state.items()}
        self._connection.execute(
            """
            INSERT INTO character_sheet_layouts (character_id, state_json)
            VALUES (?, ?)
            ON CONFLICT(character_id) DO UPDATE SET state_json = excluded.state_json
            """,
            (character_id, json.dumps(clean_state, ensure_ascii=False)),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def clear_character_sheet_layout(self, character_id: int) -> None:
        """Remove presentation customization without touching character rules data."""
        self._connection.execute(
            "DELETE FROM character_sheet_layouts WHERE character_id = ?",
            (character_id,),
        )
        self._connection.commit()

    def get_ability_scores(self, character_id: int) -> dict[str, int]:
        self._seed_abilities(character_id)
        rows = self._connection.execute(
            """
            SELECT ability, base_value FROM ability_scores
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        return {str(row["ability"]): int(row["base_value"]) for row in rows}

    def get_character_details(self, character_id: int) -> CharacterDetails:
        self._seed_details(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, player_name, race, alignment, deity, size,
                   race_key, race_ability_choice, race_variant_key,
                   race_alternate_trait_keys, race_trait_choices
            FROM character_details WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown character: {character_id}")
        return CharacterDetails(
            character_id=int(row["character_id"]),
            player_name=str(row["player_name"]),
            race=str(row["race"]),
            alignment=str(row["alignment"]),
            deity=str(row["deity"]),
            size=str(row["size"]),
            race_key=str(row["race_key"]),
            race_ability_choice=str(row["race_ability_choice"]),
            race_variant_key=str(row["race_variant_key"]),
            race_alternate_trait_keys=tuple(
                str(value)
                for value in json.loads(str(row["race_alternate_trait_keys"] or "[]"))
            ),
            race_trait_choices=tuple(
                RaceTraitChoice(
                    trait_key=str(choice.get("trait_key") or ""),
                    choice_key=str(choice.get("choice_key") or ""),
                    values=tuple(str(value) for value in choice.get("values", ())),
                )
                for choice in json.loads(str(row["race_trait_choices"] or "[]"))
                if isinstance(choice, dict)
            ),
        )

    def update_character_details(self, details: CharacterDetails) -> None:
        if details.size not in SIZES:
            raise ValueError(f"Unsupported size: {details.size}")
        if details.alignment not in ALIGNMENTS:
            raise ValueError(f"Unsupported alignment: {details.alignment}")
        self._connection.execute(
            """
            INSERT INTO character_details
                (character_id, player_name, race, alignment, deity, size,
                 race_key, race_ability_choice, race_variant_key,
                 race_alternate_trait_keys, race_trait_choices)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                player_name = excluded.player_name,
                race = excluded.race,
                alignment = excluded.alignment,
                deity = excluded.deity,
                size = excluded.size,
                race_key = excluded.race_key,
                race_ability_choice = excluded.race_ability_choice,
                race_variant_key = excluded.race_variant_key,
                race_alternate_trait_keys = excluded.race_alternate_trait_keys,
                race_trait_choices = excluded.race_trait_choices
            """,
            (
                details.character_id,
                details.player_name.strip(),
                details.race.strip(),
                details.alignment,
                details.deity.strip(),
                details.size,
                details.race_key,
                details.race_ability_choice,
                details.race_variant_key,
                json.dumps(list(details.race_alternate_trait_keys)),
                json.dumps([
                    {
                        "trait_key": choice.trait_key,
                        "choice_key": choice.choice_key,
                        "values": list(choice.values),
                    }
                    for choice in details.race_trait_choices
                ]),
            ),
        )
        self._touch_character(details.character_id)
        self._connection.commit()

    def get_hit_points(self, character_id: int) -> HitPoints:
        self._seed_hit_points(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, maximum, current, temporary, nonlethal, auto_calculate
            FROM hit_points WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown character: {character_id}")
        return HitPoints(
            character_id=int(row["character_id"]),
            maximum=int(row["maximum"]),
            current=int(row["current"]),
            temporary=int(row["temporary"]),
            nonlethal=int(row["nonlethal"]),
            auto_calculate=bool(row["auto_calculate"]),
        )

    def update_hit_points(self, hit_points: HitPoints) -> None:
        if hit_points.maximum < 0 or hit_points.temporary < 0 or hit_points.nonlethal < 0:
            raise ValueError("Maximum, temporary, and nonlethal HP cannot be negative.")
        self._connection.execute(
            """
            INSERT INTO hit_points
                (character_id, maximum, current, temporary, nonlethal, auto_calculate)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                maximum = excluded.maximum,
                current = excluded.current,
                temporary = excluded.temporary,
                nonlethal = excluded.nonlethal,
                auto_calculate = excluded.auto_calculate
            """,
            (
                hit_points.character_id,
                hit_points.maximum,
                hit_points.current,
                hit_points.temporary,
                hit_points.nonlethal,
                int(hit_points.auto_calculate),
            ),
        )
        self._touch_character(hit_points.character_id)
        self._connection.commit()

    def list_equipment(self, character_id: int) -> list[EquipmentItem]:
        rows = self._connection.execute(
            """
            SELECT id, name, category, quantity, weight, equipped, ac_bonus,
                   bonus_type, max_dex_bonus, armor_check_penalty, notes, slot, value_gp,
                   catalog_key, catalog_source, state, choices_json, automation_json,
                   enhancement_bonus, masterwork, weapon_damage_dice, weapon_damage_type,
                   weapon_critical, weapon_range
            FROM equipment WHERE character_id = ? ORDER BY category, name COLLATE NOCASE
            """,
            (character_id,),
        ).fetchall()
        return [
            EquipmentItem(
                id=int(row["id"]),
                name=str(row["name"]),
                category=str(row["category"]),
                quantity=int(row["quantity"]),
                weight=float(row["weight"]),
                equipped=bool(row["equipped"]),
                ac_bonus=int(row["ac_bonus"]),
                bonus_type=str(row["bonus_type"]),
                max_dex_bonus=(
                    None if row["max_dex_bonus"] is None else int(row["max_dex_bonus"])
                ),
                armor_check_penalty=int(row["armor_check_penalty"]),
                notes=str(row["notes"]),
                slot=str(row["slot"]),
                value_gp=float(row["value_gp"]),
                catalog_key=str(row["catalog_key"]),
                catalog_source=str(row["catalog_source"]),
                state=(
                    str(row["state"])
                    or (
                        "armor" if bool(row["equipped"]) and str(row["category"]) == "Armor"
                        else "shield" if bool(row["equipped"]) and str(row["category"]) == "Shield"
                        else "worn" if bool(row["equipped"]) and bool(str(row["slot"]))
                        else "wielded" if bool(row["equipped"]) and str(row["category"]) == "Weapon"
                        else "carried" if bool(row["equipped"]) else "stored"
                    )
                ),
                choices_json=str(row["choices_json"]),
                automation_json=str(row["automation_json"]),
                enhancement_bonus=int(row["enhancement_bonus"]),
                masterwork=bool(row["masterwork"]),
                weapon_damage_dice=str(row["weapon_damage_dice"]),
                weapon_damage_type=str(row["weapon_damage_type"]),
                weapon_critical=str(row["weapon_critical"]),
                weapon_range=str(row["weapon_range"]),
            )
            for row in rows
        ]

    def list_inventory_placements(
        self, character_id: int
    ) -> tuple[InventoryPlacement, ...]:
        rows = self._connection.execute(
            """
            SELECT placement.equipment_id, placement.category,
                   placement.subcategory, placement.sort_order,
                   placement.container_equipment_id
            FROM inventory_item_placements AS placement
            JOIN equipment AS item ON item.id = placement.equipment_id
            WHERE placement.character_id = ? AND item.character_id = ?
            ORDER BY placement.sort_order, item.name COLLATE NOCASE
            """,
            (character_id, character_id),
        ).fetchall()
        return tuple(
            InventoryPlacement(
                int(row["equipment_id"]),
                str(row["category"]),
                str(row["subcategory"] or "General"),
                int(row["sort_order"]),
                (
                    int(row["container_equipment_id"])
                    if row["container_equipment_id"] is not None else None
                ),
            )
            for row in rows
        )

    def list_inventory_custom_groups(
        self, character_id: int
    ) -> tuple[InventoryCustomGroup, ...]:
        rows = self._connection.execute(
            """
            SELECT category, subcategory, sort_order
            FROM inventory_custom_groups
            WHERE character_id = ?
            ORDER BY sort_order, category COLLATE NOCASE, subcategory COLLATE NOCASE
            """,
            (character_id,),
        ).fetchall()
        return tuple(
            InventoryCustomGroup(
                str(row["category"]),
                str(row["subcategory"] or "General"),
                int(row["sort_order"]),
            )
            for row in rows
        )

    def replace_inventory_organization(
        self,
        character_id: int,
        placements: tuple[InventoryPlacement, ...] | list[InventoryPlacement],
        custom_groups: tuple[InventoryCustomGroup, ...] | list[InventoryCustomGroup],
    ) -> None:
        """Atomically replace presentation-only inventory grouping state."""

        owned_ids = {
            int(row["id"])
            for row in self._connection.execute(
                "SELECT id FROM equipment WHERE character_id = ?", (character_id,)
            ).fetchall()
        }
        cleaned_placements: list[InventoryPlacement] = []
        seen_items: set[int] = set()
        for placement in placements:
            item_id = int(placement.equipment_id)
            category = str(placement.category).strip()
            subcategory = str(placement.subcategory).strip() or "General"
            container_id = (
                int(placement.container_equipment_id)
                if placement.container_equipment_id is not None else None
            )
            if item_id not in owned_ids:
                raise ValueError("An inventory placement references another character's item.")
            if container_id is not None and container_id not in owned_ids:
                raise ValueError("An inventory container belongs to another character.")
            if container_id == item_id:
                raise ValueError("An item cannot contain itself.")
            if item_id in seen_items or not category:
                raise ValueError("Inventory placements require unique items and named categories.")
            seen_items.add(item_id)
            cleaned_placements.append(
                InventoryPlacement(
                    item_id, category, subcategory, int(placement.sort_order), container_id
                )
            )
        parent_map = {
            placement.equipment_id: placement.container_equipment_id
            for placement in cleaned_placements
            if placement.container_equipment_id is not None
        }
        for item_id in parent_map:
            seen = {item_id}
            parent_id = parent_map.get(item_id)
            while parent_id is not None:
                if parent_id in seen:
                    raise ValueError("Inventory containers cannot form a cycle.")
                seen.add(parent_id)
                parent_id = parent_map.get(parent_id)
        cleaned_groups: list[InventoryCustomGroup] = []
        seen_groups: set[tuple[str, str]] = set()
        for group in custom_groups:
            category = str(group.category).strip()
            subcategory = str(group.subcategory).strip() or "General"
            folded = (category.casefold(), subcategory.casefold())
            if not category or folded in seen_groups:
                raise ValueError("Custom inventory groups require unique names.")
            seen_groups.add(folded)
            cleaned_groups.append(
                InventoryCustomGroup(category, subcategory, int(group.sort_order))
            )
        self._connection.execute(
            "DELETE FROM inventory_item_placements WHERE character_id = ?",
            (character_id,),
        )
        self._connection.executemany(
            """
            INSERT INTO inventory_item_placements
                (character_id, equipment_id, category, subcategory, sort_order,
                 container_equipment_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    character_id,
                    placement.equipment_id,
                    placement.category,
                    placement.subcategory,
                    placement.sort_order,
                    placement.container_equipment_id,
                )
                for placement in cleaned_placements
            ),
        )
        self._connection.execute(
            "DELETE FROM inventory_custom_groups WHERE character_id = ?",
            (character_id,),
        )
        self._connection.executemany(
            """
            INSERT INTO inventory_custom_groups
                (character_id, category, subcategory, sort_order)
            VALUES (?, ?, ?, ?)
            """,
            (
                (character_id, group.category, group.subcategory, group.sort_order)
                for group in cleaned_groups
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def reset_inventory_organization(self, character_id: int) -> None:
        self.replace_inventory_organization(character_id, (), ())

    def list_worn_slots(self, character_id: int) -> tuple[str, ...]:
        """Return this character's ordered worn-slot catalog.

        A missing profile intentionally resolves to the built-in catalog, so
        old databases and imported characters gain empty slot rows without a
        migration that rewrites every character.
        """

        row = self._connection.execute(
            "SELECT slots_json FROM worn_slot_catalogs WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if row is None:
            return tuple(slot for slot in WORN_SLOTS if slot)
        try:
            values = json.loads(str(row["slots_json"] or "[]"))
        except json.JSONDecodeError:
            return tuple(slot for slot in WORN_SLOTS if slot)
        if not isinstance(values, list):
            return tuple(slot for slot in WORN_SLOTS if slot)
        return tuple(str(value) for value in values if str(value).strip())

    def update_worn_slots(self, character_id: int, slots: list[str] | tuple[str, ...]) -> None:
        """Save a character slot catalog and safely detach removed slots."""

        cleaned: list[str] = []
        seen: set[str] = set()
        for value in slots:
            slot = str(value).strip()
            folded = slot.casefold()
            if not slot:
                raise ValueError("A worn-item slot needs a name.")
            if folded in seen:
                raise ValueError(f"The worn-item slot {slot!r} is duplicated.")
            seen.add(folded)
            cleaned.append(slot)
        previous = set(self.list_worn_slots(character_id))
        removed = previous - set(cleaned)
        for slot in removed:
            self._connection.execute(
                """
                UPDATE equipment
                SET slot = '',
                    state = CASE
                        WHEN state IN ('worn', 'armor', 'shield')
                          OR (state IN ('', 'stored') AND equipped = 1)
                        THEN 'carried' ELSE state END,
                    equipped = CASE
                        WHEN state IN ('worn', 'armor', 'shield')
                          OR (state IN ('', 'stored') AND equipped = 1)
                        THEN 1 ELSE equipped END
                WHERE character_id = ? AND slot = ?
                """,
                (character_id, slot),
            )
        self._connection.execute(
            """
            INSERT INTO worn_slot_catalogs (character_id, slots_json)
            VALUES (?, ?)
            ON CONFLICT(character_id) DO UPDATE SET slots_json = excluded.slots_json
            """,
            (character_id, json.dumps(cleaned, ensure_ascii=False)),
        )
        self._touch_character(character_id)
        self._connection.commit()

    @staticmethod
    def _state_occupies_worn_slot(
        state: str, category: str, slot: str, equipped: bool
    ) -> bool:
        if not slot or not equipped:
            return False
        if state:
            return state in {"worn", "armor", "shield"} or state == "stored"
        return category in {"Armor", "Shield"} or bool(slot)

    def _release_worn_slot(
        self, character_id: int, slot: str, *, except_item_id: int | None = None
    ) -> None:
        """Make room in a slot while keeping the displaced item carried."""

        if not slot:
            return
        self._connection.execute("UPDATE engineering_devices SET worn_slot='',applied_to_character=0,effect_rounds=0,state=CASE WHEN state='active' THEN 'inactive' ELSE state END WHERE character_id=? AND worn_slot=?",
            (character_id,slot))
        parameters: list[object] = [character_id, slot]
        exclusion = ""
        if except_item_id is not None:
            exclusion = " AND id != ?"
            parameters.append(except_item_id)
        self._connection.execute(
            f"""
            UPDATE equipment SET state = 'carried', equipped = 1
            WHERE character_id = ? AND slot = ?{exclusion}
              AND equipped = 1
              AND state IN ('', 'stored', 'worn', 'armor', 'shield')
            """,
            tuple(parameters),
        )

    def list_item_enchantments(
        self, character_id: int, equipment_id: int | None = None
    ) -> list[ItemEnchantment]:
        parameters: list[int] = [character_id]
        item_filter = ""
        if equipment_id is not None:
            item_filter = " AND enchantment.equipment_id = ?"
            parameters.append(equipment_id)
        rows = self._connection.execute(
            f"""
            SELECT enchantment.id, enchantment.equipment_id,
                   enchantment.enchantment_key, enchantment.name,
                   enchantment.bonus_equivalent, enchantment.notes
            FROM equipment_enchantments AS enchantment
            JOIN equipment AS item ON item.id = enchantment.equipment_id
            WHERE item.character_id = ?{item_filter}
            ORDER BY enchantment.name COLLATE NOCASE, enchantment.id
            """,
            tuple(parameters),
        ).fetchall()
        return [
            ItemEnchantment(
                id=int(row["id"]),
                equipment_id=int(row["equipment_id"]),
                key=str(row["enchantment_key"]),
                name=str(row["name"]),
                bonus_equivalent=int(row["bonus_equivalent"]),
                notes=str(row["notes"]),
            )
            for row in rows
        ]

    def add_item_enchantment(
        self,
        character_id: int,
        equipment_id: int,
        key: str,
        name: str,
        bonus_equivalent: int = 0,
        notes: str = "",
    ) -> int:
        item_row = self._connection.execute(
            "SELECT category, enhancement_bonus FROM equipment WHERE id = ? AND character_id = ?",
            (equipment_id, character_id),
        ).fetchone()
        if item_row is None:
            raise ValueError("The selected item does not belong to this character.")
        clean_key = key.strip()
        clean_name = name.strip()
        if not clean_key or not clean_name:
            raise ValueError("An enchantment needs a stable key and name.")
        if bonus_equivalent < 0:
            raise ValueError("An enchantment bonus equivalent cannot be negative.")
        try:
            if (
                str(item_row["category"]) in {"Weapon", "Armor", "Shield"}
                and int(item_row["enhancement_bonus"] or 0) < 1
            ):
                self._connection.execute(
                    """
                    UPDATE equipment
                    SET enhancement_bonus = 1,
                        masterwork = 1
                    WHERE id = ? AND character_id = ?
                    """,
                    (equipment_id, character_id),
                )
            cursor = self._connection.execute(
                """
                INSERT INTO equipment_enchantments
                    (equipment_id, enchantment_key, name, bonus_equivalent, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    equipment_id,
                    clean_key,
                    clean_name,
                    bonus_equivalent,
                    notes.strip(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"{clean_name} is already attached to this item.") from error
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def delete_item_enchantment(
        self, character_id: int, enchantment_id: int
    ) -> None:
        self._connection.execute(
            """
            DELETE FROM equipment_enchantments
            WHERE id = ? AND equipment_id IN (
                SELECT id FROM equipment WHERE character_id = ?
            )
            """,
            (enchantment_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def add_equipment(
        self,
        character_id: int,
        name: str,
        category: str,
        quantity: int,
        weight: float,
        equipped: bool,
        ac_bonus: int,
        bonus_type: str,
        max_dex_bonus: int | None,
        notes: str,
        armor_check_penalty: int = 0,
        slot: str = "",
        value_gp: float = 0.0,
        catalog_key: str = "",
        catalog_source: str = "",
        state: str = "",
        choices_json: str = "{}",
        automation_json: str = "",
        enhancement_bonus: int = 0,
        masterwork: bool = False,
        weapon_damage_dice: str = "",
        weapon_damage_type: str = "",
        weapon_critical: str = "",
        weapon_range: str = "",
    ) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Item name cannot be empty.")
        if category not in EQUIPMENT_CATEGORIES:
            raise ValueError("Unsupported equipment category.")
        if bonus_type not in EQUIPMENT_BONUS_TYPES:
            raise ValueError("Unsupported equipment bonus type.")
        if slot and slot not in self.list_worn_slots(character_id):
            raise ValueError("Unsupported worn-item slot.")
        if state and state not in EQUIPMENT_STATES:
            raise ValueError("Unsupported equipment state.")
        if (
            quantity < 0 or weight < 0 or armor_check_penalty < 0
            or value_gp < 0 or enhancement_bonus < 0
        ):
            raise ValueError(
                "Quantity, weight, value, armor check penalty, and enhancement cannot be negative."
            )
        try:
            parsed_choices = json.loads(choices_json or "{}")
        except json.JSONDecodeError as error:
            raise ValueError("Invalid item choices.") from error
        if not isinstance(parsed_choices, dict):
            raise ValueError("Item choices must be an object.")
        validate_item_choices(automation_from_json(automation_json), parsed_choices)
        if category in {"Weapon", "Armor", "Shield"} and enhancement_bonus > 0:
            masterwork = True
        if self._state_occupies_worn_slot(state, category, slot, equipped):
            self._release_worn_slot(character_id, slot)
        cursor = self._connection.execute(
            """
            INSERT INTO equipment
                (character_id, name, category, quantity, weight, equipped,
                 ac_bonus, bonus_type, max_dex_bonus, armor_check_penalty, notes,
                 slot, value_gp, catalog_key, catalog_source, state, choices_json,
                 automation_json, enhancement_bonus, masterwork, weapon_damage_dice,
                 weapon_damage_type, weapon_critical, weapon_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                category,
                quantity,
                weight,
                int(equipped),
                ac_bonus,
                bonus_type,
                max_dex_bonus,
                armor_check_penalty,
                notes.strip(),
                slot,
                value_gp,
                catalog_key,
                catalog_source,
                state,
                choices_json,
                automation_json,
                enhancement_bonus,
                int(masterwork),
                weapon_damage_dice,
                weapon_damage_type,
                weapon_critical,
                weapon_range,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_equipment(
        self,
        character_id: int,
        item_id: int,
        name: str,
        category: str,
        quantity: int,
        weight: float,
        equipped: bool,
        ac_bonus: int,
        bonus_type: str,
        max_dex_bonus: int | None,
        notes: str,
        armor_check_penalty: int = 0,
        slot: str = "",
        value_gp: float = 0.0,
        state: str | None = None,
        choices_json: str | None = None,
        automation_json: str | None = None,
        enhancement_bonus: int | None = None,
        masterwork: bool | None = None,
        weapon_damage_dice: str | None = None,
        weapon_damage_type: str | None = None,
        weapon_critical: str | None = None,
        weapon_range: str | None = None,
    ) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Item name cannot be empty.")
        if category not in EQUIPMENT_CATEGORIES or bonus_type not in EQUIPMENT_BONUS_TYPES:
            raise ValueError("Unsupported equipment category or bonus type.")
        if slot and slot not in self.list_worn_slots(character_id):
            raise ValueError("Unsupported worn-item slot.")
        if state is not None and state not in EQUIPMENT_STATES:
            raise ValueError("Unsupported equipment state.")
        if (
            quantity < 0 or weight < 0 or armor_check_penalty < 0
            or value_gp < 0
            or (enhancement_bonus is not None and enhancement_bonus < 0)
        ):
            raise ValueError(
                "Quantity, weight, value, armor check penalty, and enhancement cannot be negative."
            )
        if choices_json is not None:
            try:
                parsed_choices = json.loads(choices_json or "{}")
            except json.JSONDecodeError as error:
                raise ValueError("Invalid item choices.") from error
            row = self._connection.execute(
                "SELECT automation_json FROM equipment WHERE id = ? AND character_id = ?",
                (item_id, character_id),
            ).fetchone()
            effective_automation = (
                automation_json
                if automation_json is not None
                else (str(row["automation_json"]) if row is not None else "")
            )
            validate_item_choices(
                automation_from_json(effective_automation), parsed_choices
            )
        if (
            category in {"Weapon", "Armor", "Shield"}
            and enhancement_bonus is not None
            and enhancement_bonus > 0
        ):
            masterwork = True
        existing_usage = self._connection.execute(
            "SELECT state FROM equipment WHERE id = ? AND character_id = ?",
            (item_id, character_id),
        ).fetchone()
        effective_state = (
            state
            if state is not None
            else (str(existing_usage["state"]) if existing_usage is not None else "")
        )
        if self._state_occupies_worn_slot(
            effective_state, category, slot, equipped
        ):
            self._release_worn_slot(
                character_id, slot, except_item_id=item_id
            )
        self._connection.execute(
            """
            UPDATE equipment SET name = ?, category = ?, quantity = ?, weight = ?,
                equipped = ?, ac_bonus = ?, bonus_type = ?, max_dex_bonus = ?,
                armor_check_penalty = ?, notes = ?, slot = ?, value_gp = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                category,
                quantity,
                weight,
                int(equipped),
                ac_bonus,
                bonus_type,
                max_dex_bonus,
                armor_check_penalty,
                notes.strip(),
                slot,
                value_gp,
                item_id,
                character_id,
            ),
        )
        optional = {
            "state": state, "choices_json": choices_json, "automation_json": automation_json,
            "enhancement_bonus": enhancement_bonus, "masterwork": None if masterwork is None else int(masterwork),
            "weapon_damage_dice": weapon_damage_dice, "weapon_damage_type": weapon_damage_type,
            "weapon_critical": weapon_critical, "weapon_range": weapon_range,
        }
        for column, value in optional.items():
            if value is not None:
                self._connection.execute(
                    f"UPDATE equipment SET {column} = ? WHERE id = ? AND character_id = ?",
                    (value, item_id, character_id),
                )
        self._touch_character(character_id)
        self._connection.commit()

    def set_equipment_equipped(self, character_id: int, item_id: int, equipped: bool) -> None:
        item = next((value for value in self.list_equipment(character_id) if value.id == item_id), None)
        if item is None:
            return
        active_state = preferred_item_state(item)
        if equipped and self._state_occupies_worn_slot(
            active_state, item.category, item.slot, True
        ):
            self._release_worn_slot(
                character_id, item.slot, except_item_id=item_id
            )
        self._connection.execute(
            "UPDATE equipment SET equipped = ?, state = ? WHERE id = ? AND character_id = ?",
            (int(equipped), active_state if equipped else "stored", item_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_equipment_state(self, character_id: int, item_id: int, state: str) -> None:
        if state not in EQUIPMENT_STATES:
            raise ValueError("Unsupported equipment state.")
        item = next(
            (value for value in self.list_equipment(character_id) if value.id == item_id),
            None,
        )
        if item is None:
            return
        if self._state_occupies_worn_slot(
            state, item.category, item.slot, state != "stored"
        ):
            self._release_worn_slot(
                character_id, item.slot, except_item_id=item_id
            )
        self._connection.execute(
            "UPDATE equipment SET state = ?, equipped = ? WHERE id = ? AND character_id = ?",
            (state, int(state != "stored"), item_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_equipment_choices(self, character_id: int, item_id: int, choices_json: str) -> None:
        try:
            parsed = json.loads(choices_json)
        except json.JSONDecodeError as error:
            raise ValueError("Invalid item choices.") from error
        if not isinstance(parsed, dict):
            raise ValueError("Item choices must be an object.")
        row = self._connection.execute(
            "SELECT automation_json FROM equipment WHERE id = ? AND character_id = ?",
            (item_id, character_id),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown equipment item.")
        validate_item_choices(automation_from_json(str(row["automation_json"])), parsed)
        self._connection.execute(
            "UPDATE equipment SET choices_json = ? WHERE id = ? AND character_id = ?",
            (choices_json, item_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_equipment(self, character_id: int, item_id: int) -> None:
        self._connection.execute(
            "UPDATE attacks SET equipment_id = NULL WHERE character_id = ? AND equipment_id = ?",
            (character_id, item_id),
        )
        self._connection.execute(
            """
            UPDATE inventory_item_placements
            SET container_equipment_id = NULL
            WHERE character_id = ? AND container_equipment_id = ?
            """,
            (character_id, item_id),
        )
        self._connection.execute(
            "DELETE FROM equipment WHERE id = ? AND character_id = ?", (item_id, character_id)
        )
        self._touch_character(character_id)
        self._connection.commit()

    def get_currency_purse(self, character_id: int) -> CurrencyPurse:
        self._seed_currency(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, copper, silver, gold, platinum, notes
            FROM currency_purses WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown character: {character_id}")
        return CurrencyPurse(
            character_id=int(row["character_id"]),
            copper=int(row["copper"]),
            silver=int(row["silver"]),
            gold=int(row["gold"]),
            platinum=int(row["platinum"]),
            notes=str(row["notes"]),
        )

    def update_currency_purse(self, purse: CurrencyPurse) -> None:
        values = (purse.copper, purse.silver, purse.gold, purse.platinum)
        if any(value < 0 for value in values):
            raise ValueError("Currency amounts cannot be negative.")
        self._connection.execute(
            """
            INSERT INTO currency_purses
                (character_id, copper, silver, gold, platinum, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                copper = excluded.copper,
                silver = excluded.silver,
                gold = excluded.gold,
                platinum = excluded.platinum,
                notes = excluded.notes
            """,
            (
                purse.character_id,
                purse.copper,
                purse.silver,
                purse.gold,
                purse.platinum,
                purse.notes.strip(),
            ),
        )
        self._touch_character(purse.character_id)
        self._connection.commit()

    def list_attacks(self, character_id: int) -> list[Attack]:
        rows = self._connection.execute(
            """
            SELECT id, name, attack_type, ability, attack_bonus, damage_dice,
                   damage_ability, damage_multiplier, damage_bonus, critical, notes,
                   equipment_id, profile_key, damage_ability_mode, visibility_condition
            FROM attacks WHERE character_id = ? ORDER BY name COLLATE NOCASE
            """,
            (character_id,),
        ).fetchall()
        return [
            Attack(
                id=int(row["id"]),
                name=str(row["name"]),
                attack_type=str(row["attack_type"]),
                ability=str(row["ability"]),
                attack_bonus=int(row["attack_bonus"]),
                damage_dice=str(row["damage_dice"]),
                damage_ability=(
                    None if row["damage_ability"] is None else str(row["damage_ability"])
                ),
                damage_multiplier=float(row["damage_multiplier"]),
                damage_bonus=int(row["damage_bonus"]),
                critical=str(row["critical"]),
                notes=str(row["notes"]),
                equipment_id=None if row["equipment_id"] is None else int(row["equipment_id"]),
                profile_key=str(row["profile_key"]),
                damage_ability_mode=str(row["damage_ability_mode"] or "manual"),
                visibility_condition=str(row["visibility_condition"] or ""),
            )
            for row in rows
        ]

    def add_attack(
        self,
        character_id: int,
        name: str,
        attack_type: str,
        ability: str,
        attack_bonus: int,
        damage_dice: str,
        damage_ability: str | None,
        damage_multiplier: float,
        damage_bonus: int,
        critical: str,
        notes: str,
        equipment_id: int | None = None,
        profile_key: str = "",
        damage_ability_mode: str = "manual",
        visibility_condition: str = "",
    ) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Attack name cannot be empty.")
        if attack_type not in ATTACK_TYPES:
            raise ValueError("Unsupported attack type.")
        if ability not in ABILITY_KEYS or (
            damage_ability is not None and damage_ability not in ABILITY_KEYS
        ):
            raise ValueError("Unsupported attack ability.")
        if damage_multiplier not in DAMAGE_MULTIPLIERS:
            raise ValueError("Unsupported damage multiplier.")
        if damage_ability_mode not in DAMAGE_ABILITY_MODES:
            raise ValueError("Unsupported damage ability mode.")
        clean_visibility_condition = visibility_condition.strip()
        if clean_visibility_condition:
            parse_formula(clean_visibility_condition)
        if equipment_id is not None and self._connection.execute(
            "SELECT 1 FROM equipment WHERE id = ? AND character_id = ?",
            (equipment_id, character_id),
        ).fetchone() is None:
            raise ValueError("The linked weapon does not belong to this character.")
        cursor = self._connection.execute(
            """
            INSERT INTO attacks
                (character_id, name, attack_type, ability, attack_bonus, damage_dice,
                 damage_ability, damage_multiplier, damage_bonus, critical, notes,
                 equipment_id, profile_key, damage_ability_mode, visibility_condition)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                attack_type,
                ability,
                attack_bonus,
                damage_dice.strip().lower(),
                damage_ability,
                damage_multiplier,
                damage_bonus,
                critical.strip() or "20/x2",
                notes.strip(),
                equipment_id,
                profile_key.strip(),
                damage_ability_mode,
                clean_visibility_condition,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def delete_attack(self, character_id: int, attack_id: int) -> None:
        self._connection.execute(
            "DELETE FROM numeric_formulas WHERE character_id = ? "
            "AND entity_type = 'attack' AND entity_id = ?",
            (character_id, attack_id),
        )
        self._connection.execute(
            "DELETE FROM attacks WHERE id = ? AND character_id = ?", (attack_id, character_id)
        )
        self._touch_character(character_id)
        self._connection.commit()

    def update_attack(
        self,
        character_id: int,
        attack_id: int,
        name: str,
        attack_type: str,
        ability: str,
        attack_bonus: int,
        damage_dice: str,
        damage_ability: str | None,
        damage_multiplier: float,
        damage_bonus: int,
        critical: str,
        notes: str,
        equipment_id: int | None = None,
        profile_key: str = "",
        damage_ability_mode: str = "manual",
        visibility_condition: str = "",
    ) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Attack name cannot be empty.")
        if attack_type not in ATTACK_TYPES:
            raise ValueError("Unsupported attack type.")
        if ability not in ABILITY_KEYS or (
            damage_ability is not None and damage_ability not in ABILITY_KEYS
        ):
            raise ValueError("Unsupported attack ability.")
        if damage_multiplier not in DAMAGE_MULTIPLIERS:
            raise ValueError("Unsupported damage multiplier.")
        if damage_ability_mode not in DAMAGE_ABILITY_MODES:
            raise ValueError("Unsupported damage ability mode.")
        clean_visibility_condition = visibility_condition.strip()
        if clean_visibility_condition:
            parse_formula(clean_visibility_condition)
        if equipment_id is not None and self._connection.execute(
            "SELECT 1 FROM equipment WHERE id = ? AND character_id = ?",
            (equipment_id, character_id),
        ).fetchone() is None:
            raise ValueError("The linked weapon does not belong to this character.")
        self._connection.execute(
            """
            UPDATE attacks SET name = ?, attack_type = ?, ability = ?, attack_bonus = ?,
                damage_dice = ?, damage_ability = ?, damage_multiplier = ?,
                damage_bonus = ?, critical = ?, notes = ?, equipment_id = ?,
                profile_key = ?, damage_ability_mode = ?, visibility_condition = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                attack_type,
                ability,
                attack_bonus,
                damage_dice.strip().lower(),
                damage_ability,
                damage_multiplier,
                damage_bonus,
                critical.strip() or "20/x2",
                notes.strip(),
                equipment_id,
                profile_key.strip(),
                damage_ability_mode,
                clean_visibility_condition,
                attack_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_class_levels(self, character_id: int) -> list[ClassLevel]:
        rows = self._connection.execute(
            """
            SELECT id, class_name, level, bab_progression,
                   fort_progression, reflex_progression, will_progression,
                   preset_key, hit_die, hp_gained
            FROM class_levels WHERE character_id = ? ORDER BY id
            """,
            (character_id,),
        ).fetchall()
        return [
            ClassLevel(
                id=int(row["id"]),
                class_name=str(row["class_name"]),
                level=int(row["level"]),
                bab_progression=str(row["bab_progression"]),
                fort_progression=str(row["fort_progression"]),
                reflex_progression=str(row["reflex_progression"]),
                will_progression=str(row["will_progression"]),
                preset_key=str(row["preset_key"]),
                hit_die=int(row["hit_die"]),
                hp_gained=int(row["hp_gained"]),
            )
            for row in rows
        ]

    def list_favored_class_bonuses(
        self, character_id: int
    ) -> dict[int, FavoredClassBonus]:
        rows = self._connection.execute(
            """
            SELECT character_id, class_level_id, hp_bonus, skill_point_bonus,
                   manual_bonus, manual_code
            FROM favored_class_bonuses
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        return {
            int(row["class_level_id"]): FavoredClassBonus(
                character_id=int(row["character_id"]),
                class_level_id=int(row["class_level_id"]),
                hp_bonus=int(row["hp_bonus"]),
                skill_point_bonus=int(row["skill_point_bonus"]),
                manual_bonus=int(row["manual_bonus"]),
                manual_code=str(row["manual_code"]),
            )
            for row in rows
        }

    def update_favored_class_bonus(self, bonus: FavoredClassBonus) -> None:
        class_row = self._connection.execute(
            "SELECT level FROM class_levels WHERE id = ? AND character_id = ?",
            (bonus.class_level_id, bonus.character_id),
        ).fetchone()
        if class_row is None:
            raise ValueError("The favored-class allocation has no matching class.")
        values = (bonus.hp_bonus, bonus.skill_point_bonus, bonus.manual_bonus)
        if any(value < 0 for value in values) or sum(values) > int(class_row["level"]):
            raise ValueError("Favored-class allocations cannot exceed levels in that class.")
        self._connection.execute(
            """
            INSERT INTO favored_class_bonuses
                (character_id, class_level_id, hp_bonus, skill_point_bonus,
                 manual_bonus, manual_code)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(class_level_id) DO UPDATE SET
                hp_bonus = excluded.hp_bonus,
                skill_point_bonus = excluded.skill_point_bonus,
                manual_bonus = excluded.manual_bonus,
                manual_code = excluded.manual_code
            """,
            (
                bonus.character_id,
                bonus.class_level_id,
                bonus.hp_bonus,
                bonus.skill_point_bonus,
                bonus.manual_bonus,
                bonus.manual_code.strip(),
            ),
        )
        self._touch_character(bonus.character_id)
        self._connection.commit()

    def list_advancement_adjustments(
        self, character_id: int
    ) -> dict[str, AdvancementAdjustment]:
        rows = self._connection.execute(
            """
            SELECT character_id, budget_key, adjustment, override_total, note
            FROM advancement_adjustments WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        return {
            str(row["budget_key"]): AdvancementAdjustment(
                character_id=int(row["character_id"]),
                budget_key=str(row["budget_key"]),
                adjustment=int(row["adjustment"]),
                override_total=(
                    None if row["override_total"] is None else int(row["override_total"])
                ),
                note=str(row["note"]),
            )
            for row in rows
        }

    def update_advancement_adjustment(self, item: AdvancementAdjustment) -> None:
        if not item.budget_key.strip():
            raise ValueError("Advancement budget key cannot be empty.")
        if item.override_total is not None and item.override_total < 0:
            raise ValueError("An advancement override cannot be negative.")
        self._connection.execute(
            """
            INSERT INTO advancement_adjustments
                (character_id, budget_key, adjustment, override_total, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_id, budget_key) DO UPDATE SET
                adjustment = excluded.adjustment,
                override_total = excluded.override_total,
                note = excluded.note
            """,
            (
                item.character_id,
                item.budget_key.strip(),
                item.adjustment,
                item.override_total,
                item.note.strip(),
            ),
        )
        self._touch_character(item.character_id)
        self._connection.commit()

    def list_ability_score_increases(
        self, character_id: int
    ) -> dict[str, AbilityScoreIncreaseAllocation]:
        """Return the sparse, source-tagged player allocation for level ASIs."""

        rows = self._connection.execute(
            """
            SELECT character_id, ability, points
            FROM ability_score_increases
            WHERE character_id = ?
            ORDER BY ability
            """,
            (character_id,),
        ).fetchall()
        return {
            str(row["ability"]): AbilityScoreIncreaseAllocation(
                int(row["character_id"]), str(row["ability"]), int(row["points"])
            )
            for row in rows
        }

    def update_ability_score_increase(
        self, allocation: AbilityScoreIncreaseAllocation
    ) -> None:
        """Save one ASI allocation without baking it into the base score.

        The repository deliberately does not reject an over-allocation.  The
        advancement budget reports it as a negative remainder, which preserves
        characters after level loss and supports explicit budget overrides.
        """

        if allocation.ability not in ABILITY_KEYS:
            raise ValueError(f"Unsupported ability: {allocation.ability}")
        if not 0 <= allocation.points <= 999:
            raise ValueError("Ability-score increases must be between 0 and 999.")
        if allocation.points == 0:
            self._connection.execute(
                "DELETE FROM ability_score_increases WHERE character_id = ? AND ability = ?",
                (allocation.character_id, allocation.ability),
            )
        else:
            self._connection.execute(
                """
                INSERT INTO ability_score_increases (character_id, ability, points)
                VALUES (?, ?, ?)
                ON CONFLICT(character_id, ability) DO UPDATE SET points = excluded.points
                """,
                (allocation.character_id, allocation.ability, allocation.points),
            )
        self._touch_character(allocation.character_id)
        self._connection.commit()

    def get_movement_profile(self, character_id: int) -> MovementProfile:
        self._seed_movement(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, land_speed, armor_speed, fly_speed, swim_speed,
                   climb_speed, burrow_speed, teleport_speed,
                   fly_maneuverability, notes
            FROM movement_profiles WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        assert row is not None
        return MovementProfile(**dict(row))

    def update_movement_profile(self, profile: MovementProfile) -> None:
        speeds = (
            profile.land_speed, profile.armor_speed, profile.fly_speed,
            profile.swim_speed, profile.climb_speed, profile.burrow_speed,
            profile.teleport_speed,
        )
        if any(not 0 <= speed <= 9999 for speed in speeds):
            raise ValueError("Movement speeds must be between 0 and 9,999 feet.")
        self._connection.execute(
            """
            INSERT INTO movement_profiles
                (character_id, land_speed, armor_speed, fly_speed, swim_speed,
                 climb_speed, burrow_speed, teleport_speed,
                 fly_maneuverability, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                land_speed = excluded.land_speed,
                armor_speed = excluded.armor_speed,
                fly_speed = excluded.fly_speed,
                swim_speed = excluded.swim_speed,
                climb_speed = excluded.climb_speed,
                burrow_speed = excluded.burrow_speed,
                teleport_speed = excluded.teleport_speed,
                fly_maneuverability = excluded.fly_maneuverability,
                notes = excluded.notes
            """,
            (
                profile.character_id, *speeds,
                profile.fly_maneuverability.strip(), profile.notes.strip(),
            ),
        )
        self._touch_character(profile.character_id)
        self._connection.commit()

    def add_class_level(
        self,
        character_id: int,
        class_name: str,
        level: int,
        bab_progression: str,
        fort_progression: str,
        reflex_progression: str,
        will_progression: str,
        preset_key: str = "",
        hit_die: int = 0,
        hp_gained: int = 0,
    ) -> int:
        clean_name = class_name.strip()
        if not clean_name:
            raise ValueError("Class name cannot be empty.")
        if not 1 <= level <= 20:
            raise ValueError("Class level must be between 1 and 20.")
        if bab_progression not in BAB_PROGRESSIONS:
            raise ValueError("Unsupported BAB progression.")
        saves = (fort_progression, reflex_progression, will_progression)
        if any(save not in SAVE_PROGRESSIONS for save in saves):
            raise ValueError("Unsupported save progression.")
        if hit_die not in {0, 6, 8, 10, 12} or hp_gained < 0:
            raise ValueError("Unsupported hit die or class HP total.")
        cursor = self._connection.execute(
            """
            INSERT INTO class_levels
                (character_id, class_name, level, bab_progression,
                 fort_progression, reflex_progression, will_progression,
                 preset_key, hit_die, hp_gained)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                level,
                bab_progression,
                fort_progression,
                reflex_progression,
                will_progression,
                preset_key,
                hit_die,
                hp_gained,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_class_level(
        self,
        character_id: int,
        class_level_id: int,
        class_name: str,
        level: int,
        bab_progression: str,
        fort_progression: str,
        reflex_progression: str,
        will_progression: str,
        preset_key: str = "",
        hit_die: int = 0,
        hp_gained: int = 0,
    ) -> None:
        clean_name = class_name.strip()
        if not clean_name or not 1 <= level <= 20:
            raise ValueError("Enter a class name and a level from 1 to 20.")
        if bab_progression not in BAB_PROGRESSIONS:
            raise ValueError("Unsupported BAB progression.")
        if any(
            save not in SAVE_PROGRESSIONS
            for save in (fort_progression, reflex_progression, will_progression)
        ):
            raise ValueError("Unsupported save progression.")
        if hit_die not in {0, 6, 8, 10, 12} or hp_gained < 0:
            raise ValueError("Unsupported hit die or class HP total.")
        self._connection.execute(
            """
            UPDATE class_levels SET class_name = ?, level = ?, bab_progression = ?,
                fort_progression = ?, reflex_progression = ?, will_progression = ?,
                preset_key = ?, hit_die = ?, hp_gained = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                level,
                bab_progression,
                fort_progression,
                reflex_progression,
                will_progression,
                preset_key,
                hit_die,
                hp_gained,
                class_level_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_class_level(self, character_id: int, class_level_id: int) -> None:
        self._connection.execute(
            "DELETE FROM class_levels WHERE id = ? AND character_id = ?",
            (class_level_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_proficiency_adjustments(
        self, character_id: int
    ) -> list[ProficiencyAdjustment]:
        rows = self._connection.execute(
            """SELECT character_id, class_level_id, weapons, armor, notes
               FROM proficiency_adjustments WHERE character_id=? ORDER BY class_level_id""",
            (character_id,),
        ).fetchall()
        return [
            ProficiencyAdjustment(
                int(row["character_id"]), int(row["class_level_id"]),
                str(row["weapons"]), str(row["armor"]), str(row["notes"]),
            )
            for row in rows
        ]

    def save_proficiency_adjustment(self, item: ProficiencyAdjustment) -> None:
        owner = self._connection.execute(
            "SELECT 1 FROM class_levels WHERE id=? AND character_id=?",
            (item.class_level_id, item.character_id),
        ).fetchone()
        if owner is None:
            raise ValueError("Class level does not belong to this character.")
        self._connection.execute(
            """INSERT INTO proficiency_adjustments
                   (character_id, class_level_id, weapons, armor, notes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(class_level_id) DO UPDATE SET
                   weapons=excluded.weapons, armor=excluded.armor, notes=excluded.notes""",
            (item.character_id, item.class_level_id, item.weapons.strip(),
             item.armor.strip(), item.notes.strip()),
        )
        self._touch_character(item.character_id)
        self._connection.commit()

    def delete_proficiency_adjustment(
        self, character_id: int, class_level_id: int
    ) -> None:
        self._connection.execute(
            "DELETE FROM proficiency_adjustments WHERE character_id=? AND class_level_id=?",
            (character_id, class_level_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_special_ability_adjustments(
        self, character_id: int
    ) -> list[SpecialAbilityAdjustment]:
        rows = self._connection.execute(
            """SELECT id, character_id, feature_key, level, name, description,
                      hidden, custom
               FROM special_ability_adjustments
               WHERE character_id = ? ORDER BY custom, level, name COLLATE NOCASE""",
            (character_id,),
        ).fetchall()
        return [
            SpecialAbilityAdjustment(
                int(row["id"]), int(row["character_id"]), str(row["feature_key"]),
                int(row["level"]), str(row["name"]), str(row["description"]),
                bool(row["hidden"]), bool(row["custom"]),
            )
            for row in rows
        ]

    def save_special_ability_adjustment(
        self, item: SpecialAbilityAdjustment
    ) -> int:
        if not item.name.strip() or not item.feature_key.strip():
            raise ValueError("Special abilities need a name and feature key.")
        cursor = self._connection.execute(
            """INSERT INTO special_ability_adjustments
                   (character_id, feature_key, level, name, description, hidden, custom)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(character_id, feature_key) DO UPDATE SET
                   level=excluded.level, name=excluded.name,
                   description=excluded.description, hidden=excluded.hidden,
                   custom=excluded.custom""",
            (item.character_id, item.feature_key, max(1, item.level), item.name.strip(),
             item.description.strip(), int(item.hidden), int(item.custom)),
        )
        self._touch_character(item.character_id)
        self._connection.commit()
        row = self._connection.execute(
            "SELECT id FROM special_ability_adjustments WHERE character_id=? AND feature_key=?",
            (item.character_id, item.feature_key),
        ).fetchone()
        return int(row["id"] if row else cursor.lastrowid)

    def delete_special_ability_adjustment(self, character_id: int, feature_key: str) -> None:
        self._connection.execute(
            "DELETE FROM special_ability_adjustments WHERE character_id=? AND feature_key=?",
            (character_id, feature_key),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_class_feature_selections(self, character_id: int) -> list[ClassFeatureSelection]:
        rows = self._connection.execute(
            "SELECT * FROM class_feature_selections WHERE character_id=? ORDER BY class_level_id, feature_key",
            (character_id,),
        ).fetchall()
        return [ClassFeatureSelection(**dict(row)) for row in rows]

    def save_class_feature_selection(self, item: ClassFeatureSelection) -> None:
        self._connection.execute(
            """INSERT INTO class_feature_selections
                   (character_id,class_level_id,feature_key,option_type,option_key,name,description)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(character_id,class_level_id,feature_key) DO UPDATE SET
                   option_type=excluded.option_type, option_key=excluded.option_key,
                   name=excluded.name, description=excluded.description""",
            (item.character_id, item.class_level_id, item.feature_key,
             item.option_type.strip(), item.option_key.strip(), item.name.strip(),
             item.description.strip()),
        )
        self._touch_character(item.character_id)
        self._connection.commit()

    def delete_class_feature_selection(
        self, character_id: int, class_level_id: int, feature_key: str
    ) -> None:
        """Remove one reusable class-feature choice without disturbing siblings."""

        self._connection.execute(
            """DELETE FROM class_feature_selections
               WHERE character_id=? AND class_level_id=? AND feature_key=?""",
            (character_id, class_level_id, feature_key),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_class_feature_states(self, character_id: int) -> list[ClassFeatureState]:
        rows = self._connection.execute(
            """SELECT character_id, class_level_id, feature_key, current_value,
                      maximum_adjustment, maximum_override, active,
                      choices_json, notes
               FROM class_feature_states
               WHERE character_id = ?
               ORDER BY class_level_id, feature_key""",
            (character_id,),
        ).fetchall()
        return [
            ClassFeatureState(
                character_id=int(row["character_id"]),
                class_level_id=int(row["class_level_id"]),
                feature_key=str(row["feature_key"]),
                current_value=(
                    None if row["current_value"] is None else int(row["current_value"])
                ),
                maximum_adjustment=int(row["maximum_adjustment"]),
                maximum_override=(
                    None
                    if row["maximum_override"] is None
                    else int(row["maximum_override"])
                ),
                active=bool(row["active"]),
                choices_json=str(row["choices_json"]),
                notes=str(row["notes"]),
            )
            for row in rows
        ]

    def save_class_feature_state(self, item: ClassFeatureState) -> None:
        if not item.feature_key.strip():
            raise ValueError("Class feature state requires a stable key.")
        if item.current_value is not None and item.current_value < 0:
            raise ValueError("Class feature current value cannot be negative.")
        if item.maximum_override is not None and item.maximum_override < 0:
            raise ValueError("Class feature maximum override cannot be negative.")
        try:
            choices = json.loads(item.choices_json or "[]")
        except (TypeError, ValueError):
            raise ValueError("Class feature choices must be valid JSON.") from None
        if not isinstance(choices, list):
            raise ValueError("Class feature choices must be a list.")
        self._connection.execute(
            """INSERT INTO class_feature_states
                   (character_id, class_level_id, feature_key, current_value,
                    maximum_adjustment, maximum_override, active,
                    choices_json, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(character_id, class_level_id, feature_key) DO UPDATE SET
                   current_value = excluded.current_value,
                   maximum_adjustment = excluded.maximum_adjustment,
                   maximum_override = excluded.maximum_override,
                   active = excluded.active,
                   choices_json = excluded.choices_json,
                   notes = excluded.notes""",
            (
                item.character_id,
                item.class_level_id,
                item.feature_key.strip(),
                item.current_value,
                item.maximum_adjustment,
                item.maximum_override,
                int(item.active),
                json.dumps([str(value) for value in choices]),
                item.notes.strip(),
            ),
        )
        self._touch_character(item.character_id)
        self._connection.commit()

    def delete_class_feature_state(
        self, character_id: int, class_level_id: int, feature_key: str
    ) -> None:
        self._connection.execute(
            """DELETE FROM class_feature_states
               WHERE character_id = ? AND class_level_id = ? AND feature_key = ?""",
            (character_id, class_level_id, feature_key),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def get_animal_companion(self, character_id: int) -> AnimalCompanion:
        row = self._connection.execute(
            "SELECT * FROM animal_companions WHERE character_id=?", (character_id,)
        ).fetchone()
        return AnimalCompanion(character_id) if row is None else AnimalCompanion(**dict(row))

    def update_animal_companion(self, item: AnimalCompanion) -> None:
        self._connection.execute(
            """INSERT INTO animal_companions
                   (character_id,name,species_key,effective_level_adjustment,
                    effective_level_override,current_hp,temporary_hp,
                    ability_overrides_json,skill_ranks_json,feats_json,tricks_json,
                    special_abilities_json,details_json,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(character_id) DO UPDATE SET
                   name=excluded.name, species_key=excluded.species_key,
                   effective_level_adjustment=excluded.effective_level_adjustment,
                   effective_level_override=excluded.effective_level_override,
                   current_hp=excluded.current_hp, temporary_hp=excluded.temporary_hp,
                   ability_overrides_json=excluded.ability_overrides_json,
                   skill_ranks_json=excluded.skill_ranks_json, feats_json=excluded.feats_json,
                   tricks_json=excluded.tricks_json,
                   special_abilities_json=excluded.special_abilities_json,
                   details_json=excluded.details_json,
                   notes=excluded.notes""",
            (item.character_id,item.name.strip(),item.species_key.strip(),
             item.effective_level_adjustment,item.effective_level_override,
             item.current_hp,item.temporary_hp,item.ability_overrides_json,
             item.skill_ranks_json,item.feats_json,item.tricks_json,
             item.special_abilities_json,item.details_json,item.notes.strip()),
        )
        self._touch_character(item.character_id)
        self._connection.commit()

    def get_bonded_companion(
        self, character_id: int, companion_key: str
    ) -> BondedCompanion:
        row = self._connection.execute(
            "SELECT * FROM bonded_companions WHERE character_id=? AND companion_key=?",
            (character_id, companion_key),
        ).fetchone()
        return (
            BondedCompanion(character_id, companion_key)
            if row is None
            else BondedCompanion(**dict(row))
        )

    def list_bonded_companions(self, character_id: int) -> tuple[BondedCompanion, ...]:
        rows = self._connection.execute(
            "SELECT * FROM bonded_companions WHERE character_id=? ORDER BY companion_key",
            (character_id,),
        ).fetchall()
        return tuple(BondedCompanion(**dict(row)) for row in rows)

    def update_bonded_companion(self, item: BondedCompanion) -> None:
        self._connection.execute(
            """INSERT INTO bonded_companions
                   (character_id,companion_key,name,species,current_hp,temporary_hp,details_json,notes)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(character_id,companion_key) DO UPDATE SET
                   name=excluded.name,species=excluded.species,
                   current_hp=excluded.current_hp,temporary_hp=excluded.temporary_hp,
                   details_json=excluded.details_json,notes=excluded.notes""",
            (
                item.character_id,
                item.companion_key.strip(),
                item.name.strip(),
                item.species.strip(),
                item.current_hp,
                item.temporary_hp,
                item.details_json,
                item.notes.strip(),
            ),
        )
        self._touch_character(item.character_id)
        self._connection.commit()

    def list_class_archetype_keys(
        self, character_id: int, class_level_id: int | None = None
    ) -> dict[int, tuple[str, ...]]:
        parameters: tuple[int, ...]
        condition = "cl.character_id = ?"
        parameters = (character_id,)
        if class_level_id is not None:
            condition += " AND cl.id = ?"
            parameters = (character_id, class_level_id)
        rows = self._connection.execute(
            f"""
            SELECT cl.id AS class_level_id, cla.archetype_key
            FROM class_levels cl
            JOIN class_level_archetypes cla ON cla.class_level_id = cl.id
            WHERE {condition}
            ORDER BY cl.id, cla.selection_order, cla.archetype_key
            """,
            parameters,
        ).fetchall()
        result: dict[int, list[str]] = {}
        for row in rows:
            result.setdefault(int(row["class_level_id"]), []).append(str(row["archetype_key"]))
        return {key: tuple(values) for key, values in result.items()}

    def set_class_archetype_keys(
        self, character_id: int, class_level_id: int, archetype_keys: list[str] | tuple[str, ...]
    ) -> None:
        owner = self._connection.execute(
            "SELECT 1 FROM class_levels WHERE id = ? AND character_id = ?",
            (class_level_id, character_id),
        ).fetchone()
        if owner is None:
            raise ValueError("Class level does not belong to this character.")
        clean_keys = tuple(dict.fromkeys(key.strip() for key in archetype_keys if key.strip()))
        self._connection.execute(
            "DELETE FROM class_level_archetypes WHERE class_level_id = ?", (class_level_id,)
        )
        self._connection.executemany(
            """
            INSERT INTO class_level_archetypes (class_level_id, archetype_key, selection_order)
            VALUES (?, ?, ?)
            """,
            ((class_level_id, key, order) for order, key in enumerate(clean_keys)),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def update_ability_score(self, character_id: int, ability: str, value: int) -> None:
        if ability not in ABILITY_KEYS:
            raise ValueError(f"Unsupported ability: {ability}")
        if not 0 <= value <= 999:
            raise ValueError("Ability score must be between 0 and 999.")
        self._connection.execute(
            """
            INSERT INTO ability_scores (character_id, ability, base_value)
            VALUES (?, ?, ?)
            ON CONFLICT(character_id, ability) DO UPDATE SET base_value = excluded.base_value
            """,
            (character_id, ability, value),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_custom_trackers(self, character_id: int) -> list[CustomTracker]:
        rows = self._connection.execute(
            """
            SELECT id, tracker_key, name, tracker_type, formula, manual_maximum,
                   current_value, temporary_value, unit, description,
                   recovery_event, recovery_operation
            FROM custom_trackers WHERE character_id = ? ORDER BY id
            """,
            (character_id,),
        ).fetchall()
        return [
            CustomTracker(
                id=int(row["id"]),
                key=str(row["tracker_key"]),
                name=str(row["name"]),
                tracker_type=str(row["tracker_type"]),
                formula=str(row["formula"]),
                manual_maximum=float(row["manual_maximum"]),
                current_value=float(row["current_value"]),
                temporary_value=float(row["temporary_value"]),
                unit=str(row["unit"]),
                description=str(row["description"]),
                recovery_event=str(row["recovery_event"]),
                recovery_operation=str(row["recovery_operation"]),
            )
            for row in rows
        ]

    def list_engineering_devices(self, character_id):
        return [dict(row) for row in self._connection.execute(
            "SELECT * FROM engineering_devices WHERE character_id=? ORDER BY id", (character_id,))]

    def save_engineering_device(self, character_id, record, device_id=None):
        sphere = record.get("sphere")
        state = record.get("state", "inactive")
        if sphere not in {"Tech", "Tinker"} or state not in {"inactive", "active", "depleted", "abandoned"}:
            raise ValueError("Invalid device system or state.")
        name = str(record.get("name", "")).strip()
        if not name:
            raise ValueError("Device name is required.")
        host_id=record.get("host_id")
        if host_id is not None:
            host=self._connection.execute("SELECT sphere,catalog_key FROM engineering_devices WHERE id=? AND character_id=?",(host_id,character_id)).fetchone()
            if (host is None or host["sphere"]!=sphere or host_id==device_id
                    or not is_battery(record) or is_battery(dict(host))):
                raise ValueError("A battery must attach to a non-battery device of the same sphere owned by this character.")
            if sphere=="Tech" and self._connection.execute(
                "SELECT 1 FROM engineering_devices WHERE sphere='Tech' AND catalog_key=? AND host_id=? AND (? IS NULL OR id!=?)",
                (TECH_BATTERY_KEY,host_id,device_id,device_id)).fetchone():
                raise ValueError("A Tech device can have only one attached battery. Detach its existing battery first.")
        fields = ("sphere", "catalog_key", "name", "level", "modifier", "state", "charges", "minor", "advanced", "host_id", "damage", "configuration", "applied_to_character", "function_mode", "effect_rounds", "worn_slot")
        values = (sphere, str(record.get("catalog_key", "")), name,
                  int(record.get("level", 0)), int(record.get("modifier", 0)), state,
                  int(record.get("charges", 0)), int(bool(record.get("minor", False))),
                  int(record.get("advanced", 0)), host_id, int(record.get("damage",0)),
                  str(record.get("configuration", "")),int(bool(record.get("applied_to_character",False))),
                  str(record.get("function_mode","")),int(record.get("effect_rounds",0)),str(record.get("worn_slot","")))
        if not 0 <= values[3] <= 999 or not -100 <= values[4] <= 100 or not 0 <= values[6] <= 99999 or not 0 <= values[8] <= 99:
            raise ValueError("Device statistics are outside supported bounds.")
        if not 0<=values[10]<=99999:
            raise ValueError("Device damage is outside supported bounds.")
        if len(values[11])>200:
            raise ValueError("Device configuration is too long.")
        if len(values[13])>100 or not 0<=values[14]<=999999 or len(values[15])>100:
            raise ValueError("Device function or duration is outside supported bounds.")
        if (sphere=="Tinker" and values[6]) or (sphere=="Tech" and (values[7] or values[8])):
            raise ValueError("Tech charges and Tinker minor/advanced rules cannot be mixed.")
        if device_id is None:
            cursor = self._connection.execute(
                "INSERT INTO engineering_devices (character_id," + ",".join(fields) + ") VALUES ("+",".join("?" for _ in range(len(fields)+1))+")",
                (character_id, *values))
            device_id = cursor.lastrowid
        else:
            cursor = self._connection.execute(
                "UPDATE engineering_devices SET " + ",".join(f + "=?" for f in fields) + " WHERE id=? AND character_id=?",
                (*values, device_id, character_id))
            if not cursor.rowcount:
                raise KeyError("Device does not belong to this character.")
        self._touch_character(character_id)
        self._connection.commit()
        return device_id

    def transfer_engineering_charges(self, character_id, device_id, tracker_id, amount, *, received_amount=None):
        """Move existing charges atomically; both records must have one owner."""
        amount=int(amount)
        with self._connection:
            device=self._connection.execute(
                "SELECT * FROM engineering_devices WHERE id=? AND character_id=? AND sphere='Tech' AND state NOT IN ('abandoned','depleted')",
                (device_id,character_id)).fetchone()
            pool=self._connection.execute(
                "SELECT current_value FROM custom_trackers WHERE id=? AND character_id=?",
                (tracker_id,character_id)).fetchone()
            if device is None or pool is None or device_condition(dict(device))["destroyed"]:
                raise ValueError("Charge transfer records do not belong to this character or are unavailable.")
            received=amount if received_amount is None else int(received_amount)
            if received_amount is not None and not 0<=received<=amount:
                raise ValueError("Invalid credited charge amount.")
            charges=device["charges"]+received
            current=pool["current_value"]-amount
            if not 0<=charges<=99999 or current<0:
                raise ValueError("Not enough charges for this transfer.")
            if device["catalog_key"]==TECH_BATTERY_KEY:
                if amount<0 or received>max(0,tech_battery_capacity(device["modifier"],from_pool=True)-device["charges"]):
                    raise ValueError("Invalid Tech battery pool transfer.")
            self._connection.execute("UPDATE engineering_devices SET charges=? WHERE id=?",(charges,device_id))
            self._connection.execute("UPDATE custom_trackers SET current_value=? WHERE id=?",(current,tracker_id))
            self._touch_character(character_id)

    def spend_tech_device_charges(self, character_id, device_id, amount, *, function_mode=None,worn_slot=""):
        """Atomic battery-first spending, preserving charges on failed uses."""
        amount=int(amount)
        if amount<=0:
            raise ValueError("Charge cost must be positive.")
        with self._connection:
            host=self._connection.execute(
                "SELECT * FROM engineering_devices WHERE id=? AND character_id=? AND sphere='Tech' AND state NOT IN ('abandoned','depleted')",
                (device_id,character_id)).fetchone()
            if host is None or device_condition(dict(host))["destroyed"]:
                raise ValueError("Select a functioning Tech device.")
            if function_mode is not None and (host["catalog_key"]!=JET_BOOSTERS_KEY
                    or function_mode not in JET_MODES or host["configuration"] not in {"flight","aquatic"}
                    or amount!=JET_MODES[function_mode][0] or host["effect_rounds"]>0):
                raise ValueError("Invalid device function activation.")
            if function_mode is not None:
                if not worn_slot or worn_slot=="Slotless" or worn_slot not in self.list_worn_slots(character_id):
                    raise ValueError("Choose an equipment slot for the boosters.")
                if self._connection.execute("SELECT 1 FROM equipment WHERE character_id=? AND slot=? AND equipped=1 AND state IN ('','stored','worn','armor','shield')",(character_id,worn_slot)).fetchone() or self._connection.execute("SELECT 1 FROM engineering_devices WHERE character_id=? AND worn_slot=? AND id!=? AND state!='abandoned'",(character_id,worn_slot,device_id)).fetchone():
                    raise ValueError("That equipment slot is occupied.")
            battery=None if host["catalog_key"]==TECH_BATTERY_KEY else self._connection.execute(
                "SELECT * FROM engineering_devices WHERE host_id=? AND character_id=? AND catalog_key=? AND state NOT IN ('abandoned','depleted')",
                (device_id,character_id,TECH_BATTERY_KEY)).fetchone()
            if battery and device_condition(dict(battery))["destroyed"]:
                battery=None
            available=host["charges"]+(battery["charges"] if battery else 0)
            if amount>available:
                raise ValueError("Not enough charges in this device and its attached battery.")
            battery_spent=min(amount,battery["charges"]) if battery else 0
            if battery:
                self._connection.execute("UPDATE engineering_devices SET charges=charges-? WHERE id=?",(battery_spent,battery["id"]))
            self._connection.execute("UPDATE engineering_devices SET charges=charges-? WHERE id=?",(amount-battery_spent,device_id))
            if function_mode is not None:
                self._connection.execute("UPDATE engineering_devices SET state='active',applied_to_character=1,function_mode=?,effect_rounds=?,worn_slot=? WHERE id=?",
                    (function_mode,JET_MODES[function_mode][1],worn_slot,device_id))
            self._touch_character(character_id)

    def advance_engineering_time(self,character_id,rounds):
        rounds=int(rounds)
        if not 1<=rounds<=999999:
            raise ValueError("Elapsed rounds must be between 1 and 999,999.")
        with self._connection:
            self._connection.execute("UPDATE engineering_devices SET effect_rounds=MAX(0,effect_rounds-?),state=CASE WHEN effect_rounds<=? AND state='active' AND catalog_key=? THEN 'inactive' ELSE state END WHERE character_id=? AND state!='abandoned' AND effect_rounds>0",
                (rounds,rounds,JET_BOOSTERS_KEY,character_id))
            self._touch_character(character_id)

    def deplete_engineering_batteries(self,character_id,host_id,battery_ids):
        ids=tuple(dict.fromkeys(int(i) for i in battery_ids))
        if not ids:
            raise ValueError("Select at least one battery.")
        placeholders=",".join("?" for _ in ids)
        with self._connection:
            rows=self._connection.execute(
                "SELECT b.id FROM engineering_devices b JOIN engineering_devices h ON h.id=b.host_id WHERE b.character_id=? AND b.host_id=? AND b.catalog_key='tinker:battery' AND b.state='active' AND h.state='active' AND b.damage<3*b.level AND h.damage<3*h.level AND b.level>=h.level AND b.id IN ("+placeholders+")",
                (character_id,host_id,*ids)).fetchall()
            if len(rows)!=len(ids):
                raise ValueError("Attached battery is no longer available.")
            self._connection.execute("UPDATE engineering_devices SET state='depleted' WHERE id IN ("+placeholders+")",ids)
            self._touch_character(character_id)

    def add_custom_tracker(
        self,
        character_id: int,
        key: str,
        name: str,
        tracker_type: str,
        formula: str = "",
        manual_maximum: float = 0,
        current_value: float = 0,
        temporary_value: float = 0,
        unit: str = "",
        description: str = "",
        recovery_event: str = "none",
        recovery_operation: str = "none",
    ) -> int:
        values = self._validate_custom_tracker(
            key, name, tracker_type, formula, manual_maximum, current_value,
            temporary_value, unit, description, recovery_event, recovery_operation,
        )
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO custom_trackers
                    (character_id, tracker_key, name, tracker_type, formula,
                     manual_maximum, current_value, temporary_value, unit,
                     description, recovery_event, recovery_operation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (character_id, *values),
            )
        except sqlite3.IntegrityError as error:
            if "custom_trackers.character_id, custom_trackers.tracker_key" in str(error):
                raise ValueError("Tracker reference key must be unique for this character.") from None
            raise
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_custom_tracker(
        self,
        character_id: int,
        tracker_id: int,
        key: str,
        name: str,
        tracker_type: str,
        formula: str = "",
        manual_maximum: float = 0,
        current_value: float = 0,
        temporary_value: float = 0,
        unit: str = "",
        description: str = "",
        recovery_event: str = "none",
        recovery_operation: str = "none",
    ) -> None:
        values = self._validate_custom_tracker(
            key, name, tracker_type, formula, manual_maximum, current_value,
            temporary_value, unit, description, recovery_event, recovery_operation,
        )
        try:
            self._connection.execute(
                """
                UPDATE custom_trackers
                SET tracker_key = ?, name = ?, tracker_type = ?, formula = ?,
                    manual_maximum = ?, current_value = ?, temporary_value = ?,
                    unit = ?, description = ?, recovery_event = ?, recovery_operation = ?
                WHERE id = ? AND character_id = ?
                """,
                (*values, tracker_id, character_id),
            )
        except sqlite3.IntegrityError as error:
            if "custom_trackers.character_id, custom_trackers.tracker_key" in str(error):
                raise ValueError("Tracker reference key must be unique for this character.") from None
            raise
        self._touch_character(character_id)
        self._connection.commit()

    def delete_custom_tracker(self, character_id: int, tracker_id: int) -> None:
        self._connection.execute(
            "DELETE FROM custom_trackers WHERE id = ? AND character_id = ?",
            (tracker_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_custom_tracker_values(
        self,
        character_id: int,
        tracker_id: int,
        *,
        current_value: float | None = None,
        temporary_value: float | None = None,
    ) -> None:
        """Update live tracker values without rewriting its definition."""
        tracker = next(
            (
                item
                for item in self.list_custom_trackers(character_id)
                if item.id == tracker_id
            ),
            None,
        )
        if tracker is None:
            raise KeyError(f"Unknown custom tracker: {tracker_id}")
        current = tracker.current_value if current_value is None else float(current_value)
        temporary = (
            tracker.temporary_value
            if temporary_value is None
            else float(temporary_value)
        )
        if not all(
            math.isfinite(value) and abs(value) <= 1_000_000_000_000
            for value in (current, temporary)
        ):
            raise ValueError("Tracker values must be finite numbers of a reasonable size.")
        self._connection.execute(
            """
            UPDATE custom_trackers
            SET current_value = ?, temporary_value = ?
            WHERE id = ? AND character_id = ?
            """,
            (current, temporary, tracker_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def get_rest_preferences(self, character_id: int) -> dict[str, bool]:
        row = self._connection.execute(
            "SELECT enabled_targets_json FROM character_rest_settings WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if row is None:
            return {}
        try:
            values = json.loads(str(row["enabled_targets_json"]))
        except (TypeError, ValueError):
            return {}
        return (
            {str(key): bool(value) for key, value in values.items()}
            if isinstance(values, dict)
            else {}
        )

    def save_rest_preferences(
        self, character_id: int, preferences: dict[str, bool]
    ) -> None:
        clean = {str(key): bool(value) for key, value in preferences.items()}
        self._connection.execute(
            """
            INSERT INTO character_rest_settings (character_id, enabled_targets_json)
            VALUES (?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                enabled_targets_json = excluded.enabled_targets_json
            """,
            (character_id, json.dumps(clean, sort_keys=True)),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def numeric_formulas(
        self,
        character_id: int,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> dict[tuple[str, int, str], str]:
        clauses = ["character_id = ?"]
        parameters: list[object] = [character_id]
        if entity_type is not None:
            clauses.append("entity_type = ?")
            parameters.append(entity_type)
        if entity_id is not None:
            clauses.append("entity_id = ?")
            parameters.append(entity_id)
        rows = self._connection.execute(
            "SELECT entity_type, entity_id, field_key, expression FROM numeric_formulas "
            f"WHERE {' AND '.join(clauses)} ORDER BY entity_type, entity_id, field_key",
            tuple(parameters),
        ).fetchall()
        return {
            (str(row["entity_type"]), int(row["entity_id"]), str(row["field_key"])):
            str(row["expression"])
            for row in rows
        }

    def set_numeric_formula(
        self,
        character_id: int,
        entity_type: str,
        entity_id: int,
        field_key: str,
        expression: str,
    ) -> None:
        clean_type = entity_type.strip().casefold()
        clean_field = field_key.strip().casefold()
        clean_expression = expression.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", clean_type):
            raise ValueError("Invalid formula entity type.")
        if entity_id < 0 or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", clean_field):
            raise ValueError("Invalid formula field identity.")
        if clean_expression:
            try:
                parse_formula(clean_expression)
            except FormulaError as error:
                raise ValueError(str(error)) from None
            self._connection.execute(
                """
                INSERT INTO numeric_formulas
                    (character_id, entity_type, entity_id, field_key, expression)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(character_id, entity_type, entity_id, field_key)
                DO UPDATE SET expression = excluded.expression
                """,
                (character_id, clean_type, entity_id, clean_field, clean_expression),
            )
        else:
            self._connection.execute(
                """
                DELETE FROM numeric_formulas
                WHERE character_id = ? AND entity_type = ?
                  AND entity_id = ? AND field_key = ?
                """,
                (character_id, clean_type, entity_id, clean_field),
            )
        self._touch_character(character_id)
        self._connection.commit()

    @staticmethod
    def _validate_custom_tracker(
        key: str, name: str, tracker_type: str, formula: str,
        manual_maximum: float, current_value: float, temporary_value: float,
        unit: str, description: str, recovery_event: str, recovery_operation: str,
    ) -> tuple:
        clean_key = key.strip().casefold()
        clean_name = name.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", clean_key):
            raise ValueError("Reference key must start with a letter and use only letters, numbers, and underscores.")
        if not clean_name:
            raise ValueError("Tracker name cannot be empty.")
        if tracker_type not in CUSTOM_TRACKER_TYPES:
            raise ValueError("Unsupported tracker type.")
        numbers = (float(manual_maximum), float(current_value), float(temporary_value))
        if not all(math.isfinite(value) and abs(value) <= 1_000_000_000_000 for value in numbers):
            raise ValueError("Tracker values must be finite numbers of a reasonable size.")
        if tracker_type == "calculated" and not formula.strip():
            raise ValueError("Calculated values require a formula.")
        if formula.strip():
            try:
                parse_formula(formula)
            except FormulaError as error:
                raise ValueError(str(error)) from None
        if recovery_event not in TRACKER_RECOVERY_EVENTS:
            raise ValueError("Unsupported recovery event.")
        if recovery_operation not in TRACKER_RECOVERY_OPERATIONS:
            raise ValueError("Unsupported recovery operation.")
        return (
            clean_key, clean_name, tracker_type, formula.strip(), *numbers,
            unit.strip()[:40], description.strip(), recovery_event, recovery_operation,
        )

    def list_modifiers(self, character_id: int, target: str | None = None) -> list[StatModifier]:
        if target is None:
            rows = self._connection.execute(
                """
                SELECT id, target, source, bonus_type, value, enabled
                FROM modifiers WHERE character_id = ? ORDER BY id
                """,
                (character_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT id, target, source, bonus_type, value, enabled
                FROM modifiers WHERE character_id = ? AND target = ? ORDER BY id
                """,
                (character_id, target),
            ).fetchall()
        return [
            StatModifier(
                id=int(row["id"]),
                target=str(row["target"]),
                source=str(row["source"]),
                bonus_type=str(row["bonus_type"]),
                value=int(row["value"]),
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def add_modifier(
        self,
        character_id: int,
        target: str,
        source: str,
        bonus_type: str,
        value: int,
    ) -> int:
        if target not in STAT_TARGETS:
            raise ValueError(f"Unsupported modifier target: {target}")
        clean_source = source.strip()
        if not clean_source:
            raise ValueError("Modifier source cannot be empty.")
        cursor = self._connection.execute(
            """
            INSERT INTO modifiers (character_id, target, source, bonus_type, value)
            VALUES (?, ?, ?, ?, ?)
            """,
            (character_id, target, clean_source, bonus_type, value),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def set_modifier_enabled(self, character_id: int, modifier_id: int, enabled: bool) -> None:
        self._connection.execute(
            "UPDATE modifiers SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), modifier_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_modifier(self, character_id: int, modifier_id: int) -> None:
        self._connection.execute(
            "DELETE FROM modifiers WHERE id = ? AND character_id = ?",
            (modifier_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_skill_states(self, character_id: int) -> dict[str, SkillState]:
        self._seed_skills(character_id)
        rows = self._connection.execute(
            """
            SELECT skill_key, ranks, class_skill, misc_bonus, notes, ability_override,
                   class_skill_override
            FROM skills WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        return {
            str(row["skill_key"]): SkillState(
                skill_key=str(row["skill_key"]),
                ranks=int(row["ranks"]),
                class_skill=bool(row["class_skill"]),
                misc_bonus=int(row["misc_bonus"]),
                notes=str(row["notes"]),
                ability_override=str(row["ability_override"]),
                class_skill_override=(
                    bool(row["class_skill_override"])
                    if row["class_skill_override"] is not None else None
                ),
            )
            for row in rows
        }

    def update_skill_state(self, character_id: int, state: SkillState) -> None:
        valid_keys = {skill.key for skill in SKILLS} | {
            item.skill_key for item in self.list_skill_specializations(character_id)
        }
        if state.skill_key not in valid_keys:
            raise ValueError("Unsupported skill.")
        if not 0 <= state.ranks <= 999:
            raise ValueError("Skill ranks must be between 0 and 999.")
        if state.ability_override not in {"", *ABILITY_KEYS}:
            raise ValueError("Unsupported skill ability override.")
        self._connection.execute(
            """
            INSERT INTO skills
                (character_id, skill_key, ranks, class_skill, misc_bonus, notes,
                 ability_override, class_skill_override)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id, skill_key) DO UPDATE SET
                ranks = excluded.ranks,
                class_skill = excluded.class_skill,
                misc_bonus = excluded.misc_bonus,
                notes = excluded.notes,
                ability_override = excluded.ability_override,
                class_skill_override = excluded.class_skill_override
            """,
            (
                character_id,
                state.skill_key,
                state.ranks,
                int(state.class_skill),
                state.misc_bonus,
                state.notes.strip(),
                state.ability_override,
                (
                    int(state.class_skill_override)
                    if state.class_skill_override is not None else None
                ),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_skill_specializations(
        self, character_id: int
    ) -> tuple[SkillSpecialization, ...]:
        rows = self._connection.execute(
            """
            SELECT skill_key, base_skill_key, specialty, sort_order
            FROM skill_specializations
            WHERE character_id = ?
            ORDER BY base_skill_key, sort_order, skill_key
            """,
            (character_id,),
        ).fetchall()
        return tuple(
            SkillSpecialization(
                str(row["skill_key"]),
                str(row["base_skill_key"]),
                str(row["specialty"]),
                int(row["sort_order"]),
            )
            for row in rows
        )

    def update_skill_specialization(
        self,
        character_id: int,
        skill_key: str,
        base_skill_key: str,
        specialty: str,
    ) -> None:
        if base_skill_key not in {"craft", "perform", "profession"}:
            raise ValueError("Only Craft, Perform, and Profession use specializations.")
        if skill_key != base_skill_key and not skill_key.startswith(
            f"{base_skill_key}__"
        ):
            raise ValueError("That specialization does not belong to this skill.")
        specialty = specialty.strip()
        existing = self.list_skill_specializations(character_id)
        order = next(
            (item.sort_order for item in existing if item.skill_key == skill_key),
            0 if skill_key == base_skill_key else len(existing),
        )
        self._connection.execute(
            """
            INSERT INTO skill_specializations
                (character_id, skill_key, base_skill_key, specialty, sort_order)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_id, skill_key) DO UPDATE SET
                base_skill_key = excluded.base_skill_key,
                specialty = excluded.specialty,
                sort_order = excluded.sort_order
            """,
            (character_id, skill_key, base_skill_key, specialty, order),
        )
        self._connection.execute(
            "INSERT OR IGNORE INTO skills (character_id, skill_key) VALUES (?, ?)",
            (character_id, skill_key),
        )
        refreshed = self.list_skill_specializations(character_id)
        if specialty and not any(
            item.base_skill_key == base_skill_key
            and item.skill_key != skill_key
            and not item.specialty
            for item in refreshed
        ):
            used = {
                item.skill_key for item in refreshed
                if item.base_skill_key == base_skill_key
            }
            index = 1
            while f"{base_skill_key}__{index}" in used:
                index += 1
            next_key = f"{base_skill_key}__{index}"
            next_order = 1 + max(
                (
                    item.sort_order for item in refreshed
                    if item.base_skill_key == base_skill_key
                ),
                default=0,
            )
            self._connection.execute(
                """
                INSERT INTO skill_specializations
                    (character_id, skill_key, base_skill_key, specialty, sort_order)
                VALUES (?, ?, ?, '', ?)
                """,
                (character_id, next_key, base_skill_key, next_order),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO skills (character_id, skill_key) VALUES (?, ?)",
                (character_id, next_key),
            )
        self._touch_character(character_id)
        self._connection.commit()

    def list_sheet_notes(self, character_id: int) -> tuple[SheetNote, ...]:
        rows = self._connection.execute(
            """
            SELECT id, character_id, page_key, x, y, width, height, pinned,
                   content_html, toolbar_expanded, visible, pages_json, current_page
            FROM sheet_notes WHERE character_id = ? ORDER BY id
            """,
            (character_id,),
        ).fetchall()
        return tuple(
            SheetNote(
                int(row["id"]), int(row["character_id"]), str(row["page_key"]),
                int(row["x"]), int(row["y"]), int(row["width"]), int(row["height"]),
                bool(row["pinned"]), str(row["content_html"]),
                bool(row["toolbar_expanded"]),
                bool(row["visible"]),
                str(row["pages_json"]),
                int(row["current_page"]),
            )
            for row in rows
        )

    def add_sheet_note(self, character_id: int, **values) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO sheet_notes
                (character_id, page_key, x, y, width, height, pinned,
                 content_html, toolbar_expanded, visible, pages_json, current_page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id, str(values.get("page_key", "")),
                int(values.get("x", 80)), int(values.get("y", 100)),
                max(220, int(values.get("width", 360))),
                max(150, int(values.get("height", 260))),
                int(bool(values.get("pinned", False))),
                str(values.get("content_html", "")),
                int(bool(values.get("toolbar_expanded", False))),
                int(bool(values.get("visible", True))),
                str(values.get("pages_json", "[]")),
                max(0, int(values.get("current_page", 0))),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_sheet_note(self, character_id: int, note_id: int, **values) -> None:
        self._connection.execute(
            """
            UPDATE sheet_notes SET page_key = ?, x = ?, y = ?, width = ?, height = ?,
                pinned = ?, content_html = ?, toolbar_expanded = ?, visible = ?,
                pages_json = ?, current_page = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                str(values.get("page_key", "")), int(values.get("x", 80)),
                int(values.get("y", 100)), max(220, int(values.get("width", 360))),
                max(150, int(values.get("height", 260))),
                int(bool(values.get("pinned", False))),
                str(values.get("content_html", "")),
                int(bool(values.get("toolbar_expanded", False))),
                int(bool(values.get("visible", True))),
                str(values.get("pages_json", "[]")),
                max(0, int(values.get("current_page", 0))),
                note_id, character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_conditions(self, character_id: int) -> list[Condition]:
        rows = self._connection.execute(
            "SELECT id, name, enabled, notes FROM conditions WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
        return [
            Condition(int(row["id"]), str(row["name"]), bool(row["enabled"]), str(row["notes"]))
            for row in rows
        ]

    def add_condition(self, character_id: int, name: str, notes: str = "") -> int:
        if name not in CONDITION_PRESETS:
            raise ValueError("Unsupported condition.")
        existing = self._connection.execute(
            "SELECT 1 FROM conditions WHERE character_id = ? AND name = ?",
            (character_id, name),
        ).fetchone()
        if existing is not None:
            raise ValueError(f"{name} is already on this character.")
        cursor = self._connection.execute(
            "INSERT INTO conditions (character_id, name, notes) VALUES (?, ?, ?)",
            (character_id, name, notes.strip()),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def set_condition_enabled(self, character_id: int, condition_id: int, enabled: bool) -> None:
        self._connection.execute(
            "UPDATE conditions SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), condition_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_condition(self, character_id: int, condition_id: int) -> None:
        self._connection.execute(
            "DELETE FROM conditions WHERE id = ? AND character_id = ?",
            (condition_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_ongoing_effects(self, character_id: int) -> list[OngoingEffect]:
        rows = self._connection.execute(
            """
            SELECT id, name, source_type, enabled, duration, target,
                   bonus_type, value, notes
            FROM ongoing_effects
            WHERE character_id = ?
            ORDER BY name COLLATE NOCASE, id
            """,
            (character_id,),
        ).fetchall()
        return [
            OngoingEffect(
                id=int(row["id"]),
                name=str(row["name"]),
                source_type=str(row["source_type"]),
                enabled=bool(row["enabled"]),
                duration=str(row["duration"]),
                target=str(row["target"]),
                bonus_type=str(row["bonus_type"]),
                value=int(row["value"]),
                notes=str(row["notes"]),
            )
            for row in rows
        ]

    @staticmethod
    def _validate_ongoing_effect(
        name: str, source_type: str, target: str, bonus_type: str
    ) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Effect name cannot be empty.")
        if source_type not in ONGOING_EFFECT_SOURCE_TYPES:
            raise ValueError("Unsupported ongoing-effect source.")
        if target and target not in STAT_TARGETS:
            raise ValueError("Unsupported ongoing-effect target.")
        if bonus_type not in BONUS_TYPES:
            raise ValueError("Unsupported ongoing-effect bonus type.")
        return clean_name

    def add_ongoing_effect(
        self,
        character_id: int,
        name: str,
        source_type: str = "Spell",
        duration: str = "",
        target: str = "",
        bonus_type: str = "untyped",
        value: int = 0,
        notes: str = "",
    ) -> int:
        clean_name = self._validate_ongoing_effect(
            name, source_type, target, bonus_type
        )
        cursor = self._connection.execute(
            """
            INSERT INTO ongoing_effects
                (character_id, name, source_type, duration, target,
                 bonus_type, value, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                source_type,
                duration.strip(),
                target,
                bonus_type,
                int(value),
                notes.strip(),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_ongoing_effect(
        self,
        character_id: int,
        effect_id: int,
        name: str,
        source_type: str = "Spell",
        duration: str = "",
        target: str = "",
        bonus_type: str = "untyped",
        value: int = 0,
        notes: str = "",
    ) -> None:
        clean_name = self._validate_ongoing_effect(
            name, source_type, target, bonus_type
        )
        self._connection.execute(
            """
            UPDATE ongoing_effects
            SET name = ?, source_type = ?, duration = ?, target = ?,
                bonus_type = ?, value = ?, notes = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                source_type,
                duration.strip(),
                target,
                bonus_type,
                int(value),
                notes.strip(),
                effect_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_ongoing_effect_enabled(
        self, character_id: int, effect_id: int, enabled: bool
    ) -> None:
        self._connection.execute(
            "UPDATE ongoing_effects SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), effect_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_ongoing_effect(self, character_id: int, effect_id: int) -> None:
        self._connection.execute(
            "DELETE FROM numeric_formulas WHERE character_id = ? "
            "AND entity_type = 'ongoing_effect' AND entity_id = ?",
            (character_id, effect_id),
        )
        self._connection.execute(
            "DELETE FROM ongoing_effects WHERE id = ? AND character_id = ?",
            (effect_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_feats(self, character_id: int) -> list[Feat]:
        rows = self._connection.execute(
            """
            SELECT id, name, enabled, target, bonus_type, value, notes,
                   catalog_key, catalog_category, prerequisites, source_url, choice,
                   effects_json, repeatable, activation, activation_note
            FROM feats WHERE character_id = ? ORDER BY name COLLATE NOCASE, id
            """,
            (character_id,),
        ).fetchall()
        return [
            Feat(
                id=int(row["id"]),
                name=str(row["name"]),
                enabled=bool(row["enabled"]),
                target=str(row["target"]),
                bonus_type=str(row["bonus_type"]),
                value=int(row["value"]),
                notes=str(row["notes"]),
                catalog_key=str(row["catalog_key"]),
                catalog_category=str(row["catalog_category"]),
                prerequisites=str(row["prerequisites"]),
                source_url=str(row["source_url"]),
                choice=str(row["choice"]),
                effects=self._parse_feat_effects(str(row["effects_json"])),
                repeatable=bool(row["repeatable"]),
                activation=str(row["activation"]),
                activation_note=str(row["activation_note"]),
            )
            for row in rows
        ]

    def add_feat(
        self,
        character_id: int,
        name: str,
        target: str = "",
        bonus_type: str = "untyped",
        value: int = 0,
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        repeatable: bool = False,
        activation: str = "always",
        activation_note: str = "",
    ) -> int:
        clean_name, target, value = self._validate_feat(name, target, bonus_type, value)
        clean_catalog_key = catalog_key.strip()
        clean_choice = choice.strip()
        clean_effects, effects_json = self._normalize_feat_effects(effects)
        self._validate_catalog_feat_duplicate(
            character_id, clean_catalog_key, clean_choice, repeatable
        )
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported feat activation mode.")
        cursor = self._connection.execute(
            """
            INSERT INTO feats
                (character_id, name, target, bonus_type, value, notes, catalog_key,
                 catalog_category, prerequisites, source_url, choice, effects_json,
                 repeatable, activation, activation_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                target,
                bonus_type,
                value,
                notes.strip(),
                clean_catalog_key,
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                clean_choice,
                effects_json,
                int(repeatable),
                activation,
                activation_note.strip(),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_feat(
        self,
        character_id: int,
        feat_id: int,
        name: str,
        target: str = "",
        bonus_type: str = "untyped",
        value: int = 0,
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        repeatable: bool = False,
        activation: str = "always",
        activation_note: str = "",
    ) -> None:
        clean_name, target, value = self._validate_feat(name, target, bonus_type, value)
        clean_catalog_key = catalog_key.strip()
        clean_choice = choice.strip()
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        self._validate_catalog_feat_duplicate(
            character_id, clean_catalog_key, clean_choice, repeatable, feat_id
        )
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported feat activation mode.")
        self._connection.execute(
            """
            UPDATE feats SET name = ?, target = ?, bonus_type = ?, value = ?, notes = ?,
                catalog_key = ?, catalog_category = ?, prerequisites = ?, source_url = ?,
                choice = ?, effects_json = ?, repeatable = ?, activation = ?,
                activation_note = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                target,
                bonus_type,
                value,
                notes.strip(),
                clean_catalog_key,
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                clean_choice,
                effects_json,
                int(repeatable),
                activation,
                activation_note.strip(),
                feat_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_feat_enabled(self, character_id: int, feat_id: int, enabled: bool) -> None:
        self._connection.execute(
            "UPDATE feats SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), feat_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_feat(self, character_id: int, feat_id: int) -> None:
        self._connection.execute(
            "DELETE FROM feats WHERE id = ? AND character_id = ?", (feat_id, character_id)
        )
        self._touch_character(character_id)
        self._connection.commit()

    @staticmethod
    def _validate_feat(
        name: str, target: str, bonus_type: str, value: int
    ) -> tuple[str, str, int]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Feat name cannot be empty.")
        if target and target not in STAT_TARGETS:
            raise ValueError("Unsupported feat bonus target.")
        if bonus_type not in BONUS_TYPES:
            raise ValueError("Unsupported feat bonus type.")
        return clean_name, target, value if target else 0

    @staticmethod
    def _parse_feat_effects(payload: str) -> tuple[FeatEffect, ...]:
        try:
            values = json.loads(payload or "[]")
        except (TypeError, json.JSONDecodeError):
            values = []
        result: list[FeatEffect] = []
        if isinstance(values, list):
            for value in values:
                if not isinstance(value, dict):
                    continue
                try:
                    result.append(
                        FeatEffect(
                            target=str(value.get("target", "")),
                            bonus_type=str(value.get("bonus_type", "untyped")),
                            value=int(value.get("value", 0)),
                            formula=str(value.get("formula", "")),
                            scope=str(value.get("scope", "")),
                        )
                    )
                except (TypeError, ValueError):
                    continue
        return tuple(result)

    @staticmethod
    def _normalize_feat_effects(
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...],
    ) -> tuple[tuple[FeatEffect, ...], str]:
        allowed_formulas = {
            "",
            "allow_untrained",
            "bab_2_4_at_10",
            "bab_step_5",
            "bab_step_7",
            "bab_step",
            "character_level_min_3",
            "class_skill",
            "equipped_category",
            "equipped_item",
            "half_bab_min_1",
            "half_level_round_up",
            "power_attack_damage",
            "rank_scaled_2_4",
            "rank_scaled_3_6",
            "skill_rank_base_2_step_4",
            "unarmored_bab_thirds",
        }
        skill_keys = {definition.key for definition in SKILLS}
        normalized: list[FeatEffect] = []
        for value in effects:
            if isinstance(value, FeatEffect):
                effect = value
            elif isinstance(value, dict):
                effect = FeatEffect(
                    target=str(value.get("target", "")),
                    bonus_type=str(value.get("bonus_type", "untyped")),
                    value=int(value.get("value", 0)),
                    formula=str(value.get("formula", "")),
                    scope=str(value.get("scope", "")),
                )
            else:
                raise ValueError("Unsupported feat effect.")
            valid_dynamic_target = any(
                effect.target.startswith(prefix)
                and bool(
                    re.fullmatch(
                        r"[a-z0-9][a-z0-9_-]*",
                        effect.target.removeprefix(prefix),
                    )
                )
                for prefix in DYNAMIC_EFFECT_TARGET_PREFIXES
            )
            valid_target = (
                effect.target in STAT_TARGETS
                or valid_dynamic_target
                or (
                    effect.target.startswith("skill:")
                    and effect.target.removeprefix("skill:") in skill_keys
                )
            )
            if not valid_target:
                raise ValueError(f"Unsupported feat effect target: {effect.target}")
            if effect.bonus_type not in BONUS_TYPES:
                raise ValueError("Unsupported feat effect bonus type.")
            if effect.formula not in allowed_formulas:
                raise ValueError("Unsupported feat effect formula.")
            normalized.append(effect)
        serializable = [
            {
                "target": effect.target,
                "bonus_type": effect.bonus_type,
                "value": effect.value,
                "formula": effect.formula,
                "scope": effect.scope,
            }
            for effect in normalized
        ]
        return tuple(normalized), json.dumps(serializable, separators=(",", ":"))

    def _validate_catalog_feat_duplicate(
        self,
        character_id: int,
        catalog_key: str,
        choice: str,
        repeatable: bool,
        excluding_id: int | None = None,
    ) -> None:
        if not catalog_key:
            return
        query = "SELECT id, choice FROM feats WHERE character_id = ? AND catalog_key = ?"
        rows = self._connection.execute(query, (character_id, catalog_key)).fetchall()
        rows = [row for row in rows if excluding_id is None or int(row["id"]) != excluding_id]
        if not rows:
            return
        if not repeatable:
            raise ValueError("This feat is already on the character.")
        if choice and any(str(row["choice"]).casefold() == choice.casefold() for row in rows):
            raise ValueError("This feat is already applied to that choice.")

    def _validate_catalog_trait_duplicate(
        self,
        character_id: int,
        catalog_key: str,
        choice: str,
        repeatable: bool,
        excluding_id: int | None = None,
    ) -> None:
        if not catalog_key:
            return
        rows = self._connection.execute(
            "SELECT id, choice FROM traits WHERE character_id = ? AND catalog_key = ?",
            (character_id, catalog_key),
        ).fetchall()
        rows = [row for row in rows if excluding_id is None or int(row["id"]) != excluding_id]
        if not rows:
            return
        if not repeatable:
            raise ValueError("This trait is already on the character.")
        if choice and any(str(row["choice"]).casefold() == choice.casefold() for row in rows):
            raise ValueError("This trait is already applied to that choice.")

    def list_traits(self, character_id: int) -> list[Trait]:
        rows = self._connection.execute(
            """
            SELECT id, name, enabled, target, bonus_type, value, notes,
                   catalog_key, catalog_category, prerequisites, source_url, choice,
                   effects_json, repeatable, activation, activation_note
            FROM traits WHERE character_id = ? ORDER BY name COLLATE NOCASE, id
            """,
            (character_id,),
        ).fetchall()
        return [
            Trait(
                id=int(row["id"]),
                name=str(row["name"]),
                enabled=bool(row["enabled"]),
                target=str(row["target"]),
                bonus_type=str(row["bonus_type"]),
                value=int(row["value"]),
                notes=str(row["notes"]),
                catalog_key=str(row["catalog_key"]),
                catalog_category=str(row["catalog_category"]),
                prerequisites=str(row["prerequisites"]),
                source_url=str(row["source_url"]),
                choice=str(row["choice"]),
                effects=self._parse_feat_effects(str(row["effects_json"])),
                repeatable=bool(row["repeatable"]),
                activation=str(row["activation"]),
                activation_note=str(row["activation_note"]),
            )
            for row in rows
        ]

    def add_trait(
        self,
        character_id: int,
        name: str,
        target: str = "",
        bonus_type: str = "trait",
        value: int = 0,
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        repeatable: bool = False,
        activation: str = "always",
        activation_note: str = "",
    ) -> int:
        clean_name, target, value = self._validate_trait(name, target, bonus_type, value)
        clean_catalog_key = catalog_key.strip()
        clean_choice = choice.strip()
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        self._validate_catalog_trait_duplicate(
            character_id, clean_catalog_key, clean_choice, repeatable
        )
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported trait activation mode.")
        cursor = self._connection.execute(
            """
            INSERT INTO traits
                (character_id, name, target, bonus_type, value, notes, catalog_key,
                 catalog_category, prerequisites, source_url, choice, effects_json,
                 repeatable, activation, activation_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                target,
                bonus_type,
                value,
                notes.strip(),
                clean_catalog_key,
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                clean_choice,
                effects_json,
                int(repeatable),
                activation,
                activation_note.strip(),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_trait(
        self,
        character_id: int,
        trait_id: int,
        name: str,
        target: str = "",
        bonus_type: str = "trait",
        value: int = 0,
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        repeatable: bool = False,
        activation: str = "always",
        activation_note: str = "",
    ) -> None:
        clean_name, target, value = self._validate_trait(name, target, bonus_type, value)
        clean_catalog_key = catalog_key.strip()
        clean_choice = choice.strip()
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        self._validate_catalog_trait_duplicate(
            character_id, clean_catalog_key, clean_choice, repeatable, trait_id
        )
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported trait activation mode.")
        self._connection.execute(
            """
            UPDATE traits SET name = ?, target = ?, bonus_type = ?, value = ?, notes = ?,
                catalog_key = ?, catalog_category = ?, prerequisites = ?, source_url = ?,
                choice = ?, effects_json = ?, repeatable = ?, activation = ?,
                activation_note = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                target,
                bonus_type,
                value,
                notes.strip(),
                clean_catalog_key,
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                clean_choice,
                effects_json,
                int(repeatable),
                activation,
                activation_note.strip(),
                trait_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_trait_enabled(self, character_id: int, trait_id: int, enabled: bool) -> None:
        self._connection.execute(
            "UPDATE traits SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), trait_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_trait(self, character_id: int, trait_id: int) -> None:
        self._connection.execute(
            "DELETE FROM traits WHERE id = ? AND character_id = ?", (trait_id, character_id)
        )
        self._touch_character(character_id)
        self._connection.commit()

    @staticmethod
    def _validate_trait(
        name: str, target: str, bonus_type: str, value: int
    ) -> tuple[str, str, int]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Trait name cannot be empty.")
        if target and target not in STAT_TARGETS:
            raise ValueError("Unsupported trait bonus target.")
        if bonus_type not in BONUS_TYPES:
            raise ValueError("Unsupported trait bonus type.")
        return clean_name, target, value if target else 0

    def get_martial_focus(self, character_id: int) -> MartialFocus:
        self._seed_martial_focus(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, current, maximum, recovery_method, notes
            FROM martial_focus WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown character: {character_id}")
        return MartialFocus(
            character_id=int(row["character_id"]),
            current=int(row["current"]),
            maximum=int(row["maximum"]),
            recovery_method=str(row["recovery_method"]),
            notes=str(row["notes"]),
        )

    def update_martial_focus(self, focus: MartialFocus) -> None:
        if not 1 <= focus.maximum <= 99:
            raise ValueError("Martial focus maximum must be between 1 and 99.")
        if not 0 <= focus.current <= focus.maximum:
            raise ValueError("Current martial focus must be between zero and its maximum.")
        self._connection.execute(
            """
            INSERT INTO martial_focus
                (character_id, current, maximum, recovery_method, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                current = excluded.current,
                maximum = excluded.maximum,
                recovery_method = excluded.recovery_method,
                notes = excluded.notes
            """,
            (
                focus.character_id,
                focus.current,
                focus.maximum,
                focus.recovery_method.strip(),
                focus.notes.strip(),
            ),
        )
        self._touch_character(focus.character_id)
        self._connection.commit()

    def list_character_traditions(
        self, character_id: int, kind: str | None = None
    ) -> list[CharacterTradition]:
        parameters: tuple[object, ...] = (character_id,)
        where = "character_id = ?"
        if kind is not None:
            where += " AND kind = ?"
            parameters = (character_id, kind)
        rows = self._connection.execute(
            f"""SELECT id, character_id, catalog_key, name, kind, choices_json,
                       grants_json, definition_json
                FROM character_traditions WHERE {where}
                ORDER BY kind, name COLLATE NOCASE""",
            parameters,
        ).fetchall()
        return [CharacterTradition(**dict(row)) for row in rows]

    def add_character_tradition(
        self,
        character_id: int,
        catalog_key: str,
        name: str,
        kind: str,
        choices_json: str = "{}",
        grants_json: str = "[]",
        definition_json: str = "{}",
    ) -> int:
        if kind not in {"Casting", "Martial", "Crafting", "Tinker"}:
            raise ValueError("Unknown tradition kind.")
        json.loads(choices_json)
        json.loads(grants_json)
        json.loads(definition_json)
        cursor = self._connection.execute(
            """INSERT INTO character_traditions
               (character_id, catalog_key, name, kind, choices_json, grants_json,
                definition_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                character_id, catalog_key, name.strip(), kind, choices_json,
                grants_json, definition_json,
            ),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    def delete_character_tradition(self, character_id: int, tradition_id: int) -> None:
        self._connection.execute(
            "DELETE FROM character_traditions WHERE id = ? AND character_id = ?",
            (tradition_id, character_id),
        )
        self._connection.commit()

    def update_optional_tradition_notes(self, character_id: int, tradition_id: int, notes: str) -> None:
        self._connection.execute(
            "UPDATE character_traditions SET choices_json = ? WHERE character_id = ? AND id = ? "
            "AND kind IN ('Crafting', 'Tinker')",
            (json.dumps({'Notes': [notes]} if notes else {}), character_id, tradition_id),
        )
        self._connection.commit()

    def list_audit_ignores(self, character_id: int) -> dict[str, str]:
        """Return explicitly ignored audit finding keys for one character."""

        rows = self._connection.execute(
            """
            SELECT finding_key, reason
            FROM character_audit_ignores
            WHERE character_id = ?
            ORDER BY finding_key
            """,
            (character_id,),
        ).fetchall()
        return {str(row["finding_key"]): str(row["reason"]) for row in rows}

    def set_audit_finding_ignored(
        self,
        character_id: int,
        finding_key: str,
        ignored: bool,
        reason: str = "",
    ) -> None:
        """Persist a presentation-only acknowledgement without changing rules data."""

        key = finding_key.strip()
        if not key:
            raise ValueError("An audit finding needs a stable key.")
        if ignored:
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            self._connection.execute(
                """
                INSERT INTO character_audit_ignores
                    (character_id, finding_key, reason, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(character_id, finding_key) DO UPDATE SET
                    reason = excluded.reason,
                    created_at = excluded.created_at
                """,
                (character_id, key, reason.strip(), now),
            )
        else:
            self._connection.execute(
                """
                DELETE FROM character_audit_ignores
                WHERE character_id = ? AND finding_key = ?
                """,
                (character_id, key),
            )
        self._touch_character(character_id)
        self._connection.commit()

    def get_casting_profile(self, character_id: int) -> CastingProfile:
        self._seed_casting_profile(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, casting_ability, casting_class_levels, caster_level,
                   msb_misc, dc_misc, concentration_misc, spell_points_maximum,
                   spell_points_current, spell_points_temporary, spell_points_misc, auto_spell_points,
                   tradition_name, tradition_boons, tradition_drawbacks, tradition_notes
            FROM casting_profiles WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown character: {character_id}")
        return CastingProfile(
            character_id=int(row["character_id"]),
            casting_ability=str(row["casting_ability"]),
            casting_class_levels=int(row["casting_class_levels"]),
            caster_level=int(row["caster_level"]),
            msb_misc=int(row["msb_misc"]),
            dc_misc=int(row["dc_misc"]),
            concentration_misc=int(row["concentration_misc"]),
            spell_points_maximum=int(row["spell_points_maximum"]),
            spell_points_current=int(row["spell_points_current"]),
            spell_points_temporary=int(row["spell_points_temporary"]),
            spell_points_misc=int(row["spell_points_misc"]),
            auto_spell_points=bool(row["auto_spell_points"]),
            tradition_name=str(row["tradition_name"]),
            tradition_boons=str(row["tradition_boons"]),
            tradition_drawbacks=str(row["tradition_drawbacks"]),
            tradition_notes=str(row["tradition_notes"]),
        )

    def update_casting_profile(self, profile: CastingProfile) -> None:
        if profile.casting_ability not in ABILITY_KEYS:
            raise ValueError("Unsupported casting ability.")
        bounded_values = (
            profile.casting_class_levels,
            profile.caster_level,
            profile.spell_points_maximum,
            profile.spell_points_current,
            profile.spell_points_temporary,
        )
        if any(value < 0 or value > 99999 for value in bounded_values):
            raise ValueError("Casting levels and spell points must be non-negative.")
        self._connection.execute(
            """
            INSERT INTO casting_profiles
                (character_id, casting_ability, casting_class_levels, caster_level,
                 msb_misc, dc_misc, concentration_misc, spell_points_maximum,
                 spell_points_current, spell_points_temporary, spell_points_misc, auto_spell_points,
                 tradition_name, tradition_boons, tradition_drawbacks, tradition_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                casting_ability = excluded.casting_ability,
                casting_class_levels = excluded.casting_class_levels,
                caster_level = excluded.caster_level,
                msb_misc = excluded.msb_misc,
                dc_misc = excluded.dc_misc,
                concentration_misc = excluded.concentration_misc,
                spell_points_maximum = excluded.spell_points_maximum,
                spell_points_current = excluded.spell_points_current,
                spell_points_temporary = excluded.spell_points_temporary,
                spell_points_misc = excluded.spell_points_misc,
                auto_spell_points = excluded.auto_spell_points,
                tradition_name = excluded.tradition_name,
                tradition_boons = excluded.tradition_boons,
                tradition_drawbacks = excluded.tradition_drawbacks,
                tradition_notes = excluded.tradition_notes
            """,
            (
                profile.character_id,
                profile.casting_ability,
                profile.casting_class_levels,
                profile.caster_level,
                profile.msb_misc,
                profile.dc_misc,
                profile.concentration_misc,
                profile.spell_points_maximum,
                profile.spell_points_current,
                profile.spell_points_temporary,
                profile.spell_points_misc,
                int(profile.auto_spell_points),
                profile.tradition_name.strip(),
                profile.tradition_boons.strip(),
                profile.tradition_drawbacks.strip(),
                profile.tradition_notes.strip(),
            ),
        )
        self._touch_character(profile.character_id)
        self._connection.commit()

    def list_sphere_statistics(self, character_id: int) -> list[SphereStatistic]:
        rows = self._connection.execute(
            """
            SELECT character_id, sphere, caster_level_bonus, dc_bonus, notes
            FROM sphere_statistics
            WHERE character_id = ?
            ORDER BY sphere COLLATE NOCASE
            """,
            (character_id,),
        ).fetchall()
        return [
            SphereStatistic(
                character_id=int(row["character_id"]),
                sphere=str(row["sphere"]),
                caster_level_bonus=int(row["caster_level_bonus"]),
                dc_bonus=int(row["dc_bonus"]),
                notes=str(row["notes"]),
            )
            for row in rows
        ]

    def update_sphere_statistic(self, statistic: SphereStatistic) -> None:
        sphere = statistic.sphere.strip()
        if not sphere:
            raise ValueError("Sphere name cannot be empty.")
        self._connection.execute(
            """
            INSERT INTO sphere_statistics
                (character_id, sphere, caster_level_bonus, dc_bonus, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_id, sphere) DO UPDATE SET
                caster_level_bonus = excluded.caster_level_bonus,
                dc_bonus = excluded.dc_bonus,
                notes = excluded.notes
            """,
            (
                statistic.character_id,
                sphere,
                statistic.caster_level_bonus,
                statistic.dc_bonus,
                statistic.notes.strip(),
            ),
        )
        self._touch_character(statistic.character_id)
        self._connection.commit()

    def delete_sphere_statistic(self, character_id: int, sphere: str) -> None:
        self._connection.execute(
            "DELETE FROM sphere_statistics WHERE character_id = ? AND sphere = ?",
            (character_id, sphere.strip()),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_martial_talents(self, character_id: int) -> list[MartialTalent]:
        rows = self._connection.execute(
            """
            SELECT id, name, sphere, talent_type, notes, catalog_key,
                   catalog_category, prerequisites, source_url, enabled, choice,
                   effects_json, activation, activation_note
            FROM martial_talents
            WHERE character_id = ?
            ORDER BY sphere COLLATE NOCASE, name COLLATE NOCASE, id
            """,
            (character_id,),
        ).fetchall()
        return [
            MartialTalent(
                id=int(row["id"]),
                name=str(row["name"]),
                sphere=str(row["sphere"]),
                talent_type=str(row["talent_type"]),
                notes=str(row["notes"]),
                catalog_key=str(row["catalog_key"]),
                catalog_category=str(row["catalog_category"]),
                prerequisites=str(row["prerequisites"]),
                source_url=str(row["source_url"]),
                enabled=bool(row["enabled"]),
                choice=str(row["choice"]),
                effects=self._parse_feat_effects(str(row["effects_json"])),
                activation=str(row["activation"]),
                activation_note=str(row["activation_note"]),
            )
            for row in rows
        ]

    def list_flexible_talent_selections(
        self, character_id: int, source_key: str | None = None
    ) -> list[FlexibleTalentSelection]:
        where = "character_id = ?"
        parameters: tuple[object, ...] = (character_id,)
        if source_key is not None:
            where += " AND source_key = ?"
            parameters = (character_id, source_key)
        rows = self._connection.execute(
            f"""
            SELECT id, character_id, source_key, slot_index, talent_kind,
                   catalog_key, name, sphere, category, description, choice, choice_key
            FROM flexible_talent_selections
            WHERE {where}
            ORDER BY source_key COLLATE NOCASE, slot_index, id
            """,
            parameters,
        ).fetchall()
        return [
            FlexibleTalentSelection(
                id=int(row["id"]),
                character_id=int(row["character_id"]),
                source_key=str(row["source_key"]),
                slot_index=int(row["slot_index"]),
                talent_kind=str(row["talent_kind"]),
                catalog_key=str(row["catalog_key"]),
                name=str(row["name"]),
                sphere=str(row["sphere"]),
                category=str(row["category"]),
                description=str(row["description"]),
                choice=str(row["choice"]),
                choice_key=str(row["choice_key"]),
            )
            for row in rows
        ]

    def replace_flexible_talent_selections(
        self,
        character_id: int,
        source_key: str,
        selections: list[dict] | tuple[dict, ...],
    ) -> None:
        """Atomically replace one provider's flexible slots.

        The generic source boundary is intentionally reusable for future class
        features; Exploitant is only the first consumer.
        """

        clean_source = source_key.strip()
        if not clean_source:
            raise ValueError("Flexible talent source cannot be empty.")
        normalized: list[tuple[object, ...]] = []
        for index, raw in enumerate(selections):
            kind = str(raw.get("talent_kind") or "").strip().casefold()
            if kind not in {"martial", "magic"}:
                raise ValueError("Flexible talents must be martial or magic talents.")
            catalog_key = str(raw.get("catalog_key") or "").strip()
            name = str(raw.get("name") or "").strip()
            if not catalog_key or not name:
                raise ValueError("Flexible talent selections require a catalog entry.")
            normalized.append((
                character_id,
                clean_source,
                index,
                kind,
                catalog_key,
                name,
                str(raw.get("sphere") or "").strip(),
                str(raw.get("category") or "Talent").strip() or "Talent",
                str(raw.get("description") or "").strip(),
                str(raw.get("choice") or "").strip(),
                str(raw.get("choice_key") or "").strip(),
            ))
        with self._connection:
            self._connection.execute(
                "DELETE FROM flexible_talent_selections WHERE character_id = ? AND source_key = ?",
                (character_id, clean_source),
            )
            self._connection.executemany(
                """
                INSERT INTO flexible_talent_selections
                    (character_id, source_key, slot_index, talent_kind, catalog_key,
                     name, sphere, category, description, choice, choice_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                normalized,
            )
            self._connection.execute(
                """
                INSERT INTO flexible_talent_source_states
                    (character_id, source_key, change_available)
                VALUES (?, ?, 0)
                ON CONFLICT(character_id, source_key)
                DO UPDATE SET change_available = 0
                """,
                (character_id, clean_source),
            )
            self._touch_character(character_id)

    def flexible_talent_change_available(
        self, character_id: int, source_key: str
    ) -> bool:
        row = self._connection.execute(
            """
            SELECT change_available FROM flexible_talent_source_states
            WHERE character_id = ? AND source_key = ?
            """,
            (character_id, source_key.strip()),
        ).fetchone()
        return True if row is None else bool(row["change_available"])

    def set_flexible_talent_change_available(
        self, character_id: int, source_key: str, available: bool
    ) -> None:
        clean_source = source_key.strip()
        if not clean_source:
            raise ValueError("Flexible talent source cannot be empty.")
        self._connection.execute(
            """
            INSERT INTO flexible_talent_source_states
                (character_id, source_key, change_available)
            VALUES (?, ?, ?)
            ON CONFLICT(character_id, source_key)
            DO UPDATE SET change_available = excluded.change_available
            """,
            (character_id, clean_source, int(available)),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def add_martial_talent(
        self,
        character_id: int,
        name: str,
        sphere: str = "",
        talent_type: str = "Talent",
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        activation: str = "always",
        activation_note: str = "",
        allow_duplicate_catalog: bool = False,
    ) -> int:
        clean_name = self._validate_martial_talent(name, talent_type)
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported martial talent activation mode.")
        if catalog_key and not allow_duplicate_catalog and self._connection.execute(
            "SELECT 1 FROM martial_talents WHERE character_id = ? AND catalog_key = ?",
            (character_id, catalog_key),
        ).fetchone() is not None:
            raise ValueError("This sphere or talent is already on the character.")
        cursor = self._connection.execute(
            """
            INSERT INTO martial_talents
                (character_id, name, sphere, talent_type, notes, catalog_key,
                 catalog_category, prerequisites, source_url, choice, effects_json,
                 activation, activation_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                sphere.strip(),
                talent_type,
                notes.strip(),
                catalog_key.strip(),
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                choice.strip(),
                effects_json,
                activation,
                activation_note.strip(),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_martial_talent(
        self,
        character_id: int,
        talent_id: int,
        name: str,
        sphere: str = "",
        talent_type: str = "Talent",
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        activation: str = "always",
        activation_note: str = "",
    ) -> None:
        clean_name = self._validate_martial_talent(name, talent_type)
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported martial talent activation mode.")
        self._connection.execute(
            """
            UPDATE martial_talents
            SET name = ?, sphere = ?, talent_type = ?, notes = ?, catalog_key = ?,
                catalog_category = ?, prerequisites = ?, source_url = ?, choice = ?,
                effects_json = ?, activation = ?, activation_note = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                sphere.strip(),
                talent_type,
                notes.strip(),
                catalog_key.strip(),
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                choice.strip(),
                effects_json,
                activation,
                activation_note.strip(),
                talent_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_martial_talent_enabled(
        self, character_id: int, talent_id: int, enabled: bool
    ) -> None:
        self._connection.execute(
            "UPDATE martial_talents SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), talent_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_martial_talent(self, character_id: int, talent_id: int) -> None:
        self._connection.execute(
            "DELETE FROM martial_talents WHERE id = ? AND character_id = ?",
            (talent_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    @staticmethod
    def _validate_martial_talent(name: str, talent_type: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Martial talent name cannot be empty.")
        if talent_type not in MARTIAL_TALENT_TYPES:
            raise ValueError("Unsupported martial talent type.")
        return clean_name

    def list_spells(self, character_id: int) -> list[Spell]:
        rows = self._connection.execute(
            """
            SELECT id, name, system, level, school_or_sphere, uses_max, uses_used,
                   casting_time, range, duration, save, spell_resistance, notes,
                   catalog_key, catalog_category, prerequisites, source_url, enabled,
                   choice, effects_json, activation, activation_note
            FROM spells
            WHERE character_id = ?
            ORDER BY level, name COLLATE NOCASE, id
            """,
            (character_id,),
        ).fetchall()
        return [
            Spell(
                id=int(row["id"]),
                name=str(row["name"]),
                system=str(row["system"]),
                level=int(row["level"]),
                school_or_sphere=str(row["school_or_sphere"]),
                uses_max=int(row["uses_max"]),
                uses_used=int(row["uses_used"]),
                casting_time=str(row["casting_time"]),
                range=str(row["range"]),
                duration=str(row["duration"]),
                save=str(row["save"]),
                spell_resistance=str(row["spell_resistance"]),
                notes=str(row["notes"]),
                catalog_key=str(row["catalog_key"]),
                catalog_category=str(row["catalog_category"]),
                prerequisites=str(row["prerequisites"]),
                source_url=str(row["source_url"]),
                enabled=bool(row["enabled"]),
                choice=str(row["choice"]),
                effects=self._parse_feat_effects(str(row["effects_json"])),
                activation=str(row["activation"]),
                activation_note=str(row["activation_note"]),
            )
            for row in rows
        ]

    def add_spell(
        self,
        character_id: int,
        name: str,
        system: str = "Prepared",
        level: int = 0,
        school_or_sphere: str = "",
        uses_max: int = 0,
        uses_used: int = 0,
        casting_time: str = "",
        range: str = "",
        duration: str = "",
        save: str = "",
        spell_resistance: str = "",
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        activation: str = "always",
        activation_note: str = "",
    ) -> int:
        clean_name = self._validate_spell(name, system, level, uses_max, uses_used)
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported magic talent activation mode.")
        if catalog_key and self._connection.execute(
            "SELECT 1 FROM spells WHERE character_id = ? AND catalog_key = ?",
            (character_id, catalog_key),
        ).fetchone() is not None:
            raise ValueError("This magic sphere, talent, or drawback is already on the character.")
        cursor = self._connection.execute(
            """
            INSERT INTO spells
                (character_id, name, system, level, school_or_sphere, uses_max, uses_used,
                 casting_time, range, duration, save, spell_resistance, notes,
                 catalog_key, catalog_category, prerequisites, source_url, choice,
                 effects_json, activation, activation_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                system,
                level,
                school_or_sphere.strip(),
                uses_max,
                uses_used,
                casting_time.strip(),
                range.strip(),
                duration.strip(),
                save.strip(),
                spell_resistance.strip(),
                notes.strip(),
                catalog_key.strip(),
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                choice.strip(),
                effects_json,
                activation,
                activation_note.strip(),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_spell(
        self,
        character_id: int,
        spell_id: int,
        name: str,
        system: str = "Prepared",
        level: int = 0,
        school_or_sphere: str = "",
        uses_max: int = 0,
        uses_used: int = 0,
        casting_time: str = "",
        range: str = "",
        duration: str = "",
        save: str = "",
        spell_resistance: str = "",
        notes: str = "",
        catalog_key: str = "",
        catalog_category: str = "",
        prerequisites: str = "",
        source_url: str = "",
        choice: str = "",
        effects: list[dict] | tuple[dict, ...] | tuple[FeatEffect, ...] = (),
        activation: str = "always",
        activation_note: str = "",
    ) -> None:
        clean_name = self._validate_spell(name, system, level, uses_max, uses_used)
        _clean_effects, effects_json = self._normalize_feat_effects(effects)
        if activation not in ("always", "toggle"):
            raise ValueError("Unsupported magic talent activation mode.")
        self._connection.execute(
            """
            UPDATE spells SET
                name = ?, system = ?, level = ?, school_or_sphere = ?,
                uses_max = ?, uses_used = ?, casting_time = ?, range = ?, duration = ?,
                save = ?, spell_resistance = ?, notes = ?, catalog_key = ?,
                catalog_category = ?, prerequisites = ?, source_url = ?, choice = ?,
                effects_json = ?, activation = ?, activation_note = ?
            WHERE id = ? AND character_id = ?
            """,
            (
                clean_name,
                system,
                level,
                school_or_sphere.strip(),
                uses_max,
                uses_used,
                casting_time.strip(),
                range.strip(),
                duration.strip(),
                save.strip(),
                spell_resistance.strip(),
                notes.strip(),
                catalog_key.strip(),
                catalog_category.strip(),
                prerequisites.strip(),
                source_url.strip(),
                choice.strip(),
                effects_json,
                activation,
                activation_note.strip(),
                spell_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def update_spell_duration(
        self, character_id: int, spell_id: int, duration: str
    ) -> None:
        """Update only a spell or sphere record's user-editable duration.

        Keeping this narrow operation separate prevents a small presentation
        edit from accidentally overwriting catalog metadata or automation.
        """

        cursor = self._connection.execute(
            "UPDATE spells SET duration = ? WHERE id = ? AND character_id = ?",
            (duration.strip(), spell_id, character_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("That spell or sphere ability no longer exists.")
        self._touch_character(character_id)
        self._connection.commit()

    def set_spell_enabled(self, character_id: int, spell_id: int, enabled: bool) -> None:
        self._connection.execute(
            "UPDATE spells SET enabled = ? WHERE id = ? AND character_id = ?",
            (int(enabled), spell_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def set_spell_uses_used(self, character_id: int, spell_id: int, uses_used: int) -> None:
        row = self._connection.execute(
            "SELECT uses_max FROM spells WHERE id = ? AND character_id = ?",
            (spell_id, character_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown spell: {spell_id}")
        uses_max = int(row["uses_max"])
        if uses_max == 0 or not 0 <= uses_used <= uses_max:
            raise ValueError("Used spell charges must be between zero and the available uses.")
        self._connection.execute(
            "UPDATE spells SET uses_used = ? WHERE id = ? AND character_id = ?",
            (uses_used, spell_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_spell(self, character_id: int, spell_id: int) -> None:
        self._connection.execute(
            "DELETE FROM spells WHERE id = ? AND character_id = ?", (spell_id, character_id)
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_prepared_spells(self, character_id: int) -> list[PreparedSpell]:
        rows = self._connection.execute(
            """
            SELECT ps.id, ps.character_id, ps.class_level_id, ps.known_spell_id,
                   CASE WHEN ps.custom = 0 THEN s.name ELSE ps.name END AS display_name,
                   CASE WHEN ps.custom = 0 THEN s.level ELSE ps.level END AS display_level,
                   ps.prepared_count, ps.used_count, ps.catalog_key, ps.custom
            FROM prepared_spells ps
            LEFT JOIN spells s ON s.id = ps.known_spell_id
            WHERE ps.character_id = ?
            ORDER BY ps.class_level_id, display_level, display_name COLLATE NOCASE, ps.id
            """,
            (character_id,),
        ).fetchall()
        return [
            PreparedSpell(
                id=int(row["id"]),
                character_id=int(row["character_id"]),
                class_level_id=int(row["class_level_id"]),
                known_spell_id=(
                    int(row["known_spell_id"])
                    if row["known_spell_id"] is not None
                    else None
                ),
                name=str(row["display_name"]),
                level=int(row["display_level"]),
                prepared_count=int(row["prepared_count"]),
                used_count=int(row["used_count"]),
                catalog_key=str(row["catalog_key"]),
                custom=bool(row["custom"]),
            )
            for row in rows
        ]

    def add_prepared_spell(
        self,
        character_id: int,
        class_level_id: int,
        known_spell_id: int | None = None,
        *,
        name: str = "",
        level: int = 0,
        prepared_count: int = 1,
        used_count: int = 0,
        catalog_key: str = "",
        custom: bool = False,
    ) -> int:
        owner = self._connection.execute(
            "SELECT 1 FROM class_levels WHERE id = ? AND character_id = ?",
            (class_level_id, character_id),
        ).fetchone()
        if owner is None:
            raise ValueError("Prepared spell class does not belong to this character.")
        if not 1 <= prepared_count <= 999 or not 0 <= used_count <= prepared_count:
            raise ValueError("Prepared and used copies are outside the supported range.")
        if custom:
            clean_name = name.strip()
            if not clean_name or not 0 <= level <= 9:
                raise ValueError("A custom prepared spell needs a name and spell level 0–9.")
            known_spell_id = None
        else:
            row = self._connection.execute(
                "SELECT name, level, system FROM spells WHERE id = ? AND character_id = ?",
                (known_spell_id, character_id),
            ).fetchone()
            if row is None or str(row["system"]) == "Sphere":
                raise ValueError("Prepared spells must come from this character's Spells Known list.")
            clean_name = str(row["name"])
            level = int(row["level"])
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO prepared_spells
                    (character_id, class_level_id, known_spell_id, name, level,
                     prepared_count, used_count, catalog_key, custom)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    character_id, class_level_id, known_spell_id, clean_name, level,
                    prepared_count, used_count, catalog_key.strip(), int(custom),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("That spell is already prepared for this class; edit its quantity instead.") from error
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_prepared_spell_counts(
        self,
        character_id: int,
        prepared_spell_id: int,
        prepared_count: int,
        used_count: int,
    ) -> None:
        if not 1 <= prepared_count <= 999 or not 0 <= used_count <= prepared_count:
            raise ValueError("Used copies cannot exceed prepared copies.")
        cursor = self._connection.execute(
            """
            UPDATE prepared_spells SET prepared_count = ?, used_count = ?
            WHERE id = ? AND character_id = ?
            """,
            (prepared_count, used_count, prepared_spell_id, character_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown prepared spell: {prepared_spell_id}")
        self._touch_character(character_id)
        self._connection.commit()

    def reset_prepared_spell_uses(self, character_id: int) -> int:
        restored = int(
            self._connection.execute(
                "SELECT COALESCE(SUM(used_count), 0) FROM prepared_spells WHERE character_id = ?",
                (character_id,),
            ).fetchone()[0]
        )
        self._connection.execute(
            "UPDATE prepared_spells SET used_count = 0 WHERE character_id = ?",
            (character_id,),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return restored

    def delete_prepared_spell(self, character_id: int, prepared_spell_id: int) -> None:
        self._connection.execute(
            "DELETE FROM prepared_spells WHERE id = ? AND character_id = ?",
            (prepared_spell_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def list_spontaneous_slot_uses(
        self, character_id: int
    ) -> list[SpontaneousSlotUse]:
        rows = self._connection.execute(
            """
            SELECT character_id, class_level_id, spell_level, used_count
            FROM spontaneous_spell_slots
            WHERE character_id = ?
            ORDER BY class_level_id, spell_level
            """,
            (character_id,),
        ).fetchall()
        return [
            SpontaneousSlotUse(
                character_id=int(row["character_id"]),
                class_level_id=int(row["class_level_id"]),
                spell_level=int(row["spell_level"]),
                used_count=int(row["used_count"]),
            )
            for row in rows
        ]

    def set_spontaneous_slot_uses(
        self,
        character_id: int,
        class_level_id: int,
        spell_level: int,
        used_count: int,
    ) -> None:
        owner = self._connection.execute(
            "SELECT 1 FROM class_levels WHERE id = ? AND character_id = ?",
            (class_level_id, character_id),
        ).fetchone()
        if owner is None:
            raise ValueError("Spontaneous casting class does not belong to this character.")
        if not 1 <= int(spell_level) <= 9 or not 0 <= int(used_count) <= 999:
            raise ValueError("Spontaneous slot usage is outside the supported range.")
        self._connection.execute(
            """
            INSERT INTO spontaneous_spell_slots
                (character_id, class_level_id, spell_level, used_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(character_id, class_level_id, spell_level)
            DO UPDATE SET used_count = excluded.used_count
            """,
            (character_id, class_level_id, spell_level, used_count),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def reset_spontaneous_slot_uses(self, character_id: int) -> int:
        restored = int(
            self._connection.execute(
                "SELECT COALESCE(SUM(used_count), 0) FROM spontaneous_spell_slots WHERE character_id = ?",
                (character_id,),
            ).fetchone()[0]
        )
        self._connection.execute(
            "UPDATE spontaneous_spell_slots SET used_count = 0 WHERE character_id = ?",
            (character_id,),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return restored

    @staticmethod
    def _validate_spell(
        name: str, system: str, level: int, uses_max: int, uses_used: int
    ) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Spell name cannot be empty.")
        if system not in SPELL_SYSTEMS:
            raise ValueError("Unsupported spell system.")
        if not 0 <= level <= 9:
            raise ValueError("Spell level must be between zero and nine.")
        if not 0 <= uses_max <= 999:
            raise ValueError("Spell uses must be between zero and 999.")
        if uses_max == 0 and uses_used != 0:
            raise ValueError("At-will spells cannot have used charges.")
        if uses_max and not 0 <= uses_used <= uses_max:
            raise ValueError("Used spell charges cannot exceed available uses.")
        return clean_name

    def get_prodigy_sequence(self, character_id: int) -> ProdigySequence:
        self._seed_prodigy_sequence(character_id)
        row = self._connection.execute(
            """
            SELECT character_id, active, current, maximum, imbue_key
            FROM prodigy_sequence WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown character: {character_id}")
        return ProdigySequence(
            character_id=int(row["character_id"]),
            active=bool(row["active"]),
            current=int(row["current"]),
            maximum=int(row["maximum"]),
            imbue_key=str(row["imbue_key"]),
        )

    def update_prodigy_sequence(self, sequence: ProdigySequence) -> None:
        if not 1 <= sequence.maximum <= 99:
            raise ValueError("Maximum sequence length must be between 1 and 99.")
        if sequence.active and not 1 <= sequence.current <= sequence.maximum:
            raise ValueError("An active sequence must contain at least one link.")
        if not sequence.active and sequence.current != 0:
            raise ValueError("An inactive sequence must have zero links.")
        self._connection.execute(
            """
            INSERT INTO prodigy_sequence (character_id, active, current, maximum, imbue_key)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                active = excluded.active,
                current = excluded.current,
                maximum = excluded.maximum,
                imbue_key = excluded.imbue_key
            """,
            (
                sequence.character_id,
                int(sequence.active),
                sequence.current,
                sequence.maximum,
                sequence.imbue_key.strip(),
            ),
        )
        self._touch_character(sequence.character_id)
        self._connection.commit()

    def list_sequence_options(
        self, character_id: int, option_type: str | None = None
    ) -> list[SequenceOption]:
        parameters: tuple = (character_id,)
        where = "character_id = ?"
        if option_type is not None:
            if option_type not in SEQUENCE_OPTION_TYPES:
                raise ValueError("Unsupported sequence option type.")
            where += " AND option_type = ?"
            parameters = (character_id, option_type)
        rows = self._connection.execute(
            f"""
            SELECT id, name, option_type, sphere, minimum_links, action, notes, built_in
            FROM sequence_options WHERE {where}
            ORDER BY option_type, name COLLATE NOCASE, id
            """,
            parameters,
        ).fetchall()
        return [
            SequenceOption(
                id=int(row["id"]),
                name=str(row["name"]),
                option_type=str(row["option_type"]),
                sphere=str(row["sphere"]),
                minimum_links=int(row["minimum_links"]),
                action=str(row["action"]),
                notes=str(row["notes"]),
                built_in=bool(row["built_in"]),
            )
            for row in rows
        ]

    def add_sequence_option(
        self,
        character_id: int,
        name: str,
        option_type: str,
        sphere: str = "",
        minimum_links: int = 0,
        action: str = "",
        notes: str = "",
        built_in: bool = False,
    ) -> int:
        clean_name, minimum_links = self._validate_sequence_option(
            name, option_type, minimum_links
        )
        cursor = self._connection.execute(
            """
            INSERT INTO sequence_options
                (character_id, name, option_type, sphere, minimum_links, action, notes, built_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                clean_name,
                option_type,
                sphere.strip(),
                minimum_links,
                action.strip(),
                notes.strip(),
                int(built_in),
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_sequence_option(
        self,
        character_id: int,
        option_id: int,
        name: str,
        option_type: str,
        sphere: str = "",
        minimum_links: int = 0,
        action: str = "",
        notes: str = "",
    ) -> None:
        clean_name, minimum_links = self._validate_sequence_option(
            name, option_type, minimum_links
        )
        self._connection.execute(
            """
            UPDATE sequence_options SET
                name = ?, option_type = ?, sphere = ?, minimum_links = ?,
                action = ?, notes = ?
            WHERE id = ? AND character_id = ? AND built_in = 0
            """,
            (
                clean_name,
                option_type,
                sphere.strip(),
                minimum_links,
                action.strip(),
                notes.strip(),
                option_id,
                character_id,
            ),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def delete_sequence_option(self, character_id: int, option_id: int) -> None:
        self._connection.execute(
            "DELETE FROM sequence_options WHERE id = ? AND character_id = ? AND built_in = 0",
            (option_id, character_id),
        )
        self._touch_character(character_id)
        self._connection.commit()

    def sync_builtin_sphere_sequence_options(
        self,
        character_id: int,
        options: tuple,
    ) -> None:
        """Keep sphere-granted Prodigy options aligned with the owned base spheres."""
        existing = {
            (item.option_type, item.sphere.casefold(), item.name.casefold()): item
            for item in self.list_sequence_options(character_id)
            if item.built_in and item.sphere
        }
        desired = {
            (item.option_type, item.sphere.casefold(), item.name.casefold()): item
            for item in options
        }
        changed = False
        for key, item in existing.items():
            if key not in desired:
                self._connection.execute(
                    "DELETE FROM sequence_options WHERE id = ? AND character_id = ? AND built_in = 1",
                    (item.id, character_id),
                )
                changed = True
        for key, item in desired.items():
            current = existing.get(key)
            values = (
                item.minimum_links,
                item.action.strip(),
                item.description.strip(),
            )
            if current is None:
                self._connection.execute(
                    """
                    INSERT INTO sequence_options
                        (character_id, name, option_type, sphere, minimum_links, action, notes, built_in)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        character_id,
                        item.name,
                        item.option_type,
                        item.sphere,
                        *values,
                    ),
                )
                changed = True
            elif values != (current.minimum_links, current.action, current.notes):
                self._connection.execute(
                    """
                    UPDATE sequence_options
                    SET minimum_links = ?, action = ?, notes = ?
                    WHERE id = ? AND character_id = ? AND built_in = 1
                    """,
                    (*values, current.id, character_id),
                )
                changed = True
        if changed:
            self._touch_character(character_id)
            self._connection.commit()

    @staticmethod
    def _validate_sequence_option(
        name: str, option_type: str, minimum_links: int
    ) -> tuple[str, int]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Sequence option name cannot be empty.")
        if option_type not in SEQUENCE_OPTION_TYPES:
            raise ValueError("Unsupported sequence option type.")
        if not 0 <= minimum_links <= 99:
            raise ValueError("Minimum links must be between zero and 99.")
        return clean_name, minimum_links if option_type == "Finisher" else 0

    def _touch_character(self, character_id: int) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        self._connection.execute(
            "UPDATE characters SET updated_at = ? WHERE id = ?", (now, character_id)
        )

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _validate_name(name: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Character name cannot be empty.")
        return clean_name

    @staticmethod
    def _to_summary(row: sqlite3.Row) -> CharacterSummary:
        return CharacterSummary(
            id=int(row["id"]),
            name=str(row["name"]),
            character_type=str(row["character_type"]),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
