# Optional crafting and Tinker traditions

- `tools/import_optional_traditions.py` imports the Spheres wiki's published sample
  traditions and their rule sections. It retains paragraph/table formatting and
  source links, strips navigation, and generates `data/pf1e/optional_traditions.json`.
- `app/optional_traditions.py` supplies cached catalog access and scoped selection
  operations. The existing `character_traditions` table and character export/import
  preserve selections and notes. A savepoint-protected migration widens the legacy
  kind constraint, preserving records and IDs; no separate database is used.
- `app/catalogs.py` exposes these entries through the existing Codex/search gateway.
- `app/ui/optional_traditions.py` contains the reusable picker and Equipment-page
  section. `optional_traditions` is registered as a movable/removable building block.
- These optional selections are not advancement requirements and have no audit
  provider. Selecting them does not award magic/martial talents, spell points, or
  bonus ranks. Crafting effects apply to particular crafted items; Tinker bonuses
  depend on the dominant tradition and gizmos created with it. This release records
  selections and GM choices, rather than applying those effects indiscriminately
  to the character. Future crafting/gizmo services should consume this data and
  model item provenance and the dominant tradition explicitly before automation.
- Sample-specific decisions and GM adjustments are editable in Choices / Notes.
  The full source rules remain available in the picker, hover description, and Codex.
- Source notices: `data/pf1e/reference_rules_LICENSE.txt`.
