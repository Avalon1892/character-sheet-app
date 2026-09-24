"""Modular, archetype-aware play systems derived from resolved class features.

Class catalogs decide which features a character owns.  Archetype resolution
happens before this registry is consulted, so a replaced feature automatically
removes its controls and automation while character-specific state is retained
in case the archetype is later changed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import permutations
import json
import re
from typing import Callable, Iterable, Mapping

from app.class_packages import (
    all_class_packages,
    archetype_runtime_package,
    class_package,
)
from app.class_packages.schemas import package_effect, package_module
from app.class_feature_rules import feature_token
from app.class_feature_context import resolved_class_features_for_level
from app.catalogs import DEFAULT_CATALOG
from app.models import Attack, ClassFeatureState, StatModifier


@dataclass(frozen=True, slots=True)
class ClassFeatureResourceDefinition:
    key: str
    name: str
    feature_tokens: tuple[str, ...]
    base_maximum: Callable[[int, int], int]
    description: str
    can_activate: bool = False
    choice_options: tuple[str, ...] = ()
    activate_on_spend: bool = False
    maximum_resolver: Callable[
        [int, Mapping[str, int], frozenset[str], frozenset[str], frozenset[str]], int
    ] | None = None
    recovery_resolver: Callable[
        [int, Mapping[str, int], frozenset[str], frozenset[str], frozenset[str]], int
    ] | None = None
    choice_options_resolver: Callable[[frozenset[str]], tuple[str, ...]] | None = None
    recover_on_full_rest: bool = True
    end_on_full_rest: bool = True
    custom_choice_label: str = ""
    activation_requires: str = ""
    restore_resources_on_activate: tuple[str, ...] = ()
    deactivate_resources_on_end: tuple[str, ...] = ()
    restore_on_activate: bool = False
    use_requires_active: bool = False
    deactivate_resources_on_use: tuple[str, ...] = ()
    maximum_choices_resolver: Callable[[int, frozenset[str]], int] | None = None
    use_increases: bool = False
    restore_toward_zero: bool = False
    spend_resource_key: str = ""
    use_cost: int = 1
    tracks_uses: bool = True
    external_cost_key: str = ""
    requires_choice_provider: str = ""
    requires_choice_option: str = ""
    extra_damage_levels: tuple[int, ...] = ()
    extra_damage_die: str = ""
    extra_damage_type: str = "precision"


@dataclass(frozen=True, slots=True)
class ClassFeatureModuleDefinition:
    key: str
    title: str
    owner_class_keys: frozenset[str]
    governing_ability: str
    resources: tuple[ClassFeatureResourceDefinition, ...]
    grantable: bool = False


@dataclass(frozen=True, slots=True)
class ResolvedClassFeatureResource:
    class_level_id: int
    class_name: str
    key: str
    name: str
    description: str
    maximum: int
    current: int
    active: bool
    choices: tuple[str, ...]
    choice_options: tuple[str, ...]
    maximum_choices: int
    state: ClassFeatureState
    can_activate: bool = False
    activate_on_spend: bool = False
    recovery_value: int = 0
    recover_on_full_rest: bool = True
    end_on_full_rest: bool = True
    custom_choice_label: str = ""
    activation_requires: str = ""
    restore_resources_on_activate: tuple[str, ...] = ()
    deactivate_resources_on_end: tuple[str, ...] = ()
    restore_on_activate: bool = False
    use_requires_active: bool = False
    deactivate_resources_on_use: tuple[str, ...] = ()
    use_increases: bool = False
    restore_toward_zero: bool = False
    spend_resource_key: str = ""
    use_cost: int = 1
    tracks_uses: bool = True
    external_cost_key: str = ""
    extra_damage_levels: tuple[int, ...] = ()
    extra_damage_die: str = ""
    extra_damage_type: str = "precision"


@dataclass(frozen=True, slots=True)
class ResolvedClassFeatureModule:
    key: str
    title: str
    class_level_id: int
    class_name: str
    class_level: int
    governing_ability: str
    feature_tokens: frozenset[str]
    resources: tuple[ResolvedClassFeatureResource, ...]
    domain_available: bool = False
    solo_tactics: bool = False
    teamwork_feat_slots: int = 0


@dataclass(frozen=True, slots=True)
class ClassExtraDamage:
    dice: str
    damage_type: str
    source: str


JUDGMENT_TYPES = (
    "Destruction",
    "Healing",
    "Justice",
    "Piercing",
    "Protection",
    "Purity",
    "Resiliency",
    "Resistance",
    "Smiting",
)

BANE_CREATURE_TYPES = (
    "Aberration",
    "Animal",
    "Construct",
    "Dragon",
    "Fey",
    "Humanoid (choose subtype)",
    "Magical beast",
    "Monstrous humanoid",
    "Ooze",
    "Outsider (choose subtype)",
    "Plant",
    "Undead",
    "Vermin",
)


INQUISITOR_RESOURCES = (
    ClassFeatureResourceDefinition(
        "judgment",
        "Judgment",
        ("judgment",),
        lambda level, _wisdom: 1 + max(0, level - 1) // 3,
        "Daily judgments. Activating one spends a use and lasts until combat ends.",
        True,
        JUDGMENT_TYPES,
        True,
    ),
    ClassFeatureResourceDefinition(
        "bane",
        "Bane",
        ("bane",),
        lambda level, _wisdom: level,
        "Rounds per day of bane on a wielded weapon against the selected creature type.",
        True,
        BANE_CREATURE_TYPES,
        True,
    ),
    ClassFeatureResourceDefinition(
        "discern_lies",
        "Discern Lies",
        ("discern-lies",),
        lambda level, _wisdom: level,
        "Rounds per day of discern lies; activating it is an immediate action.",
        True,
        (),
        True,
    ),
    ClassFeatureResourceDefinition(
        "teamwork_swaps",
        "Teamwork Feat Changes",
        ("teamwork-feat",),
        lambda _level, wisdom: max(0, wisdom),
        "Daily changes of the most recently gained bonus teamwork feat.",
    ),
)

MONK_RESOURCES = (
    ClassFeatureResourceDefinition(
        "ki_pool",
        "Ki Pool",
        ("ki-pool",),
        lambda level, wisdom: level // 2 + wisdom,
        "Ki points equal half the retained Monk class level plus Wisdom modifier. The pool refreshes after 8 hours of rest.",
    ),
)

BARBARIAN_RESOURCES = (
    ClassFeatureResourceDefinition(
        "rage",
        "Rage Rounds",
        ("rage",),
        lambda level, constitution: 2 * level + 2 + constitution,
        "Rounds of rage per day equal 4 + Constitution modifier, plus 2 for every class level after 1st. The pool refreshes after 8 hours of rest.",
        True,
    ),
)

BARD_PERFORMANCES = (
    ("countersong", "Countersong"),
    ("distraction", "Distraction"),
    ("fascinate", "Fascinate"),
    ("inspire-courage", "Inspire Courage"),
    ("inspire-competence", "Inspire Competence"),
    ("suggestion", "Suggestion"),
    ("dirge-of-doom", "Dirge of Doom"),
    ("inspire-greatness", "Inspire Greatness"),
    ("soothing-performance", "Soothing Performance"),
    ("frightening-tune", "Frightening Tune"),
    ("inspire-heroics", "Inspire Heroics"),
    ("mass-suggestion", "Mass Suggestion"),
    ("deadly-performance", "Deadly Performance"),
)

BARD_RESOURCES = (
    ClassFeatureResourceDefinition(
        "bardic_performance",
        "Bardic Performance",
        ("bardic-performance",),
        lambda level, charisma: 2 * level + 2 + charisma,
        "Rounds per day equal 4 + Charisma modifier at 1st level, plus 2 per additional Bard level. Activate one retained performance at a time and spend one round for each round maintained.",
        can_activate=True,
        use_requires_active=True,
    ),
)


def _ability(abilities: Mapping[str, int], name: str) -> int:
    return int(abilities.get(name, 0))


def _alchemist_bombs(
    level: int, abilities: Mapping[str, int], *_context
) -> int:
    return level + _ability(abilities, "intelligence")


def _arcanist_capacity(level: int, _abilities: Mapping[str, int], *_context) -> int:
    return level + 3


def _arcanist_daily_fill(level: int, _abilities: Mapping[str, int], *_context) -> int:
    return 3 + level // 2


def _investigator_inspiration(
    level: int, abilities: Mapping[str, int], *_context
) -> int:
    return max(1, level // 2 + _ability(abilities, "intelligence"))


def _magus_arcane_pool(
    level: int, abilities: Mapping[str, int], *_context
) -> int:
    return max(0, max(1, level // 2) + _ability(abilities, "intelligence"))


def _ninja_ki(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, level // 2 + _ability(abilities, "charisma"))


def _gunslinger_grit(
    _level: int,
    abilities: Mapping[str, int],
    _tokens: frozenset[str],
    archetype_keys: frozenset[str],
    _powers: frozenset[str],
) -> int:
    use_charisma = any(
        key.endswith(":mysterious-stranger")
        or key.endswith(":buccaneer")
        or key.endswith(":firebrand")
        for key in archetype_keys
    )
    return max(1, _ability(abilities, "charisma" if use_charisma else "wisdom"))


def _swashbuckler_panache(
    _level: int,
    abilities: Mapping[str, int],
    _tokens: frozenset[str],
    archetype_keys: frozenset[str],
    _powers: frozenset[str],
) -> int:
    charisma = max(1, _ability(abilities, "charisma"))
    if any(key.endswith(":inspired-blade") for key in archetype_keys):
        return charisma + max(1, _ability(abilities, "intelligence"))
    return charisma


def _bloodrage_rounds(
    level: int, abilities: Mapping[str, int], *_context
) -> int:
    return 2 * level + 2 + _ability(abilities, "constitution")


def _mutagen_choice_options(power_names: frozenset[str]) -> tuple[str, ...]:
    physical = ("Strength", "Dexterity", "Constitution")
    folded = {name.casefold() for name in power_names}
    if "grand mutagen" in folded:
        return tuple(" > ".join(values) for values in permutations(physical, 3))
    if "greater mutagen" in folded:
        return tuple(" > ".join(values) for values in permutations(physical, 2))
    return physical


ALCHEMIST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "bombs",
        "Bombs",
        ("bomb", "bombs"),
        lambda _level, _intelligence: 0,
        "Bombs per day equal Alchemist level + Intelligence modifier. Base damage is 1d6 at 1st level and increases by 1d6 at every odd level; splash damage adds Intelligence modifier.",
        maximum_resolver=_alchemist_bombs,
    ),
    ClassFeatureResourceDefinition(
        "mutagen",
        "Mutagen",
        ("mutagen", "persistent-mutagen"),
        lambda _level, _intelligence: 1,
        "One prepared mutagen. Choose the enhanced physical ability before drinking it; the active bonuses, natural armor, and associated mental penalty feed the sheet automatically.",
        can_activate=True,
        choice_options=("Strength", "Dexterity", "Constitution"),
        activate_on_spend=True,
        choice_options_resolver=_mutagen_choice_options,
        recover_on_full_rest=False,
    ),
)

ARCANIST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "arcane_reservoir",
        "Arcane Reservoir",
        ("arcane-reservoir",),
        lambda _level, _intelligence: 0,
        "The reservoir can hold level + 3 points. Preparing spells normally fills it to 3 + half the Arcanist level, so capacity and daily recovery are tracked separately.",
        maximum_resolver=_arcanist_capacity,
        recovery_resolver=_arcanist_daily_fill,
    ),
)

INVESTIGATOR_RESOURCES = (
    ClassFeatureResourceDefinition(
        "inspiration",
        "Inspiration",
        ("inspiration",),
        lambda _level, _intelligence: 0,
        "Inspiration points equal half the Investigator level + Intelligence modifier (minimum 1) and refresh each day.",
        maximum_resolver=_investigator_inspiration,
    ),
    ClassFeatureResourceDefinition(
        "studied_combat",
        "Studied Combat",
        ("studied-combat",),
        lambda _level, intelligence: max(1, intelligence),
        "Remaining rounds against one studied opponent. While active, melee attacks and damage gain an insight bonus equal to half the Investigator level. Configure the target name, then activate the study.",
        can_activate=True,
        recover_on_full_rest=False,
        custom_choice_label="Studied target",
        restore_resources_on_activate=("studied_strike",),
        deactivate_resources_on_end=("studied_strike",),
        restore_on_activate=True,
        use_requires_active=True,
    ),
    ClassFeatureResourceDefinition(
        "studied_strike",
        "Studied Strike",
        ("studied-strike",),
        lambda _level, _intelligence: 1,
        "Arm this for the next successful melee hit against the current studied target. Its precision damage scales from 1d6 at 4th level to 9d6 at 20th level and is not multiplied on a critical hit.",
        can_activate=True,
        recover_on_full_rest=False,
        activation_requires="studied_combat",
        restore_on_activate=True,
        use_requires_active=True,
        deactivate_resources_on_use=("studied_combat",),
    ),
)

MAGUS_RESOURCES = (
    ClassFeatureResourceDefinition(
        "arcane_pool",
        "Arcane Pool",
        ("arcane-pool",),
        lambda _level, _intelligence: 0,
        "Arcane pool points equal half the Magus level (minimum 1) + Intelligence modifier and refresh when spells are prepared.",
        maximum_resolver=_magus_arcane_pool,
    ),
)

NINJA_RESOURCES = (
    ClassFeatureResourceDefinition(
        "ki_pool",
        "Ki Pool",
        ("ki-pool-nin", "ki-pool"),
        lambda _level, _charisma: 0,
        "Ki points equal half the Ninja level + Charisma modifier and refresh each day.",
        maximum_resolver=_ninja_ki,
    ),
)

GUNSLINGER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "grit",
        "Grit",
        ("grit",),
        lambda _level, _wisdom: 1,
        "Grit begins each day at the governing ability modifier (minimum 1), fluctuates through deeds, and normally cannot exceed that maximum.",
        maximum_resolver=_gunslinger_grit,
    ),
)

SWASHBUCKLER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "panache",
        "Panache",
        ("panache", "inspired-panache"),
        lambda _level, _charisma: 1,
        "Panache begins each day at Charisma modifier (minimum 1), fluctuates through deeds, and normally cannot exceed that maximum.",
        maximum_resolver=_swashbuckler_panache,
    ),
)

BLOODRAGER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "bloodrage",
        "Bloodrage Rounds",
        ("bloodrage", "greater-bloodrage", "mighty-bloodrage"),
        lambda _level, _constitution: 0,
        "Bloodrage rounds equal 4 + Constitution modifier at 1st level, plus 2 per additional Bloodrager level. Temporary Constitution increases do not increase this pool.",
        can_activate=True,
        maximum_resolver=_bloodrage_rounds,
    ),
)


# The following definitions cover recurring base-class mechanics that used to
# exist only as prose in Special Abilities.  They intentionally use the same
# resource contract as the older Inquisitor/Monk providers so archetype
# replacement, rest, formulas, and the shared UI keep working automatically.
FAVORED_ENEMY_TYPES = (
    "Aberration", "Animal", "Construct", "Dragon", "Fey",
    "Humanoid (aquatic)", "Humanoid (dwarf)", "Humanoid (elf)",
    "Humanoid (giant)", "Humanoid (goblinoid)", "Humanoid (gnoll)",
    "Humanoid (gnome)", "Humanoid (halfling)", "Humanoid (human)",
    "Humanoid (orc)", "Humanoid (reptilian)", "Humanoid (other subtype)",
    "Magical beast", "Monstrous humanoid", "Ooze", "Outsider (air)",
    "Outsider (chaotic)", "Outsider (earth)", "Outsider (evil)",
    "Outsider (fire)", "Outsider (good)", "Outsider (lawful)",
    "Outsider (native)", "Outsider (water)", "Plant", "Undead", "Vermin",
)


def _one_plus_every_three(level: int, *_context) -> int:
    return 1 + max(0, level - 1) // 3


def _half_level_pool(level: int, abilities: Mapping[str, int], *_context) -> int:
    # The module's governing score is normalized by _resource_view; these
    # resource-specific resolvers use their published fixed ability instead.
    return max(0, level // 2 + max(abilities.values(), default=0))


def _paladin_lay_on_hands(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, level // 2 + _ability(abilities, "charisma"))


def _warpriest_fervor(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, level // 2 + _ability(abilities, "wisdom"))


def _cleric_channel(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, 3 + _ability(abilities, "charisma"))


def _wild_shape_uses(level: int, *_context) -> int:
    if level < 4:
        return 0
    return 99 if level >= 20 else 1 + (level - 4) // 2


def _burn_capacity(_level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, 3 + _ability(abilities, "constitution"))


def _mental_focus(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, level + _ability(abilities, "intelligence"))


def _phrenic_pool(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(
        1,
        level // 2 + max(
            _ability(abilities, "wisdom"), _ability(abilities, "charisma")
        ),
    )


def _raging_song_rounds(level: int, abilities: Mapping[str, int], *_context) -> int:
    return max(0, 2 * level + 1 + _ability(abilities, "charisma"))


def _eidolon_evolution_pool(level: int, *_context) -> int:
    progression = (3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 25, 26)
    return progression[max(0, min(19, level - 1))]


SMITE_RESOURCES = (
    ClassFeatureResourceDefinition(
        "smite", "Smite Uses", ("smite-evil", "smite-good"),
        lambda _level, _ability: 0,
        "Daily smite uses. Spend one and name the target to make the target-bound attack and damage bonuses live until the smite ends.",
        can_activate=True, activate_on_spend=True,
        maximum_resolver=_one_plus_every_three,
        custom_choice_label="Current smite target",
    ),
)

PALADIN_RESOURCES = SMITE_RESOURCES + (
    ClassFeatureResourceDefinition(
        "lay_on_hands", "Lay on Hands", ("lay-on-hands",),
        lambda _level, _ability: 0,
        "Daily uses equal half Paladin level + Charisma modifier. Each use heals 1d6 per two Paladin levels; Channel Energy consumes two uses.",
        maximum_resolver=_paladin_lay_on_hands,
    ),
    ClassFeatureResourceDefinition(
        "channel_energy", "Channel Positive Energy", ("channel-positive-energy",),
        lambda _level, _ability: 0,
        "Available channel uses are derived live from remaining Lay on Hands uses. Using channel spends two Lay on Hands uses.",
        spend_resource_key="lay_on_hands", use_cost=2,
    ),
)

ANTIPALADIN_RESOURCES = SMITE_RESOURCES + (
    ClassFeatureResourceDefinition(
        "touch_of_corruption", "Touch of Corruption", ("touch-of-corruption",),
        lambda _level, _ability: 0,
        "Daily uses equal half Antipaladin level + Charisma modifier. Each use deals or heals undead for 1d6 per two Antipaladin levels; Channel Energy consumes two uses.",
        maximum_resolver=_paladin_lay_on_hands,
    ),
    ClassFeatureResourceDefinition(
        "channel_energy", "Channel Negative Energy", ("channel-negative-energy",),
        lambda _level, _ability: 0,
        "Available channel uses are derived live from remaining Touch of Corruption uses. Using channel spends two Touch of Corruption uses.",
        spend_resource_key="touch_of_corruption", use_cost=2,
    ),
)

CLERIC_RESOURCES = (
    ClassFeatureResourceDefinition(
        "channel_energy", "Channel Energy", ("channel-energy",),
        lambda _level, _ability: 0,
        "Channel uses per day equal 3 + Charisma modifier; channel dice are 1d6 plus 1d6 for every two Cleric levels beyond 1st.",
        choice_options=("Positive energy", "Negative energy"),
        maximum_resolver=_cleric_channel,
    ),
)

WARPRIEST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "blessing_uses", "Blessing Uses", ("blessings",),
        lambda level, _wisdom: 3 + level // 2,
        "Shared daily uses for both selected blessings. Each minor or major blessing spends one use.",
    ),
    ClassFeatureResourceDefinition(
        "fervor", "Fervor", ("fervor",), lambda _level, _ability: 0,
        "Daily uses equal half Warpriest level + Wisdom modifier. Fervor heals or harms and can quicken a self-targeting prepared spell.",
        maximum_resolver=_warpriest_fervor,
    ),
    ClassFeatureResourceDefinition(
        "channel_energy", "Channel Energy", ("channel-energy-war",),
        lambda _level, _ability: 0,
        "Available channel uses are derived live from remaining Fervor uses. Using channel spends two Fervor uses.",
        spend_resource_key="fervor", use_cost=2,
    ),
)

CHALLENGE_RESOURCES = (
    ClassFeatureResourceDefinition(
        "challenge", "Challenge", ("challenge", "challenge-cav", "challenge-sam"),
        lambda _level, _ability: 0,
        "Spend one daily use and name the foe. While active, melee damage against that target gains the class level and the challenge's other order-specific effects remain visible in the feature rules.",
        can_activate=True, activate_on_spend=True,
        maximum_resolver=_one_plus_every_three,
        custom_choice_label="Current challenge target",
    ),
)

WILD_SHAPE_RESOURCES = (
    ClassFeatureResourceDefinition(
        "wild_shape", "Wild Shape", ("wild-shape", "wild-shape-shi"),
        lambda _level, _ability: 0,
        "Daily transformations and current form. The tracker follows the class progression; form-dependent statistics remain explicit because the chosen creature or Shifter aspect determines them.",
        can_activate=True, activate_on_spend=True,
        maximum_resolver=_wild_shape_uses,
        custom_choice_label="Current form",
    ),
)

KINETICIST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "burn", "Burn Accepted", ("burn",), lambda _level, _ability: 0,
        "Accumulated burn. Each point deals unhealable nonlethal damage equal to character level; Full Rest clears burn instead of filling the counter.",
        maximum_resolver=_burn_capacity,
        recovery_resolver=lambda *_context: 0,
        use_increases=True, restore_toward_zero=True,
    ),
)

OCCULTIST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "mental_focus", "Mental Focus", ("mental-focus",),
        lambda _level, _ability: 0,
        "Mental focus equals Occultist level + Intelligence modifier. Configure notes to record the daily allocation among retained implements; spending points updates this shared total.",
        maximum_resolver=_mental_focus,
    ),
)

PSYCHIC_RESOURCES = (
    ClassFeatureResourceDefinition(
        "phrenic_pool", "Phrenic Pool", ("phrenic-pool",),
        lambda _level, _ability: 0,
        "Phrenic points equal half Psychic level + the Wisdom or Charisma modifier selected by the psychic discipline.",
        choice_options=("Wisdom", "Charisma"),
        maximum_resolver=_phrenic_pool,
    ),
)

SNEAK_ATTACK_RESOURCES = (
    ClassFeatureResourceDefinition(
        "sneak_attack", "Sneak Attack Applies", ("sneak-attack", "sneak-attack-uc", "sneak-attack-sla"),
        lambda _level, _ability: 1,
        "Toggle this when the target is denied Dexterity to AC or is flanked. The correct class dice are added as precision damage and are not multiplied on a critical hit.",
        can_activate=True, recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

SLAYER_RESOURCES = SNEAK_ATTACK_RESOURCES + (
    ClassFeatureResourceDefinition(
        "studied_target", "Studied Target", ("studied-target",),
        lambda _level, _ability: 1,
        "Name and activate a studied target. The scaling attack, damage, class-DC, and relevant skill bonuses then feed the sheet.",
        can_activate=True, custom_choice_label="Studied target name",
        maximum_choices_resolver=lambda level, _tokens: 1 + level // 5,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

RANGER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "favored_enemy", "Favored Enemy Applies", ("favored-enemy",),
        lambda _level, _ability: 2,
        "Choose the enemy types owned at this level and activate this tracker when an attack or check concerns one of them. The maximum override is the effective bonus for the current enemy, allowing the published +2 increases to be distributed correctly.",
        can_activate=True, choice_options=FAVORED_ENEMY_TYPES,
        maximum_choices_resolver=lambda level, _tokens: 1 + level // 5,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

SKALD_RESOURCES = (
    ClassFeatureResourceDefinition(
        "raging_song", "Raging Song", ("raging-song",),
        lambda _level, _ability: 0,
        "Raging song rounds equal 3 + Charisma modifier at 1st level and two more per later Skald level. Choose the current song; Inspired Rage applies its live bonuses.",
        can_activate=True, use_requires_active=True,
        choice_options=("Inspired Rage", "Song of Marching", "Song of Strength", "Dirge of Doom", "Song of the Fallen"),
        maximum_resolver=_raging_song_rounds,
    ),
)

SHAMAN_RESOURCES = (
    ClassFeatureResourceDefinition(
        "shaman_hexes", "Shaman Hexes", ("hex-sha",),
        lambda level, _ability: 1 + level // 2,
        "Record retained shaman and spirit hexes. The number of selections follows the base hex progression; Wandering Hex remains a temporary daily choice.",
        custom_choice_label="Known hex names, comma-separated",
        maximum_choices_resolver=lambda level, _tokens: 1 + level // 2,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

EIDOLON_RESOURCES = (
    ClassFeatureResourceDefinition(
        "eidolon", "Eidolon", ("eidolon", "eidolon-uc"),
        lambda _level, _ability: 1,
        "Track whether the eidolon is summoned and record its name/base form or subtype. Its evolution pool follows Summoner level and remains manually allocated until a full evolution builder is opened.",
        can_activate=True, custom_choice_label="Eidolon name / base form or subtype",
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
    ClassFeatureResourceDefinition(
        "evolution_pool", "Eidolon Evolution Points", ("eidolon", "eidolon-uc"),
        lambda _level, _ability: 0,
        "Evolution points available for the eidolon's retained evolutions. Use the adjustment or override for feats and other rule changes.",
        maximum_resolver=_eidolon_evolution_pool,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

MERCY_RESOURCES = (
    ClassFeatureResourceDefinition(
        "mercies", "Mercies", ("mercy",), lambda _level, _ability: 0,
        "Record one mercy at 3rd level and every 3 levels thereafter. Retained mercies are applied whenever Lay on Hands heals a target.",
        custom_choice_label="Known mercies, comma-separated",
        maximum_choices_resolver=lambda level, _tokens: level // 3,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

CRUELTY_RESOURCES = (
    ClassFeatureResourceDefinition(
        "cruelties", "Cruelties", ("cruelty",), lambda _level, _ability: 0,
        "Record one cruelty at 3rd level and every 3 levels thereafter. Choose one retained cruelty whenever Touch of Corruption damages a target.",
        custom_choice_label="Known cruelties, comma-separated",
        maximum_choices_resolver=lambda level, _tokens: level // 3,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

SAMURAI_RESOURCES = CHALLENGE_RESOURCES + (
    ClassFeatureResourceDefinition(
        "resolve", "Resolve", ("resolve",),
        lambda level, _charisma: 1 + max(0, level - 1) // 2,
        "Daily resolve uses support Determined, Resolute, and Unstoppable; defeating the current challenge target restores one use up to the maximum.",
        choice_options=("Determined", "Resolute", "Unstoppable", "Greater Resolve", "True Resolve"),
    ),
)

BRAWLER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "martial_flexibility", "Martial Flexibility", ("martial-flexibility",),
        lambda level, _ability: 3 + level // 2,
        "Spend uses to gain temporary combat feats for 1 minute. Configure the currently flexed feats; each selected feat consumes one use.",
        can_activate=True, activate_on_spend=True,
        custom_choice_label="Current temporary combat feats",
        maximum_choices_resolver=lambda level, _tokens: 1 if level < 6 else 2 if level < 10 else 3 if level < 12 else 4 if level < 20 else 99,
    ),
)

ANIMAL_FOCUS_OPTIONS = (
    "Bat", "Bear", "Bull", "Falcon", "Frog", "Monkey", "Mouse", "Owl",
    "Snake", "Stag", "Tiger", "Wolf",
)
HUNTER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "animal_focus", "Animal Focus Minutes", ("animal-focus",),
        lambda level, _wisdom: level,
        "Minutes per day for the Hunter's personal animal focus. The companion's focus is unlimited and can be recorded in the companion notes.",
        can_activate=True, use_requires_active=True,
        choice_options=ANIMAL_FOCUS_OPTIONS,
        maximum_choices_resolver=lambda level, _tokens: 2 if level >= 8 else 1,
    ),
)

MEDIUM_RESOURCES = (
    ClassFeatureResourceDefinition(
        "influence", "Spirit Influence", ("spirit-surge", "spirit-bonus"),
        lambda _level, _charisma: 5,
        "Accumulated spirit influence. Spirit Surge and taboo benefits add influence; reaching 5 causes the spirit to take control. Full Rest clears the counter.",
        choice_options=("Archmage", "Champion", "Guardian", "Hierophant", "Marshal", "Trickster"),
        recovery_resolver=lambda *_context: 0,
        use_increases=True, restore_toward_zero=True,
    ),
)

MESMERIST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "hypnotic_stare", "Hypnotic Stare", ("hypnotic-stare",),
        lambda _level, _charisma: 1,
        "Name and activate the creature currently affected by Hypnotic Stare. Painful Stare damage then appears on the Mesmerist's attacks.",
        can_activate=True, custom_choice_label="Stare target",
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
    ClassFeatureResourceDefinition(
        "mesmerist_tricks", "Mesmerist Tricks", ("mesmerist-tricks",),
        lambda level, charisma: max(1, level // 2 + charisma),
        "Daily trick implants equal half Mesmerist level + Charisma modifier. Spend one to implant and record the current trick and subject.",
        can_activate=True, activate_on_spend=True,
        custom_choice_label="Current implanted trick / subject",
    ),
    ClassFeatureResourceDefinition(
        "touch_treatment", "Touch Treatment", ("touch-treatment",),
        lambda _level, charisma: max(0, 3 + charisma),
        "Daily Touch Treatment uses equal 3 + Charisma modifier. The conditions available to remove are determined by Mesmerist level.",
    ),
)

SPIRITUALIST_RESOURCES = (
    ClassFeatureResourceDefinition(
        "phantom", "Phantom", ("phantom",), lambda _level, _wisdom: 1,
        "Track the bonded phantom's name, emotional focus, and current manifestation. The feature is retained separately from spells so spell-replacing archetypes do not remove it.",
        can_activate=True,
        choice_options=("Anger", "Dedication", "Despair", "Fear", "Hatred", "Jealousy", "Remorse", "Zeal"),
        custom_choice_label="Phantom name / emotional focus",
        maximum_choices_resolver=lambda _level, _tokens: 2,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

FIGHTER_WEAPON_GROUPS = (
    "Axes", "Heavy blades", "Light blades", "Bows", "Close", "Crossbows",
    "Double", "Firearms", "Flails", "Hammers", "Monk", "Natural", "Polearms",
    "Siege engines", "Spears", "Thrown",
)
FIGHTER_RESOURCES = (
    ClassFeatureResourceDefinition(
        "weapon_training", "Weapon Training", ("weapon-training",),
        lambda level, _strength: max(0, 1 + (level - 5) // 4) if level >= 5 else 0,
        "Select trained weapon groups in acquisition order. Activate this row when the current attack belongs to a trained group; the maximum override can represent the exact group's scaling bonus.",
        can_activate=True, choice_options=FIGHTER_WEAPON_GROUPS,
        maximum_choices_resolver=lambda level, _tokens: 0 if level < 5 else 1 + (level - 5) // 4,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
    ClassFeatureResourceDefinition(
        "armor_training", "Armor Training", ("armor-training",),
        lambda level, _strength: 0 if level < 3 else min(4, 1 + (level - 3) // 4),
        "Automatic reduction to armor check penalty and increase to maximum Dexterity bonus. Medium armor no longer reduces speed; heavy armor follows at 7th level.",
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

SWASHBUCKLER_TRAINING_RESOURCES = (
    ClassFeatureResourceDefinition(
        "weapon_training", "Swashbuckler Weapon Training", ("swashbuckler-weapon-training",),
        lambda level, _charisma: max(0, 1 + (level - 5) // 4) if level >= 5 else 0,
        "Activate for a light or one-handed piercing melee weapon. The scaling attack and damage bonuses then feed that attack; the expanded critical threat remains visible in the effect summary.",
        can_activate=True, recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

SHIFTER_RESOURCES = WILD_SHAPE_RESOURCES + (
    ClassFeatureResourceDefinition(
        "shifter_aspect", "Minor Aspect Minutes", ("shifter-aspect",),
        lambda level, _wisdom: 3 + level,
        "Minutes per day in selected minor aspects. Record the currently assumed aspects; Chimeric Aspect increases how many may be active together.",
        can_activate=True, use_requires_active=True,
        custom_choice_label="Current minor aspects",
        maximum_choices_resolver=lambda level, _tokens: 3 if level >= 14 else 2 if level >= 9 else 1,
    ),
)

PSYCHIC_ADVANCEMENT_RESOURCES = (
    ClassFeatureResourceDefinition(
        "phrenic_amplifications", "Phrenic Amplifications", ("phrenic-amplifications",),
        lambda _level, _ability: 0,
        "Record the amplifications learned at 1st, 3rd, 7th, 11th, 15th, and 19th levels. Their point costs are paid from the Phrenic Pool.",
        custom_choice_label="Known amplifications, comma-separated",
        maximum_choices_resolver=lambda level, _tokens: 1 + int(level >= 3) + max(0, (level - 3) // 4),
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

OCCULTIST_ADVANCEMENT_RESOURCES = (
    ClassFeatureResourceDefinition(
        "implements", "Implement Schools", ("implements",),
        lambda _level, _ability: 0,
        "Record implement schools in acquisition order. Repeated schools are legal and grant another spell set; daily focus allocations belong in Mental Focus notes.",
        custom_choice_label="Implement schools, comma-separated",
        maximum_choices_resolver=lambda level, _tokens: 2 + (0 if level < 2 else 1 + (level - 2) // 4),
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

RANGER_ADVANCEMENT_RESOURCES = (
    ClassFeatureResourceDefinition(
        "favored_terrain", "Favored Terrains", ("favored-terrain",),
        lambda _level, _wisdom: 0,
        "Record favored terrains and their distributed bonuses. Situational terrain bonuses remain explicit rather than applying globally.",
        custom_choice_label="Favored terrains and bonuses",
        maximum_choices_resolver=lambda level, _tokens: 0 if level < 3 else 1 + (level - 3) // 5,
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
    ClassFeatureResourceDefinition(
        "combat_style", "Combat Style Feats", ("combat-style-feat",),
        lambda _level, _wisdom: 0,
        "Record combat style and granted feats at 2nd, 6th, 10th, 14th, and 18th levels. These feats ignore their normal prerequisites where the class rule permits.",
        custom_choice_label="Combat style / granted feats",
        maximum_choices_resolver=lambda level, _tokens: sum(level >= threshold for threshold in (2, 6, 10, 14, 18)),
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)

VIGILANTE_RESOURCES = (
    ClassFeatureResourceDefinition(
        "hidden_strike", "Hidden Strike Applies", ("vigilante-specialization",),
        lambda _level, _charisma: 1,
        "For a Stalker, toggle when the target qualifies for full d8 hidden strike damage. Use the notes for flanking/denied-Dexterity cases that reduce the dice to d4s.",
        can_activate=True, choice_options=("Avenger", "Stalker"),
        recover_on_full_rest=False, end_on_full_rest=False,
    ),
)


def _package_progression(key: str) -> Callable[[int, int], int]:
    """Resolve allowlisted package progression names into pure calculations."""

    progressions: dict[str, Callable[[int, int], int]] = {
        "zero": lambda _level, _ability: 0,
        "one": lambda _level, _ability: 1,
        "two": lambda _level, _ability: 2,
        "three": lambda _level, _ability: 3,
        "four": lambda _level, _ability: 4,
        "five": lambda _level, _ability: 5,
        "six": lambda _level, _ability: 6,
        "level": lambda level, _ability: level,
        "level_times_three": lambda level, _ability: level * 3,
        "ability_modifier": lambda _level, ability: ability,
        "ability_modifier_nonnegative": lambda _level, ability: max(0, ability),
        "one_plus_ability": lambda _level, ability: 1 + ability,
        "ability_modifier_minimum_one": lambda _level, ability: max(1, ability),
        "one_plus_ability_minimum_one": lambda _level, ability: max(1, 1 + ability),
        "three_plus_ability": lambda _level, ability: 3 + ability,
        "three_plus_ability_minimum_one": lambda _level, ability: max(1, 3 + ability),
        "four_plus_ability": lambda _level, ability: 4 + ability,
        "level_plus_ability_minimum_one": lambda level, ability: max(1, level + ability),
        "half_level_minimum_one": lambda level, _ability: max(1, level // 2),
        "half_level_plus_ability_minimum_one": lambda level, ability: max(1, level // 2 + ability),
        "level_minus_one_plus_ability_minimum_one": lambda level, ability: max(1, level - 1 + ability),
        "quarter_level": lambda level, _ability: level // 4,
        "level_plus_ten": lambda level, _ability: level + 10,
        "monk_ac_level_bonus": lambda level, _ability: level // 4,
        "monk_fast_movement": lambda level, _ability: (level // 3) * 10,
        "monk_maneuver_training_bonus": lambda level, _ability: level - ((level * 3) // 4),
        "fighter_bravery": lambda level, _ability: 0 if level < 2 else 1 + (level - 2) // 4,
        "third_level": lambda level, _ability: level // 3,
        "fighter_conditioning": lambda level, _ability: 0 if level < 2 else 1 + (level - 2) // 4,
        "skirmisher_mobility": lambda level, _ability: 0 if level < 3 else min(4, 1 + (level - 3) // 4),
        "dragonheir_natural_armor": lambda level, _ability: 3 if level >= 13 else 2 if level >= 7 else 1 if level >= 3 else 0,
        "dragonheir_fearful_might": lambda level, _ability: 0 if level < 1 else min(5, 1 if level < 6 else 2 + (level - 6) // 4),
        "savage_natural_savagery": lambda level, _ability: 0 if level < 5 else 1 + (level - 5) // 4,
        "minus_two": lambda _level, _ability: -2,
        "three_plus_half_level": lambda level, _ability: 3 + level // 2,
        "bardic_performance_rounds": lambda level, ability: 2 * level + 2 + ability,
        "bard_lore_master_uses": lambda level, _ability: 0 if level < 5 else 1 + (level - 5) // 6,
        "archaeologist_luck_bonus": lambda level, _ability: 4 if level >= 17 else 3 if level >= 11 else 2 if level >= 5 else 1,
        "inquisitor_judgment_uses": lambda level, _ability: 1 + max(0, level - 1) // 3,
        "one_plus_every_three_after_one": lambda level, _ability: 1 + max(0, level - 1) // 3,
        "one_plus_every_four_after_one": lambda level, _ability: 1 + max(0, level - 1) // 4,
        "one_plus_every_four_after_three": lambda level, _ability: 0 if level < 3 else 1 + (level - 3) // 4,
        "cavalier_tactician_uses": lambda level, _ability: 1 + level // 5,
        "cavalier_banner_bonus": lambda level, _ability: 0 if level < 5 else 2 + (level - 5) // 5,
        "cavalier_banner_charge_bonus": lambda level, _ability: 0 if level < 5 else 1 + (level - 5) // 5,
        "weapon_training_from_five": lambda level, _ability: 0 if level < 5 else 1 + (level - 5) // 4,
        "armor_training_from_five": lambda level, _ability: 0 if level < 5 else 1 + (level - 5) // 4,
        "wild_shape_from_seven": lambda level, _ability: 0 if level < 7 else 1 + (level - 7) // 4,
        "wild_shape_from_four": lambda level, _ability: 0 if level < 4 else 99 if level >= 20 else 1 + (level - 4) // 2,
        "spiritualist_bonded_manifestation": lambda level, _ability: 3 + (2 * level if level >= 17 else level),
        "one_plus_every_four_after_six": lambda level, _ability: 0 if level < 6 else 1 + (level - 6) // 4,
        "triple_goddess_thread_uses": lambda level, _ability: (
            0 if level < 5 else 1 + (level - 5) // 4
        ),
        "one_plus_every_four_after_seven": lambda level, _ability: 0 if level < 7 else 1 + (level - 7) // 4,
        "one_at_eleven_two_at_sixteen": lambda level, _ability: 0 if level < 11 else 2 if level >= 16 else 1,
        "one_at_thirteen_two_at_seventeen": lambda level, _ability: 0 if level < 13 else 2 if level >= 17 else 1,
        "slayer_quarry_bonus": lambda level, _ability: 0 if level < 14 else 4 if level >= 19 else 2,
        "bloody_jake_favored_terrain": lambda level, _ability: 2 + 2 * (level // 5),
        "hunting_serpent_death_mark": lambda level, _ability: 0 if level < 4 else 1 + (level - 4) // 4,
        "frozen_shadow_illusion_save": lambda level, _ability: 0 if level < 4 else 4 if level >= 8 else 2,
        "favored_terrain_from_five": lambda level, _ability: 0 if level < 5 else 1 + (level - 5) // 4,
        "one_plus_half_level": lambda level, _ability: 1 + level // 2,
        "twice_level": lambda level, _ability: 2 * level,
        "speak_to_city_bonus": lambda level, _ability: 0 if level < 1 else 2 + 2 * max(0, (level - 1) // 5),
        "hagbound_strength": lambda level, _ability: 0 if level < 2 else 6 if level >= 14 else 4 if level >= 8 else 2,
        "invoke_patron_bonus": lambda level, _ability: 0 if level < 1 else 3 if level >= 16 else 2 if level >= 8 else 1,
        "gunslinger_nimble": lambda level, _ability: 0 if level < 2 else 1 + (level - 2) // 4,
        "armor_training_from_four": lambda level, _ability: 0 if level < 4 else min(4, 1 + (level - 4) // 4),
        "commando_favored_terrains": lambda level, _ability: 0 if level < 2 else 1 + (level - 2) // 4,
        "firebrand_bombs": lambda level, ability: 0 if level < 5 else max(1, level - 4 + ability),
        "wandering_ritual_uses": lambda level, _ability: 0 if level < 6 else 3 if level >= 14 else 2 if level >= 8 else 1,
        "imperial_judgment_uses": lambda level, _ability: 0 if level < 4 else 1 + (level - 4) // 3,
        "myrmidarch_weapon_training": lambda level, _ability: 0 if level < 6 else 1 + (level - 6) // 6,
        "myrmidarch_armor_training": lambda level, _ability: 0 if level < 8 else 1 + (level - 8) // 6,
        "spell_dance_speed": lambda level, _ability: 10 * (1 + max(0, level - 1) // 4),
        "spell_dance_defense": lambda level, _ability: 2 * (1 + max(0, level - 1) // 4),
        "pitax_extra_performance_rounds": lambda level, _ability: (
            0 if level < 2 else 6 * (1 + max(0, level - 2) // 6)
        ),
        "armiger_customized_weapons": lambda level, _ability: (
            5 if level >= 19 else 4 if level >= 11 else 3
        ),
        "armiger_enhancement": lambda level, _ability: (
            0 if level < 5 else 1 + (level - 5) // 4
        ),
        "armorist_bound_items": lambda level, _ability: (
            5 if level >= 20 else 4 if level >= 15 else 3 if level >= 10 else 2 if level >= 5 else 1
        ),
        "armorist_bound_bonus": lambda level, _ability: min(
            10, 1 + max(0, level - 1) // 2
        ),
        "armorist_armor_training": lambda level, _ability: (
            0 if level < 3 else min(5, 1 + (level - 3) // 4)
        ),
        "blacksmith_maintenance_allies": lambda _level, ability: max(1, 1 + ability),
        "blacksmith_maintenance_count": lambda level, _ability: (
            4 if level >= 17 else 3 if level >= 13 else 2 if level >= 9 else 1
        ),
        "blacksmith_maintenance_bonus": lambda level, _ability: 1 + level // 5,
        "blacksmith_weapon_maintenance_bonus": lambda level, _ability: 2 * (1 + level // 5),
        "elementalist_dodge": lambda level, _ability: min(5, level // 4),
        "elementalist_resistance": lambda level, _ability: (
            20 if level >= 20 else 15 if level >= 17 else 10 if level >= 11 else 5 if level >= 5 else 0
        ),
        "elementalist_movement_choices": lambda level, _ability: (
            3 if level >= 19 else 2 if level >= 13 else 1 if level >= 7 else 0
        ),
        "elementalist_land_movement": lambda level, _ability: (
            40 if level >= 19 else 30 if level >= 13 else 20 if level >= 7 else 0
        ),
        "elementalist_swim_movement": lambda level, _ability: (
            50 if level >= 19 else 40 if level >= 13 else 30 if level >= 7 else 0
        ),
        "elementalist_fly_movement": lambda level, _ability: (
            40 if level >= 19 else 30 if level >= 13 else 20 if level >= 7 else 0
        ),
        "elementalist_burrow_movement": lambda level, _ability: (
            35 if level >= 19 else 25 if level >= 13 else 15 if level >= 7 else 0
        ),
        "commander_active_tactics": lambda level, _ability: (
            3 if level >= 20 else 2 if level >= 10 else 1 if level >= 2 else 0
        ),
        "commander_group_focus": lambda level, _ability: (
            0 if level < 5 else 1 + (level - 5) // 6
        ),
        "ten_plus_half_level_plus_ability": lambda level, ability: (
            10 + level // 2 + ability
        ),
        "thirty_plus_ten_level": lambda level, _ability: 30 + 10 * level,
        "sentinel_challenge_bonus": lambda level, _ability: min(
            5, 1 + max(0, level - 1) // 4
        ),
        "sentinel_dedicated_defense": lambda level, _ability: (
            0 if level < 2 else 1 + (level - 2) // 4
        ),
        "sentinel_guard_wall": lambda level, _ability: (
            0 if level < 2 else 4 if level >= 12 else 2
        ),
        "striker_tension": lambda level, ability: (
            max(1, ability) + level // 3
        ),
        "striker_opening_tension": lambda level, _ability: (
            7 if level >= 20 else 0 if level < 2 else 1 + max(0, level - 1) // 6
        ),
        "striker_drill_knuckle": lambda level, _ability: (
            0 if level < 3 else 2 + (level - 3) // 3
        ),
        "technician_gadgets": lambda level, ability: max(
            1, level // 2 + ability
        ),
        "technician_inventions": lambda level, _ability: (
            0 if level < 1 else 1 + (level + 1) // 4
        ),
        "technician_danger_sense": lambda level, _ability: level // 3,
        "one_plus_every_five_after_one": lambda level, _ability: (
            0 if level < 1 else 1 + level // 5
        ),
        "quarter_level_plus_ability_minimum_one": lambda level, ability: max(
            1, level // 4 + ability
        ),
        "mageknight_resist_magic": lambda level, _ability: min(
            5, 1 + max(0, level - 1) // 4
        ),
        "mageknight_mystic_defense": lambda level, _ability: (
            0 if level < 11 else level // 2
        ),
        "soul_weaver_channel_dice": lambda level, _ability: (
            1 + max(0, level - 1) // 2
        ),
        "thaumaturge_forbidden_lore": lambda level, _ability: min(
            6, 2 + max(0, level - 1) // 4
        ),
        "thaumaturge_occult_knowledge": lambda level, _ability: (
            0 if level < 2 else min(5, 1 + (level - 2) // 4)
        ),
        "odd_level_dice": lambda level, _ability: (level + 1) // 2,
        "fey_adept_shadowmark_penalty": lambda level, _ability: (
            4 if level >= 19 else 3 if level >= 13 else 2 if level >= 7 else 1
        ),
        "symbiat_battlefield_sense": lambda level, ability: max(0, ability) + level // 4,
        "symbiat_pushed_movement": lambda level, _ability: (
            0 if level < 3 else min(60, 10 * (level // 3))
        ),
        "three_plus_half_level": lambda level, _ability: 3 + level // 2,
        "eliciter_persuasive": lambda level, _ability: (
            5 if level >= 18 else 4 if level >= 12 else 3 if level >= 6 else 2
        ),
        "eliciter_save_dc": lambda level, ability: (
            10 + level // 2 + ability
            + (5 if level >= 18 else 4 if level >= 12 else 3 if level >= 6 else 2)
        ),
        "eliciter_convincing": lambda level, _ability: (
            0 if level < 9 else 3 if level >= 17 else 2 if level >= 13 else 1
        ),
        "quarter_level": lambda level, _ability: level // 4,
        "twenty": lambda _level, _ability: 20,
        "three_plus_ability_minimum_one": lambda _level, ability: max(1, 3 + ability),
        "necros_necrotic_shield": lambda level, ability: (
            (level + ability) * (2 if level >= 13 else 1)
        ),
        "necros_decaying_form": lambda level, _ability: min(4, level // 4),
        "troubadour_quick_change": lambda level, _ability: (
            0 if level < 2 else 1 + max(0, level - 2) // 4
        ),
        "troubadour_flexible_truth": lambda level, _ability: 15 + level // 2,
        "troubadour_disguise": lambda level, _ability: 5 + level // 4,
        "troubadour_synergy": lambda level, _ability: (
            1 if level < 5 else 2 if level < 9 else 3 if level < 13 else 4 if level < 17 else 5
        ),
        "necrotech_necrografts": lambda level, _ability: (
            0 if level < 3 else 1 + max(0, (level - 3) // 4)
        ),
        "binder_potent_expulsion": lambda level, _ability: (
            0 if level < 2 else 1 + max(0, (level - 2) // 8)
        ),
        "ringmaster_ceremony_duration": lambda level, _ability: (
            0 if level < 3 else 3 + level // 2
        ),
        "jailer_detain_targets": lambda level, ability: (
            max(1, ability) if level >= 20 else 1
        ),
        "crimson_bloodletting_increment": lambda _level, ability: max(1, ability // 2),
        "crimson_autocautery": lambda level, _ability: min(6, 1 + level // 4),
        "crimson_voracity_speed": lambda level, _ability: (
            0 if level < 4 else 30 if level >= 20 else 20 if level >= 12 else 10
        ),
        "mountebank_thiefs_mark": lambda level, _ability: min(5, 1 + max(0, level - 1) // 4),
        "mountebank_secretive_spell": lambda level, _ability: (
            0 if level < 6 else min(3, 1 + (level - 6) // 6)
        ),
        "mountebank_creative_strike": lambda level, ability: min(level, max(0, ability)),
        "mountebank_tension_boost": lambda level, _ability: (
            0 if level < 3 else 4 if level >= 19 else 3 if level >= 13 else 2 if level >= 7 else 1
        ),
        "mountebank_rising_tension": lambda level, _ability: (
            0 if level < 11 else 2 if level >= 16 else 1
        ),
        "mountebank_controlling_attack": lambda level, _ability: (
            0 if level < 5 else min(5, 1 + (level - 5) // 4)
        ),
        "mountebank_controlling_damage": lambda level, _ability: (
            2 * min(5, 1 + max(0, level - 1) // 4)
        ),
        "grifter_tension": lambda level, ability: max(1, ability) + (
            0 if level < 3 else 4 if level >= 19 else 3 if level >= 13 else 2 if level >= 7 else 1
        ),
        "reaper_favored_prey": lambda level, _ability: min(10, 2 + 2 * (level // 5)),
        "reaper_prey_casting": lambda level, _ability: (
            0 if level < 3 else min(5, 1 + (level - 3) // 4)
        ),
        "flagellant_natural_armor": lambda level, _ability: (
            0 if level < 5 else 2 + max(0, level - 5) // 5
        ),
        "machine_cultist_dr": lambda level, _ability: (
            0 if level < 3 else 2 * (1 + max(0, level - 3) // 4)
        ),
        "warden_guarded_allies": lambda level, _ability: (
            5 if level >= 20 else 4 if level >= 17 else 3 if level >= 11 else 2 if level >= 5 else 1
        ),
        "warden_guard_bonus": lambda level, _ability: (
            0 if level < 2 else min(5, 1 + max(0, level - 2) // 4)
        ),
        "warden_steadfast": lambda level, _ability: 1 + level // 5,
        "warden_projected_empathy": lambda level, _ability: (
            10000 if level >= 20 else 100 if level >= 15 else 30 if level >= 10 else 10 if level >= 5 else 0
        ),
        "thirty": lambda _level, _ability: 30,
        "shifter_enhanced_physicality": lambda level, _ability: (
            3 if level >= 19 else 2 if level >= 13 else 1 if level >= 7 else 0
        ),
        "holy_gun_grit": lambda level, ability: (
            0 if level < 11 else max(1, ability) + max(0, (level - 11) // 3)
        ),
    }
    try:
        return progressions[key]
    except KeyError:
        raise ValueError(f"Unknown class-package progression: {key}") from None


def _package_ability_modifier(
    abilities: Mapping[str, int], governing_ability: str
) -> int:
    """Resolve a single or declarative highest-of ability key."""

    key = str(governing_ability or "").strip().casefold()
    if key.startswith("higher:"):
        options = tuple(
            value.strip() for value in key.removeprefix("higher:").split(",")
            if value.strip()
        )
        return max((int(abilities.get(value, 0)) for value in options), default=0)
    return int(abilities.get(key, 0))


def _package_module_definitions() -> tuple[ClassFeatureModuleDefinition, ...]:
    """Adapt data-only packages to the generic class-resource engine."""

    result = []
    for package in all_class_packages():
        owner_keys = {package.class_key}
        if package.class_key.startswith("pathfinder-class:"):
            owner_keys.add(package.class_key.removeprefix("pathfinder-class:"))
        for module in package.resource_modules:
            result.append(
                ClassFeatureModuleDefinition(
                    module.key,
                    module.title,
                    frozenset(owner_keys),
                    module.governing_ability,
                    tuple(
                        ClassFeatureResourceDefinition(
                            key=resource.key,
                            name=resource.name,
                            feature_tokens=resource.feature_tokens,
                            base_maximum=_package_progression(resource.progression),
                            description=resource.description,
                            can_activate=resource.can_activate,
                            choice_options=resource.choice_options,
                            activate_on_spend=resource.activate_on_spend,
                            recover_on_full_rest=resource.recover_on_full_rest,
                            end_on_full_rest=resource.end_on_full_rest,
                            custom_choice_label=resource.custom_choice_label,
                            use_requires_active=resource.use_requires_active,
                            use_cost=resource.use_cost,
                            tracks_uses=resource.tracks_uses,
                            external_cost_key=resource.external_cost_key,
                            requires_choice_provider=resource.requires_choice_provider,
                            requires_choice_option=resource.requires_choice_option,
                            extra_damage_levels=resource.extra_damage_levels,
                            extra_damage_die=resource.extra_damage_die,
                            extra_damage_type=resource.extra_damage_type,
                            maximum_choices_resolver=(
                                lambda level, _tokens, progression=resource.maximum_choices_progression:
                                _package_progression(progression)(level, 0)
                            ) if resource.maximum_choices_progression else None,
                            recovery_resolver=(
                                lambda level, abilities, _tokens, _archetypes, _powers,
                                progression=resource.recovery_progression,
                                ability=module.governing_ability:
                                _package_progression(progression)(
                                    level, _package_ability_modifier(abilities, ability)
                                )
                            ) if resource.recovery_progression else None,
                            use_increases=resource.use_increases,
                            restore_toward_zero=resource.restore_toward_zero,
                        )
                        for resource in module.resources
                    ),
                    module.grantable,
                )
            )
    return tuple(result)


def _runtime_module_definitions(
    class_key: str,
    archetype_keys: frozenset[str],
) -> tuple[ClassFeatureModuleDefinition, ...]:
    """Adapt reviewed archetype-only resources from separate overlay files."""

    result: list[ClassFeatureModuleDefinition] = []
    for archetype_key in sorted(archetype_keys):
        overlay = archetype_runtime_package(archetype_key) or {}
        for raw in overlay.get("resource_modules", ()):
            if not isinstance(raw, Mapping):
                continue
            module = package_module(raw)
            result.append(
                ClassFeatureModuleDefinition(
                    module.key,
                    module.title,
                    frozenset({class_key}),
                    module.governing_ability,
                    tuple(
                        ClassFeatureResourceDefinition(
                            key=resource.key,
                            name=resource.name,
                            feature_tokens=resource.feature_tokens,
                            base_maximum=_package_progression(resource.progression),
                            description=resource.description,
                            can_activate=resource.can_activate,
                            choice_options=resource.choice_options,
                            activate_on_spend=resource.activate_on_spend,
                            recover_on_full_rest=resource.recover_on_full_rest,
                            end_on_full_rest=resource.end_on_full_rest,
                            custom_choice_label=resource.custom_choice_label,
                            use_requires_active=resource.use_requires_active,
                            use_cost=resource.use_cost,
                            tracks_uses=resource.tracks_uses,
                            external_cost_key=resource.external_cost_key,
                            requires_choice_provider=resource.requires_choice_provider,
                            requires_choice_option=resource.requires_choice_option,
                            extra_damage_levels=resource.extra_damage_levels,
                            extra_damage_die=resource.extra_damage_die,
                            extra_damage_type=resource.extra_damage_type,
                            maximum_choices_resolver=(
                                lambda level, _tokens, progression=resource.maximum_choices_progression:
                                _package_progression(progression)(level, 0)
                            ) if resource.maximum_choices_progression else None,
                            recovery_resolver=(
                                lambda level, abilities, _tokens, _archetypes, _powers,
                                progression=resource.recovery_progression,
                                ability=module.governing_ability:
                                _package_progression(progression)(
                                    level, _package_ability_modifier(abilities, ability)
                                )
                            ) if resource.recovery_progression else None,
                            use_increases=resource.use_increases,
                            restore_toward_zero=resource.restore_toward_zero,
                        )
                        for resource in module.resources
                    ),
                )
            )
    return tuple(result)


def _apply_runtime_resource_adjustments(
    resources: tuple[ResolvedClassFeatureResource, ...],
    overlays: Iterable[Mapping[str, object]],
    class_level: int,
    ability_modifier: int,
) -> tuple[ResolvedClassFeatureResource, ...]:
    """Layer archetype deltas over retained resources without replacing them.

    This covers rules such as bonus performance rounds while preserving the
    base resource's activation, recovery, choices, and character overrides.
    """

    declarations = {
        str(raw.get("resource_key") or ""): raw
        for overlay in overlays
        for raw in overlay.get("resource_adjustments", ())
        if isinstance(raw, Mapping) and str(raw.get("resource_key") or "")
    }
    result = []
    for resource in resources:
        declaration = declarations.get(resource.key)
        if not declaration:
            result.append(resource)
            continue
        progression = str(declaration.get("maximum_bonus_progression") or "zero")
        bonus = max(0, _package_progression(progression)(class_level, ability_modifier))
        maximum_progression = str(declaration.get("maximum_progression") or "")
        if maximum_progression and resource.state.maximum_override is None:
            maximum = max(
                0,
                _package_progression(maximum_progression)(
                    class_level, ability_modifier
                ) + int(resource.state.maximum_adjustment),
            )
            bonus = 0
        else:
            if resource.state.maximum_override is not None:
                bonus = 0
            maximum = resource.maximum + bonus
        recovery_progression = str(declaration.get("recovery_progression") or "")
        recovery = (
            _package_progression(recovery_progression)(class_level, ability_modifier)
            if recovery_progression else resource.recovery_value + bonus
        )
        recovery = max(0, min(maximum, recovery))
        default_progression = str(
            declaration.get("current_default_progression") or ""
        )
        if resource.state.current_value is None and default_progression:
            current = _package_progression(default_progression)(
                class_level, ability_modifier
            )
        elif resource.state.current_value is None:
            current = resource.current + bonus
        else:
            current = resource.current
        current = max(0, min(maximum, current))
        description = str(declaration.get("description") or resource.description)
        name = str(declaration.get("name") or resource.name)
        choice_options = (
            tuple(str(value) for value in declaration.get("choice_options", ()))
            if "choice_options" in declaration else resource.choice_options
        )
        maximum_choice_levels = tuple(
            max(1, int(value))
            for value in declaration.get("maximum_choices_levels", ())
        )
        maximum_choices = (
            sum(class_level >= level for level in maximum_choice_levels)
            if maximum_choice_levels else resource.maximum_choices
        )
        result.append(
            replace(
                resource,
                name=name,
                description=description,
                maximum=maximum,
                current=current,
                recovery_value=recovery,
                choice_options=choice_options,
                maximum_choices=maximum_choices,
                choices=resource.choices[:maximum_choices],
                use_increases=(
                    bool(declaration.get("use_increases"))
                    if "use_increases" in declaration else resource.use_increases
                ),
                restore_toward_zero=(
                    bool(declaration.get("restore_toward_zero"))
                    if "restore_toward_zero" in declaration
                    else resource.restore_toward_zero
                ),
                recover_on_full_rest=(
                    bool(declaration.get("recover_on_full_rest"))
                    if "recover_on_full_rest" in declaration
                    else resource.recover_on_full_rest
                ),
                end_on_full_rest=(
                    bool(declaration.get("end_on_full_rest"))
                    if "end_on_full_rest" in declaration
                    else resource.end_on_full_rest
                ),
            )
        )
    return tuple(result)

CLASS_FEATURE_MODULES: tuple[ClassFeatureModuleDefinition, ...] = (
    *_package_module_definitions(),
    ClassFeatureModuleDefinition(
        "monk", "Monk Ki",
        frozenset({"pathfinder-class:monk"}), "wisdom", MONK_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "monk_unchained", "Unchained Monk Ki",
        frozenset({"pathfinder-class:monk-unchained"}), "wisdom", MONK_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "barbarian", "Barbarian Rage",
        frozenset({"pathfinder-class:barbarian"}), "constitution", BARBARIAN_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "barbarian_unchained", "Unchained Barbarian Rage",
        frozenset({"pathfinder-class:barbarian-unchained"}), "constitution", BARBARIAN_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "alchemist", "Alchemist Resources",
        frozenset({"pathfinder-class:alchemist"}), "intelligence", ALCHEMIST_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "arcanist", "Arcanist Resources",
        frozenset({"pathfinder-class:arcanist"}), "intelligence", ARCANIST_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "investigator", "Investigator Inspiration",
        frozenset({"pathfinder-class:investigator"}), "intelligence", INVESTIGATOR_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "magus", "Magus Arcane Pool",
        frozenset({"pathfinder-class:magus"}), "intelligence", MAGUS_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "ninja", "Ninja Ki",
        frozenset({"pathfinder-class:ninja"}), "charisma", NINJA_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "gunslinger", "Gunslinger Grit",
        frozenset({"pathfinder-class:gunslinger"}), "wisdom", GUNSLINGER_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "swashbuckler", "Swashbuckler Panache",
        frozenset({"pathfinder-class:swashbuckler"}), "charisma", SWASHBUCKLER_RESOURCES + SWASHBUCKLER_TRAINING_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "bloodrager", "Bloodrager Bloodrage",
        frozenset({"pathfinder-class:bloodrager"}), "constitution", BLOODRAGER_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "paladin", "Paladin Class Systems",
        frozenset({"pathfinder-class:paladin"}), "charisma", PALADIN_RESOURCES + MERCY_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "antipaladin", "Antipaladin Class Systems",
        frozenset({"pathfinder-class:antipaladin"}), "charisma", ANTIPALADIN_RESOURCES + CRUELTY_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "cleric", "Cleric Channel Energy",
        frozenset({"pathfinder-class:cleric"}), "charisma", CLERIC_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "warpriest", "Warpriest Fervor",
        frozenset({"pathfinder-class:warpriest"}), "wisdom", WARPRIEST_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "cavalier", "Cavalier Challenge",
        frozenset({"pathfinder-class:cavalier"}), "charisma", CHALLENGE_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "samurai", "Samurai Challenge",
        frozenset({"pathfinder-class:samurai"}), "charisma", SAMURAI_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "druid", "Druid Wild Shape",
        frozenset({"pathfinder-class:druid"}), "wisdom", WILD_SHAPE_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "shifter", "Shifter Wild Shape",
        frozenset({"pathfinder-class:shifter"}), "wisdom", SHIFTER_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "kineticist", "Kineticist Burn",
        frozenset({"pathfinder-class:kineticist"}), "constitution", KINETICIST_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "occultist", "Occultist Mental Focus",
        frozenset({"pathfinder-class:occultist"}), "intelligence", OCCULTIST_RESOURCES + OCCULTIST_ADVANCEMENT_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "psychic", "Psychic Phrenic Pool",
        frozenset({"pathfinder-class:psychic"}), "wisdom", PSYCHIC_RESOURCES + PSYCHIC_ADVANCEMENT_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "rogue", "Rogue Sneak Attack",
        frozenset({"pathfinder-class:rogue"}), "dexterity", SNEAK_ATTACK_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "rogue_unchained", "Unchained Rogue Sneak Attack",
        frozenset({"pathfinder-class:rogue-unchained"}), "dexterity", SNEAK_ATTACK_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "ninja_precision", "Ninja Sneak Attack",
        frozenset({"pathfinder-class:ninja"}), "dexterity", SNEAK_ATTACK_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "slayer", "Slayer Combat Systems",
        frozenset({"pathfinder-class:slayer"}), "intelligence", SLAYER_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "ranger", "Ranger Favored Enemies",
        frozenset({"pathfinder-class:ranger"}), "wisdom", RANGER_RESOURCES + RANGER_ADVANCEMENT_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "skald", "Skald Raging Song",
        frozenset({"pathfinder-class:skald"}), "charisma", SKALD_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "summoner", "Summoner Eidolon",
        frozenset({"pathfinder-class:summoner"}), "charisma", EIDOLON_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "summoner_unchained", "Unchained Summoner Eidolon",
        frozenset({"pathfinder-class:summoner-unchained"}), "charisma", EIDOLON_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "brawler", "Brawler Martial Flexibility",
        frozenset({"pathfinder-class:brawler"}), "strength", BRAWLER_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "hunter", "Hunter Animal Focus",
        frozenset({"pathfinder-class:hunter"}), "wisdom", HUNTER_RESOURCES, True,
    ),
    ClassFeatureModuleDefinition(
        "fighter", "Fighter Training",
        frozenset({"pathfinder-class:fighter"}), "strength", FIGHTER_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "medium", "Medium Spirit",
        frozenset({"pathfinder-class:medium"}), "charisma", MEDIUM_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "mesmerist", "Mesmerist Class Systems",
        frozenset({"pathfinder-class:mesmerist"}), "charisma", MESMERIST_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "spiritualist", "Spiritualist Phantom",
        frozenset({"pathfinder-class:spiritualist"}), "wisdom", SPIRITUALIST_RESOURCES,
    ),
    ClassFeatureModuleDefinition(
        "vigilante", "Vigilante Specialization",
        frozenset({"pathfinder-class:vigilante"}), "charisma", VIGILANTE_RESOURCES,
    ),
)


def _choices(state: ClassFeatureState) -> tuple[str, ...]:
    try:
        values = json.loads(state.choices_json or "[]")
    except (TypeError, ValueError):
        return ()
    return tuple(str(value) for value in values if str(value).strip()) if isinstance(values, list) else ()


def _resource_view(
    definition: ClassFeatureResourceDefinition,
    character_id: int,
    class_level,
    ability_modifiers: Mapping[str, int],
    governing_ability: str,
    feature_tokens: frozenset[str],
    archetype_keys: frozenset[str],
    power_names: frozenset[str],
    state: ClassFeatureState | None,
) -> ResolvedClassFeatureResource | None:
    if not any(
        token in feature_tokens
        or any(
            re.fullmatch(rf"{re.escape(token)}-\d+(?:d\d+)?(?:-.+)?", owned)
            for owned in feature_tokens
        )
        for token in definition.feature_tokens
    ):
        return None
    state = state or ClassFeatureState(
        character_id, class_level.id, definition.key
    )
    effective_abilities = dict(ability_modifiers)
    # Rage's own temporary Constitution bonus must never enlarge the pool it
    # is currently consuming. Other permanent ability changes still count.
    if state.active and governing_ability == "constitution" and definition.key in {
        "rage", "bloodrage",
    }:
        modifier_increase = 4 if class_level.level >= 20 else 3 if class_level.level >= 11 else 2
        effective_abilities["constitution"] = (
            int(effective_abilities.get("constitution", 0)) - modifier_increase
        )
    governing_modifier = _package_ability_modifier(
        effective_abilities, governing_ability
    )
    if definition.key == "phrenic_pool" and state is not None:
        selected_ability = next(iter(_choices(state)), "").strip().casefold()
        if selected_ability in {"wisdom", "charisma"}:
            governing_modifier = int(effective_abilities.get(selected_ability, 0))
            other = "charisma" if selected_ability == "wisdom" else "wisdom"
            effective_abilities[other] = -99
    automatic = max(
        0,
        (
            definition.maximum_resolver(
                class_level.level,
                effective_abilities,
                feature_tokens,
                archetype_keys,
                power_names,
            )
            if definition.maximum_resolver is not None
            else definition.base_maximum(class_level.level, governing_modifier)
        ),
    )
    if (
        definition.key == "mental_focus"
        and "pathfinder-archetype:pathfinder-class:occultist:silksworn"
        in archetype_keys
    ):
        automatic = max(
            0,
            class_level.level
            + int(effective_abilities.get("intelligence", 0))
            + int(effective_abilities.get("charisma", 0)),
        )
    maximum = (
        state.maximum_override
        if state.maximum_override is not None
        else automatic + state.maximum_adjustment
    )
    maximum = max(0, int(maximum))
    automatic_recovery = (
        definition.recovery_resolver(
            class_level.level,
            effective_abilities,
            feature_tokens,
            archetype_keys,
            power_names,
        )
        if definition.recovery_resolver is not None
        else maximum
    )
    recovery_value = max(0, min(maximum, int(automatic_recovery)))
    current = recovery_value if state.current_value is None else max(0, int(state.current_value))
    if definition.maximum_choices_resolver is not None:
        maximum_choices = max(
            0, int(definition.maximum_choices_resolver(class_level.level, feature_tokens))
        )
    elif definition.key == "judgment":
        maximum_choices = (
            3 if "third-judgment" in feature_tokens
            else 2 if "second-judgment" in feature_tokens
            else 1
        )
    else:
        maximum_choices = 1 if (
            definition.choice_options
            or definition.choice_options_resolver
            or definition.custom_choice_label
        ) else 0
    choice_options = (
        definition.choice_options_resolver(power_names)
        if definition.choice_options_resolver is not None
        else definition.choice_options
    )
    if definition.key == "bardic_performance":
        choice_options = tuple(
            name for token, name in BARD_PERFORMANCES if token in feature_tokens
        )
        maximum_choices = 1
    choices = _choices(state)
    if definition.key == "bardic_performance":
        standard_performances = {name.casefold() for _token, name in BARD_PERFORMANCES}
        available_performances = {name.casefold() for name in choice_options}
        choices = tuple(choice for choice in choices
                        if choice.casefold() not in standard_performances
                        or choice.casefold() in available_performances)
    if maximum_choices:
        choices = choices[:maximum_choices]
    return ResolvedClassFeatureResource(
        class_level.id,
        class_level.class_name,
        definition.key,
        definition.name,
        definition.description,
        maximum,
        current,
        bool(state.active and definition.can_activate),
        choices,
        choice_options,
        maximum_choices,
        state,
        definition.can_activate,
        definition.activate_on_spend,
        recovery_value,
        definition.recover_on_full_rest,
        definition.end_on_full_rest,
        definition.custom_choice_label,
        definition.activation_requires,
        definition.restore_resources_on_activate,
        definition.deactivate_resources_on_end,
        definition.restore_on_activate,
        definition.use_requires_active,
        definition.deactivate_resources_on_use,
        definition.use_increases,
        definition.restore_toward_zero,
        definition.spend_resource_key,
        max(1, int(definition.use_cost)),
        definition.tracks_uses,
        definition.external_cost_key,
        definition.extra_damage_levels,
        definition.extra_damage_die,
        definition.extra_damage_type,
    )


def _resolve_linked_resource_costs(
    resources: tuple[ResolvedClassFeatureResource, ...],
) -> tuple[ResolvedClassFeatureResource, ...]:
    """Project resources such as Channel Energy from their real source pool.

    Paladins, antipaladins, and warpriests do not own an independent channel
    pool: one use costs two Lay on Hands, Touch of Corruption, or Fervor uses.
    Keeping that relationship declarative prevents the two displayed counters
    from drifting apart.
    """

    by_key = {resource.key: resource for resource in resources}
    result: list[ResolvedClassFeatureResource] = []
    for resource in resources:
        source = by_key.get(resource.spend_resource_key)
        if source is None:
            result.append(resource)
            continue
        cost = max(1, resource.use_cost)
        result.append(
            replace(
                resource,
                maximum=source.maximum // cost,
                current=source.current // cost,
                recovery_value=source.recovery_value // cost,
            )
        )
    return tuple(result)


def _decoded_choice_keys(value: object) -> frozenset[str]:
    """Read both current JSON choice records and legacy single-key saves."""

    text = str(value or "").strip()
    if not text:
        return frozenset()
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError):
        return frozenset({text})
    if isinstance(decoded, list):
        return frozenset(str(item) for item in decoded if str(item))
    return frozenset({text})


def _resource_choice_requirement_met(
    definition: ClassFeatureResourceDefinition,
    class_level_id: int,
    selected_choices: Mapping[tuple[int, str], frozenset[str]],
) -> bool:
    provider = definition.requires_choice_provider
    if not provider:
        return True
    selected = selected_choices.get((class_level_id, provider), frozenset())
    if not definition.requires_choice_option:
        return bool(selected)
    required = definition.requires_choice_option
    return any(
        key == required or key.rsplit(":", 1)[-1] == required
        for key in selected
    )


def _equipment_requirements(repository, character_id: int) -> tuple[bool, bool]:
    """Return live no-armor/no-shield and light-load eligibility.

    This intentionally lives beside the package-effect adapter so any future
    class package can reuse the same requirements without adding a class-name
    branch to the calculation service.
    """

    from app.item_containers import carried_inventory_weight
    from app.item_effects import effective_item_state
    from app.rules import calculate_encumbrance

    equipment = tuple(repository.list_equipment(character_id))
    unarmored = not any(
        effective_item_state(item) in {"armor", "shield"}
        for item in equipment
        if int(item.quantity) > 0
    )
    details = repository.get_character_details(character_id)
    strength = int(repository.get_ability_scores(character_id).get("strength", 10))
    weight = carried_inventory_weight(
        equipment,
        repository.list_inventory_placements(character_id),
    )
    unencumbered = calculate_encumbrance(
        strength, details.size, weight, 0
    ).load == "Light"
    return unarmored, unencumbered


def _choice_feature_resource_modules(
    repository,
    character_id: int,
    ability_modifiers: Mapping[str, int],
    saved: Mapping[tuple[int, str], ClassFeatureState],
    archetype_keys_by_level: Mapping[int, frozenset[str]],
) -> tuple[ResolvedClassFeatureModule, ...]:
    """Project build-time-normalized school/domain power uses.

    Choice catalogs own the exact granted powers.  The importer may attach a
    small resource declaration to a power with recurring daily uses; this
    adapter turns that data into the same tracker used by all class packages.
    """

    from app.class_choice_rules import resolve_class_choice_slots

    classes = {item.id: item for item in repository.list_class_levels(character_id)}
    result: list[ResolvedClassFeatureModule] = []
    for slot in resolve_class_choice_slots(repository, character_id):
        class_level = classes.get(slot.class_level_id)
        if class_level is None:
            continue
        package = class_package(class_level.preset_key)
        default_ability = (
            package.governing_ability if package and package.governing_ability
            else "charisma"
        )
        for option in slot.selected_options:
            for feature in option.granted_features:
                if not isinstance(feature, Mapping):
                    continue
                if max(1, int(feature.get("level") or 1)) > class_level.level:
                    continue
                resource = feature.get("resource")
                if not isinstance(resource, Mapping):
                    continue
                progression = str(resource.get("progression") or "")
                if not progression:
                    continue
                feature_name = str(feature.get("name") or "Class Power")
                token = feature_token(feature_name)
                option_token = feature_token(option.name)
                key = (
                    f"choice_{feature_token(slot.key)}_{option_token}_{token}"
                )
                governing_ability = str(
                    resource.get("ability") or default_ability
                ).casefold()
                definition = ClassFeatureResourceDefinition(
                    key,
                    feature_name,
                    (token,),
                    _package_progression(progression),
                    str(feature.get("description") or option.description),
                    recover_on_full_rest=bool(
                        resource.get("recover_on_full_rest", True)
                    ),
                )
                view = _resource_view(
                    definition,
                    character_id,
                    class_level,
                    ability_modifiers,
                    governing_ability,
                    frozenset({token}),
                    archetype_keys_by_level.get(class_level.id, frozenset()),
                    frozenset(),
                    saved.get((class_level.id, key)),
                )
                if view is None:
                    continue
                result.append(ResolvedClassFeatureModule(
                    f"choice:{slot.key}:{option_token}:{token}",
                    f"{slot.label}: {option.name}",
                    class_level.id,
                    class_level.class_name,
                    class_level.level,
                    governing_ability,
                    frozenset({token}),
                    (view,),
                ))
    return tuple(result)


def _combine_grit_and_panache(
    modules: list[ResolvedClassFeatureModule],
    saved: Mapping[tuple[int, str], ClassFeatureState],
    character_id: int,
) -> tuple[ResolvedClassFeatureModule, ...]:
    """Apply the published rule that grit and panache form one heroic pool."""

    grit_modules = [module for module in modules if module.key == "gunslinger"]
    panache_modules = [module for module in modules if module.key == "swashbuckler"]
    if not grit_modules or not panache_modules:
        return tuple(modules)
    participating = (*grit_modules, *panache_modules)
    resources = [resource for module in participating for resource in module.resources]
    if not any(resource.key == "grit" for resource in resources) or not any(
        resource.key == "panache" for resource in resources
    ):
        return tuple(modules)
    anchor = min(participating, key=lambda module: module.class_level_id)
    state = saved.get((anchor.class_level_id, "grit_panache")) or ClassFeatureState(
        character_id, anchor.class_level_id, "grit_panache"
    )
    automatic_maximum = sum(resource.maximum for resource in resources)
    maximum = (
        state.maximum_override
        if state.maximum_override is not None
        else automatic_maximum + state.maximum_adjustment
    )
    maximum = max(0, int(maximum))
    recovery_value = min(maximum, sum(resource.recovery_value for resource in resources))
    current = recovery_value if state.current_value is None else max(0, state.current_value)
    shared = ResolvedClassFeatureResource(
        class_level_id=anchor.class_level_id,
        class_name="Gunslinger / Swashbuckler",
        key="grit_panache",
        name="Grit & Panache",
        description=(
            "Grit and Panache are two paths into one shared heroic pool. Their "
            "daily starting values and maximums are combined; either kind of deed "
            "can spend or restore the shared points."
        ),
        maximum=maximum,
        current=current,
        active=False,
        choices=(),
        choice_options=(),
        maximum_choices=0,
        state=state,
        recovery_value=recovery_value,
    )
    combined = ResolvedClassFeatureModule(
        key="heroic_pool",
        title="Grit & Panache",
        class_level_id=anchor.class_level_id,
        class_name="Gunslinger / Swashbuckler",
        class_level=sum(module.class_level for module in participating),
        governing_ability="Wisdom + Charisma",
        feature_tokens=frozenset().union(
            *(module.feature_tokens for module in participating)
        ),
        resources=(shared,),
    )
    result: list[ResolvedClassFeatureModule] = []
    inserted = False
    participating_ids = {id(module) for module in participating}
    for module in modules:
        if id(module) in participating_ids:
            if not inserted:
                result.append(combined)
                inserted = True
            continue
        result.append(module)
    return tuple(result)


def resolve_class_feature_modules(
    repository,
    character_id: int,
    ability_modifiers: Mapping[str, int] | None = None,
) -> tuple[ResolvedClassFeatureModule, ...]:
    """Resolve registered class systems after all archetype exchanges."""

    if ability_modifiers is None:
        scores = repository.get_ability_scores(character_id)
        ability_modifiers = {
            key: (int(value) - 10) // 2 for key, value in scores.items()
        }
    selection_records = repository.list_class_feature_selections(character_id)
    saved = {
        (item.class_level_id, item.feature_key): item
        for item in repository.list_class_feature_states(character_id)
    }
    selected_choices = {
        (
            item.class_level_id,
            str(item.feature_key).removeprefix("class-choice:"),
        ): _decoded_choice_keys(item.option_key)
        for item in selection_records
        if str(item.feature_key).startswith("class-choice:")
    }
    psychic_discipline_abilities = {
        int(class_level_id): str(entry.get("resource_ability") or "")
        for (class_level_id, provider_key), selected in selected_choices.items()
        if provider_key == "psychic-discipline"
        for selected_key in selected
        for entry in DEFAULT_CATALOG.class_choice_entries(
            "psychic_discipline", "Psychic"
        )
        if str(entry.get("key") or "") == selected_key
        and str(entry.get("resource_ability") or "")
    }
    archetype_choice_selections = {
        (item.class_level_id, str(item.feature_key)): _decoded_choice_keys(
            item.option_key
        )
        for item in selection_records
        if str(item.feature_key).startswith("archetype-choice:")
    }
    archetype_keys_by_level = {
        int(class_level_id): frozenset(keys)
        for class_level_id, keys in repository.list_class_archetype_keys(
            character_id
        ).items()
    }
    # Power selections are catalog-driven and independent of this resource
    # registry. Reading them here lets resource upgrades (such as Greater
    # Mutagen) affect one shared tracker without coupling either subsystem.
    from app.class_power_rules import resolve_class_power_sets

    power_names_by_level: dict[int, frozenset[str]] = {}
    selected_power_sets_by_level: dict[int, frozenset[str]] = {}
    for power_set in resolve_class_power_sets(repository, character_id):
        current = set(power_names_by_level.get(power_set.class_level_id, ()))
        current.update(option.name for option in power_set.selected_options)
        power_names_by_level[power_set.class_level_id] = frozenset(current)
        if power_set.selected_options:
            providers = set(
                selected_power_sets_by_level.get(power_set.class_level_id, ())
            )
            providers.add(power_set.key)
            selected_power_sets_by_level[power_set.class_level_id] = frozenset(
                providers
            )
    modules: list[ResolvedClassFeatureModule] = []
    for class_level in repository.list_class_levels(character_id):
        resolved = resolved_class_features_for_level(repository, character_id, class_level)
        tokens = frozenset(feature_token(feature.name) for feature in resolved)
        archetype_keys = archetype_keys_by_level.get(class_level.id, frozenset())
        runtime_overlays = tuple(
            archetype_runtime_package(key) or {} for key in archetype_keys
        )
        tokens = tokens | frozenset(
            feature_token(value)
            for overlay in runtime_overlays
            for value in overlay.get("system_features", ())
            if str(value)
        )
        power_names = power_names_by_level.get(class_level.id, frozenset())
        selected_power_sets = selected_power_sets_by_level.get(
            class_level.id, frozenset()
        )
        target_package = class_package(class_level.preset_key)
        claimed_resource_keys: set[str] = set()
        available_module_definitions = (
            *CLASS_FEATURE_MODULES,
            *_runtime_module_definitions(class_level.preset_key, archetype_keys),
        )
        # A class-owned implementation must claim a shared resource key before
        # a grantable implementation does.  Ninja and Unchained Barbarian, for
        # example, deliberately share the published ``ki_pool`` and ``rage``
        # tokens with Monk and Barbarian while using different governing
        # abilities or live effects.  Preserve registry order within both
        # groups so this remains deterministic for future modules.
        module_definitions = tuple(
            definition
            for definition in available_module_definitions
            if class_level.preset_key in definition.owner_class_keys
        ) + tuple(
            definition
            for definition in available_module_definitions
            if class_level.preset_key not in definition.owner_class_keys
        )
        for module_definition in module_definitions:
            owned_module = class_level.preset_key in module_definition.owner_class_keys
            if not owned_module and not module_definition.grantable:
                continue
            if not owned_module and not any(
                token in tokens
                for definition in module_definition.resources
                for token in definition.feature_tokens
            ):
                continue
            governing_ability = module_definition.governing_ability
            if (
                target_package is not None
                and target_package.governing_ability_choice_provider
            ):
                selected_ability = next(
                    iter(
                        selected_choices.get(
                            (
                                class_level.id,
                                target_package.governing_ability_choice_provider,
                            ),
                            (),
                        )
                    ),
                    "",
                ).rsplit(":", 1)[-1].casefold()
                if selected_ability in ability_modifiers:
                    governing_ability = selected_ability
            if (
                not owned_module
                and target_package is not None
                and target_package.governing_ability
            ):
                governing_ability = target_package.governing_ability
            if module_definition.key == "inquisitor" and "whimsical-worship" in tokens:
                governing_ability = "charisma"
            if module_definition.key == "gunslinger" and any(
                key.endswith(":mysterious-stranger")
                or key.endswith(":buccaneer")
                or key.endswith(":firebrand")
                for key in archetype_keys
            ):
                governing_ability = "charisma"
            if module_definition.key == "swashbuckler" and any(
                key.endswith(":inspired-blade") for key in archetype_keys
            ):
                governing_ability = "charisma + intelligence"
            reviewed_ability = next(
                (
                    str(overlay.get("governing_ability") or "").strip().casefold()
                    for overlay in runtime_overlays
                    if str(overlay.get("governing_ability") or "").strip()
                ),
                "",
            )
            if reviewed_ability:
                governing_ability = reviewed_ability
            ability_choice = next(
                (
                    overlay.get("governing_ability_choice")
                    for overlay in runtime_overlays
                    if isinstance(overlay.get("governing_ability_choice"), Mapping)
                ),
                None,
            )
            if isinstance(ability_choice, Mapping):
                feature_key = str(ability_choice.get("feature_key") or "")
                option_map = ability_choice.get("options")
                selected = archetype_choice_selections.get(
                    (class_level.id, feature_key), frozenset()
                )
                if isinstance(option_map, Mapping):
                    selected_ability = next(
                        (
                            str(option_map[key]).strip().casefold()
                            for key in selected
                            if key in option_map and str(option_map[key]).strip()
                        ),
                        "",
                    )
                    if selected_ability:
                        governing_ability = selected_ability
            module_ability_modifiers = dict(ability_modifiers)
            if (
                not owned_module
                and governing_ability in ability_modifiers
                and module_definition.governing_ability in ability_modifiers
            ):
                module_ability_modifiers[module_definition.governing_ability] = int(
                    ability_modifiers.get(governing_ability, 0)
                )
            resources = _apply_runtime_resource_adjustments(
                _resolve_linked_resource_costs(tuple(
                    view
                    for definition in module_definition.resources
                    if definition.key not in claimed_resource_keys
                    if _resource_choice_requirement_met(
                        definition, class_level.id, selected_choices
                    )
                    if not (
                        module_definition.key == "gutter_rat"
                        and definition.key == "sneak_attack"
                        and "gutter-rat-roguish-adaptation" not in selected_power_sets
                    )
                    if (
                        view := _resource_view(
                            definition,
                            character_id,
                            class_level,
                            module_ability_modifiers,
                            governing_ability,
                            tokens,
                            archetype_keys,
                            power_names,
                            (
                                replace(
                                    saved.get((class_level.id, definition.key))
                                    or ClassFeatureState(
                                        character_id,
                                        class_level.id,
                                        definition.key,
                                    ),
                                    choices_json=json.dumps([
                                        psychic_discipline_abilities[class_level.id]
                                    ]),
                                )
                                if definition.key == "phrenic_pool"
                                and class_level.id in psychic_discipline_abilities
                                and not _choices(
                                    saved.get((class_level.id, definition.key))
                                    or ClassFeatureState(
                                        character_id,
                                        class_level.id,
                                        definition.key,
                                    )
                                )
                                else saved.get((class_level.id, definition.key))
                            ),
                        )
                    ) is not None
                )),
                runtime_overlays,
                class_level.level,
                _package_ability_modifier(
                    module_ability_modifiers, governing_ability
                ),
            )
            if not resources and module_definition.key != "inquisitor":
                continue
            claimed_resource_keys.update(resource.key for resource in resources)
            modules.append(
                ResolvedClassFeatureModule(
                    module_definition.key,
                    module_definition.title,
                    class_level.id,
                    class_level.class_name,
                    class_level.level,
                    governing_ability,
                    tokens,
                    resources,
                    domain_available=module_definition.key == "inquisitor" and any(
                        token == "domain" or token.startswith("domain-") for token in tokens
                    ),
                    solo_tactics=module_definition.key == "inquisitor" and "solo-tactics" in tokens,
                    teamwork_feat_slots=(
                        class_level.level // 3
                        if module_definition.key == "inquisitor" and "teamwork-feat" in tokens else 0
                    ),
                )
            )
    modules.extend(_choice_feature_resource_modules(
        repository,
        character_id,
        ability_modifiers,
        saved,
        archetype_keys_by_level,
    ))
    return _combine_grit_and_panache(modules, saved, character_id)


_KNOWLEDGE_SKILL_TARGETS = (
    "skill:knowledge_arcana",
    "skill:knowledge_dungeoneering",
    "skill:knowledge_engineering",
    "skill:knowledge_geography",
    "skill:knowledge_history",
    "skill:knowledge_local",
    "skill:knowledge_nature",
    "skill:knowledge_nobility",
    "skill:knowledge_planes",
    "skill:knowledge_religion",
)
_CREATURE_KNOWLEDGE_SKILL_TARGETS = (
    "skill:knowledge_arcana",
    "skill:knowledge_dungeoneering",
    "skill:knowledge_local",
    "skill:knowledge_nature",
    "skill:knowledge_planes",
    "skill:knowledge_religion",
)


def _package_effect_targets(target_family: str) -> tuple[str, ...]:
    return {
        "knowledge_skills": _KNOWLEDGE_SKILL_TARGETS,
        "creature_knowledge_skills": _CREATURE_KNOWLEDGE_SKILL_TARGETS,
    }.get(target_family, ())


def _package_modifier_map(
    repository,
    character_id: int,
    modules: tuple[ResolvedClassFeatureModule, ...],
) -> dict[str, list[StatModifier]]:
    """Project reviewed passive package effects after archetype replacement."""

    result: dict[str, list[StatModifier]] = {}
    unarmored, unencumbered = _equipment_requirements(
        repository, character_id
    )
    ability_scores = repository.get_ability_scores(character_id)
    ability_modifiers = {
        key: (int(value) - 10) // 2 for key, value in ability_scores.items()
    }
    modules_by_level: dict[int, list[ResolvedClassFeatureModule]] = {}
    for module in modules:
        modules_by_level.setdefault(module.class_level_id, []).append(module)
    for class_level in repository.list_class_levels(character_id):
        package = class_package(class_level.preset_key)
        if package is None:
            continue
        features = resolved_class_features_for_level(
            repository, character_id, class_level
        )
        tokens = frozenset(feature_token(feature.name) for feature in features)
        local_modules = modules_by_level.get(class_level.id, [])
        governing_ability = (
            local_modules[0].governing_ability
            if local_modules else package.governing_ability or "charisma"
        )
        resource_by_key = {
            resource.key: resource
            for module in local_modules
            for resource in module.resources
        }
        archetype_keys = repository.list_class_archetype_keys(
            character_id, class_level.id
        ).get(class_level.id, ())
        runtime_overlays = tuple(
            archetype_runtime_package(key) or {} for key in archetype_keys
        )
        tokens = tokens | frozenset(
            feature_token(value)
            for overlay in runtime_overlays
            for value in overlay.get("system_features", ())
            if str(value)
        )
        runtime_effects = tuple(
            package_effect(raw)
            for overlay in runtime_overlays
            for raw in overlay.get("passive_effects", ())
            if isinstance(raw, Mapping)
        )
        for effect in (*package.passive_effects, *runtime_effects):
            if class_level.level < effect.minimum_level:
                continue
            if not any(
                token in tokens
                or any(
                    re.fullmatch(rf"{re.escape(token)}-\d+(?:d\d+)?(?:-.+)?", owned)
                    for owned in tokens
                )
                for token in effect.feature_tokens
            ):
                continue
            if effect.requires_resource_active and not bool(
                resource_by_key.get(effect.requires_resource_active)
                and resource_by_key[effect.requires_resource_active].active
            ):
                continue
            if effect.requires_resource_choice:
                resource = resource_by_key.get(
                    effect.requires_resource_key or effect.requires_resource_active
                )
                if resource is None or effect.requires_resource_choice.casefold() not in {
                    choice.casefold() for choice in resource.choices
                }:
                    continue
            if effect.requires_unarmored and not unarmored:
                continue
            if effect.requires_unencumbered and not unencumbered:
                continue
            ability = (
                governing_ability if effect.ability == "governing"
                else effect.ability or governing_ability
            )
            value = _package_progression(effect.progression)(
                class_level.level,
                _package_ability_modifier(ability_modifiers, ability),
            )
            if effect.replaces_ability:
                if effect.replacement_cap_progression:
                    value = min(
                        value,
                        _package_progression(
                            effect.replacement_cap_progression
                        )(class_level.level, 0),
                    )
                value -= int(
                    ability_modifiers.get(effect.replaces_ability.casefold(), 0)
                )
                if effect.only_if_better and value <= 0:
                    continue
            if not value:
                continue
            targets = effect.targets + _package_effect_targets(effect.target_family)
            for target in dict.fromkeys(targets):
                result.setdefault(target, []).append(
                    StatModifier(
                        None,
                        target,
                        effect.source,
                        effect.bonus_type,
                        value,
                        True,
                    )
                )
    return result


def class_feature_modifier_map(repository, character_id: int) -> dict[str, list[StatModifier]]:
    """Return safe numeric effects for currently active resolved systems."""

    modules = resolve_class_feature_modules(repository, character_id)
    result = _package_modifier_map(repository, character_id, modules)
    archetype_keys_by_level = {
        int(class_level_id): frozenset(keys)
        for class_level_id, keys in repository.list_class_archetype_keys(
            character_id
        ).items()
    }
    for module in modules:
        level = module.class_level
        judgment = next((item for item in module.resources if item.key == "judgment"), None)
        if judgment is not None and judgment.active:
            selected = {choice.casefold() for choice in judgment.choices}
            every_three = 1 + level // 3
            every_five = 1 + level // 5
            source = "Inquisitor: active Judgment"
            if "destruction" in selected:
                result.setdefault("damage", []).append(
                    StatModifier(None, "damage", f"{source} — Destruction", "sacred", every_three, True)
                )
            if "justice" in selected:
                result.setdefault("attack", []).append(
                    StatModifier(None, "attack", f"{source} — Justice", "sacred", every_five, True)
                )
            if "protection" in selected:
                result.setdefault("armor_class", []).append(
                    StatModifier(None, "armor_class", f"{source} — Protection", "sacred", every_five, True)
                )
            if "purity" in selected:
                for target in ("fortitude", "reflex", "will"):
                    result.setdefault(target, []).append(
                        StatModifier(None, target, f"{source} — Purity", "sacred", every_five, True)
                    )
            if "piercing" in selected:
                result.setdefault("concentration", []).append(
                    StatModifier(None, "concentration", f"{source} — Piercing", "sacred", every_three, True)
                )
        bane = next((item for item in module.resources if item.key == "bane"), None)
        if bane is not None and bane.active:
            for target in ("attack", "damage"):
                result.setdefault(target, []).append(
                    StatModifier(None, target, "Inquisitor: active Bane", "untyped", 2, True)
                )
        mutagen = next((item for item in module.resources if item.key == "mutagen"), None)
        if mutagen is not None and mutagen.active and mutagen.choices:
            selected = tuple(
                value.strip().casefold()
                for value in mutagen.choices[0].split(">")
                if value.strip()
            )
            ability_bonuses = (
                (8, 6, 4) if len(selected) >= 3
                else (6, 4) if len(selected) == 2
                else (4,)
            )
            natural_armor = 6 if len(selected) >= 3 else 4 if len(selected) == 2 else 2
            mental_for = {
                "strength": "intelligence",
                "dexterity": "wisdom",
                "constitution": "charisma",
            }
            for ability, bonus in zip(selected, ability_bonuses):
                if ability not in mental_for:
                    continue
                result.setdefault(ability, []).append(
                    StatModifier(None, ability, "Alchemist: active Mutagen", "alchemical", bonus, True)
                )
                mental = mental_for[ability]
                result.setdefault(mental, []).append(
                    StatModifier(None, mental, "Alchemist: active Mutagen", "untyped", -2, True)
                )
            result.setdefault("armor_class", []).append(
                StatModifier(
                    None, "armor_class", "Alchemist: active Mutagen",
                    "natural armor", natural_armor, True,
                )
            )
        rage = next((item for item in module.resources if item.key == "rage"), None)
        if rage is not None and rage.active:
            if module.key == "barbarian":
                ability_bonus = 8 if level >= 20 else 6 if level >= 11 else 4
                will_bonus = 4 if level >= 20 else 3 if level >= 11 else 2
                rage_profile = next(
                    (
                        dict(overlay.get("rage_profile") or {})
                        for key in archetype_keys_by_level.get(
                            module.class_level_id, frozenset()
                        )
                        for overlay in (archetype_runtime_package(key) or {},)
                        if overlay.get("rage_profile")
                    ),
                    {},
                )
                ability_targets = tuple(
                    str(value).casefold()
                    for value in rage_profile.get(
                        "ability_targets", ("strength", "constitution")
                    )
                )
                rage_source = str(
                    rage_profile.get("source") or "Barbarian: active Rage"
                )
                for target in ability_targets:
                    result.setdefault(target, []).append(
                        StatModifier(
                            None, target, rage_source, "morale",
                            ability_bonus, True,
                        )
                    )
            else:
                will_bonus = 4 if level >= 20 else 3 if level >= 11 else 2
            result.setdefault("will", []).append(
                StatModifier(None, "will", f"{module.class_name}: active Rage", "morale", will_bonus, True)
            )
            result.setdefault("armor_class", []).append(
                StatModifier(None, "armor_class", f"{module.class_name}: active Rage", "untyped", -2, True)
            )
        bloodrage = next(
            (item for item in module.resources if item.key == "bloodrage"), None
        )
        if bloodrage is not None and bloodrage.active:
            level = module.class_level
            ability_bonus = 8 if level >= 20 else 6 if level >= 11 else 4
            will_bonus = 4 if level >= 20 else 3 if level >= 11 else 2
            for target in ("strength", "constitution"):
                result.setdefault(target, []).append(
                    StatModifier(
                        None, target, "Bloodrager: active Bloodrage",
                        "morale", ability_bonus, True,
                    )
                )
            result.setdefault("will", []).append(
                StatModifier(
                    None, "will", "Bloodrager: active Bloodrage",
                    "morale", will_bonus, True,
                )
            )
            result.setdefault("armor_class", []).append(
                StatModifier(
                    None, "armor_class", "Bloodrager: active Bloodrage",
                    "untyped", -2, True,
                )
            )
        performance = next(
            (
                item for item in module.resources
                if item.key in {"bardic_performance", "inspiring_song"}
            ),
            None,
        )
        if performance is not None and performance.active and performance.choices:
            selected_performance = performance.choices[0].casefold()
            if selected_performance == "inspire courage":
                bonus = 1 + (1 if level >= 5 else 0) + (1 if level >= 11 else 0) + (1 if level >= 17 else 0)
                for target in ("attack", "damage"):
                    result.setdefault(target, []).append(
                        StatModifier(
                            None,
                            target,
                            f"{module.class_name}: active Inspire Courage",
                            "competence",
                            bonus,
                            True,
                        )
                    )
            elif selected_performance == "inspire greatness":
                result.setdefault("attack", []).append(
                    StatModifier(
                        None, "attack", f"{module.class_name}: active Inspire Greatness",
                        "competence", 2, True,
                    )
                )
                result.setdefault("fortitude", []).append(
                    StatModifier(
                        None, "fortitude", f"{module.class_name}: active Inspire Greatness",
                        "competence", 1, True,
                    )
                )
            elif selected_performance == "inspire heroics":
                for target in ("armor_class", "touch_ac"):
                    result.setdefault(target, []).append(
                        StatModifier(
                            None, target, f"{module.class_name}: active Inspire Heroics",
                            "dodge", 4, True,
                        )
                    )
                for target in ("fortitude", "reflex", "will"):
                    result.setdefault(target, []).append(
                        StatModifier(
                            None, target, f"{module.class_name}: active Inspire Heroics",
                            "morale", 4, True,
                        )
                    )
        raging_song = next(
            (item for item in module.resources if item.key == "raging_song"), None
        )
        if (
            raging_song is not None
            and raging_song.active
            and any(choice.casefold() == "inspired rage" for choice in raging_song.choices)
        ):
            strength = 6 if level >= 16 else 4 if level >= 8 else 2
            will = 1 + level // 4
            for target in ("strength", "constitution"):
                result.setdefault(target, []).append(
                    StatModifier(None, target, "Skald: active Inspired Rage", "morale", strength, True)
                )
            result.setdefault("will", []).append(
                StatModifier(None, "will", "Skald: active Inspired Rage", "morale", will, True)
            )
            result.setdefault("armor_class", []).append(
                StatModifier(None, "armor_class", "Skald: active Inspired Rage", "untyped", -1, True)
            )
        challenge = next(
            (item for item in module.resources if item.key == "challenge"), None
        )
        if challenge is not None and challenge.active:
            result.setdefault("armor_class", []).append(
                StatModifier(
                    None, "armor_class",
                    f"{module.class_name}: active Challenge (penalty does not apply against its target)",
                    "untyped", -2, True,
                )
            )
        studied_target = next(
            (item for item in module.resources if item.key == "studied_target"), None
        )
        if studied_target is not None and studied_target.active:
            bonus = 1 + level // 5
            source = f"Slayer: Studied Target ({studied_target.choices[0] if studied_target.choices else 'target'})"
            for skill in ("bluff", "knowledge_arcana", "knowledge_dungeoneering", "knowledge_engineering", "knowledge_geography", "knowledge_history", "knowledge_local", "knowledge_nature", "knowledge_nobility", "knowledge_planes", "knowledge_religion", "perception", "sense_motive", "survival"):
                result.setdefault(f"skill:{skill}", []).append(
                    StatModifier(None, f"skill:{skill}", source, "untyped", bonus, True)
                )
        favored = next(
            (item for item in module.resources if item.key == "favored_enemy"), None
        )
        if favored is not None and favored.active:
            bonus = max(2, favored.maximum)
            source = "Ranger: active Favored Enemy"
            for skill in ("bluff", "perception", "sense_motive", "survival"):
                result.setdefault(f"skill:{skill}", []).append(
                    StatModifier(None, f"skill:{skill}", source, "untyped", bonus, True)
                )
        animal_focus = next(
            (item for item in module.resources if item.key == "animal_focus"), None
        )
        if animal_focus is not None and animal_focus.active:
            tier = 6 if level >= 15 else 4 if level >= 8 else 2
            for choice in (value.casefold() for value in animal_focus.choices):
                source = f"Hunter: {choice.title()} Animal Focus"
                if choice in {"bear", "bull", "tiger"}:
                    target = {"bear": "constitution", "bull": "strength", "tiger": "dexterity"}[choice]
                    result.setdefault(target, []).append(
                        StatModifier(None, target, source, "enhancement", tier, True)
                    )
                elif choice == "falcon":
                    result.setdefault("skill:perception", []).append(
                        StatModifier(None, "skill:perception", source, "competence", tier + 2, True)
                    )
                elif choice == "frog":
                    for skill in ("acrobatics", "swim"):
                        result.setdefault(f"skill:{skill}", []).append(
                            StatModifier(None, f"skill:{skill}", source, "competence", tier + 2, True)
                        )
                elif choice == "monkey":
                    result.setdefault("skill:climb", []).append(
                        StatModifier(None, "skill:climb", source, "competence", tier + 2, True)
                    )
                elif choice == "owl":
                    result.setdefault("skill:stealth", []).append(
                        StatModifier(None, "skill:stealth", source, "competence", tier + 2, True)
                    )
                elif choice == "stag":
                    result.setdefault("speed", []).append(
                        StatModifier(
                            None,
                            "speed",
                            source,
                            "enhancement",
                            20 if level >= 15 else 10 if level >= 8 else 5,
                            True,
                        )
                    )
    return result


def class_feature_attack_modifiers(
    repository, character_id: int, attack: Attack
) -> tuple[list[StatModifier], list[StatModifier]]:
    """Return attack-scoped class effects that cannot safely be global."""

    attack_modifiers: list[StatModifier] = []
    damage_modifiers: list[StatModifier] = []
    kind = str(attack.attack_type or "").casefold()
    charisma = (int(repository.get_ability_scores(character_id).get("charisma", 10)) - 10) // 2
    for module in resolve_class_feature_modules(repository, character_id):
        rage = next((item for item in module.resources if item.key == "rage"), None)
        if rage is not None and rage.active and module.key == "barbarian_unchained":
            bonus = 4 if module.class_level >= 20 else 3 if module.class_level >= 11 else 2
            source = "Barbarian (Unchained): active Rage"
            if "melee" in kind:
                attack_modifiers.append(StatModifier(None, "attack", source, "untyped", bonus, True))
                damage_modifiers.append(StatModifier(None, "damage", source, "untyped", bonus, True))
            elif "thrown" in kind:
                damage_modifiers.append(StatModifier(None, "damage", source, "untyped", bonus, True))
        studied = next(
            (item for item in module.resources if item.key == "studied_combat"), None
        )
        if studied is not None and studied.active and "melee" in kind:
            bonus = max(1, module.class_level // 2)
            target = studied.choices[0] if studied.choices else "studied target"
            source = f"Investigator: Studied Combat vs. {target}"
            attack_modifiers.append(
                StatModifier(None, "attack", source, "insight", bonus, True)
            )
            damage_modifiers.append(
                StatModifier(None, "damage", source, "insight", bonus, True)
            )
        smite = next((item for item in module.resources if item.key == "smite"), None)
        if smite is not None and smite.active:
            target = smite.choices[0] if smite.choices else "smite target"
            source = f"{module.class_name}: Smite vs. {target}"
            if charisma:
                attack_modifiers.append(
                    StatModifier(None, "attack", source, "untyped", charisma, True)
                )
            damage_modifiers.append(
                StatModifier(None, "damage", source, "untyped", module.class_level, True)
            )
        challenge = next(
            (item for item in module.resources if item.key == "challenge"), None
        )
        if challenge is not None and challenge.active and "melee" in kind:
            target = challenge.choices[0] if challenge.choices else "challenge target"
            damage_modifiers.append(
                StatModifier(
                    None, "damage", f"{module.class_name}: Challenge vs. {target}",
                    "untyped", module.class_level, True,
                )
            )
        studied_target = next(
            (item for item in module.resources if item.key == "studied_target"), None
        )
        if studied_target is not None and studied_target.active:
            bonus = 1 + module.class_level // 5
            target = studied_target.choices[0] if studied_target.choices else "studied target"
            source = f"Slayer: Studied Target vs. {target}"
            attack_modifiers.append(StatModifier(None, "attack", source, "untyped", bonus, True))
            damage_modifiers.append(StatModifier(None, "damage", source, "untyped", bonus, True))
        favored = next(
            (item for item in module.resources if item.key == "favored_enemy"), None
        )
        if favored is not None and favored.active:
            bonus = max(2, favored.maximum)
            target = ", ".join(favored.choices) or "favored enemy"
            source = f"Ranger: Favored Enemy ({target})"
            attack_modifiers.append(StatModifier(None, "attack", source, "untyped", bonus, True))
            damage_modifiers.append(StatModifier(None, "damage", source, "untyped", bonus, True))
        burn = next((item for item in module.resources if item.key == "burn"), None)
        if (
            burn is not None
            and burn.current > 0
            and "blast" in f"{attack.name} {attack.notes}".casefold()
        ):
            bonus = min(burn.current, module.class_level // 3)
            if bonus:
                attack_modifiers.append(
                    StatModifier(None, "attack", "Kineticist: Elemental Overflow", "untyped", bonus, True)
                )
                damage_modifiers.append(
                    StatModifier(None, "damage", "Kineticist: Elemental Overflow", "untyped", 2 * bonus, True)
                )
        training = next(
            (item for item in module.resources if item.key == "weapon_training"), None
        )
        if training is not None and training.active:
            bonus = max(1, training.maximum)
            group = training.choices[0] if training.choices else "selected group"
            source = (
                "Swashbuckler: Weapon Training"
                if module.key == "swashbuckler"
                else f"Fighter: Weapon Training ({group})"
            )
            attack_modifiers.append(StatModifier(None, "attack", source, "untyped", bonus, True))
            damage_modifiers.append(StatModifier(None, "damage", source, "untyped", bonus, True))
    return attack_modifiers, damage_modifiers


def class_feature_extra_damage(
    repository, character_id: int, attack: Attack | None = None
) -> tuple[ClassExtraDamage, ...]:
    result: list[ClassExtraDamage] = []
    for module in resolve_class_feature_modules(repository, character_id):
        bane = next((item for item in module.resources if item.key == "bane"), None)
        if bane is not None and bane.active:
            dice = "4d6" if "greater-bane" in module.feature_tokens else "2d6"
            target = bane.choices[0] if bane.choices else "selected creature type"
            result.append(ClassExtraDamage(dice, "untyped", f"Inquisitor Bane vs. {target}"))
        studied = next(
            (item for item in module.resources if item.key == "studied_combat"), None
        )
        strike = next(
            (item for item in module.resources if item.key == "studied_strike"), None
        )
        if (
            studied is not None
            and studied.active
            and strike is not None
            and strike.active
            and attack is not None
            and "melee" in str(attack.attack_type or "").casefold()
        ):
            dice_count = min(9, 1 + max(0, module.class_level - 4) // 2)
            target = studied.choices[0] if studied.choices else "studied target"
            result.append(
                ClassExtraDamage(
                    f"{dice_count}d6",
                    "precision",
                    f"Investigator Studied Strike vs. {target}; not multiplied on a critical hit",
                )
            )
        sneak = next(
            (item for item in module.resources if item.key == "sneak_attack"), None
        )
        if sneak is not None and sneak.active:
            if sneak.extra_damage_levels and sneak.extra_damage_die:
                dice_count = sum(
                    module.class_level >= level
                    for level in sneak.extra_damage_levels
                )
            elif module.key == "slayer":
                dice_count = 1 + max(0, module.class_level - 3) // 3
            elif module.key == "gutter_rat":
                dice_count = (
                    1
                    + int(module.class_level >= 7)
                    + int(module.class_level >= 16)
                )
            else:
                dice_count = (module.class_level + 1) // 2
            result.append(
                ClassExtraDamage(
                    f"{dice_count}{sneak.extra_damage_die or 'd6'}",
                    sneak.extra_damage_type or "precision",
                    f"{module.class_name} Sneak Attack; ranged attacks require a target within 30 ft.; not multiplied on a critical hit",
                )
            )
        for resource in module.resources:
            if (
                resource.key == "sneak_attack"
                or not resource.active
                or not resource.extra_damage_levels
                or not resource.extra_damage_die
            ):
                continue
            dice_count = sum(
                module.class_level >= level
                for level in resource.extra_damage_levels
            )
            if dice_count:
                result.append(
                    ClassExtraDamage(
                        f"{dice_count}{resource.extra_damage_die}",
                        resource.extra_damage_type or "untyped",
                        f"{module.class_name}: {resource.name} (conditional)",
                    )
                )
        stare = next(
            (item for item in module.resources if item.key == "hypnotic_stare"), None
        )
        if stare is not None and stare.active:
            dice = module.class_level // 3
            flat = max(1, module.class_level // 2)
            result.append(
                ClassExtraDamage(
                    (f"{dice}d6+{flat}" if dice else str(flat)),
                    "precision",
                    "Mesmerist Painful Stare against the current stare target; once per round and not multiplied on a critical hit",
                )
            )
        hidden = next(
            (item for item in module.resources if item.key == "hidden_strike"), None
        )
        if (
            hidden is not None
            and hidden.active
            and any(choice.casefold() == "stalker" for choice in hidden.choices)
        ):
            dice = 1 + max(0, module.class_level - 1) // 2
            result.append(
                ClassExtraDamage(
                    f"{dice}d8", "precision",
                    "Vigilante Hidden Strike against an unaware/ally/startling-appearance target; use d4s for ordinary flanking or denied Dexterity",
                )
            )
    return tuple(result)


def class_feature_effect_summary(
    resource: ResolvedClassFeatureResource,
    module: ResolvedClassFeatureModule,
) -> str:
    """Concise, live rules text for the shared class-system table."""

    if resource.key == "judgment":
        if not resource.choices:
            return "Choose a judgment type"
        level = module.class_level
        every_three = 1 + level // 3
        every_five = 1 + level // 5
        summaries = {
            "destruction": f"weapon damage +{every_three}",
            "healing": f"fast healing {every_three}",
            "justice": f"attacks +{every_five}",
            "piercing": f"concentration and SR checks +{every_three}",
            "protection": f"AC +{every_five}",
            "purity": f"saves +{every_five}",
            "resiliency": f"DR {every_five}/magic" if level < 10 else f"DR {every_five}/opposed alignment",
            "resistance": f"energy resistance {2 * every_three}",
            "smiting": "weapons bypass magic DR" + (", alignment DR" if level >= 6 else "") + (", and adamantine DR" if level >= 10 else ""),
        }
        return "; ".join(
            f"{choice}: {summaries.get(choice.casefold(), 'see feature rules')}"
            for choice in resource.choices
        )
    if resource.key == "bane":
        target = resource.choices[0] if resource.choices else "Choose creature type"
        dice = "4d6" if "greater-bane" in module.feature_tokens else "2d6"
        return f"{target}: +2 attack/damage and +{dice} damage"
    if resource.key == "discern_lies":
        return "Immediate action; track one round at a time"
    if resource.key == "teamwork_swaps":
        return f"Uses governed by {module.governing_ability.title()} modifier"
    if resource.key == "monster_lore":
        return (
            f"Add {module.governing_ability.title()} modifier to creature-identification "
            "Knowledge checks" + (" (applies)" if resource.active else " (inactive)")
        )
    if resource.key == "track":
        return (
            f"+{max(1, module.class_level // 2)} Survival to follow tracks"
            + (" (applies)" if resource.active else " (inactive)")
        )
    if resource.key == "ki_pool":
        if module.key == "ninja":
            return "Spend ki for an extra full-attack strike, +20 ft. speed, +4 Stealth, or selected ninja tricks"
        return "Spend ki for class and selected ki-power abilities; Full Rest restores the pool"
    if resource.key == "rage":
        level = module.class_level
        if module.key == "barbarian_unchained":
            bonus = 4 if level >= 20 else 3 if level >= 11 else 2
            return (
                f"Active: +{bonus} melee attack/damage, thrown damage, and Will; –2 AC. "
                f"Gain {bonus} temporary HP per Hit Die when rage starts; temporary HP remain manually tracked."
            )
        ability = 8 if level >= 20 else 6 if level >= 11 else 4
        will = 4 if level >= 20 else 3 if level >= 11 else 2
        return f"Active: +{ability} Strength/Constitution, +{will} Will, –2 AC; each round spends one use"
    if resource.key == "bombs":
        dice = (module.class_level + 1) // 2
        return f"{dice}d6 base bomb damage; daily bombs and save DC use Intelligence"
    if resource.key == "mutagen":
        choice = resource.choices[0] if resource.choices else "Choose physical ability"
        tier = "Grand" if choice.count(">") >= 2 else "Greater" if ">" in choice else "Base"
        return f"{tier} mutagen — {choice}" + (" (active)" if resource.active else "")
    if resource.key == "arcane_reservoir":
        return f"Daily fill {resource.recovery_value}; capacity {resource.maximum}"
    if resource.key == "inspiration":
        die = "2d6" if module.class_level >= 20 else "1d6"
        return f"Spend inspiration to add {die}; trained Knowledge, Linguistics, and Spellcraft are normally free"
    if resource.key == "arcane_pool":
        enhancement = min(5, 1 + max(0, module.class_level - 1) // 4)
        return f"Spend 1 point to enhance one held weapon by up to +{enhancement} for 1 minute"
    if resource.key in {"grit", "panache", "grit_panache"}:
        return "Fluctuating heroic pool; deeds spend points and qualifying critical hits or finishing blows restore them"
    if resource.key == "bloodrage":
        level = module.class_level
        ability = 8 if level >= 20 else 6 if level >= 11 else 4
        will = 4 if level >= 20 else 3 if level >= 11 else 2
        return f"Active: +{ability} Strength/Constitution, +{will} Will, –2 AC; each round spends one use"
    if resource.key == "bardic_performance":
        performance = resource.choices[0] if resource.choices else "Choose a performance"
        action = "swift" if module.class_level >= 13 else "move" if module.class_level >= 7 else "standard"
        if performance.casefold() == "inspire courage":
            bonus = 1 + (1 if module.class_level >= 5 else 0) + (1 if module.class_level >= 11 else 0) + (1 if module.class_level >= 17 else 0)
            detail = f"+{bonus} attack and weapon damage; +{bonus} vs. charm and fear"
        elif performance.casefold() == "inspire greatness":
            detail = "+2 attack, +1 Fortitude; bonus Hit Dice and temporary HP remain target-specific"
        elif performance.casefold() == "inspire heroics":
            detail = "+4 dodge AC and +4 morale saves"
        else:
            detail = resource.description
        return f"{performance} · start as {action} action · {detail}"
    if resource.key == "inspiring_song":
        performance = resource.choices[0] if resource.choices else "Choose an inspiring song"
        return f"{performance} · {resource.current}/{resource.maximum} rounds remaining"
    if resource.key == "healers_way":
        return (
            f"{resource.current}/{resource.maximum} uses · "
            f"heal {max(1, module.class_level // 2)}d6 hit points per use"
        )
    if resource.key == "archaeologists_luck":
        bonus = 4 if module.class_level >= 17 else 3 if module.class_level >= 11 else 2 if module.class_level >= 5 else 1
        return (
            f"{resource.current}/{resource.maximum} rounds · +{bonus} luck to attacks, "
            "weapon damage, saves, and skills while active"
        )
    if resource.key == "adaptation":
        simultaneous = (
            3 if module.class_level >= 13
            else 2 if module.class_level >= 5
            else 1
        )
        return f"{resource.current}/{resource.maximum} uses · up to {simultaneous} simultaneous talents"
    if resource.key == "steady_skill":
        skill = resource.choices[0] if resource.choices else "Choose Steady Skill"
        take = 20 if module.class_level >= 19 else 15
        return f"{skill} · expend martial focus to take {take} as though taking 10"
    if resource.key == "smite":
        target = resource.choices[0] if resource.choices else "Choose target"
        return f"{target}: attack + governing Charisma modifier; damage +{module.class_level}" + (
            " (active)" if resource.active else ""
        )
    if resource.key in {"lay_on_hands", "touch_of_corruption"}:
        return f"{(module.class_level + 1) // 2}d6 per use; channeling costs two uses"
    if resource.key == "fervor":
        dice = min(7, 1 + max(0, module.class_level - 2) // 3)
        return f"{dice}d6 per healing/harm use; channeling costs two uses"
    if resource.key == "channel_energy":
        dice = (module.class_level + 1) // 2
        kind = resource.choices[0] if resource.choices else resource.name
        return f"{kind}: {dice}d6 · DC 10 + half class level + Charisma modifier"
    if resource.key == "challenge":
        target = resource.choices[0] if resource.choices else "Choose target"
        return f"{target}: melee damage +{module.class_level}; –2 AC except against the target"
    if resource.key == "wild_shape":
        form = resource.choices[0] if resource.choices else "No current form"
        return ("At will" if resource.maximum >= 99 else f"{resource.current}/{resource.maximum} uses") + f" · {form}"
    if resource.key == "burn":
        per_round = 1 if module.class_level < 6 else 2 if module.class_level < 11 else 3 if module.class_level < 16 else 4
        return f"{resource.current}/{resource.maximum} burn · {resource.current * module.class_level} associated nonlethal damage · limit {per_round}/round"
    if resource.key == "mental_focus":
        return f"{resource.current}/{resource.maximum} unspent focus; daily implement allocations belong in Configure notes"
    if resource.key == "phrenic_pool":
        ability = resource.choices[0] if resource.choices else "higher of Wisdom/Charisma until discipline is selected"
        return f"{resource.current}/{resource.maximum} points · {ability}"
    if resource.key == "sneak_attack":
        dice = (
            sum(module.class_level >= level for level in resource.extra_damage_levels)
            if resource.extra_damage_levels and resource.extra_damage_die
            else
            1 + max(0, module.class_level - 3) // 3
            if module.key == "slayer"
            else 1 + int(module.class_level >= 7) + int(module.class_level >= 16)
            if module.key == "gutter_rat"
            else (module.class_level + 1) // 2
        )
        die = resource.extra_damage_die or "d6"
        return f"{dice}{die} {resource.extra_damage_type or 'precision'} damage" + (" (applies)" if resource.active else " (inactive)")
    if resource.key == "studied_target":
        target = resource.choices[0] if resource.choices else "Choose target"
        return f"{target}: +{1 + module.class_level // 5} attack, damage, relevant skills, and class DCs"
    if resource.key == "favored_enemy":
        targets = ", ".join(resource.choices) or "Choose favored enemies"
        return f"{targets} · current effective bonus +{max(2, resource.maximum)}"
    if resource.key == "raging_song":
        song = resource.choices[0] if resource.choices else "Choose song"
        return f"{song} · {resource.current}/{resource.maximum} rounds" + (" (active)" if resource.active else "")
    if resource.key == "shaman_hexes":
        return ", ".join(resource.choices) or "Record selected hexes"
    if resource.key == "eidolon":
        identity = resource.choices[0] if resource.choices else "Configure eidolon"
        return f"{identity}" + (" (summoned)" if resource.active else " (not summoned)")
    if resource.key == "evolution_pool":
        return f"{resource.maximum} evolution points in the retained eidolon build"
    if resource.key in {"mercies", "cruelties", "phrenic_amplifications", "implements", "favored_terrain", "combat_style"}:
        return ", ".join(resource.choices) or resource.description
    if resource.key == "resolve":
        return f"{resource.current}/{resource.maximum} uses · Determined, Resolute, and Unstoppable"
    if resource.key == "martial_flexibility":
        feats = ", ".join(resource.choices) or "No temporary combat feats selected"
        return f"{resource.current}/{resource.maximum} uses · {feats}"
    if resource.key == "animal_focus":
        aspects = ", ".join(resource.choices) or "Choose current aspect"
        return f"{resource.current}/{resource.maximum} minutes · {aspects}"
    if resource.key == "influence":
        spirit = resource.choices[0] if resource.choices else "Choose spirit"
        return f"{resource.current}/5 influence · {spirit}"
    if resource.key == "hypnotic_stare":
        target = resource.choices[0] if resource.choices else "Choose stare target"
        return f"{target}" + (" · active" if resource.active else " · inactive")
    if resource.key == "mesmerist_tricks":
        trick = ", ".join(resource.choices) or "No implanted trick recorded"
        return f"{resource.current}/{resource.maximum} implants · {trick}"
    if resource.key == "phantom":
        identity = " · ".join(resource.choices) or "Configure phantom and emotional focus"
        return identity + (" · manifested" if resource.active else " · confined")
    if resource.key == "weapon_training":
        if module.key == "swashbuckler":
            return f"+{resource.maximum} attack/damage with qualifying piercing weapons; critical threat expands at 5th level" + (" · applies" if resource.active else "")
        groups = ", ".join(resource.choices) or "No trained weapon group yet"
        return f"Up to +{resource.maximum} attack/damage · {groups}" + (" · applies" if resource.active else "")
    if resource.key == "armor_training":
        speed = "medium and heavy armor retain speed" if module.class_level >= 7 else "medium armor retains speed"
        return f"ACP reduced and maximum Dexterity increased by {resource.maximum}; {speed}"
    if resource.key == "shifter_aspect":
        aspects = ", ".join(resource.choices) or "No current minor aspect"
        return f"{resource.current}/{resource.maximum} minutes · {aspects}"
    if resource.key == "hidden_strike":
        specialization = resource.choices[0] if resource.choices else "Choose Vigilante specialization"
        dice = 1 + max(0, module.class_level - 1) // 2
        return f"{specialization} · {dice}d8 qualifying hidden strike" + (" · applies" if resource.active else "")
    return resource.description


def class_feature_reference_values(
    repository,
    character_id: int,
    ability_modifiers: Mapping[str, int] | None = None,
) -> dict[str, float | bool]:
    """Expose every registered resource through a predictable formula namespace."""

    values: dict[str, float | bool] = {}
    for module in resolve_class_feature_modules(
        repository, character_id, ability_modifiers
    ):
        for resource in module.resources:
            prefix = f"class_feature.{module.key}.{resource.key}"
            values[f"{prefix}.current"] = float(resource.current)
            values[f"{prefix}.maximum"] = float(resource.maximum)
            values[f"{prefix}.active"] = bool(resource.active)
            values[f"{prefix}.recovery"] = float(resource.recovery_value)
            if module.key == "heroic_pool" and resource.key == "grit_panache":
                for alias in (
                    "class_feature.gunslinger.grit",
                    "class_feature.swashbuckler.panache",
                ):
                    values[f"{alias}.current"] = float(resource.current)
                    values[f"{alias}.maximum"] = float(resource.maximum)
                    values[f"{alias}.active"] = False
                    values[f"{alias}.recovery"] = float(resource.recovery_value)
    return values
