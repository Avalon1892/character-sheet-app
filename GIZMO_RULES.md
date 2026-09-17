# Gizmo reference catalog

`tools/import_gizmo_rules.py` imports nine Ultimate Engineering pages from the
Spheres wiki: Using Tinker Sphere, Tinker, Skill Rules, Mastering Gizmos, AI and
Mechanoids, Gizmo Feats, Optional and Variant Rules, Inventioneering, and Tinker
Bestiary. Includes the site's third-party additions and source notices.

The generated `data/pf1e/gizmo_rules.json` contains complete-page references plus
individually searchable sections. Formatting and tables are retained, navigation
and advertisements removed, and cross-links to imported pages open locally in
the Codex. Source links remain available. License notices are in
`data/pf1e/reference_rules_LICENSE.txt`.

`REFERENCE_FAMILIES` in `app/reference_rules.py` registers the family once for
tree navigation, index pages, and search. The shared reference renderer handles
presentation. Future gizmo editors can look up stable reference keys for help.

This is documentation, not a second talent/feat database. It does not grant
gizmos, change character resources, enable optional variants, or add Review
requirements. Existing talent/feat mechanics remain unchanged.
