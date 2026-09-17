from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CharacterSummary:
    id: int
    name: str
    character_type: str
    updated_at: datetime


CHARACTER_TYPES = ("Pathfinder 1e", "Spheres")

ABILITIES = (
    ("strength", "Strength", "STR"),
    ("dexterity", "Dexterity", "DEX"),
    ("constitution", "Constitution", "CON"),
    ("intelligence", "Intelligence", "INT"),
    ("wisdom", "Wisdom", "WIS"),
    ("charisma", "Charisma", "CHA"),
)

ABILITY_KEYS = tuple(key for key, _, _ in ABILITIES)

BONUS_TYPES = (
    "armor",
    "shield",
    "natural armor",
    "natural armor enhancement",
    "deflection",
    "dodge",
    "resistance",
    "racial",
    "enhancement",
    "inherent",
    "size",
    "age",
    "morale",
    "luck",
    "sacred",
    "profane",
    "circumstance",
    "untyped",
    "condition",
    "competence",
    "insight",
    "trait",
)

COMBAT_TARGETS = (
    "initiative",
    "fortitude",
    "reflex",
    "will",
    "ac",
    "touch_ac",
    "flat_footed_ac",
    "cmb",
    "cmd",
)
GLOBAL_TARGETS = (
    "attack", "damage", "skills", "hp", "land_speed", "armor_speed",
    "fly_speed", "swim_speed", "climb_speed", "burrow_speed",
    "teleport_speed", "caster_level",
    "save_dc", "concentration", "magic_skill_bonus", "magic_skill_defense",
    "spell_resistance", "spell_points",
)
STAT_TARGETS = ABILITY_KEYS + COMBAT_TARGETS + GLOBAL_TARGETS
DYNAMIC_EFFECT_TARGET_PREFIXES = (
    "sphere_save_dc:",
)

SIZES = (
    "Fine",
    "Diminutive",
    "Tiny",
    "Small",
    "Medium",
    "Large",
    "Huge",
    "Gargantuan",
    "Colossal",
)

ALIGNMENTS = ("", "LG", "NG", "CG", "LN", "N", "CN", "LE", "NE", "CE")
BAB_PROGRESSIONS = ("Full", "3/4", "1/2")
SAVE_PROGRESSIONS = ("Good", "Poor")
CUSTOM_TRACKER_TYPES = ("calculated", "counter", "pool")
TRACKER_RECOVERY_EVENTS = ("none", "full_rest")
TRACKER_RECOVERY_OPERATIONS = ("none", "set_to_max", "reset_to_zero")


@dataclass(frozen=True, slots=True)
class StatModifier:
    id: int | None
    target: str
    source: str
    bonus_type: str
    value: int
    enabled: bool = True
    disabled_reason: str = ""


@dataclass(frozen=True, slots=True)
class RaceTraitChoice:
    """One persisted answer to a catalog-defined racial-trait choice."""

    trait_key: str
    choice_key: str
    values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CharacterDetails:
    character_id: int
    player_name: str = ""
    race: str = ""
    alignment: str = ""
    deity: str = ""
    size: str = "Medium"
    race_key: str = ""
    race_ability_choice: str = ""
    race_variant_key: str = ""
    race_alternate_trait_keys: tuple[str, ...] = ()
    race_trait_choices: tuple[RaceTraitChoice, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassLevel:
    id: int
    class_name: str
    level: int
    bab_progression: str
    fort_progression: str
    reflex_progression: str
    will_progression: str
    preset_key: str = ""
    hit_die: int = 0
    hp_gained: int = 0


@dataclass(frozen=True, slots=True)
class ProficiencyAdjustment:
    """Character-owned display override for one class level's proficiencies."""

    character_id: int
    class_level_id: int
    weapons: str = ""
    armor: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SpecialAbilityAdjustment:
    """A character-owned overlay for an automatically resolved class feature."""

    id: int
    character_id: int
    feature_key: str
    level: int
    name: str
    description: str = ""
    hidden: bool = False
    custom: bool = False


@dataclass(frozen=True, slots=True)
class ClassFeatureSelection:
    """A reusable selection attached to a class feature such as Domain."""

    character_id: int
    class_level_id: int
    feature_key: str
    option_type: str = ""
    option_key: str = ""
    name: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class ClassFeatureState:
    """Mutable play state for one resolved class-feature building block.

    Definitions and scaling remain in the rules registry.  This record stores
    only character-specific use, activation, choices, and optional overrides,
    so archetype changes can safely hide or restore a system without data loss.
    """

    character_id: int
    class_level_id: int
    feature_key: str
    current_value: int | None = None
    maximum_adjustment: int = 0
    maximum_override: int | None = None
    active: bool = False
    choices_json: str = "[]"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class AnimalCompanion:
    """One character's companion record; published progression remains derived."""

    character_id: int
    name: str = ""
    species_key: str = ""
    effective_level_adjustment: int = 0
    effective_level_override: int | None = None
    current_hp: int = 0
    temporary_hp: int = 0
    ability_overrides_json: str = "{}"
    skill_ranks_json: str = "{}"
    feats_json: str = "[]"
    tricks_json: str = "[]"
    special_abilities_json: str = "[]"
    details_json: str = "{}"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class BondedCompanion:
    """Extensible character-owned record for familiars and class companions."""

    character_id: int
    companion_key: str
    name: str = ""
    species: str = ""
    current_hp: int = 0
    temporary_hp: int = 0
    details_json: str = "{}"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class FavoredClassBonus:
    """Per-class allocation of the PF1e favored-class reward.

    ``manual_code`` deliberately remains descriptive.  It records campaign- or
    race-specific favored-class choices without teaching the core calculation
    service about every possible published option.
    """

    character_id: int
    class_level_id: int
    hp_bonus: int = 0
    skill_point_bonus: int = 0
    manual_bonus: int = 0
    manual_code: str = ""


@dataclass(frozen=True, slots=True)
class AdvancementAdjustment:
    """Character-specific correction layered over an automatic rules budget."""

    character_id: int
    budget_key: str
    adjustment: int = 0
    override_total: int | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class AbilityScoreIncreaseAllocation:
    """A permanent level-based ability-score increase assigned by the player.

    Base scores remain the values chosen during character creation.  Keeping
    level increases in their own source layer makes them auditable, reversible,
    and safe to combine with future alternate advancement rules.
    """

    character_id: int
    ability: str
    points: int = 0


@dataclass(frozen=True, slots=True)
class MovementProfile:
    """Stored movement bases/overrides; zero means automatic or unavailable."""

    character_id: int
    land_speed: int = 0
    armor_speed: int = 0
    fly_speed: int = 0
    swim_speed: int = 0
    climb_speed: int = 0
    burrow_speed: int = 0
    teleport_speed: int = 0
    fly_maneuverability: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class HitPoints:
    character_id: int
    maximum: int = 0
    current: int = 0
    temporary: int = 0
    nonlethal: int = 0
    auto_calculate: bool = False


@dataclass(frozen=True, slots=True)
class CustomTracker:
    id: int
    key: str
    name: str
    tracker_type: str
    formula: str = ""
    manual_maximum: float = 0
    current_value: float = 0
    temporary_value: float = 0
    unit: str = ""
    description: str = ""
    recovery_event: str = "none"
    recovery_operation: str = "none"


EQUIPMENT_CATEGORIES = ("Armor", "Shield", "Weapon", "Gear", "Consumable", "Other")
EQUIPMENT_BONUS_TYPES = (
    "armor", "shield", "natural armor", "natural armor enhancement",
    "deflection", "dodge", "untyped",
)
WORN_SLOTS = (
    "",
    "Armor",
    "Shield",
    "Belt",
    "Body",
    "Chest",
    "Eyes",
    "Feet",
    "Hands",
    "Head",
    "Headband",
    "Neck",
    "Ring (Left)",
    "Ring (Right)",
    "Shoulders",
    "Wrists",
    "Slotless",
    "Other",
)
EQUIPMENT_STATES = ("stored", "carried", "worn", "wielded", "armor", "shield")


@dataclass(frozen=True, slots=True)
class EquipmentItem:
    id: int
    name: str
    category: str
    quantity: int
    weight: float
    equipped: bool
    ac_bonus: int
    bonus_type: str
    max_dex_bonus: int | None
    armor_check_penalty: int = 0
    notes: str = ""
    slot: str = ""
    value_gp: float = 0.0
    catalog_key: str = ""
    catalog_source: str = ""
    state: str = "stored"
    choices_json: str = "{}"
    automation_json: str = ""
    enhancement_bonus: int = 0
    masterwork: bool = False
    weapon_damage_dice: str = ""
    weapon_damage_type: str = ""
    weapon_critical: str = ""
    weapon_range: str = ""


@dataclass(frozen=True, slots=True)
class InventoryPlacement:
    """Presentation-only location of one saved item in the Inventory organizer."""

    equipment_id: int
    category: str
    subcategory: str = "General"
    sort_order: int = 0
    container_equipment_id: int | None = None


@dataclass(frozen=True, slots=True)
class InventoryCustomGroup:
    """A reusable drop target created by the user for one character."""

    category: str
    subcategory: str = "General"
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class ItemEnchantment:
    """A composable magic property attached to one saved equipment item."""

    id: int
    equipment_id: int
    key: str
    name: str
    bonus_equivalent: int = 0
    notes: str = ""


@dataclass(frozen=True, slots=True)
class CurrencyPurse:
    character_id: int
    copper: int = 0
    silver: int = 0
    gold: int = 0
    platinum: int = 0
    notes: str = ""


ATTACK_TYPES = ("Melee", "Ranged")
DAMAGE_MULTIPLIERS = (0.0, 0.5, 1.0, 1.5, 2.0)
DAMAGE_ABILITY_MODES = ("automatic", "manual")


@dataclass(frozen=True, slots=True)
class Attack:
    id: int
    name: str
    attack_type: str
    ability: str
    attack_bonus: int
    damage_dice: str
    damage_ability: str | None
    damage_multiplier: float
    damage_bonus: int
    critical: str
    notes: str = ""
    equipment_id: int | None = None
    profile_key: str = ""
    damage_ability_mode: str = "manual"
    visibility_condition: str = ""


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    key: str
    name: str
    ability: str
    trained_only: bool = False
    armor_check_multiplier: int = 0


SKILLS = (
    SkillDefinition("acrobatics", "Acrobatics", "dexterity", False, 1),
    SkillDefinition("appraise", "Appraise", "intelligence"),
    SkillDefinition("bluff", "Bluff", "charisma"),
    SkillDefinition("climb", "Climb", "strength", False, 1),
    SkillDefinition("craft", "Craft", "intelligence"),
    SkillDefinition("diplomacy", "Diplomacy", "charisma"),
    SkillDefinition("disable_device", "Disable Device", "dexterity", True, 1),
    SkillDefinition("disguise", "Disguise", "charisma"),
    SkillDefinition("escape_artist", "Escape Artist", "dexterity", False, 1),
    SkillDefinition("fly", "Fly", "dexterity", False, 1),
    SkillDefinition("handle_animal", "Handle Animal", "charisma", True),
    SkillDefinition("heal", "Heal", "wisdom"),
    SkillDefinition("intimidate", "Intimidate", "charisma"),
    SkillDefinition("knowledge_arcana", "Knowledge (Arcana)", "intelligence", True),
    SkillDefinition("knowledge_dungeoneering", "Knowledge (Dungeoneering)", "intelligence", True),
    SkillDefinition("knowledge_engineering", "Knowledge (Engineering)", "intelligence", True),
    SkillDefinition("knowledge_geography", "Knowledge (Geography)", "intelligence", True),
    SkillDefinition("knowledge_history", "Knowledge (History)", "intelligence", True),
    SkillDefinition("knowledge_local", "Knowledge (Local)", "intelligence", True),
    SkillDefinition("knowledge_nature", "Knowledge (Nature)", "intelligence", True),
    SkillDefinition("knowledge_nobility", "Knowledge (Nobility)", "intelligence", True),
    SkillDefinition("knowledge_planes", "Knowledge (Planes)", "intelligence", True),
    SkillDefinition("knowledge_religion", "Knowledge (Religion)", "intelligence", True),
    SkillDefinition("linguistics", "Linguistics", "intelligence", True),
    SkillDefinition("perception", "Perception", "wisdom"),
    SkillDefinition("perform", "Perform", "charisma"),
    SkillDefinition("profession", "Profession", "wisdom", True),
    SkillDefinition("ride", "Ride", "dexterity", False, 1),
    SkillDefinition("sense_motive", "Sense Motive", "wisdom"),
    SkillDefinition("sleight_of_hand", "Sleight of Hand", "dexterity", True, 1),
    SkillDefinition("spellcraft", "Spellcraft", "intelligence", True),
    SkillDefinition("stealth", "Stealth", "dexterity", False, 1),
    SkillDefinition("survival", "Survival", "wisdom"),
    SkillDefinition("swim", "Swim", "strength", False, 2),
    SkillDefinition("use_magic_device", "Use Magic Device", "charisma", True),
)


@dataclass(frozen=True, slots=True)
class SkillState:
    skill_key: str
    ranks: int = 0
    class_skill: bool = False
    misc_bonus: int = 0
    notes: str = ""
    ability_override: str = ""
    class_skill_override: bool | None = None


@dataclass(frozen=True, slots=True)
class SkillSpecialization:
    """Character-owned Craft, Perform, or Profession specialization row."""

    skill_key: str
    base_skill_key: str
    specialty: str = ""
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class SheetNote:
    """Persistent floating rich-text note placed over a character sheet."""

    id: int
    character_id: int
    page_key: str = ""
    x: int = 80
    y: int = 100
    width: int = 360
    height: int = 260
    pinned: bool = False
    content_html: str = ""
    toolbar_expanded: bool = False
    visible: bool = True
    pages_json: str = "[]"
    current_page: int = 0


CONDITION_PRESETS = {
    "Battered": (("cmd", -2),),
    "Blinded": (("ac", -2), ("skills", -4)),
    "Dazzled": (("attack", -1),),
    "Entangled": (("dexterity", -4), ("attack", -2)),
    "Exhausted": (("strength", -6), ("dexterity", -6)),
    "Fatigued": (("strength", -2), ("dexterity", -2)),
    "Prone": (("attack", -4),),
    "Shaken": (
        ("attack", -2),
        ("fortitude", -2),
        ("reflex", -2),
        ("will", -2),
        ("skills", -2),
    ),
    "Sickened": (
        ("attack", -2),
        ("damage", -2),
        ("fortitude", -2),
        ("reflex", -2),
        ("will", -2),
        ("skills", -2),
    ),
}

CONDITION_RULES_TEXT = {
    "Battered": (
        "−2 CMD. You cannot make attacks of opportunity provoked by a creature "
        "performing a combat maneuver. Total defense, lesser restoration, the "
        "Life sphere's restore ability, or a similar effect can remove battered."
    ),
}


@dataclass(frozen=True, slots=True)
class Condition:
    id: int
    name: str
    enabled: bool = True
    notes: str = ""


ONGOING_EFFECT_SOURCE_TYPES = ("Spell", "Sphere", "Other")


@dataclass(frozen=True, slots=True)
class OngoingEffect:
    """One temporary spell/sphere effect tracked independently of conditions.

    A record may optionally contribute one typed modifier to the ordinary sheet
    calculation pipeline.  More involved rules remain readable in ``notes`` and
    can be represented by additional records without coupling this tracker to a
    particular spell catalog.
    """

    id: int
    name: str
    source_type: str = "Spell"
    enabled: bool = True
    duration: str = ""
    target: str = ""
    bonus_type: str = "untyped"
    value: int = 0
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SheetEffect:
    target: str
    bonus_type: str = "untyped"
    value: int = 0
    formula: str = ""
    scope: str = ""


# Kept as a public alias so older exports, tests, and integrations that imported
# FeatEffect continue to work. Effects are now shared by every rules catalog.
FeatEffect = SheetEffect


@dataclass(frozen=True, slots=True)
class Feat:
    id: int
    name: str
    enabled: bool = True
    target: str = ""
    bonus_type: str = "untyped"
    value: int = 0
    notes: str = ""
    catalog_key: str = ""
    catalog_category: str = ""
    prerequisites: str = ""
    source_url: str = ""
    choice: str = ""
    effects: tuple[SheetEffect, ...] = ()
    repeatable: bool = False
    activation: str = "always"
    activation_note: str = ""


@dataclass(frozen=True, slots=True)
class Trait:
    id: int
    name: str
    enabled: bool = True
    target: str = ""
    bonus_type: str = "trait"
    value: int = 0
    notes: str = ""
    catalog_key: str = ""
    catalog_category: str = ""
    prerequisites: str = ""
    source_url: str = ""
    choice: str = ""
    effects: tuple[SheetEffect, ...] = ()
    repeatable: bool = False
    activation: str = "always"
    activation_note: str = ""


@dataclass(frozen=True, slots=True)
class MartialFocus:
    character_id: int
    current: int = 1
    maximum: int = 1
    recovery_method: str = "Take a full-round action"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class CastingProfile:
    character_id: int
    casting_ability: str = "charisma"
    casting_class_levels: int = 0
    caster_level: int = 0
    msb_misc: int = 0
    dc_misc: int = 0
    concentration_misc: int = 0
    spell_points_maximum: int = 0
    spell_points_current: int = 0
    spell_points_temporary: int = 0
    spell_points_misc: int = 0
    auto_spell_points: bool = False
    tradition_name: str = ""
    tradition_boons: str = ""
    tradition_drawbacks: str = ""
    tradition_notes: str = ""


@dataclass(frozen=True, slots=True)
class CharacterTradition:
    """One catalog tradition and the choices used when its package was applied."""

    id: int
    character_id: int
    catalog_key: str
    name: str
    kind: str
    choices_json: str = "{}"
    grants_json: str = "[]"
    definition_json: str = "{}"


@dataclass(frozen=True, slots=True)
class SphereStatistic:
    character_id: int
    sphere: str
    caster_level_bonus: int = 0
    dc_bonus: int = 0
    notes: str = ""


MARTIAL_TALENT_TYPES = ("Base Sphere", "Talent", "Drawback", "Tradition", "Other")


@dataclass(frozen=True, slots=True)
class MartialTalent:
    id: int
    name: str
    sphere: str = ""
    talent_type: str = "Talent"
    notes: str = ""
    catalog_key: str = ""
    catalog_category: str = ""
    prerequisites: str = ""
    source_url: str = ""
    enabled: bool = True
    choice: str = ""
    effects: tuple[SheetEffect, ...] = ()
    activation: str = "always"
    activation_note: str = ""


@dataclass(frozen=True, slots=True)
class FlexibleTalentSelection:
    """One replaceable talent slot supplied by a class feature or similar rule."""

    id: int
    character_id: int
    source_key: str
    slot_index: int
    talent_kind: str
    catalog_key: str
    name: str
    sphere: str = ""
    category: str = "Talent"
    description: str = ""
    choice: str = ""
    choice_key: str = ""


SPELL_SYSTEMS = ("Prepared", "Spontaneous", "Sphere", "Spell-like", "Other")


@dataclass(frozen=True, slots=True)
class Spell:
    id: int
    name: str
    system: str = "Prepared"
    level: int = 0
    school_or_sphere: str = ""
    uses_max: int = 0
    uses_used: int = 0
    casting_time: str = ""
    range: str = ""
    duration: str = ""
    save: str = ""
    spell_resistance: str = ""
    notes: str = ""
    catalog_key: str = ""
    catalog_category: str = ""
    prerequisites: str = ""
    source_url: str = ""
    enabled: bool = True
    choice: str = ""
    effects: tuple[SheetEffect, ...] = ()
    activation: str = "always"
    activation_note: str = ""


@dataclass(frozen=True, slots=True)
class PreparedSpell:
    id: int
    character_id: int
    class_level_id: int
    known_spell_id: int | None
    name: str
    level: int
    prepared_count: int = 1
    used_count: int = 0
    catalog_key: str = ""
    custom: bool = False

    @property
    def remaining(self) -> int:
        return max(0, self.prepared_count - self.used_count)


@dataclass(frozen=True, slots=True)
class SpontaneousSlotUse:
    character_id: int
    class_level_id: int
    spell_level: int
    used_count: int = 0


SEQUENCE_OPTION_TYPES = ("Opener", "Link", "Finisher")


@dataclass(frozen=True, slots=True)
class ProdigySequence:
    character_id: int
    active: bool = False
    current: int = 0
    maximum: int = 4
    imbue_key: str = ""


@dataclass(frozen=True, slots=True)
class SequenceOption:
    id: int
    name: str
    option_type: str
    sphere: str = ""
    minimum_links: int = 0
    action: str = ""
    notes: str = ""
    built_in: bool = False
