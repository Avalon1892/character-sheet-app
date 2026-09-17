# Refined Sheet

## Plan and boundaries

1. Back up source and take a consistent SQLite backup before editing.
2. Register a fourth, lazily constructed presentation. Reuse existing controls,
   workflows, and calculations; replace composition and styling only.
3. Render populated Overview and Equipment prototypes, correct their sizing,
   and extend the same components to the remaining pages.
4. Isolate per-character tabs, blocks, cells, columns, layout, and history.
5. Verify representative characters, all themes, multiple widths/scales, the
   complete tests, and existing styles before normal desktop deployment.

## Extension points

| Change | Location |
| --- | --- |
| Register a sheet style | `app/ui/sheet_types.py` |
| Default pages and section placement | `app/ui/refined/pages.py`: `DEFAULT_TABS`, `PLACEMENTS` |
| Safe upgrades for existing default layouts | `app/ui/refined/layout_migrations.py` |
| Reusable responsive controls and tables | `app/ui/refined/components.py` |
| Page search, live match counts, and optional quick filters | `app/ui/refined/table_tools.py` |
| Prominent play statistics | `app/ui/refined/overview.py` |
| Clickable stat cards and movement-card interaction | `app/ui/refined/stat_cards.py` |
| Palette, typography, density, category accents | `app/ui/refined/theme.py` |
| Compact section commands | `app/ui/refined/actions.py` |
| Details, formula presentation, capability projection | `app/ui/refined/sheet.py` |
| Customization, properties, tabs, snapping, history | `app/ui/refined/customization.py` |
| Mouse-transparent alignment guides | `app/ui/refined/guides.py` |
| Companion panel presentation adapters | `app/ui/refined/companions.py` |
| Style-specific presentation persistence | `app/presentation_storage.py` |
| Gameplay calculations, resources, and rules | Existing services/rules/repositories, never Refined UI |

`RefinedSheetWidget` inherits the existing workflows and signal bindings and
recomposes their controls. Add a built-in section through the shared section and
block registry, then assign its stable key in `PLACEMENTS`. Unmapped alternate
blocks remain available in Building Blocks rather than appearing automatically.
Capability checks remain in the shared, archetype-aware providers. Dynamic
trackers, custom blocks, and companions retain their existing formula, runtime,
and progression systems.

## Persistence

`sheet_style_preferences` stores only the chosen style and presentation state.
Refined tabs, block instances, and cell overrides use `refined_`-prefixed tables.
The adapter aliases only a closed set of presentation table/index names; it does
not rewrite gameplay tables or SQL values. User-created block templates remain
shared. Customizable's original layout storage and global defaults are unchanged.

Character exports add optional `sheet_styles` and `refined_blocks` fields. Older
files remain compatible. Resetting Refined changes only its presentation. Hiding
a block never deletes its gameplay records. Refined has an independent bounded
undo/redo history, and native text-editor history retains priority.

The Skills page pairs Skills with Special Abilities in a 2:1 responsive row,
stacking below 1200 px of available content width. `ResponsiveRow.stretches`
declares column proportions; its content-height signal requests a bounded page
reflow when either child grows. Searches resolve current table ownership so
blocks moved to another page remain searchable there.

`PageSearchBar` provides a 400 ms search delay, Enter-to-apply, Escape/reset,
and live result counts. `TableFilterChoice` adds predicates over already-rendered
values; the Skills choices read effective ranks and the resolved class-skill
marker, including automated grants. They never calculate rules or change records.
Filters reset when the active character changes. Each table adapter composes
its text search, optional filters, and capability predicate, and clears hidden
selection targets. Feats/Traits default to a 2:1 row; wider category columns are
initial defaults only, so explicit Build Mode column widths remain authoritative.

Default layout changes use named, one-time presentation migrations. The Skills
upgrade moves only untouched old blocks; saved positions, sizes, hidden blocks,
and cell layouts retain their previous factory baseline. Template snapshots
record that baseline. Reset explicitly adopts the current default. Restore the
baseline before applying stored block destinations, never after, or an explicit
cross-page move can be silently discarded.

Shared helper changes are opt-in: `defaultHiddenColumns` provides style-specific
column defaults and `showFormulaIndicator` supplies the subtle formula cue.
Existing styles do not set them. The customization controller still defaults to
its original QSettings store; Refined injects a separate cache.

## Second-pass presentation refinements

- Overview groups Movement with a stack of eligible Focus/Spell Point sections.
  Each remains a separately registered, movable building block. Unavailable
  movement modes do not leave gaps, and detached movement cards are never
  reinserted by a live refresh.
- Ability modifiers use a distinct, larger accent style, separate from the
  score and the small secondary labels.
- Skills opt into `defaultColumnOrder` so the roll total precedes the skill
  name. This changes visual order only; logical columns, editor identities,
  and explicit saved user arrangements are preserved. Other styles do not
  use this property.
- `TableDisclosure` in `refined/components.py` adds a six-row reference preview
  to Special Abilities. Expansion uses the page scrollbar and is saved per
  character in `expanded_sections`. Searching reveals every match, even when
  the list was folded, and clearing the search restores that fold. Neither
  operation modifies gameplay data. Empty tables distinguish no entries from
  no matching entries.
- Refined's factory-layout restorer reapplies responsive row stretch and top
  alignment after the shared engine reinserts registered blocks. This avoids
  vertically centered short panels and inconsistent column widths after load.

`tools/render_refined_polish.py` supplements the all-page renderer with expanded
and filtered abilities plus all movement modes and their formula editors.

The defensive-stat presentation groups Armor Class (prominent total with compact
Touch/Flat-footed values), Saving Throws, and Combat Maneuvers. Eligible sphere
casters additionally see a tinted Magic Maneuvers subgroup. `MetricCard` and
`decorate_metric` provide the common surface, typography hooks, whole-card mouse
interaction, and Enter/Space access. Movement uses the decorator on its original
frames, preserving widget identities, formulas, and nested-editor bindings.
Dragging does not invoke the card action, and detail callbacks are suppressed in
Customize mode. All totals remain bound to the shared sheet calculations;
movement and magic details render existing resolved values and contribution data.
The stat-card pass passed all 13 Refined tests plus a final two-test interaction
and compatibility rerun. Overview previews cover Classic, Light, and Dark at
1600/1100 widths and 100%/125% scaling; movement-editor previews cover all modes.

Second-pass verification (2026-09-08): 39 shared layout/style/theme tests passed,
plus all 11 Refined checks. The new no-gameplay-write test was rerun successfully
after moving its baseline past the intentional page-preference save. Previews
cover all six default pages in three themes at two widths, plus expanded/search
states and movement editors at 125% display scaling. This was a focused UI
regression pass; the complete-suite figures below describe the first release.

## Feature-parity checklist

- Character: identity, race, classes/archetypes, advancement, ASIs, favored-class
  bonuses, proficiencies, traditions, and custom pools retain existing editors.
- Overview: HP overlays and Damage/Heal, initiative, abilities, defenses,
  attacks, conditions, movement, Focus, spell points, class systems, Sequence,
  and Imbues retain shared calculations and eligibility checks.
- Skills: class-skill/specialty editing, automatic ranks, allocation, formulas,
  and calculation access remain available; Special Abilities sits beside Skills.
- Abilities: martial/moldable talents, feats, traits, catalogs,
  choices, and the Martial Book remain available.
- Magic: known/prepared spells, spontaneous resources, sphere effects, duration,
  and Spell Book reuse their existing rules and resources.
- Equipment: inventory, containers, slots, enchantments, quantities, wealth,
  value, encumbrance, and Open Inventory retain their original workflows.
- Companion pages reuse animal/familiar/other companion panels and progression.
- Rest, Notes, and Audit use the application-wide implementations.
- Actions menus forward to original controls, including enabled/checkable
  states and existing destructive confirmations.
- Properties and Building Blocks modify presentation only. Columns can be
  hidden/restored or added from section Actions. Cell editing and grouping use
  the existing nested editor.

## Deliberate limits

- No new rules are implemented here; shared rules limitations remain unchanged.
- Grouping applies to editable cells. Multiple whole blocks can be aligned,
  stacked, sized, and placed together; they are not converted into a composite
  gameplay object.
- Large lists use bounded scrolling. Allocation grids retain semantic order
  rather than sorting embedded editors.
- Catalogs and complex editors retain their established interaction workflows.

## Verification

`tests/test_refined_sheet.py` covers isolated layouts and exports, reset/undo,
capability combinations, HP, formulas, details, columns, and responsive themes.
Existing spellbook, recovery, catalog, nested-cell, column, and sheet tests cover
the reused workflows. `tools/render_refined_sheet.py` renders populated pages
against a temporary database; `QT_SCALE_FACTOR` enables additional DPI checks.
Tests and renderers never use the live character database.

Verified on 2026-09-08:

- Complete suite: 722 tests across 115 isolated modules, with zero failures,
  errors, or skips. `tools/run_isolated_tests.py` gives each module a fresh Qt
  process; a monolithic run encountered native cross-module Qt teardown issues.
- Populated default pages checked in Classic, Light, and Dark at 1600×1000 and
  1100×800, at 100% and 125% display scaling. Additional previews cover prepared
  and spontaneous casters, Prodigy, animal companions, familiars, and Necros.
- All 39 original-style comparison images retained their layout and appearance;
  the only two pixel differences were the blinking text cursor.
- Visiting Customize without changing positions preserves responsive defaults.
  Embedded editors include padding in their row-height calculation, and companion
  panels align at the top rather than reserving unexplained empty space.
- Normal desktop deployment verified: all 25 delivered files matched their
  source hashes, 12 installed-copy tests passed, and populated installed previews
  were checked at both window sizes. The live database passed its integrity
  check and retained both characters. No Transportable files were updated.
