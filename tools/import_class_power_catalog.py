"""Build the reusable recurring class-power catalog.

The runtime only reads the generated JSON.  Import-time adapters are kept here
so a future source refresh does not require touching the UI or rules engine.
"""
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
from bs4.element import Tag  # type: ignore  # noqa: E402


SOURCE = ROOT / ".item-source" / "packs" / "class-abilities"
OUTPUT = ROOT / "data" / "pf1e" / "class_powers.json"
KI_URL = "https://www.aonprd.com/MonkUCKiPowers.aspx"
MESMERIST_TRICKS_URL = "https://www.aonprd.com/MesmeristTricks.aspx"
MESMERIST_STARES_URL = "https://www.aonprd.com/MesmeristStares.aspx"
PHRENIC_AMPLIFICATIONS_URL = "https://www.aonprd.com/PhrenicAmplifications.aspx"


# Exact compendium tags are intentional.  Broad text matching would turn class
# progression features and archetype prose into selectable powers.
POWER_FAMILIES: tuple[dict, ...] = (
    {
        "key": "rogue_talent", "label": "Rogue Talents",
        "classes": ("Rogue", "Rogue (Unchained)"),
        "url": "https://www.aonprd.com/RogueTalents.aspx",
        "tags": {"Rogue Talent": ("Standard", 1), "Rogue Talent, Advanced": ("Advanced", 10)},
    },
    {
        "key": "slayer_talent", "label": "Slayer Talents", "classes": ("Slayer",),
        "url": "https://www.aonprd.com/SlayerTalents.aspx",
        "tags": {"Slayer Talent": ("Standard", 1), "Slayer Talent, Advanced": ("Advanced", 10)},
    },
    {
        "key": "alchemist_discovery", "label": "Alchemist Discoveries", "classes": ("Alchemist",),
        "url": "https://www.aonprd.com/AlchemistDiscoveries.aspx",
        "tags": {"Alchemist Discovery": ("General", 1)},
    },
    {
        "key": "alchemist_grand_discovery", "label": "Alchemist Grand Discoveries", "classes": ("Alchemist",),
        "url": "https://www.aonprd.com/AlchemistDiscoveries.aspx",
        "tags": {},
    },
    {
        "key": "investigator_talent", "label": "Investigator Talents", "classes": ("Investigator",),
        "url": "https://www.aonprd.com/InvestigatorTalents.aspx",
        "tags": {"Investigator Talent": ("General", 1)},
    },
    {
        "key": "witch_hex", "label": "Witch Hexes", "classes": ("Witch",),
        "url": "https://www.aonprd.com/WitchHexes.aspx",
        "tags": {"Hex": ("Hex", 1), "Major Hex": ("Major Hex", 10), "Grand Hex": ("Grand Hex", 18)},
    },
    {
        "key": "magus_arcana", "label": "Magus Arcana", "classes": ("Magus",),
        "url": "https://www.aonprd.com/MagusArcana.aspx",
        "tags": {"Magus Arcana": ("General", 1)},
    },
    {
        "key": "arcanist_exploit", "label": "Arcanist Exploits", "classes": ("Arcanist",),
        "url": "https://www.aonprd.com/ArcanistExploits.aspx",
        "tags": {
            "Arcanist Exploit": ("Exploit", 1),
            "Arcanist Exploit, Outer Rift": ("Outer Rift", 1),
            "Arcanist Exploit, Greater": ("Greater Exploit", 11),
        },
    },
    {
        "key": "ninja_trick", "label": "Ninja Tricks", "classes": ("Ninja",),
        "url": "https://www.aonprd.com/NinjaTricks.aspx",
        "tags": {"Ninja Trick": ("Trick", 1), "Ninja Trick, Master": ("Master Trick", 10)},
    },
    {
        "key": "shaman_hex", "label": "Shaman Hexes", "classes": ("Shaman",),
        "url": "https://www.aonprd.com/ShamanHexes.aspx",
        "tags": {"Hex": ("General Hex", 1), "Shaman Spirit Hex": ("Spirit Hex", 1)},
    },
    {
        "key": "occultist_focus_power", "label": "Occultist Focus Powers", "classes": ("Occultist",),
        "url": "https://www.aonprd.com/OccultistImplements.aspx",
        "tags": {"Focus Power": ("Focus Power", 1)},
    },
    {
        "key": "vigilante_talent", "label": "Vigilante Talents", "classes": ("Vigilante",),
        "url": "https://www.aonprd.com/VigilanteTalents.aspx",
        "tags": {"Vigilante Talents": ("Vigilante Talent", 1)},
    },
    {
        "key": "vigilante_social_talent", "label": "Vigilante Social Talents", "classes": ("Vigilante",),
        "url": "https://www.aonprd.com/VigilanteTalents.aspx",
        "tags": {"Vigilante Social Talent": ("Social Talent", 1)},
    },
    {
        "key": "mesmerist_trick", "label": "Mesmerist Tricks", "classes": ("Mesmerist",),
        "url": MESMERIST_TRICKS_URL, "tags": {},
    },
    {
        "key": "bold_stare", "label": "Bold Stares", "classes": ("Mesmerist",),
        "url": MESMERIST_STARES_URL, "tags": {},
    },
    {
        "key": "phrenic_amplification", "label": "Phrenic Amplifications",
        "classes": ("Psychic",), "url": PHRENIC_AMPLIFICATIONS_URL,
        "tags": {},
    },
)

FAMILY_BY_KEY = {str(spec["key"]): spec for spec in POWER_FAMILIES}

ALCHEMIST_GRAND_DISCOVERIES = {
    "Awakened Intellect",
    "Change Alignment, Greater",
    "Eternal Youth",
    "Fast Healing",
    "Philosopher's Stone",
    "Poison Touch",
    "True Mutagen",
}

OCCULTIST_CLASS_FEATURES = {
    "Focus Powers", "Implements", "Knacks (OCC)", "Mental Focus",
    "Occultist Spells", "Magic Item Skill", "Object Reading", "Shift Focus",
    "Aura Sight", "Exchange Spell (Medium)", "Magic Circles", "Outside Contact",
    "Binding Circles", "Fast Circles", "Implement Mastery", "Intense Focus (OCC)",
}
OCCULTIST_BASE_FOCUS_POWERS = {
    "Mind Barrier", "Servitor", "Sudden Insight", "Cloud Mind", "Energy Ray",
    "Minor Figment", "Necromantic Servant", "Legacy Weapon",
}
VIGILANTE_CLASS_FEATURES = {
    "Dual Identity", "Seamless Guise", "Social Talent", "Vigilante Specialization",
    "Vigilante Talent", "Unshakable", "Startling Appearance",
    "Frightening Appearance", "Stunning Appearance", "Vengeance Strike",
}
VIGILANTE_SOCIAL_TALENTS = {
    "Always Prepared", "Ancestral Enlightenment", "Any Guise", "Beast Friend",
    "Beast Speech", "Beginner's Luck", "Bellflower Innuendo", "Case the Joint",
    "Celebrity Discount", "Celebrity Perks", "Companion to the Lonely",
    "Conflicted Identity", "Discreet Inquiries", "Double Time", "Entrepreneur",
    "Everyman", "Feign Innocence", "Gossip Collector", "Great Renown",
    "Guise of Life", "Guise of Unlife", "Hidden Magic", "Immediate Change",
    "In Vogue", "Incredible Renown", "Instant Recognition", "Intrigue Feats",
    "Kalistocrat's Acumen", "Loyal Aid", "Many Guises", "Mockingbird",
    "Morphic Mask", "Notorious Fool", "Obscurity", "Owl's Sight", "Quick Change",
    "Renown", "Safe House", "Seemless Shapechanger", "Skill Familiarity",
    "Social Grace", "Songbird", "Subjective Truth", "Transformation Sequence",
    "Triumphant Return", "Well-Known Expert",
}

# Only effects whose scope is unconditional and whose sheet target is
# unambiguous are imported. Situational prose remains visible and can use the
# live activation toggle/formula namespace without guessing at the target.
REVIEWED_AUTOMATIC_MODIFIERS: dict[tuple[str, str], tuple[dict, ...]] = {
    ("alchemist_grand_discovery", "Awakened Intellect"): (
        {"target": "intelligence", "bonus_type": "untyped", "value": 2, "label": "Permanent Intelligence increase"},
    ),
    ("witch_hex", "Iceplant"): (
        {"target": "ac", "bonus_type": "natural armor", "value": 2, "label": "Iceplant natural armor"},
    ),
    ("witch_hex", "Flight Hex"): (
        {"target": "skill:swim", "bonus_type": "racial", "value": 4, "label": "Flight hex Swim bonus"},
    ),
    ("alchemist_discovery", "Webbed Extremities"): (
        {"target": "skill:swim", "bonus_type": "alchemical", "value": 4, "label": "Webbed extremities Swim bonus"},
    ),
}


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
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def minimum_level(description: str) -> int:
    levels = [
        int(value)
        for value in re.findall(
            r"(?:must|has to) (?:be (?:at least )?|have reached )(\d+)(?:st|nd|rd|th) level",
            description,
            re.I,
        )
    ]
    levels.extend(
        int(value)
        for value in re.findall(
            r"minimum (?:monk|barbarian|oracle)?\s*level(?: of)?\s*(\d+)",
            description,
            re.I,
        )
    )
    levels.extend(
        int(value)
        for value in re.findall(
            r"(?:must|has to) be (?:at least )?(?:a )?(\d+)(?:st|nd|rd|th)[- ]level",
            description,
            re.I,
        )
    )
    return max(levels, default=1)


def prerequisite_names(description: str) -> list[str]:
    result: list[str] = []
    power_type = (
        r"(?:ki|rage) power(?:s)?|rogue talents?|slayer talents?|investigator talents?|"
        r"ninja tricks?|alchemist discoveries|discover(?:y|ies)|hex(?:es)?|"
        r"magus arcana|arcana|arcanist exploits?|exploits?|focus powers?|"
        r"vigilante talents?|mesmerist tricks?|masterful tricks?|bold stares?|"
        r"phrenic amplifications?|major amplifications?"
    )
    patterns = (
        rf"(?:must|has to) (?:have|possess) (?:selected )?(?:the )?([^.;]{{1,90}}?)\s+(?:{power_type})\b",
        rf"(?:this|the) (?:talent|discovery|hex|arcana|exploit|trick|power) requires (?:having )?(?:the )?([^.;]{{1,90}}?)\s+(?:{power_type})\b",
    )
    for pattern in patterns:
        for value in re.findall(pattern, description, re.I):
            cleaned = re.sub(r"\b(?:and|or)\b", ",", value, flags=re.I)
            for part in cleaned.split(","):
                part = re.sub(r"^(?:selected|the)\s+", "", part.strip(" ."), flags=re.I)
                if (
                    part
                    and len(part.split()) <= 8
                    and not re.search(r"\b(?:one|any) of (?:the )?following\b", part, re.I)
                ):
                    result.append(part)
    return list(dict.fromkeys(result))


def repeatable_power(description: str) -> bool:
    lowered = description.casefold()
    if "cannot select" in lowered and "more than once" in lowered:
        return False
    return bool(
        re.search(
            r"\b(?:select|take|choose|selected|taken)\b[^.]{0,100}"
            r"\b(?:multiple times|more than once|\w+ times|times)\b",
            description,
            re.I,
        )
    )


def _compendium_entries() -> list[dict]:
    entries: list[dict] = []
    for path in SOURCE.rglob("*.yaml"):
        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        system = record.get("system") or {}
        tags = [str(value) for value in system.get("tags", ())]
        raw_name = str(record.get("name") or "Unnamed Power")
        name = raw_name
        description = plain((system.get("description") or {}).get("value"))
        actions = system.get("actions") or {}
        activatable = any(
            str((action.get("activation") or {}).get("type") or "").strip()
            for action in actions.values()
            if isinstance(action, dict)
        ) if isinstance(actions, dict) else False
        classes = [
            str(value)
            for value in (system.get("associations") or {}).get("classes", ())
            if str(value).strip()
        ]
        if "Vigilante" in classes:
            name = re.sub(r"\s+\((?:VIG|Talent)\)$", "", name)
            if name == "Entrepeneur":
                name = "Entrepreneur"
            elif name == "Take 'em Alive":
                name = "Take 'Em Alive"
        matched_families: list[tuple[str, str, int, tuple[str, ...], str]] = []
        lowered = {value.casefold() for value in tags}
        if "rage power" in lowered:
            categories = [value.split(",", 1)[1].strip() for value in tags if value.startswith("Rage Power,")]
            matched_families.append(("rage_power", categories[0] if categories else "General", 1, tuple(classes), "https://www.aonprd.com/BarbarianRagePowers.aspx"))
        if "revelation" in lowered and "final revelation" not in name.casefold():
            categories = [value.removesuffix(" Mystery") for value in tags if value.endswith(" Mystery")]
            matched_families.append(("revelation", categories[0] if categories else "General", 1, tuple(classes), "https://www.aonprd.com/OracleMysteries.aspx"))
        tag_set = set(tags)
        for spec in POWER_FAMILIES:
            matches = [
                (tag, category, tier_level)
                for tag, (category, tier_level) in spec["tags"].items()
                if tag in tag_set
            ]
            if not matches:
                continue
            if classes and not set(classes).intersection(spec["classes"]):
                continue
            if spec["key"] == "alchemist_discovery" and name in ALCHEMIST_GRAND_DISCOVERIES:
                continue
            _tag, category, tier_level = max(matches, key=lambda item: item[2])
            if spec["key"] == "alchemist_discovery" and "Bomb Discovery" in tag_set:
                category = "Bomb"
            matched_families.append(
                (str(spec["key"]), str(category), int(tier_level), tuple(spec["classes"]), str(spec["url"]))
            )
        if "Alchemist Discovery" in tag_set and name in ALCHEMIST_GRAND_DISCOVERIES:
            grand = FAMILY_BY_KEY["alchemist_grand_discovery"]
            matched_families.append(
                ("alchemist_grand_discovery", "Grand Discovery", 20, tuple(grand["classes"]), str(grand["url"]))
            )
        if (
            "Occultist" in classes
            and name not in OCCULTIST_CLASS_FEATURES
            and name not in OCCULTIST_BASE_FOCUS_POWERS
            and not name.endswith(" Resonant School")
            and not any(family == "occultist_focus_power" for family, *_rest in matched_families)
        ):
            spec = FAMILY_BY_KEY["occultist_focus_power"]
            matched_families.append(
                ("occultist_focus_power", "Focus Power", 1, tuple(spec["classes"]), str(spec["url"]))
            )
        if "Vigilante" in classes and name not in VIGILANTE_CLASS_FEATURES:
            family = (
                "vigilante_social_talent"
                if name in VIGILANTE_SOCIAL_TALENTS
                else "vigilante_talent"
            )
            if not any(found == family for found, *_rest in matched_families):
                spec = FAMILY_BY_KEY[family]
                matched_families.append(
                    (family, str(spec["label"]).removesuffix("s"), 1, tuple(spec["classes"]), str(spec["url"]))
                )
        for family, category, tier_level, family_classes, source_url in matched_families:
            entries.append({
                "key": f"class-power:{family}:{slug(raw_name)}",
                "family": family,
                "category": category,
                "name": name,
                "description": description,
                "classes": list(family_classes),
                "minimum_level": max(tier_level, minimum_level(description)),
                "prerequisite_names": prerequisite_names(description),
                "repeatable": repeatable_power(description),
                "activatable": activatable,
                "automatic_modifiers": list(REVIEWED_AUTOMATIC_MODIFIERS.get((family, name), ())),
                "source": ", ".join(
                    str(value.get("id")) for value in system.get("sources", ()) if value.get("id")
                ) or "Pathfinder RPG",
                "source_url": source_url,
            })
    return entries


def _ki_entries() -> list[dict]:
    request = Request(KI_URL, headers={"User-Agent": "Mozilla/5.0 Character Sheet catalog importer"})
    soup = BeautifulSoup(urlopen(request, timeout=60).read(), "html.parser")
    heading = soup.find("h1", string=lambda value: bool(value and "Ki Powers" in value))
    table = heading.find_next("table") if heading else None
    if table is None:
        raise RuntimeError("Archives of Nethys Ki Power table was not found")
    entries: list[dict] = []
    for row in table.find_all("tr"):
        text = " ".join(row.get_text(" ", strip=True).split())
        match = re.match(r"(.+?)\s+\((Ex|Su|Sp)(?:,\s*(?:Ex|Su|Sp))*\)\s+\(\s*(.+?)\s*\)\s*:\s*(.+)", text)
        if not match:
            continue
        name, ability_type, source, description = match.groups()
        entries.append(
            {
                "key": f"class-power:ki_power:{slug(name)}",
                "family": "ki_power",
                "category": ability_type,
                "name": name.strip(),
                "description": description.strip(),
                "classes": ["Monk (Unchained)"],
                "minimum_level": minimum_level(description),
                "prerequisite_names": prerequisite_names(description),
                "repeatable": repeatable_power(description),
                "activatable": True,
                "source": source.strip(),
                "source_url": KI_URL,
            }
        )
    return entries


def _mesmerist_page_entries(
    url: str,
    *,
    family: str,
    link_prefix: str,
    default_category: str,
) -> list[dict]:
    """Import AoN's authored Mesmerist option lists at build time.

    These pages are prose lists rather than catalog tables. Runtime code still
    consumes only the generated normalized JSON and never scrapes or parses
    rules text.
    """

    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 Character Sheet catalog importer"},
    )
    soup = BeautifulSoup(urlopen(request, timeout=60).read(), "html.parser")
    main = soup.find(id="main") or soup
    category = default_category
    entries: list[dict] = []
    seen: set[str] = set()
    for node in main.find_all(["h1", "a"]):
        if node.name == "h1":
            heading = plain(node.get_text(" ", strip=True))
            if heading:
                category = heading
            continue
        href = str(node.get("href") or "")
        if link_prefix.casefold() not in href.casefold():
            continue
        name = plain(node.get_text(" ", strip=True))
        option_key = slug(name)
        if not name or option_key in seen:
            continue
        seen.add(option_key)

        anchor_container = node.find_parent("i") or node
        fragments: list[str] = []
        sibling = anchor_container.next_sibling
        while sibling is not None:
            if isinstance(sibling, Tag) and sibling.name == "hr":
                break
            fragments.append(
                sibling.get_text(" ", strip=True)
                if isinstance(sibling, Tag)
                else str(sibling)
            )
            sibling = sibling.next_sibling
        body = plain(" ".join(fragments)).lstrip(" :")
        source = "Pathfinder RPG"
        source_match = re.match(r"\(([^)]+)\)\s*:\s*(.*)", body, re.S)
        if source_match:
            source, body = source_match.groups()
        is_masterful = "masterful" in category.casefold()
        entries.append(
            {
                "key": f"class-power:{family}:{option_key}",
                "family": family,
                "category": "Masterful Trick" if is_masterful else default_category,
                "name": name,
                "description": body.strip(),
                "classes": ["Mesmerist"],
                "minimum_level": max(12 if is_masterful else 1, minimum_level(body)),
                "prerequisite_names": prerequisite_names(body),
                "repeatable": repeatable_power(body),
                "activatable": family == "mesmerist_trick",
                "automatic_modifiers": [],
                "source": source.strip(),
                "source_url": url,
            }
        )
    if not entries:
        raise RuntimeError(f"Archives of Nethys options were not found at {url}")
    return entries


def _mesmerist_entries() -> list[dict]:
    return _mesmerist_page_entries(
        MESMERIST_TRICKS_URL,
        family="mesmerist_trick",
        link_prefix="MesmeristTricksDisplay.aspx",
        default_category="Mesmerist Trick",
    ) + _mesmerist_page_entries(
        MESMERIST_STARES_URL,
        family="bold_stare",
        link_prefix="MesmeristStaresDisplay.aspx",
        default_category="Bold Stare",
    )


def _phrenic_amplification_entries() -> list[dict]:
    """Import normal and major amplifications from their official detail pages."""

    headers = {
        "User-Agent": "Mozilla/5.0 Character Sheet catalog importer",
        "Referer": "https://www.aonprd.com/ClassDisplay.aspx?ItemName=Psychic",
    }
    soup = BeautifulSoup(
        urlopen(Request(PHRENIC_AMPLIFICATIONS_URL, headers=headers), timeout=60).read(),
        "html.parser",
    )
    category = "Phrenic Amplification"
    entries: list[dict] = []
    seen: set[str] = set()
    for node in (soup.find(id="main") or soup).find_all(["h1", "a"]):
        if node.name == "h1":
            heading = plain(node.get_text(" ", strip=True))
            if "major" in heading.casefold():
                category = "Major Amplification"
            elif "amplification" in heading.casefold():
                category = "Phrenic Amplification"
            continue
        href = str(node.get("href") or "")
        if "PhrenicAmplificationsDisplay.aspx" not in href:
            continue
        name = plain(node.get_text(" ", strip=True))
        key = slug(name)
        if not name or key in seen:
            continue
        seen.add(key)
        detail_url = quote(
            urljoin(PHRENIC_AMPLIFICATIONS_URL, href), safe=":/?=&%"
        )
        detail = BeautifulSoup(
            urlopen(Request(detail_url, headers=headers), timeout=60).read(),
            "html.parser",
        )
        container = next(
            (
                node
                for node in detail.find_all("span", id=re.compile("LabelName", re.I))
                if plain(node.get_text(" ", strip=True)).casefold().startswith(
                    name.casefold()
                )
            ),
            None,
        )
        body = plain(str(container)) if container is not None else ""
        body = re.sub(
            rf"^{re.escape(name)}\s*(?:\([^)]*\))?\s*(?:\([^:]+\))?\s*:\s*",
            "",
            body,
            flags=re.I,
        ).strip()
        source_node = container.find("i") if container is not None else None
        source = plain(source_node.get_text(" ", strip=True)) if source_node else "Pathfinder RPG"
        major = category == "Major Amplification"
        entries.append({
            "key": f"class-power:phrenic_amplification:{key}",
            "family": "phrenic_amplification",
            "category": category,
            "name": name,
            "description": body,
            "classes": ["Psychic"],
            "minimum_level": max(11 if major else 1, minimum_level(body)),
            "prerequisite_names": prerequisite_names(body),
            "repeatable": repeatable_power(body),
            "activatable": True,
            "automatic_modifiers": [],
            "source": source,
            "source_url": detail_url,
        })
    if not entries:
        raise RuntimeError("Archives of Nethys Phrenic Amplifications were not found")
    return entries


def _manual_entries() -> list[dict]:
    """Small source-backed repairs for options absent from the compendium."""

    return [
        {
            "key": "class-power:alchemist_grand_discovery:fast-healing",
            "family": "alchemist_grand_discovery",
            "category": "Grand Discovery",
            "name": "Fast Healing",
            "description": "The alchemist gains fast healing 5.",
            "classes": ["Alchemist"],
            "minimum_level": 20,
            "prerequisite_names": [],
            "repeatable": False,
            "activatable": False,
            "automatic_modifiers": [],
            "source": "Advanced Player's Guide",
            "source_url": "https://www.aonprd.com/AlchemistDiscoveries.aspx",
        },
        {
            "key": "class-power:vigilante_talent:swamp-concoctions",
            "family": "vigilante_talent",
            "category": "Vigilante Talent",
            "name": "Swamp Concoctions",
            "description": (
                "Twice per day, improvise an alchemical weapon using Environment Weapon. "
                "Its value is limited by Vigilante level, it becomes inert after 3 rounds, "
                "and it grants Throw Anything for that improvised weapon. Requires "
                "Environment Weapon with jungle, swamp, or water selected."
            ),
            "classes": ["Vigilante"],
            "minimum_level": 1,
            "prerequisite_names": ["Environment Weapon"],
            "repeatable": False,
            "activatable": True,
            "automatic_modifiers": [],
            "source": "People of the Wastes",
            "source_url": "https://www.aonprd.com/VigilanteTalents.aspx",
        },
    ]


def build_catalog() -> dict:
    entries = (
        _compendium_entries()
        + _ki_entries()
        + _mesmerist_entries()
        + _phrenic_amplification_entries()
        + _manual_entries()
    )
    unique = {str(entry["key"]): entry for entry in entries}
    ordered = sorted(unique.values(), key=lambda row: (row["family"], row["category"], row["name"].casefold()))
    return {
        "version": 2,
        "families": [
            {
                "key": str(spec["key"]),
                "label": str(spec["label"]),
                "source_url": str(spec["url"]),
            }
            for spec in POWER_FAMILIES
        ] + [
            {"key": "ki_power", "label": "Ki Powers", "source_url": KI_URL},
            {"key": "rage_power", "label": "Rage Powers", "source_url": "https://www.aonprd.com/BarbarianRagePowers.aspx"},
            {"key": "revelation", "label": "Oracle Revelations", "source_url": "https://www.aonprd.com/OracleMysteries.aspx"},
        ],
        "sources": [
            {"name": "Pathfinder 1e system compendium", "path": ".item-source/packs/class-abilities"},
            {"name": "Archives of Nethys", "url": KI_URL},
            {"name": "Archives of Nethys — Mesmerist Tricks", "url": MESMERIST_TRICKS_URL},
            {"name": "Archives of Nethys — Bold Stares", "url": MESMERIST_STARES_URL},
            {"name": "Archives of Nethys — Phrenic Amplifications", "url": PHRENIC_AMPLIFICATIONS_URL},
        ],
        "entries": ordered,
    }


def main() -> None:
    document = build_catalog()
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    for entry in document["entries"]:
        counts[entry["family"]] = counts.get(entry["family"], 0) + 1
    print(f"Wrote {len(document['entries'])} class powers to {OUTPUT}")
    print(", ".join(f"{key}: {value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
