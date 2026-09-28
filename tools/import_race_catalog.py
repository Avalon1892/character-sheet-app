"""Import every playable first-party PF1e race from Archives of Nethys.

The importer deliberately keeps source acquisition outside the runtime.  It
stores both readable rules text and conservative structured fields used by the
sheet.  Unrecognised prose remains available in the Codex instead of being
guessed into automation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
sys.path.insert(0, str(ROOT / "tools"))

from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore

from catalog_import_common import USER_AGENT, clean_text, slug


INDEX_URLS = (
    ("Core", "https://www.aonprd.com/Races.aspx?Category=Core"),
    ("Other", "https://www.aonprd.com/Races.aspx?Category=NonCore"),
)
CACHE_ROOT = ROOT / ".race-source"
OUTPUT = ROOT / "data" / "pf1e" / "races.json"
ABILITIES = {
    "str": "strength", "strength": "strength",
    "dex": "dexterity", "dexterity": "dexterity",
    "con": "constitution", "constitution": "constitution",
    "int": "intelligence", "intelligence": "intelligence",
    "wis": "wisdom", "wisdom": "wisdom",
    "cha": "charisma", "charisma": "charisma",
}
SKILLS = {
    "acrobatics": "acrobatics", "appraise": "appraise", "bluff": "bluff",
    "climb": "climb", "diplomacy": "diplomacy", "disable device": "disable_device",
    "disguise": "disguise", "escape artist": "escape_artist", "fly": "fly",
    "handle animal": "handle_animal", "heal": "heal", "intimidate": "intimidate",
    "linguistics": "linguistics", "perception": "perception", "ride": "ride",
    "sense motive": "sense_motive", "sleight of hand": "sleight_of_hand",
    "spellcraft": "spellcraft", "stealth": "stealth", "survival": "survival",
    "swim": "swim", "use magic device": "use_magic_device",
    "knowledge (arcana)": "knowledge_arcana",
    "knowledge (dungeoneering)": "knowledge_dungeoneering",
    "knowledge (engineering)": "knowledge_engineering",
    "knowledge (geography)": "knowledge_geography",
    "knowledge (history)": "knowledge_history",
    "knowledge (local)": "knowledge_local",
    "knowledge (nature)": "knowledge_nature",
    "knowledge (nobility)": "knowledge_nobility",
    "knowledge (planes)": "knowledge_planes",
    "knowledge (religion)": "knowledge_religion",
}

ABILITY_OPTIONS = tuple(
    {"key": key, "label": label}
    for key, label in (
        ("strength", "Strength"), ("dexterity", "Dexterity"),
        ("constitution", "Constitution"), ("intelligence", "Intelligence"),
        ("wisdom", "Wisdom"), ("charisma", "Charisma"),
    )
)
FEY_SKILLS = (
    "acrobatics", "bluff", "climb", "diplomacy", "disguise",
    "escape_artist", "fly", "knowledge_nature", "perception", "perform",
    "sense_motive", "sleight_of_hand", "stealth", "swim",
    "use_magic_device",
)
KNOWLEDGE_SKILLS = tuple(key for key in SKILLS.values() if key.startswith("knowledge_"))
SKILL_LABELS = {value: key.title() for key, value in SKILLS.items()}
SKILL_LABELS.update({
    "escape_artist": "Escape Artist", "handle_animal": "Handle Animal",
    "sense_motive": "Sense Motive", "sleight_of_hand": "Sleight of Hand",
    "use_magic_device": "Use Magic Device",
    **{
        key: "Knowledge (" + key.removeprefix("knowledge_").replace("_", " ").title() + ")"
        for key in KNOWLEDGE_SKILLS
    },
})


def choice_option(key: str, label: str, automation: dict | None = None, description: str = "") -> dict:
    result: dict = {"key": key, "label": label}
    if description:
        result["description"] = description
    if automation:
        result["automation"] = automation
    return result


def option_choice(
    key: str,
    label: str,
    options: list[dict] | tuple[dict, ...],
    *,
    minimum: int = 1,
    maximum: int = 1,
    distinct: bool = False,
    kind: str = "options",
) -> dict:
    return {
        "key": key, "label": label, "kind": kind,
        "minimum": minimum, "maximum": maximum, "distinct": distinct,
        "options": list(options),
    }


def skill_options(keys: tuple[str, ...] | list[str], *, class_skill: bool = False, bonus: int = 0) -> list[dict]:
    result: list[dict] = []
    for key in keys:
        automation: dict = {}
        if class_skill:
            automation["class_skills"] = [key]
        if bonus:
            automation["modifiers"] = [{
                "target": f"skill:{key}", "bonus_type": "racial", "value": bonus,
            }]
        result.append(choice_option(key, SKILL_LABELS.get(key, key.replace("_", " ").title()), automation))
    return result


def text(value: object) -> str:
    if isinstance(value, Tag):
        return clean_text(value.get_text(" ", strip=True))
    return clean_text(str(value or ""))


def fetch_page(url: str, cache_path: Path, *, refresh: bool) -> str:
    """Fetch AoN's UTF-8 pages into a reproducible local source cache."""

    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    source = raw.decode("utf-8", errors="replace")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(source, encoding="utf-8")
    return source


def sibling_text(start: Tag, stop_names: set[str]) -> str:
    parts: list[str] = []
    for node in start.next_siblings:
        if isinstance(node, Tag) and node.name in stop_names:
            break
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag):
            parts.append(node.get_text(" ", strip=True))
    return clean_text(" ".join(parts))


def ability_adjustments(value: str) -> tuple[dict[str, int], int]:
    adjustments: dict[str, int] = {}
    for amount, ability in re.findall(
        r"([+\-–−]\d+)\s*(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma|Str|Dex|Con|Int|Wis|Cha)\b",
        value,
        re.I,
    ):
        key = ABILITIES[ability.casefold()]
        adjustments[key] = adjustments.get(key, 0) + int(amount.replace("–", "-").replace("−", "-"))
    flexible = 0
    flexible_match = re.search(
        r"\+(\d+)\s+(?:racial bonus\s+)?to\s+(?:any|one)\s+(?:one\s+)?ability(?: score)?",
        value,
        re.I,
    )
    if flexible_match:
        flexible = int(flexible_match.group(1))
    return adjustments, flexible


def trait_automation(name: str, description: str) -> dict:
    ability_increases: dict[str, int] = {}
    modifiers: list[dict] = []
    conditional_modifiers: list[dict] = []
    class_skills: list[str] = []
    senses: list[dict] = []
    natural_attacks: list[dict] = []
    resistances: list[dict] = []
    lower = description.casefold()
    # Only unconditional skill sentences are automated. Situational bonuses
    # remain readable rules text so the sheet never applies them globally.
    for match in re.finditer(
        r"\+(\d+)\s+racial bonus on ([^. ;]+?) (?:skill )?checks?",
        description,
        re.I,
    ):
        phrase = match.group(2).strip()
        if any(word in phrase.casefold() for word in ("against ", "made ", "to ", "while ", "when ")):
            continue
        amount = int(match.group(1))
        candidates = re.split(r"\s*,\s*|\s+and\s+", phrase)
        for candidate in candidates:
            skill = SKILLS.get(candidate.strip().casefold())
            if skill:
                modifiers.append({"target": f"skill:{skill}", "bonus_type": "racial", "value": amount})
    save_match = re.search(r"\+(\d+)\s+racial bonus on all saving throws\b", description, re.I)
    if save_match:
        for target in ("fortitude", "reflex", "will"):
            modifiers.append({"target": target, "bonus_type": "racial", "value": int(save_match.group(1))})
    initiative_match = re.search(r"\+(\d+)\s+racial bonus on initiative checks\b", description, re.I)
    if initiative_match and not any(word in lower for word in ("during ", "when ", "while ")):
        modifiers.append({"target": "initiative", "bonus_type": "racial", "value": int(initiative_match.group(1))})
    natural_match = re.search(r"\+(\d+)\s+natural armor bonus (?:to|on) (?:their |its |her |his )?(?:armor class|ac)\b", description, re.I)
    if natural_match:
        modifiers.append({"target": "ac", "bonus_type": "natural armor", "value": int(natural_match.group(1))})

    # Direct, unconditional ability and combat-statistic grants are safe to
    # apply. Bonuses limited to a purpose, target, terrain, or circumstance are
    # stored as conditional reminders and never inflated into the baseline.
    for match in re.finditer(
        r"(?:gain|gains|receive|receives|have|has) (?:an? )?additional\s+\+(\d+)\s+"
        r"(?:racial bonus )?to (?:your |their |his |her |its )?"
        r"(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)(?: score)?",
        description, re.I,
    ):
        ability_increases[ABILITIES[match.group(2).casefold()]] = int(match.group(1))
    for amount, save_name in re.findall(
        r"\+(\d+)\s+(?:racial )?bonus on (?:all )?(Fortitude|Reflex|Will) (?:saving throws|saves)(?=[.\s]*$)",
        description, re.I,
    ):
        modifiers.append({
            "target": save_name.casefold(), "bonus_type": "racial", "value": int(amount),
        })
    for target, pattern in (
        ("cmb", r"\+(\d+)\s+(?:racial )?bonus on (?:all )?combat maneuver checks"),
        ("cmd", r"\+(\d+)\s+(?:racial )?bonus to (?:their |his |her |its )?CMD\b"),
    ):
        match = re.search(pattern, description, re.I)
        if match:
            modifiers.append({"target": target, "bonus_type": "racial", "value": int(match.group(1))})

    # Always-class-skill clauses are deterministic. Creation-time choices use
    # option automation and arrive through the same class_skills field.
    for match in re.finditer(
        r"([A-Z][A-Za-z ()]+?(?:\s*,\s*[A-Z][A-Za-z ()]+)*?(?:\s+and\s+[A-Z][A-Za-z ()]+)?)\s+"
        r"(?:are|is) always (?:treated as )?class skills?",
        description,
    ):
        for candidate in re.split(r"\s*,\s*|\s+and\s+", match.group(1)):
            skill = SKILLS.get(candidate.strip().casefold())
            if skill and skill not in class_skills:
                class_skills.append(skill)

    # Senses are normalized once during import. Replacement prose alone does
    # not create a sense: either the trait is the sense or the text must state a
    # positive grant/possession.
    sense_defs = (
        ("darkvision", "Darkvision"), ("low_light_vision", "Low-Light Vision"),
        ("blindsense", "Blindsense"), ("blindsight", "Blindsight"),
        ("tremorsense", "Tremorsense"), ("scent", "Scent"),
        ("see_in_darkness", "See in Darkness"),
    )
    trait_key = name.casefold().replace("-", " ")
    for key, label in sense_defs:
        words = label.casefold().replace("-", "[- ]?")
        positive = re.search(
            rf"(?:gain|gains|possess|possesses|receive|receives) (?:the )?{words}\b",
            description, re.I,
        )
        if name.casefold() in {"senses", "exceptional senses", "exceptional senses (ex)"}:
            positive = positive or re.search(
                rf"(?:have|has) (?:the )?{words}\b", description, re.I,
            )
        if key in {"darkvision", "see_in_darkness"}:
            positive = positive or re.search(
                rf"can see in (?:normal and magical )?darkness.*?(\d+)\s*feet",
                description, re.I,
            )
        if key.replace("_", " ") in trait_key or positive:
            ranges = [int(value) for value in re.findall(
                rf"{words}[^.;]{{0,80}}?(\d+)\s*(?:-| )?feet", description, re.I
            )]
            if key == "darkvision" and not ranges:
                ranges = [int(value) for value in re.findall(
                    r"see in the dark (?:for )?up to (\d+)\s*feet", description, re.I
                )]
            senses.append({"key": key, "name": label, "range": max(ranges, default=0)})

    # Normalize resistance values for formulas and future defensive blocks.
    for energy in ("acid", "cold", "electricity", "fire", "sonic"):
        values: list[int] = []
        for matched_values in re.findall(
            rf"(?:{energy}\s+resistance\s+(\d+)|resistance\s+(\d+)\s+(?:to\s+)?{energy})",
            description, re.I,
        ):
            values.extend(int(value) for value in matched_values if value)
        if values:
            resistances.append({"type": energy, "value": max(values)})

    # Generated natural attacks use only sentences that explicitly grant or
    # describe the character's own attack. References to an enemy's natural
    # attack (for example reactive damage) do not contain a named granted attack
    # and are therefore ignored.
    for sentence in re.split(r"(?<=[.!?])\s+", description):
        if not re.search(r"\b(?:bite|claw|slam|gore|talon|tail slap|hoof|lashvine)\b", sentence, re.I):
            continue
        dice_match = re.search(r"\b(\d+d\d+)\b", sentence, re.I)
        if not dice_match or not re.search(
            r"(?:gain|gains|have|has|possess|possesses|can (?:make|choose to bite)|natural (?:attack|weapon)|act as natural weapons)",
            sentence, re.I,
        ):
            continue
        before_dice = sentence[:dice_match.start()]
        attack_names = list(re.finditer(
            r"(?:(two|2)\s+)?(bite|claw|slam|gore|talon|tail slap|hoof|lashvine)(?: attacks?| weapons?| fingers?)?",
            before_dice, re.I,
        ))
        for attack_match in attack_names[-3:]:
            attack_type = attack_match.group(2).casefold()
            count = 2 if attack_match.group(1) or re.search(
                rf"two\s+{re.escape(attack_type)}", sentence, re.I
            ) else 1
            primary = bool(re.search(r"primary natural attacks?", sentence, re.I))
            secondary = bool(re.search(r"secondary natural attacks?", sentence, re.I))
            natural_attacks.append({
                "key": slug(attack_type),
                "name": attack_type.title(),
                "count": count,
                "damage": dice_match.group(1).lower(),
                "primary": primary or not secondary,
                "damage_types": {
                    "bite": "bludgeoning, piercing, and slashing",
                    "claw": "piercing and slashing", "talon": "piercing and slashing",
                    "slam": "bludgeoning", "gore": "piercing",
                    "tail slap": "bludgeoning", "hoof": "bludgeoning",
                    "lashvine": "slashing",
                }.get(attack_type, "physical"),
                "condition": (
                    "Special use restriction; see trait description."
                    if re.search(r"grapple|helpless|change shape|transfor", sentence, re.I)
                    else ""
                ),
            })
    if not natural_attacks and re.search(
        r"(?:granting|provides?|gain|gains|has|have|natural (?:attack|weapon)|make attacks?)",
        description, re.I,
    ):
        for dice_match in re.finditer(r"\b(\d+d\d+)\b", description, re.I):
            window = description[max(0, dice_match.start() - 260):dice_match.end() + 60]
            attack_names = list(re.finditer(
                r"(?:(two|2|pair of)\s+)?(bite|claw|slam|gore|talon|tail slap|hoof|lashvine)(?: attacks?| weapons?| fingers?)?",
                window, re.I,
            ))
            if not attack_names:
                continue
            for attack_match in attack_names[-3:]:
                attack_type = attack_match.group(2).casefold()
                count = 2 if attack_match.group(1) else 1
                primary = bool(re.search(r"primary natural attacks?", window, re.I))
                secondary = bool(re.search(r"secondary natural attacks?", window, re.I))
                natural_attacks.append({
                    "key": slug(attack_type), "name": attack_type.title(), "count": count,
                    "damage": dice_match.group(1).lower(),
                    "primary": primary or not secondary,
                    "damage_types": {
                        "bite": "bludgeoning, piercing, and slashing",
                        "claw": "piercing and slashing", "talon": "piercing and slashing",
                        "slam": "bludgeoning", "gore": "piercing",
                        "tail slap": "bludgeoning", "hoof": "bludgeoning",
                        "lashvine": "slashing",
                    }.get(attack_type, "physical"),
                    "condition": (
                        "Special use restriction; see trait description."
                        if re.search(r"grapple|helpless|change shape|transfor", window, re.I)
                        else ""
                    ),
                })

    # Keep conditional rules structured but inactive. This is intentionally
    # conservative and provides future condition toggles without corrupting the
    # always-on totals today.
    for match in re.finditer(
        r"\+(\d+)\s+racial bonus on ([^.]+?(?:checks?|saving throws?|attack rolls?|damage rolls?))\s+(against|while|when|to|in)\s+([^.]+)",
        description, re.I,
    ):
        conditional_modifiers.append({
            "value": int(match.group(1)), "bonus_type": "racial",
            "applies_to": clean_text(match.group(2)),
            "condition": clean_text(f"{match.group(3)} {match.group(4)}"),
        })

    result: dict = {}
    if ability_increases:
        result["ability_increases"] = ability_increases
    if modifiers:
        result["modifiers"] = modifiers
    if conditional_modifiers:
        result["conditional_modifiers"] = conditional_modifiers
    if class_skills:
        result["class_skills"] = class_skills
    if senses:
        result["senses"] = list({item["key"]: item for item in senses}.values())
    if natural_attacks:
        unique_attacks: dict[tuple[str, str], dict] = {}
        for attack in natural_attacks:
            unique_attacks.setdefault((attack["key"], attack["damage"]), attack)
        result["natural_attacks"] = list(unique_attacks.values())
    if resistances:
        result["resistances"] = resistances
    return result


def _numbered_variant_options(description: str) -> list[dict]:
    """Extract the reviewed d100 race-variant table into selectable entries."""

    markers = list(re.finditer(r"(?:^|\s)(\d{1,3})\s+(?=[A-Z])", description))
    sequential: list[tuple[int, int, int]] = []
    expected = 1
    for marker in markers:
        number = int(marker.group(1))
        if number != expected:
            continue
        sequential.append((number, marker.end(), marker.start()))
        expected += 1
        if number == 100:
            break
    if len(sequential) < 90:
        return []
    result: list[dict] = []
    for index, (number, start, _marker_start) in enumerate(sequential):
        end = sequential[index + 1][2] if index + 1 < len(sequential) else len(description)
        option_text = clean_text(description[start:end]).rstrip(" .")
        if number == 100:
            # Result 100 instructs the player to roll/select two actual
            # abilities. The chooser therefore permits two selections but does
            # not save a non-ability placeholder as the character's feature.
            continue
        option_automation = trait_automation(f"Variant ability {number}", option_text)
        result.append(choice_option(str(number), f"{number}. {option_text}", option_automation, option_text))
    return result


def alternate_trait_choices(race_name: str, name: str, description: str) -> tuple[list[dict], dict]:
    """Return reviewed structured choices and their rule effects.

    This is deliberately catalog-driven: newly reviewed traits extend this
    registry without adding database columns or UI branches.
    """

    if race_name.casefold() == "human" and name.casefold() == "dual talent":
        return ([option_choice(
            "ability_scores", "Ability scores", list(ABILITY_OPTIONS),
            minimum=2, maximum=2, distinct=True,
        )], {
            "choice_effects": [{
                "choice_key": "ability_scores",
                "target": "$choice",
                "bonus_type": "racial",
                "value": 2,
            }],
        })

    folded_race = race_name.casefold()
    folded_name = name.casefold()
    if folded_name == "fey thoughts":
        return ([option_choice(
            "class_skills", "Class skills",
            skill_options(list(FEY_SKILLS), class_skill=True),
            minimum=2, maximum=2, distinct=True,
        )], {})
    if folded_name == "surface survivalist":
        return ([option_choice("climate", "Adapted climate", [
            choice_option("hot", "Hot climates"),
            choice_option("cold", "Cold climates"),
        ])], {})
    if folded_name == "breath weapon" and folded_race == "dwarf":
        return ([
            option_choice("energy", "Damage type", [
                choice_option(value, value.title()) for value in ("cold", "electricity", "fire")
            ]),
            option_choice("shape", "Shape", [
                choice_option("cone_15", "15-foot cone"),
                choice_option("line_20", "20-foot line"),
            ]),
        ], {})
    if folded_name == "memories beyond death":
        return ([option_choice(
            "knowledge_skills", "Knowledge class skills",
            skill_options(list(KNOWLEDGE_SKILLS), class_skill=True),
            minimum=2, maximum=2, distinct=True,
        )], {})
    if folded_name == "illustrious urbanite":
        return ([option_choice("spell_school", "Spell Focus school", [
            choice_option(value, value.title())
            for value in ("conjuration", "illusion", "transmutation")
        ])], {})
    if folded_name == "dragon soul":
        return ([option_choice("counts_as", "Ancestry counted as", [
            choice_option("elf", "Elf", {"identity_tags": ["elf"]}),
            choice_option("human", "Human", {"identity_tags": ["human"]}),
        ])], {})
    if folded_name == "adoptive parentage":
        return ([{
            "key": "adoptive_race", "label": "Adoptive humanoid race",
            "kind": "text", "minimum": 1, "maximum": 1,
            "placeholder": "Enter a non-human humanoid race",
        }], {})
    if folded_name == "tribalistic":
        return ([{
            "key": "ethnicity", "label": "Ethnicity / tribal language",
            "kind": "text", "minimum": 1, "maximum": 1,
            "placeholder": "Enter the ethnicity and its language",
        }], {})
    if folded_name == "planar envoy":
        return ([option_choice("starting_language", "Planar language", [
            choice_option(value.casefold(), value)
            for value in ("Abyssal", "Aquan", "Auran", "Celestial", "Ignan", "Infernal", "Terran")
        ])], {})
    if folded_name == "eternal smith":
        return ([option_choice("craft_skill", "Craft skill", skill_options([
            "craft_armor", "craft_bows", "craft_weapons",
        ]))], {})
    if folded_name == "ambitious schemer":
        return ([option_choice(
            "class_skill", "Class skill", skill_options(["bluff", "diplomacy"], class_skill=True, bonus=2)
        )], {})
    if folded_name == "natural camouflage":
        terrains = (
            "cold", "desert", "forest", "jungle", "mountain", "plains",
            "swamp", "underground",
        )
        return ([option_choice("terrain", "Favored terrain", [
            choice_option(value, value.title(), {
                "conditional_modifiers": [{
                    "applies_to": "Stealth checks", "condition": f"in {value} terrain",
                    "bonus_type": "racial", "value": 4,
                }]
            }) for value in terrains
        ])], {})
    if folded_name == "wyrmcrowned":
        return ([option_choice(
            "class_skill", "Class skill",
            skill_options(["diplomacy", "intimidate"], class_skill=True, bonus=2),
        )], {})
    if folded_name == "energy strike (su)":
        return ([option_choice("energy", "Energy type", [
            choice_option(value, value.title(), {"resistances": [{"type": value, "value": 5}]})
            for value in ("acid", "cold", "electricity", "fire")
        ])], {})
    if folded_name == "scaled skin":
        return ([option_choice("energy", "Energy resistance", [
            choice_option(value, value.title(), {"resistances": [{"type": value, "value": 5}]})
            for value in ("cold", "electricity", "fire")
        ])], {})
    if folded_name == "maw or claw":
        return ([option_choice("natural_weapon", "Natural weapon", [
            choice_option("bite", "Bite — 1d6", {"natural_attacks": [{
                "key": "bite", "name": "Bite", "count": 1, "damage": "1d6",
                "primary": True, "damage_types": "bludgeoning, piercing, and slashing",
            }]}),
            choice_option("claws", "Two claws — 1d4 each", {"natural_attacks": [{
                "key": "claw", "name": "Claw", "count": 2, "damage": "1d4",
                "primary": True, "damage_types": "piercing and slashing",
            }]}),
        ])], {})
    if folded_name == "experimental body":
        options = []
        for key, label, rules in (
            ("blessed", "Blessed", "Use divine favor once per day as a spell-like ability at character level."),
            ("enchanted", "Enchanted", "Treat Intelligence as 2 higher when determining bonus spells or extracts per day."),
            ("fey_touched", "Fey-Touched", "Use charm animal once per day as a spell-like ability at character level."),
            ("scorched", "Scorched", "Once per day after a successful melee attack, add Wisdom modifier damage as a free action."),
        ):
            options.append(choice_option(key, label, description=rules))
        return ([option_choice("construction", "Experimental construction", options)], {})
    if folded_name == "exotic weapon training" and folded_race == "tengu":
        return ([{
            "key": "eastern_weapons", "label": "Eastern weapon proficiencies",
            "kind": "text_list", "minimum": 3, "maximum": 10, "distinct": True,
            "placeholder": "Enter one weapon per line (3 + Intelligence modifier)",
        }], {})
    if folded_name in {"variant aasimar abilities", "variant tiefling abilities"}:
        options = _numbered_variant_options(description)
        if options:
            return ([option_choice(
                "variant_abilities", "Variant racial ability (choose two only for result 100)", options,
                minimum=1, maximum=2, distinct=True,
            )], {})
    return ([], {})


def base_trait_automation(race_name: str, name: str, description: str) -> dict:
    automation = trait_automation(name, description)
    advancement: list[dict] = []
    if race_name.casefold() == "human" and name.casefold() == "skilled":
        advancement.append({"target": "skill_points_per_level", "value": 1})
    if race_name.casefold() == "human" and name.casefold() == "bonus feat":
        advancement.append({"target": "feat_slots", "value": 1})
    return {**automation, "advancement": advancement} if advancement else automation


def section_after(heading: Tag) -> list[Tag]:
    result: list[Tag] = []
    for node in heading.next_siblings:
        if isinstance(node, Tag) and node.name == "h1":
            break
        if isinstance(node, Tag):
            result.append(node)
    return result


def base_traits(container: Tag, race_name: str) -> list[dict]:
    heading = next(
        (
            tag for tag in container.find_all("h1")
            if "racial traits" in text(tag).casefold()
            and "alternate" not in text(tag).casefold()
        ),
        None,
    )
    if heading is None:
        return []
    result: list[dict] = []
    candidates = heading.find_all("b", recursive=True) or section_after(heading)
    for tag in candidates:
        if tag.name != "b":
            continue
        name = text(tag).strip().rstrip(":")
        if not name or name.casefold() in {"source", "monster entry"}:
            continue
        description = sibling_text(tag, {"b", "h1", "h2", "h3"}).lstrip(": ")
        if not description:
            continue
        result.append({
            "key": f"race-trait:{slug(race_name)}:{slug(name)}",
            "name": name,
            "description": description,
            "automation": base_trait_automation(race_name, name, description),
        })
    return result


def subraces(container: Tag, race_name: str) -> list[dict]:
    heading = next((tag for tag in container.find_all("h1") if text(tag).casefold() == "subraces"), None)
    if heading is None:
        return []
    result: list[dict] = []
    for tag in section_after(heading):
        if tag.name != "h3":
            continue
        name = text(tag)
        description = sibling_text(tag, {"h1", "h2", "h3"})
        adjustments, flexible = ability_adjustments(description)
        skill_names = ""
        match = re.search(r"Alternate Skill Modifiers\s+(.+?)(?:Alternate Spell-Like Ability|$)", description, re.I)
        if match:
            skill_names = clean_text(match.group(1))
        result.append({
            "key": f"race-variant:{slug(race_name)}:{slug(name)}",
            "name": name,
            "description": description,
            "adjustments": adjustments,
            "flexible_bonus": flexible,
            "alternate_skill_modifiers": skill_names,
        })
    return result


def alternate_traits(container: Tag, race_name: str) -> list[dict]:
    heading = next(
        (
            tag for tag in container.find_all("h1")
            if "alternate racial trait" in text(tag).casefold()
        ),
        None,
    )
    if heading is None:
        return []
    result: list[dict] = []
    replacements: list[str] = []
    descendants = heading.find_all(["h2", "b"], recursive=True)
    candidates = descendants if descendants else [
        tag for tag in heading.next_siblings if isinstance(tag, Tag)
    ]
    for tag in candidates:
        if tag is not heading and tag.name == "h1":
            break
        if tag.name == "h2":
            heading_text = text(tag)
            replacements = [part.strip() for part in re.split(r"\s*,\s*|\s+and\s+", re.sub(r"^Replaces\s+", "", heading_text, flags=re.I)) if part.strip()]
            continue
        if tag.name != "b":
            continue
        name = text(tag).strip().rstrip(":")
        if not name or name.casefold() in {"source", "monster entry"} or name.casefold().startswith("source "):
            continue
        source_tag = tag.find_next("b")
        if not isinstance(source_tag, Tag) or text(source_tag).casefold() != "source":
            continue
        description = sibling_text(source_tag, {"b", "h1", "h2", "h3"})
        description = re.sub(r"^Source\s+[^:]+?(?=(?:Some|Many|An?\s|The\s|This\s|Members|Those|While|When|A\s))", "", description, flags=re.I)
        description = clean_text(description)
        if not description or len(description) < 12:
            continue
        choice_specs, choice_automation = alternate_trait_choices(race_name, name, description)
        automation = trait_automation(name, description)
        choice_keys = {str(spec.get("key") or "") for spec in choice_specs}
        if "variant_abilities" in choice_keys:
            # The long d100 table describes mutually exclusive outcomes. Its
            # selected option owns the automation; the table container itself
            # grants none of those one hundred effects.
            automation = {}
        if "natural_weapon" in choice_keys:
            automation.pop("natural_attacks", None)
        if choice_automation:
            automation = {**automation, **choice_automation}
        result.append({
            "key": f"race-alt-trait:{slug(race_name)}:{slug(name)}",
            "name": name,
            "description": description,
            "replaces": list(replacements),
            "choice_specs": choice_specs,
            "automation": automation,
        })
    # AoN occasionally repeats the same bold label while linking sources.
    unique: dict[str, dict] = {}
    for entry in result:
        unique.setdefault(entry["key"], entry)
    resolved = list(unique.values())
    if race_name.casefold() == "human":
        heart_options = [
            choice_option(
                str(entry["key"]), str(entry["name"]),
                dict(entry.get("automation") or {}), str(entry.get("description") or ""),
            )
            for entry in resolved
            if str(entry.get("name") or "").casefold().startswith("heart of ")
        ]
        for entry in resolved:
            if str(entry.get("name") or "").casefold() == "mixed heritage" and heart_options:
                entry["choice_specs"] = [option_choice(
                    "second_heart_trait", "Additional Heart of the… trait", heart_options,
                )]
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    indexed: dict[str, dict] = {}
    for category, url in INDEX_URLS:
        source = fetch_page(url, CACHE_ROOT / f"index-{category.casefold()}.html", refresh=args.refresh)
        soup = BeautifulSoup(source, "html.parser")
        for link in soup.select('a[href*="RacesDisplay.aspx?ItemName="]'):
            name = text(link)
            if not name:
                continue
            indexed.setdefault(name, {"name": name, "category": category})

    entries: list[dict] = []
    for number, item in enumerate(sorted(indexed.values(), key=lambda value: value["name"].casefold()), 1):
        name = item["name"]
        url = f"https://www.aonprd.com/RacesDisplay.aspx?ItemName={quote(name)}"
        source = fetch_page(url, CACHE_ROOT / "pages" / f"{slug(name)}.html", refresh=args.refresh)
        soup = BeautifulSoup(source, "html.parser")
        container = soup.find(id="MainContent_DataListTypes_LabelName_0")
        if not isinstance(container, Tag):
            print(f"WARN: no race content for {name}")
            continue
        traits = base_traits(container, name)
        combined = " ".join(f"{entry['name']} {entry['description']}" for entry in traits)
        adjustments, flexible = ability_adjustments(combined)
        size = "Medium"
        for candidate in ("Fine", "Diminutive", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan", "Colossal"):
            if any(entry["name"].casefold() == candidate.casefold() for entry in traits):
                size = candidate
                break
        speed_match = re.search(r"base (?:land )?speed (?:of|is)\s*(\d+)\s*feet", combined, re.I)
        base_speed = int(speed_match.group(1)) if speed_match else (20 if size == "Small" else 30)
        movement_speeds: dict[str, int] = {}
        for mode in ("fly", "swim", "climb", "burrow"):
            matches = re.findall(
                rf"(?:base\s+)?{mode}\s+speed\s+(?:of\s+|is\s+)?(\d+)\s*feet",
                combined,
                re.I,
            )
            if matches:
                movement_speeds[f"{mode}_speed"] = max(int(value) for value in matches)
        first_heading = next((tag for tag in container.find_all("h1") if "racial traits" in text(tag).casefold()), None)
        description_parts: list[str] = []
        if first_heading is not None:
            for node in first_heading.previous_siblings:
                if isinstance(node, (NavigableString, Tag)):
                    description_parts.append(text(node))
            description_parts.reverse()
        description = clean_text(" ".join(description_parts))
        source_names = [text(tag) for tag in container.find_all("i", limit=4) if text(tag)]
        entries.append({
            "key": slug(name), "name": name, "category": item["category"],
            "size": size, "base_speed": base_speed,
            "movement_speeds": movement_speeds,
            "adjustments": adjustments, "flexible_bonus": flexible,
            "description": description, "racial_traits": traits,
            "variants": subraces(container, name),
            "alternate_racial_traits": alternate_traits(container, name),
            "rules_text": text(container),
            "source": ", ".join(dict.fromkeys(source_names)) or "Pathfinder RPG",
            "source_url": url,
        })
        print(f"[{number:02d}/{len(indexed)}] {name}: {len(traits)} traits")
    entries.sort(key=lambda entry: (0 if entry["category"] == "Core" else 1, entry["name"].casefold()))
    # Duergar's Dwarf Traits deliberately reaches into another race's alternate
    # trait catalog. Resolve that cross-race option only after every entry has
    # been imported so the runtime remains data-driven.
    dwarf = next((entry for entry in entries if entry["key"] == "dwarf"), None)
    duergar = next((entry for entry in entries if entry["key"] == "duergar"), None)
    if dwarf and duergar:
        eligible = [
            trait for trait in dwarf.get("alternate_racial_traits", ())
            if any(
                replacement.casefold() in {"stability", "hardy"}
                for replacement in trait.get("replaces", ())
            )
        ]
        for trait in duergar.get("alternate_racial_traits", ()):
            if trait.get("name", "").casefold() != "dwarf traits":
                continue
            trait["choice_specs"] = [option_choice(
                "dwarf_trait", "Dwarf alternate racial trait",
                [
                    choice_option(
                        str(option["key"]), str(option["name"]),
                        dict(option.get("automation") or {}),
                        str(option.get("description") or ""),
                    )
                    for option in eligible
                ],
            )]
    OUTPUT.write_text(json.dumps({
        "version": 2,
        "source": "Archives of Nethys Pathfinder 1e",
        "source_url": "https://www.aonprd.com/Races.aspx",
        "entries": entries,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(entries)} races to {OUTPUT}")


if __name__ == "__main__":
    main()
