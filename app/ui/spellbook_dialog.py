"""Wide, optional play interface for traditional spells and sphere effects."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.presentation import readable_tooltip
from app.spellbook import SpellBookEntry, SpellBookService
from app.ui.components import DebouncedCallback


class SpellBookDialog(QDialog):
    """Modeless spell browser backed only by the character's saved records."""

    resources_changed = Signal()
    CARDS_PER_ROW = 4

    def __init__(
        self, service: SpellBookService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Spell Book")
        self.resize(1420, 840)
        self.setMinimumSize(1080, 620)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._traditional_entries: tuple[SpellBookEntry, ...] = ()
        self._sphere_entries: tuple[SpellBookEntry, ...] = ()
        self._traditional_level_ceiling: int | None = None
        self.entry_cards: dict[str, QFrame] = {}
        self.cast_buttons: dict[str, QPushButton] = {}
        self.sphere_use_buttons: dict[str, dict[int, QPushButton]] = {}
        self.sphere_at_will_labels: dict[str, QLabel] = {}
        self.usage_labels: dict[str, QLabel] = {}
        self.usage_editors: dict[str, QSpinBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel("SPELL BOOK")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Find in this character's spellbook"))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Search spell name, description, or school…")
        from app.ui.search_navigation import install_search_shortcut
        self.search_shortcut = install_search_shortcut(self, self.search)
        search_row.addWidget(self.search, 1)
        layout.addLayout(search_row)

        self.status = QLabel("")
        self.status.setObjectName("mutedText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.traditional_scroll, self.traditional_canvas, self.traditional_layout = (
            self._book_page("traditionalSpellBookPage")
        )
        self.sphere_scroll, self.sphere_canvas, self.sphere_layout = self._book_page(
            "sphereSpellBookPage"
        )
        self.tabs.addTab(self.traditional_scroll, "Traditional Spells")
        self.tabs.addTab(self.sphere_scroll, "Magic Sphere Effects")
        layout.addWidget(self.tabs, 1)

        self.empty_book = QLabel(
            "This character currently has no traditional spells or Magic Sphere effects."
        )
        self.empty_book.setObjectName("mutedText")
        self.empty_book.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_book.setWordWrap(True)
        layout.addWidget(self.empty_book, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.close)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close)
        layout.addLayout(close_row)

        self.search_debounce = DebouncedCallback(self._render, 400, self)
        self.search.textChanged.connect(self.search_debounce.schedule)
        self.refresh()

    @staticmethod
    def _book_page(object_name: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName("spellBookScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        canvas = QWidget()
        canvas.setObjectName(object_name)
        page_layout = QVBoxLayout(canvas)
        page_layout.setContentsMargins(8, 8, 8, 14)
        page_layout.setSpacing(9)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(canvas)
        return scroll, canvas, page_layout

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                SpellBookDialog._clear_layout(child_layout)

    @staticmethod
    def _matches(entry: SpellBookEntry, query: str) -> bool:
        return not query or query in entry.searchable_text

    def refresh(self) -> None:
        """Reload current repository state without recreating the dialog."""

        traditional_entries = self.service.traditional_entries()
        self._traditional_level_ceiling = self.service.traditional_level_ceiling(
            traditional_entries
        )
        self._traditional_entries = tuple(
            entry
            for entry in traditional_entries
            if self._traditional_level_ceiling is not None
            and entry.level <= self._traditional_level_ceiling
        )
        self._sphere_entries = self.service.sphere_entries()
        traditional_visible = bool(self._traditional_entries)
        sphere_visible = bool(self._sphere_entries)
        current_page = self.tabs.currentWidget()
        traditional_index = self.tabs.indexOf(self.traditional_scroll)
        sphere_index = self.tabs.indexOf(self.sphere_scroll)
        self.tabs.setTabVisible(traditional_index, traditional_visible)
        self.tabs.setTabVisible(sphere_index, sphere_visible)
        self.tabs.setVisible(traditional_visible or sphere_visible)
        self.empty_book.setVisible(not (traditional_visible or sphere_visible))
        if current_page is self.sphere_scroll and sphere_visible:
            self.tabs.setCurrentWidget(self.sphere_scroll)
        elif current_page is self.traditional_scroll and traditional_visible:
            self.tabs.setCurrentWidget(self.traditional_scroll)
        elif sphere_visible:
            self.tabs.setCurrentWidget(self.sphere_scroll)
        elif traditional_visible:
            self.tabs.setCurrentWidget(self.traditional_scroll)
        self._render()

    def _render(self) -> None:
        query = self.search.text().strip().casefold()
        self.entry_cards.clear()
        self.cast_buttons.clear()
        self.sphere_use_buttons.clear()
        self.sphere_at_will_labels.clear()
        self.usage_labels.clear()
        self.usage_editors.clear()
        self._render_traditional(query)
        self._render_spheres(query)
        shown = sum(
            1
            for entry in (*self._traditional_entries, *self._sphere_entries)
            if self._matches(entry, query)
        )
        total = len(self._traditional_entries) + len(self._sphere_entries)
        if query:
            self.status.setText(f"{shown} of {total} character entries match the search.")
        elif not self.status.text() or "match" in self.status.text():
            self.status.setText(f"{total} spell and sphere entries are currently available in this book.")

    def _render_traditional(self, query: str) -> None:
        self._clear_layout(self.traditional_layout)
        if self._traditional_level_ceiling is None:
            self.traditional_layout.addStretch()
            return
        for level in range(self._traditional_level_ceiling + 1):
            entries = tuple(
                entry
                for entry in self._traditional_entries
                if entry.level == level and self._matches(entry, query)
            )
            if query and not entries:
                continue
            section, grid = self._section(f"LEVEL {level}")
            self.traditional_layout.addWidget(section)
            if not entries:
                empty = QLabel("No spells at this level.")
                empty.setObjectName("mutedText")
                grid.addWidget(empty, 0, 0, 1, self.CARDS_PER_ROW)
                continue
            for index, entry in enumerate(entries):
                grid.addWidget(
                    self._traditional_card(entry),
                    index // self.CARDS_PER_ROW,
                    index % self.CARDS_PER_ROW,
                )
        self.traditional_layout.addStretch()

    def _render_spheres(self, query: str) -> None:
        self._clear_layout(self.sphere_layout)
        groups = tuple(
            sorted({entry.group for entry in self._sphere_entries}, key=str.casefold)
        )
        for group in groups:
            entries = tuple(
                entry
                for entry in self._sphere_entries
                if entry.group == group and self._matches(entry, query)
            )
            if not entries:
                continue
            section, grid = self._section(f"{group.upper()} SPHERE")
            from app.ui.sphere_colors import style_sphere_group
            style_sphere_group(section.findChild(QLabel, 'spellBookSectionTitle'), group, 'magic', self)
            self.sphere_layout.addWidget(section)
            for index, entry in enumerate(entries):
                grid.addWidget(
                    self._sphere_card(entry),
                    index // self.CARDS_PER_ROW,
                    index % self.CARDS_PER_ROW,
                )
        if not groups or (query and not any(self._matches(item, query) for item in self._sphere_entries)):
            empty = QLabel("No sphere effects match the current character and search.")
            empty.setObjectName("mutedText")
            self.sphere_layout.addWidget(empty)
        self.sphere_layout.addStretch()

    @staticmethod
    def _section(title: str) -> tuple[QFrame, QGridLayout]:
        frame = QFrame()
        frame.setObjectName("spellBookSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("spellBookSectionTitle")
        layout.addWidget(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)
        for column in range(SpellBookDialog.CARDS_PER_ROW):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)
        return frame, grid

    def _base_card(self, entry: SpellBookEntry) -> tuple[QFrame, QVBoxLayout, str]:
        card = QFrame()
        card.setObjectName("spellBookEntry")
        card.setProperty("available", entry.can_cast if entry.resource_kind != "sphere" else entry.enabled)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card.setMinimumWidth(235)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(5)
        name = QLabel(entry.name)
        name.setObjectName("spellBookEntryName")
        name.setWordWrap(True)
        layout.addWidget(name)
        tooltip = readable_tooltip(entry.name, entry.description or "No description available.")
        for widget in (card, name):
            widget.setToolTip(tooltip)
        self.entry_cards[entry.key] = card
        return card, layout, tooltip

    def _traditional_card(self, entry: SpellBookEntry) -> QFrame:
        card, layout, tooltip = self._base_card(entry)
        usage = QLabel(entry.usage_text)
        usage.setObjectName("spellBookUsage")
        usage.setToolTip(tooltip)
        usage_row = QHBoxLayout()
        usage_row.addWidget(usage, 1)
        if entry.resource_kind in {"prepared", "spontaneous", "limited"}:
            editor = QSpinBox()
            editor.setObjectName("spellBookRemainingEditor")
            editor.setRange(0, entry.maximum)
            editor.setValue(entry.current)
            editor.setPrefix("Remaining: ")
            editor.setToolTip(
                "Edit the remaining daily amount directly. This never changes the prepared maximum."
            )
            editor.editingFinished.connect(
                partial(self._set_traditional_remaining, entry.key, editor)
            )
            usage_row.addWidget(editor)
            self.usage_editors[entry.key] = editor
        layout.addLayout(usage_row)
        buttons = QHBoxLayout()
        cast = QPushButton("Cast")
        cast.setObjectName("primaryButton")
        cast.setEnabled(entry.can_cast)
        cast.clicked.connect(partial(self._cast_traditional, entry.key))
        restore = QPushButton("Restore")
        restore.setEnabled(entry.can_restore)
        restore.setToolTip("Restore one expended copy or slot for manual correction.")
        restore.clicked.connect(partial(self._restore_traditional, entry.key))
        buttons.addWidget(cast)
        buttons.addWidget(restore)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.cast_buttons[entry.key] = cast
        self.usage_labels[entry.key] = usage
        return card

    def _sphere_card(self, entry: SpellBookEntry) -> QFrame:
        card, layout, tooltip = self._base_card(entry)
        usage = QLabel()
        usage.setObjectName("spellBookUsage")
        usage.setToolTip(tooltip)
        positive_costs = tuple(value for value in entry.costs if value > 0)
        if positive_costs:
            limited = (
                f" · {entry.limited_remaining} / {entry.limited_maximum} limited uses"
                if entry.limited_remaining is not None
                else ""
            )
            usage.setText(f"{entry.current} spell points available{limited}")
        else:
            usage.setText(
                entry.sphere_usage_text(0)
                if 0 in entry.costs
                else "No usable spell-point option"
            )
        layout.addWidget(usage)
        if positive_costs:
            controls = QHBoxLayout()
            buttons: dict[int, QPushButton] = {}
            if 0 in entry.costs:
                at_will = QLabel("At Will · 0 SP")
                at_will.setObjectName("spellBookAtWillOption")
                at_will.setToolTip(entry.sphere_usage_text(0))
                controls.addWidget(at_will)
                self.sphere_at_will_labels[entry.key] = at_will
            for cost in positive_costs:
                cast = QPushButton(f"Use · {cost} SP")
                cast.setObjectName("primaryButton")
                cast.setEnabled(entry.can_use_sphere(cost))
                cast.setToolTip(entry.sphere_usage_text(cost))
                cast.clicked.connect(
                    partial(self._use_sphere, entry.key, cost)
                )
                controls.addWidget(cast)
                buttons[cost] = cast
            controls.addStretch()
            layout.addLayout(controls)
            self.sphere_use_buttons[entry.key] = buttons
        self.usage_labels[entry.key] = usage
        return card

    def _cast_traditional(self, key: str) -> None:
        result = self.service.cast_traditional(key)
        self.status.setText(result.message)
        if result.changed:
            self.resources_changed.emit()
            self.refresh()

    def _restore_traditional(self, key: str) -> None:
        result = self.service.restore_traditional(key)
        self.status.setText(result.message)
        if result.changed:
            self.resources_changed.emit()
            self.refresh()

    def _set_traditional_remaining(self, key: str, editor: QSpinBox) -> None:
        result = self.service.set_traditional_remaining(key, editor.value())
        self.status.setText(result.message)
        if result.changed:
            self.resources_changed.emit()
            self.refresh()

    def _use_sphere(self, key: str, cost: int) -> None:
        result = self.service.use_sphere(key, cost)
        self.status.setText(result.message)
        if result.changed:
            self.resources_changed.emit()
            self.refresh()
