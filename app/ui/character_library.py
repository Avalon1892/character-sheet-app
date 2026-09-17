"""Card-based startup library for opening and creating characters.

The page deliberately consumes small immutable view models instead of reaching into
the repository itself.  That keeps it reusable if the application later gains a
different persistence layer or additional launcher metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import CharacterSummary, ClassLevel


@dataclass(frozen=True, slots=True)
class CharacterLibraryEntry:
    """The display-only character information required by the startup page."""

    character_id: int
    name: str
    class_names: tuple[str, ...]
    total_level: int
    character_type: str

    @property
    def class_label(self) -> str:
        return " / ".join(self.class_names) if self.class_names else "No class selected"

    @property
    def level_label(self) -> str:
        return f"Level {self.total_level}" if self.total_level else "Level not selected"

    @classmethod
    def from_character(
        cls,
        character: CharacterSummary,
        class_levels: list[ClassLevel] | tuple[ClassLevel, ...],
    ) -> "CharacterLibraryEntry":
        names: list[str] = []
        for row in class_levels:
            clean_name = row.class_name.strip()
            if clean_name and clean_name not in names:
                names.append(clean_name)
        return cls(
            character_id=character.id,
            name=character.name,
            class_names=tuple(names),
            total_level=sum(max(0, int(row.level)) for row in class_levels),
            character_type=character.character_type,
        )


class CharacterLibraryPage(QWidget):
    """Responsive startup screen containing character cards and a create card."""

    open_requested = Signal(int)
    create_requested = Signal()

    _MIN_CARD_WIDTH = 238

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("characterLibraryPage")
        self._entries: tuple[CharacterLibraryEntry, ...] = ()
        self._cards: list[QPushButton] = []
        self._column_count = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(34, 28, 34, 28)
        outer.setSpacing(18)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("CHARACTER LIBRARY")
        title.setObjectName("libraryTitle")
        subtitle = QLabel("Choose a character to continue, or begin a new adventure.")
        subtitle.setObjectName("librarySubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("characterLibraryScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.card_host = QWidget()
        self.card_host.setObjectName("characterLibraryCards")
        self.card_grid = QGridLayout(self.card_host)
        self.card_grid.setContentsMargins(2, 2, 14, 14)
        self.card_grid.setHorizontalSpacing(18)
        self.card_grid.setVerticalSpacing(18)
        self.card_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.card_host)
        outer.addWidget(self.scroll, 1)

        self.set_entries(())

    def set_entries(self, entries: list[CharacterLibraryEntry] | tuple[CharacterLibraryEntry, ...]) -> None:
        """Replace the page contents while retaining a deterministic card order."""

        self._entries = tuple(entries)
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        for entry in self._entries:
            card = QPushButton(
                f"{entry.name}\n\n{entry.class_label}\n{entry.level_label}"
            )
            card.setObjectName("characterLibraryCard")
            card.setProperty("characterId", entry.character_id)
            card.setProperty("characterType", entry.character_type)
            card.setAccessibleName(
                f"Open {entry.name}, {entry.class_label}, {entry.level_label}"
            )
            card.setToolTip(f"{entry.character_type} · {entry.class_label} · {entry.level_label}")
            card.clicked.connect(
                lambda _checked=False, character_id=entry.character_id:
                self.open_requested.emit(character_id)
            )
            self._prepare_card(card)
            self._cards.append(card)

        create = QPushButton("＋\n\nCreate New Character")
        create.setObjectName("createCharacterCard")
        create.setAccessibleName("Create New Character")
        create.clicked.connect(self.create_requested.emit)
        self._prepare_card(create)
        self._cards.append(create)
        self._reflow(force=True)

    def character_cards(self) -> tuple[QPushButton, ...]:
        """Return only existing-character cards (primarily useful for UI automation)."""

        return tuple(
            card
            for card in self._cards
            if card.property("characterId") is not None
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt virtual method
        super().resizeEvent(event)
        self._reflow()

    @staticmethod
    def _prepare_card(card: QPushButton) -> None:
        card.setMinimumSize(238, 170)
        card.setMaximumHeight(210)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

    def _reflow(self, *, force: bool = False) -> None:
        available = max(self._MIN_CARD_WIDTH, self.scroll.viewport().width() - 20)
        columns = max(1, min(4, available // (self._MIN_CARD_WIDTH + 18)))
        if not force and columns == self._column_count:
            return
        self._column_count = columns
        while self.card_grid.count():
            self.card_grid.takeAt(0)
        for index, card in enumerate(self._cards):
            self.card_grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            self.card_grid.setColumnStretch(column, 1)

