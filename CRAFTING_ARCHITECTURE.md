# Crafting

## Automation expansion (September 2026)

- Published market/construction costs derive the magical base price using
  `base = 2 × (market − construction)`. This excludes independent masterwork or
  costly-component value from crafting-time calculations. Nonstandard/unknown
  pricing is not guessed.
- Standard active class progressions suggest legal minimum item caster levels
  for spell-derived recipes, including sorcerer and paladin/ranger differences.
  Unusual class providers and CL modifiers remain reviewable. Spellcasting
  removed by an archetype cannot supply dormant saved spell entries.
- Exact Craft specialties are selected automatically when available; composite
  bow Strength ratings adjust price and DC. Faster mundane crafting raises both
  the normal and masterwork DC by 10.
- Quantity, whole magic-item completion days, the one-item-per-day limit, and
  adventuring's two hours of daily progress are calculated together.
- Enabled Hedge Magician or Spark of Creation applies a visible, optional 5%
  magic-creation cost reduction. Multiple reductions are explicitly flagged for
  GM stacking review rather than silently stacked.
- `tools/build_crafting_automation.py` generates 320 conservative structured
  overrides: citation-only remnants, exact alignment conditions, and unambiguous
  two-spell OR requirements. Rebuild this sidecar after importing reference data.
  Unknown prose continues to require review; the UI never parses rules text.
- `app/crafting_equipment.py` reuses the existing enchantment compatibility and
  pricing engine for a selected property plus a +1–+5 base enhancement. Its cost
  includes a purchased masterwork base; mundane base manufacture is separate.
- Selecting another recipe resets component costs and quantity, preventing
  accidental carry-over from the previous project.

All fields remain adjustable. Planning still performs no resource/inventory
writes. These are additional automation providers, not a claim that technology,
every class exception, all creature-building rules, or external prerequisites
are fully automated.

The Crafting tab is additive and available in the customizable and Refined sheets.
It does not change character rules, spend currency, or create inventory items.
Existing character layouts are retained; the new tab/block is seeded using the
existing presentation repositories.

## Extension points

- `app/crafting_rules.py`: pure standard mundane and magic crafting estimates.
  Mundane progress uses gp × 10 / (check × DC) weeks, with a separate masterwork
  component. Magic time rounds up each 1,000 gp of magical base price.
- `app/crafting_catalog.py`: cached catalog access and spell-derived recipes.
  Recipes retain existing item/spell identities. No network requests occur in UI.
- `app/services/crafting.py`: character-owned feats, archetype-resolved granted
  feats, known spells, and prerequisite status. Add specialized eligibility
  providers here rather than implementing rules in the window.
- `app/ui/crafting.py`: selection, filtering, editable planning inputs and display.
  Search is debounced 400 ms; only 500 matches are rendered at once.
- `tools/import_crafting_catalog.py`: reproducible, cached, build-time import of
  official Archives of Nethys construction records. Raw reference descriptions are
  not parsed for rules during character play.
- `data/pf1e/crafting_catalog.json`: 4,217 published item/property recipes from the
  official magic-item indexes, with construction requirements and source links.
  Existing item keys are reused where matched; this is documentation metadata,
  not an independent inventory database or a replacement for item automation.

## Deliberate safety boundaries

The planner handles standard mundane and magic-item creation. It is not a crafting
project execution system. It does not claim every specialist subsystem is automated.
Technology, creature construction/body costs, alternate skill DCs, unusual creator
requirements, and campaign exceptions require their own structured providers or
explicit review. Variable-price properties require the actual configured item's
base price, construction cost and caster level before an estimate is displayed.

`Listed requirements met` means the listed feat/spell names are on the character;
it is not a guarantee of daily spell availability, workspace access or every prose
condition. Other conditions are flagged `Needs review`. Missing spells may be
supplied externally; standard waivable spell prerequisites can add +5 DC each.
Potion, scroll, wand and staff spell prerequisites cannot use that bypass.

Spell-derived recipes retain class-list spell levels. The player must confirm a
legal creator caster level and costly components; the planner never assumes
2 × spell level − 1 is valid for every class. Potion eligibility also needs final
target confirmation. Additional component cost is entered as the total for the
item (including all charges, where applicable).

For mundane entries without a verified standard DC, the displayed starting DC is
explicitly provisional and editable. Living creatures, class-kit bundles and
non-crafting reference categories are excluded.

## Verification

`tests/test_crafting.py` covers arithmetic, catalog integrity, variable-price
safety, prerequisite filtering, character scope, no automatic selection and
no writes on closing the planner. Building-block tests include the new default
tab. `tools/check_crafting.py` renders disposable examples in all three themes.
The portable package is not part of this deployment.
