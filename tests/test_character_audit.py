from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from app.character_audit import (
    AuditFinding,
    AuditProviderRegistry,
    AuditSubject,
    build_character_audit,
)
from app.audit_resolution import DEFAULT_AUDIT_RESOLVERS, audit_context
from app.database import CharacterRepository
from app.models import CastingProfile, CharacterDetails, HitPoints
from app.transfer import export_character, import_character
from app.ui.character_audit_dialog import CharacterAuditDialog
from app.ui.character_sheet import CharacterSheetWidget


class CharacterAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.database_path = Path(self.root.name) / "audit.db"
        self.repository = CharacterRepository(self.database_path)
        self.character = self.repository.create_character("Audit Hero", "Pathfinder 1e")
        self.class_id = self.repository.add_class_level(
            self.character,
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

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_advancement_and_class_choices_share_one_report(self) -> None:
        report = build_character_audit(self.repository, self.character)

        keys = {item.key for item in report.choices}
        self.assertIn("advancement:feats:remaining", keys)
        self.assertTrue(any(key.startswith("class-choice:") for key in keys))
        self.assertGreater(len(report.choices), 0)
        self.assertEqual("choice", report.status_kind)

    def test_incomplete_racial_choices_are_a_directly_resolvable_audit_choice(self) -> None:
        trait_key = "race-alt-trait:tiefling:maw-or-claw"
        self.repository.update_character_details(CharacterDetails(
            self.character, race="Tiefling", race_key="tiefling",
            race_alternate_trait_keys=(trait_key,),
        ))
        report = build_character_audit(self.repository, self.character)
        finding = next(
            item for item in report.choices
            if item.key == "race:tiefling:missing-choice"
        )
        self.assertEqual("race-choice", finding.resolver_key)
        self.assertEqual("race", finding.subject.kind)
        self.assertFalse(finding.can_ignore)

    def test_resource_conflicts_are_not_silently_corrected(self) -> None:
        self.repository.update_hit_points(
            HitPoints(self.character, maximum=20, current=30)
        )
        profile = self.repository.get_casting_profile(self.character)
        self.repository.update_casting_profile(
            replace(
                profile,
                spell_points_maximum=3,
                spell_points_current=5,
                auto_spell_points=False,
            )
        )

        report = build_character_audit(self.repository, self.character)

        self.assertIn("resource:hp:above-maximum", {item.key for item in report.warnings})
        self.assertIn("resource:spell-points:above-maximum", {item.key for item in report.errors})
        self.assertEqual(30, self.repository.get_hit_points(self.character).current)

    def test_ignored_warning_is_persistent_and_exported(self) -> None:
        self.repository.update_hit_points(
            HitPoints(self.character, maximum=20, current=30)
        )
        key = "resource:hp:above-maximum"
        self.repository.set_audit_finding_ignored(
            self.character, key, True, "Campaign rule"
        )
        report = build_character_audit(self.repository, self.character)
        self.assertIn(key, report.ignored_keys)
        self.assertNotIn(key, {item.key for item in report.active_findings})

        export_path = Path(self.root.name) / "audit-character.json"
        export_character(self.repository, self.character, export_path)
        imported = import_character(self.repository, export_path)
        self.assertEqual(
            "Campaign rule",
            self.repository.list_audit_ignores(imported)[key],
        )

    def test_provider_registry_accepts_future_rule_module(self) -> None:
        registry = AuditProviderRegistry()
        registry.register(
            "future",
            lambda _context: (
                AuditFinding(
                    "future:choice",
                    "choice",
                    "Future system",
                    "Choose a future option",
                    action_key="future",
                ),
            ),
        )

        report = build_character_audit(
            self.repository, self.character, registry
        )

        self.assertEqual(("future:choice",), tuple(item.key for item in report.findings))

    def test_dialog_and_global_status_use_same_audit(self) -> None:
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        dialog = CharacterAuditDialog(
            self.repository, self.character, parent=sheet
        )

        self.assertEqual(sheet._audit_report.status_text, dialog._report.status_text)
        self.assertIn("remaining", sheet.audit_status_bar.label.text().casefold())
        self.assertGreater(dialog.table.rowCount(), 0)

        dialog.close()
        sheet.close()

    def test_resource_finding_exposes_identity_and_reversible_direct_fix(self) -> None:
        self.repository.update_hit_points(
            HitPoints(self.character, maximum=20, current=30)
        )
        report = build_character_audit(self.repository, self.character)
        finding = next(
            item for item in report.findings
            if item.key == "resource:hp:above-maximum"
        )
        self.assertEqual(AuditSubject("resource", key="hit-points", field="current"), finding.subject)
        self.assertEqual("resource-clamp", finding.resolver_key)
        remedies = DEFAULT_AUDIT_RESOLVERS.remedies(
            audit_context(self.repository, self.character), finding
        )
        self.assertEqual(("clamp",), tuple(item.key for item in remedies))

        outcome = DEFAULT_AUDIT_RESOLVERS.apply(
            audit_context(self.repository, self.character), finding, "clamp"
        )
        self.assertTrue(outcome.changed)
        self.assertEqual(20, self.repository.get_hit_points(self.character).current)
        self.assertIsNotNone(outcome.undo)
        outcome.undo.restore()
        self.assertEqual(30, self.repository.get_hit_points(self.character).current)

    def test_required_findings_cannot_be_ignored(self) -> None:
        report = build_character_audit(self.repository, self.character)
        self.assertTrue(report.choices)
        self.assertTrue(all(not item.can_ignore for item in report.choices))
        self.assertTrue(all(not item.can_ignore for item in report.errors))
        required = report.choices[0]
        self.repository.set_audit_finding_ignored(
            self.character, required.key, True, "Old saved dismissal"
        )
        refreshed = build_character_audit(self.repository, self.character)
        self.assertIn(required.key, {item.key for item in refreshed.active_findings})
        self.assertNotIn(required.key, {item.key for item in refreshed.ignored_findings})

    def test_dialog_confirms_applies_and_undoes_one_direct_fix(self) -> None:
        self.repository.update_hit_points(
            HitPoints(self.character, maximum=20, current=30)
        )
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        with patch.object(sheet, "refresh_all", wraps=sheet.refresh_all) as refresh_all:
            sheet._review_advancement()
            dialog = sheet._level_up_dialog
            self.assertIsNotNone(dialog)
            finding = next(
                item for item in dialog._report.findings
                if item.key == "resource:hp:above-maximum"
            )
            emissions = []
            dialog.resolution_applied.connect(lambda: emissions.append("resolved"))
            with patch.object(dialog, "refresh", wraps=dialog.refresh) as audit_refresh:
                with patch(
                    "app.ui.character_audit_dialog.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.Yes,
                ):
                    dialog._apply_remedy(finding, "clamp")
                self.assertEqual(1, audit_refresh.call_count)
            self.assertEqual(20, self.repository.get_hit_points(self.character).current)
            self.assertEqual(["resolved"], emissions)
            self.assertEqual(1, refresh_all.call_count)
            self.assertTrue(dialog.undo_button.isEnabled())

            dialog._undo_last_fix()
            self.assertEqual(30, self.repository.get_hit_points(self.character).current)
            self.assertEqual(["resolved", "resolved"], emissions)
            self.assertEqual(2, refresh_all.call_count)
        dialog.close()
        sheet.close()


if __name__ == "__main__":
    unittest.main()
