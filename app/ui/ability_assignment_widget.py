"""Reusable ability assignment control for guided character creation."""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.ability_score_generation import (
    ABILITY_ARRAY_PRESETS,
    ABILITY_ARRAYS_BY_KEY,
    ability_point_buy_cost,
)
from app.models import ABILITIES


class AbilityAssignmentWidget(QWidget):
    """Assign manual scores or distribute one registered score array."""

    scoresChanged = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._swapping = False
        self._racial_adjustments: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Score method"))
        self.method = QComboBox()
        self.method.addItem("Enter scores manually", "manual")
        for preset in ABILITY_ARRAY_PRESETS:
            self.method.addItem(preset.name, preset.key)
            self.method.setItemData(self.method.count() - 1, preset.description, 3)
        method_row.addWidget(self.method, 1)
        self.edit_manually = QPushButton("Edit these scores manually")
        self.edit_manually.setToolTip(
            "Keep the current assignment, then unlock every score for free editing."
        )
        self.edit_manually.clicked.connect(self._convert_to_manual)
        self.edit_manually.hide()
        method_row.addWidget(self.edit_manually)
        layout.addLayout(method_row)

        self.help = QLabel(
            "Enter base scores before racial adjustments. Preset arrays can be reassigned "
            "freely; choosing a used value swaps the two assignments."
        )
        self.help.setObjectName("mutedText")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for column, text in enumerate(("ABILITY", "BASE SCORE", "RACIAL", "STARTING SCORE")):
            label = QLabel(text)
            label.setObjectName("creationColumnHeader")
            grid.addWidget(label, 0, column)

        self._editors: dict[str, QStackedWidget] = {}
        self._manual: dict[str, QSpinBox] = {}
        self._array: dict[str, QComboBox] = {}
        self._racial_labels: dict[str, QLabel] = {}
        self._final_labels: dict[str, QLabel] = {}
        for row, (key, _name, abbreviation) in enumerate(ABILITIES, 1):
            ability = QLabel(abbreviation)
            ability.setObjectName("creationAbilityName")
            grid.addWidget(ability, row, 0)

            stack = QStackedWidget()
            manual = QSpinBox()
            manual.setRange(1, 99)
            manual.setValue(10)
            manual.valueChanged.connect(self._emit_scores)
            array = QComboBox()
            array.currentIndexChanged.connect(
                lambda _index, ability_key=key: self._array_assignment_changed(ability_key)
            )
            stack.addWidget(manual)
            stack.addWidget(array)
            grid.addWidget(stack, row, 1)
            self._editors[key] = stack
            self._manual[key] = manual
            self._array[key] = array

            racial = QLabel("+0")
            racial.setObjectName("creationRacialAdjustment")
            final = QLabel("10")
            final.setObjectName("creationFinalScore")
            grid.addWidget(racial, row, 2)
            grid.addWidget(final, row, 3)
            self._racial_labels[key] = racial
            self._final_labels[key] = final
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.cost = QLabel("Point-buy total: 0")
        self.cost.setObjectName("creationScoreCost")
        layout.addWidget(self.cost)
        layout.addStretch()

        self.method.currentIndexChanged.connect(self._method_changed)
        self.method.setCurrentIndex(self.method.findData("standard"))

    def scores(self) -> dict[str, int]:
        if self.method.currentData() == "manual":
            return {key: field.value() for key, field in self._manual.items()}
        return {
            key: int(field.currentData()[1])
            for key, field in self._array.items()
            if isinstance(field.currentData(), tuple)
        }

    def set_scores(self, scores: Mapping[str, int]) -> None:
        self.method.setCurrentIndex(self.method.findData("manual"))
        for key, field in self._manual.items():
            field.blockSignals(True)
            field.setValue(int(scores.get(key, 10)))
            field.blockSignals(False)
        self._emit_scores()

    def set_racial_adjustments(self, adjustments: Mapping[str, int]) -> None:
        self._racial_adjustments = {str(key): int(value) for key, value in adjustments.items()}
        self._update_totals()

    def _method_changed(self, *_args) -> None:
        key = str(self.method.currentData() or "manual")
        manual = key == "manual"
        for stack in self._editors.values():
            stack.setCurrentIndex(0 if manual else 1)
        self.edit_manually.setVisible(not manual)
        if not manual:
            self._load_array(key)
        self._emit_scores()

    def _load_array(self, key: str) -> None:
        preset = ABILITY_ARRAYS_BY_KEY.get(key)
        if preset is None:
            return
        tokens = tuple(enumerate(preset.scores))
        for assignment, (ability_key, field) in enumerate(self._array.items()):
            field.blockSignals(True)
            field.clear()
            for token, value in tokens:
                field.addItem(str(value), (token, value))
            field.setCurrentIndex(assignment)
            field._previous_token = tokens[assignment]
            field.blockSignals(False)

    def _array_assignment_changed(self, changed_key: str) -> None:
        if self._swapping:
            return
        changed = self._array[changed_key]
        token = changed.currentData()
        if not isinstance(token, tuple):
            return
        previous_token = getattr(changed, "_previous_token", None)
        if previous_token is None:
            previous_token = token
        duplicate = next(
            (
                field for key, field in self._array.items()
                if key != changed_key and field.currentData() == token
            ),
            None,
        )
        if duplicate is not None:
            self._swapping = True
            try:
                index = next(
                    (
                        item_index for item_index in range(duplicate.count())
                        if duplicate.itemData(item_index) == previous_token
                    ),
                    -1,
                )
                if index >= 0:
                    duplicate.setCurrentIndex(index)
                    duplicate._previous_token = previous_token
            finally:
                self._swapping = False
        changed._previous_token = token
        self._emit_scores()

    def _convert_to_manual(self) -> None:
        current = self.scores()
        self.method.setCurrentIndex(self.method.findData("manual"))
        for key, value in current.items():
            self._manual[key].blockSignals(True)
            self._manual[key].setValue(value)
            self._manual[key].blockSignals(False)
        self._emit_scores()

    def _emit_scores(self, *_args) -> None:
        self._update_totals()
        self.scoresChanged.emit(self.scores())

    def _update_totals(self) -> None:
        scores = self.scores()
        for key, base in scores.items():
            adjustment = self._racial_adjustments.get(key, 0)
            self._racial_labels[key].setText(f"{adjustment:+d}")
            self._final_labels[key].setText(str(base + adjustment))
        point_cost = ability_point_buy_cost(scores)
        self.cost.setText(
            "Point-buy total: outside the 7–18 purchase range"
            if point_cost is None
            else f"Point-buy total: {point_cost}"
        )
