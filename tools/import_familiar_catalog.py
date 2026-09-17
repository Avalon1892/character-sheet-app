"""Import the PF1e normal-familiar catalog and published creature statistics.

The runtime never scrapes rules sites.  This importer builds one immutable local
catalog that the Familiar/Pet rules and picker share.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "pf1e" / "familiars.json"
INDEX_URL = "https://www.d20pfsrd.com/classes/core-classes/wizard/familiar/"
EXTRA_FORMS = (
    {
        "name": "Fox, Firefoot Fennec",
        "url": "https://www.d20pfsrd.com/bestiary/monster-listings/animals/canines/fox/fox-firefoot-fennec",
        "special": "Master gains a +2 bonus on Reflex saves (fox familiar).",
        "source": "Pathfinder Campaign Setting: The Inner Sea World Guide",
        "ruleset": "Pathfinder",
    },
    {
        "name": "Fox, Creamfoot Fennec",
        "url": "https://www.d20pfsrd.com/bestiary/monster-listings/animals/canines/fox/fox-creamfoot-fennec/",
        "special": "The master is treated as possessing the desert runner quality.",
        "source": "Wayfinder #12",
        "ruleset": "Third Party",
    },
)

URL_CORRECTIONS = {
    "Penguin": "https://www.d20pfsrd.com/bestiary/monster-listings/animals/birds/penguin/",
    "Spiny Starfish": "https://www.d20pfsrd.com/bestiary/monster-listings/vermin/starfish/spiny-starfish/",
}


def _fetch(url: str) -> BeautifulSoup:
    request = Request(url, headers={"User-Agent": "CharacterSheetCatalogImporter/1.0"})
    return BeautifulSoup(urlopen(request, timeout=60).read(), "html.parser")


def _slug(value: str) -> str:
    value = re.sub(r"\([^)]*use\s+.+?statistics[^)]*\)", "", value, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _compact_text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def _between(text: str, start: str, *ends: str) -> str:
    if start not in text:
        return ""
    value = text.split(start, 1)[1]
    positions = [value.find(end) for end in ends if value.find(end) >= 0]
    return value[: min(positions)] if positions else value


def _match(text: str, pattern: str, default: str = "") -> str:
    found = re.search(pattern, text, re.I | re.S)
    return " ".join(found.group(1).split()).strip(" ;,.") if found else default


def _number(text: str, pattern: str) -> int | None:
    value = _match(text, pattern)
    if not value:
        return None
    try:
        return int(value.replace("−", "-").replace("–", "-"))
    except ValueError:
        return None


def _statblock(soup: BeautifulSoup, url: str) -> dict:
    body = soup.select_one("main") or soup.select_one("article") or soup.body or soup
    text = _compact_text(body)
    defense = _between(text, "DEFENSE", "OFFENSE")
    offense = _between(text, "OFFENSE", "STATISTICS")
    statistics = _between(text, "STATISTICS", "SPECIAL ABILITIES", "ECOLOGY", "Section 15")
    prefix = text.split("DEFENSE", 1)[0]
    if not defense or not offense or not statistics:
        return {"source_url": url, "parse_warning": "No complete creature stat block found."}

    ability_match = re.search(
        r"Str\s+([+−–-]?\d+|—),?\s+Dex\s+([+−–-]?\d+|—),?\s+"
        r"Con\s+([+−–-]?\d+|—),?\s+Int\s+([+−–-]?\d+|—),?\s+"
        r"Wis\s+([+−–-]?\d+|—),?\s+Cha\s+([+−–-]?\d+|—)",
        statistics,
        re.I,
    )
    abilities = {}
    if ability_match:
        for key, raw in zip(("str", "dex", "con", "int", "wis", "cha"), ability_match.groups()):
            if raw != "—":
                abilities[key] = int(raw.replace("−", "-").replace("–", "-"))

    identity_match = re.search(
        r"\b(?:[A-Z]{1,2})\s+(Fine|Diminutive|Tiny|Small|Medium|Large|Huge|Gargantuan|Colossal)\s+([A-Za-z ]+?)\s+Init\b",
        prefix,
    )
    size = identity_match.group(1) if identity_match else ""
    creature_type = identity_match.group(2).strip() if identity_match else ""
    ac_breakdown = _match(defense, r"AC\s+[-+]?\d+.*?\((.*?)\)\s*hp\b")
    natural_armor = _number(ac_breakdown, r"([+−–-]?\d+)\s+natural") or 0
    if not size:
        size_bonus = _number(ac_breakdown, r"([+−–-]?\d+)\s+size")
        size = {8: "Fine", 4: "Diminutive", 2: "Tiny", 1: "Small", 0: "Medium", -1: "Large"}.get(
            size_bonus, ""
        )
    if not creature_type:
        creature_type = "Vermin" if "int" not in abilities else "Animal"
    result = {
        "source_url": url,
        "size": size,
        "creature_type": creature_type,
        "initiative": _number(prefix, r"\bInit\s+([+−–-]?\d+)"),
        "senses": _match(prefix, r"\bSenses\s+(.+?)(?:;\s*Perception|\s+DEFENSE)"),
        "perception": _number(prefix, r"\bPerception\s+([+−–-]?\d+)"),
        "armor_class": _number(defense, r"\bAC\s+([+−–-]?\d+)"),
        "touch_ac": _number(defense, r"\btouch\s+([+−–-]?\d+)"),
        "flat_footed_ac": _number(defense, r"\bflat-footed\s+([+−–-]?\d+)"),
        "natural_armor": natural_armor,
        "base_hp": _number(defense, r"\bhp\s+(\d+)"),
        "hit_dice": _match(defense, r"\bhp\s+\d+\s*\(([^)]+)\)"),
        "fortitude": _number(defense, r"\bFort\s+([+−–-]?\d+)"),
        "reflex": _number(defense, r"\bRef\s+([+−–-]?\d+)"),
        "will": _number(defense, r"\bWill\s+([+−–-]?\d+)"),
        "speed": _match(offense, r"\bSpeed\s+(.+?)(?=\s+(?:Melee|Ranged|Space|Reach|Special Attacks)\b|$)"),
        "melee": _match(offense, r"\bMelee\s+(.+?)(?=\s+(?:Ranged|Space|Reach|Special Attacks)\b|$)"),
        "ranged": _match(offense, r"\bRanged\s+(.+?)(?=\s+(?:Melee|Space|Reach|Special Attacks)\b|$)"),
        "abilities": abilities,
        "base_attack": _number(statistics, r"\bBase Atk\s+([+−–-]?\d+)"),
        "cmb": _match(statistics, r"\bCMB\s+(.+?)(?=;\s*CMD\b)"),
        "cmd": _match(statistics, r"\bCMD\s+(.+?)(?=\s+(?:Feats|Skills|Languages|SQ)\b|$)"),
        "feats": _match(statistics, r"\bFeats\s+(.+?)(?=\s+(?:Skills|Languages|SQ)\b|$)"),
        "skills": _match(statistics, r"\bSkills\s+(.+?)(?=\s+(?:Languages|SQ|SPECIAL ABILITIES)\b|$)"),
        "special_qualities": _match(statistics, r"\bSQ\s+(.+)$"),
    }
    return {key: value for key, value in result.items() if value not in (None, "", {})}


def _index_entries() -> list[dict]:
    soup = _fetch(INDEX_URL)
    table = next(
        table for table in soup.find_all("table")
        if "Familiar" in [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
    )
    entries = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        raw_name = cells[0].get_text(" ", strip=True).replace("*", "").strip()
        link = cells[0].find("a", href=True)
        url = URL_CORRECTIONS.get(raw_name) or (
            urljoin(INDEX_URL, link["href"]) if link else ""
        )
        entries.append({
            "key": _slug(raw_name),
            "name": raw_name,
            "source_url": url,
            "familiar_special": cells[1].get_text(" ", strip=True),
            "source": cells[2].get_text(" ", strip=True),
            "ruleset": "Pathfinder",
        })
    return entries


def build_catalog() -> dict:
    entries = _index_entries()
    for extra in EXTRA_FORMS:
        entries.append({
            "key": _slug(extra["name"]),
            "name": extra["name"],
            "source_url": extra["url"],
            "familiar_special": extra["special"],
            "source": extra["source"],
            "ruleset": extra["ruleset"],
        })

    urls = sorted({entry["source_url"] for entry in entries if entry.get("source_url")})
    parsed: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                parsed[url] = _statblock(future.result(), url)
            except Exception as error:  # noqa: BLE001 - importer records failures for audit
                parsed[url] = {"source_url": url, "parse_warning": str(error)}
    for entry in entries:
        entry.update(parsed.get(entry.get("source_url", ""), {}))
        if "abilities" not in entry:
            used = re.search(r"use\s+(.+?)\s+statistics", entry["name"], re.I)
            if used:
                target_name = used.group(1).strip().casefold()
                target = next(
                    (
                        candidate for candidate in entries
                        if candidate["name"].casefold() == target_name
                        or candidate["name"].casefold().startswith(target_name + ",")
                    ),
                    None,
                )
                if target is not None:
                    inherited = parsed.get(target.get("source_url", ""), {})
                    entry.update({key: value for key, value in inherited.items() if key != "source_url"})
                    entry.pop("parse_warning", None)
        entry["key"] = _slug(entry["name"])
    unique: dict[str, dict] = {}
    for entry in entries:
        existing = unique.get(entry["key"])
        if existing is None or (
            "abilities" not in existing and "abilities" in entry
        ):
            unique[entry["key"]] = entry
    entries = sorted(unique.values(), key=lambda item: item["name"].casefold())
    return {
        "version": 1,
        "source_url": INDEX_URL,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_catalog()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    warnings = [entry for entry in payload["entries"] if entry.get("parse_warning")]
    print(f"Wrote {len(payload['entries'])} familiar forms to {args.output}")
    print(f"Stat-block warnings: {len(warnings)}")
    for entry in warnings:
        print(f"- {entry['name']}: {entry['parse_warning']}")


if __name__ == "__main__":
    main()
