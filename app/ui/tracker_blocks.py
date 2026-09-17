from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.custom_trackers import ResolvedCustomTracker, display_number


class CustomTrackerBlock(QFrame):
    """A movable presentation block backed by one persistent tracker record."""

    def __init__(
        self,
        resolved: ResolvedCustomTracker,
        save_values: Callable[[int, float, float], None],
        edit_tracker: Callable[[int], None],
    ) -> None:
        super().__init__()
        self.setObjectName("customTrackerBlock")
        self._save_values = save_values
        self._edit_tracker = edit_tracker
        self._loading = False
        self.tracker_id = resolved.tracker.id
        self.tracker_key = resolved.tracker.key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(5)
        header = QHBoxLayout()
        self.name = QLabel()
        self.name.setObjectName("minorTitle")
        header.addWidget(self.name, 1)
        edit = QPushButton("Edit")
        edit.setMaximumWidth(58)
        edit.clicked.connect(lambda: self._edit_tracker(self.tracker_id))
        header.addWidget(edit)
        layout.addLayout(header)
        self.reference = QLabel()
        self.reference.setObjectName("mutedText")
        layout.addWidget(self.reference)

        values = QHBoxLayout()
        self.current_label = QLabel("CURRENT")
        self.current_label.setObjectName("mutedText")
        self.current = QDoubleSpinBox()
        self.current.setDecimals(2)
        self.current.setRange(-1_000_000_000, 1_000_000_000)
        self.current.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.maximum_label = QLabel()
        self.maximum_label.setObjectName("formulaTotal")
        self.temporary = QDoubleSpinBox()
        self.temporary.setDecimals(2)
        self.temporary.setRange(0, 1_000_000_000)
        self.temporary.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.temporary.setPrefix("Temp ")
        self.temporary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        values.addWidget(self.current_label)
        values.addWidget(self.current, 2)
        values.addWidget(self.maximum_label, 2)
        values.addWidget(self.temporary, 2)
        layout.addLayout(values)
        self.error = QLabel()
        self.error.setObjectName("warningText")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.current.editingFinished.connect(self._store)
        self.temporary.editingFinished.connect(self._store)
        self.update_from(resolved)

    def update_from(self, resolved: ResolvedCustomTracker) -> None:
        tracker = resolved.tracker
        self._loading = True
        try:
            self.tracker_id = tracker.id
            self.tracker_key = tracker.key
            self.name.setText(tracker.name.upper())
            self.reference.setText(f"trackers.{tracker.key}.value")
            calculated = tracker.tracker_type == "calculated"
            self.current_label.setText("VALUE" if calculated else "CURRENT")
            self.current.setReadOnly(calculated)
            self.current.setValue(
                float(resolved.value or 0) if calculated else tracker.current_value
            )
            self.maximum_label.setText(
                tracker.unit
                if calculated
                else f"/ {display_number(resolved.maximum)} {tracker.unit}".strip()
            )
            self.temporary.setVisible(tracker.tracker_type == "pool")
            self.temporary.setValue(tracker.temporary_value)
            self.error.setText(resolved.error)
            self.error.setVisible(bool(resolved.error))
            details = tracker.description or "No description entered."
            self.setToolTip(
                f"{tracker.name}\n\n{details}\n\nFormula: {tracker.formula or 'Manual maximum'}"
            )
        finally:
            self._loading = False

    def _store(self) -> None:
        if not self._loading and not self.current.isReadOnly():
            self._save_values(
                self.tracker_id, self.current.value(), self.temporary.value()
            )
