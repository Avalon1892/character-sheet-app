"""Small, reusable controls for multi-choice and include/exclude filters."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton, QToolButton,
    QVBoxLayout, QWidget, QWidgetAction,
)


class MultiChoiceFilter(QToolButton):
    selectionChanged = Signal()

    def __init__(self, options, parent=None, *, empty_text="Any"):
        super().__init__(parent)
        self.empty_text = empty_text
        self.setText(empty_text)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        panel = QWidget(menu)
        layout = QVBoxLayout(panel)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find an option…")
        self.options = QListWidget()
        self.options.setMinimumSize(280, 240)
        self.options.setWordWrap(True)
        for option in options:
            item = QListWidgetItem(str(option), self.options)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
        clear = QPushButton("Clear selection (Any)")
        done = QPushButton("Done")
        for widget in (self.search, self.options, clear, done):
            layout.addWidget(widget)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        self.setMenu(menu)
        self.options.itemChanged.connect(self._changed)
        self.search.textChanged.connect(self._filter_options)
        clear.clicked.connect(self.clear)
        done.clicked.connect(menu.close)

    def selected_values(self):
        return tuple(self.options.item(i).text() for i in range(self.options.count())
                     if self.options.item(i).checkState() == Qt.CheckState.Checked)

    def set_selected_values(self, values):
        self.options.blockSignals(True)
        for i in range(self.options.count()):
            item = self.options.item(i)
            item.setCheckState(Qt.CheckState.Checked if item.text() in values else Qt.CheckState.Unchecked)
        self.options.blockSignals(False)
        self._changed()

    def clear(self):
        self.search.clear()
        self.set_selected_values(())

    def _changed(self, *_):
        values = self.selected_values()
        summary = values[0] if len(values) == 1 else f"{len(values)} selected"
        self.setText(self.empty_text if not values else summary if len(summary) <= 24 else summary[:21] + "…")
        self.setToolTip("Any of: " + "; ".join(values) if values else "No restriction. Select any number of options.")
        self.selectionChanged.emit()

    def _filter_options(self, text):
        for i in range(self.options.count()):
            item = self.options.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())


class CapabilityFilter(QPushButton):
    """Cycle Any → required check → excluded X using mouse or keyboard."""
    stateChanged = Signal(int)

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.state = 0
        self.clicked.connect(self._cycle)
        self.set_state(0)

    def set_state(self, state):
        if state not in (0, 1, -1):
            raise ValueError("Capability state must be any, required, or excluded")
        self.state = state
        symbol, meaning = {0: ("—", "Unrestricted"), 1: ("✓", "Required"), -1: ("✕", "Excluded")}[state]
        self.setText(f"{symbol} {self.label}")
        self.setAccessibleName(f"{self.label}: {meaning}")
        self.setToolTip(f"{meaning}. Click to cycle: — unrestricted → ✓ required → ✕ excluded.")
        self.stateChanged.emit(state)

    def _cycle(self):
        self.set_state({0: 1, 1: -1, -1: 0}[self.state])
