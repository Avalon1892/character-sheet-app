# Reference descriptions

`data/pf1e/reference_rules.json` contains the imported Pathfinder skill families
and Prodigy Sequence actions/imbues. It is documentation, not a calculation engine.
Each record has a stable key, source URL, plain search text, and sanitized HTML.
The accompanying license file preserves the source notices.

`tools/import_reference_catalog.py` performs the explicit network import. Runtime
code never downloads or parses rules prose. Re-run with `--licenses` to update
the accompanying source notices. Check coverage before deploying a new import.

`app/reference_rules.py` owns cached access, specialization aliases, reference
formatting, and search projections. `app/ui/reference_details.py` adds the active
theme's link color. Codex and selected skill/Sequence Details use these helpers.
New reference families should follow this boundary and retain stable identities.

Skills use their saved skill keys, including Knowledge variants and additional
Craft, Perform, and Profession specialties. Selecting a skill is read-only;
editing still uses the existing skill editor. Optional unlock descriptions do not
automatically grant unlocks or change calculations.

Prodigy source entries are matched by both name and sphere. The full reference
does not change existing prerequisites, costs, or sequence execution behavior.
