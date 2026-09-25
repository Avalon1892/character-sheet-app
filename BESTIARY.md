# Bestiary and encounters

Open **Bestiary → Bestiary & Encounters**. Single-click previews; double-click
or Enter adds the selected quantity. Filters combine, and encounter selections
survive searches. Save/Save copy persist a draft in the application's database;
closing an unsaved draft offers Save, Discard, or Cancel. No character is needed.

## Coverage and sources

`data/pf1e/bestiary.json` imports the Archives of Nethys PF1 **Monster (All),
Unique, NPC (All), and Mythic (All)** indexes. Its header records index sizes,
unique source-page count, successful imports, and any failed URLs. Completeness
means those indexes, not every third-party publication or unpublished NPC.
Source URLs and publication/page credits are retained per creature. The catalog
contains game statistics and ability mechanics, not artwork or narrative lore.
The accompanying `bestiary_LICENSE.txt` retains the OGL and source notices.

Legacy 3.5 blocks with Grapple rather than CMB/CMD are marked for review and can
be filtered out. Missing XP remains explicitly unknown; the app does not invent
an XP award or convert these entries. Location searches the published environment,
not an inferred campaign location. Melee/Ranged/Caster are non-exclusive capabilities;
Caster includes spell-like abilities, extracts, and psychic magic.

## Extension points

- **Import/data:** `tools/import_bestiary.py`; cached, resumable downloads with a
  global request interval, stable source-URL keys, and sanitized mechanical HTML.
  Run `.venv/Scripts/python.exe tools/import_bestiary.py` from the repository root.
  `--limit` is for local samples only; never claim a sample is a complete release.
- **Catalog access:** `RulesCatalog.bestiary_entries()` / `bestiary_entry()`.
  An older installed catalog release falls back to the bundled Bestiary.
- **Filters and shared details:** `app/bestiary.py`, used by both the dialog and
  Codex. New filters belong here; no runtime scraping or description-based rules.
- **Encounter math and persistence:** `app/encounters.py`. `encounters` is an
  additive table on the existing connection, separate from character mechanics.
  Saved encounters hold stable catalog keys/quantities, party levels, and notes,
  not copies of stat blocks. Missing catalog entries remain visible after load.
- **UI:** `app/ui/bestiary_dialog.py`; existing debounce, catalog search, dialog
  theme, and layout helpers are reused. Results are capped at 300 rendered rows.
- **Codex:** `app/codex_index.py` adds search records; the existing Codex routes
  `codex:bestiary:<key>` links to the same creature details.

Encounter budgeting follows the Core Rulebook encounter-design table: sum
published XP, round APL to nearest (half up), adjust for party size, and compare
with the selected difficulty budget. Between-threshold totals are labeled as a
range. The supplied XP reference spans CR 1/8–25; higher totals/targets are
explicitly outside that table. These guidelines are not a guarantee of balance.

Focused checks: `.venv/Scripts/python.exe -m pytest tests/test_bestiary.py -q`.
