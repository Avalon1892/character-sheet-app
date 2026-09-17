"""Render the shared audit status and review workflow in every built-in theme."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import CharacterRepository
from app.ui.main_window import MainWindow


def main() -> None:
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory
        )
        repository = CharacterRepository(Path(directory) / "preview.db")
        character_id = repository.create_character("Audit Preview", "Pathfinder 1e")
        repository.add_class_level(
            character_id,
            "Wizard",
            5,
            "1/2",
            "Poor",
            "Poor",
            "Good",
            preset_key="wizard",
            hit_die=6,
            hp_gained=18,
        )
        window = MainWindow(repository)
        window.resize(1440, 920)
        window.refresh_characters(character_id)
        window.show()
        application.processEvents()
        for theme in ("classic", "light", "dark"):
            window._set_theme(theme)
            application.processEvents()
            window.grab().save(str(output / f"{theme}-audit-status.png"))
            window.sheet._review_advancement()
            application.processEvents()
            dialog = window.sheet._level_up_dialog
            if dialog is not None:
                dialog.grab().save(str(output / f"{theme}-audit-dialog.png"))
                dialog.close()
                application.processEvents()
        window.close()
        repository.close()


if __name__ == "__main__":
    main()
