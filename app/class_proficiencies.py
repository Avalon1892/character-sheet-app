"""Resolve class and archetype proficiency text for Page 0."""
from __future__ import annotations

import re
from typing import Iterable, Mapping

from app.archetype_rules import archetype_choices, selected_archetype_choice_options


_ARMOR = {"lgt": "Light armor", "med": "Medium armor", "hvy": "Heavy armor", "shl": "Shields"}

_PROFICIENCY_HEADINGS = {
    "proficiencies", "class proficiencies", "weapon and armor proficiency",
    "weapon and armor proficiencies", "weapons and armor proficiency",
    "weapon and armor training",
}


def _rules_proficiencies(entry: Mapping[str, object]) -> tuple[list[str], list[str]]:
    """Extract the bounded proficiency paragraph used by older Spheres records.

    Spheres class imports predate the structured proficiency fields.  Reading only
    a named section keeps this compatibility adapter deterministic and avoids
    guessing from unrelated rules prose.
    """

    text = str(entry.get("rules_text") or entry.get("description") or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    paragraph = ""
    for index, line in enumerate(lines):
        heading, separator, inline = line.partition(":")
        normalized_heading = heading.casefold().strip()
        if separator and normalized_heading in _PROFICIENCY_HEADINGS:
            paragraph = inline.strip()
            break
        if normalized_heading in _PROFICIENCY_HEADINGS and index + 1 < len(lines):
            paragraph = lines[index + 1]
            break
    if not paragraph or "proficien" not in paragraph.casefold():
        return [], []

    lower = paragraph.casefold()
    weapons: list[str] = []
    armor: list[str] = []
    if re.search(r"\ball simple weapons\b|\bsimple weapons\b", lower):
        weapons.append("Simple weapons")
    if re.search(r"\ball martial weapons\b|\bmartial weapons\b", lower):
        weapons.append("Martial weapons")
    if "favored weapon" in lower:
        weapons.append("Deity's favored weapon")
    for phrase, label in (
        ("light armor", "Light armor"),
        ("medium armor", "Medium armor"),
        ("heavy armor", "Heavy armor"),
        ("buckler", "Bucklers"),
        ("tower shield", "Tower shields"),
        ("shield", "Shields"),
    ):
        if phrase in lower:
            armor.append(label)
    if "except tower shield" in lower or "excluding tower shield" in lower:
        armor = [value for value in armor if value != "Tower shields"]
        if "Shields" in armor:
            armor[armor.index("Shields")] = "Shields (except tower shields)"
    return list(dict.fromkeys(weapons)), list(dict.fromkeys(armor))


def _apply_change(
    weapons: list[str], armor: list[str], change: Mapping[str, object]
) -> tuple[list[str], list[str]]:
    mode = str(change.get("mode") or "modify").casefold()
    if mode == "replace":
        weapons = [str(value) for value in change.get("weapons", ()) if str(value)]
        armor = [str(value) for value in change.get("armor", ()) if str(value)]
    remove_weapons = {
        str(value).casefold() for value in change.get("remove_weapons", ())
    }
    remove_armor = {
        str(value).casefold() for value in change.get("remove_armor", ())
    }
    weapons = [value for value in weapons if value.casefold() not in remove_weapons]
    armor = [value for value in armor if value.casefold() not in remove_armor]
    weapons.extend(str(value) for value in change.get("add_weapons", ()) if str(value))
    armor.extend(str(value) for value in change.get("add_armor", ()) if str(value))
    return weapons, armor


def resolved_proficiencies(
    class_entry: Mapping[str, object],
    archetypes: Iterable[Mapping[str, object]],
    choice_selections: Mapping[str, Iterable[str]] | None = None,
) -> tuple[str, str]:
    archetypes = tuple(archetypes)
    weapons = [str(value) for value in class_entry.get("weapon_proficiencies", ())]
    armor = [_ARMOR.get(str(value), str(value)) for value in class_entry.get("armor_proficiencies", ())]
    if not weapons and not armor:
        weapons, armor = _rules_proficiencies(class_entry)
    for archetype in archetypes:
        modifications = archetype.get("class_modifications")
        proficiency_change = (
            modifications.get("proficiencies", {})
            if isinstance(modifications, Mapping) else {}
        )
        if isinstance(proficiency_change, Mapping) and proficiency_change:
            weapons, armor = _apply_change(weapons, armor, proficiency_change)
            continue
        text = str(archetype.get("description") or "")
        first = text.split("\n\n", 1)[0]
        if "proficien" in first.casefold() and "not proficient" in first.casefold():
            # Complex partial removals remain visible in the explanatory note.
            armor.append(f"Archetype adjustment: {first}")
    choices = tuple(
        choice for archetype in archetypes for choice in archetype_choices(archetype)
    )
    for option in selected_archetype_choice_options(
        choices, choice_selections or {}
    ):
        declaration = option.class_modifications or {}
        change = declaration.get("proficiencies", {})
        if isinstance(change, Mapping):
            weapons, armor = _apply_change(weapons, armor, change)
    return tuple(dict.fromkeys(weapons)), tuple(dict.fromkeys(armor))
