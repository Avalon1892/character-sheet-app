"""Render every built-in sheet presentation for repeatable visual QA."""

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
from tools.create_validation_character import build_character


def _render_tabs(application, window, output: Path, prefix: str) -> None:
    widget = window.sheet_stack.currentWidget()
    tabs = getattr(widget, "page_tabs", None)
    if tabs is None:
        application.processEvents()
        window.grab().save(str(output / f"{prefix}.png"))
        return
    for index in range(tabs.count()):
        if hasattr(tabs, "isTabVisible") and not tabs.isTabVisible(index):
            continue
        tabs.setCurrentIndex(index)
        application.processEvents()
        application.processEvents()
        label = tabs.tabText(index).casefold().replace("&", "and").replace(" ", "-")
        window.grab().save(str(output / f"{prefix}-{index + 1}-{label}.png"))


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "sheet-gallery")
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory
        )
        repository = CharacterRepository(Path(directory) / "gallery.db")
        character_id = build_character(repository, "Aster, Codex Cartographer")
        window = MainWindow(repository)
        window.resize(1600, 1000)
        window.refresh_characters(character_id)
        window.show()
        application.processEvents()
        for theme in ("classic", "light", "dark"):
            window._set_theme(theme)
            for sheet_type in ("customizable", "original_spheres", "ultra"):
                window._set_sheet_type(sheet_type)
                _render_tabs(
                    application,
                    window,
                    output,
                    f"{theme}-{sheet_type}",
                )
        window.close()
        repository.close()


if __name__ == "__main__":
    main()
