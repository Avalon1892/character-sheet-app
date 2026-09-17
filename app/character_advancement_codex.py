"""Source-backed Pathfinder 1e character-advancement Codex page."""

from __future__ import annotations


CHARACTER_ADVANCEMENT_SOURCE_URL = "https://www.aonprd.com/Rules.aspx?ID=85"


_ADVANCEMENT_ROWS = (
    (1, "—", "—", "—", "1st", "—"),
    (2, "3,000", "2,000", "1,300", "—", "—"),
    (3, "7,500", "5,000", "3,300", "2nd", "—"),
    (4, "14,000", "9,000", "6,000", "—", "1st"),
    (5, "23,000", "15,000", "10,000", "3rd", "—"),
    (6, "35,000", "23,000", "15,000", "—", "—"),
    (7, "53,000", "35,000", "23,000", "4th", "—"),
    (8, "77,000", "51,000", "34,000", "—", "2nd"),
    (9, "115,000", "75,000", "50,000", "5th", "—"),
    (10, "160,000", "105,000", "71,000", "—", "—"),
    (11, "235,000", "155,000", "105,000", "6th", "—"),
    (12, "330,000", "220,000", "145,000", "—", "3rd"),
    (13, "475,000", "315,000", "210,000", "7th", "—"),
    (14, "665,000", "445,000", "295,000", "—", "—"),
    (15, "955,000", "635,000", "425,000", "8th", "—"),
    (16, "1,135,000", "890,000", "600,000", "—", "4th"),
    (17, "1,900,000", "1,300,000", "850,000", "9th", "—"),
    (18, "2,700,000", "1,800,000", "1,200,000", "—", "—"),
    (19, "3,850,000", "2,550,000", "1,700,000", "10th", "—"),
    (20, "5,350,000", "3,600,000", "2,400,000", "—", "5th"),
)


def character_advancement_codex_html() -> str:
    rows = "".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>"
        for row in _ADVANCEMENT_ROWS
    )
    return (
        "<h1>Character Advancement</h1>"
        "<p><b>Source:</b> Pathfinder RPG Core Rulebook, pages 30–31.</p>"
        "<p>Characters gain levels when their accumulated experience reaches the chosen "
        "slow, medium, or fast advancement threshold. The campaign chooses the track.</p>"
        "<h2>Advancement and level-dependent bonuses</h2>"
        "<table cellspacing='6'><tr><th>Level</th><th>Slow XP</th><th>Medium XP</th>"
        "<th>Fast XP</th><th>General feat</th><th>Ability increase</th></tr>"
        f"{rows}</table>"
        "<p>The Feat and Ability columns count the total general feats and level-based "
        "ability increases earned at that character level. Class bonus feats and other "
        "class-specific awards are additional.</p>"
        "<h2>Applying a new level</h2>"
        "<ol><li>Choose the next class level and meet its prerequisites before gaining its benefits.</li>"
        "<li>Apply any level-based ability score increase.</li>"
        "<li>Add the class level's features and hit points.</li>"
        "<li>Allocate new skill ranks and feats.</li></ol>"
        "<h2>Multiclassing</h2>"
        "<p>A level in a new class grants that class's 1st-level abilities. Add its hit points, "
        "base attack bonus, saves, skills, and other class benefits to the existing character. "
        "Character-level and Hit-Dice effects use total levels; most class features use levels "
        "in the class that granted them.</p>"
        "<h2>Favored class</h2>"
        "<p>A character normally chooses one favored class at creation. Each level taken in it "
        "grants either +1 hit point or +1 skill rank for that level. Prestige classes cannot be "
        "favored classes and do not grant favored-class bonuses.</p>"
        "<h2>Prestige classes</h2>"
        "<p>All prerequisites must be met before taking the first level of a prestige class and "
        "before receiving that level's benefits.</p>"
        f"<p><a href='{CHARACTER_ADVANCEMENT_SOURCE_URL}'>Open complete rules source</a></p>"
    )


CHARACTER_ADVANCEMENT_SEARCH_TEXT = (
    "Pathfinder character advancement experience XP slow medium fast level up "
    "general feats ability score increases ASI multiclassing favored class hit point "
    "skill rank prestige class prerequisites advancement order"
)
