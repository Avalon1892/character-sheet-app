"""Build-time Marvelous Item import into existing equipment/crafting catalogs.

Accept a reviewed UTF-8 HTML snapshot on stdin; no runtime network or prose rules.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.import_reference_catalog import BeautifulSoup
from tools.catalog_import_common import slug
from tools.import_crafting_catalog import money


def parse_page(raw, stem):
    soup = BeautifulSoup(raw, "html.parser")
    content = soup.find(id="page-content")
    if content is None:
        raise ValueError("Missing page content.")
    entries, recipes, seen = [], [], set()
    for heading in content.find_all("h3"):
        nodes = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in {"h1", "h2", "h3"}:
                break
            nodes.append(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
        text = re.sub(r"\s+", " ", " ".join(nodes)).strip()
        title = heading.get_text(" ", strip=True)
        construction = re.search(r'\bConstruction Requirements\b\s*|\bConstruction\s+(?=(?:Craft|Forge|Brew|Scribe|Mythic)\b)', text)
        has_construction = construction is not None
        artifact = bool(re.search(r'\((?:Minor|Major) Artifact\)', title, re.I))
        if not has_construction and not artifact:
            continue
        name = re.sub(r"\s*\[[^]]+\]\s*$", "", title).strip()
        key = f"spheres:{stem}:{slug(name)}"
        # Current tab appears first; preserve a distinct legacy record when its
        # published text differs instead of silently substituting either version.
        if key in seen:
            key += ":original"
        if key in seen:
            raise ValueError(f"Duplicate source identity: {key}")
        seen.add(key)
        requirements = text[construction.end():].strip() if construction else ''
        metadata = text.replace(' — ', '; ')
        cost_match = re.search(r"\bCost\s+(.+)$", requirements)
        cost = money(cost_match[1]) if cost_match else None
        price_match = re.search(r"\bPrice\s+([^;]+)", metadata)
        price = money(price_match[1]) if price_match else None
        cl = re.search(r"\bCL\s+(\d+)", text)
        slot = re.search(r"\bSlot\s+([^;]+)", metadata)
        weight = re.search(r"\bWeight\s+(\d+(?:\.\d+)?)\s*(?:lbs?\.?|pounds)", text)
        url = f"https://spheresofpower.wikidot.com/{stem}"
        entry = dict(key=key, name=name + (" (Original)" if key.endswith(":original") else ""),
            source_group="Spheres", family="Marvelous Items", category="Magic Items",
            subcategory="Marvelous Items", description=text, source=title,
            source_url=url, price_gp=price or 0, weight_lb=float(weight[1]) if weight else 0,
            slot=slot[1].strip() if slot else "", item_type="spheres-item", automation={},
            rules_version="Original" if key.endswith(":original") else "Current")
        entries.append(entry)
        if not has_construction:
            entry['subcategory'] = 'Artifacts'
            entry['artifact'] = True
            continue
        feats = [feat for feat in ("Craft Marvelous Item", "Craft Wondrous Item", "Craft Apparatus",
                 "Forge Charm", "Craft Implement Of Power", "Mythic Crafter") if feat.casefold() in requirements.casefold()]
        feats = list(dict.fromkeys("Craft Marvelous Item" if f == "Craft Wondrous Item" else f for f in feats))
        variable = "scaling wonder" in text.casefold() or (price is not None and cost is not None and cost > price)
        recipes.append(dict(key="craft:" + key, item_key=key, name=entry["name"],
            kind="magic", system="spheres", feats=feats, spells=[],
            requirements=requirements, review="Sphere/talent and special prerequisites require explicit verification.",
            caster_level=int(cl[1]) if cl else None, creation_cost_gp=None if variable else cost,
            price_gp=None if variable else price, category="Marvelous Items", source_url=url,
            description=text, rules_version=entry["rules_version"]))
    if not entries:
        raise ValueError("No Marvelous Items parsed; refusing an empty import.")
    return entries, recipes


def merge_records(existing, updates):
    result = {row["key"]: row for row in existing}
    for row in updates:
        # Retain reviewed automation on existing identities.
        result[row["key"]] = {**result.get(row["key"], {}), **row,
                              "automation": result.get(row["key"], {}).get("automation", row.get("automation", {}))}
    return list(result.values())


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("stem", choices=("marvelous-items", "marvelous-items-2"))
    args = parser.parse_args()
    entries, recipes = parse_page(sys.stdin.read(), args.stem)
    item_path = ROOT / "data/pf1e/items.json"
    craft_path = ROOT / "data/pf1e/crafting_catalog.json"
    items = json.loads(item_path.read_text(encoding="utf-8"))
    crafting = json.loads(craft_path.read_text(encoding="utf-8"))
    items["entries"] = merge_records(items["entries"], entries)
    crafting["entries"] = merge_records(crafting["entries"], entries)
    crafting["recipes"] = merge_records(crafting["recipes"], recipes)
    payloads = [(path, json.dumps(document, ensure_ascii=False, indent=2).replace("\n", "\r\n" if b"\r\n" in path.read_bytes() else "\n").encode("utf-8"))
                for path, document in ((item_path, items), (craft_path, crafting))]
    for path, payload in payloads:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
    manifest_path = ROOT / "data/pf1e/catalog_manifest.json"
    manifest = manifest_path.read_text(encoding="utf-8")
    for path, payload in payloads:
        record = dict(path=path.name, sha256=hashlib.sha256(payload).hexdigest(), size=len(payload))
        manifest = re.sub(r'\{"path": "' + re.escape(path.name) + r'"[^}]*\}', json.dumps(record), manifest)
    manifest_path.write_text(manifest, encoding="utf-8", newline="\n")
    print(f"Imported {len(entries)} entries and {len(recipes)} recipes from {args.stem}.")


if __name__ == "__main__":
    main()
