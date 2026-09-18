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
        from app.class_packages.loader import (
            archetype_package, archetype_runtime_package, class_package,
            reviewed_archetype_profile, supplemental_archetype_entries,
        )

        # Exercise every definition directory through the packaged runtime loader;
        # an empty window can otherwise start successfully with missing automation.
        sapper = "pathfinder-archetype:pathfinder-class:alchemist:alchemical-sapper"
        definitions = (
            class_package("pathfinder-class:wizard"),
            class_package("prodigy"),
            archetype_package("pathfinder-archetype:pathfinder-class:alchemist:aerochemist"),
            archetype_runtime_package(sapper),
            reviewed_archetype_profile(sapper),
            supplemental_archetype_entries(),
        )
        return 0 if all(definitions) else 1
    window.show()
    return application.exec()
