"""Class edits release their modal safely without losing saved selections."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.database import CharacterRepository
from app.ui.dialogs import ClassLevelDialog
from app.ui.refined.sheet import RefinedSheetWidget


@pytest.mark.parametrize("accepted", [True, False])
def test_replace_class_and_release_modal(accepted):
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        repository = CharacterRepository(Path(directory) / "character.db")
        sheet = RefinedSheetWidget(repository)
        try:
            character_id = repository.create_character("Replacement", "Spheres")
            class_id = repository.add_class_level(
                character_id, "Barbarian (Unchained)", 4, "Full", "Good", "Poor", "Poor",
                preset_key="barbarian-unchained", hit_die=12, hp_gained=33,
            )
            original_archetype = "spheres-archetype:pathfinder-class:barbarian-unchained:super-soldier"
            replacement = "spheres-archetype:spheres-class:reaper:machine-cultist"
            repository.set_class_archetype_keys(character_id, class_id, (original_archetype,))
            sheet.load_character(character_id)
            dialogs = []
            original_exec = ClassLevelDialog.exec

            def execute(dialog):
                dialogs.append(dialog)

                def choose():
                    dialog.preset.setCurrentIndex(dialog.preset.findData("spheres-class:reaper"))
                    dialog._selected_archetype_keys = {replacement}
                    dialog._refresh_archetypes()
                    dialog._apply_archetype_profile()
                    if accepted:
                        dialog._accept_if_valid()
                    else:
                        dialog.reject()

                QTimer.singleShot(0, choose)
                return original_exec(dialog)

            with patch.object(ClassLevelDialog, "exec", execute):
                assert sheet._edit_class_with_dialog(
                    repository.list_class_levels(character_id)[0], False
                ) is accepted
            saved = repository.list_class_levels(character_id)[0]
            assert saved.id == class_id
            assert saved.level == 4
            assert saved.preset_key == ("spheres-class:reaper" if accepted else "barbarian-unchained")
            assert repository.list_class_archetype_keys(character_id, class_id)[class_id] == (
                replacement if accepted else original_archetype,
            )
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert not isValid(dialogs[0])
            application.processEvents()
        finally:
            sheet.close()
            sheet.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            repository.close()
