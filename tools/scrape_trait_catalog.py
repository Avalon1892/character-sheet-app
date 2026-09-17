from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from lxml import html

from scrape_magic_catalog import current_rules_scope
from scrape_martial_catalog import (
    BASE_URL as SPHERES_BASE_URL,
    SOURCE_TAG_PATTERN,
    clean_text,
    description_after,
    fetch,
    heading_level,
    source_tags,
)


AON_TRAITS_URL = "https://aonprd.com/Traits.aspx"
SPHERES_POWER_TRAITS_URL = f"{SPHERES_BASE_URL}/traits"
SPHERES_MIGHT_TRAITS_URL = f"{SPHERES_BASE_URL}/practitioner-traits"

KNOWN_TRAIT_TYPES = {
    "campaign",
    "combat",
    "drawback",
    "equipment",
    "faith",
    "legacy",
    "magic",
    "race",
    "racial",
    "region",
    "religion",
    "social",
    "tradition",
}

LEGACY_SECTIONS = {
    "ascension",
    "dynasty",
    "final mission",
    "isolation",
    "mentorship",
    "rulership",
    "survived by works",
    "transformation",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _aon_item_name(href: str) -> str:
    return parse_qs(urlparse(href).query).get("ItemName", [""])[0].strip()


def _aon_category_label(value: str) -> str:
    match = re.fullmatch(r"Basic \(([^)]+)\)", value, re.IGNORECASE)
    return match.group(1).title() if match else value


def aon_category_links(payload: bytes) -> dict[str, str]:
    document = html.fromstring(payload)
    result: dict[str, str] = {}
    for link in document.xpath("//a[contains(@href, 'Traits.aspx?Type=')]"):
        href = urljoin(AON_TRAITS_URL, str(link.get("href"))).replace(" ", "%20")
        category = parse_qs(urlparse(href).query).get("Type", [""])[0].strip()
        if category:
            result.setdefault(category, href)
    return result


def _heading_segment(heading) -> tuple[str, str]:
    """Return the source label and rules text following an AoN trait heading."""
    parent = heading.getparent()
    if parent is None:
        return "", ""
    siblings = list(parent)
    try:
        index = siblings.index(heading)
    except ValueError:
        return "", ""
    source = ""
    pieces: list[str] = []
    after_source_break = False
    if heading.tail:
        pieces.append(heading.tail)
    for node in siblings[index + 1 :]:
        level = heading_level(node)
        if level is not None and level <= 2:
            break
        if not source and str(node.tag).lower() == "a":
            source = clean_text(node.text_content())
        if str(node.tag).lower() == "br" and not after_source_break:
            after_source_break = True
        if after_source_break:
            # lxml's ``itertext(with_tail=True)`` includes descendant tails but not
            # the current element's own tail. AoN stores most rules text in the
            # tail of the first line break, so append it explicitly.
            pieces.append("".join(node.itertext()) + (node.tail or ""))
    return source, clean_text(" ".join(pieces))


def _campaign_group(heading) -> str:
    parent = heading.getparent()
    if parent is None:
        return ""
    group = ""
    for node in list(parent):
        if node is heading:
            break
        if heading_level(node) == 1:
            group = clean_text(node.text_content())
    return group


def parse_aon_page(payload: bytes, raw_category: str) -> list[dict]:
    document = html.fromstring(payload)
    category = _aon_category_label(raw_category)
    result: list[dict] = []
    for heading in document.xpath(
        "//h2[.//a[contains(@href, 'TraitDisplay.aspx?ItemName=')]]"
    ):
        link = next(
            (
                node
                for node in heading.xpath(".//a[@href]")
                if "TraitDisplay.aspx?ItemName=" in str(node.get("href"))
            ),
            None,
        )
        if link is None:
            continue
        item_name = _aon_item_name(str(link.get("href")))
        name = item_name or re.sub(
            r"\s*\[\s*Link\s*\]\s*$", "", clean_text(heading.text_content())
        )
        if not name:
            continue
        source_book, description = _heading_segment(heading)
        if not description:
            continue
        tags: list[str] = []
        group = _campaign_group(heading)
        if raw_category.casefold() == "campaign" and group:
            tags.append(group)
        for image in heading.xpath(".//img[@title]"):
            title = clean_text(str(image.get("title")))
            if title:
                tags.append(title)
        result.append(
            {
                "key": f"aon:{slugify(item_name or name)}",
                "name": name,
                "categories": [category],
                "source_group": "Pathfinder",
                "source_name": "Archives of Nethys",
                "source_book": source_book,
                "description": description,
                "source_tags": sorted(set(tags), key=str.casefold),
                "source_url": (
                    "https://aonprd.com/TraitDisplay.aspx?ItemName="
                    + quote_plus(item_name or name)
                ),
                "repeatable": False,
                "full_rules": True,
            }
        )
    return result


def merge_entries(entries: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for entry in entries:
        key = str(entry["key"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = entry
            continue
        existing["categories"] = sorted(
            set(existing["categories"]) | set(entry["categories"]), key=str.casefold
        )
        existing["source_tags"] = sorted(
            set(existing.get("source_tags", [])) | set(entry.get("source_tags", [])),
            key=str.casefold,
        )
        if len(str(entry["description"])) > len(str(existing["description"])):
            for field in ("description", "source_book", "source_url"):
                existing[field] = entry[field]
    return sorted(merged.values(), key=lambda item: str(item["name"]).casefold())


def build_aon_catalog(main_payload: bytes, workers: int) -> list[dict]:
    links = aon_category_links(main_payload)
    entries: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch, url): category for category, url in links.items()
        }
        for future in as_completed(futures):
            category = futures[future]
            parsed = parse_aon_page(future.result(), category)
            entries.extend(parsed)
            print(f"Parsed Pathfinder traits: {category} ({len(parsed)})", flush=True)
    return merge_entries(entries)


def _section_category(section: str) -> str:
    clean = SOURCE_TAG_PATTERN.sub("", section).strip()
    lower = clean.casefold()
    if "legacy" in lower:
        return "Legacy"
    if "campaign" in lower:
        return "Campaign"
    clean = re.sub(r"\s+Traits?$", "", clean, flags=re.IGNORECASE).strip()
    return clean.title() if clean else "General"


def _spheres_name_and_categories(raw_name: str, section: str) -> tuple[str, list[str]]:
    tags_removed = SOURCE_TAG_PATTERN.sub("", raw_name).strip()
    categories = {_section_category(section)}

    def replace_group(match: re.Match[str]) -> str:
        values = [value.strip() for value in match.group(1).split(",")]
        if values and all(value.casefold() in KNOWN_TRAIT_TYPES for value in values):
            categories.update(value.title() for value in values)
            return ""
        return match.group(0)

    name = re.sub(r"\(([^()]*)\)", replace_group, tags_removed)
    name = re.sub(r"\s+", " ", name).strip(" -")
    categories.discard("General") if len(categories) > 1 else None
    return name, sorted(categories, key=str.casefold)


def _heading_anchor(node) -> str:
    if node.get("id"):
        return str(node.get("id"))
    child = next((item for item in node.xpath(".//*[@id]") if item.get("id")), None)
    return "" if child is None else str(child.get("id"))


def _legacy_entry(
    section_name: str, description: str, source_url: str, raw_heading: str
) -> dict | None:
    match = re.search(
        r"(?:^|\n)([^\n:]{2,100})\s+\[([^\]]+)\]:\s*(.+)\Z",
        description,
        re.DOTALL,
    )
    if match is None:
        return None
    name = clean_text(match.group(1))
    categories = [value.strip().title() for value in match.group(2).split(",")]
    return {
        "key": f"spheres-power:{slugify(name)}",
        "name": name,
        "categories": sorted(set(categories + ["Legacy"]), key=str.casefold),
        "source_group": "Spheres of Power",
        "source_name": "Spheres of Power Wiki",
        "source_book": "",
        "description": clean_text(match.group(3)),
        "source_tags": source_tags(raw_heading),
        "source_url": source_url,
        "repeatable": False,
        "full_rules": True,
        "section": section_name,
    }


def parse_spheres_page(
    payload: bytes, page_url: str, source_group: str, current_tab_only: bool
) -> list[dict]:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    scope = current_rules_scope(content) if current_tab_only else content
    for node in scope.xpath(
        ".//script|.//style|.//*[@id='toc']|.//*[contains(@class, 'page-tags')]"
    ):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    active_section = "General"
    result: list[dict] = []
    for heading in scope.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6"):
        level = heading_level(heading)
        raw_heading = clean_text(heading.text_content())
        if level in {1, 2, 3}:
            active_section = raw_heading
            continue
        if level != 4 or not raw_heading:
            continue
        parent = heading.getparent()
        if parent is None:
            continue
        siblings = list(parent)
        description = description_after(siblings, siblings.index(heading), 4)
        if not description:
            continue
        anchor = _heading_anchor(heading)
        url = f"{page_url}#{anchor}" if anchor else page_url
        normalized_heading = SOURCE_TAG_PATTERN.sub("", raw_heading).strip().casefold()
        if normalized_heading.startswith("optional rule:"):
            continue
        if source_group == "Spheres of Power" and normalized_heading in LEGACY_SECTIONS:
            legacy = _legacy_entry(active_section, description, url, raw_heading)
            if legacy is not None:
                result.append(legacy)
            continue
        name, categories = _spheres_name_and_categories(raw_heading, active_section)
        if not name:
            continue
        prefix = "spheres-power" if source_group == "Spheres of Power" else "spheres-might"
        result.append(
            {
                "key": f"{prefix}:{slugify(name)}",
                "name": name,
                "categories": categories,
                "source_group": source_group,
                "source_name": "Spheres of Power Wiki",
                "source_book": "",
                "description": description,
                "source_tags": source_tags(raw_heading),
                "source_url": url,
                "repeatable": False,
                "full_rules": True,
                "section": active_section,
            }
        )
    return merge_entries(result)


def build_catalog(workers: int = 6) -> dict:
    with ThreadPoolExecutor(max_workers=3) as executor:
        aon_future = executor.submit(fetch, AON_TRAITS_URL)
        power_future = executor.submit(fetch, SPHERES_POWER_TRAITS_URL)
        might_future = executor.submit(fetch, SPHERES_MIGHT_TRAITS_URL)
        aon_payload = aon_future.result()
        power_payload = power_future.result()
        might_payload = might_future.result()
    print("Downloaded trait indexes", flush=True)
    aon_entries = build_aon_catalog(aon_payload, workers)
    power_entries = parse_spheres_page(
        power_payload, SPHERES_POWER_TRAITS_URL, "Spheres of Power", True
    )
    might_entries = parse_spheres_page(
        might_payload, SPHERES_MIGHT_TRAITS_URL, "Spheres of Might", False
    )
    entries = aon_entries + power_entries + might_entries
    keys = [str(entry["key"]) for entry in entries]
    if len(aon_entries) < 1000:
        raise RuntimeError(f"Pathfinder trait catalog unexpectedly small: {len(aon_entries)}")
    if len(power_entries) < 90:
        raise RuntimeError(f"Spheres of Power trait catalog unexpectedly small: {len(power_entries)}")
    if len(might_entries) < 15:
        raise RuntimeError(f"Spheres of Might trait catalog unexpectedly small: {len(might_entries)}")
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate trait catalog keys were generated.")
    if any(not entry["name"] or not entry["description"] for entry in entries):
        raise RuntimeError("A trait is missing its name or description.")
    return {
        "format": "character-sheet-trait-catalog",
        "version": 1,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [
            AON_TRAITS_URL,
            SPHERES_POWER_TRAITS_URL,
            SPHERES_MIGHT_TRAITS_URL,
        ],
        "counts": {
            "pathfinder": len(aon_entries),
            "spheres_power": len(power_entries),
            "spheres_might": len(might_entries),
            "total": len(entries),
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "pf1e" / "traits.json",
    )
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    catalog = build_catalog(args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    counts = catalog["counts"]
    print(
        f"Wrote {counts['total']} traits to {args.output} "
        f"({counts['pathfinder']} Pathfinder, {counts['spheres_power']} Spheres of Power, "
        f"{counts['spheres_might']} Spheres of Might)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
