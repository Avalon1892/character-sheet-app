from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QTableWidget, QVBoxLayout, QWidget

from app.feature_registry import FeatureKind, feature_category
from app.ui.components import (
    DetailsPanel,
    TableColumn,
    action_menu_button,
    configure_columns,
    section_shell,
)
from app.ui.table_profiles import FEATURE_TABLE_COLUMNS


@dataclass(frozen=True, slots=True)
class SavedFeatureSection:
    kind: FeatureKind
    table_attribute: str
    columns: tuple[TableColumn, ...]
    add_label: str
    add_callback: str
    edit_callback: str
    toggle_callback: str
    remove_callback: str
    details_label: str
    toggle_label: str = "Activate / deactivate"
    maximum_height: int | None = None


SAVED_FEATURE_SECTIONS = {
    FeatureKind.FEAT: SavedFeatureSection(
        FeatureKind.FEAT,
        "feat_table",
        FEATURE_TABLE_COLUMNS[FeatureKind.FEAT],
        "+ Browse feats",
        "_add_feat",
        "_edit_feat",
        "_toggle_feat",
        "_remove_feat",
        "Feat",
    ),
    FeatureKind.TRAIT: SavedFeatureSection(
        FeatureKind.TRAIT,
        "trait_table",
        FEATURE_TABLE_COLUMNS[FeatureKind.TRAIT],
        "+ Browse traits",
        "_add_trait",
        "_edit_trait",
        "_toggle_trait",
        "_remove_trait",
        "Trait",
        "Enable / disable",
        205,
    ),
    FeatureKind.MARTIAL_TALENT: SavedFeatureSection(
        FeatureKind.MARTIAL_TALENT,
        "martial_talent_table",
        FEATURE_TABLE_COLUMNS[FeatureKind.MARTIAL_TALENT],
        "+ Browse talents",
        "_add_martial_talent",
        "_edit_martial_talent",
        "_toggle_martial_talent",
        "_remove_martial_talent",
        "Martial Talent",
    ),
}


def build_saved_feature_section(sheet, kind: FeatureKind) -> QWidget:
    spec = SAVED_FEATURE_SECTIONS[kind]
    category = feature_category(kind)
    section, layout, title = section_shell(category.plural.upper())
    section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    if kind == FeatureKind.TRAIT:
        title.setToolTip(
            "Characters normally have two traits. Hover for rules or select for details."
        )
    else:
        title.setToolTip(
            f"Hover a {category.singular.lower()} for its complete rules. "
            "Select it for the shared details panel."
        )

    table = QTableWidget()
    configure_columns(table, spec.columns)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.doubleClicked.connect(getattr(sheet, spec.edit_callback))
    table.itemSelectionChanged.connect(
        lambda: sheet._show_feature_details(spec.details_label)
    )
    table.cellClicked.connect(
        lambda _row, _column: sheet._show_feature_details(spec.details_label)
    )
    setattr(sheet, spec.table_attribute, table)
    layout.addWidget(table)

    actions = QHBoxLayout()
    add_button = QPushButton(spec.add_label)
    add_button.setObjectName("primaryButton")
    add_button.clicked.connect(getattr(sheet, spec.add_callback))
    menu_button = action_menu_button(
        (
            ("Edit selected", getattr(sheet, spec.edit_callback)),
            (spec.toggle_label, getattr(sheet, spec.toggle_callback)),
            ("", None),
            ("Remove selected", getattr(sheet, spec.remove_callback)),
        )
    )
    actions.addWidget(add_button)
    if kind == FeatureKind.MARTIAL_TALENT:
        sheet.open_martial_book_button = QPushButton("Open Martial Book")
        sheet.open_martial_book_button.setObjectName("primaryButton")
        sheet.open_martial_book_button.setToolTip(
            "Browse this character's owned martial talents by sphere and spend martial focus from the relevant talents."
        )
        sheet.open_martial_book_button.clicked.connect(sheet._open_martial_book)
        actions.addWidget(sheet.open_martial_book_button)
    actions.addWidget(menu_button)
    actions.addStretch()
    layout.addLayout(actions)
    if spec.maximum_height is not None:
        section.setMaximumHeight(spec.maximum_height)
    return section


def build_feature_details_section(sheet) -> QWidget:
    section, layout, _title = section_shell("SELECTED FEATURE DETAILS")
    sheet.feature_details = DetailsPanel("")
    layout.addWidget(sheet.feature_details, 1)
    return section
