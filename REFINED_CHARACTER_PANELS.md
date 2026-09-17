# Refined character panels

`app/ui/refined/character_panels.py` owns presentation composition for ability development, Martial Focus, and the embedded equipment figure. No character rules or persistence are implemented there.

- Ability Scores & Advancement reuses the original base-score and ASI controls and save handlers. Values remain separate in the database. The `base_abilities` block key remains stable; the former standalone ASI presentation is not registered in Refined. Old presentation records are retained, not deleted. Audit navigation points to the combined section.
- Martial Focus reuses its existing resource controls, setup editor, and spend/regain callbacks. The status and enabled actions reflect the live resource.
- Worn Items and Equipment Figure remain independent blocks, paired responsively by `refined/pages.py`. Narrow windows stack the pair. Both can still be moved or removed through customization.
- `app/ui/equipment_figure.py` exposes one shared content implementation as `EquipmentFigurePanel` and `EquipmentFigureDialog`. Both use `EquipmentWearService`, scoped drag payloads, and the existing sheet refresh callback. Character changes replace the embedded panel with a new character-scoped service.
- The other sheet styles retain their existing ability/ASI and focus layouts. Their separate equipment figure dialog continues to work.

Verification: `tests/test_refined_character_panels.py`, `tests/test_equipment_figure.py`, `tests/test_refined_sheet.py`, and `tools/check_refined_character_panels.py` (disposable data, three themes).
