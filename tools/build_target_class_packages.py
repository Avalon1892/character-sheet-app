"""Build structured archetype overlays for the reviewed class families.

This is an import/build-time normalization step. Runtime rules never parse
archetype descriptions; they load the generated feature/replacement records
from ``app/class_packages/definitions/archetypes``.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping

from app.archetype_rules import (
    archetype_compatibility_metadata,
    replaced_features,
)
from app.class_feature_rules import archetype_granted_features
from app.class_mechanics_audit import detected_interactive_mechanics
from app.codex_descriptions import normalize_spheres_archetype_codex_entry
from app.text_cleanup import repair_text_tree
from app.class_packages.loader import supplemental_archetype_entries


ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data" / "pf1e"
OUTPUT_ROOT = ROOT / "app" / "class_packages" / "definitions" / "archetypes"
TARGETS = {
    "alchemist": "pathfinder-class:alchemist",
    "antipaladin": "pathfinder-class:antipaladin",
    "arcanist": "pathfinder-class:arcanist",
    "bard": "pathfinder-class:bard",
    "barbarian": "pathfinder-class:barbarian",
    "barbarian-unchained": "pathfinder-class:barbarian-unchained",
    "bloodrager": "pathfinder-class:bloodrager",
    "brawler": "pathfinder-class:brawler",
    "cleric": "pathfinder-class:cleric",
    "cavalier": "pathfinder-class:cavalier",
    "druid": "pathfinder-class:druid",
    "fighter": "pathfinder-class:fighter",
    "gunslinger": "pathfinder-class:gunslinger",
    "hunter": "pathfinder-class:hunter",
    "inquisitor": "pathfinder-class:inquisitor",
    "investigator": "pathfinder-class:investigator",
    "kineticist": "pathfinder-class:kineticist",
    "magus": "pathfinder-class:magus",
    "medium": "pathfinder-class:medium",
    "mesmerist": "pathfinder-class:mesmerist",
    "monk": "pathfinder-class:monk",
    "ninja": "pathfinder-class:ninja",
    "oracle": "pathfinder-class:oracle",
    "occultist": "pathfinder-class:occultist",
    "paladin": "pathfinder-class:paladin",
    "prodigy": "prodigy",
    "psychic": "pathfinder-class:psychic",
    "rogue": "pathfinder-class:rogue",
    "ranger": "pathfinder-class:ranger",
    "samurai": "pathfinder-class:samurai",
    "sorcerer": "pathfinder-class:sorcerer",
    "spiritualist": "pathfinder-class:spiritualist",
    "shaman": "pathfinder-class:shaman",
    "slayer": "pathfinder-class:slayer",
    "wizard": "pathfinder-class:wizard",
    "warpriest": "pathfinder-class:warpriest",
    "witch": "pathfinder-class:witch",
    "armiger": "spheres-class:armiger",
    "armorist": "spheres-class:armorist",
    "incanter": "spheres-class:incanter",
    "blacksmith": "spheres-class:blacksmith",
    "conscript": "spheres-class:conscript",
    "elementalist": "spheres-class:elementalist",
    "commander": "spheres-class:commander",
    "scholar": "spheres-class:scholar",
    "sentinel": "spheres-class:sentinel",
    "striker": "spheres-class:striker",
    "technician": "spheres-class:technician",
    "mageknight": "spheres-class:mageknight",
    "hedgewitch": "spheres-class:hedgewitch",
    "shifter": "spheres-class:shifter",
    "soul-weaver": "spheres-class:soul-weaver",
    "thaumaturge": "spheres-class:thaumaturge",
    "fey-adept": "spheres-class:fey-adept",
    "symbiat": "spheres-class:symbiat",
    "eliciter": "spheres-class:eliciter",
    "wraith": "spheres-class:wraith",
    "sage": "spheres-class:sage",
    "necros": "spheres-class:necros",
    "troubadour": "spheres-class:troubadour",
    "warden": "spheres-class:warden",
    "crimson-dancer": "spheres-class:crimson-dancer",
    "mountebank": "spheres-class:mountebank",
    "reaper": "spheres-class:reaper",
}


def _document(name: str) -> dict:
    with (DATA_ROOT / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def _combined_entries() -> tuple[dict, ...]:
    combined = tuple(_document("archetypes.json").get("entries", ())) + tuple(
        _document("spheres_class_archetypes.json").get("entries", ())
    ) + supplemental_archetype_entries()
    unique: dict[str, dict] = {}
    for raw in combined:
        source = repair_text_tree(raw)
        entry = (
            normalize_spheres_archetype_codex_entry(source)
            if str(source.get("source_group") or "").casefold() == "spheres"
            else dict(source)
        )
        key = str(entry.get("key") or "")
        if not key:
            continue
        if key in unique:
            # Complete class-page imports enrich the reviewed index entry.
            for field in (
                "replaces",
                "replaces_features",
                "removed_features",
                "compatibility",
                "class_modifications",
                "choices",
                "features",
            ):
                if entry.get(field):
                    unique[key][field] = entry[field]
            continue
        unique[key] = entry
    return tuple(unique.values())


def _structured_feature(feature) -> dict:
    return {
        "level": int(feature.level),
        "name": str(feature.name),
        "description": str(feature.description),
    }


def _removed_feature_clauses(features: tuple[dict, ...]) -> tuple[str, ...]:
    """Preserve the exact scope of explicit replacement sentences.

    Normalized compatibility tokens intentionally collapse details such as
    “the 2nd- and 12th-level bonus feats”.  That is useful for overlap checks,
    but not for deciding whether an overarching feature row remains present.
    Store the published clause separately at build time so runtime feature
    resolution never needs to parse catalog prose.
    """

    result: list[str] = []
    for feature in features:
        description = str(feature.get("description") or "")
        for match in re.finditer(
            r"(?:This|These) (?:ability|abilities|class feature|class features)?\s*"
            r"replaces?\s+(?:the )?([^\n.]+)",
            description,
            re.I,
        ):
            clause = match.group(1).strip()
            # Split lists of distinct features, but not level scopes such as
            # “2nd and 12th level bonus feats”.
            result.extend(
                part.strip(" ,")
                for part in re.split(r",|\band\b(?=\s*[A-Za-z])", clause, flags=re.I)
                if part.strip(" ,")
            )
    return tuple(dict.fromkeys(value for value in result if value))


def _package_entry(
    entry: Mapping[str, object], definitions: Mapping[str, Mapping[str, object]],
) -> dict:
    features = tuple(
        _structured_feature(feature)
        for feature in archetype_granted_features(entry, 20)
    )
    removed = tuple(
        str(value) for value in entry.get("removed_features", ()) if str(value)
    )
    if not removed and str(entry.get("source_group") or "").casefold() != "spheres":
        removed = tuple(sorted(replaced_features(entry)))
    return {
        "key": str(entry.get("key") or ""),
        "package": str(entry.get("class_key") or ""),
        "name": str(entry.get("name") or ""),
        "source_group": str(entry.get("source_group") or ""),
        "source_url": str(entry.get("source_url") or ""),
        "replaces_features": list(sorted(replaced_features(entry))),
        "removed_features": list(removed),
        "removed_feature_clauses": list(_removed_feature_clauses(features)),
        "compatibility": archetype_compatibility_metadata(entry, definitions),
        "class_modifications": entry.get("class_modifications") or {},
        "choices": entry.get("choices") or [],
        "features": list(features),
        "detected_systems": list(detected_interactive_mechanics(entry)),
    }


def build(output_root: Path = OUTPUT_ROOT, class_slugs: tuple[str, ...] = ()) -> tuple[Path, ...]:
    unknown = set(class_slugs) - TARGETS.keys()
    if unknown:
        raise ValueError(f"Unknown class packages: {', '.join(sorted(unknown))}")
    entries = _combined_entries()
    definitions = {str(entry["key"]): entry for entry in entries}
    output_root.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, class_key in TARGETS.items():
        if class_slugs and slug not in class_slugs:
            continue
        packaged = [
            _package_entry(entry, definitions)
            for entry in entries
            if str(entry.get("class_key") or "") == class_key
        ]
        packaged.sort(key=lambda entry: (entry["name"].casefold(), entry["key"]))
        target = output_root / f"{slug}.json"
        target.write_text(
            json.dumps(
                {
                    "version": 1,
                    "class_key": class_key,
                    "entries": packaged,
                },
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        written.append(target)
    return tuple(written)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--class", dest="class_slugs", action="append", choices=sorted(TARGETS),
                        help="Regenerate only this class family; repeat for a focused batch.")
    arguments = parser.parse_args()
    for path in build(arguments.output, tuple(arguments.class_slugs or ())):
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
