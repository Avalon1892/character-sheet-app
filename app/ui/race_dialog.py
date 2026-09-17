"""Searchable, rules-aware race and alternate racial trait chooser."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QSplitter, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget,
)

from app.content import entries
from app.models import ABILITIES, CharacterDetails, RaceTraitChoice
from app.race_rules import (
    alternate_trait_conflicts,
    racial_choice_specs,
    resolved_race,
    validate_race_trait_choices,
)


class RaceCatalogDialog(QDialog):
    """Select one race, optional heritage, and compatible alternate traits."""

    def __init__(self, details: CharacterDetails, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose race")
        self.resize(1180, 760)
        self._entries = tuple(entries("races"))
        self._by_key = {str(entry["key"]): entry for entry in self._entries}
        self._initial = details
        self._entry: dict | None = None
        self._loading = False
        self._choice_widgets: dict[tuple[str, str], list[QWidget]] = {}
        self._choice_specs: dict[tuple[str, str], dict] = {}

        layout = QVBoxLayout(self)
        title = QLabel("PATHFINDER RACES")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search race names and descriptions…")
        layout.addWidget(self.search)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.races = QListWidget()
        self.races.setMinimumWidth(230)
        splitter.addWidget(self.races)

        choices = QWidget()
        choice_layout = QVBoxLayout(choices)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        selectors = QHBoxLayout()
        selectors.addWidget(QLabel("Subrace / heritage"))
        self.variant = QComboBox()
        selectors.addWidget(self.variant, 1)
        selectors.addWidget(QLabel("Flexible ability"))
        self.ability = QComboBox()
        self.ability.addItem("Not applicable", "")
        for key, name, _short in ABILITIES:
            self.ability.addItem(name, key)
        selectors.addWidget(self.ability)
        choice_layout.addLayout(selectors)
        alternate_title = QLabel("ALTERNATE RACIAL TRAITS")
        alternate_title.setObjectName("sectionTitle")
        choice_layout.addWidget(alternate_title)
        self.alternates = QTableWidget(0, 3)
        self.alternates.setHorizontalHeaderLabels(("Use", "Trait", "Replaces"))
        self.alternates.verticalHeader().setVisible(False)
        self.alternates.setAlternatingRowColors(True)
        self.alternates.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.alternates.horizontalHeader().setStretchLastSection(True)
        self.alternates.setColumnWidth(0, 48)
        self.alternates.setColumnWidth(1, 250)
        choice_layout.addWidget(self.alternates, 1)
        self.trait_choices_group = QGroupBox("Required trait choices")
        self.trait_choices_layout = QFormLayout(self.trait_choices_group)
        self.trait_choices_layout.setContentsMargins(8, 8, 8, 8)
        self.choice_details = QLabel("")
        self.choice_details.setObjectName("mutedText")
        self.choice_details.setWordWrap(True)
        self.choice_details.hide()
        choice_layout.addWidget(self.trait_choices_group)
        choice_layout.addWidget(self.choice_details)
        self.trait_choices_group.hide()
        self.validation = QLabel("")
        self.validation.setObjectName("mutedText")
        self.validation.setWordWrap(True)
        choice_layout.addWidget(self.validation)
        splitter.addWidget(choices)

        self.details = QTextBrowser()
        self.details.setMinimumWidth(370)
        self.details.setOpenExternalLinks(True)
        splitter.addWidget(self.details)
        splitter.setSizes([240, 500, 440])
        layout.addWidget(splitter, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.search.textChanged.connect(self._filter)
        self.races.currentItemChanged.connect(self._race_changed)
        self.variant.currentIndexChanged.connect(self._variant_changed)
        self.alternates.itemChanged.connect(self._alternate_changed)
        self.alternates.currentCellChanged.connect(self._alternate_preview)
        self._filter("")
        if details.race_key:
            self._select_key(details.race_key)

    def _filter(self, query: str) -> None:
        needle = query.strip().casefold()
        current = self.current_race_key()
        self.races.clear()
        for entry in self._entries:
            haystack = f"{entry['name']} {entry.get('description', '')}".casefold()
            if needle and needle not in haystack:
                continue
            item = QListWidgetItem(str(entry["name"]))
            item.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
            item.setToolTip(str(entry.get("description") or ""))
            self.races.addItem(item)
        if current:
            self._select_key(current)

    def _select_key(self, key: str) -> None:
        for row in range(self.races.count()):
            item = self.races.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole)) == key:
                self.races.setCurrentItem(item)
                self.races.scrollToItem(item)
                return

    def current_race_key(self) -> str:
        item = self.races.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _race_changed(self, item: QListWidgetItem | None, _previous=None) -> None:
        key = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        self._entry = self._by_key.get(key)
        self._loading = True
        try:
            self.variant.clear()
            self.variant.addItem("Base race", "")
            for variant in (self._entry or {}).get("variants", ()):
                self.variant.addItem(str(variant["name"]), str(variant["key"]))
            if key == self._initial.race_key:
                index = self.variant.findData(self._initial.race_variant_key)
                self.variant.setCurrentIndex(max(0, index))
            self._populate_alternates(
                set(self._initial.race_alternate_trait_keys) if key == self._initial.race_key else set()
            )
            initial_choices = {
                (choice.trait_key, choice.choice_key): choice.values
                for choice in self._initial.race_trait_choices
            } if key == self._initial.race_key else {}
            self._rebuild_choice_controls(initial_choices)
            self._update_flexible_ability()
            ability_index = self.ability.findData(
                self._initial.race_ability_choice
                if key == self._initial.race_key and self.ability.isEnabled()
                else ""
            )
            self.ability.setCurrentIndex(max(0, ability_index))
        finally:
            self._loading = False
        self._show_race()
        self._validate()

    def _populate_alternates(self, selected: set[str]) -> None:
        traits = tuple((self._entry or {}).get("alternate_racial_traits", ()))
        self.alternates.setRowCount(len(traits))
        for row, trait in enumerate(traits):
            use = QTableWidgetItem("")
            use.setFlags(use.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(
                Qt.CheckState.Checked if str(trait["key"]) in selected else Qt.CheckState.Unchecked
            )
            use.setData(Qt.ItemDataRole.UserRole, dict(trait))
            name = QTableWidgetItem(str(trait["name"]))
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            replaces = QTableWidgetItem(", ".join(str(value) for value in trait.get("replaces", ())) or "Nothing")
            replaces.setFlags(replaces.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for cell in (use, name, replaces):
                cell.setToolTip(str(trait.get("description") or ""))
            self.alternates.setItem(row, 0, use)
            self.alternates.setItem(row, 1, name)
            self.alternates.setItem(row, 2, replaces)
        self.alternates.resizeRowsToContents()

    def selected_alternate_keys(self) -> tuple[str, ...]:
        result: list[str] = []
        for row in range(self.alternates.rowCount()):
            item = self.alternates.item(row, 0)
            trait = item.data(Qt.ItemDataRole.UserRole) if item else None
            if item and item.checkState() == Qt.CheckState.Checked and isinstance(trait, dict):
                result.append(str(trait["key"]))
        return tuple(result)

    def _alternate_changed(self, _item: QTableWidgetItem) -> None:
        if not self._loading:
            current = self._choice_values()
            self._loading = True
            try:
                self._rebuild_choice_controls(current)
                self._update_flexible_ability()
            finally:
                self._loading = False
            self._validate()

    def _clear_choice_controls(self) -> None:
        while self.trait_choices_layout.rowCount():
            self.trait_choices_layout.removeRow(0)
        self._choice_widgets.clear()
        self._choice_specs.clear()
        self.choice_details.clear()
        self.choice_details.hide()

    def _choice_values(self) -> dict[tuple[str, str], tuple[str, ...]]:
        result: dict[tuple[str, str], tuple[str, ...]] = {}
        for key, widgets in self._choice_widgets.items():
            spec = self._choice_specs.get(key, {})
            kind = str(spec.get("kind") or "options")
            values: list[str] = []
            for widget in widgets:
                if isinstance(widget, QComboBox):
                    value = str(widget.currentData() or "")
                    if value:
                        values.append(value)
                elif isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                    if value:
                        values.append(value)
                elif isinstance(widget, QPlainTextEdit):
                    values.extend(
                        value.strip()
                        for value in widget.toPlainText().replace(",", "\n").splitlines()
                        if value.strip()
                    )
            if values:
                result[key] = tuple(values)
        return result

    def _rebuild_choice_controls(
        self,
        preferred: dict[tuple[str, str], tuple[str, ...]],
    ) -> None:
        self._clear_choice_controls()
        if self._entry is None:
            self.trait_choices_group.hide()
            return
        for trait, spec in racial_choice_specs(self._entry, self.selected_alternate_keys()):
            key = (str(trait.get("key") or ""), str(spec.get("key") or ""))
            self._choice_specs[key] = {
                **spec, "_trait_name": str(trait.get("name") or "Racial trait")
            }
            maximum = int(spec.get("maximum", spec.get("count", 1)) or 1)
            kind = str(spec.get("kind") or "options")
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            widgets: list[QWidget] = []
            selected = preferred.get(key, ())
            if kind == "text":
                editor = QLineEdit()
                editor.setPlaceholderText(str(spec.get("placeholder") or "Enter a value"))
                if selected:
                    editor.setText(selected[0])
                editor.textChanged.connect(self._choice_changed)
                widgets.append(editor)
                row_layout.addWidget(editor, 1)
            elif kind == "text_list":
                editor = QPlainTextEdit()
                editor.setPlaceholderText(str(spec.get("placeholder") or "Enter one value per line"))
                editor.setMaximumHeight(90)
                editor.setPlainText("\n".join(selected))
                editor.textChanged.connect(self._choice_changed)
                widgets.append(editor)
                row_layout.addWidget(editor, 1)
            else:
                for index in range(maximum):
                    combo = QComboBox()
                    combo.setSizeAdjustPolicy(
                        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                    )
                    combo.setMinimumContentsLength(24)
                    combo.setSizePolicy(
                        QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
                    )
                    combo.view().setTextElideMode(Qt.TextElideMode.ElideRight)
                    combo.addItem("Choose…", "")
                    for option in spec.get("options", ()):
                        combo.addItem(
                            str(option.get("label") or option.get("key") or ""),
                            str(option.get("key") or ""),
                        )
                        option_index = combo.count() - 1
                        description = str(option.get("description") or "")
                        if description:
                            combo.setItemData(option_index, description, Qt.ItemDataRole.ToolTipRole)
                    if index < len(selected):
                        option_index = combo.findData(selected[index])
                        combo.setCurrentIndex(max(0, option_index))
                    combo.currentIndexChanged.connect(self._choice_changed)
                    widgets.append(combo)
                    row_layout.addWidget(combo, 1)
            self._choice_widgets[key] = widgets
            self.trait_choices_layout.addRow(
                f"{trait.get('name', 'Trait')} · {spec.get('label', 'Choice')}", row
            )
        self.trait_choices_group.setVisible(bool(self._choice_widgets))
        self._update_choice_details()

    def _choice_changed(self) -> None:
        self._update_choice_details()
        if not self._loading:
            self._validate()

    def _update_choice_details(self) -> None:
        lines: list[str] = []
        for key, values in self._choice_values().items():
            spec = self._choice_specs.get(key, {})
            options = {
                str(option.get("key") or ""): option
                for option in spec.get("options", ())
            }
            for value in values:
                option = options.get(value)
                description = str((option or {}).get("description") or "")
                if description:
                    lines.append(
                        f"{spec.get('_trait_name', 'Trait')} — "
                        f"{option.get('label', value)}: {description}"
                    )
        self.choice_details.setText("\n\n".join(lines))
        self.choice_details.setVisible(bool(lines))

    def selected_trait_choices(self) -> tuple[RaceTraitChoice, ...]:
        return tuple(
            RaceTraitChoice(trait_key, choice_key, values)
            for (trait_key, choice_key), values in self._choice_values().items()
            if values
        )

    def _update_flexible_ability(self) -> None:
        if self._entry is None:
            self.ability.setEnabled(False)
            return
        profile = resolved_race(CharacterDetails(
            self._initial.character_id,
            race=str(self._entry.get("name") or ""),
            race_key=str(self._entry.get("key") or ""),
            race_variant_key=str(self.variant.currentData() or ""),
            race_alternate_trait_keys=self.selected_alternate_keys(),
            race_trait_choices=self.selected_trait_choices(),
        ))
        self.ability.setEnabled(bool(profile.flexible_bonus))
        if not profile.flexible_bonus:
            self.ability.setCurrentIndex(0)

    def _validate(self) -> None:
        conflicts = alternate_trait_conflicts(self._entry or {}, self.selected_alternate_keys())
        choice_errors = validate_race_trait_choices(
            self._entry or {}, self.selected_alternate_keys(), self.selected_trait_choices()
        )
        ok = self._entry is not None and not conflicts and not choice_errors
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            self.validation.setText(f"Choose only one alternate trait replacing each base trait. Conflict: {names}.")
        elif self._entry is None:
            self.validation.setText("Choose a race.")
        elif choice_errors:
            self.validation.setText(" ".join(choice_errors))
        else:
            self.validation.setText(
                f"{len(self.selected_alternate_keys())} alternate racial trait(s) selected."
            )

    def _variant_changed(self) -> None:
        if self._loading or self._entry is None:
            return
        self._update_flexible_ability()
        self._show_race()

    def _show_race(self) -> None:
        if self._entry is None:
            self.details.clear()
            return
        variant = next(
            (item for item in self._entry.get("variants", ()) if item.get("key") == self.variant.currentData()),
            None,
        )
        traits = "".join(
            f"<h3>{html.escape(str(trait['name']))}</h3><p>{html.escape(str(trait.get('description') or ''))}</p>"
            for trait in self._entry.get("racial_traits", ())
        )
        variant_html = (
            f"<h2>{html.escape(str(variant['name']))}</h2><p>{html.escape(str(variant.get('description') or ''))}</p>"
            if variant else ""
        )
        source = html.escape(str(self._entry.get("source_url") or ""), quote=True)
        self.details.setHtml(
            f"<h1>{html.escape(str(self._entry['name']))}</h1>"
            f"<p>{html.escape(str(self._entry.get('description') or ''))}</p>{variant_html}"
            f"<p><b>Size:</b> {html.escape(str(self._entry.get('size') or 'Medium'))} &nbsp; "
            f"<b>Speed:</b> {int(self._entry.get('base_speed') or 30)} ft.</p>"
            f"<p><a href='{source}'>Official rules source</a></p><h2>Base racial traits</h2>{traits}"
        )

    def _alternate_preview(self, row: int, _column: int, *_args) -> None:
        item = self.alternates.item(row, 0) if row >= 0 else None
        trait = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(trait, dict):
            self._show_race()
            return
        self.details.setHtml(
            f"<h1>{html.escape(str(trait['name']))}</h1>"
            f"<p><b>Replaces:</b> {html.escape(', '.join(trait.get('replaces', ())) or 'Nothing')}</p>"
            f"<p>{html.escape(str(trait.get('description') or ''))}</p>"
        )

    def selection(self) -> dict:
        if self._entry is None:
            return {}
        variant = next(
            (item for item in self._entry.get("variants", ()) if item.get("key") == self.variant.currentData()),
            None,
        )
        return {
            "race_key": str(self._entry["key"]),
            "race_name": str(self._entry["name"]),
            "size": str((variant or {}).get("size") or self._entry.get("size") or "Medium"),
            "ability_choice": str(self.ability.currentData() or "") if self.ability.isEnabled() else "",
            "variant_key": str(self.variant.currentData() or ""),
            "alternate_trait_keys": self.selected_alternate_keys(),
            "trait_choices": self.selected_trait_choices(),
        }
