"""Honest, data-driven automation coverage for classes and archetypes.

The rules catalogs document thousands of options.  Documentation is not the
same thing as runtime automation, so this module records both independently.
It deliberately has no Qt or database dependency: import tools, tests, Codex
diagnostics, and future developer UI can all consume the same report.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Iterable, Mapping, Sequence

from app.class_packages import archetype_runtime_package

from app.class_feature_rules import feature_token
from app.class_proficiencies import resolved_proficiencies


AUTOMATED = "automated"
PARTIAL = "partial"
DOCUMENTED = "documented"
MISSING = "missing"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class MechanicPattern:
    key: str
    label: str
    patterns: tuple[str, ...]


# This vocabulary identifies mechanics that normally require mutable state,
# choices, calculations, or a dedicated play surface.  Adding a new recurring
# mechanic here improves the audit without changing any sheet code.
INTERACTIVE_MECHANICS: tuple[MechanicPattern, ...] = (
    MechanicPattern("rage", "Rage", (r"\brage\b", r"\bbloodrage\b", r"raging song")),
    MechanicPattern("rage_power", "Rage Powers", (r"rage powers?",)),
    MechanicPattern("ki_pool", "Ki Pool", (r"\bki pool\b",)),
    MechanicPattern("ki_power", "Ki Powers", (r"ki powers?",)),
    MechanicPattern("arcane_pool", "Arcane Pool", (r"\barcane pool\b",)),
    MechanicPattern("arcane_reservoir", "Arcane Reservoir", (r"\barcane reservoir\b",)),
    MechanicPattern("grit_panache_luck", "Grit / Panache / Luck", (r"\bgrit\b", r"\bpanache\b", r"\bluck pool\b")),
    MechanicPattern("inspiration", "Inspiration", (r"\binspiration\b",)),
    MechanicPattern("mental_focus", "Mental Focus", (r"\bmental focus\b",)),
    MechanicPattern("phrenic_pool", "Phrenic Pool", (r"\bphrenic pool\b",)),
    MechanicPattern("burn", "Burn", (r"\bburn\b",)),
    MechanicPattern("bardic_performance", "Bardic Performance", (r"bardic performance",)),
    MechanicPattern("channel_energy", "Channel Energy", (r"channel energy",)),
    MechanicPattern("lay_on_hands", "Lay on Hands", (r"lay on hands",)),
    MechanicPattern("smite", "Smite", (r"\bsmite(?: evil| good)?\b",)),
    MechanicPattern("wild_shape", "Wild Shape", (r"wild shape",)),
    MechanicPattern("bombs", "Bombs", (r"\bbombs?\b",)),
    MechanicPattern("mutagen", "Mutagen", (r"\bmutagen\b",)),
    MechanicPattern("sneak_attack", "Sneak Attack", (r"sneak attack",)),
    MechanicPattern("studied_target", "Studied Target", (r"studied target",)),
    MechanicPattern("studied_combat", "Studied Combat / Strike", (r"studied combat", r"studied strike")),
    MechanicPattern("favored_enemy", "Favored Enemy", (r"favored enemy",)),
    MechanicPattern("challenge", "Challenge", (r"\bchallenge\b",)),
    MechanicPattern("domain", "Domain / Inquisition", (r"\bdomains?\b", r"\binquisitions?\b")),
    MechanicPattern("bloodline", "Bloodline", (r"\bbloodline\b",)),
    MechanicPattern("mystery", "Mystery", (r"\bmystery\b",)),
    MechanicPattern("revelation", "Revelations", (r"\brevelations?\b",)),
    MechanicPattern("hex", "Hexes", (r"\bhex(?:es)?\b",)),
    MechanicPattern("rogue_talent", "Rogue Talents", (r"\brogue talents?\b",)),
    MechanicPattern("slayer_talent", "Slayer Talents", (r"\bslayer talents?\b",)),
    MechanicPattern("alchemist_discovery", "Alchemist Discoveries", (r"\bdiscover(?:y|ies)\b",)),
    MechanicPattern("investigator_talent", "Investigator Talents", (r"\binvestigator talents?\b",)),
    MechanicPattern("magus_arcana", "Magus Arcana", (r"\bmagus arcana\b",)),
    MechanicPattern("arcanist_exploit", "Arcanist Exploits", (r"\barcanist exploits?\b",)),
    MechanicPattern("ninja_trick", "Ninja Tricks", (r"\bninja tricks?\b",)),
    MechanicPattern("school", "Arcane School", (r"arcane school", r"school powers?")),
    MechanicPattern("bond", "Bond", (r"arcane bond", r"divine bond", r"hunter.?s bond")),
    MechanicPattern("judgment", "Judgment", (r"\bjudg(?:e)?ment\b",)),
    MechanicPattern("bane", "Bane", (r"\bbane\b",)),
    MechanicPattern("animal_companion", "Animal Companion", (r"animal companion",)),
    MechanicPattern("eidolon", "Eidolon", (r"\beidolon\b",)),
    MechanicPattern("familiar", "Familiar", (r"\bfamiliar\b",)),
    MechanicPattern("martial_flexibility", "Martial Flexibility", (r"martial flexibility",)),
    MechanicPattern("resolve", "Resolve", (r"\bgreater resolve\b", r"\btrue resolve\b", r"^resolve$")),
    MechanicPattern("animal_focus", "Animal Focus", (r"animal focus",)),
    MechanicPattern("weapon_training", "Weapon Training", (r"weapon training",)),
    MechanicPattern("armor_training", "Armor Training", (r"armor training",)),
    MechanicPattern("blessing", "Blessings", (r"\bblessings?\b",)),
    MechanicPattern("fervor", "Fervor", (r"\bfervor\b",)),
    MechanicPattern("spirit_influence", "Spirit Influence", (r"spirit surge", r"spirit bonus")),
    MechanicPattern("hypnotic_stare", "Hypnotic Stare", (r"hypnotic stare",)),
    MechanicPattern("mesmerist_trick", "Mesmerist Tricks", (r"mesmerist tricks?",)),
    MechanicPattern("phantom", "Phantom", (r"\bphantom\b",)),
    MechanicPattern("shifter_aspect", "Shifter Aspects", (r"shifter aspect",)),
    MechanicPattern("phrenic_amplification", "Phrenic Amplifications", (r"phrenic amplifications?",)),
    MechanicPattern("focus_power", "Focus Powers", (r"focus powers?",)),
    MechanicPattern("implements", "Implements", (r"\bimplements?\b",)),
    MechanicPattern("favored_terrain", "Favored Terrain", (r"favored terrain",)),
    MechanicPattern("combat_style", "Combat Style", (r"combat style feat",)),
    MechanicPattern("vigilante_talent", "Vigilante Talents", (r"vigilante talents?",)),
    MechanicPattern("vigilante_social_talent", "Vigilante Social Talents", (r"social talents?",)),
    MechanicPattern("mercy", "Mercies", (r"\bmercies\b", r"\bpaladin mercy\b")),
    MechanicPattern("cruelty", "Cruelties", (r"\bcruelty\b",)),
    MechanicPattern("order", "Orders", (r"\b(?:cavalier|samurai) order\b", r"\border abilities\b")),
    MechanicPattern("elemental_focus", "Elemental Focus", (r"elemental focus", r"expanded element")),
    MechanicPattern("oracle_curse", "Oracle's Curse", (r"oracle.?s curse",)),
    MechanicPattern("witch_patron", "Witch Patron", (r"patron spells",)),
    MechanicPattern("psychic_discipline", "Psychic Discipline", (r"psychic discipline",)),
    MechanicPattern("sequence", "Prodigy Sequence", (r"\bprodigy sequence\b", r"\bimbue sequence\b", r"\bsequence links?\b")),
)


_RUNTIME_POWER_FAMILIES = {
    "rage_power": "rage_power",
    "ki_power": "ki_power",
    "revelation": "revelation",
    "rogue_talent": "rogue_talent",
    "slayer_talent": "slayer_talent",
    "investigator_talent": "investigator_talent",
    "witch_hex": "hex",
    "shaman_hex": "hex",
    "ninja_trick": "ninja_trick",
    "vigilante_social_talent": "vigilante_social_talent",
}

_GRANTABLE_RESOURCE_MECHANICS = frozenset({
    "rage", "ki_pool", "inspiration", "channel_energy", "lay_on_hands",
    "smite", "sneak_attack", "studied_target", "martial_flexibility",
    "animal_focus", "favored_enemy", "favored_terrain", "blessing", "fervor",
    "burn", "mental_focus", "bombs", "grit_panache_luck",
})


def _runtime_mechanics(entry: Mapping[str, object]) -> frozenset[str]:
    overlay = archetype_runtime_package(str(entry.get("key") or "")) or {}
    result: set[str] = set()
    text_parts = [str(value) for value in overlay.get("system_features", ())]
    for module in overlay.get("resource_modules", ()):
        if not isinstance(module, Mapping):
            continue
        for resource in module.get("resources", ()):
            if not isinstance(resource, Mapping):
                continue
            text_parts.extend((
                str(resource.get("key") or ""),
                str(resource.get("name") or ""),
                *(str(value) for value in resource.get("feature_tokens", ())),
            ))
    runtime_text = "\n".join(text_parts).replace("_", " ").replace("-", " ")
    for mechanic in INTERACTIVE_MECHANICS:
        if any(re.search(pattern, runtime_text, re.I) for pattern in mechanic.patterns):
            result.add(mechanic.key)
    for provider in overlay.get("power_providers", ()):
        if isinstance(provider, Mapping):
            family = _RUNTIME_POWER_FAMILIES.get(str(provider.get("family") or ""))
            if family:
                result.add(family)
    # Reviewed packages can suppress vocabulary hits that are not actually a
    # granted subsystem (for example, a domain restriction named "Divine
    # Judgment").  Keep these exceptions declarative and archetype-scoped.
    ignored = {
        str(value)
        for value in overlay.get("audit_ignore_mechanics", ())
        if str(value)
    }
    return frozenset(result - ignored)


@dataclass(frozen=True, slots=True)
class AutomationProvider:
    key: str
    implementation: str
    owner_class_keys: frozenset[str] = frozenset()

    def supports(self, entry: Mapping[str, object]) -> bool:
        if not self.owner_class_keys:
            return True
        owner = str(entry.get("class_key") or entry.get("key") or "")
        if owner in self.owner_class_keys:
            return True
        if not str(entry.get("class_key") or ""):
            return False
        return self.key in _runtime_mechanics(entry) or self.key in _GRANTABLE_RESOURCE_MECHANICS


# Provider coverage mirrors code that is actually wired into calculations,
# state, rest, formulas, and/or dedicated UI. Choice providers remain scoped to
# the classes whose retained features actually create the corresponding slot.
AUTOMATED_MECHANIC_PROVIDERS: Mapping[str, AutomationProvider] = {
    "rage": AutomationProvider(
        "rage", "class_feature_systems:barbarian", frozenset({
            "pathfinder-class:barbarian", "pathfinder-class:barbarian-unchained",
            "pathfinder-class:bloodrager", "pathfinder-class:skald",
        })
    ),
    "rage_power": AutomationProvider(
        "rage_power", "class_power_rules:rage-powers", frozenset({
            "pathfinder-class:barbarian", "pathfinder-class:barbarian-unchained",
            "pathfinder-class:skald",
        })
    ),
    "ki_pool": AutomationProvider(
        "ki_pool", "class_feature_systems:monk", frozenset({
            "pathfinder-class:monk", "pathfinder-class:monk-unchained",
            "pathfinder-class:ninja", "spheres-class:sage",
        })
    ),
    "arcane_pool": AutomationProvider(
        "arcane_pool", "class_feature_systems:magus",
        frozenset({"pathfinder-class:magus"}),
    ),
    "arcane_reservoir": AutomationProvider(
        "arcane_reservoir", "class_feature_systems:arcanist",
        frozenset({"pathfinder-class:arcanist"}),
    ),
    "grit_panache_luck": AutomationProvider(
        "grit_panache_luck", "class_feature_systems:heroic-pool",
        frozenset({"pathfinder-class:gunslinger", "pathfinder-class:swashbuckler"}),
    ),
    "inspiration": AutomationProvider(
        "inspiration", "class_feature_systems:investigator",
        frozenset({"pathfinder-class:investigator"}),
    ),
    "mental_focus": AutomationProvider(
        "mental_focus", "class_feature_systems:occultist",
        frozenset({"pathfinder-class:occultist"}),
    ),
    "phrenic_pool": AutomationProvider(
        "phrenic_pool", "class_feature_systems:psychic",
        frozenset({"pathfinder-class:psychic"}),
    ),
    "burn": AutomationProvider(
        "burn", "class_feature_systems:kineticist",
        frozenset({"pathfinder-class:kineticist"}),
    ),
    "bardic_performance": AutomationProvider(
        "bardic_performance", "class_feature_systems:bard",
        frozenset({"pathfinder-class:bard"}),
    ),
    "channel_energy": AutomationProvider(
        "channel_energy", "class_feature_systems:channel-energy",
        frozenset({
            "pathfinder-class:antipaladin", "pathfinder-class:cleric",
            "pathfinder-class:paladin", "pathfinder-class:warpriest",
            "spheres-class:soul-weaver", "spheres-class:necros",
        }),
    ),
    "lay_on_hands": AutomationProvider(
        "lay_on_hands", "class_feature_systems:paladin",
        frozenset({"pathfinder-class:paladin"}),
    ),
    "smite": AutomationProvider(
        "smite", "class_feature_systems:smite",
        frozenset({"pathfinder-class:paladin", "pathfinder-class:antipaladin"}),
    ),
    "wild_shape": AutomationProvider(
        "wild_shape", "class_feature_systems:wild-shape",
        frozenset({"pathfinder-class:druid", "pathfinder-class:shifter"}),
    ),
    "sneak_attack": AutomationProvider(
        "sneak_attack", "class_feature_systems:sneak-attack",
        frozenset({
            "pathfinder-class:ninja", "pathfinder-class:rogue",
            "pathfinder-class:rogue-unchained", "pathfinder-class:slayer",
            "spheres-class:fey-adept", "spheres-class:symbiat",
        }),
    ),
    "studied_target": AutomationProvider(
        "studied_target", "class_feature_systems:slayer",
        frozenset({"pathfinder-class:slayer"}),
    ),
    "favored_enemy": AutomationProvider(
        "favored_enemy", "class_feature_systems:ranger",
        frozenset({"pathfinder-class:ranger"}),
    ),
    "challenge": AutomationProvider(
        "challenge", "class_feature_systems:challenge",
        frozenset({
            "pathfinder-class:cavalier", "pathfinder-class:samurai",
            "spheres-class:sentinel",
        }),
    ),
    "studied_combat": AutomationProvider(
        "studied_combat", "class_feature_systems + class_combat_rules:investigator",
        frozenset({"pathfinder-class:investigator"}),
    ),
    "bombs": AutomationProvider(
        "bombs", "class_feature_systems + class_combat_rules:alchemist",
        frozenset({"pathfinder-class:alchemist"}),
    ),
    "mutagen": AutomationProvider(
        "mutagen", "class_feature_systems:alchemist",
        frozenset({"pathfinder-class:alchemist"}),
    ),
    "ki_power": AutomationProvider(
        "ki_power", "class_power_rules:ki-powers", frozenset({
            "pathfinder-class:monk-unchained",
        })
    ),
    "revelation": AutomationProvider(
        "revelation", "class_power_rules:revelations", frozenset({"pathfinder-class:oracle"})
    ),
    "rogue_talent": AutomationProvider(
        "rogue_talent", "class_power_rules:rogue-talents",
        frozenset({"pathfinder-class:rogue", "pathfinder-class:rogue-unchained", "spheres-class:fey-adept"}),
    ),
    "slayer_talent": AutomationProvider(
        "slayer_talent", "class_power_rules:slayer-talents", frozenset({"pathfinder-class:slayer"}),
    ),
    "alchemist_discovery": AutomationProvider(
        "alchemist_discovery", "class_power_rules:alchemist-discoveries", frozenset({"pathfinder-class:alchemist", "spheres-class:thaumaturge"}),
    ),
    "investigator_talent": AutomationProvider(
        "investigator_talent", "class_power_rules:investigator-talents", frozenset({"pathfinder-class:investigator"}),
    ),
    "hex": AutomationProvider(
        "hex", "class_power_rules:witch-hexes + class_feature_systems:shaman",
        frozenset({"pathfinder-class:witch", "pathfinder-class:shaman"}),
    ),
    "magus_arcana": AutomationProvider(
        "magus_arcana", "class_power_rules:magus-arcana", frozenset({"pathfinder-class:magus"}),
    ),
    "arcanist_exploit": AutomationProvider(
        "arcanist_exploit", "class_power_rules:arcanist-exploits", frozenset({"pathfinder-class:arcanist"}),
    ),
    "ninja_trick": AutomationProvider(
        "ninja_trick", "class_power_rules:ninja-tricks", frozenset({"pathfinder-class:ninja"}),
    ),
    "judgment": AutomationProvider(
        "judgment", "class_feature_systems:inquisitor", frozenset({"pathfinder-class:inquisitor"})
    ),
    "bane": AutomationProvider(
        "bane", "class_feature_systems:inquisitor", frozenset({"pathfinder-class:inquisitor"})
    ),
    "domain": AutomationProvider(
        "domain", "class_choice_rules:domain", frozenset({
            "pathfinder-class:cleric", "pathfinder-class:druid",
            "pathfinder-class:inquisitor",
        })
    ),
    "bloodline": AutomationProvider(
        "bloodline", "class_choice_rules:bloodline", frozenset({
            "pathfinder-class:sorcerer", "pathfinder-class:bloodrager",
        })
    ),
    "mystery": AutomationProvider(
        "mystery", "class_choice_rules:mystery", frozenset({"pathfinder-class:oracle"})
    ),
    "school": AutomationProvider(
        "school", "class_choice_rules:arcane-school", frozenset({"pathfinder-class:wizard"})
    ),
    "bond": AutomationProvider(
        "bond", "class_choice_rules:bonds", frozenset({
            "pathfinder-class:druid", "pathfinder-class:paladin",
            "pathfinder-class:ranger", "pathfinder-class:wizard",
        })
    ),
    "animal_companion": AutomationProvider(
        "animal_companion", "animal_companion_rules"
    ),
    "eidolon": AutomationProvider(
        "eidolon", "class_feature_systems:summoner-eidolon",
        frozenset({"pathfinder-class:summoner", "pathfinder-class:summoner-unchained"}),
    ),
    "familiar": AutomationProvider(
        "familiar", "bonded_companion_rules:familiar"
    ),
    "martial_flexibility": AutomationProvider(
        "martial_flexibility", "class_feature_systems:brawler",
        frozenset({"pathfinder-class:brawler"}),
    ),
    "resolve": AutomationProvider(
        "resolve", "class_feature_systems:samurai",
        frozenset({"pathfinder-class:samurai"}),
    ),
    "animal_focus": AutomationProvider(
        "animal_focus", "class_feature_systems:hunter",
        frozenset({"pathfinder-class:hunter"}),
    ),
    "weapon_training": AutomationProvider(
        "weapon_training", "class_feature_systems:fighter-and-swashbuckler",
        frozenset({"pathfinder-class:fighter", "pathfinder-class:swashbuckler", "spheres-class:armorist"}),
    ),
    "armor_training": AutomationProvider(
        "armor_training", "class_feature_systems:shared-armor-training",
        frozenset({"pathfinder-class:fighter", "spheres-class:armorist"}),
    ),
    "blessing": AutomationProvider(
        "blessing", "class_choice_rules:warpriest-blessings + class_feature_systems:warpriest",
        frozenset({"pathfinder-class:warpriest", "spheres-class:soul-weaver"}),
    ),
    "fervor": AutomationProvider(
        "fervor", "class_feature_systems:warpriest",
        frozenset({"pathfinder-class:warpriest"}),
    ),
    "spirit_influence": AutomationProvider(
        "spirit_influence", "class_feature_systems:medium",
        frozenset({"pathfinder-class:medium"}),
    ),
    "hypnotic_stare": AutomationProvider(
        "hypnotic_stare", "class_feature_systems:mesmerist",
        frozenset({"pathfinder-class:mesmerist"}),
    ),
    "mesmerist_trick": AutomationProvider(
        "mesmerist_trick", "class_feature_systems:mesmerist",
        frozenset({"pathfinder-class:mesmerist"}),
    ),
    "phantom": AutomationProvider(
        "phantom", "class_feature_systems:spiritualist",
        frozenset({"pathfinder-class:spiritualist"}),
    ),
    "shifter_aspect": AutomationProvider(
        "shifter_aspect", "class_choice_rules + class_feature_systems:shifter",
        frozenset({"pathfinder-class:shifter"}),
    ),
    "phrenic_amplification": AutomationProvider(
        "phrenic_amplification", "class_feature_systems:psychic",
        frozenset({"pathfinder-class:psychic"}),
    ),
    "focus_power": AutomationProvider(
        "focus_power", "class_power_rules:occultist-focus-powers",
        frozenset({"pathfinder-class:occultist"}),
    ),
    "implements": AutomationProvider(
        "implements", "class_feature_systems:shared-implements",
        frozenset({"pathfinder-class:occultist", "spheres-class:armorist"}),
    ),
    "favored_terrain": AutomationProvider(
        "favored_terrain", "class_feature_systems:ranger",
        frozenset({"pathfinder-class:ranger"}),
    ),
    "combat_style": AutomationProvider(
        "combat_style", "class_feature_systems:ranger",
        frozenset({"pathfinder-class:ranger"}),
    ),
    "vigilante_talent": AutomationProvider(
        "vigilante_talent", "class_power_rules:vigilante-talents",
        frozenset({"pathfinder-class:vigilante"}),
    ),
    "vigilante_social_talent": AutomationProvider(
        "vigilante_social_talent", "class_power_rules:vigilante-social-talents",
        frozenset({"pathfinder-class:vigilante", "spheres-class:mountebank"}),
    ),
    "mercy": AutomationProvider(
        "mercy", "class_feature_systems:paladin",
        frozenset({"pathfinder-class:paladin"}),
    ),
    "cruelty": AutomationProvider(
        "cruelty", "class_feature_systems:antipaladin",
        frozenset({"pathfinder-class:antipaladin"}),
    ),
    "order": AutomationProvider(
        "order", "class_choice_rules:orders",
        frozenset({"pathfinder-class:cavalier", "pathfinder-class:samurai"}),
    ),
    "elemental_focus": AutomationProvider(
        "elemental_focus", "class_choice_rules:kineticist-elements",
        frozenset({"pathfinder-class:kineticist"}),
    ),
    "oracle_curse": AutomationProvider(
        "oracle_curse", "class_choice_rules:oracle-curse",
        frozenset({"pathfinder-class:oracle"}),
    ),
    "witch_patron": AutomationProvider(
        "witch_patron", "class_choice_rules:witch-patron",
        frozenset({"pathfinder-class:witch"}),
    ),
    "psychic_discipline": AutomationProvider(
        "psychic_discipline", "class_choice_rules:psychic-discipline",
        frozenset({"pathfinder-class:psychic"}),
    ),
    "sequence": AutomationProvider(
        "sequence", "prodigy_system", frozenset({"prodigy"})
    ),
}


@dataclass(frozen=True, slots=True)
class CoverageAxis:
    key: str
    status: str
    reason: str


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _text(entry: Mapping[str, object]) -> str:
    parts = [
        str(entry.get("name") or ""),
        str(entry.get("summary") or ""),
        str(entry.get("description") or ""),
        str(entry.get("rules_text") or ""),
    ]
    parts.extend(
        str(feature.get("name") or "")
        for feature in entry.get("features", ())
        if isinstance(feature, Mapping)
    )
    return "\n".join(parts).casefold()


def _class_feature_text(entry: Mapping[str, object]) -> str:
    """Return only the class's actual progression, not its whole wiki page.

    Spheres class pages also embed archetypes, favored-class bonuses, talents,
    and examples.  Scanning all of ``rules_text`` would incorrectly attribute
    those mechanics to the base class itself.
    """

    parts = [str(entry.get("name") or "")]
    # Feature names identify ownership. Descriptions frequently say that an
    # ability protects against, counts as, or replaces some *other* mechanic;
    # scanning them would produce false ownership such as giving Sneak Attack
    # to every class whose Uncanny Dodge text happens to mention it.
    parts.extend(
        str(feature.get("name") or "")
        for feature in entry.get("features", ())
        if isinstance(feature, Mapping)
    )
    return "\n".join(parts).casefold()


def _archetype_feature_text(entry: Mapping[str, object]) -> str:
    """Use owned feature headings rather than incidental rules references."""

    parts = [str(entry.get("name") or "")]
    parts.extend(
        str(feature.get("name") or "")
        for feature in entry.get("features", ())
        if isinstance(feature, Mapping)
    )
    return "\n".join(parts).casefold()


def detected_interactive_mechanics(
    entry: Mapping[str, object], *, class_record: bool = False
) -> tuple[str, ...]:
    text = _class_feature_text(entry) if class_record else _archetype_feature_text(entry)
    detected = {
        mechanic.key
        for mechanic in INTERACTIVE_MECHANICS
        if any(re.search(pattern, text, re.I) for pattern in mechanic.patterns)
    }
    if not class_record:
        detected.update(_runtime_mechanics(entry))
        overlay = archetype_runtime_package(str(entry.get("key") or "")) or {}
        detected.difference_update(
            str(value)
            for value in overlay.get("audit_ignore_mechanics", ())
            if str(value)
        )
    detected.difference_update(
        str(value)
        for value in entry.get("audit_ignore_mechanics", ())
        if str(value)
    )
    return tuple(
        mechanic.key for mechanic in INTERACTIVE_MECHANICS
        if mechanic.key in detected
    )


def _class_statistics(entry: Mapping[str, object]) -> CoverageAxis:
    keys = ("hit_die", "bab", "fort", "reflex", "will", "skill_points")
    present = sum(entry.get(key) not in (None, "") for key in keys)
    if present == len(keys):
        return CoverageAxis("statistics", AUTOMATED, "Hit Die, BAB, saves, and skill points use the shared class profile.")
    if present:
        return CoverageAxis("statistics", PARTIAL, f"{present}/{len(keys)} base statistics are declared.")
    return CoverageAxis("statistics", MISSING, "No structured base statistics are declared.")


def _class_features(entry: Mapping[str, object]) -> CoverageAxis:
    features = tuple(entry.get("features") or ())
    if features:
        described = sum(bool(str(feature.get("description") or "").strip()) for feature in features if isinstance(feature, Mapping))
        status = AUTOMATED if described == len(features) else PARTIAL
        return CoverageAxis("special_abilities", status, f"{len(features)} level features are projected through the shared Special Abilities resolver; {described} have descriptions.")
    return CoverageAxis("special_abilities", MISSING, "No structured class feature progression is available.")


def _class_casting(entry: Mapping[str, object]) -> CoverageAxis:
    casting = _mapping(entry.get("casting"))
    sphere = str(casting.get("sphere_progression") or "").title()
    if sphere in {"High", "Mid", "Low"}:
        return CoverageAxis("casting", AUTOMATED, f"{sphere} sphere casting uses the shared caster-level and spell-point engines.")
    if casting.get("traditional") is False:
        return CoverageAxis("casting", NOT_APPLICABLE, "The catalog explicitly declares no traditional casting.")
    if casting.get("progression") or casting.get("spells"):
        if casting.get("type") in {"prepared", "spontaneous", "hybrid"}:
            return CoverageAxis("casting", AUTOMATED, "Traditional caster level and the prepared/spontaneous spell subsystem use the shared casting profile.")
        return CoverageAxis("casting", PARTIAL, "Casting exists, but its preparation type is not fully classified.")
    return CoverageAxis("casting", NOT_APPLICABLE, "No casting progression is declared for this class.")


def _class_proficiency(entry: Mapping[str, object]) -> CoverageAxis:
    weapons, armor = resolved_proficiencies(entry, ())
    if entry.get("weapon_proficiencies") or entry.get("armor_proficiencies"):
        return CoverageAxis("proficiencies", AUTOMATED, f"Structured proficiencies resolve to {len(weapons)} weapon and {len(armor)} armor groups.")
    if weapons or armor:
        return CoverageAxis("proficiencies", PARTIAL, "Proficiencies are recovered from a bounded rules-text adapter rather than structured catalog data.")
    return CoverageAxis("proficiencies", MISSING, "No reliable structured or bounded proficiency declaration was found.")


def _class_advancement(entry: Mapping[str, object]) -> CoverageAxis:
    casting = _mapping(entry.get("casting"))
    capabilities = {str(value).casefold() for value in entry.get("capabilities", ())}
    sphere = str(casting.get("sphere_progression") or "").title() in {"High", "Mid", "Low"}
    if entry.get("advancement"):
        return CoverageAxis("advancement", AUTOMATED, "A structured advancement declaration feeds the shared budget engine.")
    if str(entry.get("key") or "").startswith("pathfinder-class:"):
        return CoverageAxis(
            "advancement",
            AUTOMATED,
            "General feats, skill points, favored-class awards, ASIs, and traditional spell capacity use the shared advancement engines; recurring class choices are audited separately as class systems.",
        )
    if sphere or capabilities & {"magic", "martial", "skill"}:
        return CoverageAxis("advancement", PARTIAL, "Sphere/talent advancement is inferred from the imported class table or rules text.")
    if casting.get("progression") or casting.get("spells"):
        return CoverageAxis("advancement", PARTIAL, "Spell capacity is automated, but class choices and bonus resources are not comprehensively declared.")
    return CoverageAxis("advancement", PARTIAL, "General feats, skill points, and ASIs are automated; class-specific advancement choices require declarations.")


def _interactive_axis(
    entry: Mapping[str, object],
    *,
    class_record: bool = False,
) -> tuple[CoverageAxis, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    detected = detected_interactive_mechanics(entry, class_record=class_record)
    supported = tuple(
        key
        for key in detected
        if key in AUTOMATED_MECHANIC_PROVIDERS
        and AUTOMATED_MECHANIC_PROVIDERS[key].supports(entry)
    )
    missing = tuple(key for key in detected if key not in supported)
    if missing and supported:
        axis = CoverageAxis("interactive_systems", PARTIAL, f"{len(supported)} detected systems have providers; {len(missing)} still need providers.")
    elif missing:
        axis = CoverageAxis("interactive_systems", MISSING, f"{len(missing)} detected stateful or choice-driven systems do not yet have runtime providers.")
    elif supported:
        axis = CoverageAxis("interactive_systems", AUTOMATED, f"All {len(supported)} detected systems have registered runtime providers.")
    else:
        axis = CoverageAxis("interactive_systems", NOT_APPLICABLE, "No known stateful class-system signature was detected.")
    return axis, detected, supported, missing


def _overall(axes: Sequence[CoverageAxis], review: bool = False) -> str:
    statuses = {axis.status for axis in axes}
    if review:
        return "manual_review"
    if MISSING in statuses:
        return "partially_automated"
    if PARTIAL in statuses:
        return "partially_automated"
    if AUTOMATED in statuses:
        return "fully_automated"
    return "documented_only"


def audit_class(entry: Mapping[str, object]) -> dict:
    interactive, detected, supported, missing = _interactive_axis(
        entry, class_record=True
    )
    axes = (
        _class_statistics(entry),
        _class_features(entry),
        _class_casting(entry),
        _class_proficiency(entry),
        _class_advancement(entry),
        interactive,
    )
    gaps = [axis.reason for axis in axes if axis.status in {MISSING, PARTIAL}]
    return {
        "kind": "class",
        "key": str(entry.get("key") or ""),
        "name": str(entry.get("name") or "Unnamed class"),
        "source_group": str(entry.get("source_group") or ("Spheres" if str(entry.get("key", "")).startswith("spheres-class:") else "Pathfinder")),
        "category": str(entry.get("category") or ""),
        "status": _overall(axes),
        "coverage": [asdict(axis) for axis in axes],
        "detected_interactive_mechanics": list(detected),
        "automated_interactive_mechanics": list(supported),
        "missing_interactive_mechanics": list(missing),
        "gaps": gaps,
        "source_url": str(entry.get("source_url") or ""),
    }


def _archetype_replacements(entry: Mapping[str, object]) -> CoverageAxis:
    replacements = tuple(entry.get("removed_features") or ()) + tuple(
        entry.get("replaces_features") or ()
    )
    raw = str(entry.get("replaces") or "").strip()
    if replacements:
        return CoverageAxis("feature_replacements", AUTOMATED, f"{len(replacements)} structured removed-feature declarations feed the shared resolver.")
    if raw:
        return CoverageAxis("feature_replacements", PARTIAL, "Replacement prose is available and uses the compatibility resolver, but is not normalized into structured feature keys.")
    if re.search(r"\b(?:replaces?|alters?|modifies?)\b", _text(entry), re.I):
        return CoverageAxis("feature_replacements", MISSING, "Rules prose mentions a replacement or alteration without a structured declaration.")
    return CoverageAxis("feature_replacements", NOT_APPLICABLE, "No feature exchange was detected.")


def _archetype_profile(entry: Mapping[str, object]) -> CoverageAxis:
    declared = _mapping(entry.get("class_modifications"))
    text = str(entry.get("description") or "")
    profile_language = bool(re.search(
        r"(?:^|\n)(?:casting|combat training|proficiencies|class skills|hit die)\s*(?::|\n)",
        text,
        re.I,
    ))
    if declared:
        return CoverageAxis("class_profile", AUTOMATED, "Statistics, casting, advancement, capabilities, or proficiencies are layered by the universal class-profile resolver.")
    compatibility = _mapping(entry.get("compatibility"))
    if profile_language and not (
        compatibility.get("requires") or compatibility.get("requires_any")
    ):
        return CoverageAxis("class_profile", MISSING, "The prose appears to change the class profile, but no declarative modification was imported.")
    return CoverageAxis("class_profile", NOT_APPLICABLE, "No whole-class profile change was detected.")


def _archetype_choices(entry: Mapping[str, object]) -> CoverageAxis:
    choices = tuple(entry.get("choices") or ())
    if choices:
        return CoverageAxis("choices", AUTOMATED, f"{len(choices)} reusable required-choice groups are declared and persisted by stable keys.")
    runtime = archetype_runtime_package(str(entry.get("key") or "")) or {}
    runtime_choices = tuple(runtime.get("choice_providers", ()))
    runtime_alterations = tuple(runtime.get("choice_provider_overrides", ())) + tuple(
        runtime.get("choice_option_filters", ())
    )
    resource_choices = tuple(
        resource
        for module in runtime.get("resource_modules", ())
        if isinstance(module, Mapping)
        for resource in module.get("resources", ())
        if isinstance(resource, Mapping)
        and (
            resource.get("choice_options")
            or resource.get("custom_choice_label")
        )
    )
    if runtime_choices or runtime_alterations or resource_choices:
        count = len(runtime_choices) + len(runtime_alterations) + len(resource_choices)
        return CoverageAxis(
            "choices", AUTOMATED,
            f"{count} archetype-aware choice declarations alter or add exact shared choice controls.",
        )
    handling = str(runtime.get("choice_handling") or "").casefold()
    if handling == "automatic":
        return CoverageAxis(
            "choices",
            AUTOMATED,
            str(runtime.get("choice_handling_note") or "The apparent choice is fixed by the archetype and applied automatically."),
        )
    if handling == "transient":
        return CoverageAxis(
            "choices",
            NOT_APPLICABLE,
            str(runtime.get("choice_handling_note") or "The apparent choice is made per use or target and is not persistent character state."),
        )
    # Limit this signal to prominent rule constructions to avoid classifying
    # every incidental target/type choice as a missing archetype-level choice.
    text = _text(entry)
    likely = bool(re.search(
        r"\bat (?:1st|first) level[^.]{0,240}\b(?:must |may )?(?:choose|select)\b|"
        r"\bmust (?:choose|select) (?:one|two|between|from the following)\b",
        text,
        re.I,
    ))
    if likely:
        return CoverageAxis("choices", MISSING, "A prominent player choice is described in prose but has no reusable choice declaration.")
    return CoverageAxis("choices", NOT_APPLICABLE, "No prominent archetype-level choice signature was detected.")


def _archetype_features(entry: Mapping[str, object]) -> CoverageAxis:
    features = tuple(entry.get("features") or ())
    if features:
        return CoverageAxis("granted_features", AUTOMATED, f"{len(features)} structured archetype features feed Special Abilities.")
    if str(entry.get("description") or "").strip():
        return CoverageAxis("granted_features", PARTIAL, "Rules are documented, but granted abilities still depend on paragraph parsing rather than structured feature rows.")
    return CoverageAxis("granted_features", MISSING, "No archetype rules text or structured feature rows are available.")


def _archetype_compatibility(entry: Mapping[str, object]) -> CoverageAxis:
    compatibility = _mapping(entry.get("compatibility"))
    if compatibility:
        return CoverageAxis("compatibility", AUTOMATED, "Structured compatibility metadata drives incompatible-archetype disabling.")
    if entry.get("replaces") or entry.get("removed_features"):
        return CoverageAxis("compatibility", PARTIAL, "Compatibility is inferred from overlapping replacement text rather than explicit structured conflicts.")
    return CoverageAxis("compatibility", MISSING, "No reliable replacement or compatibility declaration is available.")


def audit_archetype(entry: Mapping[str, object]) -> dict:
    interactive, detected, supported, missing = _interactive_axis(entry)
    axes = (
        CoverageAxis("documentation", DOCUMENTED if str(entry.get("description") or "").strip() else MISSING, "Complete imported rules text is present." if str(entry.get("description") or "").strip() else "Rules text is missing."),
        _archetype_replacements(entry),
        _archetype_profile(entry),
        _archetype_choices(entry),
        _archetype_features(entry),
        _archetype_compatibility(entry),
        interactive,
    )
    gaps = [axis.reason for axis in axes if axis.status in {MISSING, PARTIAL}]
    review = any(axis.status == MISSING for axis in axes if axis.key in {"documentation", "class_profile", "choices"})
    return {
        "kind": "archetype",
        "key": str(entry.get("key") or ""),
        "name": str(entry.get("name") or "Unnamed archetype"),
        "class_key": str(entry.get("class_key") or ""),
        "class_name": str(entry.get("class_name") or ""),
        "source_group": str(entry.get("source_group") or ""),
        "status": _overall(axes, review),
        "coverage": [asdict(axis) for axis in axes],
        "detected_interactive_mechanics": list(detected),
        "automated_interactive_mechanics": list(supported),
        "missing_interactive_mechanics": list(missing),
        "gaps": gaps,
        "source_url": str(entry.get("source_url") or ""),
    }


def _summary(records: Iterable[Mapping[str, object]]) -> dict:
    rows = tuple(records)
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)
    sources = Counter(str(row.get("source_group") or "Unknown") for row in rows)
    missing = Counter(
        mechanic
        for row in rows
        for mechanic in row.get("missing_interactive_mechanics", ())
    )
    return {
        "total": len(rows),
        "by_status": dict(sorted(statuses.items())),
        "by_source_group": dict(sorted(sources.items())),
        "most_common_missing_interactive_mechanics": [
            {"key": key, "count": count}
            for key, count in missing.most_common()
        ],
    }


def build_audit(
    classes: Iterable[Mapping[str, object]],
    archetypes: Iterable[Mapping[str, object]],
) -> dict:
    class_rows = sorted((audit_class(entry) for entry in classes), key=lambda row: (row["source_group"], row["name"].casefold()))
    archetype_rows = sorted((audit_archetype(entry) for entry in archetypes), key=lambda row: (row["source_group"], row["class_name"].casefold(), row["name"].casefold()))
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "principle": "Documentation, static projection, calculations, choices, and interactive runtime systems are audited separately.",
            "statuses": [AUTOMATED, PARTIAL, DOCUMENTED, MISSING, NOT_APPLICABLE],
            "provider_registry": {
                key: {
                    "implementation": provider.implementation,
                    "owner_class_keys": sorted(provider.owner_class_keys),
                }
                for key, provider in AUTOMATED_MECHANIC_PROVIDERS.items()
            },
        },
        "summary": {
            "classes": _summary(class_rows),
            "archetypes": _summary(archetype_rows),
        },
        "classes": class_rows,
        "archetypes": archetype_rows,
    }


def markdown_summary(document: Mapping[str, object]) -> str:
    summary = _mapping(document.get("summary"))
    classes = _mapping(summary.get("classes"))
    archetypes = _mapping(summary.get("archetypes"))

    def table(title: str, data: Mapping[str, object]) -> list[str]:
        by_status = _mapping(data.get("by_status"))
        lines = [f"## {title}", "", f"Total: {data.get('total', 0)}", "", "| Status | Count |", "|---|---:|"]
        lines.extend(f"| {key.replace('_', ' ').title()} | {value} |" for key, value in by_status.items())
        return lines

    missing = list(classes.get("most_common_missing_interactive_mechanics") or ()) + list(archetypes.get("most_common_missing_interactive_mechanics") or ())
    combined = Counter()
    for row in missing:
        if isinstance(row, Mapping):
            combined[str(row.get("key"))] += int(row.get("count") or 0)
    lines = [
        "# Class & Archetype Automation Audit",
        "",
        "This report distinguishes rules documentation from actual sheet automation. It is generated from the same bundled catalogs and provider registry used by the application.",
        "",
    ]
    lines.extend(table("Original Classes", classes))
    lines.extend([""])
    lines.extend(table("Archetypes", archetypes))
    lines.extend(["", "## Highest-priority reusable systems", "", "| System | Affected records |", "|---|---:|"])
    lines.extend(f"| {key.replace('_', ' ').title()} | {count} |" for key, count in combined.most_common(20))
    lines.extend([
        "",
        "## How to use this audit",
        "",
        "1. Implement one recurring system as a shared provider.",
        "2. Register that provider once in `app/class_mechanics_audit.py`.",
        "3. Add declarative class or archetype data instead of class-named UI branches.",
        "4. Regenerate the report; every affected record is reclassified automatically.",
        "",
        "The JSON report contains per-entry coverage axes, detected systems, exact gaps, and source links.",
    ])
    return "\n".join(lines)
