from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from lxml import html

from scrape_martial_catalog import (
    BASE_URL,
    HEADING_TAGS,
    PREREQUISITE_PATTERN,
    SOURCE_TAG_PATTERN,
    clean_text,
    description_after,
    entry_key,
    fetch,
    heading_level,
    source_tags,
)


CASTING_TRADITIONS_URL = f"{BASE_URL}/casting-traditions"
SPHERES = (
    ("Alteration", "alteration"),
    ("Blood", "blood"),
    ("Conjuration", "conjuration"),
    ("Creation", "creation"),
    ("Dark", "dark"),
    ("Death", "death"),
    ("Destruction", "destruction"),
    ("Divination", "divination"),
    ("Enhancement", "enhancement"),
    ("Fallen Fey", "fallen-fey"),
    ("Fate", "fate"),
    ("Illusion", "illusion"),
    ("Life", "life"),
    ("Light", "light"),
    ("Mana", "mana"),
    ("Mind", "mind"),
    ("Nature", "nature"),
    ("Protection", "protection"),
    ("Telekinesis", "telekinesis"),
    ("Time", "time"),
    ("War", "war"),
    ("Warp", "warp"),
    ("Weather", "weather"),
)

# Reviewed heading ranges on the combined casting-traditions page.  Content
# after Weather continues at the same heading depth with drawback feats, boons,
# and class-specific drawbacks, so heading depth alone is insufficient.
SPHERE_DRAWBACK_TOC_RANGES = {
    "Alteration": (68, 74), "Blood": (76, 80), "Conjuration": (82, 90),
    "Creation": (92, 98), "Dark": (100, 110), "Death": (112, 119),
    "Destruction": (121, 126), "Divination": (128, 132),
    "Enhancement": (134, 139), "Fallen Fey": (141, 141),
    "Fate": (143, 149), "Illusion": (151, 157), "Life": (159, 167),
    "Light": (169, 176), "Mana": (178, 181), "Mind": (183, 192),
    "Nature": (194, 195), "Protection": (197, 206),
    "Telekinesis": (213, 218), "Time": (220, 223), "War": (225, 234),
    "Warp": (236, 245), "Weather": (247, 251),
}


def current_rules_scope(content):
    candidates = [
        node
        for node in content.xpath(".//div[@id]")
        if re.fullmatch(r"wiki-tab-\d+-0", str(node.get("id")))
    ]
    if not candidates:
        return content
    return min(candidates, key=lambda node: len(list(node.iterancestors())))


def section_category(section: str, sphere_name: str) -> str:
    section = SOURCE_TAG_PATTERN.sub("", section).strip()
    lower = section.casefold()
    if "advanced" in lower:
        return "Advanced Talent"
    stem = re.sub(r"\s+Talents?\s*$", "", section, flags=re.IGNORECASE).strip()
    if not stem or stem.casefold() in {
        sphere_name.casefold(),
        f"{sphere_name} sphere".casefold(),
        "magic",
    }:
        return "Talent"
    return f"{stem} Talent"


def heading_anchor(node) -> str:
    if node.get("id"):
        return str(node.get("id"))
    child = next((item for item in node.xpath(".//*[@id]") if item.get("id")), None)
    return "" if child is None else str(child.get("id"))


def parse_sphere(name: str, slug: str, payload: bytes) -> dict:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    scope = current_rules_scope(content)
    for node in scope.xpath(".//script|.//style|.//*[@id='toc']|.//*[contains(@class, 'page-tags')]"):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    headings = scope.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")

    first_talent_heading = next(
        (
            node
            for node in headings
            if (heading_level(node) or 9) <= 2
            and "talent" in clean_text(node.text_content()).casefold()
            and not any(
                excluded in clean_text(node.text_content()).casefold()
                for excluded in ("talent type", "class option", "sphere feat")
            )
        ),
        None,
    )
    base_pieces: list[str] = []
    for node in scope.iter():
        if node is first_talent_heading:
            break
        if str(node.tag).lower() not in HEADING_TAGS | {"p"}:
            continue
        text = clean_text(node.text_content())
        if text and "Spheres of Power\n$" not in text:
            base_pieces.append(text)

    talents: list[dict] = []
    active_section = ""
    active_level = 0
    for index, node in enumerate(headings):
        level = heading_level(node)
        if level is None:
            continue
        heading = clean_text(node.text_content())
        lower = heading.casefold()
        if level <= 2:
            if "talent" in lower and not any(
                excluded in lower
                for excluded in (
                    "talent type",
                    "class option",
                    "sphere feat",
                    "using talents",
                )
            ):
                active_section = heading
                active_level = level
            else:
                active_section = ""
                active_level = 0
            continue
        if not active_section or level <= active_level:
            continue
        if level < 4:
            following_levels = [
                heading_level(candidate)
                for candidate in headings[index + 1 :]
                if heading_level(candidate) is not None
            ]
            if following_levels and following_levels[0] > level:
                continue
        parent = node.getparent()
        if parent is None:
            continue
        siblings = list(parent)
        description = description_after(siblings, parent.index(node), level)
        if not description:
            continue
        category = section_category(active_section, name)
        match = PREREQUISITE_PATTERN.search(description)
        prerequisites = clean_text(match.group(1)) if match else ""
        anchor = heading_anchor(node)
        talents.append(
            {
                "key": entry_key(slug, category, heading),
                "name": heading,
                "category": category,
                "sphere": name,
                "description": description,
                "prerequisites": prerequisites,
                "source_tags": source_tags(heading),
                "source_url": f"{BASE_URL}/{slug}#{anchor}" if anchor else f"{BASE_URL}/{slug}",
            }
        )
    unique: dict[str, dict] = {}
    for talent in talents:
        unique.setdefault(talent["key"], talent)
    return {
        "name": name,
        "slug": slug,
        "source_url": f"{BASE_URL}/{slug}",
        "description": "\n".join(base_pieces),
        "talents": list(unique.values()),
    }


def parse_drawbacks(payload: bytes) -> tuple[dict[str, list[dict]], list[dict]]:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    scope = current_rules_scope(content)
    headings = scope.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")
    in_drawbacks = False
    sphere = ""
    result: dict[str, list[dict]] = {}
    universal: list[dict] = []
    sphere_names = {name for name, _ in SPHERES}
    for node in headings:
        level = heading_level(node)
        heading = clean_text(node.text_content())
        if level == 2:
            in_drawbacks = heading.casefold() == "sphere-specific drawbacks"
            sphere = ""
            continue
        if not in_drawbacks:
            continue
        if level == 3:
            sphere = SOURCE_TAG_PATTERN.sub("", heading).strip()
            if sphere in sphere_names:
                result.setdefault(sphere, [])
            continue
        if level != 4 or not sphere or (sphere not in sphere_names and sphere != "Universal"):
            continue
        parent = node.getparent()
        if parent is None:
            continue
        siblings = list(parent)
        description = description_after(siblings, parent.index(node), level)
        if not description:
            continue
        slug = next((slug for name, slug in SPHERES if name == sphere), "universal")
        anchor = heading_anchor(node)
        toc_match = re.fullmatch(r"toc(\d+)", anchor)
        limits = SPHERE_DRAWBACK_TOC_RANGES.get(sphere)
        if limits and toc_match and not (
            limits[0] <= int(toc_match.group(1)) <= limits[1]
        ):
            continue
        entry = {
            "key": entry_key(slug, "Drawback", heading),
            "name": heading,
            "category": "Drawback",
            "sphere": sphere,
            "description": description,
            "prerequisites": "",
            "source_tags": source_tags(heading),
            "source_url": (
                f"{CASTING_TRADITIONS_URL}#{anchor}" if anchor else CASTING_TRADITIONS_URL
            ),
        }
        if sphere == "Universal":
            universal.append(entry)
        else:
            result[sphere].append(entry)
    return result, universal


def build_catalog(workers: int = 6) -> dict:
    jobs = {name: f"{BASE_URL}/{slug}" for name, slug in SPHERES}
    jobs["__drawbacks__"] = CASTING_TRADITIONS_URL
    payloads: dict[str, bytes] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch, url): name for name, url in jobs.items()}
        for future in as_completed(futures):
            name = futures[future]
            payloads[name] = future.result()
            print(f"Downloaded {name}", flush=True)
    drawbacks, universal = parse_drawbacks(payloads["__drawbacks__"])
    spheres = []
    for name, slug in SPHERES:
        sphere = parse_sphere(name, slug, payloads[name])
        sphere["talents"].extend(drawbacks.get(name, []))
        sphere["talents"].sort(key=lambda item: (item["category"], item["name"].casefold()))
        spheres.append(sphere)
        print(f"Parsed {name}: {len(sphere['talents'])} talents/drawbacks", flush=True)
    universal.sort(key=lambda item: item["name"].casefold())
    return {
        "format": "character-sheet-magic-catalog",
        "version": 1,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [f"{BASE_URL}/", CASTING_TRADITIONS_URL],
        "spheres": spheres,
        "universal_drawbacks": universal,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "pf1e" / "magic_spheres.json",
    )
    parser.add_argument("--workers", type=int, default=6)
    arguments = parser.parse_args()
    catalog = build_catalog(max(1, arguments.workers))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    total = sum(len(sphere["talents"]) for sphere in catalog["spheres"])
    total += len(catalog["universal_drawbacks"])
    print(f"Wrote {len(catalog['spheres'])} spheres and {total} entries to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
