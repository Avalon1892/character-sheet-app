from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.backup import create_database_backup
from app.paths import DATABASE_PATH
from app.ui.main_window import MainWindow


def run() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Character Sheet")
    application.setOrganizationName("Character Sheet App")

    try:
        create_database_backup(DATABASE_PATH)
    except OSError:
        pass
    repository = CharacterRepository(DATABASE_PATH)
    application.aboutToQuit.connect(repository.close)

    window = MainWindow(repository)
    if "--smoke-test" in sys.argv:
        # A packaged-build check must exercise migrations and construct every
        # top-level service without opening an unattended GUI forever.
        application.processEvents()
        window.close()
        repository.close()
        return 0
    window.show()
    return application.exec()
