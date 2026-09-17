"""Build the traditional Pathfinder spell catalog.

First-party entries come from the locally bundled structured PF1e compendium.
Third-party entries are kept as a separately labeled family and are discovered
from d20PFSRD's publisher-organized 3PP spell index.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
import yaml  # type: ignore

from catalog_import_common import clean_text, element_fragment, fetch_cached, html_text, slug


OFFICIAL_ROOT = ROOT / ".item-source" / "packs" / "spells"
CACHE_ROOT = ROOT / ".spell-source" / "d20pfsrd"
OUTPUT = ROOT / "data" / "pf1e" / "spells.json"
THIRD_PARTY_INDEX = "https://www.d20pfsrd.com/magic/3rd-party-spells/"
SCHOOL_NAMES = {
    "abj": "Abjuration", "con": "Conjuration", "div": "Divination",
    "enc": "Enchantment", "evo": "Evocation", "ill": "Illusion",
    "nec": "Necromancy", "trs": "Transmutation", "uni": "Universal",
}


def _plain(value: object) -> str:
    return clean_text(html_text(str(value or "")))


def _labels(value: object) -> list[str]:
    """Normalize compendium string-or-list labels without leaking Python reprs."""

    if value in (None, ""):
        return []
    values = value if isinstance(value, (list, tuple, set)) else (value,)
    return [str(item).replace("-", " ").title() for item in values if str(item).strip()]


def _action_value(action: dict, key: str) -> str:
    value = action.get(key) or {}
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    description = str(value.get("description") or "").strip()
    if description:
        return description
    amount = value.get("value")
    units = str(value.get("units") or "").strip()
    if amount not in (None, ""):
        return f"{amount} {units}".strip()
    return units


def _activation_value(action: dict) -> str:
    activation = action.get("activation") or {}
    if isinstance(activation, str):
        return activation
    if not isinstance(activation, dict):
        return ""
    description = str(activation.get("description") or "").strip()
    if description:
        return description
    action_type = str(activation.get("type") or "").replace("-", " ").strip()
    cost = activation.get("cost")
    if cost not in (None, "", 1) and action_type:
        return f"{cost} {action_type} actions"
    return (f"1 {action_type} action" if action_type else "").replace("1 standard action", "1 standard action")


def official_entries() -> list[dict]:
    result: list[dict] = []
    for path in OFFICIAL_ROOT.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if data.get("type") != "spell":
            continue
        system = data.get("system") or {}
        actions = list((system.get("actions") or {}).values())
        action = actions[0] if actions else {}
        learned = system.get("learnedAt") or {}
        class_levels = {
            str(name).replace("-", " ").title(): int(level)
            for name, level in (learned.get("class") or {}).items()
        }
        descriptions = system.get("description") or {}
        description = _plain(descriptions.get("value") or descriptions.get("unidentified"))
        summary = _plain(descriptions.get("summary"))
        sources = [
            str(source.get("id")) + (f" p. {source.get('pages')}" if source.get("pages") else "")
            for source in system.get("sources", ())
            if source.get("id")
        ]
        school_key = str(system.get("school") or "")
        result.append(
            {
                "key": f"pathfinder-spell:{data.get('_id') or slug(str(data.get('name') or path.stem))}",
                "name": str(data.get("name") or path.stem),
                "source_group": "Pathfinder",
                "publisher": "Paizo",
                "third_party": False,
                "school": SCHOOL_NAMES.get(school_key, school_key.title()),
                "subschool": ", ".join(_labels(system.get("subschool"))),
                "descriptors": _labels(system.get("descriptors")),
                "level": int(system.get("level") or 0),
                "class_levels": class_levels,
                "domain_levels": dict(learned.get("domain") or {}),
                "subdomain_levels": dict(learned.get("subDomain") or {}),
                "bloodline_levels": dict(learned.get("bloodline") or {}),
                "components": ", ".join(
                    label for key, label in (("verbal", "V"), ("somatic", "S"), ("material", "M"), ("focus", "F"), ("divineFocus", "DF"))
                    if (system.get("components") or {}).get(key)
                ),
                "casting_time": _activation_value(action),
                "range": _action_value(action, "range"),
                "target": _action_value(action, "target") or _action_value(action, "area") or _action_value(action, "effect"),
                "duration": _action_value(action, "duration"),
                "saving_throw": _action_value(action, "save"),
                "spell_resistance": str(system.get("sr") or ""),
                "summary": summary or (description.split("\n", 1)[0] if description else ""),
                "description": description or summary,
                "source": ", ".join(sources) or "Pathfinder Roleplaying Game",
                "source_url": "https://www.aonprd.com/Spells.aspx",
            }
        )
    return result


def third_party_urls(index_source: str) -> list[str]:
    urls: set[str] = set()
    for raw in re.findall(r'href=["\']([^"\']+)["\']', index_source, re.I):
        url = urllib.parse.urljoin(THIRD_PARTY_INDEX, html.unescape(raw))
        parsed = urllib.parse.urlsplit(url)
        if parsed.netloc.casefold() not in {"www.d20pfsrd.com", "d20pfsrd.com"}:
            continue
        path = re.sub(r"/+", "/", parsed.path).casefold()
        if not path.startswith("/magic/3rd-party-spells/") or path == "/magic/3rd-party-spells/":
            continue
        urls.add(urllib.parse.urlunsplit(("https", "www.d20pfsrd.com", path.rstrip("/") + "/", "", "")))
    return sorted(urls)


def _labeled(text: str, label: str, following: tuple[str, ...]) -> str:
    tail = "|".join(re.escape(value) for value in following)
    match = re.search(rf"\b{re.escape(label)}\b\s*(.*?)(?=\s+\b(?:{tail})\b|$)", text, re.I | re.S)
    return clean_text(match.group(1)) if match else ""


def _third_party_entry(url: str, refresh: bool) -> dict | None:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    source = fetch_cached(url, CACHE_ROOT / f"{digest}--{slug(url.rstrip('/').rsplit('/', 1)[-1])}.html", refresh=refresh)
    article = element_fragment(source, "article-content")
    if not article:
        return None
    text = html_text(article)
    if not re.search(r"\bSchool\b", text, re.I) or not re.search(r"\bLevel\b", text, re.I) or "DESCRIPTION" not in text:
        return None
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", article, re.I | re.S)
    name = html_text(title_match.group(1)) if title_match else ""
    if not name:
        return None
    description_marker = re.search(r"\bDESCRIPTION\b", text, re.I)
    if not description_marker:
        return None
    before_description = text[: description_marker.start()]
    cast_marker = re.search(r"\bCAST(?:ING)?\b", before_description, re.I)
    effect_marker = re.search(r"\bEFFECT\b", before_description, re.I)
    stat_match = re.search(
        r"\bSchool\b\s*(.*?)\s*;\s*\bLevel\b\s*(.*?)(?=\s+\b(?:CASTING|CAST|EFFECTS?|Casting Time|Components|Range|Targets?|Area|Duration|Saving Throw|Spell Resistance)\b|$)",
        before_description,
        re.I | re.S,
    )
    school_raw = clean_text(stat_match.group(1)) if stat_match else ""
    levels_raw = clean_text(stat_match.group(2)) if stat_match else ""
    casting_end = effect_marker.start() if effect_marker else description_marker.start()
    casting = text[cast_marker.end() : casting_end] if cast_marker else before_description
    effect = (
        text[effect_marker.end() : description_marker.start()]
        if effect_marker
        else before_description
    )
    description_tail = text[description_marker.end() :]
    description = re.split(r"\bSection 15\b|\bDiscuss!\b", description_tail, maxsplit=1)[0].strip()
    copyright_text = description_tail.split("Section 15", 1)[1].strip() if "Section 15" in description_tail else ""
    class_levels: dict[str, int] = {}
    for match in re.finditer(r"([A-Za-z][A-Za-z' /&-]*?)\s+(\d+)(?=\s*,|$)", levels_raw):
        for class_name in re.split(r"/|\band\b", match.group(1), flags=re.I):
            cleaned = clean_text(class_name).title()
            if cleaned:
                class_levels[cleaned] = int(match.group(2))
    breadcrumbs = re.findall(r'class="bread-parent"[^>]*>(.*?)</a>', article, re.I | re.S)
    publisher = html_text(breadcrumbs[-1]) if breadcrumbs else "Third Party"
    descriptors = [clean_text(value).title() for value in re.findall(r"\[([^]]+)\]", school_raw)]
    school_without_descriptors = re.sub(r"\[[^]]+\]", "", school_raw).strip()
    school_match = re.match(r"([^()]+?)(?:\s*\(([^)]+)\))?$", school_without_descriptors)
    school = clean_text(school_match.group(1)).title() if school_match else school_raw.title()
    subschool = clean_text(school_match.group(2)).title() if school_match and school_match.group(2) else ""
    return {
        "key": f"third-party-spell:{slug(urllib.parse.urlsplit(url).path)}",
        "name": name,
        "source_group": "Third Party",
        "publisher": publisher,
        "third_party": True,
        "school": school,
        "subschool": subschool,
        "descriptors": descriptors,
        "level": min(class_levels.values()) if class_levels else 0,
        "class_levels": class_levels,
        "class_levels_text": levels_raw,
        "domain_levels": {},
        "subdomain_levels": {},
        "bloodline_levels": {},
        "components": _labeled(casting, "Components", ("Casting Time",)),
        "casting_time": _labeled(casting, "Casting Time", ("Components",)),
        "range": _labeled(effect, "Range", ("Target", "Targets", "Area", "Effect", "Duration", "Saving Throw", "Spell Resistance")),
        "target": _labeled(effect, "Target", ("Targets", "Area", "Effect", "Duration", "Saving Throw", "Spell Resistance")) or _labeled(effect, "Targets", ("Area", "Effect", "Duration", "Saving Throw", "Spell Resistance")) or _labeled(effect, "Area", ("Effect", "Duration", "Saving Throw", "Spell Resistance")) or _labeled(effect, "Effect", ("Duration", "Saving Throw", "Spell Resistance")),
        "duration": _labeled(effect, "Duration", ("Saving Throw", "Spell Resistance")),
        "saving_throw": _labeled(effect, "Saving Throw", ("Spell Resistance",)),
        "spell_resistance": _labeled(effect, "Spell Resistance", ()),
        "summary": description.split("\n", 1)[0][:500],
        "description": description,
        "source": copyright_text or publisher,
        "source_url": url,
    }


def third_party_entries(refresh: bool = False, workers: int = 20) -> tuple[list[dict], list[str]]:
    index = fetch_cached(THIRD_PARTY_INDEX, CACHE_ROOT / "index.html", refresh=refresh)
    urls = third_party_urls(index)
    result: list[dict] = []
    warnings: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_third_party_entry, url, refresh): url for url in urls}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                entry = future.result()
                if entry is not None:
                    result.append(entry)
            except Exception as error:  # retain a refreshable warning without aborting the catalog
                warnings.append(f"{futures[future]}: {error}")
            if completed % 250 == 0:
                print(f"Scanned {completed}/{len(urls)} third-party pages; found {len(result)} spells", flush=True)
    return result, warnings


def build_catalog(refresh: bool = False, workers: int = 20, skip_third_party: bool = False) -> dict:
    entries = official_entries()
    warnings: list[str] = []
    if not skip_third_party:
        third_party, warnings = third_party_entries(refresh, workers)
        entries.extend(third_party)
    entries = list({entry["key"]: entry for entry in entries}.values())
    entries.sort(key=lambda item: (str(item["name"]).casefold(), str(item["source_group"]), str(item.get("publisher", ""))))
    return {
        "version": 1,
        "sources": [
            {"name": "Foundry Virtual Tabletop PF1e compendium", "url": "https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1"},
            {"name": "d20PFSRD Third-Party Spells", "url": THIRD_PARTY_INDEX},
        ],
        "warnings": warnings,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the traditional Pathfinder spell catalog.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--skip-third-party", action="store_true")
    arguments = parser.parse_args()
    document = build_catalog(arguments.refresh, arguments.workers, arguments.skip_third_party)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    pathfinder = sum(not entry["third_party"] for entry in document["entries"])
    third_party = len(document["entries"]) - pathfinder
    print(f"Wrote {len(document['entries'])} spells ({pathfinder} Pathfinder, {third_party} third-party) to {OUTPUT}")
    if document["warnings"]:
        print(f"Completed with {len(document['warnings'])} refresh warnings; cached entries can be retried later.")


if __name__ == "__main__":
    main()
