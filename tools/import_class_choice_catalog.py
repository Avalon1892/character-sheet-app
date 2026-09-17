"""Build reusable PF1e class-choice catalogs from the bundled compendium."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
import sys
import unicodedata
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
import yaml  # type: ignore  # noqa: E402
from bs4 import BeautifulSoup  # type: ignore  # noqa: E402


SOURCE = ROOT / ".item-source" / "packs" / "class-abilities"
OUTPUT = ROOT / "data" / "pf1e" / "class_choices.json"
INQUISITIONS = ROOT / "data" / "pf1e" / "inquisitions.json"
SPELLS = ROOT / "data" / "pf1e" / "spells.json"
OCCULTIST_IMPLEMENT_URL = "https://www.aonprd.com/OccultistImplements.aspx"
PHANTOM_FOCUS_URL = "https://www.aonprd.com/PhantomFocus.aspx"


def slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def plain(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"@(?:UUID|Embed)\[[^]]+\](?:\{([^}]+)\})?", lambda match: match.group(1) or "", text)
    text = re.sub(r"<li\b[^>]*>", "\n• ", text, flags=re.I)
    text = re.sub(r"</(?:p|li|h\d|ul|ol)>", "\n", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    # Some upstream compendium exports used U+FFFD for bullets and minus
    # signs.  Keep catalog prose readable and preserve mechanically important
    # negative values instead of leaking replacement glyphs into the Codex.
    text = re.sub(r"(?<=\s)�(?=\d)", "−", text)
    text = text.replace("� ", "• ").replace("�", "•")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _mystery_bonus_spells(description: str) -> list[dict]:
    """Extract the explicitly headed Oracle mystery spell progression.

    This runs only while building the catalog. Runtime rules consume the
    structured rows and never infer mechanics from displayed prose.
    """

    match = re.search(r"\bBonus Spells\s*:\s*(.*)", description, re.I | re.S)
    if match is None:
        return []
    result = []
    for line in match.group(1).splitlines():
        cleaned = re.sub(r"^[•*\-\s]+", "", line).strip().rstrip(".,;")
        spell = re.match(
            r"(?P<name>.+)\s+\((?P<level>\d+)(?:st|nd|rd|th)\)$",
            cleaned,
            re.I,
        )
        if spell is None:
            continue
        grant_level = int(spell.group("level"))
        result.append(
            {
                "name": spell.group("name").strip(),
                "class_level": grant_level,
                "spell_level": max(1, min(9, grant_level // 2)),
            }
        )
    return result


def _mystery_class_skills(description: str) -> list[str]:
    match = re.search(
        r"\badds?\s+(.+?)\s+to\s+(?:her|his|their)\s+list of class skills",
        description,
        re.I,
    )
    if match is None:
        return []
    value = re.sub(r"\band\b", ",", match.group(1), flags=re.I)
    return [item.strip(" .,:") for item in value.split(",") if item.strip(" .,:")]


def _bloodline_bonus_spells(description: str) -> list[dict]:
    """Extract Sorcerer/Bloodrager bloodline spells at catalog-build time."""

    match = re.search(
        r"\bBonus Spells\s*:\s*(.*?)(?=\n\s*(?:Bonus Feats|Bloodline Arcana|Bloodline Powers|Class Skill)\s*:|\Z)",
        description,
        re.I | re.S,
    )
    if match is None:
        return []
    result: list[dict] = []
    for line in match.group(1).splitlines():
        cleaned = re.sub(r"^[•*\-\s]+", "", line).strip().rstrip(".,;")
        spell = re.match(
            r"(?P<name>.+?)\s*\((?P<level>\d+)(?:st|nd|rd|th)\)\s*,?$",
            cleaned,
            re.I,
        )
        if spell is None:
            continue
        grant_level = int(spell.group("level"))
        # Sorcerer bloodline spells arrive at 3, 5, 7, ...; Bloodrager
        # bloodline spells arrive at 7, 10, 13, and 16.
        spell_level = (
            max(1, min(4, (grant_level - 4) // 3))
            if grant_level in {7, 10, 13, 16}
            and len(re.findall(r"\(\d+(?:st|nd|rd|th)\)", match.group(1), re.I)) <= 4
            else max(1, min(9, (grant_level - 1) // 2))
        )
        result.append({
            "name": spell.group("name").strip(),
            "class_level": grant_level,
            "spell_level": spell_level,
        })
    return result


def _bloodline_class_skills(description: str) -> list[str]:
    match = re.search(r"\bClass Skill\s*:\s*([^\n.]+)", description, re.I)
    if match is None:
        return []
    return [match.group(1).strip(" .,:;")]


def _domain_bonus_spells(description: str) -> list[dict]:
    """Extract the explicitly headed nine-level Domain Spells table.

    Domain spells unlock when a Cleric first gains the corresponding spell
    level (class levels 1, 3, 5, ... 17).  Keeping those thresholds in the
    generated catalog lets Clerics, Druids, and archetypes share one runtime
    grant service without inspecting description text while a character is
    open.
    """

    match = re.search(r"\bDomain Spells\b\s*(.*)", description, re.I | re.S)
    if match is None:
        return []
    result: list[dict] = []
    for line in match.group(1).splitlines():
        cleaned = re.sub(r"^[•*\-\s]+", "", line).strip().rstrip(".,;")
        row = re.match(
            r"(?P<level>\d+)(?:st|nd|rd|th)\s*[-–—:]\s*(?P<name>.+)",
            cleaned,
            re.I,
        )
        if row is None:
            continue
        spell_level = max(1, min(9, int(row.group("level"))))
        result.append({
            "name": row.group("name").strip(),
            "class_level": spell_level * 2 - 1,
            "spell_level": spell_level,
        })
    return result


def _spell_name_index() -> tuple[tuple[str, str, int], ...]:
    try:
        entries = json.loads(SPELLS.read_text(encoding="utf-8")).get("entries", ())
    except (OSError, ValueError):
        return ()
    result: dict[str, tuple[str, int]] = {}
    for entry in entries:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        class_levels = {
            str(key).casefold(): int(value)
            for key, value in (entry.get("class_levels") or {}).items()
            if str(value).isdigit() or isinstance(value, int)
        }
        level = class_levels.get("oracle")
        if level is None:
            for preferred in (
                "cleric", "sorcerer", "wizard", "druid", "bard", "witch",
                "shaman", "psychic",
            ):
                if preferred in class_levels:
                    level = class_levels[preferred]
                    break
        if level is None:
            candidates = [
                int(value)
                for values in (
                    entry.get("class_levels") or {},
                    entry.get("domain_levels") or {},
                    entry.get("subdomain_levels") or {},
                    entry.get("bloodline_levels") or {},
                )
                for value in values.values()
                if isinstance(value, int) or str(value).isdigit()
            ]
            level = min(candidates) if candidates else 0
        result.setdefault(name.casefold(), (name, max(0, min(9, int(level)))))
    return tuple(
        (folded, value[0], value[1])
        for folded, value in sorted(
            result.items(), key=lambda item: (-len(item[0]), item[0])
        )
    )


_SPELL_NAMES = _spell_name_index()


def _oracle_curse_bonus_spells(description: str) -> list[dict]:
    """Extract explicitly granted curse spells at catalog-build time."""

    result: list[dict] = []
    pattern = re.compile(
        r"(?:At\s+(?P<level>\d+)(?:st|nd|rd|th)\s+level,\s*)?"
        r"(?P<prefix>[^.\n]{0,100}?)\badds?\s+(?P<names>.+?)\s+"
        r"to\s+(?:your|her|his|their)\s+list of spells known",
        re.I,
    )
    for match in pattern.finditer(description):
        grant_level = int(match.group("level") or 1)
        text = match.group("names")
        folded = text.casefold()
        occupied: list[tuple[int, int]] = []
        for spell_folded, spell_name, spell_level in _SPELL_NAMES:
            for found in re.finditer(rf"(?<![a-z]){re.escape(spell_folded)}(?![a-z])", folded):
                span = found.span()
                if any(span[0] < end and start < span[1] for start, end in occupied):
                    continue
                occupied.append(span)
                result.append(
                    {
                        "name": spell_name,
                        "class_level": grant_level,
                        "spell_level": spell_level,
                    }
                )
                break
    unique = {
        (item["name"].casefold(), item["class_level"]): item for item in result
    }
    return sorted(
        unique.values(),
        key=lambda item: (item["class_level"], item["spell_level"], item["name"].casefold()),
    )


def _shaman_spirit_bonus_spells(description: str) -> list[dict]:
    """Extract the explicit Spirit Magic spell table for reusable spirit grants."""

    match = re.search(
        r"\bSpirit Magic Spells\b\s*(.*?)(?=\n\s*(?:Spirit Animal|Hexes?|Spirit Ability)\b|\Z)",
        description,
        re.I | re.S,
    )
    if match is None:
        return []
    result: list[dict] = []
    for line in match.group(1).splitlines():
        cleaned = re.sub(r"^[•*\-\s]+", "", line).strip().rstrip(".,;")
        row = re.match(r"(?P<level>\d+)(?:st|nd|rd|th)\s*[-–—:]\s*(?P<name>.+)", cleaned, re.I)
        if row is None:
            continue
        spell_level = max(1, min(9, int(row.group("level"))))
        name = row.group("name").strip()
        result.append({
            "name": name,
            # Spirit Guide first receives its current spirit-magic list at
            # Oracle 4, then unlocks later spell levels normally.
            "class_level": max(4, spell_level * 2),
            "spell_level": spell_level,
        })
    return result


def _psychic_discipline_bonus_spells(description: str) -> list[dict]:
    """Extract a discipline's nine authored bonus spells at import time."""

    parts = re.split(r"\bBonus Spells\s*:\s*", description, maxsplit=1, flags=re.I)
    if len(parts) != 2:
        return []
    result: list[dict] = []
    for row in re.finditer(
        r"(?:^|\n)\s*[•*\-]\s*(?P<name>[^\n]+?)\s*"
        r"\((?P<level>\d+)(?:st|nd|rd|th)\)\s*[,.;]?",
        parts[1],
        re.I,
    ):
        class_level = max(1, int(row.group("level")))
        result.append({
            "name": row.group("name").strip(),
            "class_level": class_level,
            "spell_level": 1 if class_level == 1 else min(9, class_level // 2),
        })
    return result


def _psychic_discipline_ability(description: str) -> str:
    match = re.search(
        r"\bPhrenic Pool Ability\s*:\s*(Wisdom|Charisma)\b",
        description,
        re.I,
    )
    return match.group(1).casefold() if match is not None else ""


def _load() -> tuple[dict[str, dict], dict[str, Path]]:
    by_id: dict[str, dict] = {}
    paths: dict[str, Path] = {}
    for path in SOURCE.rglob("*.yaml"):
        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        identifier = str(record.get("_id") or "")
        if identifier:
            by_id[identifier] = record
            paths[identifier] = path
    return by_id, paths


def _linked_features(record: dict, by_id: dict[str, dict]) -> list[dict]:
    system = record.get("system") or {}
    result = []
    for link in (system.get("links") or {}).get("supplements", ()):
        identifier = str(link.get("uuid") or "").rsplit(".", 1)[-1]
        child = by_id.get(identifier)
        if not child:
            continue
        child_system = child.get("system") or {}
        description = plain((child_system.get("description") or {}).get("value"))
        row = {
                "key": f"class-choice-feature:{identifier}",
                "level": max(1, int(link.get("level") or 1)),
                "name": str(child.get("name") or "Granted Feature"),
                "description": description,
            }
        resource = _feature_resource_metadata(description)
        if resource:
            row["resource"] = resource
        result.append(row)
    return sorted(result, key=lambda row: (row["level"], row["name"].casefold()))


def _feature_resource_metadata(description: str) -> dict:
    """Normalize recurring daily-use language at catalog-build time.

    Runtime character calculations consume only this allowlisted declaration;
    they never scrape the rules text shown in the Codex or tooltips.
    """

    text = str(description or "")
    progression = ""
    if re.search(r"\b3\s+times\s+(?:your|the)\s+\w+\s+level\s+per\s+day\b", text, re.I):
        progression = "level_times_three"
    elif re.search(r"\b(?:number of times|uses?|rounds?)\s+per\s+day\s+equal\s+to\s+3\s*\+\s+(?:your\s+)?\w+\s+modifier\b", text, re.I):
        progression = "three_plus_ability"
    elif re.search(r"\b(?:number of times|uses?|rounds?)\s+per\s+day\s+equal\s+to\s+1\s*\+\s+(?:your\s+)?\w+\s+modifier\b", text, re.I):
        progression = "one_plus_ability_minimum_one"
    elif re.search(r"\b(?:number of times|uses?|rounds?)\s+per\s+day\s+equal\s+to\s+(?:your\s+)?\w+\s+modifier\b", text, re.I):
        progression = "ability_modifier_minimum_one"
    elif re.search(r"\b(?:number of times|uses?|rounds?)\s+per\s+day\s+equal\s+to\s+(?:half|1/2)\s+(?:your\s+)?(?:class\s+|\w+\s+)?level\b", text, re.I):
        progression = "half_level_minimum_one"
    elif re.search(r"\b(?:number of times|uses?|rounds?)\s+per\s+day\s+equal\s+to\s+(?:your\s+)?(?:class\s+|\w+\s+)?level\b", text, re.I):
        progression = "level"
    elif re.search(r"\bonce per day\b", text, re.I):
        progression = "one"
    elif re.search(r"\btwice per day\b", text, re.I):
        progression = "two"
    elif re.search(r"\bthree times per day\b", text, re.I):
        progression = "three"
    if not progression:
        return {}
    ability_match = re.search(
        r"\b(?:your\s+)?(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+modifier\b",
        text,
        re.I,
    )
    return {
        "progression": progression,
        "recover_on_full_rest": True,
        "ability": ability_match.group(1).casefold() if ability_match else "",
    }


def _family(record: dict, path: Path) -> tuple[str, str] | None:
    name = str(record.get("name") or "")
    system = record.get("system") or {}
    tags = {str(value).casefold() for value in system.get("tags", ())}
    parts = {part.casefold() for part in path.parts}
    if "domains" in parts and name.casefold().endswith((" domain", " subdomain")):
        return "domain", "Subdomain" if name.casefold().endswith(" subdomain") else "Domain"
    if name.casefold().endswith(" bloodline") and name.casefold() not in {
        "bloodrager bloodline", "sorcerer bloodline"
    }:
        return "bloodline", "Bloodrager" if "bloodrager" in name.casefold() else "Sorcerer"
    if name.casefold().endswith(" mystery"):
        return "mystery", "Oracle Mystery"
    if "wizard school" in tags and name.casefold().endswith(" school"):
        return "arcane_school", "Elemental School" if "elemental-schools" in parts else "Arcane School"
    if "cavalier order" in tags or "samurai order" in tags:
        return "order", "Cavalier / Samurai Order"
    if "kineticist element" in tags and name.casefold() != "universal":
        return "kineticist_element", "Kineticist Element"
    if "shaman spirit" in tags and name.casefold().endswith(" spirit"):
        return "shaman_spirit", "Shaman Spirit"
    if "shifter aspect" in tags and name.casefold().endswith(" aspect"):
        return "shifter_aspect", "Shifter Aspect"
    if "blessing" in tags and name.casefold().endswith(" blessing"):
        return "warpriest_blessing", "Warpriest Blessing"
    classes = {
        str(value).casefold()
        for value in (system.get("associations") or {}).get("classes", ())
    }
    if "oracle" in classes and "curse" in tags and name.casefold().endswith(" curse"):
        return "oracle_curse", "Oracle Curse"
    if "witch" in classes and name.casefold().endswith(" patron"):
        return "witch_patron", "Witch Patron"
    if "psychic" in classes and name.casefold().endswith(" discipline") and name.casefold() != "psychic discipline":
        return "psychic_discipline", "Psychic Discipline"
    return None


def _aon_detail_choices(
    index_url: str,
    *,
    link_fragment: str,
    default_family: str,
    default_category: str,
    classes: tuple[str, ...],
) -> list[dict]:
    """Import authored option pages at catalog-build time.

    Archives of Nethys wraps each detail record in one span containing its
    title and complete rules text. Runtime code consumes only the generated
    JSON and never performs network access or description parsing.
    """

    headers = {"User-Agent": "Mozilla/5.0 Character Sheet catalog importer"}
    index = BeautifulSoup(
        urlopen(Request(index_url, headers=headers), timeout=60).read(),
        "html.parser",
    )
    category = default_category
    result: list[dict] = []
    seen: set[str] = set()
    for node in (index.find(id="main") or index).find_all(["h1", "a"]):
        if node.name == "h1":
            heading = plain(node.get_text(" ", strip=True))
            if heading:
                category = heading
            continue
        href = str(node.get("href") or "")
        if link_fragment.casefold() not in href.casefold():
            continue
        name = plain(node.get_text(" ", strip=True))
        key = slug(name)
        if not name or key in seen:
            continue
        seen.add(key)
        detail_url = quote(urljoin(index_url, href), safe=":/?=&%")
        detail = BeautifulSoup(
            urlopen(
                Request(detail_url, headers={**headers, "Referer": index_url}),
                timeout=60,
            ).read(),
            "html.parser",
        )
        title = next(
            (
                heading
                for heading in detail.find_all("h1")
                if plain(heading.get_text(" ", strip=True)).casefold()
                == name.casefold()
            ),
            None,
        )
        container = title.parent if title is not None else None
        description = plain(str(container)) if container is not None else ""
        description = re.sub(
            rf"^{re.escape(name)}\s+(?:Source\s+[^\n]+\s+)?",
            "",
            description,
            flags=re.I,
        ).strip()
        source_node = container.find("i") if container is not None else None
        source = plain(source_node.get_text(" ", strip=True)) if source_node else "Pathfinder RPG"
        family = default_family
        option_category = default_category
        if default_family == "occultist_implement":
            if "panopl" in category.casefold():
                family = "occultist_panoply"
                option_category = "Panoply"
            else:
                option_category = "Implement School"
        result.append({
            "key": f"class-choice:{family}:{key}",
            "family": family,
            "category": option_category,
            "name": name,
            "description": description,
            "classes": list(classes),
            "granted_features": [],
            "bonus_spells": [],
            "class_skills": [],
            "source": source,
            "source_url": detail_url,
        })
    if not result:
        raise RuntimeError(f"Archives of Nethys options were not found at {index_url}")
    return result


def build_catalog() -> dict:
    by_id, paths = _load()
    entries = []
    for identifier, record in by_id.items():
        family_category = _family(record, paths[identifier])
        if family_category is None:
            continue
        family, category = family_category
        system = record.get("system") or {}
        classes = [
            str(value)
            for value in (system.get("associations") or {}).get("classes", ())
            if str(value).strip()
        ]
        name = str(record.get("name") or "Unnamed Option")
        description = plain((system.get("description") or {}).get("value"))
        entries.append(
            {
                "key": f"class-choice:{family}:{slug(name)}",
                "family": family,
                "category": category,
                "name": name,
                "description": description,
                "classes": classes,
                "granted_features": _linked_features(record, by_id),
                "bonus_spells": (
                    _domain_bonus_spells(description)
                    if family == "domain"
                    else _mystery_bonus_spells(description)
                    if family == "mystery"
                    else _oracle_curse_bonus_spells(description)
                    if family == "oracle_curse"
                    else _shaman_spirit_bonus_spells(description)
                    if family == "shaman_spirit"
                    else _psychic_discipline_bonus_spells(description)
                    if family == "psychic_discipline"
                    else _bloodline_bonus_spells(description)
                    if family == "bloodline"
                    else []
                ),
                "resource_ability": (
                    _psychic_discipline_ability(description)
                    if family == "psychic_discipline" else ""
                ),
                "class_skills": (
                    _mystery_class_skills(description)
                    if family == "mystery"
                    else _bloodline_class_skills(description)
                    if family == "bloodline"
                    else []
                ),
                "source": ", ".join(
                    str(value.get("id"))
                    for value in system.get("sources", ())
                    if value.get("id")
                ) or "Pathfinder RPG",
                "source_url": {
                    "domain": "https://www.aonprd.com/ClericDomains.aspx",
                    "bloodline": "https://www.aonprd.com/SorcererBloodlines.aspx",
                    "mystery": "https://www.aonprd.com/OracleMysteries.aspx",
                    "arcane_school": "https://www.aonprd.com/WizardArcaneSchools.aspx",
                    "order": "https://www.aonprd.com/CavalierOrders.aspx",
                    "kineticist_element": "https://www.aonprd.com/KineticistElements.aspx",
                    "shaman_spirit": "https://www.aonprd.com/ShamanSpirits.aspx",
                    "shifter_aspect": "https://www.aonprd.com/ShifterAspects.aspx",
                    "warpriest_blessing": "https://www.aonprd.com/WarpriestBlessings.aspx",
                    "oracle_curse": "https://www.aonprd.com/OracleCurses.aspx",
                    "witch_patron": "https://www.aonprd.com/WitchPatrons.aspx",
                    "psychic_discipline": "https://www.aonprd.com/PsychicDisciplines.aspx",
                }[family],
            }
        )
    entries.extend(_aon_detail_choices(
        OCCULTIST_IMPLEMENT_URL,
        link_fragment="OccultistImplementsDisplay.aspx",
        default_family="occultist_implement",
        default_category="Implement School",
        classes=("Occultist",),
    ))
    entries.extend(_aon_detail_choices(
        PHANTOM_FOCUS_URL,
        link_fragment="PhantomFocusDisplay.aspx",
        default_family="phantom_focus",
        default_category="Emotional Focus",
        classes=("Spiritualist",),
    ))
    try:
        inquiries = json.loads(INQUISITIONS.read_text(encoding="utf-8")).get(
            "entries", ()
        )
    except (OSError, ValueError):
        inquiries = ()
    for record in inquiries:
        name = str(record.get("name") or "Unnamed Inquisition")
        entries.append(
            {
                "key": str(record.get("key") or f"class-choice:inquisition:{slug(name)}"),
                "family": "inquisition",
                "category": "Inquisition",
                "name": name,
                "description": str(record.get("description") or ""),
                "classes": ["Inquisitor"],
                "granted_features": list(record.get("granted_features") or ()),
                "source": str(record.get("source") or "Pathfinder RPG"),
                "source_url": str(record.get("source_url") or "https://www.aonprd.com/Inquisitions.aspx"),
            }
        )
    entries.sort(key=lambda row: (row["family"], row["category"], row["name"].casefold()))
    return {
        "version": 1,
        "sources": [
            {"name": "Pathfinder 1e system compendium", "path": ".item-source/packs/class-abilities"},
            {"name": "Archives of Nethys", "url": "https://www.aonprd.com/Classes.aspx"},
            {"name": "Archives of Nethys — Occultist Implements", "url": OCCULTIST_IMPLEMENT_URL},
            {"name": "Archives of Nethys — Phantom Emotional Focus", "url": PHANTOM_FOCUS_URL},
        ],
        "entries": entries,
    }


def main() -> None:
    document = build_catalog()
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    for entry in document["entries"]:
        counts[entry["family"]] = counts.get(entry["family"], 0) + 1
    print(f"Wrote {len(document['entries'])} class-choice options to {OUTPUT}")
    print(", ".join(f"{key}: {value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
