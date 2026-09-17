"""Shared picker for recurring class powers such as revelations and rage powers."""
from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QTextBrowser, QVBoxLayout,
)

from app.class_power_rules import ClassPowerOption, ResolvedClassPowerSet


class ClassPowerDialog(QDialog):
    """Search a catalog, inspect rules, and fill ordered acquisition slots."""

    def __init__(self, power_set: ResolvedClassPowerSet, parent=None) -> None:
        super().__init__(parent)
        self.power_set = power_set
        self._selected = list(power_set.selected_keys)
        self._active = set(power_set.active_keys)
        self._populating_selected = False
        self.setWindowTitle(f"{power_set.class_name} — {power_set.label}")
        self.resize(1040, 650)

        layout = QVBoxLayout(self)
        title = QLabel(f"<b>{html.escape(power_set.label)}</b> — {len(self._selected)} / {power_set.maximum}")
        self.title = title
        layout.addWidget(title)
        note = QLabel(power_set.description)
        note.setObjectName("mutedText"); note.setWordWrap(True); layout.addWidget(note)

        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search names and descriptions…")
        self.category = QComboBox(); self.category.addItem("All categories", "")
        for category in sorted({option.category for option in power_set.options}, key=str.casefold):
            self.category.addItem(category, category)
        filters.addWidget(QLabel("Find")); filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Category")); filters.addWidget(self.category)
        layout.addLayout(filters)

        body = QHBoxLayout()
        available_column = QVBoxLayout(); available_column.addWidget(QLabel("AVAILABLE POWERS"))
        self.available = QListWidget(); available_column.addWidget(self.available, 1)
        add = QPushButton("Add selected →"); add.setObjectName("primaryButton"); add.clicked.connect(self._add)
        available_column.addWidget(add)
        selected_column = QVBoxLayout(); selected_column.addWidget(QLabel("SELECTED / ACQUISITION ORDER"))
        self.selected = QListWidget(); selected_column.addWidget(self.selected, 1)
        remove = QPushButton("Remove selected"); remove.clicked.connect(self._remove)
        selected_column.addWidget(remove)
        self.details = QTextBrowser(); self.details.setOpenExternalLinks(True); self.details.setMinimumWidth(330)
        self.available.setMinimumWidth(280)
        self.selected.setMinimumWidth(230)
        self.available.setWordWrap(True); self.selected.setWordWrap(True)
        body.addLayout(available_column, 3); body.addLayout(selected_column, 2); body.addWidget(self.details, 4)
        layout.addLayout(body, 1)

        self.status = QLabel(); self.status.setObjectName("mutedText"); layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)

        self.search.textChanged.connect(self._populate_available)
        self.category.currentIndexChanged.connect(self._populate_available)
        self.available.currentItemChanged.connect(self._show_available_details)
        self.available.itemDoubleClicked.connect(lambda _item: self._add())
        self.selected.currentItemChanged.connect(self._show_selected_details)
        self.selected.itemChanged.connect(self._selected_state_changed)
        self.selected.itemDoubleClicked.connect(lambda _item: self._remove())
        self._refresh()

    @property
    def selected_keys(self) -> tuple[str, ...]:
        return tuple(self._selected[: self.power_set.maximum])

    @property
    def active_keys(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(key for key in self._selected if key in self._active))

    def _option(self, key: str) -> ClassPowerOption | None:
        return next((option for option in self.power_set.options if option.key == key), None)

    @staticmethod
    def _name_token(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()

    def _reason(self, option: ClassPowerOption) -> str:
        if len(self._selected) >= self.power_set.maximum:
            return "All available class-power slots are filled."
        acquisition_level = self.power_set.slot_levels[len(self._selected)]
        if acquisition_level < option.minimum_level:
            return f"Requires class level {option.minimum_level}; the next open power slot is level {acquisition_level}."
        owned = {
            self._name_token(selected.name)
            for key in self._selected
            if (selected := self._option(key)) is not None
        }
        missing = [name for name in option.prerequisite_names if self._name_token(name) not in owned]
        return "Requires: " + ", ".join(missing) if missing else ""

    def _visible(self) -> tuple[ClassPowerOption, ...]:
        query = self.search.text().strip().casefold()
        category = str(self.category.currentData() or "")
        return tuple(
            option for option in self.power_set.options
            if (not category or option.category == category)
            and (not query or query in option.name.casefold() or query in option.description.casefold())
        )

    def _populate_available(self, *_args) -> None:
        current = str(self.available.currentItem().data(Qt.ItemDataRole.UserRole) or "") if self.available.currentItem() else ""
        self.available.clear()
        for option in self._visible():
            reason = self._reason(option)
            owned = self._selected.count(option.key)
            label = option.name + (f"  ·  {option.category}" if option.category else "")
            if owned:
                label += f"  ·  selected{f' ×{owned}' if owned > 1 else ''}"
            item = QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole, option.key)
            if reason:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(reason)
            else:
                item.setToolTip(option.description)
            self.available.addItem(item)
            if option.key == current: self.available.setCurrentItem(item)
        if self.available.currentRow() < 0 and self.available.count(): self.available.setCurrentRow(0)

    def _populate_selected(self) -> None:
        current = self.selected.currentRow()
        self._populating_selected = True
        self.selected.clear()
        for index, key in enumerate(self._selected):
            option = self._option(key)
            if option is None: continue
            level = self.power_set.slot_levels[index] if index < len(self.power_set.slot_levels) else "—"
            item = QListWidgetItem(f"Level {level} · {option.name}")
            item.setData(Qt.ItemDataRole.UserRole, (index, key)); item.setToolTip(option.description)
            if option.activatable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if key in self._active else Qt.CheckState.Unchecked
                )
            self.selected.addItem(item)
        self._populating_selected = False
        if self.selected.count(): self.selected.setCurrentRow(min(max(current, 0), self.selected.count() - 1))

    def _refresh(self) -> None:
        self._populate_available(); self._populate_selected()
        count = len(self._selected); self.title.setText(f"<b>{html.escape(self.power_set.label)}</b> — {count} / {self.power_set.maximum}")
        self.status.setText(f"Selected {count} of {self.power_set.maximum} available class-power slots. Empty slots are allowed while building the character.")

    def _add(self) -> None:
        item = self.available.currentItem()
        if item is None or len(self._selected) >= self.power_set.maximum: return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        option = self._option(key)
        if option is None or self._reason(option): return
        if key in self._selected and not option.repeatable: return
        self._selected.append(key); self._refresh()

    def _remove(self) -> None:
        item = self.selected.currentItem()
        if item is None: return
        index, _key = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= int(index) < len(self._selected):
            removed = self._selected.pop(int(index))
            if removed not in self._selected:
                self._active.discard(removed)
        self._refresh()

    def _selected_state_changed(self, item: QListWidgetItem) -> None:
        if self._populating_selected:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        _index, key = data
        option = self._option(str(key))
        if option is None or not option.activatable:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._active.add(str(key))
        else:
            self._active.discard(str(key))
        # Repeatable powers share one live state; keep duplicate rows in sync.
        self._populate_selected()

    def _show_available_details(self, item: QListWidgetItem | None, _previous=None) -> None:
        key = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        self._show_details(self._option(key))

    def _show_selected_details(self, item: QListWidgetItem | None, _previous=None) -> None:
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._show_details(self._option(str(data[1]))) if data else self.details.clear()

    def _show_details(self, option: ClassPowerOption | None) -> None:
        if option is None: self.details.clear(); return
        reason = self._reason(option)
        requirements = []
        if option.minimum_level > 1: requirements.append(f"Class level {option.minimum_level}")
        requirements.extend(option.prerequisite_names)
        active_note = (
            "<p><b>Play state:</b> Check this power in the selected list while its situational effect is active.</p>"
            if option.activatable else ""
        )
        automatic = "".join(
            f"<li>{html.escape(str(effect.get('label') or effect.get('target') or 'Automatic effect'))}: "
            f"{int(effect.get('value') or 0):+d} {html.escape(str(effect.get('bonus_type') or 'untyped'))}</li>"
            for effect in option.automatic_modifiers
        )
        self.details.setHtml(
            f"<h2>{html.escape(option.name)}</h2><p><i>{html.escape(option.category)} · {html.escape(option.source)}</i></p>"
            + (f"<p><b>Unavailable:</b> {html.escape(reason)}</p>" if reason else "")
            + (f"<p><b>Requirements:</b> {html.escape(', '.join(requirements))}</p>" if requirements else "")
            + active_note
            + (f"<p><b>Automatic sheet effects</b></p><ul>{automatic}</ul>" if automatic else "")
            + f"<p>{html.escape(option.description).replace(chr(10), '<br>')}</p>"
            + (f'<p><a href="{html.escape(option.source_url, quote=True)}">Rules source</a></p>' if option.source_url else "")
        )
