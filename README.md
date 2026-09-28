# Character Sheet App

A local desktop character manager for Pathfinder 1e and Spheres of Power/Might.

## Current milestone

Step 1 provides:

- a desktop application shell;
- a local character library;
- regular PF1e and Spheres character types;
- create, rename, open, and delete actions;
- automatic SQLite persistence in `%LOCALAPPDATA%\CharacterSheetApp`;
- a Refined interface with **Overview**, **Skills and Abilities**, **Abilities**,
  **Magic**, **Equipment**, **Character**, **Class Progression**, and **Crafting** pages;
- a separate level-up workspace for character management, identity, classes, editable
  base ability scores, casting setup, base spheres, and initial sphere drawbacks;
- an Overview with Abilities, Defense, Conditions, Attacks, and live resources,
  plus a dedicated skills and abilities reference page;
- **Classic Parchment** and **Dark Mode** themes;
- the **Refined Sheet**, with customizable Building Blocks and character-specific layouts;
- a responsive Refined arrangement for every character,
  with movable sections and a safe one-click
  reset that preserves all character rules data;
- reference-style ability rows, formula-based combat strips, and clean record lists
  in place of spreadsheet grids;
- all six persistent ability scores;
- automatic Pathfinder ability modifiers;
- custom typed bonuses and penalties;
- PF1e typed-bonus stacking with an auditable calculation breakdown;
- modifier enable/disable and removal controls.
- identity fields for player, race, alignment, deity, and size;
- multiclass rows with configurable BAB and save progressions;
- automatic initiative, Fortitude, Reflex, Will, AC, CMB, and CMD;
- size adjustments and derived-stat calculation breakdowns.
- current, maximum, temporary, and nonlethal hit points;
- equipment quantities, individual and total weight, value, worn slots, equipped state,
  AC bonuses, and maximum Dexterity;
- quiet one-click Wear and Remove actions that choose the natural worn, wielded, armor,
  shield, or carried state without deleting the inventory item;
- a dedicated worn-item overview, persistent CP/SP/GP/PP purse, and automatic total value;
- automatic PF1e light, medium, heavy, lifting, and dragging thresholds from Strength
  and size, with a live encumbrance state;
- normal, touch, and flat-footed AC;
- saved melee and ranged attacks with automatic attack and damage totals;
- built-in d20 and damage-dice rolling.
- the complete core PF1e skill list with ranks, filled-square class-skill markers,
  editable governing abilities, and notes, displayed without an internal scrollbar;
- automatic armor check penalties, including doubled Swim penalties;
- persistent toggleable conditions whose effects feed live calculations;
- editing for existing equipment and attack entries.
- data-driven presets for the seven core races and eleven core classes;
- core armor, shield, and common weapon presets;
- editable class rows and a one-click class level-up workflow;
- a searchable, alphabetized class picker with 44 Pathfinder and 58 Spheres classes,
  visibly separated by ruleset and class family;
- a locally bundled catalog of 1,828 Pathfinder and Spheres archetypes, grouped by
  parent class and rules family, with complete local rules text, source links, and
  shared multiple-archetype compatibility validation;
- stackable archetype selection per class row and modular Spheres capability tags that
  show magic, martial, and Prodigy sheet modules only when the build grants them;
- clickable, compatibility-validated archetype selection while initially adding a class,
  with incompatible choices disabled and grayed immediately and the same searchable
  multi-selection workflow used when editing or leveling it;
- a sortable traditional-spell browser with prominent spell names, compact level,
  school and ruleset columns, two-row filters, and full rules in a details panel;
- a modular Page 3 Spells Known table with actual spell levels, kept separate from
  the Magic Spheres table and its spell-point costs;
- archetype-aware Special Abilities that remove replaced class features and add
  the selected archetype's own abilities at their gained levels;
- a prepared-caster Page 3 block with per-class/per-level slot capacity, known-only
  preparation, explicit Custom catalog exceptions, copy expenditure, and Full Rest recovery;
- optional automatic maximum HP from class Hit Dice and Constitution;
- automatic class-skill recognition from class presets;
- portable JSON character export/import;
- safe named formulas with character, BAB, ability, class, skill/rank, feat-state,
  martial-focus, casting, and tracker references, including dependency resolution and
  visible circular-reference errors;
- dynamic attack and damage adjustment formulas that remain live as BAB, ranks, feats,
  focus, abilities, classes, or custom trackers change, with portable saved expressions;
- Excel-style formula autocomplete shared by attacks, custom trackers, and Building Block
  formulas, with live values, descriptions, filtering, and keyboard insertion;
- Excel-style lazy `IF(condition, true_value, false_value)` formulas in addition to the
  existing `value if condition else other_value` conditional syntax;
- interchangeable boolean `and` / `&` syntax plus live `sphere.<name>`,
  `drawback.<sphere>.<name>`, and item ownership/state/quantity formula references;
- persistent custom Calculated Value, Usage Counter, and Resource Pool templates with
  manual current values, formula-driven maximums, units, recovery metadata, and export support;
- independently movable custom tracker blocks whose formulas remain stable when their visual
  position, size, color, or visible label changes;
- a configurable per-character Full Rest action for Pathfinder natural healing, nonlethal and
  temporary HP, spell points, limited uses, martial focus, Prodigy sequence, and custom trackers;
- a searchable Formula Language Codex page with every supported reference, operator, function,
  safety rule, and practical pool recipe;
- a reusable Building Blocks catalogue containing every current sheet section plus permanent
  user-created templates, searchable by name, category, and description;
- a PowerPoint-style custom block designer with labels, text and number editors, safe formulas,
  checkboxes, dropdowns, allowlisted buttons, tables, grouping, anchoring, colors, borders,
  typography, and previews in Classic, Light, and Dark;
- per-character sheet tabs that can be added, renamed, reordered, duplicated, hidden, restored,
  or removed after moving their visual blocks elsewhere;
- one-click restoration of the original Default Sheet layout for an individual character,
  without removing rules data or reusable Building Blocks templates;
- nested Build Mode editing for moving, resizing, grouping, hiding, restoring, and reparenting
  cells inside sheet boxes without deleting abilities, HP, skills, inventory, features, or any
  other character rules data;
- per-character presentation undo/redo through Edit or Build Mode, including Ctrl+Z, Ctrl+Y,
  and Ctrl+Shift+Z for box, cell, tab, color, scale, block, and table-layout changes;
- Build Mode table editing with draggable/resizable headings and a heading context menu for
  adding editable custom columns or removing, renaming, and restoring individual columns;
- portable versioned block, tab, and cell layouts with embedded template snapshots, allowing
  placed custom blocks to survive catalogue deletion and character transfer safely;
- automatic startup database backups, retaining the latest ten copies.
- a locally bundled catalog of 4,669 Pathfinder and Spheres feats;
- feat search by source, type, sphere, prerequisites, description, and sheet behavior;
- automatic multi-effect rules for common save, initiative, AC, HP, skill, armor,
  shield, and weapon feats, including level/rank/BAB scaling;
- a bundled Codex of 335 Pathfinder weapon, armor, and shield special abilities,
  with exact bonus-equivalent or flat-price costs, construction rules, applicability,
  and a fast item-aware Enchant browser;
- live market prices derived from each item's base value, masterwork quality,
  enhancement bonus, bonus-equivalent properties, and flat-price properties;
- live resolved weapon properties for threat ranges, weapon-size damage, and typed
  additional damage dice, plus automatic +1/masterwork conversion when the first
  property is placed on mundane equipment;
- activatable combat-feat calculations for Combat Expertise, Deadly Aim,
  Piranha Strike, Point-Blank Shot, and Power Attack;
- required skill, saved-attack, and armor choices for feats such as Skill Focus,
  Weapon Focus, Weapon Specialization, and Armor Focus;
- repeatable-feat handling, ownership tracking, source links, and portable metadata;
- custom feats with optional typed bonuses and calculation-breakdown integration;
- a locally bundled catalog of 2,105 Pathfinder and Spheres traits: 1,975
  Pathfinder traits, 110 Spheres of Power traits, and 20 Spheres of Might traits;
- trait search by source, category, description, and sheet behavior, with source links,
  ownership tracking, choices, editing, and enable/disable controls;
- custom traits with optional typed bonuses, notes, editing, and enable/disable controls;
- an interactive Martial Focus tracker with configurable capacity and recovery notes;
- custom Spheres of Might talents grouped by sphere and category;
- a locally bundled catalog of 26 martial spheres/systems and more than 1,500 talents;
- searchable sphere, subtype, legendary-talent, prerequisite, and drawback filters;
- automatic base-sphere acquisition, catalog ownership tracking, and duplicate prevention;
- Beastmastery Animal Companion and Pet providers with correct talent costs,
  companion-level stacking, Pet-specific familiar omissions, and a dynamic
  Pet / Familiar page for both class and sphere acquisition routes;
- prepared, spontaneous, sphere, spell-like, and custom magic entries;
- a local traditional-spell catalog containing 3,028 Pathfinder and 3,409 explicitly
  labeled third-party spells, with indexed name/description search, class and level
  filters, publisher grouping, full Codex documentation, and stable source links;
- capability-driven sheet tiers: every character keeps the universal foundation,
  traditional casters gain their spellcasting tier, and Spheres casters gain only
  the relevant Spheres sections and progression, even after a saved Building Blocks
  layout is reloaded or the tabs are reordered;
- a locally bundled catalog of all 23 Spheres of Power magic spheres and more than 1,700 talents;
- searchable sphere, talent-subtype, advanced-talent, prerequisite, and drawback filters;
- 230 sphere-specific and universal drawbacks from Casting Traditions;
- automatic magic base-sphere acquisition, catalog ownership tracking, and duplicate prevention;
- per-spell use tracking with use and reset controls;
- a persistent spherecasting profile with casting ability, casting-class levels, caster
  level, MSB/MSD, concentration, save DC, and global manual adjustments, edited on Page 0;
- synchronized spell-point controls on Core and Magic pages, with optional automatic
  maximum, temporary points, spending, regaining, and daily reset actions;
- a modular spell-point contribution engine for casting levels, casting ability,
  manual adjustments, feats, and future class/tradition providers, with a visible breakdown;
- casting-tradition name, boons, drawbacks, and notes;
- a compact play-page magic summary using one global caster level and sphere DC;
- a streamlined sphere-effect table without build-only level, category, CL/DC, save,
  spell-resistance, or prerequisite columns;
- description-derived spell-point costs, including alternate costs such as `0 / 1`;
- first-acquisition base-sphere and sphere-specific drawback selection on Page 0, with
  drawbacks omitted from the play-page effect table;
- one shared effect system for feats, traits, martial talents, and magic talents;
- currently representable sheet effects for 38 feats, 433 traits, 8 martial entries,
  and 4 magic entries, including explicit toggles for conditional effects;
- conservative automation that applies exact skill, save, initiative, AC, HP, attack,
  damage, class-skill, and trained-skill effects while leaving situational rules visible
  in their descriptions instead of guessing;
- a Prodigy-only sequence tracker with opener, link, and finisher activation rules,
  readable hover descriptions, and live Inspired Sequence caster-level feedback;
- a selectable Prodigy class preset with d8 Hit Die, 3/4 BAB, class saves and skills,
  mid-caster progression, level-based spell pool and sequence capacity, Adaptation uses,
  and automatic Inspired Sequence attack, damage, and caster-level bonuses;
- all 24 basic Prodigy openers, link components, and finishers preloaded as protected
  base options, with quiet handling of unavailable sequence actions;
- custom sequence options with sphere/source, action, minimum-link, and description fields.

## Set up on Windows

1. Install a current 64-bit Python 3 from <https://www.python.org/downloads/windows/>.
   Enable **Add Python to PATH** in the installer.
2. Open PowerShell in this folder.
3. Run `Set-ExecutionPolicy -Scope Process Bypass` if local scripts are disabled.
4. Run `.\setup.ps1` once.
5. Run `.\run.ps1` whenever you want to open the app.

## Portable Windows build

Run `.\packaging\Build-Transportable.ps1 -Bootstrap -SkipInstaller` once to prepare
the dedicated `.build-venv` and build the portable ZIP. For subsequent builds, use
`.\packaging\Build-Transportable.ps1 -SkipInstaller`. Output is written to
`.artifacts\transportable` by default; `-OutputRoot` selects another build directory.

The script gives PyInstaller and the packaged smoke check a process-local PATH
containing only the build environment, its PySide6 directory, its base Python
installation (including DLLs), and Windows/system directories. This prevents
unrelated tools on the caller's PATH from supplying bundled DLLs. PyInstaller also
runs in Python isolated mode. The caller's PATH is restored even on failure; no
user or machine environment variables are changed. Manual PATH cleanup is unnecessary.

The default smoke check verifies startup and loads class/archetype definitions
through the packaged runtime loader. Do not skip it for release validation.

## Tests

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## Architecture and future extensions

See [ARCHITECTURE.md](ARCHITECTURE.md) for the page, component, feature-category,
theme, state, calculation, automation, and bundled-rules extension points. New work
should use those boundaries so saved-character compatibility and shared behavior remain
covered by the test suite.

The next milestone can expand complete casting-tradition builders, automatic feat and
talent prerequisite validation, additional conditional feat rules, item containers,
and custom skill specializations.
