from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from app.database import CharacterRepository
from app.models import SkillState
from app.presentation import feature_details_html
from app.services.character_calculations import CharacterCalculationService
from app.skill_specializations import character_skill_definitions
from app.transfer import export_character, import_character
from app.ui.floating_notes import FloatingNoteManager, FormulaNoteEditor, _formula_expression


class SkillSpecializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "skills.db")
        self.character_id = self.repository.create_character("Skilled", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_explicit_false_overrides_automatic_class_skill(self) -> None:
        self.repository.add_class_level(
            self.character_id,
            "Rogue",
            1,
            "3/4",
            "Poor",
            "Good",
            "Poor",
            "pathfinder-class:rogue",
            8,
            8,
        )
        state = self.repository.list_skill_states(self.character_id)["acrobatics"]
        automatic = CharacterCalculationService(self.repository, self.character_id)
        self.assertIn("acrobatics", automatic.resolved_class_skills())
        self.repository.update_skill_state(
            self.character_id,
            SkillState(
                state.skill_key, 1, False, 0, "", "", False
            ),
        )
        result = CharacterCalculationService(
            self.repository, self.character_id
        ).skill_result("acrobatics")
        self.assertNotIn(
            "Class skill bonus",
            {value.source for value in result.contributions if value.value},
        )

    def test_each_named_specialization_creates_one_new_empty_independent_row(self) -> None:
        self.repository.update_skill_specialization(
            self.character_id, "craft", "craft", "Alchemy"
        )
        definitions = character_skill_definitions(
            self.repository, self.character_id
        )
        craft_rows = [value for value in definitions if value.key.startswith("craft")]
        self.assertEqual(["Craft (Alchemy)", "Craft"], [value.name for value in craft_rows])
        empty_key = craft_rows[1].key
        self.repository.update_skill_state(
            self.character_id,
            SkillState(empty_key, 4, True, 2, "Weaponsmith", "intelligence", True),
        )
        self.repository.update_skill_specialization(
            self.character_id, empty_key, "craft", "Weapons"
        )
        craft_rows = [
            value for value in character_skill_definitions(
                self.repository, self.character_id
            ) if value.key.startswith("craft")
        ]
        self.assertEqual(
            ["Craft (Alchemy)", "Craft (Weapons)", "Craft"],
            [value.name for value in craft_rows],
        )
        self.assertEqual(
            4,
            self.repository.list_skill_states(self.character_id)[empty_key].ranks,
        )
        result = CharacterCalculationService(
            self.repository, self.character_id
        ).skill_result(empty_key)
        self.assertEqual(
            4,
            next(value.value for value in result.contributions if value.source == "Ranks"),
        )

    def test_specializations_and_class_override_transfer(self) -> None:
        self.repository.update_skill_specialization(
            self.character_id, "perform", "perform", "Oratory"
        )
        state = self.repository.list_skill_states(self.character_id)["perform"]
        self.repository.update_skill_state(
            self.character_id,
            SkillState(state.skill_key, 2, False, 1, "", "charisma", False),
        )
        path = Path(self.directory.name) / "skills.character.json"
        export_character(self.repository, self.character_id, path)
        imported = import_character(self.repository, path)
        self.assertEqual(
            "Oratory",
            next(
                item.specialty
                for item in self.repository.list_skill_specializations(imported)
                if item.skill_key == "perform"
            ),
        )
        self.assertFalse(
            self.repository.list_skill_states(imported)["perform"].class_skill_override
        )


class FloatingNoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "notes.db")
        self.character_id = self.repository.create_character("Writer", "Pathfinder 1e")
        self.host = QWidget(); self.host.resize(1000, 700); self.host.show()
        self.page = ["core"]
        self.manager = FloatingNoteManager(
            self.repository, self.host, lambda: self.page[0], lambda expression: eval(expression, {"__builtins__": {}}, {}),
        )
        self.manager.load_character(self.character_id)

    def tearDown(self) -> None:
        self.manager.clear(); self.host.close(); self.application.processEvents()
        self.repository.close(); self.directory.cleanup()

    def test_formula_result_persists_expression_and_updates(self) -> None:
        value = [3]
        editor = FormulaNoteEditor(lambda _expression: value[0])
        editor.insert_formula_template(); editor.insertPlainText("level+1")
        editor.finalize_formulas()
        self.assertEqual("3", editor.toPlainText())
        html = editor.toHtml()
        reloaded = FormulaNoteEditor(lambda _expression: 8)
        reloaded.setHtml(html); reloaded.refresh_formula_results()
        self.assertEqual("8", reloaded.toPlainText())
        cursor = reloaded.textCursor(); cursor.setPosition(0); cursor.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        self.assertEqual("level+1", _formula_expression(cursor.charFormat()))
        self.assertNotEqual(
            QTextCharFormat.UnderlineStyle.NoUnderline,
            cursor.charFormat().underlineStyle(),
        )
        editor.close(); reloaded.close()

    def test_formula_result_reopens_and_enter_commits_it(self) -> None:
        editor = FormulaNoteEditor(
            lambda expression: eval(expression, {"__builtins__": {}}, {})
        )
        editor.show(); editor.setFocus()
        editor.insert_formula_template(); editor.insertPlainText("2+2")
        editor.finalize_formulas()
        self.assertEqual("4", editor.toPlainText())
        span = editor._formula_span_at_position(0)
        self.assertIsNotNone(span)
        editor._open_formula_span(span)
        self.assertEqual("{2+2}", editor.toPlainText())
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.assertEqual("4", editor.toPlainText())
        editor.close()

    def test_note_autosave_does_not_commit_an_open_formula(self) -> None:
        self.manager.create_or_show(self.host.mapToGlobal(self.host.rect().center()))
        note = self.manager.notes[0]
        note.editor.insert_formula_template()
        note.editor.insertPlainText("2+2")
        self.manager.save_all()
        self.assertEqual("{2+2}", note.editor.toPlainText())
        saved = self.repository.list_sheet_notes(self.character_id)[0]
        self.assertIn("{2+2}", saved.content_html)

    def test_note_pages_preserve_page_one_and_persist_active_page(self) -> None:
        self.manager.create_or_show(self.host.mapToGlobal(self.host.rect().center()))
        note = self.manager.notes[0]
        note.editor.setPlainText("Page one")
        note._add_page()
        note.editor.setPlainText("Page two")
        self.manager.save_all()

        saved = self.repository.list_sheet_notes(self.character_id)[0]
        self.assertEqual(1, saved.current_page)
        self.assertIn("Page one", saved.content_html)
        self.manager.load_character(self.character_id)
        reloaded = self.manager.notes[0]
        self.assertEqual(2, len(reloaded.pages))
        self.assertEqual("Page two", reloaded.editor.toPlainText())
        reloaded._switch_page(0)
        self.assertEqual("Page one", reloaded.editor.toPlainText())

    def test_note_page_delete_confirms_reorders_and_is_undoable(self) -> None:
        self.manager.create_or_show(self.host.mapToGlobal(self.host.rect().center()))
        note = self.manager.notes[0]
        note.editor.setPlainText("Keep page one")
        note._add_page(); note.editor.setPlainText("Delete page two")
        note._add_page(); note.editor.setPlainText("Keep page three")
        with patch(
            "app.ui.floating_notes.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            note._delete_page(1)
        self.assertEqual(2, len(note.pages))
        self.assertEqual("Keep page three", note.editor.toPlainText())
        note._undo_page_change()
        self.assertEqual(3, len(note.pages))
        note._switch_page(1)
        self.assertEqual("Delete page two", note.editor.toPlainText())
        note._redo_page_change()
        self.assertEqual(2, len(note.pages))
        with patch(
            "app.ui.floating_notes.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            note._delete_page(1)
        self.assertEqual(1, len(note.pages))
        note._delete_page(0)
        self.assertEqual(1, len(note.pages))

    def test_note_geometry_content_visibility_and_pin_are_persistent(self) -> None:
        self.manager.create_or_show(self.host.mapToGlobal(self.host.rect().center()))
        note = self.manager.notes[0]
        note.move(120, 140); note.resize(430, 310)
        note.editor.setPlainText("Campaign reminder")
        note.pinned = True; note.page_key = "core"
        self.manager.save_all()
        saved = self.repository.list_sheet_notes(self.character_id)[0]
        self.assertEqual((120, 140, 430, 310), (saved.x, saved.y, saved.width, saved.height))
        self.assertIn("Campaign reminder", saved.content_html)
        self.page[0] = "inventory"; self.manager.page_changed()
        self.assertTrue(note.isHidden())
        self.page[0] = "core"; self.manager.page_changed()
        self.assertFalse(note.isHidden())
        note._close_preserving(); self.manager.save_all()
        self.assertFalse(self.repository.list_sheet_notes(self.character_id)[0].visible)
        self.manager.create_or_show(self.host.mapToGlobal(self.host.rect().center()))
        self.assertTrue(note.user_visible)

    def test_feature_description_comes_immediately_after_name(self) -> None:
        record = SimpleNamespace(
            name="Focused Feature", notes="The complete description.",
            source_url="", sphere="", catalog_category="Class Feature",
            enabled=True, effects=(), target="", value=0, choice="",
            activation_note="", activation="always", prerequisites="",
        )
        details = feature_details_html("Feature", record)
        self.assertLess(details.index("The complete description."), details.index("Type:"))


if __name__ == "__main__":
    unittest.main()
