"""Import missing Paladin options into the existing catalogs (build time only)."""
from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".tools-deps")]
from bs4 import BeautifulSoup
from tools.import_archetype_catalog import html_text, slug
from app.class_feature_rules import archetype_granted_features
from tools.build_target_class_packages import _structured_feature, _removed_feature_clauses

BASE = "https://www.aonprd.com/"
DATA = ROOT / "data" / "pf1e"


def page(url):
    request = Request(quote(url, safe=":/?=&%"), headers={"User-Agent": "Mozilla/5.0 Character Sheet catalog importer"})
    with urlopen(request, timeout=60) as response:
        return BeautifulSoup(response.read().decode("utf-8"), "html.parser")


def option_entries(path, family, default_level):
    url = BASE + path
    soup = page(url)
    entries = []
    for span in soup.select('span[id*="LabelName_"]'):
        title = span.find("b")
        if not title:
            continue
        name = title.get_text(" ", strip=True)
        source = span.select_one("a.external-link")
        text = span.get_text(" ", strip=True)
        description = text.split("):", 1)[1].strip()
        heading = span.find_previous("h2", class_="title")
        match = re.match(r"(\d+)", heading.get_text() if heading else "")
        level = int(match[1]) if match else default_level
        prerequisites = re.findall(r"must have the ([a-z]+) mercy", description, re.I)
        entries.append({
            "key": f"class-power:{family}:{slug(name)}", "family": family,
            "category": f"Level {level}", "name": name, "description": description,
            "classes": ["Paladin"], "minimum_level": level,
            "prerequisite_names": ["Fatigued" if name.casefold() == "fatigue" else name.title() for name in prerequisites],
            "repeatable": False, "activatable": False, "automatic_modifiers": [],
            "source": source.get_text(" ", strip=True) if source else "Pathfinder RPG",
            "source_url": url,
        })
    if not entries:
        raise ValueError(f"No Paladin options found at {url}")
    return entries


def oath_entries():
    soup = page(BASE + "PaladinOaths.aspx")
    entries = []
    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            continue
        link = cells[0].find("a", href=re.compile("OathDisplay"))
        if not link:
            continue
        name = link.get_text(" ", strip=True)
        url = urljoin(BASE, link["href"])
        detail = page(url).select_one('span[id*="LabelName_0"]')
        if detail is None:
            raise ValueError(f"Missing oath description: {name}")
        description = html_text(str(detail))
        # AoN's older oath pages contain replacement characters in punctuation.
        description = re.sub(r"(?<=\w)�(?=(?:s\b|t\b))", "’", description)
        description = re.sub(r"(\d+(?:st|nd|rd|th))�", r"\1—", description)
        description = description.replace("equals�to", "equals—to")
        entry = {
            "key": f"pathfinder-archetype:pathfinder-class:paladin:{slug(name)}",
            "class_key": "pathfinder-class:paladin", "class_name": "Paladin",
            "name": name, "source_group": "Pathfinder", "category": "Oath",
            "replaces": cells[1].get_text(" ", strip=True),
            "summary": cells[2].get_text(" ", strip=True),
            "description": description, "source_url": url,
            "source": "Pathfinder RPG (see description for publication)",
        }
        entry["features"] = [_structured_feature(feature) for feature in archetype_granted_features(entry, 20)]
        entry["features"] = [feature for feature in entry["features"]
                             if feature["name"] not in {name, "Deities", "Possessed"}]
        levels = {"Order of Good": 4, "Channel Wrath": 4, "Divine Bond": 5}
        for feature in entry["features"]:
            feature["level"] = levels.get(feature["name"], feature["level"])
        entry["removed_feature_clauses"] = list(_removed_feature_clauses(tuple(entry["features"])))
        entry["removed_features"] = entry["removed_feature_clauses"]
        entries.append(entry)
    if len(entries) != 15:
        raise ValueError(f"Expected 15 Paladin oaths, found {len(entries)}")
    by_name = {entry["name"]: entry for entry in entries}
    for child_name, parent_name, excluded in (
        ("Oath against the Whispering Way", "Oath against Undeath", {"Aura of Life"}),
        ("Oath of the Mendevian Crusade", "Oath against Fiends", set()),
    ):
        child, parent = by_name[child_name], by_name[parent_name]
        own = {feature["name"] for feature in child["features"]}
        child["features"] += [dict(feature) for feature in parent["features"]
                              if feature["name"] not in own | excluded]
        for field in ("removed_feature_clauses", "removed_features"):
            child[field] = list(dict.fromkeys(child[field] + parent[field]))
    return entries


def merge(path, entries):
    document = json.loads(path.read_text("utf-8"))
    by_key = {entry["key"]: entry for entry in document["entries"]}
    by_key.update({entry["key"]: entry for entry in entries})
    document["entries"] = list(by_key.values())
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8")


def complete_class_rules():
    soup = page(BASE + "ClassDisplay.aspx?ItemName=Paladin")
    document = json.loads((DATA / "pathfinder_classes.json").read_text("utf-8"))
    entry = next(entry for entry in document["entries"] if entry["key"] == "pathfinder-class:paladin")
    heading = next(node for node in soup.find_all("b") if node.get_text().startswith("Divine Bond ("))
    fragments = []
    for node in heading.next_siblings:
        if getattr(node, "name", None) == "h2" or (
            getattr(node, "name", None) == "b" and node.get_text().startswith("Aura of Resolve")
        ):
            break
        fragments.append(str(node))
    description = html_text("".join(fragments)).lstrip(": ")
    description = re.sub("\ufffd(?=\\d)", "−", description)
    if "mount" not in description or len(description) < 3000:
        raise ValueError("Divine Bond source is incomplete")
    for feature in entry["features"]:
        if feature["name"] == "Divine Bond":
            feature["description"] = description
    return entry


def update_manifest():
    path = DATA / "catalog_manifest.json"
    text = path.read_text("utf-8")
    text = re.sub(r'"catalog_version": "[^"]+"', '"catalog_version": "2026.09.27.1"', text)
    text = re.sub(r'"created_utc": "[^"]+"', '"created_utc": "2026-09-27T00:00:00Z"', text)
    for filename in ("class_powers.json", "archetypes.json", "pathfinder_classes.json"):
        content = (DATA / filename).read_bytes()
        record = {"path": filename, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        text = re.sub(r'\{"path": "' + re.escape(filename) + r'"[^}]*\}', json.dumps(record), text)
    path.write_text(text, "utf-8", newline="\n")


def main():
    # Fetch and validate everything before changing any bundled data.
    mercies = option_entries("PaladinMercies.aspx", "paladin_mercy", 3)
    bonds = option_entries("PaladinDivineBonds.aspx", "paladin_divine_bond", 5)
    oaths = oath_entries()
    paladin = complete_class_rules()
    merge(DATA / "class_powers.json", mercies + bonds)
    merge(DATA / "archetypes.json", oaths)
    merge(DATA / "pathfinder_classes.json", [paladin])
    update_manifest()
    print(f"Imported {len(mercies)} mercies, {len(bonds)} variant bonds, {len(oaths)} oaths.")


if __name__ == "__main__":
    main()
