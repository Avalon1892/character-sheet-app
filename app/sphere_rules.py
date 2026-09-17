from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.drawback_rules import sphere_package_access


@dataclass(frozen=True, slots=True)
class BaseAbilitySpec:
    name: str
    heading: str
    packages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SphereAbilityView:
    """A read-only Page 3 projection derived from base-sphere ownership."""

    key: str
    source_id: int
    name: str
    sphere: str
    notes: str
    source_url: str
    system: str = "Sphere"
    catalog_category: str = "Sphere Ability"
    choice: str = ""
    casting_time: str = ""
    range: str = ""
    duration: str = ""
    prerequisites: str = ""
    effects: tuple = ()
    enabled: bool = True

    @property
    def school_or_sphere(self) -> str:
        return self.sphere


# This is deliberately reviewed rules metadata, rather than a UI parser.  A
# future catalog refresh can update this one registry without changing Page 3.
BASE_ABILITIES: dict[str, tuple[BaseAbilitySpec, ...]] = {
    "Alteration": (
        BaseAbilitySpec("Shapeshift", "Shapeshift"),
        BaseAbilitySpec("Blank Transformation", "Blank Transformation"),
    ),
    "Blood": (
        BaseAbilitySpec("Blood Control", "Blood Control", ("Blood Control",)),
        BaseAbilitySpec("Bleed", "Bleed (quicken)", ("Quicken",)),
        BaseAbilitySpec("Coagulate", "Coagulate (still)", ("Still",)),
    ),
    "Conjuration": (BaseAbilitySpec("Summon Companion", "Summon"),),
    "Creation": (
        BaseAbilitySpec("Alter", "Alter", ("Alter",)),
        BaseAbilitySpec("Create", "Create", ("Create",)),
    ),
    "Dark": (
        BaseAbilitySpec("Darkness", "Darkness", ("Darkness",)),
        BaseAbilitySpec("Meld: Darkvision", "Meld", ("Meld",)),
    ),
    "Death": (
        BaseAbilitySpec("Ghost Strike: Exhausting Strike", "Ghost Strike", ("Ghost Strike",)),
        BaseAbilitySpec("Reanimate: Animate Dead", "Reanimate", ("Reanimate",)),
    ),
    "Destruction": (BaseAbilitySpec("Destructive Blast", "Destructive Blast"),),
    "Divination": (BaseAbilitySpec("Divine: Detect Magic", "Divine", ("Divine",)),),
    "Enhancement": (BaseAbilitySpec("Enhance Equipment", "Enhance",),),
    "Fallen Fey": (BaseAbilitySpec("Fey-Link: Nature-Connection", "Fey-Link"),),
    "Fate": (
        BaseAbilitySpec("Consecration: Serendipity", "Consecration", ("Consecration",)),
        BaseAbilitySpec("Word: Hallow", "Word", ("Word",)),
    ),
    "Illusion": (
        BaseAbilitySpec("Illusion", "Illusion"),
        BaseAbilitySpec("Illusionary Disguise", "Illusionary Disguise"),
    ),
    "Life": (
        BaseAbilitySpec("Cure", "Cure", ("Cure / Invigorate",)),
        BaseAbilitySpec("Invigorate", "Invigorate", ("Cure / Invigorate",)),
        BaseAbilitySpec("Restore", "Restore", ("Restore",)),
    ),
    "Light": (
        BaseAbilitySpec("Glow: Bright Light", "Glow", ("Glow",)),
        BaseAbilitySpec("Lens: Telescope", "Lens", ("Lens",)),
    ),
    "Mana": (
        BaseAbilitySpec("Expunge: Spellburn", "Expunge", ("Expunge",)),
        BaseAbilitySpec("Manabond: Mystical Bond", "Manabond", ("Manabond",)),
        BaseAbilitySpec("Manipulation: Shuffle", "Manipulation/Amp", ("Manipulation",)),
    ),
    "Mind": (BaseAbilitySpec("Charm: Suggestion", "Charm", ("Charm",)),),
    "Nature": (
        BaseAbilitySpec("Geomancing: Air", "Air", ("Air",)),
        BaseAbilitySpec("Geomancing: Earth", "Earth", ("Earth",)),
        BaseAbilitySpec("Geomancing: Fire", "Fire", ("Fire",)),
        BaseAbilitySpec("Geomancing: Metal", "Metal", ("Metal",)),
        BaseAbilitySpec("Geomancing: Plant", "Plant", ("Plant",)),
        BaseAbilitySpec("Geomancing: Water", "Water", ("Water",)),
    ),
    "Protection": (
        BaseAbilitySpec("Aegis: Deflection", "Aegis", ("Aegis",)),
        BaseAbilitySpec("Ward", "Ward", ("Ward",)),
        BaseAbilitySpec("Ward: Barrier", "Barrier", ("Ward", "Barrier")),
    ),
    "Telekinesis": (
        BaseAbilitySpec("Telekinesis", "Telekinesis"),
        BaseAbilitySpec("Bludgeon", "Bludgeon", ("Bludgeon",)),
        BaseAbilitySpec("Catch", "Catch", ("Catch",)),
        BaseAbilitySpec("Hostile Lift", "Hostile Lift", ("Hostile Lift",)),
        BaseAbilitySpec("Sustained Force", "Sustained Force", ("Sustained Force",)),
    ),
    "Time": (
        BaseAbilitySpec("Alter Time: Haste", "Haste", ("Haste",)),
        BaseAbilitySpec("Alter Time: Slow", "Slow", ("Slow",)),
    ),
    "War": (
        BaseAbilitySpec("Totem: Totem Of War", "Totem", ("Totem",)),
        BaseAbilitySpec("Rally: Commanding Aid", "Rally", ("Rally",)),
    ),
    "Warp": (
        BaseAbilitySpec("Teleport", "Teleport", ("Teleport",)),
        BaseAbilitySpec("Bend Space", "Bend Space", ("Bend Space",)),
    ),
    "Weather": (BaseAbilitySpec("Control Weather", "Control Weather"),),
}


_BASE_SPHERE_CHOICES: dict[str, tuple[str, ...]] = {
    "Nature": ("Air", "Earth", "Fire", "Metal", "Plant", "Water"),
    "Conjuration": ("Avian", "Biped", "Ooze", "Orb", "Quadruped", "Serpentine", "Vermin"),
}

_MARTIAL_BASE_SPHERE_CHOICES: dict[str, tuple[str, ...]] = {
    "Alchemy": ("Formulae", "Poison"),
    "Athletics": ("Climb", "Fly", "Leap", "Run", "Swim"),
    "Beastmastery": ("Handle Animal", "Ride"),
    "Guardian": ("Challenge", "Patrol"),
    "Leadership": ("Cohort", "Follower"),
    "Tinker": ("Augmentation", "Computation", "Modification", "Transmission", "Transportation"),
}


_REMOVED_BASE_ABILITIES: dict[tuple[str, str], tuple[str, ...]] = {
    ("Blood", "Cruoromancy [BaP]"): ("Blood Control", "Bleed", "Coagulate"),
    ("Blood", "Hemokinetic"): ("Blood Control", "Bleed", "Coagulate"),
    ("Dark", "Meld Into Dark"): ("Darkness",),
    ("Dark", "Penumbra"): ("Darkness",),
    ("Dark", "Shadow Master"): ("Darkness",),
    ("Fate", "Luckless"): ("Consecration",),
    ("Fate", "Neutrality"): ("Word",),
    ("Life", "Slow Recovery"): ("Cure",),
    ("Mana", "Conservationist [Mana HB]"): ("Spellburn",),
    ("Mana", "Incongruent [Mana HB]"): ("Manabond",),
    ("Mana", "Selfish Caster [Mana HB]"): ("Manipulation",),
    ("Mind", "Inward Focus [Apoc]"): ("Charm",),
    ("Protection", "Circle Of Symbols"): ("Barrier",),
    ("Telekinesis", "Passive Telekinesis"): ("Bludgeon",),
    ("War", "Alternate Rally"): ("Rally",),
    ("War", "Alternate Totem"): ("Totem",),
    ("War", "Commando"): ("Rally",),
    ("Weather", "Localized Weather"): ("Control Weather",),
}


def base_sphere_choice_options(
    sphere: str, sphere_kind: str = "magic"
) -> tuple[str, ...]:
    if sphere_kind == "martial" and sphere in {"Alchemy", "Equipment", "Tech"}:
        try:
            from app.content import martial_entries

            if sphere == "Alchemy":
                formulae = sorted(
                    {
                        str(entry.get("name", ""))
                        for entry in martial_entries(sphere)
                        if str(entry.get("category", "")) == "Formulae Talent"
                    },
                    key=str.casefold,
                )
                return ("Poison", *(f"Formulae — {name}" for name in formulae if name))
            candidates = []
            for entry in martial_entries(sphere):
                category = str(entry.get("category", ""))
                if category in {"Base Sphere", "Drawback", "Legendary Talent"}:
                    continue
                if sphere == "Tech" and "gadget" not in (
                    f"{entry.get('name', '')} {entry.get('description', '')[:180]}".casefold()
                ):
                    continue
                candidates.append(str(entry.get("name", "")))
            return tuple(sorted(set(filter(None, candidates)), key=str.casefold))
        except (ImportError, OSError, ValueError):
            return ()
    source = _MARTIAL_BASE_SPHERE_CHOICES if sphere_kind == "martial" else _BASE_SPHERE_CHOICES
    return source.get(sphere, ())


def base_sphere_choice_label(sphere: str, sphere_kind: str = "magic") -> str:
    if sphere_kind == "martial":
        return "Starting package"
    return "Companion form" if sphere == "Conjuration" else "Starting package"


def martial_base_granted_talent_name(sphere: str, choice: str) -> str:
    """Translate a starting choice that also grants a separate talent.

    Most martial sphere choices only select a package. Equipment, Tech, and
    Alchemy's Formulae package instead include a free talent. Keeping that
    translation next to the choice registry gives acquisition, projection, and
    advancement counting one shared extension point.
    """

    clean_choice = str(choice).strip()
    if sphere in {"Equipment", "Tech"}:
        return clean_choice
    if sphere == "Alchemy" and clean_choice.startswith("Formulae —"):
        return clean_choice.partition("—")[2].strip()
    return ""


def martial_base_choice_for_entry(entry: dict) -> str:
    """Infer the initial package/free talent when a grant already names it."""

    sphere = str(entry.get("sphere", ""))
    category = str(entry.get("category", ""))
    name = str(entry.get("name", ""))
    if category in {"Base Sphere", "Drawback"}:
        return ""
    if sphere in {"Equipment", "Tech"}:
        return name
    if sphere == "Alchemy":
        if category == "Formulae Talent":
            return f"Formulae — {name}"
        if category == "Toxin Talent":
            return "Poison"
    packages = {
        "Athletics": ("Climb", "Fly", "Leap", "Run", "Swim"),
        "Beastmastery": ("Handle Animal", "Ride"),
        "Guardian": ("Challenge", "Patrol"),
        "Leadership": ("Cohort", "Follower"),
        "Tinker": ("Augmentation", "Computation", "Modification", "Transmission", "Transportation"),
    }.get(sphere, ())
    text = f"{name} {category} {entry.get('prerequisites', '')}"
    matches = [option for option in packages if re.search(rf"\b{re.escape(option)}\b", text, re.I)]
    return matches[0] if len(matches) == 1 else ""


@dataclass(frozen=True, slots=True)
class MartialSphereAbilityView:
    id: int
    name: str
    sphere: str
    notes: str
    choice: str = ""
    catalog_category: str = "Base Ability"
    talent_type: str = "Base Sphere"
    catalog_key: str = ""
    prerequisites: str = ""
    source_url: str = ""
    enabled: bool = True
    effects: tuple = ()
    activation: str = "always"
    activation_note: str = ""


def granted_martial_sphere_abilities(talents: Iterable) -> tuple[object, ...]:
    """Replace package-bearing base records with their actual granted abilities."""

    result: list[object] = []
    for talent in talents:
        sphere = str(getattr(talent, "sphere", ""))
        category = str(getattr(talent, "catalog_category", ""))
        if sphere != "Athletics" or category != "Base Sphere":
            result.append(talent)
            continue
        choice = str(getattr(talent, "choice", "")).strip()
        notes = str(getattr(talent, "notes", ""))
        coordinated = notes.split("Athletics Packages", 1)[0].strip()
        result.append(MartialSphereAbilityView(
            int(getattr(talent, "id", 0)), "Coordinated Movement", sphere,
            coordinated or notes, choice,
        ))
        if choice:
            package_match = re.search(
                rf"(?ims)^\s*{re.escape(choice)}\s*$\s*(.*?)(?=^\s*(?:Climb|Fly|Leap|Run|Swim|Athletic Talent Types)\s*$|\Z)",
                notes,
            )
            package_notes = package_match.group(1).strip() if package_match else notes
            result.append(MartialSphereAbilityView(
                int(getattr(talent, "id", 0)), f"Athletics Package: {choice}",
                sphere, package_notes, choice,
            ))
    return tuple(result)


def granted_sphere_abilities(spells: Iterable) -> tuple[SphereAbilityView, ...]:
    spells = tuple(spells)
    access = sphere_package_access(spells)
    drawbacks = {
        (str(getattr(item, "school_or_sphere", "")), str(getattr(item, "name", "")))
        for item in spells
        if str(getattr(item, "catalog_category", "")) == "Drawback"
    }
    result: list[SphereAbilityView] = []
    for base in spells:
        if str(getattr(base, "catalog_category", "")) != "Base Sphere":
            continue
        sphere = str(getattr(base, "school_or_sphere", ""))
        specs = BASE_ABILITIES.get(sphere, ())
        selected_package = str(getattr(base, "choice", "")).strip()
        allowed = access.get(sphere)
        removed = {
            fragment.casefold()
            for key, fragments in _REMOVED_BASE_ABILITIES.items()
            if key in drawbacks
            for fragment in fragments
        }
        for index, spec in enumerate(specs):
            if sphere == "Nature" and selected_package and selected_package not in spec.packages:
                continue
            if allowed is not None and spec.packages and not (set(spec.packages) & allowed):
                continue
            if any(fragment in spec.name.casefold() for fragment in removed):
                continue
            notes = _ability_description(str(getattr(base, "notes", "")), specs, index)
            if sphere == "Conjuration" and selected_package:
                notes = f"Chosen companion form: {selected_package}.\n\n{notes}"
            result.append(
                SphereAbilityView(
                    key=f"sphere-ability:{sphere.casefold()}:{index}",
                    source_id=int(getattr(base, "id", 0) or 0),
                    name=spec.name,
                    sphere=sphere,
                    notes=notes,
                    source_url=str(getattr(base, "source_url", "")),
                    choice=selected_package if sphere in _BASE_SPHERE_CHOICES else "",
                    duration=str(getattr(base, "duration", "") or ""),
                )
            )
    return tuple(result)


def _ability_description(
    description: str, specs: tuple[BaseAbilitySpec, ...], index: int
) -> str:
    heading = specs[index].heading
    pattern = re.compile(rf"(?im)^{re.escape(heading)}\s*$")
    match = pattern.search(description)
    if match is None:
        return description
    start = match.start()
    end = len(description)
    for later in specs[index + 1 :]:
        later_match = re.search(rf"(?im)^{re.escape(later.heading)}\s*$", description[match.end() :])
        if later_match is not None:
            end = match.end() + later_match.start()
            break
    talent_types = re.search(r"(?im)^.+Talent Types?\s*$", description[start:end])
    if talent_types is not None:
        end = start + talent_types.start()
    return description[start:end].strip()
