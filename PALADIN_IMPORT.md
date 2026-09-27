# Paladin catalog coverage

The shared catalogs include the 47 Pathfinder and 12 Spheres archetypes already
present, plus all 15 oaths listed by Archives of Nethys. Oaths are selectable in
the existing archetype picker; their descriptions, feature exchanges, and
stacking restrictions use the existing archetype system.

Added 26 mercies, including the Healer's Handbook options, and the three variant
Divine Bonds. Mercies use the shared class-power picker: slots at levels 3, 6,
9, 12, 15, and 18; level and prerequisite checks; archetype slot exchanges.
Existing free-text mercy notes are preserved and are not silently converted.
The base Divine Bond description now includes both weapon and mount rules.

Importing is not a claim that every narrative effect is automated. Variant
bonds are documented in the Codex but not added to the existing two-option bond
picker. Oath spell-list additions and per-use oath effects still need dedicated
automation. The coverage audit continues to flag the new oaths for review.

Sources:
- https://www.aonprd.com/Archetypes.aspx?Class=Paladin
- https://www.aonprd.com/PaladinMercies.aspx
- https://www.aonprd.com/PaladinOaths.aspx
- https://www.aonprd.com/PaladinDivineBonds.aspx
- https://www.aonprd.com/ClassDisplay.aspx?ItemName=Paladin

Refresh with `python tools/import_paladin_options.py`. The importer preserves
existing record keys and unrelated entries and updates affected manifest hashes.
