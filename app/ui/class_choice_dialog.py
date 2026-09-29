"""Reusable UI for class-feature choice providers.

The dialog knows nothing about clerics, wizards, or any other concrete class.
It renders the declarative slot supplied by :mod:`app.class_choice_rules`.
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
)

from app.class_choice_rules import (
    ClassChoiceOption, ResolvedClassChoice, class_choice_requirement_errors,
)


class ClassChoiceDialog(QDialog):
    """Search, inspect, and select the allowed options for one choice slot."""

    def __init__(self, slot: ResolvedClassChoice, parent=None) -> None:
        super().__init__(parent)
        self.slot = slot
        self._selected = set(slot.selected_keys)
        self._updating = False
        self.setWindowTitle(f"{slot.class_name} — {slot.label}")
        if len(slot.options) > 12:
            self.resize(940, 620)
        else:
            self.resize(780, 480)

        layout = QVBoxLayout(self)
        heading = QLabel(f"<b>{html.escape(slot.label)}</b>")
        layout.addWidget(heading)
        explanation = QLabel(slot.description)
        explanation.setWordWrap(True)
        explanation.setObjectName("mutedText")
        layout.addWidget(explanation)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search names and descriptions…")
        self.category = QComboBox()
        self.category.addItem("All categories", "")
        categories = sorted(
            {option.category for option in slot.options if option.category},
            key=str.casefold,
        )
        for category in categories:
            self.category.addItem(category, category)
        filters.addWidget(QLabel("Find"))
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Category"))
        filters.addWidget(self.category)
        layout.addLayout(filters)

        body = QHBoxLayout()
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.results.setMinimumWidth(300)
        self.details.setMinimumWidth(340)
        body.addWidget(self.results, 2)
        body.addWidget(self.details, 3)
        layout.addLayout(body, 1)

        self.selection_status = QLabel()
        self.selection_status.setObjectName("mutedText")
        layout.addWidget(self.selection_status)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.search.textChanged.connect(self._populate)
        self.category.currentIndexChanged.connect(self._populate)
        self.results.itemChanged.connect(self._item_changed)
        self.results.currentItemChanged.connect(self._show_details)
        self._populate()

    @property
    def selected_keys(self) -> tuple[str, ...]:
        ordered = [option.key for option in self.slot.options if option.key in self._selected]
        return tuple(ordered[: self.slot.maximum])

    def _selected_cost(self, extra_key: str = "") -> int:
        keys = set(self._selected)
        if extra_key:
            keys.add(extra_key)
        return sum(option.cost for option in self.slot.options if option.key in keys)

    def _visible_options(self) -> tuple[ClassChoiceOption, ...]:
        query = self.search.text().strip().casefold()
        category = str(self.category.currentData() or "")
        return tuple(
            option
            for option in self.slot.options
            if (not category or option.category == category)
            and (
                not query
                or query in option.name.casefold()
                or query in option.description.casefold()
            )
        )

    def _populate(self, *_args) -> None:
        current_key = ""
        if self.results.currentItem() is not None:
            current_key = str(
                self.results.currentItem().data(Qt.ItemDataRole.UserRole) or ""
            )
        self._updating = True
        try:
            self.results.clear()
            for option in self._visible_options():
                label = option.name
                if option.category:
                    label += f"  ·  {option.category}"
                if self.slot.point_budget:
                    label += f"  ·  {option.cost} point{'s' if option.cost != 1 else ''}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, option.key)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if option.key in self._selected
                    else Qt.CheckState.Unchecked
                )
                item.setToolTip(option.description)
                self.results.addItem(item)
                if option.key == current_key:
                    self.results.setCurrentItem(item)
        finally:
            self._updating = False
        if self.results.currentRow() < 0 and self.results.count():
            self.results.setCurrentRow(0)
        self._update_status()

    def _item_changed(self, item: QListWidgetItem) -> None:
        if self._updating:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if item.checkState() == Qt.CheckState.Checked:
            exceeds_count = key not in self._selected and len(self._selected) >= self.slot.maximum
            exceeds_points = (
                key not in self._selected
                and bool(self.slot.point_budget)
                and self._selected_cost(key) > self.slot.point_budget
            )
            if exceeds_count or exceeds_points:
                self._updating = True
                item.setCheckState(Qt.CheckState.Unchecked)
                self._updating = False
            else:
                self._selected.add(key)
        else:
            self._selected.discard(key)
        self._update_status()

    def _show_details(self, item: QListWidgetItem | None, _previous=None) -> None:
        if item is None:
            self.details.clear()
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        option = next((value for value in self.slot.options if value.key == key), None)
        if option is None:
            self.details.clear()
            return
        source = html.escape(option.source)
        source_line = f"<p><i>{source}</i></p>" if source else ""
        link = (
            f'<p><a href="{html.escape(option.source_url, quote=True)}">Rules source</a></p>'
            if option.source_url
            else ""
        )
        grants = ""
        if option.granted_features:
            rows = "".join(
                f"<li><b>Level {int(value.get('level', 1) or 1)}:</b> "
                f"{html.escape(str(value.get('name') or 'Feature'))}</li>"
                for value in option.granted_features
            )
            grants = f"<h4>Granted features</h4><ul>{rows}</ul>"
        self.details.setHtml(
            f"<h2>{html.escape(option.name)}</h2>{source_line}"
            f"<p>{html.escape(option.description).replace(chr(10), '<br>')}</p>"
            f"{grants}{link}"
        )

    def _update_status(self) -> None:
        count = len(self._selected)
        errors = class_choice_requirement_errors(self.slot, self._selected)
        if self.slot.minimum == self.slot.maximum:
            requirement = f"choose {self.slot.maximum}"
        else:
            requirement = f"choose {self.slot.minimum}–{self.slot.maximum}"
        self.selection_status.setText(
            f"Selected {count} of {self.slot.maximum} · {requirement}"
            + (
                f" · {self._selected_cost()} of {self.slot.point_budget} points"
                if self.slot.point_budget else ""
            )
            + ("\n" + "; ".join(errors) if errors else "")
        )
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(
            self.slot.minimum <= count <= self.slot.maximum
            and not errors
            and (
                not self.slot.point_budget
                or self._selected_cost() <= self.slot.point_budget
            )
        )
