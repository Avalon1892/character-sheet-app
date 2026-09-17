from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.codex_descriptions import (  # noqa: E402 - ROOT must be importable first
    normalize_spheres_archetype_codex_entry,
)

CLASS_FILE = ROOT / "data" / "pf1e" / "pathfinder_classes.json"
OUTPUT_FILE = ROOT / "data" / "pf1e" / "archetypes.json"
CACHE_ROOT = ROOT / ".archetype-source"
USER_AGENT = "Character Sheet App archetype catalog importer/1.0"

# The wiki's general index also lists companion archetypes.  Keep their owner
# explicit so a markup change cannot make them inherit a neighboring class.
SPHERE_ARCHETYPE_PARENT_OVERRIDES = {
    "martial-beast": ("companion:animal-companion", "Animal Companion"),
}


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def clean_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


class TextParser(HTMLParser):
    BREAK_TAGS = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.ignored += 1
        elif not self.ignored and tag in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored:
            self.ignored -= 1
        elif not self.ignored and tag in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            self.parts.append(data)

    def text(self) -> str:
        return clean_text("".join(self.parts))


def html_text(fragment: str) -> str:
    parser = TextParser()
    parser.feed(fragment)
    return parser.text()


class ElementTextParser(TextParser):
    def __init__(self, element_id: str) -> None:
        super().__init__()
        self.element_id = element_id
        self.active = False
        self.depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if not self.active and attributes.get("id") == self.element_id:
            self.active = True
            self.depth = 1
            return
        if not self.active:
            return
        if tag == "div":
            self.depth += 1
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if not self.active:
            return
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.active = False
                return
        super().handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.active:
            super().handle_data(data)


def fetch(url: str, cache_path: Path, refresh: bool = False) -> str:
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    safe_url = urllib.parse.quote(url, safe=":/?=&%")
    request = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read().decode("utf-8", "ignore")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(body, encoding="utf-8")
    time.sleep(0.04)
    return body


def aon_rows(source: str) -> list[dict]:
    table_match = re.search(
        r'<table\b[^>]*id="MainContent_GridViewArchetypes"[^>]*>.*?</table>',
        source,
        re.I | re.S,
    )
    if not table_match:
        return []
    rows: list[dict] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", table_match.group(0), re.I | re.S):
        cells = re.findall(r"<td\b.*?>(.*?)</td>", row_html, re.I | re.S)
        if len(cells) < 3:
            continue
        link = re.search(
            r'href="([^"]*ArchetypeDisplay\.aspx\?FixedName=[^"]+)"', cells[0], re.I
        )
        if not link:
            continue
        rows.append(
            {
                "name": html_text(cells[0]),
                "replaces": html_text(cells[1]),
                "summary": html_text(cells[2]),
                "source_url": urllib.parse.urljoin(
                    "https://www.aonprd.com/", html.unescape(link.group(1))
                ),
            }
        )
    return rows


def aon_rules(source: str) -> tuple[str, str]:
    match = re.search(
        r'<span id="MainContent_DataListTypes_LabelName_0">(.*?)</span>', source, re.I | re.S
    )
    if not match:
        return "", ""
    fragment = match.group(1)
    source_match = re.search(r"<b>Source</b>\s*(.*?)<br\s*/?>", fragment, re.I | re.S)
    source_name = html_text(source_match.group(1)) if source_match else "Pathfinder Roleplaying Game"
    return source_name, html_text(fragment)


def sphere_groups(source: str, allowed_names: set[str]) -> list[dict]:
    start = source.find('<h2 id="toc6"')
    if start < 0:
        return []
    end = source.find('<h2 id="toc7"', start)
    section = source[start : end if end >= 0 else len(source)]
    pattern = re.compile(r"<strong>([^<]+)</strong>\s*\((.*?)\)<br\s*/?>", re.I | re.S)
    aliases = {
        "Barbarian, Unchained": "Barbarian (Unchained)",
        "Monk, Unchained": "Monk (Unchained)",
        "Rogue, Unchained": "Rogue (Unchained)",
        "Summoner, Unchained": "Summoner (Unchained)",
    }
    result: list[dict] = []
    for match in pattern.finditer(section):
        parent_name = aliases.get(html_text(match.group(1)), html_text(match.group(1)))
        parent_is_class = parent_name in allowed_names
        body = match.group(2)
        for link in re.finditer(
            r'(?:<span[^>]*color:\s*(#[0-9a-f]+)[^>]*>)?\s*<a href="(/[^"]+)">(.*?)</a>',
            body,
            re.I | re.S,
        ):
            name = html_text(link.group(3))
            if not name or "alternate class feature" in name.casefold():
                continue
            override = SPHERE_ARCHETYPE_PARENT_OVERRIDES.get(slug(name))
            if not parent_is_class and override is None:
                continue
            result.append(
                {
                    "name": name,
                    "class_name": override[1] if override else parent_name,
                    "class_key_override": override[0] if override else "",
                    "color": (link.group(1) or "").casefold(),
                    "source_url": urllib.parse.urljoin(
                        "https://spheresofpower.wikidot.com/", link.group(2)
                    ),
                }
            )
    return result


def wikidot_rules(source: str) -> tuple[str, str]:
    title = re.search(r'<div id="page-title">(.*?)</div>', source, re.I | re.S)
    parser = ElementTextParser("page-content")
    parser.feed(source)
    return html_text(title.group(1)) if title else "Spheres of Power Wiki", parser.text()


def sphere_capabilities(color: str, rules: str, class_name: str, name: str) -> dict:
    grants: set[str] = set()
    removes: set[str] = set()
    # Wiki link colors are part of the site's own system taxonomy.
    if color == "#993300":
        grants.add("martial")
    elif color == "#00c000":
        grants.update(("magic", "martial"))
    elif color == "#b900fe":
        grants.add("skill")
    else:
        grants.add("magic")
    folded = rules.casefold()
    if any(term in folded for term in ("martial talent", "combat training", "martial tradition")):
        grants.add("martial")
    if any(term in folded for term in ("magic talent", "casting tradition", "spherecasting")):
        grants.add("magic")
    if any(term in folded for term in ("skill talent", "trade tradition")):
        grants.add("skill")
    if class_name == "Prodigy":
        grants.add("sequence")
    if class_name == "Prodigy" and name == "Battle-Born":
        removes.add("magic")
    if re.search(
        r"replaces?\s+(?:the\s+)?(?:spells?|spellcasting|extracts?)\s+class feature",
        rules,
        re.I,
    ):
        removes.add("traditional_spells")
    return {"grants": sorted(grants), "removes": sorted(removes)}


def _load_detail(entry: dict, source_group: str, refresh: bool) -> dict:
    url = entry["source_url"]
    cache = CACHE_ROOT / source_group.casefold() / f"{slug(entry['class_name'])}--{slug(entry['name'])}.html"
    try:
        source = fetch(url, cache, refresh)
        source_name, rules = aon_rules(source) if source_group == "Pathfinder" else wikidot_rules(source)
    except Exception as error:  # retain the index entry even if a detail page is temporarily unavailable
        source_name, rules = source_group, ""
        entry["import_warning"] = str(error)
    entry["source"] = source_name or source_group
    entry["description"] = rules or entry.get("summary", "")
    if source_group == "Spheres":
        entry["sphere_capabilities"] = sphere_capabilities(
            entry.pop("color", ""), entry["description"], entry["class_name"], entry["name"]
        )
        entry = normalize_spheres_archetype_codex_entry(entry)
    else:
        entry["sphere_capabilities"] = {"grants": [], "removes": []}
    return entry


def build_catalog(refresh: bool = False, workers: int = 8) -> dict:
    class_doc = json.loads(CLASS_FILE.read_text(encoding="utf-8"))
    classes = list(class_doc["entries"])
    class_by_name = {str(entry["name"]): entry for entry in classes}
    # Prodigy is maintained by the Spheres catalog rather than the Paizo class importer.
    class_by_name["Prodigy"] = {"key": "prodigy", "name": "Prodigy", "category": "Spheres"}
    entries: list[dict] = []

    for class_name, class_entry in class_by_name.items():
        if class_name == "Prodigy":
            continue
        url = "https://www.aonprd.com/Archetypes.aspx?Class=" + urllib.parse.quote(class_name)
        source = fetch(url, CACHE_ROOT / "pathfinder" / "indexes" / f"{slug(class_name)}.html", refresh)
        for row in aon_rows(source):
            row.update(
                {
                    "key": f"pathfinder-archetype:{class_entry['key']}:{slug(row['name'])}",
                    "class_key": class_entry["key"],
                    "class_name": class_name,
                    "source_group": "Pathfinder",
                }
            )
            entries.append(row)

    home = fetch(
        "https://spheresofpower.wikidot.com/",
        CACHE_ROOT / "spheres" / "archetype-index.html",
        refresh,
    )
    for row in sphere_groups(home, set(class_by_name)):
        class_key_override = str(row.pop("class_key_override", "") or "")
        class_entry = (
            {"key": class_key_override}
            if class_key_override
            else class_by_name[row["class_name"]]
        )
        row.update(
            {
                "key": f"spheres-archetype:{class_entry['key']}:{slug(row['name'])}",
                "class_key": class_entry["key"],
                "source_group": "Spheres",
                "summary": "",
                "replaces": "",
            }
        )
        entries.append(row)

    # Prodigy keeps its archetype index on the class page instead of the wiki's
    # general archetype block. Keep this source-specific routing in the importer,
    # not in the runtime catalog or UI.
    prodigy_source = fetch(
        "http://spheresofpower.wikidot.com/prodigy",
        CACHE_ROOT / "spheres" / "prodigy-class.html",
        refresh,
    )
    prodigy_names = {
        "Battle-Born", "Chromamancer", "Exploitant", "Extemporizer",
        "Gutter Rat", "Mimic", "Sync", "Void Dancer",
    }
    for link in re.finditer(r'<a href="(/[^"]+)">(.*?)</a>', prodigy_source, re.I | re.S):
        name = html_text(link.group(2))
        if name not in prodigy_names:
            continue
        entries.append(
            {
                "key": f"spheres-archetype:prodigy:{slug(name)}",
                "class_key": "prodigy",
                "class_name": "Prodigy",
                "source_group": "Spheres",
                "source_url": urllib.parse.urljoin(
                    "https://spheresofpower.wikidot.com/", link.group(1)
                ),
                "summary": "",
                "replaces": "",
                "name": name,
                "color": "#00c000",
            }
        )

    # Duplicate names can legitimately exist for different parent classes; identical
    # class/source links are index aliases and should only appear once.
    unique = {entry["key"]: entry for entry in entries}
    entries = list(unique.values())
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_load_detail, dict(entry), entry["source_group"], refresh): entry["key"]
            for entry in entries
        }
        loaded = []
        for future in as_completed(futures):
            loaded.append(future.result())
    loaded.sort(key=lambda item: (item["class_name"].casefold(), item["source_group"], item["name"].casefold()))
    return {
        "version": 1,
        "sources": [
            {"name": "Archives of Nethys", "url": "https://www.aonprd.com/Archetypes.aspx"},
            {"name": "Spheres of Power Wiki", "url": "https://spheresofpower.wikidot.com/"},
        ],
        "entries": loaded,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local Pathfinder/Spheres archetype catalog.")
    parser.add_argument("--refresh", action="store_true", help="Ignore the reusable source cache.")
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args()
    document = build_catalog(arguments.refresh, arguments.workers)
    OUTPUT_FILE.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    pathfinder = sum(entry["source_group"] == "Pathfinder" for entry in document["entries"])
    spheres = len(document["entries"]) - pathfinder
    print(f"Wrote {len(document['entries'])} archetypes ({pathfinder} Pathfinder, {spheres} Spheres) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
