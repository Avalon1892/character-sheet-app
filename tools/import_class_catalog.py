"""Normalize first-party playable Pathfinder classes and their level features."""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
import yaml  # type: ignore

CLASS_ROOT = ROOT / ".item-source" / "packs" / "classes"
ABILITY_ROOT = ROOT / ".item-source" / "packs" / "class-abilities"
OUTPUT = ROOT / "data" / "pf1e" / "pathfinder_classes.json"
NPC = {"adept", "aristocrat", "commoner", "expert", "warrior"}
GROUPS = {
    "Core Classes": {"barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin", "ranger", "rogue", "sorcerer", "wizard"},
    "Base Classes": {"alchemist", "cavalier", "inquisitor", "oracle", "summoner", "witch", "gunslinger", "magus"},
    "Alternate Classes": {"antipaladin", "ninja", "samurai"},
    "Hybrid Classes": {"arcanist", "bloodrager", "brawler", "hunter", "investigator", "shaman", "skald", "slayer", "swashbuckler", "warpriest"},
    "Occult Classes": {"kineticist", "medium", "mesmerist", "occultist", "psychic", "spiritualist"},
    "Unchained Classes": {"barbarian-unchained", "monk-unchained", "rogue-unchained", "summoner-unchained"},
    "Later Classes": {"shifter", "vigilante"},
}
SKILLS = {
    "acr":"Acrobatics", "apr":"Appraise", "art":"Artistry", "blf":"Bluff", "clm":"Climb", "crf":"Craft",
    "dip":"Diplomacy", "dev":"Disable Device", "dis":"Disguise", "esc":"Escape Artist", "fly":"Fly",
    "han":"Handle Animal", "hea":"Heal", "int":"Intimidate", "kar":"Knowledge (Arcana)", "kdu":"Knowledge (Dungeoneering)",
    "ken":"Knowledge (Engineering)", "kge":"Knowledge (Geography)", "khi":"Knowledge (History)", "klo":"Knowledge (Local)",
    "kna":"Knowledge (Nature)", "kno":"Knowledge (Nobility)", "kpl":"Knowledge (Planes)", "kre":"Knowledge (Religion)",
    "lin":"Linguistics", "lor":"Lore", "per":"Perception", "prf":"Perform", "pro":"Profession", "rid":"Ride",
    "sen":"Sense Motive", "slt":"Sleight of Hand", "spl":"Spellcraft", "ste":"Stealth", "sur":"Survival", "swm":"Swim", "umd":"Use Magic Device",
}


def plain(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def category(stem: str) -> str:
    return next((group for group, names in GROUPS.items() if stem in names), "Other Playable Classes")


def skill_key(code: str) -> str:
    name = SKILLS.get(code, code)
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")


def main() -> None:
    abilities: dict[str, dict] = {}
    for path in ABILITY_ROOT.rglob("*.yaml"):
        try: data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception: continue
        if str(data.get("_key", "")).startswith("!items!"):
            abilities[str(data.get("_id"))] = data
    entries = []
    for path in CLASS_ROOT.glob("*.yaml"):
        stem = path.name.split(".", 1)[0]
        if stem in NPC: continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        system = data.get("system") or {}
        if data.get("type") != "class" or system.get("subType") != "base": continue
        features = []
        for link in (system.get("links") or {}).get("supplements", []):
            feature_id = str(link.get("uuid", "")).rsplit(".", 1)[-1]
            feature = abilities.get(feature_id)
            if not feature: continue
            feature_system = feature.get("system") or {}
            description_data = feature_system.get("description") or {}
            features.append({
                "level": int(link.get("level") or 1), "name": str(feature.get("name") or "Class Feature"),
                "description": plain(description_data.get("value") or description_data.get("unidentified") or description_data.get("summary")),
            })
        sources = [str(value.get("id")) for value in system.get("sources", []) if value.get("id")]
        casting = system.get("casting") or {}
        entries.append({
            "key": f"pathfinder-class:{stem}", "name": str(data.get("name")), "category": category(stem),
            "description": plain((system.get("description") or {}).get("value")),
            "summary": plain((system.get("description") or {}).get("summary")),
            "hit_die": int(system.get("hd") or 0),
            "bab": {"high":"Full", "med":"3/4", "low":"1/2"}.get(str(system.get("bab")), str(system.get("bab") or "")),
            "fort": "Good" if ((system.get("savingThrows") or {}).get("fort") or {}).get("value") == "high" else "Poor",
            "reflex": "Good" if ((system.get("savingThrows") or {}).get("ref") or {}).get("value") == "high" else "Poor",
            "will": "Good" if ((system.get("savingThrows") or {}).get("will") or {}).get("value") == "high" else "Poor",
            "skill_points": int(system.get("skillsPerLevel") or 0),
            "class_skill_keys": [skill_key(value) for value in system.get("classSkills", [])],
            "class_skills": [SKILLS.get(value, value) for value in system.get("classSkills", [])],
            "armor_proficiencies": list(system.get("armorProf", [])), "weapon_proficiencies": list(system.get("weaponProf", [])),
            "casting": {"ability": casting.get("ability", ""), "progression": casting.get("progression", ""), "type": casting.get("type", ""), "spells": casting.get("spells", ""), "caster_level_offset": int(casting.get("offset") or 0)},
            "features": sorted(features, key=lambda feature: (feature["level"], feature["name"])),
            "source": ", ".join(sources) or "Pathfinder RPG", "source_url": "https://www.aonprd.com/Classes.aspx",
        })
    entries.sort(key=lambda entry: (entry["category"], entry["name"]))
    OUTPUT.write_text(json.dumps({"version": 1, "entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(entries)} playable Pathfinder classes to {OUTPUT}")


if __name__ == "__main__": main()
