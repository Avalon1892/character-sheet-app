"""Render the shared archetype browser for theme regression review."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.ui.dialogs import ArchetypeSelectionDialog
from app.ui.theme import style_sheet


def main() -> int:
    application = QApplication.instance() or QApplication([])
    output = Path(__file__).resolve().parents[1] / "artifacts" / "archetype_picker_preview"
    output.mkdir(parents=True, exist_ok=True)
    for theme in ("classic", "light", "dark"):
        application.setStyleSheet(style_sheet(theme))
        for label, class_key in (
            ("pathfinder", "pathfinder-class:inquisitor"),
            ("spheres", "spheres-class:advisor"),
        ):
            dialog = ArchetypeSelectionDialog(class_key)
            dialog.resize(1240, 760)
            dialog.show()
            application.processEvents()
            dialog.grab().save(str(output / f"{theme}-{label}.png"))
            dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
