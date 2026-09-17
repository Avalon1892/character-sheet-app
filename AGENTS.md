# Agent guidance

## Scope and approach

This established Python application uses PySide6/Qt, SQLite, and JSON reference data. It supports Pathfinder First Edition, Spheres of Power, and other Spheres systems implemented here. Never assume vanilla PF1e mechanics apply universally.

Preserve existing behavior unless a change is explicitly required. Inspect existing implementations and tests before introducing a subsystem. Prefer small, reviewable changes; avoid unrelated refactors or redesigns.

## Repository map

- `app/models.py`, `app/database.py`: records, SQLite persistence, and schema compatibility.
- `app/services/character_state.py`: collected character state and effective selections.
- `app/services/character_calculations.py`: derived statistics and automatic effects.
- `app/services/sheet_presentation.py`: shared sheet projections.
- `app/rules.py` and focused rules modules under `app/`: shared calculations and dedicated validators.
- `app/class_packages/definitions/`: structured class/archetype automation.
- `data/pf1e/`: bundled reference catalogs; preserve identifiers and provenance.
- `app/ui/`: Qt editors and sheet presentations.
- `app/building_blocks/`: customizable presentation bindings and actions.
- `app/transfer.py`: character import/export and identifier remapping.
- `tests/`, `tools/`, `packaging/`: regression coverage, tooling, and distribution builds.

## Existing architecture to preserve

- Substantial shared rules infrastructure already exists. Reuse calculation providers rather than duplicating mechanics in widgets or bindings.
- Reuse the centralized scalar modifier system; preserve contribution source attribution and explanations where possible.
- Traditional spellcasting and spherecasting have distinct semantics. Do not merge them or other progression helpers merely because their implementations look similar.
- Use the existing structured class/archetype packages. Do not replace dedicated prerequisite, resource, or choice validators with a universal rules engine without strong justification.
- Temporary/flexible Spheres selections can affect calculations without replacing permanent choices. Resources can have different spending, maximum, and recovery contracts.
- Keep UI customization separate from underlying character mechanics. Hiding or rearranging presentation must not alter character choices or rules state.

## State and calculation changes

Distinguish persistent play state, stored inputs, calculated values, and cached projections. Manual overrides and stored derived values can intentionally support compatibility or user control; do not normalize them away.

Use repository methods for persistence. Do not silently change schemas, persisted semantics, ownership checks, import/export relationships, or compatibility behavior.

Some refresh operations intentionally synchronize persistent rules state; they are not purely presentation. Inspect those side effects before moving or bypassing refresh logic. Treat calculation snapshots as short-lived and refresh them after mutations.

Be particularly careful with effective class/archetype resolution, HP, casting profiles, caster level, spell points, sphere DCs, automatic modifiers, formula evaluation, temporary talents, and refresh-time synchronization. Distinguish stored literals from resolved/effective values and preserve formula recursion safeguards. Check agreement among affected sheets, bindings, formulas, and recovery paths.

## Rules changes and validation

Treat tabletop behavior changes separately from ordinary programming changes. Distinguish current code behavior, test-established intent, bundled rule/catalog data, and externally verified tabletop rules. Do not assume one Spheres edition or interpretation governs all content. If correctness is uncertain, report "Needs rules verification" rather than inventing behavior.

When changing game behavior, add or update focused regression tests for the intended rule and relevant PF1e/Spheres interactions. Run relevant tests after code changes. Do not casually modify imported catalogs, class definitions, or test expectations to make a failure disappear.

The audited baseline `d7be17d03c65042c3fd67a6a4a4611bcf7b58bbc` had 832 passing and 8 failing tests. Do not assume the full suite is green; distinguish pre-existing failures from regressions and report them separately.

Run commands from the repository root using the project's Python environment:

- Install runtime dependencies: `python -m pip install -r requirements.txt`
- Run the application: `python main.py`
- Install pytest if needed (the isolated runner requires it): `python -m pip install pytest`
- Run focused tests: `python -m pytest tests/test_<area>.py -q`
- Run the isolated suite: `python tools/run_isolated_tests.py --workers 2 --output artifacts/validation`
- Build the Windows portable distribution: `.\packaging\Build-Transportable.ps1 -SkipInstaller` (add `-Bootstrap` to prepare the build environment).
- No dedicated type-checking command is currently configured.

For packaging changes, verify catalogs and class-package definitions are included and exercise relevant packaged behavior; a successful window-startup smoke test alone is insufficient.
