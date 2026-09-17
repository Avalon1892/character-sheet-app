from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.audit_resolution import (
    AuditRemedy,
    AuditResolutionOutcome,
    AuditResolutionPreview,
    AuditResolutionRegistry,
    DEFAULT_AUDIT_RESOLVERS,
    audit_context,
)
from app.character_audit import (
    AuditContext,
    AuditFinding,
    AuditSubject,
    build_character_audit,
)
from app.class_power_rules import decode_class_power_keys, resolve_class_power_sets
from app.database import CharacterRepository
from app.models import (
    CastingProfile,
    ClassFeatureSelection,
    HitPoints,
    MartialFocus,
    ProdigySequence,
)
from app.traditional_spellcasting import spontaneous_caster_capacities
from app.ui.character_audit_dialog import AuditAction, CharacterAuditDialog
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.theme import THEME_LABELS, style_sheet


class _FutureResolver:
    def remedies(self, _context, _finding):
        return (AuditRemedy("repair", "Repair", "Repair the future record.", "automatic"),)

    def preview(self, _context, finding, _remedy_key=""):
        return AuditResolutionPreview(finding.title, "old", "new", ("One record changes.",))

    def apply(self, _context, _finding, remedy_key):
        return AuditResolutionOutcome(remedy_key == "repair")


class CharacterAuditResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "audit-resolution.db")
        self.character = self.repository.create_character("Resolver", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def add_class(self, name: str, key: str, level: int) -> int:
        return self.repository.add_class_level(
            self.character, name, level, "Full", "Good", "Good", "Good", key, 10, 50
        )

    def test_resolution_registry_is_an_independent_extension_point(self) -> None:
        registry = AuditResolutionRegistry()
        registry.register("future", _FutureResolver())
        finding = AuditFinding(
            "future:record:1",
            "warning",
            "Future",
            "Future record",
            subject=AuditSubject("future", record_id=1),
            resolver_key="future",
        )
        context = audit_context(self.repository, self.character)

        self.assertEqual(("future",), registry.keys())
        self.assertEqual(("repair",), tuple(item.key for item in registry.remedies(context, finding)))
        self.assertEqual("old", registry.preview(context, finding, "repair").current)
        self.assertTrue(registry.apply(context, finding, "repair").changed)

    def test_every_emitted_finding_has_a_registered_resolver(self) -> None:
        self.add_class("Wizard", "pathfinder-class:wizard", 5)
        report = build_character_audit(self.repository, self.character)
        self.assertTrue(report.findings)
        self.assertEqual(
            (),
            tuple(
                finding.key for finding in report.findings
                if not finding.resolver_key
                or DEFAULT_AUDIT_RESOLVERS.resolver(finding.resolver_key) is None
            ),
        )

    def test_all_current_finding_families_have_resolution_handlers(self) -> None:
        self.assertTrue({
            "advancement-choice",
            "advancement-overage",
            "favored-class",
            "class-choice",
            "archetype-choice",
            "class-power",
            "invalid-class-power",
            "magic-sphere-choice",
            "martial-sphere-choice",
            "invalid-selection",
            "feat-choice",
            "prepared-overage",
            "spontaneous-overage",
            "resource-clamp",
            "formula",
        }.issubset(set(DEFAULT_AUDIT_RESOLVERS.keys())))

    def test_resource_preview_apply_and_undo_identify_exact_values(self) -> None:
        self.repository.update_hit_points(HitPoints(self.character, maximum=18, current=31))
        finding = next(
            item for item in build_character_audit(self.repository, self.character).findings
            if item.key == "resource:hp:above-maximum"
        )
        context = audit_context(self.repository, self.character)

        preview = DEFAULT_AUDIT_RESOLVERS.preview(context, finding, "clamp")
        self.assertEqual("31", preview.current)
        self.assertEqual("18", preview.proposed)
        outcome = DEFAULT_AUDIT_RESOLVERS.apply(context, finding, "clamp")
        self.assertTrue(outcome.changed)
        self.assertEqual(18, self.repository.get_hit_points(self.character).current)
        outcome.undo.restore()
        self.assertEqual(31, self.repository.get_hit_points(self.character).current)

    def test_every_resource_clamp_family_changes_only_its_current_value(self) -> None:
        self.repository.update_casting_profile(
            CastingProfile(
                self.character,
                spell_points_maximum=3,
                spell_points_current=8,
                auto_spell_points=False,
            )
        )
        spell_finding = next(
            item
            for item in build_character_audit(
                self.repository, self.character
            ).findings
            if item.resolver_key == "resource-clamp"
            and item.subject.key == "spell-points"
        )
        spell_outcome = DEFAULT_AUDIT_RESOLVERS.apply(
            audit_context(self.repository, self.character),
            spell_finding,
            "clamp",
        )
        self.assertEqual(
            3,
            self.repository.get_casting_profile(
                self.character
            ).spell_points_current,
        )
        spell_outcome.undo.restore()
        self.assertEqual(
            8,
            self.repository.get_casting_profile(
                self.character
            ).spell_points_current,
        )

        for subject_key, before in (
            ("martial-focus", MartialFocus(1, 4, 1)),
            ("prodigy-sequence", ProdigySequence(1, True, 9, 4, "life")),
        ):
            with self.subTest(resource=subject_key):
                fake_repository = MagicMock()
                getter_name = {
                    "martial-focus": "get_martial_focus",
                    "prodigy-sequence": "get_prodigy_sequence",
                }[subject_key]
                getattr(fake_repository, getter_name).return_value = before
                context = AuditContext(fake_repository, 1, MagicMock())
                finding = AuditFinding(
                    f"resource:{subject_key}:above-maximum",
                    "error",
                    "Resources",
                    f"Invalid {subject_key}",
                    subject=AuditSubject(
                        "resource", key=subject_key, field="current"
                    ),
                    resolver_key="resource-clamp",
                )
                outcome = DEFAULT_AUDIT_RESOLVERS.apply(
                    context, finding, "clamp"
                )
                self.assertTrue(outcome.changed)
                if subject_key == "martial-focus":
                    fake_repository.update_martial_focus.assert_called_once_with(
                        MartialFocus(1, 1, 1)
                    )
                else:
                    fake_repository.update_prodigy_sequence.assert_called_once_with(
                        ProdigySequence(1, True, 4, 4, "life")
                    )
                outcome.undo.restore()
                if subject_key == "martial-focus":
                    self.assertEqual(
                        before,
                        fake_repository.update_martial_focus.call_args_list[-1].args[0],
                    )
                else:
                    self.assertEqual(
                        before,
                        fake_repository.update_prodigy_sequence.call_args_list[-1].args[0],
                    )

    def test_spontaneous_overage_never_reduces_below_the_legal_limit_and_undoes(self) -> None:
        class_id = self.repository.add_class_level(
            self.character,
            "Sorcerer",
            4,
            "1/2",
            "Poor",
            "Poor",
            "Good",
            "pathfinder-class:sorcerer",
            6,
            20,
        )
        capacity = next(
            item for item in spontaneous_caster_capacities(self.repository, self.character)
            if item.class_level_id == class_id
        )
        allowed = capacity.total_slots[1]
        self.repository.set_spontaneous_slot_uses(self.character, class_id, 1, allowed + 3)
        finding = next(
            item for item in build_character_audit(self.repository, self.character).errors
            if item.resolver_key == "spontaneous-overage" and item.subject.level == 1
        )

        outcome = DEFAULT_AUDIT_RESOLVERS.apply(
            audit_context(self.repository, self.character), finding, "clamp"
        )
        self.assertTrue(outcome.changed)
        current = next(
            item for item in self.repository.list_spontaneous_slot_uses(self.character)
            if item.class_level_id == class_id and item.spell_level == 1
        )
        self.assertEqual(allowed, current.used_count)
        outcome.undo.restore()
        restored = next(
            item for item in self.repository.list_spontaneous_slot_uses(self.character)
            if item.class_level_id == class_id and item.spell_level == 1
        )
        self.assertEqual(allowed + 3, restored.used_count)

    def test_invalid_class_power_is_named_and_remove_restores_only_its_selection(self) -> None:
        class_id = self.add_class("Barbarian", "pathfinder-class:barbarian", 2)
        power_set = next(
            item for item in resolve_class_power_sets(self.repository, self.character)
            if item.class_level_id == class_id
        )
        invalid_key = "missing-rage-power"
        before = ClassFeatureSelection(
            self.character,
            class_id,
            power_set.feature_key,
            "Class power",
            f'["{invalid_key}"]',
            "Missing Rage Power",
            "No longer available.",
        )
        self.repository.save_class_feature_selection(before)
        finding = next(
            item for item in build_character_audit(self.repository, self.character).errors
            if item.resolver_key == "invalid-class-power"
        )
        self.assertEqual(invalid_key, finding.subject.field)
        self.assertEqual(0, finding.subject.level)

        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        outcome = sheet._resolve_audit_invalid_class_power(finding, "remove")
        self.assertTrue(outcome.changed)
        saved = next(
            item for item in self.repository.list_class_feature_selections(self.character)
            if item.class_level_id == class_id and item.feature_key == power_set.feature_key
        )
        self.assertEqual((), decode_class_power_keys(saved.option_key))
        outcome.undo.restore()
        restored = next(
            item for item in self.repository.list_class_feature_selections(self.character)
            if item.class_level_id == class_id and item.feature_key == power_set.feature_key
        )
        self.assertEqual((invalid_key,), decode_class_power_keys(restored.option_key))
        sheet.close()

    def test_cancelled_interactive_resolution_writes_nothing_and_creates_no_undo(self) -> None:
        self.repository.set_numeric_formula(self.character, "attack", 41, "damage", "=1/0")
        finding = next(
            item for item in build_character_audit(self.repository, self.character).warnings
            if item.resolver_key == "formula"
        )
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        before = dict(self.repository.numeric_formulas(self.character))
        with patch("app.ui.character_sheet.QDialog.exec", return_value=QDialog.DialogCode.Rejected):
            outcome = sheet._resolve_audit_formula(finding.subject)
        self.assertFalse(outcome.changed)
        self.assertIsNone(outcome.undo)
        self.assertEqual(before, self.repository.numeric_formulas(self.character))
        sheet.close()

    def test_exact_structured_subject_is_passed_to_the_interactive_adapter(self) -> None:
        finding = AuditFinding(
            "choice:class:17:mystery",
            "choice",
            "Class choices",
            "Choose Mystery",
            subject=AuditSubject("class-choice", class_level_id=17, key="oracle-mystery"),
            resolver_key="class-choice",
        )
        received = []
        dialog = CharacterAuditDialog(
            self.repository,
            self.character,
            actions={
                "class-choice": AuditAction(
                    "Choose",
                    lambda selected, remedy: received.append((selected.subject, remedy)),
                )
            },
        )
        dialog._run_interactive(finding, "edit")
        self.assertEqual([(finding.subject, "edit")], received)
        self.assertFalse(dialog.undo_button.isEnabled())
        dialog.close()

    def test_completed_fix_disappears_and_next_priority_finding_is_selected(self) -> None:
        self.repository.update_hit_points(HitPoints(self.character, maximum=10, current=14))
        finding = next(
            item for item in build_character_audit(self.repository, self.character).findings
            if item.key == "resource:hp:above-maximum"
        )
        dialog = CharacterAuditDialog(self.repository, self.character)
        with patch(
            "app.ui.character_audit_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog._apply_remedy(finding, "clamp")
        self.assertNotIn(finding.key, {item.key for item in dialog._report.findings})
        self.assertEqual(0, dialog.table.currentRow() if dialog.table.rowCount() else 0)
        self.assertTrue(dialog.undo_button.isEnabled())
        dialog.close()

    def test_required_findings_cannot_be_constructed_as_ignorable(self) -> None:
        with self.assertRaises(ValueError):
            AuditFinding(
                "required:choice",
                "choice",
                "Choices",
                "Required choice",
                can_ignore=True,
            )

    def test_invalid_catalog_selection_exposes_all_safe_remedies(self) -> None:
        finding = AuditFinding(
            "invalid:feat:41",
            "error",
            "Prerequisites and restrictions",
            "Invalid feat",
            subject=AuditSubject("feat", record_id=41, key="feat:invalid"),
            resolver_key="invalid-selection",
        )
        remedies = DEFAULT_AUDIT_RESOLVERS.remedies(
            audit_context(self.repository, self.character), finding
        )
        self.assertEqual(
            ("deactivate", "replace", "remove"),
            tuple(remedy.key for remedy in remedies),
        )

    def test_closing_audit_discards_session_undo(self) -> None:
        self.repository.update_hit_points(
            HitPoints(self.character, maximum=10, current=14)
        )
        finding = next(
            item
            for item in build_character_audit(
                self.repository, self.character
            ).findings
            if item.key == "resource:hp:above-maximum"
        )
        dialog = CharacterAuditDialog(self.repository, self.character)
        with patch(
            "app.ui.character_audit_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog._apply_remedy(finding, "clamp")
        self.assertIsNotNone(dialog._last_undo)
        dialog.reject()
        self.assertIsNone(dialog._last_undo)
        self.assertFalse(dialog.undo_button.isEnabled())
        with self.assertRaises(ValueError):
            AuditFinding(
                "required:error",
                "error",
                "Rules",
                "Rules conflict",
                can_ignore=True,
            )

    def test_resolution_panel_is_usable_in_every_theme(self) -> None:
        self.repository.update_hit_points(HitPoints(self.character, maximum=10, current=14))
        for theme in THEME_LABELS:
            with self.subTest(theme=theme):
                dialog = CharacterAuditDialog(self.repository, self.character)
                dialog.setStyleSheet(style_sheet(theme))
                dialog.show()
                self.application.processEvents()
                self.assertTrue(dialog.resolution_panel.isVisible())
                self.assertGreaterEqual(dialog.width(), 1000)
                self.assertIn("Affected:", dialog.resolution_text.text())
                dialog.close()


if __name__ == "__main__":
    unittest.main()
