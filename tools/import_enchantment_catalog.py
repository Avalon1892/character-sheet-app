"""Normalize PF1 weapon, armor, and shield special abilities for the app.

The Foundry PF1 compendium is a build-time source only.  Runtime code consumes
the generated JSON so installed copies neither need PyYAML nor network access.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
import yaml  # type: ignore  # build-only dependency

RULES = ROOT / ".item-source" / "packs" / "rules"
OUTPUT = ROOT / "data" / "pf1e" / "enchantments.json"
SOURCES = (
    (
        RULES / "magical-weapon-abilities.q479ojN4dcCzbWrc.yaml",
        "Weapon",
        ((7_800_000, "Melee"), (10_700_000, "Ranged"), (10**20, "Universal")),
    ),
    (
        RULES / "magical-armor-and-shield-abilities.rcLVX5Td4PevCep8.yaml",
        "Armor & Shield",
        ((10_800_000, "Armor"), (13_600_000, "Shield"), (10**20, "Universal")),
    ),
)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def plain(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def section(content: str, name: str, next_name: str | None = None) -> str:
    end = rf"<h[1-6][^>]*>\s*{re.escape(next_name)}\s*</h[1-6]>" if next_name else r"\Z"
    match = re.search(
        rf"<h[1-6][^>]*>\s*{re.escape(name)}\s*</h[1-6]>(.*?)(?={end})",
        content,
        re.I | re.S,
    )
    return plain(match.group(1)) if match else ""


def category_for(sort: int, boundaries: tuple[tuple[int, str], ...]) -> str:
    return next(label for maximum, label in boundaries if sort < maximum)


def restriction_sentences(description: str) -> list[str]:
    result = []
    for sentence in re.split(r"(?<=[.!?])\s+", description):
        lowered = sentence.casefold()
        if (
            any(phrase in lowered for phrase in ("can only", "only be", "may only", "cannot be", "must be placed", "can be placed only", "placed on only"))
            or ("placed" in lowered and "only" in lowered)
        ):
            result.append(sentence.strip())
    return result


def entry_from_page(page: dict, family: str, boundaries) -> dict:
    name = str(page.get("name") or "Unnamed ability").strip()
    category = category_for(int(page.get("sort") or 0), boundaries)
    content = str((page.get("text") or {}).get("content") or "")
    header = plain(content.split("<h3", 1)[0])
    description = section(content, "Description", "Construction")
    construction = section(content, "Construction")
    source_match = re.search(r"Source\s+(.*?)(?=\s+Aura\b|\s+CL\b|\s+Price\b)", header, re.I)
    aura_match = re.search(r"Aura\s+(.*?)(?=\s+CL\b|\s+Slot\b|\s+Price\b)", header, re.I)
    cl_match = re.search(r"\bCL\s+([^;]+?)(?=\s+Slot\b|\s+Price\b|;|$)", header, re.I)
    price_match = re.search(r"\bPrice\s+([^;]+)", header, re.I)
    price_text = (price_match.group(1).strip() if price_match else "—").rstrip(".")
    bonus_match = re.search(r"\+(\d+)\s+bonus", price_text, re.I)
    gp_match = re.search(r"\+?([\d,]+)\s*gp", price_text, re.I)
    requirements_match = re.search(r"Requirements\s+(.*?)(?=\s+Price\b|$)", construction, re.I)
    key = (
        "pathfinder:weapon-property:agile"
        if family == "Weapon" and name.casefold() == "agile"
        else f"pathfinder:enchantment:{slug(family)}:{slug(category)}:{slug(name)}"
    )
    aon_page = "MagicWeaponsDisplay.aspx" if family == "Weapon" else "MagicArmorDisplay.aspx"
    return {
        "key": key,
        "name": name,
        "family": family,
        "category": category,
        "applies_to": (
            ["weapon_melee"] if category == "Melee" else
            ["weapon_ranged"] if category == "Ranged" else
            ["weapon_melee", "weapon_ranged"] if family == "Weapon" else
            ["armor"] if category == "Armor" else
            ["shield"] if category == "Shield" else
            ["armor", "shield"]
        ),
        "bonus_equivalent": int(bonus_match.group(1)) if bonus_match else 0,
        "flat_price_gp": int(gp_match.group(1).replace(",", "")) if gp_match else 0,
        "price_text": price_text,
        "aura": aura_match.group(1).strip() if aura_match else "",
        "caster_level": cl_match.group(1).strip() if cl_match else "",
        "description": description,
        "requirements": requirements_match.group(1).strip() if requirements_match else "",
        "restrictions": restriction_sentences(description),
        "source": source_match.group(1).strip() if source_match else "Pathfinder RPG",
        "source_url": "https://www.aonprd.com/" + aon_page + "?ItemName=" + urllib.parse.quote_plus(name),
        "automation_status": "automatic" if key == "pathfinder:weapon-property:agile" else "rules_only",
    }


def main() -> None:
    entries = []
    for path, family, boundaries in SOURCES:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries.extend(
            entry_from_page(page, family, boundaries)
            for page in document.get("pages", ())
            if "<h3>Description</h3>" in str((page.get("text") or {}).get("content") or "")
        )
    entries.sort(key=lambda item: (item["family"], item["category"], item["name"].casefold(), item["key"]))
    OUTPUT.write_text(
        json.dumps({"version": 1, "entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    counts = {family: sum(1 for entry in entries if entry["family"] == family) for family in ("Weapon", "Armor & Shield")}
    print(f"Wrote {len(entries)} enchantments to {OUTPUT} ({counts})")


if __name__ == "__main__":
    main()
