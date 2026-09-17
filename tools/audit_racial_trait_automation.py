"""Report racial-trait automation and structured-choice coverage."""
from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "pf1e" / "races.json"
OUTPUT = ROOT / "RACIAL_TRAIT_AUTOMATION_AUDIT.md"
CHOICE_PATTERN = re.compile(r"\b(?:choose|select|pick)\b", re.I)
REVIEWED_RUNTIME_CHOICES = {
    ("Elf", "Human-Raised"), ("Elf", "Spirit of the Waters"),
    ("Elf", "Elven Arrogance"), ("Elf", "Tongue of the Sea"),
    ("Gnome", "Dirty Trickster"), ("Half-Elf", "Water Child"),
    ("Half-Elf", "Drow Heritage"), ("Half-Elf", "Hidden Half-Breed"),
    ("Half-Orc", "Stoic"), ("Half-Orc", "Human-Raised"),
    ("Halfling", "Adaptable Luck"), ("Halfling", "Halfling Jinx"),
    ("Human", "Draconic Heritage"), ("Catfolk", "Curiosity"),
    ("Dhampir", "Fangs"), ("Ifrit", "Mostly Human"),
    ("Oread", "Mostly Human"), ("Suli", "Mostly Human"),
    ("Sylph", "Mostly Human"), ("Undine", "Mostly Human"),
    ("Tiefling", "Pass for Human"), ("Vanara", "Risky Troublemaker"),
    ("Wayang", "Shadow Speaker (Su)"),
}


def main() -> None:
    races = json.loads(CATALOG.read_text(encoding="utf-8"))["entries"]
    base = [trait for race in races for trait in race.get("racial_traits", ())]
    alternates = [
        (race, trait)
        for race in races
        for trait in race.get("alternate_racial_traits", ())
    ]
    choice_candidates = [
        (race, trait) for race, trait in alternates
        if CHOICE_PATTERN.search(str(trait.get("description") or ""))
    ]
    structured = [
        (race, trait) for race, trait in alternates if trait.get("choice_specs")
    ]
    automated = [
        (race, trait) for race, trait in alternates if trait.get("automation")
    ]
    pending = [
        (race, trait) for race, trait in choice_candidates
        if not trait.get("choice_specs")
        and (str(race.get("name")), str(trait.get("name"))) not in REVIEWED_RUNTIME_CHOICES
    ]
    runtime_choices = [
        (race, trait) for race, trait in choice_candidates
        if (str(race.get("name")), str(trait.get("name"))) in REVIEWED_RUNTIME_CHOICES
    ]
    all_traits = [*base, *(trait for _race, trait in alternates)]
    senses = [trait for trait in all_traits if (trait.get("automation") or {}).get("senses")]
    natural_attacks = [
        trait for trait in all_traits if (trait.get("automation") or {}).get("natural_attacks")
    ]
    conditional = [
        trait for trait in all_traits if (trait.get("automation") or {}).get("conditional_modifiers")
    ]
    lines = [
        "# Racial Trait Automation Audit",
        "",
        "Generated from the bundled race catalog. Description matching is used only",
        "to build this review queue; runtime rules consume reviewed structured data.",
        "",
        f"- Races: **{len(races)}**",
        f"- Base racial traits: **{len(base)}**",
        f"- Alternate racial traits: **{len(alternates)}**",
        f"- Alternate traits with reviewed automation: **{len(automated)}**",
        f"- Structured choice traits: **{len(structured)}**",
        f"- Reviewed runtime/optional decisions (not creation choices): **{len(runtime_choices)}**",
        f"- Choice candidates awaiting review: **{len(pending)}**",
        f"- Traits with structured senses: **{len(senses)}**",
        f"- Traits generating natural attacks directly: **{len(natural_attacks)}**",
        f"- Traits with non-global conditional modifiers: **{len(conditional)}**",
        "",
        "## Structured choices",
        "",
    ]
    lines.extend(
        f"- **{race['name']} — {trait['name']}**: "
        + ", ".join(str(spec.get("label") or spec.get("key")) for spec in trait["choice_specs"])
        for race, trait in structured
    )
    lines.extend(("", "## Choice review queue", ""))
    lines.extend(
        f"- {race['name']} — {trait['name']}"
        for race, trait in pending
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"races={len(races)} base={len(base)} alternates={len(alternates)} "
        f"automated={len(automated)} structured_choices={len(structured)} "
        f"runtime_choices={len(runtime_choices)} choice_review={len(pending)}"
    )


if __name__ == "__main__":
    main()
