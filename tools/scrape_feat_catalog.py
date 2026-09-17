from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from lxml import html

from scrape_magic_catalog import SPHERES as MAGIC_SPHERES
from scrape_magic_catalog import current_rules_scope
from scrape_martial_catalog import (
    BASE_URL as SPHERES_BASE_URL,
    PREREQUISITE_PATTERN,
    SOURCE_TAG_PATTERN,
    clean_text,
    description_after,
    fetch,
    heading_level,
    source_tags,
)


AON_FEATS_URL = "https://aonprd.com/Feats.aspx"
SPHERES_FEATS_URL = f"{SPHERES_BASE_URL}/feats"

KNOWN_FEAT_TYPES = {
    "achievement",
    "admixture",
    "alignment",
    "anathema",
    "ante",
    "aristeia",
    "armor mastery",
    "armor style",
    "betrayal",
    "blood hex",
    "called shot",
    "chance",
    "champion",
    "channeling",
    "combat",
    "combination",
    "companion",
    "conduit",
    "counterspell",
    "coven",
    "critical",
    "damnation",
    "deck",
    "defiler",
    "drawback",
    "dual sphere",
    "esoteric",
    "faction",
    "familiar",
    "grit",
    "hero point",
    "item creation",
    "item mastery",
    "meditation",
    "metamagic",
    "monster",
    "necrosis",
    "origin",
    "panache",
    "performance",
    "plague",
    "practitioner",
    "protokinesis",
    "proxy",
    "purring",
    "racial",
    "ritual",
    "shield mastery",
    "shield style",
    "skybourne",
    "squadron",
    "stare",
    "story",
    "style",
    "surreal",
    "targeting",
    "teamwork",
    "theurge",
    "trick",
    "weapon mastery",
    "wild magic",
    "words of power",
}

REPEATABLE_PATHFINDER_FEATS = {
    "ability focus",
    "armor focus",
    "craft magic arms and armor",
    "elemental focus",
    "exotic weapon proficiency",
    "extra channel",
    "extra discovery",
    "extra evolution",
    "extra hex",
    "extra ki",
    "extra lay on hands",
    "extra performance",
    "extra rage",
    "extra revelation",
    "extra rogue talent",
    "extra wild talent",
    "favored prestige class",
    "greater elemental focus",
    "greater spell focus",
    "greater weapon focus",
    "greater weapon specialization",
    "improved critical",
    "martial weapon proficiency",
    "skill focus",
    "spell focus",
    "spell mastery",
    "weapon focus",
    "weapon specialization",
}

MULTIPLE_TIMES_PATTERN = re.compile(
    r"(?:may|can)\s+(?:take|select|gain|choose)\s+this\s+feat\s+multiple\s+times",
    re.IGNORECASE,
)
BENEFIT_PATTERN = re.compile(r"\bBenefits?:", re.IGNORECASE)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def aon_item_name(href: str) -> str:
    return parse_qs(urlparse(href).query).get("ItemName", [""])[0].strip()


def clean_aon_name(raw_name: str) -> str:
    return re.sub(r"[\s*⊤]+$", "", clean_text(raw_name)).strip()


def aon_rows(payload: bytes) -> list:
    document = html.fromstring(payload)
    return document.xpath(
        "//table//tr[td[1]//a[contains(@href, 'FeatDisplay.aspx?ItemName=')]]"
    )


def parse_aon_entries(payload: bytes) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for row in aon_rows(payload):
        cells = row.xpath("./td")
        if len(cells) < 3:
            continue
        link = next(
            (
                node
                for node in cells[0].xpath(".//a[@href]")
                if "FeatDisplay.aspx?ItemName=" in str(node.get("href"))
            ),
            None,
        )
        if link is None:
            continue
        item_name = aon_item_name(str(link.get("href")))
        name = clean_aon_name(link.text_content()) or item_name
        if not item_name or not name:
            continue
        lookup_key = item_name.casefold()
        prerequisites = clean_text(cells[1].text_content()).strip("— ")
        summary = clean_text(cells[2].text_content()) or (
            "Open the source page for this feat's complete rules."
        )
        raw_name = clean_text(link.text_content())
        tags: list[str] = []
        if "*" in raw_name:
            tags.append("Combat")
        for image in cells[0].xpath(".//img[@title]"):
            title = clean_text(str(image.get("title")))
            if title:
                tags.append(title)
        entries[lookup_key] = {
            "key": f"aon:{slugify(item_name)}",
            "name": name,
            "categories": [],
            "source_group": "Pathfinder",
            "source_name": "Archives of Nethys",
            "description": summary,
            "prerequisites": prerequisites,
            "source_tags": sorted(set(tags)),
            "source_url": (
                "https://aonprd.com/FeatDisplay.aspx?ItemName=" + quote_plus(item_name)
            ),
            "sphere": "",
            "repeatable": name.casefold() in REPEATABLE_PATHFINDER_FEATS,
            "full_rules": False,
        }
    return entries


def aon_category_links(payload: bytes) -> dict[str, str]:
    document = html.fromstring(payload)
    result: dict[str, str] = {}
    for link in document.xpath("//a[contains(@href, 'Feats.aspx?Category=')]"):
        category = clean_text(link.text_content())
        href = urljoin(AON_FEATS_URL, str(link.get("href"))).replace(" ", "%20")
        query_category = parse_qs(urlparse(href).query).get("Category", [""])[0]
        category = query_category or category
        if category and query_category:
            result.setdefault(category, href)
    return result


def aon_category_item_names(payload: bytes) -> set[str]:
    names: set[str] = set()
    for row in aon_rows(payload):
        link = next(
            (
                node
                for node in row.xpath("./td[1]//a[@href]")
                if "FeatDisplay.aspx?ItemName=" in str(node.get("href"))
            ),
            None,
        )
        if link is not None:
            name = aon_item_name(str(link.get("href")))
            if name:
                names.add(name.casefold())
    return names


def build_aon_catalog(main_payload: bytes, workers: int) -> list[dict]:
    entries = parse_aon_entries(main_payload)
    category_links = aon_category_links(main_payload)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch, url): category
            for category, url in category_links.items()
        }
        for future in as_completed(futures):
            category = futures[future]
            for item_name in aon_category_item_names(future.result()):
                if item_name in entries:
                    entries[item_name]["categories"].append(category)
            print(f"Mapped Pathfinder category: {category}", flush=True)
    for entry in entries.values():
        categories = sorted(set(entry["categories"]), key=str.casefold)
        if "Combat" in entry["source_tags"] and "Combat" not in categories:
            categories.append("Combat")
        entry["categories"] = categories or ["General"]
    return sorted(entries.values(), key=lambda item: item["name"].casefold())


def spheres_category_links(payload: bytes) -> dict[str, str]:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    result: dict[str, str] = {}
    for link in content.xpath(".//a[@href]"):
        href = str(link.get("href"))
        label = SOURCE_TAG_PATTERN.sub("", clean_text(link.text_content())).strip()
        if (
            not href.startswith("/")
            or not href.endswith("-feats")
            or not label.casefold().endswith("feats")
        ):
            continue
        category = re.sub(r"\s+Feats$", "", label, flags=re.IGNORECASE).strip()
        if category:
            result.setdefault(category, urljoin(SPHERES_BASE_URL, href))
    result.setdefault("Operative", f"{SPHERES_BASE_URL}/operative-feats")
    return result


def feat_types_and_name(raw_heading: str, page_category: str) -> tuple[str, list[str]]:
    tags_removed = SOURCE_TAG_PATTERN.sub("", raw_heading).strip()
    types: list[str] = []

    def replace_group(match: re.Match[str]) -> str:
        values = [value.strip() for value in match.group(1).split(",") if value.strip()]
        if values and all(value.casefold() in KNOWN_FEAT_TYPES for value in values):
            types.extend(value.title() for value in values)
            return ""
        return match.group(0)

    name = re.sub(r"\(([^()]*)\)", replace_group, tags_removed)
    name = re.sub(r"\s+", " ", name).strip(" -")
    if page_category and page_category.casefold() not in {
        "general",
        "new",
        "sphere-focused",
    }:
        types.append(page_category)
    return name, sorted(set(types), key=str.casefold)


def feat_anchor(node) -> str:
    if node.get("id"):
        return str(node.get("id"))
    child = next((item for item in node.xpath(".//*[@id]") if item.get("id")), None)
    return "" if child is None else str(child.get("id"))


def parse_spheres_page(
    payload: bytes,
    page_url: str,
    page_category: str,
    sphere_name: str = "",
    section_only: bool = False,
) -> list[dict]:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    scope = current_rules_scope(content)
    for node in scope.xpath(
        ".//script|.//style|.//*[@id='toc']|.//*[contains(@class, 'page-tags')]"
    ):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    headings = scope.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")
    active_section = not section_only
    active_category = page_category
    active_level = 0
    result: list[dict] = []
    for node in headings:
        level = heading_level(node)
        if level is None:
            continue
        heading = clean_text(node.text_content())
        lower = heading.casefold()
        if section_only and level <= 2:
            active_section = "feat" in lower and "old" not in lower
            active_category = re.sub(
                r"\s+(?:Sphere\s+)?Feats?$", "", heading, flags=re.IGNORECASE
            ).strip()
            if sphere_name and active_category.casefold() == sphere_name.casefold():
                active_category = "Sphere-Focused"
            active_level = level if active_section else 0
            continue
        if section_only and (not active_section or level <= active_level):
            continue
        if not section_only and level < 3:
            continue
        parent = node.getparent()
        if parent is None:
            continue
        siblings = list(parent)
        description = description_after(siblings, parent.index(node), level)
        if not description or not BENEFIT_PATTERN.search(description):
            continue
        name, types = feat_types_and_name(heading, active_category)
        if not name or name.casefold().endswith(" feats"):
            continue
        match = PREREQUISITE_PATTERN.search(description)
        prerequisites = clean_text(match.group(1)) if match else ""
        anchor = feat_anchor(node)
        result.append(
            {
                "key": f"spheres:{slugify(name)}",
                "name": name,
                "categories": types or ["General"],
                "source_group": "Spheres",
                "source_name": "Spheres of Power Wiki",
                "description": description,
                "prerequisites": prerequisites,
                "source_tags": source_tags(heading),
                "source_url": f"{page_url}#{anchor}" if anchor else page_url,
                "sphere": sphere_name,
                "repeatable": bool(MULTIPLE_TIMES_PATTERN.search(description)),
                "full_rules": True,
            }
        )
    return result


def merge_spheres_entries(entries: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for entry in entries:
        lookup_key = re.sub(r"[^a-z0-9]+", "", entry["name"].casefold())
        existing = merged.get(lookup_key)
        if existing is None:
            merged[lookup_key] = entry
            continue
        existing["categories"] = sorted(
            set(existing["categories"]) | set(entry["categories"]), key=str.casefold
        )
        existing["source_tags"] = sorted(
            set(existing["source_tags"]) | set(entry["source_tags"]), key=str.casefold
        )
        spheres = [value for value in (existing["sphere"], entry["sphere"]) if value]
        existing["sphere"] = ", ".join(
            sorted(set(", ".join(spheres).split(", ")) - {""}, key=str.casefold)
        )
        existing["repeatable"] = existing["repeatable"] or entry["repeatable"]
        if len(entry["description"]) > len(existing["description"]):
            for field in ("description", "prerequisites", "source_url"):
                existing[field] = entry[field]
    return sorted(merged.values(), key=lambda item: item["name"].casefold())


def build_spheres_catalog(main_payload: bytes, workers: int) -> list[dict]:
    category_links = spheres_category_links(main_payload)
    jobs: dict[str, tuple[str, str, bool]] = {
        f"category:{category}": (url, category, False)
        for category, url in category_links.items()
    }
    for sphere_name, sphere_slug in MAGIC_SPHERES:
        jobs[f"sphere:{sphere_name}"] = (
            f"{SPHERES_BASE_URL}/{sphere_slug}",
            sphere_name,
            True,
        )
    payloads: dict[str, bytes] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch, url): key
            for key, (url, _label, _section_only) in jobs.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            payloads[key] = future.result()
            print(f"Downloaded Spheres feats: {key}", flush=True)
    entries: list[dict] = []
    for key, (url, label, section_only) in jobs.items():
        parsed = parse_spheres_page(
            payloads[key],
            url,
            label if not section_only else "Sphere-Focused",
            label if section_only else "",
            section_only,
        )
        entries.extend(parsed)
        print(f"Parsed Spheres feats: {key} ({len(parsed)})", flush=True)
    return merge_spheres_entries(entries)


def build_catalog(workers: int = 6) -> dict:
    with ThreadPoolExecutor(max_workers=2) as executor:
        aon_future = executor.submit(fetch, AON_FEATS_URL)
        spheres_future = executor.submit(fetch, SPHERES_FEATS_URL)
        aon_payload = aon_future.result()
        spheres_payload = spheres_future.result()
    print("Downloaded feat indexes", flush=True)
    aon_entries = build_aon_catalog(aon_payload, workers)
    spheres_entries = build_spheres_catalog(spheres_payload, workers)
    entries = aon_entries + spheres_entries
    keys = [entry["key"] for entry in entries]
    if len(aon_entries) < 3400:
        raise RuntimeError(f"Pathfinder feat catalog unexpectedly small: {len(aon_entries)}")
    if len(spheres_entries) < 500:
        raise RuntimeError(f"Spheres feat catalog unexpectedly small: {len(spheres_entries)}")
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate feat catalog keys were generated.")
    if any(not entry["name"] or not entry["description"] for entry in entries):
        raise RuntimeError("A feat is missing its name or description.")
    return {
        "format": "character-sheet-feat-catalog",
        "version": 1,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [AON_FEATS_URL, SPHERES_FEATS_URL],
        "counts": {
            "pathfinder": len(aon_entries),
            "spheres": len(spheres_entries),
            "total": len(entries),
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "pf1e" / "feats.json",
    )
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    catalog = build_catalog(args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {catalog['counts']['total']} feats to {args.output} "
        f"({catalog['counts']['pathfinder']} Pathfinder, "
        f"{catalog['counts']['spheres']} Spheres)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
