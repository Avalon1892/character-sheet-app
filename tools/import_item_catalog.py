"""Build the app-owned equipment catalog from reviewed local source snapshots.

Pathfinder records are normalized from the open PF1 Foundry compendia and retain
their Paizo source identifiers. Spheres records are extracted from the locally
downloaded Spheres wiki item-family pages. Neither source is needed at runtime.
"""
from __future__ import annotations

import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
import yaml  # type: ignore  # build-only dependency

SOURCE = ROOT / ".item-source" / "packs"
SPHERES = ROOT / ".item-source" / "spheres"
OUTPUT = ROOT / "data" / "pf1e" / "items.json"

PACK_FAMILIES = {
    "items": "Mundane Equipment",
    "weapons-and-ammo": "Weapons & Ammunition",
    "armors-and-shields": "Armor & Shields",
    "ultimate-equipment": "Magic Items",
    "technology": "Technology",
}
SPHERES_FAMILIES = {
    "alchemical-items": "Alchemical Items", "apparatuses-metamagic": "Metamagic Apparatuses",
    "apparatuses": "Apparatuses", "charms": "Charms", "compounds": "Compounds",
    "fabled-items": "Fabled Items", "implements": "Implements",
    "marvelous-items": "Marvelous Items", "radiances": "Radiances",
    "schematics": "Schematics", "scrolls": "Scrolls", "spell-engines": "Spell Engines",
    "spellzones": "Spellzones", "summoning-orbs": "Summoning Orbs",
    "talent-crystals": "Talent Crystals", "weapons": "Weapons & Martial Equipment",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def plain(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        match = re.search(r"[\d,.]+", str(value or ""))
        return float(match.group(0).replace(",", "")) if match else 0.0


def pathfinder_entries() -> list[dict]:
    result: list[dict] = []
    for pack, family in PACK_FAMILIES.items():
        root = SOURCE / pack
        documents = []
        for path in root.rglob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            documents.append((path, data))
        folders = {
            str(data.get("_id")): data for _path, data in documents
            if str(data.get("_key", "")).startswith("!folders!")
        }

        def hierarchy(folder_id: object) -> list[str]:
            labels: list[str] = []
            seen: set[str] = set()
            current = str(folder_id or "")
            while current and current not in seen and current in folders:
                seen.add(current)
                folder = folders[current]
                labels.append(str(folder.get("name", "")))
                current = str(folder.get("folder") or "")
            return list(reversed([label for label in labels if label]))

        for path, data in documents:
            if not str(data.get("_key", "")).startswith("!items!"):
                continue
            system = data.get("system") or {}
            tree = hierarchy(data.get("folder"))
            category = tree[0] if tree else family
            item_family = "Magic Items" if category == "Magic Items" else family
            subcategory = " / ".join(tree[1:]) or str(system.get("subType") or data.get("type") or "General").replace("_", " ").title()
            description_data = system.get("description") or {}
            description = plain(description_data.get("value") or description_data.get("unidentified"))
            armor = system.get("armor") or {}
            source_ids = [str(source.get("id", "")) for source in system.get("sources", []) if source.get("id")]
            item_type = str(data.get("type") or "")
            bonus_type = ""
            if system.get("subType") == "armor":
                bonus_type = "shield" if "shield" in str(system.get("equipmentSubtype", "")).casefold() else "armor"
            if "shield" in category.casefold():
                bonus_type = "shield"
            action = next(iter((system.get("actions") or {}).values()), {})
            damage_part = next(iter(((action.get("damage") or {}).get("parts") or [])), {})
            formula = str(damage_part.get("formula") or "")
            dice_match = re.search(r"sizeRoll\((\d+)\s*,\s*(\d+)", formula)
            damage_dice = f"{dice_match.group(1)}d{dice_match.group(2)}" if dice_match else ""
            critical_range = int((action.get("ability") or {}).get("critRange") or 20)
            critical_multiplier = int((action.get("ability") or {}).get("critMult") or 2)
            attack_type = "Ranged" if str(action.get("actionType")) in {"rwak", "twak"} else "Melee"
            weapon = {
                "damage_dice": damage_dice,
                "damage_type": ", ".join(str(value) for value in damage_part.get("types", ())),
                "critical": f"{critical_range}-20/x{critical_multiplier}" if critical_range < 20 else f"20/x{critical_multiplier}",
                "range": (
                    str((action.get("range") or {}).get("value") or "")
                    if attack_type == "Ranged" else "Melee"
                ),
                "attack_type": attack_type,
            } if item_type in {"weapon", "ammo"} else {}
            result.append({
                "key": f"pathfinder:{pack}:{data.get('_id')}", "name": str(data.get("name", "Unnamed item")),
                "source_group": "Pathfinder", "family": item_family, "category": category,
                "subcategory": subcategory, "description": description,
                "source": ", ".join(source_ids) or "Pathfinder 1e", "source_url": "https://www.aonprd.com/Equipment.aspx",
                "price_gp": number(system.get("price")), "weight_lb": number((system.get("weight") or {}).get("value")),
                "slot": str(system.get("slot") or ""), "item_type": item_type,
                "weapon": weapon,
                "automation": {
                    "ac_bonus": int(number(armor.get("value"))), "bonus_type": bonus_type,
                    "max_dex_bonus": int(number(armor.get("dex"))) if armor.get("dex") is not None else None,
                    "armor_check_penalty": int(number(armor.get("acp"))), "spell_failure": int(number(system.get("spellFailure"))),
                },
            })
    return result


class PageItems(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.in_heading = False
        self.heading_tag = ""
        self.heading: list[str] = []
        self.current: dict | None = None
        self.entries: list[dict] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "div" and values.get("id") == "page-content": self.depth = 1
        elif self.depth and tag == "div": self.depth += 1
        if self.depth and tag in {"h2", "h3", "h4"} and values.get("id", "").startswith("toc"):
            self._finish()
            self.in_heading, self.heading_tag, self.heading = True, tag, []

    def handle_endtag(self, tag: str) -> None:
        if self.in_heading and tag == self.heading_tag:
            title = plain("".join(self.heading))
            self.current = {"name": title, "level": self.heading_tag, "text": []}
            self.in_heading = False
        if self.depth and tag == "div": self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_heading: self.heading.append(data)
        elif self.depth and self.current is not None: self.current["text"].append(data)

    def _finish(self) -> None:
        if self.current:
            self.current["description"] = plain(" ".join(self.current.pop("text")))
            self.entries.append(self.current)
        self.current = None

    def close(self) -> None:
        super().close(); self._finish()


def spheres_entries() -> list[dict]:
    result: list[dict] = []
    generic = {"contents", "navigation", "references", "faq", "new items", "other items"}
    for stem, family in SPHERES_FAMILIES.items():
        path = SPHERES / f"{stem}.html"
        if not path.exists(): continue
        parser = PageItems(); parser.feed(path.read_text(encoding="utf-8", errors="ignore")); parser.close()
        levels = {"h3"}
        if stem in {"fabled-items", "summoning-orbs", "spellzones"}: levels.add("h4")
        seen: set[str] = set()
        for item in parser.entries:
            name = re.sub(r"\s*\[[^]]+\]\s*$", "", item["name"]).strip()
            if item["level"] not in levels or len(name) < 3 or name.casefold() in generic or name.casefold().startswith("faq"):
                continue
            key = f"spheres:{stem}:{slug(name)}"
            if key in seen: continue
            seen.add(key)
            description = item.get("description", "")
            price_match = re.search(r"(?:Price|Cost)\s*[:—-]?\s*([\d,]+)\s*gp", description, re.I)
            result.append({
                "key": key, "name": name, "source_group": "Spheres", "family": family,
                "category": "Magic Items" if stem != "weapons" else "Martial Equipment",
                "subcategory": family, "description": description, "source": "Spheres of Power Wiki",
                "source_url": f"https://spheresofpower.wikidot.com/{stem}",
                "price_gp": float(price_match.group(1).replace(",", "")) if price_match else 0.0,
                "weight_lb": 0.0, "slot": "", "item_type": "spheres-item", "automation": {},
            })
    return result


def main() -> None:
    entries = pathfinder_entries() + spheres_entries()
    entries.sort(key=lambda item: (item["source_group"], item["family"], item["name"].casefold(), item["key"]))
    OUTPUT.write_text(json.dumps({"version": 1, "entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {group: sum(1 for item in entries if item["source_group"] == group) for group in ("Pathfinder", "Spheres")}
    print(f"Wrote {len(entries)} items to {OUTPUT} ({counts})")


if __name__ == "__main__": main()
