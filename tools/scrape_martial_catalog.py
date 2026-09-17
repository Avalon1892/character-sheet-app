from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from lxml import html


BASE_URL = "http://spheresofpower.wikidot.com"
MARTIAL_TRADITIONS_URL = f"{BASE_URL}/martial-traditions"
SPHERES = (
    ("Alchemy", "alchemy"),
    ("Athletics", "athletics"),
    ("Barrage", "barrage"),
    ("Barroom", "barroom"),
    ("Beastmastery", "beastmastery"),
    ("Berserker", "berserker"),
    ("Boxing", "boxing"),
    ("Brute", "brute"),
    ("Dual Wielding", "dual-wielding"),
    ("Duelist", "duelist"),
    ("Equipment", "equipment-sphere"),
    ("Fencing", "fencing"),
    ("Gladiator", "gladiator"),
    ("Guardian", "guardian"),
    ("Lancer", "lancer"),
    ("Open Hand", "open-hand"),
    ("Scoundrel", "scoundrel"),
    ("Scout", "scout"),
    ("Shield", "shield"),
    ("Sniper", "sniper"),
    ("Trap", "trap"),
    ("Warleader", "warleader-sphere"),
    ("Wrestling", "wrestling"),
    ("Leadership", "leadership"),
    ("Tech", "tech"),
    ("Tinker", "tinker"),
)
HEADING_TAGS = {f"h{level}" for level in range(1, 7)}
SOURCE_TAG_PATTERN = re.compile(r"\[[^\]]+\]")
PREREQUISITE_PATTERN = re.compile(
    r"(?:Prerequisites?|Requires?):\s*(.+?)(?=(?:\n|Benefit:|Special:|Associated Feat:|$))",
    re.IGNORECASE,
)


def clean_text(value: str) -> str:
    lines = []
    for line in value.replace("\xa0", " ").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines)


def heading_level(node) -> int | None:
    tag = str(node.tag).lower()
    return int(tag[1]) if tag in HEADING_TAGS else None


def fetch(url: str, attempts: int = 4) -> bytes:
    request = Request(url, headers={"User-Agent": "CharacterSheetApp/1.0 catalog builder"})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=45) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def description_after(children: list, index: int, item_level: int) -> str:
    pieces: list[str] = []
    for node in children[index + 1 :]:
        level = heading_level(node)
        if level is not None and level <= item_level:
            break
        if str(node.tag).lower() in {"script", "style", "hr"}:
            continue
        text = clean_text(node.text_content())
        if text:
            pieces.append(text)
    return "\n".join(pieces)


def section_category(section: str, sphere_name: str) -> str:
    section = SOURCE_TAG_PATTERN.sub("", section).strip()
    if "legendary" in section.lower():
        return "Legendary Talent"
    stem = re.sub(r"\s+Talents?\s*$", "", section, flags=re.IGNORECASE).strip()
    if not stem or stem.casefold() in {sphere_name.casefold(), "combat"}:
        return "Talent"
    return f"{stem} Talent"


def source_tags(name: str) -> list[str]:
    return [tag[1:-1] for tag in SOURCE_TAG_PATTERN.findall(name)]


def entry_key(slug: str, category: str, name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    category_key = re.sub(r"[^a-z0-9]+", "-", category.casefold()).strip("-")
    return f"{slug}:{category_key}:{normalized}"


def parse_sphere(name: str, slug: str, payload: bytes) -> dict:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    for node in content.xpath(".//script|.//style|.//*[@id='toc']|.//*[contains(@class, 'page-tags')]"):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    children = list(content)
    headings = content.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")

    first_talent_section: int | None = None
    for index, node in enumerate(children):
        level = heading_level(node)
        text = clean_text(node.text_content()) if level is not None else ""
        lower = text.casefold()
        if level is not None and level <= 2 and "talent" in lower and not any(
            excluded in lower for excluded in ("class option", "talent type", "about legendary")
        ):
            first_talent_section = index
            break

    base_pieces: list[str] = []
    if first_talent_section is not None:
        base_start = next(
            (
                index
                for index, node in enumerate(children[:first_talent_section])
                if heading_level(node) == 1
            ),
            0,
        )
        for node in children[base_start:first_talent_section]:
            if str(node.tag).lower() in {"script", "style", "hr"}:
                continue
            text = clean_text(node.text_content())
            if text and "Spheres of Might\n$" not in text:
                base_pieces.append(text)
    if not base_pieces:
        first_talent_heading = next(
            (
                node
                for node in headings
                if (heading_level(node) or 9) <= 2
                and "talent" in clean_text(node.text_content()).casefold()
                and not any(
                    excluded in clean_text(node.text_content()).casefold()
                    for excluded in ("class option", "talent type", "about legendary")
                )
            ),
            None,
        )
        for node in content.iter():
            if node is first_talent_heading:
                break
            if str(node.tag).lower() not in HEADING_TAGS | {"p"}:
                continue
            text = clean_text(node.text_content())
            if text and "Spheres of Might\n$" not in text:
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
                for excluded in ("class option", "talent type", "about legendary")
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
        prerequisites = ""
        match = PREREQUISITE_PATTERN.search(description)
        if match:
            prerequisites = clean_text(match.group(1))
        talents.append(
            {
                "key": entry_key(slug, category, heading),
                "name": heading,
                "category": category,
                "sphere": name,
                "description": description,
                "prerequisites": prerequisites,
                "source_tags": source_tags(heading),
                "source_url": f"{BASE_URL}/{slug}#{node.get('id')}" if node.get("id") else f"{BASE_URL}/{slug}",
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


def parse_drawbacks(payload: bytes) -> dict[str, list[dict]]:
    document = html.fromstring(payload)
    content = document.get_element_by_id("page-content")
    children = list(content)
    in_drawbacks = False
    sphere = ""
    result: dict[str, list[dict]] = {}
    for index, node in enumerate(children):
        level = heading_level(node)
        if level is None:
            continue
        heading = clean_text(node.text_content())
        if level == 1:
            in_drawbacks = heading.casefold() == "sphere-specific drawbacks"
            sphere = ""
            continue
        if not in_drawbacks:
            continue
        if level == 2:
            sphere = SOURCE_TAG_PATTERN.sub("", heading).strip()
            result.setdefault(sphere, [])
            continue
        if level != 4 or not sphere:
            continue
        description = description_after(children, index, level)
        if not description:
            continue
        slug = next((slug for name, slug in SPHERES if name == sphere), sphere.casefold().replace(" ", "-"))
        result[sphere].append(
            {
                "key": entry_key(slug, "Drawback", heading),
                "name": heading,
                "category": "Drawback",
                "sphere": sphere,
                "description": description,
                "prerequisites": "",
                "source_tags": source_tags(heading),
                "source_url": f"{MARTIAL_TRADITIONS_URL}#{node.get('id')}" if node.get("id") else MARTIAL_TRADITIONS_URL,
            }
        )
    return result


def build_catalog(workers: int = 6) -> dict:
    payloads: dict[str, bytes] = {}
    jobs = {name: f"{BASE_URL}/{slug}" for name, slug in SPHERES}
    jobs["__drawbacks__"] = MARTIAL_TRADITIONS_URL
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch, url): name for name, url in jobs.items()}
        for future in as_completed(futures):
            name = futures[future]
            payloads[name] = future.result()
            print(f"Downloaded {name}", flush=True)

    drawbacks = parse_drawbacks(payloads["__drawbacks__"])
    spheres = []
    for name, slug in SPHERES:
        sphere = parse_sphere(name, slug, payloads[name])
        sphere["talents"].extend(drawbacks.get(name, []))
        sphere["talents"].sort(key=lambda item: (item["category"], item["name"].casefold()))
        spheres.append(sphere)
        print(
            f"Parsed {name}: {len(sphere['talents'])} talents/drawbacks",
            flush=True,
        )
    return {
        "format": "character-sheet-martial-catalog",
        "version": 1,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [f"{BASE_URL}/spheres-of-might", MARTIAL_TRADITIONS_URL],
        "spheres": spheres,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "pf1e" / "martial_spheres.json",
    )
    parser.add_argument("--workers", type=int, default=6)
    arguments = parser.parse_args()
    catalog = build_catalog(max(1, arguments.workers))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    total = sum(len(sphere["talents"]) for sphere in catalog["spheres"])
    print(f"Wrote {len(catalog['spheres'])} spheres and {total} entries to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
