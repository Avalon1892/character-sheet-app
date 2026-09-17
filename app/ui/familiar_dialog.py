"""Searchable chooser for the shared PF1e Familiar/Pet creature catalog."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.bonded_companion_rules import familiar_catalog
from app.catalog_search import CatalogSearchIndex
from app.ui.components import DebouncedCallback, section_title


class FamiliarCatalogDialog(QDialog):
    """Single-selection catalog with readable creature statistics."""

    def __init__(self, current_key: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Familiar or Pet Form")
        self.resize(1180, 720)
        self.selected_entry: dict | None = None
        self._entries = familiar_catalog()
        self._visible_entries: tuple[dict, ...] = ()
        self._index = CatalogSearchIndex(
            self._entries,
            description_fields=(
                "familiar_special", "source", "ruleset", "skills",
                "feats", "special_qualities", "senses",
            ),
        )
        layout = QVBoxLayout(self)
        layout.addWidget(section_title("FAMILIAR & PET FORMS"))
        subtitle = QLabel(
            "Choose a published creature baseline. Familiar progression, master BAB, "
            "saves, maximum HP, Intelligence, natural armor, and special abilities are applied automatically."
        )
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Find"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search familiar names, abilities, skills, or sources…")
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Ruleset"))
        self.ruleset = QComboBox()
        self.ruleset.addItems(("All rulesets", "Pathfinder", "Third Party"))
        filters.addWidget(self.ruleset)
        self.match_count = QLabel()
        self.match_count.setObjectName("mutedText")
        filters.addWidget(self.match_count)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(("Familiar", "Ruleset", "Size", "Master benefit"))
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.verticalHeader().setVisible(False)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.setColumnWidth(0, 260)
        self.results.setColumnWidth(1, 110)
        self.results.setColumnWidth(2, 90)
        splitter.addWidget(self.results)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.details.setHtml("<p>Select a familiar to inspect its complete baseline.</p>")
        splitter.addWidget(self.details)
        splitter.setSizes((720, 440))
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.choose_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.choose_button.setText("Choose Familiar")
        self.choose_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._debounce = DebouncedCallback(self._refresh_results, 250, self)
        self.search.textChanged.connect(lambda *_: self._debounce.schedule())
        self.ruleset.currentIndexChanged.connect(self._refresh_results)
        self.results.itemSelectionChanged.connect(self._show_selection)
        self.results.itemDoubleClicked.connect(lambda *_: self._accept_selected())
        self._refresh_results()
        if current_key:
            self._select_key(current_key)

    def _refresh_results(self) -> None:
        ruleset = self.ruleset.currentText()
        records = self._index.search(self.search.text(), mode="both", limit=500).records
        if ruleset != "All rulesets":
            records = tuple(
                entry for entry in records
                if str(entry.get("ruleset", "Pathfinder")) == ruleset
            )
        self._visible_entries = tuple(records)
        self.results.blockSignals(True)
        self.results.clearContents()
        self.results.setRowCount(len(records))
        for row, entry in enumerate(records):
            values = (
                entry.get("name", ""),
                entry.get("ruleset", "Pathfinder"),
                entry.get("size", "—"),
                entry.get("familiar_special", "—"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, str(entry.get("key", "")))
                self.results.setItem(row, column, item)
        self.results.clearSelection()
        self.results.setCurrentItem(None)
        self.results.blockSignals(False)
        self.match_count.setText(f"{len(records)} forms")
        self.selected_entry = None
        self.choose_button.setEnabled(False)
        self.details.setHtml("<p>Select a familiar to inspect its complete baseline.</p>")

    def _selected(self) -> dict | None:
        row = self.results.currentRow()
        return self._visible_entries[row] if 0 <= row < len(self._visible_entries) else None

    @staticmethod
    def _signed(value) -> str:
        try:
            return f"{int(value):+d}"
        except (TypeError, ValueError):
            return "—"

    def _show_selection(self) -> None:
        entry = self._selected()
        self.selected_entry = entry
        self.choose_button.setEnabled(entry is not None)
        if entry is None:
            return
        abilities = dict(entry.get("abilities") or {})
        ability_text = " · ".join(
            f"{key.upper()} {abilities.get(key, '—')}"
            for key in ("str", "dex", "con", "int", "wis", "cha")
        )
        attacks = " · ".join(
            value for value in (str(entry.get("melee") or ""), str(entry.get("ranged") or "")) if value
        ) or "—"
        url = str(entry.get("source_url") or "")
        source_link = f'<a href="{escape(url)}">Open rules source</a>' if url else ""
        self.details.setHtml(
            f"<h2>{escape(str(entry.get('name', 'Familiar')))}</h2>"
            f"<p><b>{escape(str(entry.get('ruleset', 'Pathfinder')))}</b> · "
            f"{escape(str(entry.get('source', 'Unknown source')))}</p>"
            f"<p><b>Master benefit:</b> {escape(str(entry.get('familiar_special', '—')))}</p>"
            f"<hr><p><b>Size/type:</b> {escape(str(entry.get('size', '—')))} "
            f"{escape(str(entry.get('creature_type', 'creature')))}</p>"
            f"<p><b>AC:</b> {escape(str(entry.get('armor_class', '—')))} · "
            f"<b>Touch:</b> {escape(str(entry.get('touch_ac', '—')))} · "
            f"<b>Flat-footed:</b> {escape(str(entry.get('flat_footed_ac', '—')))}</p>"
            f"<p><b>Creature HP/HD:</b> {escape(str(entry.get('base_hp', '—')))} "
            f"({escape(str(entry.get('hit_dice', '—')))}) · "
            f"<b>Fort/Ref/Will:</b> {self._signed(entry.get('fortitude'))} / "
            f"{self._signed(entry.get('reflex'))} / {self._signed(entry.get('will'))}</p>"
            f"<p><b>Abilities:</b> {escape(ability_text)}</p>"
            f"<p><b>Speed:</b> {escape(str(entry.get('speed', '—')))}<br>"
            f"<b>Senses:</b> {escape(str(entry.get('senses', '—')))}</p>"
            f"<p><b>Attacks:</b> {escape(attacks)}</p>"
            f"<p><b>Feats:</b> {escape(str(entry.get('feats', '—')))}<br>"
            f"<b>Skills:</b> {escape(str(entry.get('skills', '—')))}<br>"
            f"<b>Special qualities:</b> {escape(str(entry.get('special_qualities', '—')))}</p>"
            f"<p>{source_link}</p>"
        )

    def _accept_selected(self) -> None:
        if self._selected() is not None:
            self.accept()

    def _select_key(self, key: str) -> None:
        for row, entry in enumerate(self._visible_entries):
            if str(entry.get("key", "")) == key:
                self.results.setCurrentCell(row, 0)
                self.results.selectRow(row)
                break
