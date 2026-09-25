"""Resumable, rate-limited import of the Archives of Nethys PF1 creature indexes.

Only this offline tool parses published stat blocks. Runtime code uses the bundled
catalog, and never downloads pages or interprets descriptions as automation rules.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urljoin, urlsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
INDEXES = {
    "Monster": "https://aonprd.com/Monsters.aspx?Letter=All",
    "Unique": "https://aonprd.com/Monsters.aspx?Letter=Unique",
    "NPC": "https://aonprd.com/NPCs.aspx?SubGroup=All",
    "Mythic": "https://aonprd.com/MythicMonsters.aspx?Letter=All",
}
TYPES = ("aberration", "animal", "construct", "dragon", "fey", "humanoid",
         "magical beast", "monstrous humanoid", "ooze", "outsider", "plant", "undead", "vermin")
SIZES = ("Fine", "Diminutive", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan", "Colossal")


def compact(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def canonical_url(value: str) -> str:
    parts = urlsplit(urljoin("https://aonprd.com/", value))
    return "https://aonprd.com" + parts.path + "?" + urlencode(sorted(parse_qsl(parts.query)))


def parse_index(document: str, kind: str) -> list[dict]:
    soup = BeautifulSoup(document, "html.parser")
    entries = []
    for link in soup.find_all("a", href=re.compile(r"(?:Monster|NPC)Display\.aspx", re.I)):
        row = link.find_parent("tr")
        cells = row.find_all("td", recursive=False) if row else []
        if len(cells) < (3 if kind == "NPC" else 4):
            continue
        values = [compact(cell) for cell in cells]
        url = canonical_url(link["href"])
        entries.append({"key": "creature:" + hashlib.sha256(url.encode()).hexdigest()[:20],
                        "name": compact(link), "source_url": url, "kinds": [kind],
                        "cr": values[1], "type": "Unknown" if kind == "NPC" else values[-2],
                        "environment": "Unknown" if kind == "NPC" else values[-1],
                        "class_levels": values[2] if kind == "NPC" else ""})
    if not entries:
        raise ValueError(f"No creature links found in {kind} index")
    return entries


def _field(label: Tag) -> str:
    parts = []
    for sibling in label.next_siblings:
        if isinstance(sibling, Tag) and sibling.name in {"br", "b", "strong", "h1", "h2", "h3"}:
            break
        parts.append(compact(sibling) if isinstance(sibling, Tag) else str(sibling))
    return " ".join(" ".join(parts).split()).strip(" ;,")


def _tag_parts(value: str) -> list[str]:
    """Split stat-line lists without separating parameters inside parentheses."""
    parts, start, depth = [], 0, 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        elif character in ",;" and not depth:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part and part.casefold() not in {"none", "—", "-"}]


def ability_tags(block: Tag, labels: dict[str, str]) -> dict[str, list[str]]:
    """Index explicit mechanical fields, not incidental mentions in rules prose."""
    groups: dict[str, list[str]] = {}

    def add(group, text, prefix=""):
        values = groups.setdefault(group, [])
        for value in _tag_parts(text):
            tag = prefix + value
            if tag.casefold() not in {existing.casefold() for existing in values}:
                values.append(tag)

    # Regeneration/fast healing normally live after the hit-point total.
    for value in _tag_parts(labels.get("hp", ""))[1:]:
        if not re.match(r"^[\d(]", value):
            add("Recovery", value)
    for field in ("regeneration", "fast healing"):
        if labels.get(field):
            add("Recovery", labels[field], field + " ")
    for field, prefix in (("defensive abilities", ""), ("dr", "Damage reduction (DR): "),
                          ("sr", "Spell resistance (SR): "), ("immune", "Immune / immunities: "),
                          ("resist", "Resistance: ")):
        add("Defenses", labels.get(field, ""), prefix)
    add("Weaknesses", labels.get("weaknesses", ""))
    senses = re.split(r"\b(?:Perception|Listen|Spot)\s+[+−–-]?\d", labels.get("senses", ""), maxsplit=1, flags=re.I)[0]
    add("Senses", senses)
    for group, field in (("Auras", "aura"), ("Offensive abilities", "special attacks"),
                         ("Special qualities", "sq"), ("Movement", "speed")):
        add(group, labels.get(field, ""))
    for label in block.find_all(["b", "strong"]):
        name = compact(label)
        if re.search(r"\((?:Ex|Su|Sp)\)", name):
            add("Named abilities", name)
        if re.search(r"spells (?:known|prepared)|spell-like abilities|psychic magic|extracts prepared", name, re.I):
            add("Spellcasting", name)
            # Spell names are italicized in the casting section. Stop at the
            # next stat label/section, so gear and descriptive prose are excluded.
            for sibling in label.next_siblings:
                if isinstance(sibling, Tag):
                    if sibling.name in {"b", "strong", "h1", "h2", "h3", "h4"}:
                        break
                    for spell in ([sibling] if sibling.name == "i" else sibling.find_all("i")):
                        add("Spellcasting", compact(spell))
    return {group: values for group, values in groups.items() if values}


def parse_creature(document: str, seed: dict) -> dict:
    soup = BeautifulSoup(document, "html.parser")
    block = soup.find(id=re.compile(r"MainContent_DataList(?:Feats|NPCs)_Label1_0$"))
    if block is None:
        raise ValueError("Missing published creature stat block")
    for heading in block.find_all("h1"):
        if compact(heading).startswith('Creatures in "'):
            for sibling in list(heading.next_siblings):
                sibling.extract()
            heading.extract()
            break
    # Keep the game statistics and ability mechanics, not setting lore or art.
    description = next((h for h in block.find_all(["h2", "h3"]) if compact(h) == "Description"), None)
    if description:
        for sibling in list(description.next_siblings):
            sibling.extract()
        description.extract()
    first_stat_heading = block.find("h2")
    if first_stat_heading:
        for sibling in list(first_stat_heading.previous_siblings):
            if not isinstance(sibling, Tag) or sibling.name != "h1":
                sibling.extract()
    labels = {compact(label).casefold().rstrip(":"): _field(label)
              for label in block.find_all(["b", "strong"])}
    if not {"ac", "hp"} <= labels.keys():
        raise ValueError("Stat block lacks AC or hit points")
    text = compact(block)
    entry = dict(seed)
    try:
        entry["cr_value"] = float(Fraction(seed["cr"]))
    except (ValueError, ZeroDivisionError):
        entry["cr_value"] = None
    xp = re.match(r"[\d,]+", labels.get("xp", ""))
    entry["xp"] = int(xp[0].replace(",", "")) if xp else None
    entry["source"] = labels.get("source", "Archives of Nethys")
    entry["environment"] = labels.get("environment") or seed["environment"]
    identity = text.split("Defense", 1)[0]
    type_text = (identity if seed["type"] == "Unknown" else seed["type"]).casefold()
    entry["type"] = next((t for t in sorted(TYPES, key=len, reverse=True)
                           if re.search(r"\b" + t + r"\b", type_text)), seed["type"])
    # Alignment and size are on the identity line before Defense, not in prose.
    size_match = re.search(r"\b(" + "|".join(SIZES) + r")\b", identity)
    entry["size"] = size_match[0] if size_match else "Unknown"
    alignment = re.search(r"\b(LG|NG|CG|LN|N|CN|LE|NE|CE)\s+(?:" + "|".join(SIZES) + ")", identity)
    entry["alignment"] = alignment[1] if alignment else "Unknown"
    type_match = re.search(r"\b" + re.escape(entry["type"]) + r"\s*\(([^)]+)\)", identity, re.I)
    entry["subtypes"] = [s.strip() for s in type_match[1].split(",")] if type_match else []
    entry["roles"] = [role for role, label in (("Melee", "melee"), ("Ranged", "ranged"))
                      if labels.get(label) and labels[label] not in {"—", "-", "none"}]
    if any(re.search(r"spells (?:known|prepared)|spell-like abilities|psychic magic|extracts prepared", key)
           for key in labels):
        entry["roles"].append("Caster")
    speed = labels.get("speed", "")
    entry["movement"] = [m.title() for m in ("fly", "swim", "climb", "burrow")
                         if re.search(r"\b" + m + r"\b", speed, re.I)]
    if re.match(r"\d", speed):
        entry["movement"].insert(0, "Land")
    entry["speed"] = speed
    entry["ability_tags"] = ability_tags(block, labels)
    entry["defenses"] = "; ".join(tag for group in ("Recovery", "Defenses", "Weaknesses")
                                    for tag in entry["ability_tags"].get(group, ()))
    entry["special_abilities"] = "; ".join(tag for tags in entry["ability_tags"].values() for tag in tags)
    # AoN also indexes unconverted 3.5 blocks: their Grapple statistic replaces
    # PF1's CMB/CMD. Keep them identifiable rather than silently converting XP.
    entry["legacy_35"] = ("grapple" in labels and "cmb" not in labels) or (
        "3.5" in text[:1200] and bool(re.search(r"3\.5.*(?:rules|edition)|(?:rules|edition).*3\.5", text[:1200], re.I)))
    entry["description"] = text
    allowed = {"h1", "h2", "h3", "h4", "b", "strong", "i", "em", "p", "br", "table", "tbody", "tr", "td", "th", "ul", "ol", "li", "sup", "sub", "a", "span"}
    for node in list(block.find_all(True)):
        if node.name in {"script", "style", "iframe", "img", "input"}:
            node.decompose()
        elif node.name not in allowed:
            node.unwrap()
        else:
            href = urljoin(seed["source_url"], node.get("href", "")) if node.name == "a" else ""
            node.attrs = {}
            if href.startswith(("http://", "https://")):
                node["href"] = href
    entry["statblock_html"] = block.decode_contents()
    return entry


class CachedFetcher:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.next_request = 0.0

    def fetch(self, url: str) -> str:
        path = self.folder / (hashlib.sha256(url.encode()).hexdigest() + ".html")
        if path.exists():
            return path.read_text(encoding="utf-8")
        for attempt in range(3):
            with self.lock:
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + 0.3
            try:
                request = Request(url, headers={"User-Agent": "CharacterSheetCatalogImporter/1.0"})
                with urlopen(request, timeout=45) as response:
                    document = response.read().decode("utf-8-sig")
                path.write_text(document, encoding="utf-8", newline="\n")
                return document
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise AssertionError("unreachable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "artifacts/bestiary-source")
    parser.add_argument("--output", type=Path, default=ROOT / "data/pf1e/bestiary.json")
    parser.add_argument("--limit", type=int, default=0, help="Developer sample; never reported as a complete import")
    args = parser.parse_args()
    fetcher = CachedFetcher(args.cache)
    seeds = {}
    index_counts = {}
    for kind, url in INDEXES.items():
        rows = parse_index(fetcher.fetch(url), kind)
        index_counts[kind] = len(rows)
        for row in rows:
            if row["key"] in seeds:
                old = seeds[row["key"]]
                old["kinds"] = sorted(set(old["kinds"] + row["kinds"]))
            else:
                seeds[row["key"]] = row
    print(f"Indexes: {index_counts}; unique pages: {len(seeds)}", flush=True)
    records, failures = [], []
    selected = list(seeds.values())[:args.limit or None]
    def load(seed):
        return parse_creature(fetcher.fetch(seed["source_url"]), seed)
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(load, seed): seed for seed in selected}
        for number, future in enumerate(as_completed(jobs), 1):
            seed = jobs[future]
            try:
                records.append(future.result())
            except Exception as exc:
                failures.append({"name": seed["name"], "url": seed["source_url"], "error": str(exc)})
            if number % 100 == 0:
                print(f"{number}/{len(selected)} read; {len(failures)} failed", flush=True)
    payload = {"schema_version": 1, "imported_on": date.today().isoformat(),
               "sources": INDEXES, "index_counts": index_counts,
               "indexed_unique_pages": len(seeds), "imported_pages": len(records),
               "complete": not failures and len(records) == len(seeds), "failures": failures,
               "license": "Game mechanics are Open Game Content under OGL 1.0a; see bestiary_LICENSE.txt. Publication credits and source links are retained. No artwork or narrative lore is bundled.",
               "entries": sorted(records, key=lambda e: (e["name"].casefold(), e["key"]))}
    output = args.output
    if not payload["complete"] and output == ROOT / "data/pf1e/bestiary.json":
        output = ROOT / "artifacts/bestiary-incomplete.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + ".tmp")
    pending.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    pending.replace(output)
    license_page = BeautifulSoup(fetcher.fetch("https://aonprd.com/Licenses.aspx"), "html.parser")
    license_text = license_page.get_text("\n", strip=True)
    license_text = license_text[license_text.index("OPEN GAME LICENSE Version 1.0a"):]
    output.with_name("bestiary_LICENSE.txt").write_text(
        "Source: https://aonprd.com/Licenses.aspx\nImported game mechanics are Open Game Content. "
        "Names identify the referenced entries; no Product Identity license is claimed.\n\n" + license_text + "\n",
        encoding="utf-8", newline="\n")
    print(f"Wrote {len(records)} creatures to {output}; complete={payload['complete']}; failures={len(failures)}", flush=True)


if __name__ == "__main__":
    main()
