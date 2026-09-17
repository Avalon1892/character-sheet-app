from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))

from bs4 import BeautifulSoup, Tag  # type: ignore[import-not-found]


OUTPUT = ROOT / "data" / "pf1e" / "traditions.json"
MARTIAL_URL = "http://spheresofpower.wikidot.com/martial-traditions"
CASTING_URL = "http://spheresofpower.wikidot.com/casting-traditions"


def _fetch(url: str) -> BeautifulSoup:
    request = Request(url, headers={"User-Agent": "Character Sheet App catalog importer"})
    return BeautifulSoup(urlopen(request, timeout=60).read(), "html.parser")


def _clean(value: str) -> str:
    return " ".join(html.unescape(value).replace("’", "'").split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _section_nodes(heading: Tag):
    level = int(heading.name[1])
    for node in heading.next_siblings:
        if isinstance(node, Tag) and re.fullmatch(r"h[1-6]", node.name or ""):
            if int(node.name[1]) <= level:
                break
        if isinstance(node, Tag):
            yield node


def _source_name(raw_name: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*(\[[^]]+])?$", _clean(raw_name))
    assert match
    return match.group(1).strip(), (match.group(2) or "").strip("[]")


def _label_values(nodes: list[Tag]) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in nodes:
        for strong in node.find_all("strong"):
            label = _clean(strong.get_text(" ", strip=True)).rstrip(":")
            if label not in {
                "Magic Type", "Casting Ability Modifier", "Drawbacks", "Boon", "Boons"
            }:
                continue
            values: list[str] = []
            for sibling in strong.next_siblings:
                if isinstance(sibling, Tag) and sibling.name == "br":
                    break
                text = sibling.get_text(" ", strip=True) if isinstance(sibling, Tag) else str(sibling)
                values.append(text)
            result[label.casefold()] = _clean(" ".join(values)).rstrip(".")
    return result


def _spell_point_rule(boons: str) -> dict:
    text = boons.casefold()
    if "spell point" not in text:
        return {}
    base = 1 if re.search(r"\+1 spell point(?:\b|s)", text) else 0
    per = 0
    every = 0
    if "per level" in text:
        per, every = 1, 1
        base = 0
    elif "per odd level" in text:
        per, every = 1, 2
        base = 0
    else:
        match = re.search(r"\+1 per (?:every )?(\w+|\d+) levels?", text)
        words = {"three": 3, "four": 4, "five": 5, "six": 6}
        if match:
            per, every = 1, words.get(match.group(1), int(match.group(1)) if match.group(1).isdigit() else 0)
    return {
        "base": base, "per": per, "every_levels": every,
        "round_up": "per odd level" in text,
        "text": boons,
    }


def _parenthetical_choice_groups(text: str) -> list[dict]:
    groups: list[dict] = []
    stack: list[int] = []
    spans: list[str] = []
    for index, char in enumerate(text):
        if char == "(":
            stack.append(index)
        elif char == ")" and stack:
            start = stack.pop()
            if not stack:
                spans.append(text[start + 1:index])
    for value in spans:
        if " or " not in value.casefold():
            continue
        options = [part.strip(" ,") for part in re.split(r"\s*,?\s+or\s+|\s*,\s*", value) if part.strip(" ,")]
        if len(options) < 2:
            continue
        groups.append({
            "key": f"tradition-option-{len(groups) + 1}",
            "label": f"Choose for: {value}", "count": 1,
            "options": [
                {"label": option, "grants": [{"kind": "tradition_choice", "name": option}]}
                for option in options
            ],
        })
    return groups


def casting_entries(soup: BeautifulSoup) -> list[dict]:
    allowed = set(range(305, 329)) | set(range(331, 393)) | set(range(396, 403))
    result: list[dict] = []
    for heading in soup.select("#page-content h4[id^=toc]"):
        toc = int(str(heading.get("id"))[3:])
        if toc not in allowed:
            continue
        name, source_tag = _source_name(heading.get_text(" ", strip=True))
        nodes = list(_section_nodes(heading))
        fields = _label_values(nodes)
        description = _clean(" ".join(node.get_text(" ", strip=True) for node in nodes))
        ability_text = fields.get("casting ability modifier", "")
        abilities = [
            ability.casefold()
            for ability in ("Charisma", "Intelligence", "Wisdom")
            if ability.casefold() in ability_text.casefold()
        ]
        boons = fields.get("boons", fields.get("boon", ""))
        choice_groups = (
            [{
                "key": "casting-ability",
                "label": "Casting ability",
                "count": 1,
                "options": [
                    {"label": ability.title(), "grants": [{"kind": "casting_ability", "name": ability}]}
                    for ability in abilities
                ],
            }]
            if len(abilities) > 1 else []
        )
        choice_groups.extend(_parenthetical_choice_groups(fields.get("drawbacks", "")))
        result.append(
            {
                "key": f"casting-tradition:{_slug(name)}",
                "name": name,
                "kind": "Casting",
                "source": source_tag or "Spheres of Power Wiki",
                "source_url": f"https://spheresofpower.wikidot.com/casting-traditions#toc{toc}",
                "description": description,
                "magic_type": fields.get("magic type", ""),
                "casting_ability_options": abilities,
                "drawbacks": fields.get("drawbacks", ""),
                "boons": boons,
                "spell_point_rule": _spell_point_rule(boons),
                "fixed_grants": [],
                "choice_groups": choice_groups,
            }
        )
    return result


def casting_general_drawbacks(soup: BeautifulSoup) -> list[dict]:
    """Index general drawbacks separately from sample casting traditions.

    The detailed sphere-specific and boon text is already present in the local
    Spheres catalog.  General drawbacks occur before the first sphere and were
    consequently absent from that importer, so this catalog stores their stable
    names and direct rule anchors for offline discovery and online detail access.
    """

    result: list[dict] = []
    for heading in soup.select("#page-content h4[id^=toc]"):
        toc = int(str(heading.get("id"))[3:])
        if not 6 <= toc <= 63:
            continue
        name, source_tag = _source_name(heading.get_text(" ", strip=True))
        result.append({
            "key": f"casting-general-drawback:{_slug(name)}",
            "name": name,
            "kind": "Casting",
            "category": "General Drawback",
            "sphere": "",
            "source": source_tag or "Spheres of Power Wiki",
            "source_url": f"https://spheresofpower.wikidot.com/casting-traditions#toc{toc}",
            "description": (
                "General casting drawback. It defines a restriction or method "
                "shared by every sphere effect produced through this casting tradition."
            ),
        })
    return result


def _catalog_names() -> tuple[list[tuple[str, dict]], list[str]]:
    sys.path.insert(0, str(ROOT))
    from app.catalogs import RulesCatalog

    catalog = RulesCatalog(ROOT / "data" / "pf1e")
    entries = []
    for entry in catalog.martial_entries():
        item = dict(entry)
        item["_tradition_kind"] = "martial"
        display = str(item["name"])
        if item["category"] == "Base Sphere":
            display = str(item["sphere"])
        display = _clean(display)
        aliases = {
            display,
            re.sub(r"\s*\[[^]]+]\s*$", "", display).strip(),
            re.sub(r"\s*\([^)]*(?:discipline|drawback|package)\)\s*$", "", re.sub(r"\s*\[[^]]+]\s*$", "", display)).strip(),
        }
        for alias in aliases:
            if alias:
                entries.append((alias.casefold(), item))
    entries.sort(key=lambda pair: len(pair[0]), reverse=True)
    return entries, [str(sphere["name"]) for sphere in catalog.martial_spheres()]


def _mentioned_grants(text: str, catalog: list[tuple[str, dict]]) -> list[dict]:
    haystack = _clean(text).casefold()
    occupied: list[tuple[int, int]] = []
    result: list[dict] = []
    seen: set[str] = set()
    for name, entry in catalog:
        pattern = r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])"
        match = re.search(pattern, haystack)
        if (
            not match
            or str(entry["key"]) in seen
            or any(match.start() < end and match.end() > start for start, end in occupied)
        ):
            continue
        occupied.append(match.span())
        seen.add(str(entry["key"]))
        kind = str(entry.get("_tradition_kind", "martial"))
        result.append(
            {
                "kind": kind,
                "catalog_key": str(entry["key"]),
                "name": str(entry["name"]),
                "sphere": str(entry.get("sphere", "")) if kind == "martial" else "",
                "category": str(entry.get("category", "Talent")) if kind == "martial" else "Feat",
            }
        )
    result.sort(key=lambda grant: haystack.find(_clean(str(grant["name"]).removesuffix(" Sphere")).casefold()))
    return result


def _choice_group(text: str, index: int, catalog: list[tuple[str, dict]], sphere_names: list[str]) -> dict:
    grants = _mentioned_grants(text, catalog)
    lower = text.casefold()
    count_match = re.search(r"\b(one|two|three|four|1|2|3|4)\b(?:\s+additional)?\s+talents?", lower)
    numbers = {"one": 1, "two": 2, "three": 3, "four": 4}
    count = numbers.get(count_match.group(1), int(count_match.group(1)) if count_match and count_match.group(1).isdigit() else 1) if count_match else 1
    # Explicit named alternatives become exact options. Otherwise the resolver
    # offers entries from the sphere families named in the rule sentence.
    allowed = [name for name in sphere_names if re.search(r"(?<![a-z])" + re.escape(name.casefold()) + r"(?![a-z])", lower)]
    generic_from_spheres = (
        "talent" in lower
        and any(phrase in lower for phrase in ("chosen from either", "choice from", "talents from either", "talent from either"))
    )
    if generic_from_spheres:
        return {
            "key": f"choice-{index}", "label": text, "count": count, "options": [],
            "catalog_query": {"kind": "martial", "spheres": allowed, "categories": ["Talent"]},
        }
    explicit = grants if (" either " in lower or " one of " in lower) else []
    if " from the " in lower and any(grant["category"] != "Base Sphere" for grant in explicit):
        explicit = [grant for grant in explicit if grant["category"] != "Base Sphere"]
    if explicit:
        options = [{"label": grant["name"], "grants": [grant]} for grant in explicit]
        return {"key": f"choice-{index}", "label": text, "count": count, "options": options}
    return {
        "key": f"choice-{index}",
        "label": text,
        "count": count,
        "options": [],
        "catalog_query": {"kind": "martial", "spheres": allowed, "categories": ["Talent"]},
    }


def martial_entries(soup: BeautifulSoup) -> list[dict]:
    catalog, sphere_names = _catalog_names()
    from app.catalogs import RulesCatalog
    feat_catalog = RulesCatalog(ROOT / "data" / "pf1e").feat_entries()

    def feat_grants(text: str) -> list[dict]:
        if "feat" not in text.casefold():
            return []
        haystack = _clean(text).casefold()
        result = []
        for feat in feat_catalog:
            name = re.sub(r"\s*\[[^]]+]\s*$", "", _clean(str(feat["name"]))).strip().rstrip("*").strip()
            if re.search(r"(?<![a-z0-9])" + re.escape(name.casefold()) + r"(?![a-z0-9])", haystack):
                result.append({
                    "kind": "feat", "catalog_key": str(feat["key"]),
                    "name": str(feat["name"]), "sphere": "", "category": "Feat",
                })
        if "basic magical training" in haystack and not any(
            grant["name"].casefold().startswith("basic magical training") for grant in result
        ):
            result.append({
                "kind": "feat", "catalog_key": "tradition-feat:basic-magical-training",
                "name": "Basic Magical Training", "sphere": "", "category": "Feat",
            })
        return result
    result: list[dict] = []
    for toc in range(2, 68):
        heading = soup.find(id=f"toc{toc}")
        if heading is None or heading.name != "h3":
            continue
        name, source_tag = _source_name(heading.get_text(" ", strip=True))
        nodes = list(_section_nodes(heading))
        paragraphs = [_clean(node.get_text(" ", strip=True)) for node in nodes if node.name == "p"]
        lines = [_clean(node.get_text(" ", strip=True)) for node in nodes for node in node.find_all("li", recursive=False)]
        fixed_lines = [line for line in lines if not line.casefold().startswith("variable:")]
        variable_lines = [re.sub(r"^Variable:\s*", "", line, flags=re.I) for line in lines if line.casefold().startswith("variable:")]
        fixed: list[dict] = []
        for line in fixed_lines:
            for grant in [*_mentioned_grants(line, catalog), *feat_grants(line)]:
                if grant["category"] == "Base Sphere" and re.match(
                    rf"^{re.escape(str(grant['sphere']))}:\s*", line, flags=re.I
                ):
                    continue
                if grant["catalog_key"] not in {item["catalog_key"] for item in fixed}:
                    fixed.append(grant)
        choices = [_choice_group(line, index + 1, catalog, sphere_names) for index, line in enumerate(variable_lines)]
        result.append(
            {
                "key": f"martial-tradition:{_slug(name)}",
                "name": name,
                "kind": "Martial",
                "source": source_tag or "Spheres of Power Wiki",
                "source_url": f"https://spheresofpower.wikidot.com/martial-traditions#toc{toc}",
                "description": paragraphs[0] if paragraphs else "",
                "rules_text": " ".join(lines),
                "fixed_grants": fixed,
                "choice_groups": choices,
                "raw_grant_lines": fixed_lines,
                "raw_choice_lines": variable_lines,
            }
        )
    by_name = {entry["name"]: entry for entry in result}

    def exact_grants(*names: str) -> list[dict]:
        grants: list[dict] = []
        for name in names:
            match = next(
                (grant for grant in _mentioned_grants(name, catalog) if _clean(str(grant["name"])).casefold().startswith(_clean(name).casefold())),
                None,
            )
            if match:
                grants.append(match)
        return grants

    def sphere_talent_grants(sphere: str) -> list[dict]:
        unique: dict[str, dict] = {}
        for _alias, item in catalog:
            if (
                item.get("_tradition_kind") == "martial"
                and str(item.get("sphere", "")).casefold() == sphere.casefold()
                and item.get("category") == "Talent"
            ):
                unique[str(item["key"])] = {
                    "kind": "martial", "catalog_key": str(item["key"]),
                    "name": str(item["name"]), "sphere": sphere, "category": "Talent",
                }
        return sorted(unique.values(), key=lambda grant: str(grant["name"]).casefold())

    def mixed_choice(
        tradition_name: str,
        group_index: int,
        explicit_names: tuple[str, ...],
        dynamic_spheres: tuple[str, ...] = (),
    ) -> None:
        entry = by_name.get(tradition_name)
        if not entry or group_index >= len(entry["choice_groups"]):
            return
        group = entry["choice_groups"][group_index]
        group["options"] = [
            {"label": grant["name"], "grants": [grant]}
            for grant in exact_grants(*explicit_names)
        ]
        if dynamic_spheres:
            group["catalog_query"] = {
                "kind": "martial", "spheres": list(dynamic_spheres), "categories": ["Talent"]
            }
        else:
            group.pop("catalog_query", None)

    # A few official entries express variable grants inside their fixed bullet
    # list or couple two selections together. Keep those exceptions in data
    # normalization, not in the application/UI.
    cunning = by_name.get("Cunning Leader")
    if cunning:
        cunning["choice_groups"].append({
            "key": "discipline", "label": "Choose one Equipment (discipline) talent",
            "count": 1, "options": [],
            "catalog_query": {"kind": "martial", "spheres": ["Equipment"], "categories": ["Talent"], "name_contains": "(discipline)"},
        })
    weapon_master = by_name.get("Weapon Master")
    if weapon_master:
        weapon_master["choice_groups"].insert(0, {
            "key": "disciplines", "label": "Choose two Equipment (discipline) talents",
            "count": 2, "options": [],
            "catalog_query": {"kind": "martial", "spheres": ["Equipment"], "categories": ["Talent"], "name_contains": "(discipline)"},
        })
    dual = by_name.get("Dual Blade Beast")
    if dual:
        alternate_keys = {grant["catalog_key"] for grant in exact_grants("Bushido Training", "Duelist Training")}
        dual["fixed_grants"] = [grant for grant in dual["fixed_grants"] if grant["catalog_key"] not in alternate_keys]
        dual["choice_groups"].insert(0, {
            "key": "weapon-training", "label": "Choose Bushido Training or Duelist Training",
            "count": 1,
            "options": [{"label": grant["name"], "grants": [grant]} for grant in exact_grants("Bushido Training", "Duelist Training")],
        })
    mixed_choice("All-Thrower", 0, ("Barroom Sphere", "Barbaric Throw"))
    mixed_choice("Bushido Warrior", 0, ("Beastmastery Sphere", "Draw Cut"))
    mixed_choice("Buccaneer", 0, ("Athletics Sphere", "Fencing Sphere"), ("Dual Wielding",))
    mixed_choice("Challenging Knight", 0, ("Guardian Sphere",), ("Gladiator",))
    mixed_choice("Courtesan", 0, ("Dual Wielding Sphere",), ("Fencing",))
    mixed_choice("Dedicated Lancer", 0, ("Guardian Sphere",), ("Lancer",))
    mixed_choice("Dual Blade Beast", 1, ("Duelist Sphere",), ("Dual Wielding",))
    mixed_choice("Expedition Spotter", 1, ("Scout Sphere", "Expert Eye"))
    mixed_choice("Gearhead", 0, ("Tech Savvy", "Trap Sphere"))
    mixed_choice("Liturgist", 0, ("Base Of Operations",), ("Equipment",))
    mixed_choice("Rogue Gunner", 0, ("Athletics Sphere",), ("Scoundrel",))
    thief = by_name.get("Thief")
    if thief and thief["choice_groups"]:
        thief["choice_groups"][0]["options"] = []
        thief["choice_groups"][0]["catalog_query"] = {
            "kind": "martial", "spheres": ["Equipment", "Scoundrel", "Fencing"], "categories": ["Talent"]
        }
    for name in ("Crushing Juggernaut", "Giant"):
        entry = by_name.get(name)
        if entry and entry["choice_groups"]:
            original = entry["choice_groups"].pop(0)
            spheres = original.get("catalog_query", {}).get("spheres", ())
            for index, sphere in enumerate(spheres):
                entry["choice_groups"].insert(index, {
                    "key": f"sphere-talent-{_slug(sphere)}",
                    "label": f"Choose one {sphere} talent", "count": 1, "options": [],
                    "catalog_query": {"kind": "martial", "spheres": [sphere], "categories": ["Talent"]},
                })
    highlander = by_name.get("Highlander")
    if highlander and highlander["choice_groups"]:
        options = []
        for sphere in ("Dual Wielding", "Scout"):
            base = exact_grants(f"{sphere} Sphere")
            for talent in sphere_talent_grants(sphere):
                options.append({
                    "label": f"{sphere} Sphere + {talent['name']}",
                    "grants": [*base, talent],
                })
        highlander["choice_groups"][0]["options"] = options
        highlander["choice_groups"][0].pop("catalog_query", None)
    janjaweed = by_name.get("Janjaweed")
    if janjaweed and janjaweed["choice_groups"]:
        janjaweed["choice_groups"] = [
            {
                "key": "training-route", "label": "Choose the Janjaweed training route", "count": 1,
                "options": [
                    {"label": "Barrage and Sniper spheres", "grants": exact_grants("Barrage Sphere", "Sniper Sphere")},
                    {"label": "Two Beastmastery talents", "grants": []},
                ],
            },
            {
                "key": "beastmastery-talents", "label": "Choose two Beastmastery talents", "count": 2,
                "options": [],
                "catalog_query": {"kind": "martial", "spheres": ["Beastmastery"], "categories": ["Talent"]},
                "required_when": {"group": "training-route", "option": "Two Beastmastery talents"},
            },
        ]
    ace = by_name.get("Ace")
    if ace:
        ace["choice_groups"].insert(0, {
            "key": "athletics-package", "label": "Choose the Athletics package",
            "count": 1,
            "options": [
                {"label": package, "grants": [{"kind": "tradition_choice", "name": package}]}
                for package in ("fly", "run", "swim")
            ],
        })
    wandering = by_name.get("Wandering Martial Artist")
    if wandering and wandering["choice_groups"]:
        group = wandering["choice_groups"][0]
        group["catalog_query"] = {
            "kind": "martial", "spheres": ["Equipment"],
            "categories": ["Talent"], "name_contains": "(discipline)",
        }
        improved_unarmed = feat_grants("Improved Unarmed Strike feat")
        group["options"] = [
            {"label": grant["name"], "grants": [grant]}
            for grant in improved_unarmed
        ]
    return result


def main() -> None:
    casting_soup = _fetch(CASTING_URL)
    casting = casting_entries(casting_soup)
    martial = martial_entries(_fetch(MARTIAL_URL))
    document = {
        "schema_version": 2,
        "sources": [
            "https://spheresofpower.wikidot.com/casting-traditions",
            "https://spheresofpower.wikidot.com/martial-traditions",
        ],
        "casting_traditions": casting,
        "martial_traditions": martial,
        "casting_general_drawbacks": casting_general_drawbacks(casting_soup),
    }
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(casting)} casting and {len(martial)} martial traditions to {OUTPUT}")


if __name__ == "__main__":
    main()
