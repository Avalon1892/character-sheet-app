from __future__ import annotations

import re
from copy import deepcopy

from app.models import BONUS_TYPES, SKILLS


def _effect(
    target: str,
    value: int = 0,
    bonus_type: str = "untyped",
    formula: str = "",
    scope: str = "",
) -> dict:
    return {
        "target": target,
        "bonus_type": bonus_type,
        "value": value,
        "formula": formula,
        "scope": scope,
    }


def _static(*effects: dict, note: str = "Applied automatically while enabled.") -> dict:
    return {
        "effects": list(effects),
        "choice_type": "",
        "choice_label": "",
        "activation": "always",
        "activation_note": note,
        "default_enabled": True,
    }


def _choice(
    choice_type: str,
    choice_label: str,
    *effects: dict,
    note: str = "Applied automatically to the selected option while enabled.",
) -> dict:
    return {
        "effects": list(effects),
        "choice_type": choice_type,
        "choice_label": choice_label,
        "activation": "always",
        "activation_note": note,
        "default_enabled": True,
    }


def _toggle(*effects: dict, note: str) -> dict:
    return {
        "effects": list(effects),
        "choice_type": "",
        "choice_label": "",
        "activation": "toggle",
        "activation_note": note,
        "default_enabled": False,
    }


_CURATED: dict[str, dict] = {
    "focused mind": _static(
        _effect("concentration", 2, "trait"),
        note="The +2 trait bonus on concentration checks is applied automatically.",
    ),
    "courageous": _toggle(
        _effect("fortitude", 2, "trait"),
        _effect("reflex", 2, "trait"),
        _effect("will", 2, "trait"),
        note="Activate only while resolving a saving throw against a fear effect.",
    ),
    "resilient": _static(
        _effect("fortitude", 1, "trait"),
        note="The +1 trait bonus to Fortitude saves is applied automatically.",
    ),
    "maneuver trained": _static(
        _effect("cmb", 1, "trait"),
        note="The +1 trait bonus to CMB is applied automatically.",
    ),
    "steel body": _static(
        _effect("hp", formula="half_level_round_up"),
        note="Maximum HP scales automatically with total Hit Dice/character level.",
    ),
    "wisdom of the master": _choice(
        "skill",
        "Skill",
        _effect("skill:{choice_key}", 1, "trait"),
        _effect("skill:{choice_key}", formula="class_skill"),
        note="The selected skill becomes a class skill and receives its +1 trait bonus.",
    ),
    "readied blade": _choice(
        "attack",
        "Saved attack",
        _effect("attack", 1, "trait", scope="name:{choice_key}"),
        note="The selected weapon attack receives +1. Weapon-specific combat maneuver checks remain a rules reminder because the sheet does not store CMB by weapon.",
    ),
}


_SKILL_ALIASES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        ((definition.name, definition.key) for definition in SKILLS),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)
_KNOWLEDGE_KEYS = tuple(
    definition.key for definition in SKILLS if definition.key.startswith("knowledge_")
)
_BONUS_TYPES_PATTERN = "|".join(
    re.escape(value) for value in sorted(BONUS_TYPES, key=len, reverse=True)
)
_BONUS_PATTERN = re.compile(
    rf"^(?:benefit:\s*)?(?:you\s+)?(?:gain|get|receive|have)\s+(?:an?\s+)?"
    rf"(?P<value>[+]\d+)\s+(?:(?P<bonus_type>{_BONUS_TYPES_PATTERN})\s+)?"
    rf"bonus\s+(?:on|to)\s+(?P<targets>[^.;]+)",
    re.IGNORECASE,
)
_PENALTY_PATTERN = re.compile(
    rf"^(?:benefit:\s*)?(?:you\s+)?(?:take|suffer|receive|have)\s+(?:an?\s+)?"
    rf"(?P<value>-\d+)\s+(?:(?P<bonus_type>{_BONUS_TYPES_PATTERN})\s+)?"
    rf"penalty\s+(?:on|to)\s+(?P<targets>[^.;]+)",
    re.IGNORECASE,
)
_CONDITIONAL_MARKERS = re.compile(
    r"\b(?:aboard|against|as|because|during|for checks|from|if|in|involving|made|"
    r"inside|outside|related to|to|"
    r"that|when|whenever|while|with|within)\b",
    re.IGNORECASE,
)


def _normalize_rules_text(value: str) -> str:
    normalized = (
        value.replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\xa0", " ")
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _skill_targets(text: str) -> list[str]:
    lower = text.casefold()
    result: list[str] = []
    for alias, key in _SKILL_ALIASES:
        # Rules text conventionally capitalizes skill names. Keeping this check
        # case-sensitive prevents verbs such as "perform" or "craft" from being
        # mistaken for the Perform and Craft skills.
        if alias in text or (
            key.startswith("knowledge_") and alias.casefold() in lower
        ):
            result.append(key)
    if re.search(r"\ball\s+knowledge(?:\s+skill)?\s+checks?\b", lower):
        result.extend(_KNOWLEDGE_KEYS)
    if re.search(r"\ball\s+profession(?:\s+skill)?\s+checks?\b", lower):
        result.append("profession")
    return list(dict.fromkeys(result))


def _ac_targets(bonus_type: str) -> tuple[str, ...]:
    if bonus_type == "dodge":
        return ("ac", "touch_ac")
    if bonus_type in {"armor", "natural armor", "shield"}:
        return ("ac", "flat_footed_ac")
    return ("ac", "touch_ac", "flat_footed_ac")


def _numeric_targets(text: str, bonus_type: str) -> list[str]:
    lower = text.casefold()
    result = [f"skill:{key}" for key in _skill_targets(text)]
    if "initiative" in lower:
        result.append("initiative")
    if "all saving throw" in lower or "all saves" in lower:
        result.extend(("fortitude", "reflex", "will"))
    else:
        if "fortitude" in lower:
            result.append("fortitude")
        if "reflex" in lower:
            result.append("reflex")
        if "will save" in lower or "will saving" in lower:
            result.append("will")
    # Generic inference deliberately stops at skills, initiative, and saves.
    # AC, attacks, damage, CMB/CMD, and HP commonly carry weapon, target, or
    # situation qualifiers; those are automated only by reviewed definitions.
    if re.search(r"\ball\s+skill checks?\b", lower):
        result.append("skills")
    return list(dict.fromkeys(result))


def _class_skill_effects(description: str) -> list[dict]:
    lower = description.casefold()
    effects: list[dict] = []
    for alias, key in _SKILL_ALIASES:
        escaped = re.escape(alias.casefold())
        patterns = (
            rf"{escaped}\s+(?:is|becomes)\s+(?:always\s+)?a\s+class\s+skill\s+for\s+you",
            rf"you\s+(?:gain|treat)\s+{escaped}\s+as\s+(?:always\s+)?a\s+class\s+skill",
            rf"{escaped}\s+is\s+(?:always\s+)?considered\s+a\s+class\s+skill",
        )
        if any(re.search(pattern, lower) for pattern in patterns):
            effects.append(_effect(f"skill:{key}", formula="class_skill"))
    return effects


def _allow_untrained_effects(description: str) -> list[dict]:
    lower = description.casefold()
    effects: list[dict] = []
    for alias, key in _SKILL_ALIASES:
        escaped = re.escape(alias.casefold())
        if re.search(
            rf"(?:make|attempt)\s+{escaped}(?:\s+skill)?\s+checks?\s+untrained",
            lower,
        ):
            effects.append(_effect(f"skill:{key}", formula="allow_untrained"))
    return effects


def _safe_numeric_effects(description: str) -> list[dict]:
    effects: list[dict] = []
    for sentence in re.split(r"(?<=[.!?])\s+", description):
        sentence = sentence.strip()
        if not sentence or re.match(r"^(?:when|whenever|while|if)\b", sentence, re.I):
            continue
        clauses = re.sub(
            r",\s+(?:and|but)\s+(?=(?:you|your|creatures?|targets?|the|this|one|it|they)\b)",
            "\n",
            sentence,
            flags=re.IGNORECASE,
        )
        clauses = re.sub(
            r",?\s+and\s+(?=(?:an?\s+)?[+-]\d+\s+(?:[a-z ]+\s+)?(?:bonus|penalty)\b)",
            "\n",
            clauses,
            flags=re.IGNORECASE,
        )
        for clause in clauses.splitlines():
            clause = clause.strip()
            if re.match(r"^(?:an?\s+)?[+-]\d+\s+", clause, re.IGNORECASE):
                clause = "You gain " + clause
            for pattern in (_BONUS_PATTERN, _PENALTY_PATTERN):
                for match in pattern.finditer(clause):
                    targets_text = match.group("targets").strip()
                    prefix = clause[: match.start()]
                    if re.search(r"\b(?:choose|select)\b", prefix, re.IGNORECASE):
                        continue
                    if _CONDITIONAL_MARKERS.search(targets_text):
                        continue
                    bonus_type = (match.group("bonus_type") or "untyped").casefold()
                    value = int(match.group("value"))
                    for target in _numeric_targets(targets_text, bonus_type):
                        effects.append(_effect(target, value, bonus_type))
    return effects


def _deduplicate(effects: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple] = set()
    for effect in effects:
        key = tuple(effect.get(field, "") for field in (
            "target",
            "bonus_type",
            "value",
            "formula",
            "scope",
        ))
        if key not in seen:
            seen.add(key)
            result.append(effect)
    return result


def trait_automation(name: str, description: str) -> dict:
    """Return reviewed or conservatively inferred sheet behavior for a trait."""
    curated = _CURATED.get(name.casefold().strip())
    if curated is not None:
        return deepcopy(curated)
    clean_description = _normalize_rules_text(description)
    effects = _deduplicate(
        _safe_numeric_effects(clean_description)
        + _class_skill_effects(clean_description)
        + _allow_untrained_effects(clean_description)
    )
    if not effects:
        return {}
    return _static(
        *effects,
        note="Only unconditional, directly represented statistics from this trait are applied automatically. Other rules remain in the description.",
    )


def curated_trait_names() -> tuple[str, ...]:
    return tuple(sorted(_CURATED))
