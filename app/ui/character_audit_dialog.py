"""Character audit and sequential unresolved-choice presentation."""
from __future__ import annotations

from dataclasses import dataclass
import html
import inspect
from typing import Callable, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.character_audit import AuditFinding, build_character_audit
from app.audit_resolution import (
    AuditResolutionOutcome,
    AuditUndoToken,
    DEFAULT_AUDIT_RESOLVERS,
    audit_context,
)


@dataclass(frozen=True, slots=True)
class AuditAction:
    label: str
    callback: Callable[..., object]
    close_after: bool = False


class CharacterAuditStatusBar(QFrame):
    """Small global status indicator; rules remain in ``character_audit``."""

    review_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("auditStatusBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        self.label = QLabel("Character audit not yet available")
        self.label.setObjectName("auditStatusText")
        self.button = QPushButton("Review")
        self.button.setObjectName("auditStatusButton")
        self.button.clicked.connect(self.review_requested)
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.button)

    def set_report(self, report) -> None:
        self.label.setText(report.status_text)
        self.setProperty("auditState", report.status_kind)
        self.setToolTip(
            f"{len(report.errors)} conflict(s), {len(report.choices)} choice(s), "
            f"{len(report.warnings)} warning(s), {len(report.ignored_findings)} ignored."
        )
        self.style().unpolish(self)
        self.style().polish(self)


class CharacterAuditDialog(QDialog):
    """Render audit state and route fixes into existing focused editors."""

    audit_changed = Signal()
    resolution_applied = Signal()

    FILTERS = (
        ("All active", "active"),
        ("Choices remaining", "choice"),
        ("Rules conflicts", "error"),
        ("Warnings", "warning"),
        ("Ignored", "ignored"),
    )

    def __init__(
        self,
        repository,
        character_id: int,
        *,
        summary: str = "",
        gained_features: tuple[str, ...] = (),
        actions: Mapping[str, AuditAction] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id = character_id
        self.actions = dict(actions or {})
        self._report = None
        self._row_findings: dict[int, AuditFinding] = {}
        self._last_undo: AuditUndoToken | None = None
        self.setWindowTitle("Character Audit & Choices Remaining")
        self.resize(1120, 760)
        layout = QVBoxLayout(self)

        title = QLabel("CHARACTER AUDIT & CHOICES REMAINING")
        title.setObjectName("heroTitle")
        layout.addWidget(title)
        self.summary = QLabel(summary)
        self.summary.setWordWrap(True)
        self.summary.setObjectName("pageSubtitle")
        self.summary.setVisible(bool(summary))
        layout.addWidget(self.summary)
        self.gained = QLabel(
            "New class features: " + ", ".join(gained_features)
            if gained_features else ""
        )
        self.gained.setWordWrap(True)
        self.gained.setObjectName("mutedText")
        self.gained.setVisible(bool(gained_features))
        layout.addWidget(self.gained)

        toolbar = QHBoxLayout()
        self.status = QLabel()
        self.status.setObjectName("formulaText")
        self.filter = QComboBox()
        for label, key in self.FILTERS:
            self.filter.addItem(label, key)
        self.filter.currentIndexChanged.connect(self._populate)
        self.next_choice = QPushButton("Resolve next choice")
        self.next_choice.setObjectName("primaryButton")
        self.next_choice.clicked.connect(self._resolve_next_choice)
        toolbar.addWidget(self.status, 1)
        toolbar.addWidget(QLabel("Show"))
        toolbar.addWidget(self.filter)
        toolbar.addWidget(self.next_choice)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("recordTable")
        self.table.setHorizontalHeaderLabels(
            ("Status", "Category", "Finding", "Summary", "Actions")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.table.currentCellChanged.connect(self._show_selected_details)
        layout.addWidget(self.table, 1)

        self.details = QTextBrowser()
        self.details.setObjectName("detailsPanel")
        self.details.setMaximumHeight(170)
        self.details.setHtml("<i>Select a finding to see its full rules context.</i>")
        layout.addWidget(self.details)

        self.resolution_panel = QFrame()
        self.resolution_panel.setObjectName("auditResolutionPanel")
        resolution_layout = QVBoxLayout(self.resolution_panel)
        resolution_layout.setContentsMargins(10, 8, 10, 8)
        self.resolution_title = QLabel("RESOLVE THIS ISSUE")
        self.resolution_title.setObjectName("subsectionTitle")
        self.resolution_text = QLabel()
        self.resolution_text.setWordWrap(True)
        self.resolution_text.setObjectName("mutedText")
        self.remedy_buttons = QHBoxLayout()
        resolution_layout.addWidget(self.resolution_title)
        resolution_layout.addWidget(self.resolution_text)
        resolution_layout.addLayout(self.remedy_buttons)
        layout.addWidget(self.resolution_panel)

        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        refresh = QPushButton("Refresh audit")
        refresh.clicked.connect(self.refresh)
        controls.addButton(refresh, QDialogButtonBox.ButtonRole.ActionRole)
        self.undo_button = QPushButton("Undo last audit fix")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self._undo_last_fix)
        controls.addButton(self.undo_button, QDialogButtonBox.ButtonRole.ActionRole)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        self.refresh()

    def refresh(self) -> None:
        self._report = build_character_audit(self.repository, self.character_id)
        report = self._report
        self.status.setText(
            f"{report.status_text} · {len(report.warnings)} warning(s) · "
            f"{len(report.ignored_findings)} ignored"
        )
        self.next_choice.setEnabled(bool(report.choices))
        self.next_choice.setText(
            f"Resolve next choice ({len(report.choices)})"
            if report.choices else "No choices remaining"
        )
        self._populate()

    def _visible_findings(self) -> tuple[AuditFinding, ...]:
        if self._report is None:
            return ()
        selected = str(self.filter.currentData() or "active")
        if selected == "ignored":
            return self._report.ignored_findings
        if selected == "active":
            return self._report.active_findings
        return tuple(
            item for item in self._report.active_findings
            if item.severity == selected
        )

    def _populate(self, *_args) -> None:
        findings = self._visible_findings()
        self.table.setRowCount(0)
        self._row_findings.clear()
        for finding in findings:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_findings[row] = finding
            labels = {
                "error": "Conflict",
                "warning": "Warning",
                "choice": "Choice",
                "review": "Review",
            }
            values = (
                labels[finding.severity],
                finding.category,
                finding.title,
                finding.summary,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(finding.details or finding.summary)
                item.setData(Qt.ItemDataRole.UserRole, finding.key)
                if column == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(2, 1, 2, 1)
            action_layout.setSpacing(4)
            configured = self._configured_action(finding)
            remedies = self._remedies(finding)
            if configured is not None or remedies:
                resolve = QPushButton(finding.action_label or (configured.label if configured else "Resolve"))
                resolve.clicked.connect(lambda _checked=False, selected=finding: self._select_for_resolution(selected))
                action_layout.addWidget(resolve)
            ignored = self._report is not None and finding.key in self._report.ignored_keys
            if finding.can_ignore or ignored:
                ignore = QPushButton("Restore" if ignored else "Ignore")
                ignore.clicked.connect(
                    lambda _checked=False, selected=finding, state=not ignored:
                    self._set_ignored(selected, state)
                )
                action_layout.addWidget(ignore)
            action_layout.addStretch()
            self.table.setCellWidget(row, 4, actions)
        if findings:
            self.table.setCurrentCell(0, 0)
        else:
            self.details.setHtml(
                "<h3>No findings in this view</h3>"
                "<p>The audit found nothing matching the selected filter.</p>"
            )
            self._clear_remedy_buttons()
            self.resolution_text.setText("No issue is selected.")

    def _show_selected_details(self, row: int, _column: int, *_args) -> None:
        finding = self._row_findings.get(row)
        if finding is None:
            self._clear_remedy_buttons()
            self.resolution_text.setText("No issue is selected.")
            return
        self.details.setHtml(
            f"<h3>{html.escape(finding.title)}</h3>"
            f"<p><b>{html.escape(finding.category)} · "
            f"{html.escape(finding.severity.title())}</b></p>"
            f"<p>{html.escape(finding.summary)}</p>"
            + (f"<p>{html.escape(finding.details)}</p>" if finding.details else "")
        )
        self._populate_resolution_panel(finding)

    def _configured_action(self, finding: AuditFinding) -> AuditAction | None:
        return self.actions.get(finding.resolver_key) or self.actions.get(finding.action_key)

    def _remedies(self, finding: AuditFinding):
        return DEFAULT_AUDIT_RESOLVERS.remedies(
            audit_context(self.repository, self.character_id), finding
        )

    def _preview(self, finding: AuditFinding, remedy_key: str = ""):
        return DEFAULT_AUDIT_RESOLVERS.preview(
            audit_context(self.repository, self.character_id), finding, remedy_key
        )

    @staticmethod
    def _preview_html(preview) -> str:
        parts = [f"<b>Affected:</b> {html.escape(preview.affected)}"]
        if preview.current:
            parts.append(f"<b>Current:</b> {html.escape(preview.current)}")
        if preview.proposed:
            parts.append(f"<b>Proposed:</b> {html.escape(preview.proposed)}")
        if preview.consequences:
            parts.append(
                "<b>Consequences:</b><ul>"
                + "".join(f"<li>{html.escape(value)}</li>" for value in preview.consequences)
                + "</ul>"
            )
        return "<br>".join(parts)

    def _clear_remedy_buttons(self) -> None:
        while self.remedy_buttons.count():
            item = self.remedy_buttons.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_resolution_panel(self, finding: AuditFinding) -> None:
        self._clear_remedy_buttons()
        remedies = self._remedies(finding)
        configured = self._configured_action(finding)
        preview = self._preview(
            finding,
            remedies[0].key if len(remedies) == 1 else "",
        )
        self.resolution_text.setText(self._preview_html(preview))
        for remedy in remedies:
            button = QPushButton(remedy.label)
            if remedy.kind == "automatic":
                button.setObjectName("primaryButton")
            elif remedy.destructive:
                button.setObjectName("dangerButton")
            button.clicked.connect(
                lambda _checked=False, selected=finding, key=remedy.key:
                self._apply_remedy(selected, key)
            )
            button.setEnabled(remedy.kind == "automatic" or configured is not None)
            self.remedy_buttons.addWidget(button)
        if not remedies and configured is not None:
            button = QPushButton(configured.label)
            button.setObjectName("primaryButton")
            button.clicked.connect(lambda _checked=False: self._run_interactive(finding, "edit"))
            self.remedy_buttons.addWidget(button)
        self.remedy_buttons.addStretch()

    def _select_for_resolution(self, finding: AuditFinding) -> None:
        for row, candidate in self._row_findings.items():
            if candidate.key == finding.key:
                self.table.setCurrentCell(row, 0)
                self.table.scrollToItem(self.table.item(row, 0))
                break

    def _apply_remedy(self, finding: AuditFinding, remedy_key: str) -> None:
        remedy = next((item for item in self._remedies(finding) if item.key == remedy_key), None)
        if remedy is None:
            return
        preview = self._preview(finding, remedy_key)
        self.resolution_text.setText(self._preview_html(preview))
        confirmation = "\n\n".join(
            value for value in (
                f"Affected: {preview.affected}",
                f"Current: {preview.current}" if preview.current else "",
                f"Proposed: {preview.proposed}" if preview.proposed else "",
                remedy.confirmation,
            )
            if value
        )
        if remedy.kind != "automatic":
            if (remedy.destructive or remedy.confirmation) and QMessageBox.question(
                self, "Confirm audit remedy", confirmation
            ) != QMessageBox.StandardButton.Yes:
                return
            self._run_interactive(finding, remedy_key)
            return
        if remedy.confirmation and QMessageBox.question(
            self,
            "Confirm audit correction",
            confirmation,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            outcome = DEFAULT_AUDIT_RESOLVERS.apply(
                audit_context(self.repository, self.character_id), finding, remedy_key
            )
        except (ValueError, KeyError) as error:
            QMessageBox.warning(self, "Cannot resolve issue", str(error))
            return
        self._complete_resolution(outcome)

    def _run_interactive(self, finding: AuditFinding, remedy_key: str) -> None:
        action = self._configured_action(finding)
        if action is None:
            return
        if action.close_after:
            self.accept()
        parameters = inspect.signature(action.callback).parameters
        result = (
            action.callback()
            if not parameters
            else action.callback(finding, remedy_key)
        )
        if isinstance(result, AuditResolutionOutcome):
            self._complete_resolution(result)
        elif isinstance(result, AuditUndoToken):
            self._complete_resolution(AuditResolutionOutcome(True, undo=result))
        elif result:
            self._complete_resolution(AuditResolutionOutcome(True))

    def _complete_resolution(self, outcome: AuditResolutionOutcome) -> None:
        if not outcome.changed:
            if outcome.message:
                QMessageBox.information(self, "Audit", outcome.message)
            return
        self._last_undo = outcome.undo
        self.undo_button.setEnabled(self._last_undo is not None)
        self.undo_button.setText(
            self._last_undo.description if self._last_undo is not None else "Undo last audit fix"
        )
        self.resolution_applied.emit()
        self.refresh()

    def _undo_last_fix(self) -> None:
        token = self._last_undo
        if token is None:
            return
        try:
            token.restore()
        except (ValueError, KeyError) as error:
            QMessageBox.warning(self, "Cannot undo audit fix", str(error))
            return
        self._last_undo = None
        self.undo_button.setEnabled(False)
        self.undo_button.setText("Undo last audit fix")
        self.resolution_applied.emit()
        self.refresh()

    def _set_ignored(self, finding: AuditFinding, ignored: bool) -> None:
        if not finding.can_ignore:
            return
        self.repository.set_audit_finding_ignored(
            self.character_id, finding.key, ignored
        )
        self.audit_changed.emit()
        self.refresh()

    def _resolve_next_choice(self) -> None:
        if self._report is None or not self._report.choices:
            return
        finding = self._report.choices[0]
        self._select_for_resolution(finding)

    def done(self, result: int) -> None:
        """End the session-only audit undo history with the dialog itself."""

        self._last_undo = None
        self.undo_button.setEnabled(False)
        self.undo_button.setText("Undo last audit fix")
        super().done(result)


# Backward-compatible names for callers and plugins that used the first
# registry-driven level-up window.
GuidedLevelUpDialog = CharacterAuditDialog
LevelUpAction = AuditAction
