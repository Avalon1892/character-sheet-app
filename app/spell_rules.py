from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from collections.abc import Iterable, Mapping

from app.models import Spell


_SPELL_POINT_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


@dataclass(frozen=True, slots=True)
class SpellRecordPresentation:
    """The compact, rules-facing columns used by the play sheet.

    Stored spell data and catalog prose remain unchanged.  Keeping this
    projection outside the widgets lets another sheet type present the same
    rules with a different set of columns later.
    """

    name: str
    cost: str
    action: str
    description: str
    sphere: str
    duration: str
    range: str
    save: str
    spell_resistance: str

    def values(self) -> tuple[str, ...]:
        return (
            self.name,
            self.cost,
            self.action,
            self.description,
            self.sphere,
            self.duration,
            self.range,
            self.save,
            self.spell_resistance,
        )


def normalized_spell_class_name(value: str) -> str:
    """Return a stable key for spell-list and class-catalog names.

    Independent sources punctuate names such as ``Summoner (Unchained)``
    differently.  Keeping that normalization here avoids source-specific rules
    in dialogs and character-sheet code.
    """

    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def spell_level_for_class(entry: Mapping[str, object], class_name: str) -> int | None:
    """Return a catalog spell's level for a class, or ``None`` if unavailable."""

    wanted = normalized_spell_class_name(class_name)
    levels = entry.get("class_levels") or {}
    if not isinstance(levels, Mapping):
        return None
    for source_name, level in levels.items():
        if normalized_spell_class_name(str(source_name)) == wanted:
            try:
                return int(level)
            except (TypeError, ValueError):
                return None
    return None


def sphere_spell_point_costs(
    description: str, base_sphere: bool = False
) -> tuple[int, ...]:
    """Return genuine spell-point modes described by a sphere effect.

    ``base_sphere`` means the description is a granted sphere ability, not
    that it is automatically free.  A paid base effect such as Cure therefore
    reports ``1``, while Teleport reports ``0 / 1`` because its normal use is
    free and its range upgrade costs one point.
    """
    text = " ".join(description.casefold().split())
    costs: set[int] = set()
    if not text or "spell point" not in text:
        return (0,)
    amount_pattern = r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)"
    spend_pattern = re.compile(
        rf"\b(?:spend|expend|pay)\s+(?:up to\s+)?"
        rf"(?:(?P<amount>{amount_pattern})\s+)?"
        rf"(?P<additional>additional\s+)?spell points?\b"
    )
    cost_pattern = re.compile(
        rf"\b(?:costs?|requires?|at (?:an? )?cost of|for)\s+"
        rf"(?:(?P<amount>{amount_pattern})\s+)?"
        rf"(?P<additional>additional\s+)?spell points?\b"
    )
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text)
        if sentence.strip()
    ]
    first_rules_sentence = next(
        (sentence for sentence in sentences if len(sentence.split()) >= 4), ""
    )
    first_sentence_has_cost = False
    base_cost = 0
    for sentence in sentences:
        if "spell point" not in sentence:
            continue
        if any(
            phrase in sentence
            for phrase in (
                "without spending a spell point",
                "without expending a spell point",
                "costs no spell point",
                "cost no spell point",
                "does not cost a spell point",
                "at will",
            )
        ):
            costs.add(0)
        if any(
            phrase in sentence
            for phrase in (
                "reduce the spell point cost",
                "reduces the spell point cost",
                "regain spell points",
                "recover spell points",
                "remaining spell points",
            )
        ):
            continue
        sentence_matches = sorted(
            (*spend_pattern.finditer(sentence), *cost_pattern.finditer(sentence)),
            key=lambda match: match.start(),
        )
        for match in sentence_matches:
            raw = (match.group("amount") or "one").strip()
            amount = int(raw) if raw.isdigit() else _SPELL_POINT_WORDS[raw]
            additional = bool(match.group("additional"))
            if sentence == first_rules_sentence and not additional and not first_sentence_has_cost:
                first_sentence_has_cost = True
                base_cost = amount
            costs.add(base_cost + amount if additional and base_sphere else amount)
        if any(
            re.search(pattern, sentence)
            for pattern in (
                r"instead of (?:spending|expending|paying)",
                r"(?:spend|expend|pay).+spell points?\s+or\s+(?:increase|extend)",
                r"(?:increase|extend).+\s+or\s+(?:spend|expend|pay).+spell points?",
            )
        ):
            costs.add(0)
        if "alternatively" in sentence and sentence_matches:
            costs.add(0)
    if base_sphere and not first_sentence_has_cost:
        costs.add(0)
    return tuple(sorted(costs or {0}))


def sphere_spell_point_cost_display(spell: Spell) -> str:
    if spell.system != "Sphere":
        return "—"
    costs = sphere_spell_point_costs(
        spell.notes,
        base_sphere=spell.catalog_category in {"Base Sphere", "Sphere Ability"},
    )
    return " / ".join(str(cost) for cost in costs)


def _action_display(value: str, description: str) -> str:
    if value.strip():
        return re.sub(r"\s+action\b", "", value.strip(), flags=re.IGNORECASE).title()
    matches = re.findall(
        r"\b(?:as|is|requires?|spend(?:ing)?|perform(?:ed)? as)\s+(?:an?\s+)?"
        r"(immediate|swift|move|standard|full-round|free) action\b",
        description.casefold(),
    )
    ordered = tuple(dict.fromkeys(match.title() for match in matches))
    return " / ".join(ordered) if ordered else "/"


def _range_display(value: str, description: str, owned_names: set[str]) -> str:
    if value.strip():
        return value.strip()
    lower = description.casefold()
    ranges: list[str] = []
    has_touch = bool(re.search(r"\b(?:touch|touched|touching)\b", lower))
    for token in ("close", "medium", "long"):
        if re.search(rf"\b{token} range\b", lower):
            ranges.append(token.title())
    if "distant teleport" in owned_names and "teleport" in lower:
        ranges = ["Long" if value == "Medium" else value for value in ranges]
    if not ranges and has_touch:
        ranges.append("Touch")
    return " / ".join(dict.fromkeys(ranges)) if ranges else "/"


def _duration_display(value: str, description: str) -> str:
    if value.strip():
        return value.strip()
    lower = " ".join(description.split())
    candidates = (
        r"\b(?:lasts?|remain(?:s)?) for ([^. ;]+(?: per caster level)?)",
        r"\bduration of ([^. ;]+(?: per caster level)?)",
        r"\b(?:as long as|while) you concentrate",
    )
    for pattern in candidates:
        match = re.search(pattern, lower, re.IGNORECASE)
        if match is None:
            continue
        if match.lastindex:
            return match.group(1).strip().capitalize()
        return "Concentration"
    return "/"


def _save_display(value: str, description: str) -> str:
    if value.strip():
        return value.strip()
    lower = description.casefold()
    saves = [name for name in ("Fortitude", "Reflex", "Will") if name.casefold() in lower]
    if not saves:
        return "/"
    qualifier = next(
        (word for word in ("negates", "half", "partial") if word in lower), ""
    )
    return " / ".join(saves) + (f" {qualifier}" if qualifier else "")


def _spell_resistance_display(value: str, description: str) -> str:
    if value.strip():
        return value.strip()
    lower = description.casefold()
    if "not subject to spell resistance" in lower:
        return "No"
    if "subject to spell resistance" in lower:
        return "Yes"
    return "/"


def spell_record_presentation(
    spell: Spell, owned_spells: Iterable[Spell] = ()
) -> SpellRecordPresentation:
    """Project a saved spell or sphere effect into the concise play-table row."""

    description = str(getattr(spell, "notes", "") or "")
    name = str(getattr(spell, "name", "") or "")
    system = str(getattr(spell, "system", "") or "")
    owned_names = {
        str(getattr(item, "name", "") or "").casefold()
        for item in owned_spells
        if bool(getattr(item, "enabled", True))
    }
    return SpellRecordPresentation(
        name=name,
        cost=sphere_spell_point_cost_display(spell) if system == "Sphere" else "/",
        action=_action_display(str(getattr(spell, "casting_time", "") or ""), description),
        description=description or "/",
        sphere=str(getattr(spell, "school_or_sphere", "") or system or "/"),
        duration=_duration_display(str(getattr(spell, "duration", "") or ""), description),
        range=_range_display(str(getattr(spell, "range", "") or ""), description, owned_names),
        save=_save_display(str(getattr(spell, "save", "") or ""), description),
        spell_resistance=_spell_resistance_display(
            str(getattr(spell, "spell_resistance", "") or ""), description
        ),
    )
