from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.athletics_rules import athletics_packages


@dataclass(frozen=True, slots=True)
class DrawbackTalentGrant:
    """The constrained bonus choice supplied by a sphere-specific drawback.

    An empty candidate list means the drawback supplies an unrestricted bonus
    talent which remains part of the normal advancement budget.  Keeping the
    exception metadata here prevents acquisition dialogs from growing their
    own sphere-specific rule branches.
    """

    candidates: tuple[dict, ...] = ()
    count: int = 0
    feat_names: tuple[str, ...] = ()


_NO_BONUS_TALENT = {
    ("Mind", "Unusual Entreatment [3PP]"),
    ("War", "Squadron Elite"),
    ("Weather", "Personal Mantle"),
}

_DOUBLE_BONUS_TALENT = {
    ("Death", "Flesh Artisan"),
    ("Death", "Spiritual Voyager [DbH]"),
}

_DRAWBACK_BONUS_FEATS = {
    ("War", "Squadron Elite"): ("Squadron Commander",),
    ("Weather", "Personal Mantle"): ("Mantled Caster",),
}

_WEATHER_FIXED_TALENTS = {
    "Atmospheric Brew": ("Instill Weather",),
    "Small Weather": ("Focused Weather",),
}


def sphere_drawback_talent_value(drawback) -> int:
    """Return how many magic-talent budget points a drawback actually grants."""

    sphere = str(
        getattr(drawback, "school_or_sphere", "")
        or getattr(drawback, "sphere", "")
        or (drawback.get("sphere", "") if isinstance(drawback, dict) else "")
    )
    name = str(
        getattr(drawback, "name", "")
        or (drawback.get("name", "") if isinstance(drawback, dict) else "")
    )
    key = (sphere, name)
    if key in _NO_BONUS_TALENT:
        return 0
    if key in _DOUBLE_BONUS_TALENT:
        return 2
    return 1


def drawback_bonus_feat_names(drawback) -> tuple[str, ...]:
    sphere = str(drawback.get("sphere", ""))
    name = str(drawback.get("name", ""))
    return _DRAWBACK_BONUS_FEATS.get((sphere, name), ())


def _plain_talent_name(value: object) -> str:
    return re.sub(r"\s*\[[^]]+]\s*$", "", str(value or "")).strip()


def _specific_grant_text(description: str) -> str:
    """Keep only clauses which describe how the drawback's bonus is spent."""

    clauses = re.split(r"(?<=[.!?])\s+|\n+", description)
    markers = (
        "bonus talent", "talent gained", "talents gained", "with this drawback",
        "when taking this drawback", "must select", "must choose", "must take",
    )
    return " ".join(
        clause for clause in clauses
        if any(marker in clause.casefold() for marker in markers)
    )


def drawback_talent_grant(
    drawback: dict,
    catalog_entries: Iterable[dict],
    choice: str = "",
) -> DrawbackTalentGrant:
    """Resolve only constrained bonus-talent choices for one drawback.

    The catalog prose is reviewed local rules data.  Exact Weather exceptions
    are declared explicitly; the shared fallback recognizes named talents and
    tagged talent families in the sentence that describes the bonus.  This lets
    future imported drawbacks use the same dialog without UI changes.
    """

    sphere = str(drawback.get("sphere", ""))
    name = str(drawback.get("name", ""))
    key = (sphere, name)
    feat_names = drawback_bonus_feat_names(drawback)
    if key in _NO_BONUS_TALENT:
        return DrawbackTalentGrant((), 0, feat_names)

    entries = tuple(
        entry for entry in catalog_entries
        if str(entry.get("sphere", "")) == sphere
        and str(entry.get("category", "")) not in {"Base Sphere", "Drawback"}
    )
    fixed_names: tuple[str, ...] = ()
    if sphere == "Weather" and name == "Limited Weather":
        fixed_names = (
            ("Volcano Lord",)
            if choice in {"Ash", "Vog"}
            else ("Severe Weather",)
        )
    elif sphere == "Weather" and name == "Localized Weather":
        candidates = tuple(
            entry for entry in entries
            if str(entry.get("category", "")) in {"Mantle Talent", "Shroud Talent"}
        )
        return DrawbackTalentGrant(candidates, 1, feat_names)
    elif sphere == "Weather":
        fixed_names = _WEATHER_FIXED_TALENTS.get(name, ())

    grant_text = _specific_grant_text(str(drawback.get("description", "")))
    lower_grant = grant_text.casefold()
    explicit: list[dict] = []
    for entry in entries:
        plain_name = _plain_talent_name(entry.get("name", ""))
        if plain_name and re.search(rf"\b{re.escape(plain_name.casefold())}\b", lower_grant):
            explicit.append(entry)
    if fixed_names:
        explicit = [
            entry for entry in entries
            if any(
                _plain_talent_name(entry.get("name", "")).casefold()
                == fixed.casefold()
                for fixed in fixed_names
            )
        ]

    family_markers = {
        marker.strip().casefold()
        for marker in re.findall(r"\(([^)]+)\)\s+talents?", grant_text, re.I)
    }
    family_candidates = [
        entry for entry in entries
        if any(
            marker in str(entry.get("category", "")).casefold()
            or f"({marker})" in str(entry.get("name", "")).casefold()
            for marker in family_markers
        )
    ]
    candidates: dict[str, dict] = {}
    for entry in (*explicit, *family_candidates):
        candidates[str(entry.get("key", ""))] = entry
    count = sphere_drawback_talent_value(drawback) if candidates else 0
    return DrawbackTalentGrant(
        tuple(sorted(candidates.values(), key=lambda item: str(item.get("name", "")).casefold())),
        min(max(1, count), len(candidates)) if candidates else 0,
        feat_names,
    )


_CHOICE_OPTIONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("Blood", "Limited Acceleration"): ("Quicken", "Still"),
    ("Conjuration", "Material Weakness"): ("Cold iron", "Silver", "Wood", "GM-approved material"),
    ("Creation", "Limited Creation"): ("Alter", "Create"),
    ("Death", "Necromantic Limit"): ("Ghost Strike", "Reanimate"),
    ("Destruction", "Aligned Combatant"): ("Good", "Evil", "Lawful", "Chaotic"),
    ("Divination", "Limited Divination"): ("Sense", "Divine"),
    ("Life", "Limited Restoration"): ("Restore", "Cure / Invigorate"),
    ("Protection", "Aligned Protection"): ("Good", "Evil", "Lawful", "Chaotic"),
    ("Protection", "Limited Protection"): ("Aegis", "Ward"),
    ("Telekinesis", "Directional Control"): ("Toward you", "Away from you"),
    ("Time", "Altered Time"): ("Lose Haste", "Lose Slow"),
    ("Weather", "Atmoturgy"): ("Aridity", "Cold", "Heat", "Precipitation", "Wind"),
    ("Weather", "Limited Weather"): ("Aridity", "Ash", "Cold", "Heat", "Precipitation", "Vog", "Wind"),
    # The package prefix drives sheet automation. The condition suffix records the
    # actual environmental limitation so neither part of the decision is lost.
    ("Warp", "Limited Warp"): tuple(
        f"{package} — {condition}"
        for package in ("Teleport", "Bend Space")
        for condition in (
            "Dim light or darkness",
            "Body of water",
            "Touching fire",
            "Touching a living tree",
        )
    ),
    ("Alchemy", "Narrow Toxicology (requires (poison) package) [Apoc]"): (
        "Contact", "Ingested", "Inhaled", "Injury",
    ),
    ("Trap", "Focused Trapper"): ("Dart traps", "Snare traps"),
    ("Tech", "Specific Drone"): (
        "Alchemical Drone", "Clockwork Drone", "Robot Drone", "Steampowered Drone",
    ),
    ("Tech", "Uninsulated"): (
        "Doused in water", "Exposed to magnets", "Exposed to sand particles", "GM-approved condition",
    ),
    ("Tinker", "Specific Mechanoids [SUE]"): (
        "Armored", "Biological construct", "Clockwork", "Other Advanced Transportation template",
    ),
}


def drawback_choice_options(entry: dict) -> tuple[str, ...]:
    return _CHOICE_OPTIONS.get((str(entry.get("sphere", "")), str(entry.get("name", ""))), ())


def drawback_requires_choice(entry: dict) -> bool:
    if drawback_choice_options(entry):
        return True
    clauses = re.split(
        r"(?<=[.!?])\s+|\n+", str(entry.get("description", ""))
    )
    description = " ".join(
        clause for clause in clauses
        if not (
            any(marker in clause.casefold() for marker in ("bonus talent", "talent gained", "talents gained"))
            and any(marker in clause.casefold() for marker in ("must select", "must choose", "must take", "you gain"))
        )
    ).casefold()
    return any(
        re.search(pattern, description, re.DOTALL) is not None
        for pattern in (
            r"^\s*(?:source:[^\n]+\n)?\s*choose\b",
            r"\bchosen when you gain this drawback\b",
            r"\bchoose one of the following\b",
            r"\bmust (?:choose|select) (?:a|an|one|the)\b",
            r"\bchosen (?:material|terrain|creature type|object|alignment|environment)\b",
            r"\b(?:single, special substance|one type of material)\b",
            r"\bthe specifics .* determined by the player and gm\b",
        )
    )


def incompatible_drawbacks(entry: dict) -> set[str]:
    description = str(entry.get("description", ""))
    match = re.search(r"Incompatible:\s*([^\n]+)", description, re.IGNORECASE)
    if match is None:
        return set()
    return {
        item.strip().casefold()
        for item in re.split(r",|\band\b", match.group(1), flags=re.IGNORECASE)
        if item.strip()
    }


def _choice_package(choice: str) -> str:
    return re.split(r"\s+[—|]\s+", choice.strip(), maxsplit=1)[0].strip()


def sphere_package_access(spells: Iterable) -> dict[str, set[str]]:
    """Return package restrictions imposed by the character's saved drawbacks."""
    access: dict[str, set[str]] = {}
    for spell in spells:
        if str(getattr(spell, "catalog_category", "")) != "Drawback":
            continue
        sphere = str(getattr(spell, "school_or_sphere", ""))
        name = str(getattr(spell, "name", ""))
        choice = _choice_package(str(getattr(spell, "choice", "")))
        allowed: set[str] | None = None
        if sphere == "Warp" and name == "Limited Warp" and choice in {"Teleport", "Bend Space"}:
            allowed = {choice}
        elif sphere == "Blood" and name == "Limited Acceleration" and choice in {"Quicken", "Still"}:
            allowed = {choice}
        elif sphere == "Warp" and name in {"Bender"}:
            allowed = {"Bend Space"}
        elif sphere == "Warp" and name == "Exploit Fragility [SM—]":
            allowed = {"Teleport"}
        elif sphere == "Creation" and name == "Limited Creation" and choice:
            allowed = {choice}
        elif sphere == "Death" and name == "Necromantic Limit" and choice:
            allowed = {choice}
        elif sphere == "Divination" and name == "Limited Divination" and choice:
            allowed = {choice}
        elif sphere == "Life" and name == "Limited Restoration" and choice:
            allowed = {choice}
        elif sphere == "Protection" and name == "Limited Protection" and choice:
            allowed = {choice}
        elif sphere == "Time" and name == "Altered Time" and choice in {"Lose Haste", "Lose Slow"}:
            allowed = {"Slow" if choice == "Lose Haste" else "Haste"}
        if allowed is not None:
            access[sphere] = access.get(sphere, allowed) & allowed
    return access


def entry_packages(entry: dict) -> set[str]:
    sphere = str(entry.get("sphere", ""))
    category = str(entry.get("category", ""))
    name = str(entry.get("name", ""))
    text = " ".join(
        (name, category, str(entry.get("prerequisites", "")), str(entry.get("description", "")))
    ).casefold()
    if sphere == "Warp":
        if category == "Space Talent" or "(space)" in name.casefold():
            return {"Bend Space"}
        if "teleport" in text or category == "Talent":
            return {"Teleport"}
    elif sphere == "Blood":
        if "quicken" in text:
            return {"Quicken"}
        if "still" in text:
            return {"Still"}
    elif sphere == "Creation":
        if category == "Alter Talent" or " alter " in f" {text} ":
            return {"Alter"}
        if category in {"Material Talent", "Talent"} or " create " in f" {text} ":
            return {"Create"}
    elif sphere == "Death":
        if category == "Ghost Strike Talent" or "ghost strike" in text:
            return {"Ghost Strike"}
        if "reanimate" in text or "undead" in text or category in {"Talent", "Dominion Talent"}:
            return {"Reanimate"}
    elif sphere == "Divination":
        if category == "Sense Talent" or " sense " in f" {text} ":
            return {"Sense"}
        if category == "Divine Talent" or " divine " in f" {text} ":
            return {"Divine"}
    elif sphere == "Life":
        if category == "Cure Talent" or "cure" in text or "invigorate" in text:
            return {"Cure / Invigorate"}
        if "restore" in text:
            return {"Restore"}
    elif sphere == "Protection":
        packages = set()
        if "aegis" in text:
            packages.add("Aegis")
        if "ward" in text:
            packages.add("Ward")
        return packages
    elif sphere == "Time":
        packages = set()
        if "haste" in text:
            packages.add("Haste")
        if "slow" in text:
            packages.add("Slow")
        return packages
    return set()


def magic_talent_restriction_reason(entry: dict, spells: Iterable) -> str:
    spells = tuple(spells)
    access = sphere_package_access(spells)
    sphere = str(entry.get("sphere", ""))
    allowed = access.get(sphere)
    required = entry_packages(entry)
    if allowed is not None and required and not (allowed & required):
        available = " or ".join(sorted(allowed))
        needed = " or ".join(sorted(required))
        return (
            f"This character's {sphere} drawbacks retain only {available}. "
            f"{entry.get('name', 'This talent')} requires {needed}."
        )
    candidate_name = str(entry.get("name", ""))
    candidate_category = str(entry.get("category", ""))
    candidate_text = f"{candidate_name} {candidate_category}".casefold()
    for drawback in spells:
        if str(getattr(drawback, "catalog_category", "")) != "Drawback":
            continue
        if str(getattr(drawback, "school_or_sphere", "")).casefold() != sphere.casefold():
            continue
        description = _drawback_description(drawback)
        reason = _prose_restriction_reason(
            candidate_name,
            candidate_category,
            candidate_text,
            str(getattr(drawback, "name", "")),
            str(getattr(drawback, "choice", "")),
            description,
        )
        if reason:
            return reason
    return ""


def martial_talent_restriction_reason(entry: dict, talents: Iterable) -> str:
    """Return a saved-package restriction for martial talent selection."""

    sphere = str(entry.get("sphere", ""))
    packages_by_sphere = {
        "Alchemy": {"Formulae", "Poison"},
        "Athletics": {"Climb", "Fly", "Leap", "Run", "Swim"},
        "Beastmastery": {"Handle Animal", "Ride"},
        "Guardian": {"Challenge", "Patrol"},
        "Leadership": {"Cohort", "Follower"},
        "Tinker": {"Augmentation", "Computation", "Modification", "Transmission", "Transportation"},
    }
    if sphere not in packages_by_sphere:
        return ""
    category = str(entry.get("category", ""))
    if category in {"Base Sphere", "Drawback"}:
        return ""
    talents = tuple(talents)
    base = next(
        (
            item for item in talents
            if str(getattr(item, "sphere", "")) == sphere
            and str(getattr(item, "catalog_category", "")) == "Base Sphere"
        ),
        None,
    )
    if base is None:
        return ""
    saved_choice = str(getattr(base, "choice", "")).strip()
    if sphere == "Alchemy" and saved_choice.startswith("Formulae —"):
        saved_choice = "Formulae"
    available = (
        set(athletics_packages(talents))
        if sphere == "Athletics"
        else {saved_choice}
    )
    available.discard("")
    packages = packages_by_sphere[sphere]
    name = str(entry.get("name", ""))
    required = {
        package for package in packages
        if re.search(rf"\b{re.escape(package)}\b", name, re.I)
    }
    lower = f"{name} {category} {entry.get('prerequisites', '')}".casefold()
    if sphere == "Alchemy":
        if "formula" in lower:
            required = {"Formulae"}
        elif "toxin" in lower or "poison" in lower:
            required = {"Poison"}
    elif sphere == "Guardian":
        if "zone" in lower or "patrol" in lower:
            required = {"Patrol"}
        elif "challenge" in lower:
            required = {"Challenge"}
    elif sphere == "Leadership":
        if "cohort" in lower:
            required = {"Cohort"}
        elif "follower" in lower:
            required = {"Follower"}
    if not required:
        category_package = category.removesuffix(" Talent")
        if category_package in packages:
            required = {category_package}
    if required and not (available & required):
        needed = " or ".join(sorted(required))
        possessed = "none" if not available else " or ".join(sorted(available))
        return f"This {sphere} talent requires the {needed} package; this character has {possessed}."
    return ""


def _drawback_description(drawback) -> str:
    """Resolve reviewed catalog prose for old and new saved characters alike."""
    key = str(getattr(drawback, "catalog_key", ""))
    sphere = str(getattr(drawback, "school_or_sphere", ""))
    try:
        from app.content import magic_entries

        entry = next(
            (
                item
                for item in magic_entries(sphere)
                if (key and str(item.get("key", "")) == key)
                or str(item.get("name", "")).casefold()
                == str(getattr(drawback, "name", "")).casefold()
            ),
            None,
        )
    except (ImportError, OSError, ValueError):
        entry = None
    return str(entry.get("description", "")) if entry else str(getattr(drawback, "notes", ""))


def _prose_restriction_reason(
    candidate_name: str,
    candidate_category: str,
    candidate_text: str,
    drawback_name: str,
    choice: str,
    description: str,
) -> str:
    """Interpret only explicit selection prohibitions from catalog rules prose.

    This intentionally does not guess at situational limitations.  It blocks
    named talents, tagged talent families, and the small number of explicit
    whitelist drawbacks whose catalog structure makes the rule unambiguous.
    """
    lower = description.casefold()
    sentences = re.split(r"(?<=[.!?])\s+|\n+", lower)
    candidate = candidate_name.casefold()
    for sentence in sentences:
        prohibited = any(
            phrase in sentence
            for phrase in (
                "cannot select", "cannot gain", "cannot take",
                "may not select", "may not gain", "may not take",
            )
        )
        if not prohibited:
            continue
        if candidate and candidate in sentence:
            return f"{drawback_name} explicitly prohibits {candidate_name}."
        for marker in re.findall(r"\(([^)]+)\)\s+talents?", sentence):
            marker = marker.strip().casefold()
            if marker and marker in candidate_text:
                return f"{drawback_name} prohibits ({marker}) talents."

    sphere_specific = {
        "Gravity": ("gravity",),
        "Inward Focus [Apoc]": ("cognition",),
    }
    allowed_markers = sphere_specific.get(drawback_name)
    if allowed_markers and not any(marker in candidate_text for marker in allowed_markers):
        return (
            f"{drawback_name} only permits talents associated with "
            f"{', '.join(allowed_markers)}."
        )

    category = candidate_category.casefold()
    chosen = _choice_package(choice).casefold()
    if drawback_name == "Energy Focus" and "blast type" in category:
        if chosen and chosen not in candidate_text:
            return f"Energy Focus permits only the chosen {choice} blast type group."
    if drawback_name == "Shape Focus" and "blast shape" in category:
        if chosen and chosen not in candidate:
            return f"Shape Focus permits only the chosen blast shape: {choice}."
    if drawback_name == "Limited Weather" and chosen:
        weather_aspects = {"aridity", "ash", "cold", "heat", "precipitation", "vog", "wind"}
        referenced = {aspect for aspect in weather_aspects if aspect in candidate_text}
        if referenced and chosen not in referenced:
            return f"Limited Weather retains only the chosen {choice} weather category."
    return ""
