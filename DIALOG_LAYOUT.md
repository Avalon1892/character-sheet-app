# Dialog presentation extension points

Dialog presentation is separate from catalog data, selection, validation, and persistence.

- `app/ui/dialog_layout.py`: starting-size profiles and content sizing. Register a dialog class name in `PROFILES` to give it a screen-bounded initial size and optional horizontal splitter proportions. The policy runs once, so subsequent user resizing is preserved. Dense equipment forms scroll independently from their description and confirmation controls.
- `app/ui/dialog_theme.py`: common dialog typography, surfaces, readable links, and theme isolation. Colors come from the shared Refined palette. The existing main-window Show-event boundary applies this to child dialogs, including nested pickers. Custom delegates are preserved.
- `app/ui/catalog_presentation.py`: specialized catalog layout: category navigation, results/details, and addition basket. Names get priority; low-priority metadata moves out of the visible columns when space is tight and remains available in details. Search, queue state, and insertion rules are not changed here.
- `app/ui/class_choice_dialog.py` and `class_power_dialog.py`: provider-driven choice layouts. These retain ordered acquisition and existing validation behavior.

Table measurement is limited to visible rows (at most 45 in the generic adapter), with delayed coalescing rather than full-catalog scans. Embedded action controls contribute to the row height. Single-line numeric/formula fields do not absorb vertical space.

Run `tools/review_dialog_layouts.py` to render representative dialogs in Classic, Modern/Light, and Dark using disposable data. Optional arguments select individual examples, e.g. `attack equipment races audit`. Preview selection is performed only by this script, never by the production presentation layer.

Regression coverage: `tests/test_dialog_layout.py`, `test_catalog_presentation.py`, `test_dialog_colors.py`, plus existing catalog, formula-field, race, class-power, and audit suites.
