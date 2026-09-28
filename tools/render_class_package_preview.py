"""Render shared class choice UI against temporary characters, in all themes."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.class_choice_rules import resolve_class_choice_slots
from app.content import class_entry
from app.database import CharacterRepository
from app.ui.class_choice_dialog import ClassChoiceDialog
from app.ui.main_window import MainWindow


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    for filename in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename))
    application.setFont(QFont("Segoe UI", 10))
    with tempfile.TemporaryDirectory() as temporary:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, temporary)
        repository = CharacterRepository(Path(temporary) / "preview.db")
        window = MainWindow(repository)
        for class_key in sys.argv[2:]:
            entry = class_entry(class_key)
            character = repository.create_character(entry["name"], "Spheres")
            repository.add_class_level(character, entry["name"], 20, entry["bab"],
                entry["fort"], entry["reflex"], entry["will"], entry["key"],
                entry["hit_die"], 120)
            slots = resolve_class_choice_slots(repository, character)
            slot = max(slots, key=lambda value: sum(len(o.description) for o in value.options))
            for theme in ("classic", "dark"):
                window._set_theme(theme)
                dialog = ClassChoiceDialog(slot, window)
                dialog.show()
                application.processEvents()
                dialog.grab().save(str(output / (class_key.split(":")[-1] + "-" + theme + ".png")))
                dialog.close()
        window.close()
        repository.close()


if __name__ == "__main__":
    main()
