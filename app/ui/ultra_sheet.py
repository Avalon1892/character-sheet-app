"""Fixed, responsive, capability-driven Pathfinder play sheet.

Unlike the customizable presentation, Ultra has no geometry editor and stores
no layout state.  It consumes the same rules snapshot and discovers optional
class-system panels through :mod:`app.ui.ultra_modules`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import partial
from typing import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.animal_companion_rules import (
    calculate_companion_statistics,
    companion_entry,
    companion_progression,
    resolve_companion_grant,
)
from app.class_capabilities import ClassCapabilities, resolve_class_capabilities
from app.class_feature_rules import resolve_class_features
from app.archetype_rules import archetype_choice_selections_from_records
from app.content import archetype_entry, class_entry, entries
from app.database import CharacterRepository
from app.item_effects import effective_item_state, preferred_item_state
from app.item_enchantments import item_market_price
from app.models import (
    ABILITIES,
    AbilityScoreIncreaseAllocation,
    HitPoints,
    MartialFocus,
    ProdigySequence,
)
from app.services.sheet_presentation import (
    CharacterSheetSnapshot,
    build_character_sheet_snapshot,
)
from app.services.character_calculations import CharacterCalculationService
from app.spell_rules import spell_record_presentation
from app.ui.components import forward_editor_wheel_to_page, numeric_field
from app.ui.ultra_modules import (
    ULTRA_MODULES,
    UltraModuleDescriptor,
    UltraModuleRegistry,
)


@dataclass(frozen=True, slots=True)
class UltraSheetContext:
    repository: CharacterRepository
    character_id: int
    snapshot: CharacterSheetSnapshot
    class_capabilities: ClassCapabilities
    capabilities: frozenset[str]
    movement: dict[str, int | str]
    sequence: ProdigySequence
    archetypes_by_level: dict[int, tuple[str, ...]]
    companion_grant: object


def _resolved_features_by_class(
    repository: CharacterRepository,
    character_id: int,
    snapshot: CharacterSheetSnapshot,
    archetypes_by_level: dict[int, tuple[str, ...]],
) -> dict[int, tuple[object, ...]]:
    selections = repository.list_class_feature_selections(character_id)
    selected_option_keys = {selection.feature_key for selection in selections}
    result: dict[int, tuple[object, ...]] = {}
    for class_level in snapshot.classes:
        definition = class_entry(class_level.preset_key)
        if definition is None:
            continue
        archetypes = tuple(
            entry
            for key in archetypes_by_level.get(class_level.id, ())
            if (entry := archetype_entry(key)) is not None
        )
        result[class_level.id] = resolve_class_features(
            definition.get("features", ()),
            archetypes,
            class_level.level,
            class_level.class_name,
            selected_optional_feature_keys=selected_option_keys,
            selected_archetype_choices=archetype_choice_selections_from_records(
                selections, class_level.id
            ),
        )
    return result


def build_ultra_context(
    repository: CharacterRepository, character_id: int
) -> UltraSheetContext:
    snapshot = build_character_sheet_snapshot(repository, character_id)
    archetypes_by_level = {
        int(key): tuple(values)
        for key, values in repository.list_class_archetype_keys(character_id).items()
    }
    selected_keys = {key for values in archetypes_by_level.values() for key in values}
    archetypes = {
        key: definition
        for key in selected_keys
        if (definition := archetype_entry(key)) is not None
    }
    classes = {str(value.get("key")): value for value in entries("classes")}
    capabilities = resolve_class_capabilities(
        snapshot.classes, archetypes_by_level, archetypes, classes
    )
    features_by_class = _resolved_features_by_class(
        repository, character_id, snapshot, archetypes_by_level
    )
    companion_grant = resolve_companion_grant(
        snapshot.classes,
        features_by_class,
        snapshot.martial_talents,
        repository.list_skill_states(character_id),
        repository.list_class_feature_selections(character_id),
    )
    tokens = set(capabilities.active_tokens)
    tokens.add("universal")
    if capabilities.any_spellcasting:
        tokens.add("spellcasting")
    if companion_grant.available:
        tokens.add("companion")
    return UltraSheetContext(
        repository,
        character_id,
        snapshot,
        capabilities,
        frozenset(tokens),
        dict(CharacterCalculationService(repository, character_id).movement_results()),
        repository.get_prodigy_sequence(character_id),
        archetypes_by_level,
        companion_grant,
    )


class UltraCard(QFrame):
    """Shared visual shell used by all fixed Ultra modules."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ultraCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(8, 8, 8, 8)
        self.root.setSpacing(6)
        heading = QLabel(title.upper())
        heading.setObjectName("ultraCardTitle")
        self.root.addWidget(heading)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        raise NotImplementedError


def _table(headers: tuple[str, ...], *, stretch: int = 0) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setObjectName("ultraTable")
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.horizontalHeader().setStretchLastSection(False)
    from PySide6.QtWidgets import QHeaderView

    for column in range(len(headers)):
        table.horizontalHeader().setSectionResizeMode(
            column,
            QHeaderView.ResizeMode.Stretch
            if column == stretch
            else QHeaderView.ResizeMode.ResizeToContents,
        )
    return table


def _fit_table(table: QTableWidget, *, minimum: int = 2, maximum: int = 14) -> None:
    rows = max(minimum, min(maximum, table.rowCount()))
    header = table.horizontalHeader().sizeHint().height()
    table.setMinimumHeight(header + rows * 25 + 6)
    table.setMaximumHeight(header + rows * 25 + 6)


def _item(
    value: object,
    *,
    tooltip: str = "",
    center: bool = False,
    user_data: object | None = None,
) -> QTableWidgetItem:
    cell = QTableWidgetItem(str(value))
    if tooltip:
        cell.setToolTip(tooltip)
    if center:
        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if user_data is not None:
        cell.setData(Qt.ItemDataRole.UserRole, user_data)
    return cell


class UltraResponsivePage(QScrollArea):
    """Reflows modules into one, two, or three readable columns."""

    def __init__(
        self,
        modules: tuple[tuple[UltraModuleDescriptor, QWidget], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ultraScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.canvas = QWidget()
        self.canvas.setObjectName("ultraPage")
        self.root = QVBoxLayout(self.canvas)
        self.root.setContentsMargins(12, 12, 12, 22)
        self.root.setSpacing(10)
        self.modules = modules
        self.full_modules = tuple(value for value in modules if value[0].full_width)
        self.column_modules = tuple(value for value in modules if not value[0].full_width)
        for _descriptor, widget in self.full_modules:
            self.root.addWidget(widget)
        self.column_row = QHBoxLayout()
        self.column_row.setSpacing(10)
        self.columns: list[QVBoxLayout] = []
        self.column_hosts: list[QWidget] = []
        for _index in range(3):
            host = QWidget()
            host.setObjectName("ultraColumn")
            column = QVBoxLayout(host)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(10)
            self.column_hosts.append(host)
            self.columns.append(column)
            self.column_row.addWidget(host, 1)
        self.root.addLayout(self.column_row)
        self.root.addStretch()
        self.setWidget(self.canvas)
        self._column_count = 0
        self._requested_column_count = 2
        self._capabilities: frozenset[str] | None = None
        self._reflow(2)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = self.viewport().width()
        columns = 1 if width < 850 else 2 if width < 1380 else 3
        self._reflow(columns)

    def _reflow(self, requested_count: int, *, force: bool = False) -> None:
        self._requested_column_count = requested_count
        active = tuple(
            value
            for value in self.column_modules
            if self._capabilities is None
            or value[0].is_available(self._capabilities)
        )
        active_keys = {descriptor.key.casefold() for descriptor, _widget in active}
        inactive = tuple(
            value
            for value in self.column_modules
            if value[0].key.casefold() not in active_keys
        )
        count = max(1, min(requested_count, len(active) or 1))
        if count == self._column_count and not force:
            return
        self._column_count = count
        for column in self.columns:
            while column.count():
                column.takeAt(0)
        for index, host in enumerate(self.column_hosts):
            host.setVisible(index < count)
        heights = [0] * count
        for descriptor, widget in active:
            column = min(range(count), key=lambda index: heights[index])
            self.columns[column].addWidget(widget)
            heights[column] += descriptor.estimated_height
        # Keep inactive widgets owned by a layout so capability changes can
        # reveal them without recreating panels or losing their state.
        for _descriptor, widget in inactive:
            self.columns[-1].addWidget(widget)
        for index in range(count):
            self.columns[index].addStretch()

    def apply_capabilities(self, capabilities: frozenset[str]) -> None:
        self._capabilities = capabilities
        for descriptor, widget in self.modules:
            widget.setVisible(descriptor.is_available(capabilities))
        self._reflow(self._requested_column_count, force=True)


class UltraStatusHeader(QFrame):
    full_rest_requested = Signal()

    def __init__(self, owner: "UltraSheetWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.context: UltraSheetContext | None = None
        self._loading = False
        self.setObjectName("ultraStatusHeader")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(10)
        identity = QVBoxLayout()
        self.name = QLabel("No character")
        self.name.setObjectName("ultraCharacterName")
        self.name.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.classes = QLabel("—")
        self.classes.setObjectName("ultraCharacterClasses")
        self.classes.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        identity.addWidget(self.name)
        identity.addWidget(self.classes)
        top.addLayout(identity, 2)

        self.stats = QHBoxLayout()
        self.stats.setSpacing(6)
        self.stat_labels: dict[str, QLabel] = {}
        for key, label in (
            ("initiative", "INIT"), ("ac", "AC"), ("touch_ac", "TOUCH"),
            ("flat_footed_ac", "FLAT"), ("fortitude", "FORT"),
            ("reflex", "REF"), ("will", "WILL"), ("land_speed", "SPEED"),
        ):
            chip = QFrame(); chip.setObjectName("ultraStatusChip")
            chip_layout = QVBoxLayout(chip); chip_layout.setContentsMargins(6, 3, 6, 3); chip_layout.setSpacing(0)
            title = QLabel(label); title.setObjectName("ultraStatusLabel"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—"); value.setObjectName("ultraStatusValue"); value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip_layout.addWidget(title); chip_layout.addWidget(value)
            self.stats.addWidget(chip)
            self.stat_labels[key] = value

        hp = QFrame(); hp.setObjectName("ultraResourceChip")
        hp_layout = QVBoxLayout(hp); hp_layout.setContentsMargins(7, 3, 7, 3); hp_layout.setSpacing(1)
        hp_title = QLabel("HIT POINTS"); hp_title.setObjectName("ultraStatusLabel"); hp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hp_row = QHBoxLayout(); hp_row.setSpacing(3)
        self.hp_current = numeric_field(-9999, 99999, width=58)
        self.hp_max = QLabel("/ 0"); self.hp_max.setObjectName("ultraResourceTotal")
        hp_row.addWidget(self.hp_current); hp_row.addWidget(self.hp_max)
        hp_layout.addWidget(hp_title); hp_layout.addLayout(hp_row)
        self.hp_current.valueChanged.connect(self._save_hp)
        top.addWidget(hp)

        self.spell_points = QFrame(); self.spell_points.setObjectName("ultraResourceChip")
        sp_layout = QVBoxLayout(self.spell_points); sp_layout.setContentsMargins(7, 3, 7, 3); sp_layout.setSpacing(1)
        sp_title = QLabel("SPELL POINTS"); sp_title.setObjectName("ultraStatusLabel"); sp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sp_row = QHBoxLayout(); sp_row.setSpacing(3)
        self.sp_current = numeric_field(0, 99999, width=58)
        self.sp_max = QLabel("/ 0"); self.sp_max.setObjectName("ultraResourceTotal")
        sp_row.addWidget(self.sp_current); sp_row.addWidget(self.sp_max)
        sp_layout.addWidget(sp_title); sp_layout.addLayout(sp_row)
        self.sp_current.valueChanged.connect(self._save_spell_points)
        top.addWidget(self.spell_points)

        rest = QPushButton("Full Rest")
        rest.setObjectName("primaryButton")
        rest.clicked.connect(self.full_rest_requested)
        top.addWidget(rest)
        root.addLayout(top)
        root.addLayout(self.stats)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.context = context
        sheet = context.snapshot
        self._loading = True
        try:
            self.name.setText(sheet.summary.name)
            self.classes.setText(
                "  ·  ".join(f"{row.class_name} {row.level}" for row in sheet.classes)
                or "No class levels"
            )
            for key, label in self.stat_labels.items():
                if key == "land_speed":
                    label.setText(f"{int(context.movement[key])} ft")
                else:
                    value = sheet.combat[key].total
                    label.setText(str(value) if key in {"ac", "touch_ac", "flat_footed_ac"} else f"{value:+d}")
            self.hp_current.setValue(sheet.hit_points.current)
            self.hp_max.setText(f"/ {sheet.displayed_hit_point_maximum}")
            self.sp_current.setValue(sheet.casting_profile.spell_points_current)
            self.sp_max.setText(f"/ {sheet.casting.spell_points_maximum}")
            self.spell_points.setVisible(context.class_capabilities.magic)
        finally:
            self._loading = False

    def _save_hp(self, value: int) -> None:
        if self._loading or self.context is None:
            return
        hp = self.context.repository.get_hit_points(self.context.character_id)
        self.context.repository.update_hit_points(replace(hp, current=value))

    def _save_spell_points(self, value: int) -> None:
        if self._loading or self.context is None:
            return
        profile = self.context.repository.get_casting_profile(self.context.character_id)
        self.context.repository.update_casting_profile(
            replace(profile, spell_points_current=value)
        )


class UltraCorePanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("At-a-glance statistics")
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.abilities: dict[str, tuple[QLabel, QLabel]] = {}
        for column, (key, _name, abbreviation) in enumerate(ABILITIES):
            card = QFrame(); card.setObjectName("ultraStatTile")
            card_layout = QVBoxLayout(card); card_layout.setContentsMargins(5, 3, 5, 3); card_layout.setSpacing(0)
            title = QLabel(abbreviation); title.setObjectName("ultraStatLabel"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            score = QLabel("10"); score.setObjectName("ultraStatValue"); score.setAlignment(Qt.AlignmentFlag.AlignCenter)
            modifier = QLabel("+0"); modifier.setObjectName("ultraStatDetail"); modifier.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(title); card_layout.addWidget(score); card_layout.addWidget(modifier)
            grid.addWidget(card, 0, column)
            self.abilities[key] = (score, modifier)
        self.combat: dict[str, QLabel] = {}
        for column, (key, caption) in enumerate((
            ("ac", "ARMOR CLASS"), ("touch_ac", "TOUCH"),
            ("flat_footed_ac", "FLAT-FOOTED"), ("initiative", "INITIATIVE"),
            ("fortitude", "FORTITUDE"), ("reflex", "REFLEX"),
            ("will", "WILL"), ("cmb", "CMB"), ("cmd", "CMD"),
        )):
            card = QFrame(); card.setObjectName("ultraStatTile")
            card_layout = QVBoxLayout(card); card_layout.setContentsMargins(5, 3, 5, 3); card_layout.setSpacing(0)
            title = QLabel(caption); title.setObjectName("ultraStatLabel"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—"); value.setObjectName("ultraStatValue"); value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(title); card_layout.addWidget(value)
            grid.addWidget(card, 1 + column // 5, column % 5)
            self.combat[key] = value
        for column in range(6):
            grid.setColumnStretch(column, 1)
        self.root.addLayout(grid)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        for key, (score, modifier) in self.abilities.items():
            result = context.snapshot.abilities[key]
            score.setText(str(result.total))
            modifier.setText(f"{result.ability_modifier:+d}")
            tooltip = "\n".join(
                f"{entry.source}: {entry.value:+d} {entry.bonus_type}"
                for entry in result.contributions
                if entry.applied
            )
            score.setToolTip(tooltip or "Base ability score")
            modifier.setToolTip(score.toolTip())
        for key, label in self.combat.items():
            result = context.snapshot.combat[key]
            label.setText(
                str(result.total)
                if key in {"ac", "touch_ac", "flat_footed_ac", "cmd"}
                else f"{result.total:+d}"
            )


class UltraAttacksPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Attacks")
        self.table = _table(("Attack", "Bonus", "Damage", "Critical", "Type"), stretch=0)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.table.setRowCount(0)
        for attack in context.snapshot.attacks:
            row = self.table.rowCount(); self.table.insertRow(row)
            tooltip = attack.record.notes or attack.result.damage_display
            values = (
                attack.record.name,
                f"{attack.result.attack_bonus:+d}",
                attack.result.damage_display,
                attack.record.critical,
                attack.record.attack_type,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, _item(value, tooltip=tooltip, center=column > 0))
        _fit_table(self.table, minimum=3, maximum=8)


class UltraSkillsPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Skills")
        self.table = _table(("Skill", "Class", "Total", "Ability", "Ranks", "Misc"), stretch=0)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.table.setRowCount(0)
        for skill in context.snapshot.skills:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (
                skill.definition.name,
                "■" if skill.state.class_skill else "□",
                f"{skill.result.total:+d}",
                skill.ability[:3].upper(),
                skill.state.ranks,
                f"{skill.state.misc_bonus:+d}" if skill.state.misc_bonus else "—",
            )
            tooltip = f"{skill.definition.name} · governed by {skill.ability.title()}"
            for column, value in enumerate(values):
                self.table.setItem(row, column, _item(value, tooltip=tooltip, center=column > 0))
        # Ultra intentionally shows the complete skill list without an internal
        # scrollbar; the page itself remains the only scroll surface.
        _fit_table(self.table, minimum=len(context.snapshot.skills), maximum=len(context.snapshot.skills))


class UltraMovementPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Movement")
        grid = QGridLayout(); grid.setSpacing(5)
        self.values: dict[str, QLabel] = {}
        for index, (key, label) in enumerate((
            ("land_speed", "Land"), ("armor_speed", "Armor"),
            ("fly_speed", "Fly"), ("swim_speed", "Swim"),
            ("climb_speed", "Climb"), ("burrow_speed", "Burrow"),
            ("teleport_speed", "Teleport"),
        )):
            tile = QFrame(); tile.setObjectName("ultraStatTile")
            box = QVBoxLayout(tile); box.setContentsMargins(5, 3, 5, 3); box.setSpacing(0)
            title = QLabel(label.upper()); title.setObjectName("ultraStatLabel"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—"); value.setObjectName("ultraStatValue"); value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(title); box.addWidget(value)
            grid.addWidget(tile, index // 4, index % 4)
            self.values[key] = value
        self.root.addLayout(grid)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        for key, label in self.values.items():
            value = int(context.movement.get(key, 0) or 0)
            text = f"{value} ft" if value else "—"
            if key == "fly_speed" and value and context.movement.get("fly_maneuverability"):
                text += f" · {context.movement['fly_maneuverability']}"
            label.setText(text)


class UltraConditionsPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Conditions & effects")
        self.table = _table(("Condition", "Effect"), stretch=1)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.table.setRowCount(0)
        for condition in context.snapshot.conditions:
            if not bool(getattr(condition, "active", True)):
                continue
            row = self.table.rowCount(); self.table.insertRow(row)
            effect = getattr(condition, "notes", "") or "Active"
            self.table.setItem(row, 0, _item(condition.name, tooltip=effect))
            self.table.setItem(row, 1, _item(effect, tooltip=effect))
        _fit_table(self.table, minimum=2, maximum=5)


class UltraFocusPanel(UltraCard):
    def __init__(self, owner: "UltraSheetWidget") -> None:
        super().__init__("Martial Focus")
        self.owner = owner
        self.context: UltraSheetContext | None = None
        row = QHBoxLayout()
        self.status = QLabel("FOCUSED"); self.status.setObjectName("focusReady"); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value = QLabel("1 / 1"); self.value.setObjectName("ultraResourceTotal"); self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spend = QPushButton("Spend"); spend.clicked.connect(self._spend)
        regain = QPushButton("Regain"); regain.setObjectName("primaryButton"); regain.clicked.connect(self._regain)
        row.addWidget(self.status, 2); row.addWidget(self.value); row.addWidget(spend); row.addWidget(regain)
        self.root.addLayout(row)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.context = context
        focus = context.snapshot.martial_focus
        self.value.setText(f"{focus.current} / {focus.maximum}")
        ready = focus.current > 0
        self.status.setText("FOCUSED" if ready else "EXPENDED")
        self.status.setObjectName("focusReady" if ready else "focusSpent")
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.status.setToolTip(focus.recovery_method + (f"\n{focus.notes}" if focus.notes else ""))

    def _spend(self) -> None:
        if self.context is None:
            return
        focus = self.context.repository.get_martial_focus(self.context.character_id)
        if focus.current:
            self.context.repository.update_martial_focus(replace(focus, current=focus.current - 1))
            self.owner.refresh_all()

    def _regain(self) -> None:
        if self.context is None:
            return
        focus = self.context.repository.get_martial_focus(self.context.character_id)
        self.context.repository.update_martial_focus(replace(focus, current=focus.maximum))
        self.owner.refresh_all()


class UltraSequencePanel(UltraCard):
    def __init__(self, owner: "UltraSheetWidget") -> None:
        super().__init__("Prodigy Sequence")
        self.owner = owner
        self.context: UltraSheetContext | None = None
        row = QHBoxLayout()
        self.status = QLabel("INACTIVE"); self.status.setObjectName("sequenceInactive"); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter = QLabel("0 / 4 LINKS"); self.counter.setObjectName("sequenceCounter"); self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add = QPushButton("+ Link"); add.setObjectName("primaryButton"); add.clicked.connect(self._add_link)
        end = QPushButton("End"); end.clicked.connect(self._end)
        row.addWidget(self.status); row.addWidget(self.counter); row.addStretch(); row.addWidget(add); row.addWidget(end)
        self.root.addLayout(row)
        self.imbue = QLabel("No imbue selected"); self.imbue.setObjectName("ultraHint"); self.root.addWidget(self.imbue)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.context = context
        sequence = context.sequence
        self.counter.setText(f"{sequence.current} / {sequence.maximum} LINKS")
        active = bool(sequence.active and sequence.current > 0)
        self.status.setText("ACTIVE" if active else "INACTIVE")
        self.status.setObjectName("sequenceActive" if active else "sequenceInactive")
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.imbue.setText(
            f"Active imbue: {sequence.imbue_key.replace('_', ' ').title()}"
            if active and sequence.imbue_key else "No active imbue"
        )

    def _add_link(self) -> None:
        if self.context is None:
            return
        value = self.context.repository.get_prodigy_sequence(self.context.character_id)
        if value.current >= value.maximum:
            return
        self.context.repository.update_prodigy_sequence(
            replace(value, active=True, current=value.current + 1)
        )
        self.owner.refresh_all()

    def _end(self) -> None:
        if self.context is None:
            return
        value = self.context.repository.get_prodigy_sequence(self.context.character_id)
        self.context.repository.update_prodigy_sequence(replace(value, active=False, current=0))
        self.owner.refresh_all()


class UltraClassFeaturesPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Special abilities")
        self.table = _table(("Level", "Ability", "Source"), stretch=1)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.table.setRowCount(0)
        for feature in context.snapshot.class_features:
            row = self.table.rowCount(); self.table.insertRow(row)
            tooltip = f"{feature.class_name} · level {feature.level}\n\n{feature.description}"
            self.table.setItem(row, 0, _item(feature.level, tooltip=tooltip, center=True))
            self.table.setItem(row, 1, _item(feature.name, tooltip=tooltip))
            self.table.setItem(row, 2, _item(feature.class_name, tooltip=tooltip))
        _fit_table(self.table, minimum=4, maximum=14)


class UltraFeaturePanel(UltraCard):
    def __init__(
        self,
        owner: object,
        title: str,
        attribute: str,
        predicate: Callable[[object], bool] | None = None,
    ) -> None:
        super().__init__(title)
        self.attribute = attribute
        self.predicate = predicate or (lambda _value: True)
        self.table = _table(("Name", "Group", "Summary"), stretch=2)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        values = tuple(getattr(context.snapshot, self.attribute))
        self.table.setRowCount(0)
        for feature in values:
            if (
                not bool(getattr(feature, "enabled", True))
                or not self.predicate(feature)
            ):
                continue
            row = self.table.rowCount(); self.table.insertRow(row)
            group = (
                getattr(feature, "sphere", "")
                or getattr(feature, "school_or_sphere", "")
                or getattr(feature, "catalog_category", "")
                or "—"
            )
            description = str(getattr(feature, "notes", "") or "")
            summary = description.split("\n", 1)[0][:180] or "Hover for rules"
            self.table.setItem(row, 0, _item(feature.name, tooltip=description))
            self.table.setItem(row, 1, _item(group, tooltip=description))
            self.table.setItem(row, 2, _item(summary, tooltip=description))
        _fit_table(self.table, minimum=3, maximum=12)


class UltraFeatTraitPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Feats & traits")
        self.table = _table(("Type", "Name", "Summary"), stretch=2)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.table.setRowCount(0)
        for kind, values in (("Feat", context.snapshot.feats), ("Trait", context.snapshot.traits)):
            for feature in values:
                if not bool(getattr(feature, "enabled", True)):
                    continue
                row = self.table.rowCount(); self.table.insertRow(row)
                description = str(getattr(feature, "notes", "") or "")
                summary = description.split("\n", 1)[0][:180] or "Hover for rules"
                self.table.setItem(row, 0, _item(kind, tooltip=description))
                self.table.setItem(row, 1, _item(feature.name, tooltip=description))
                self.table.setItem(row, 2, _item(summary, tooltip=description))
        _fit_table(self.table, minimum=4, maximum=12)


class UltraEquipmentPanel(UltraCard):
    def __init__(self, owner: "UltraSheetWidget") -> None:
        super().__init__("Inventory")
        self.owner = owner
        self.context: UltraSheetContext | None = None
        self.table = _table(("Item", "State", "Qty", "Weight", "Value"), stretch=0)
        self.root.addWidget(self.table)
        actions = QHBoxLayout()
        wear = QPushButton("Wear / wield"); wear.setObjectName("primaryButton"); wear.clicked.connect(self._wear)
        remove = QPushButton("Remove from use"); remove.clicked.connect(self._remove)
        actions.addWidget(wear); actions.addWidget(remove); actions.addStretch()
        self.root.addLayout(actions)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.context = context
        self.table.setRowCount(0)
        enchantments = context.repository.list_item_enchantments(
            context.character_id
        )
        for equipment in context.snapshot.equipment:
            row = self.table.rowCount(); self.table.insertRow(row)
            state = effective_item_state(equipment)
            tooltip = equipment.notes or equipment.name
            values = (
                equipment.name, state.title(), equipment.quantity,
                f"{equipment.weight * equipment.quantity:g} lb",
                f"{item_market_price(equipment, enchantments) * equipment.quantity:g} gp",
            )
            for column, value in enumerate(values):
                self.table.setItem(
                    row, column,
                    _item(value, tooltip=tooltip, center=column > 0, user_data=equipment.id),
                )
        _fit_table(self.table, minimum=6, maximum=16)

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return int(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def _wear(self) -> None:
        if self.context is None or (item_id := self._selected_id()) is None:
            return
        item = next((value for value in self.context.snapshot.equipment if value.id == item_id), None)
        if item is None or item.quantity <= 0 or effective_item_state(item) == preferred_item_state(item):
            return
        self.context.repository.set_equipment_equipped(self.context.character_id, item.id, True)
        self.owner.refresh_all()

    def _remove(self) -> None:
        if self.context is None or (item_id := self._selected_id()) is None:
            return
        item = next((value for value in self.context.snapshot.equipment if value.id == item_id), None)
        if item is None or effective_item_state(item) == "stored":
            return
        self.context.repository.set_equipment_state(self.context.character_id, item.id, "stored")
        self.owner.refresh_all()


class UltraWornLoadPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Worn items, load & currency")
        self.summary = QLabel("—"); self.summary.setObjectName("ultraHint"); self.summary.setWordWrap(True)
        self.root.addWidget(self.summary)
        self.table = _table(("Slot / resource", "Value"), stretch=1)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        sheet = context.snapshot
        worn = [
            item for item in sheet.equipment
            if effective_item_state(item) in {"worn", "wielded", "armor", "shield"}
        ]
        self.summary.setText(
            f"{sheet.total_weight:g} lb carried · light {sheet.carrying_capacity.light:g} lb · "
            f"medium {sheet.carrying_capacity.medium:g} lb · heavy {sheet.carrying_capacity.heavy:g} lb"
        )
        self.table.setRowCount(0)
        for item in worn:
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, _item(item.slot or effective_item_state(item).title(), tooltip=item.notes))
            self.table.setItem(row, 1, _item(item.name, tooltip=item.notes))
        purse = sheet.currency
        for label, value in (("Copper", purse.copper), ("Silver", purse.silver), ("Gold", purse.gold), ("Platinum", purse.platinum)):
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, _item(label))
            self.table.setItem(row, 1, _item(value))
        _fit_table(self.table, minimum=6, maximum=16)


class UltraCastingPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Casting summary")
        grid = QGridLayout(); grid.setSpacing(5)
        self.values: dict[str, QLabel] = {}
        for index, (key, title) in enumerate((
            ("caster_level", "Caster Level"), ("save_dc", "Sphere DC"),
            ("magic_skill_bonus", "MSB"), ("magic_skill_defense", "MSD"),
            ("casting_ability_modifier", "CAM"), ("concentration_bonus", "Concentration"),
            ("spell_points", "Spell Points"),
        )):
            tile = QFrame(); tile.setObjectName("ultraStatTile")
            box = QVBoxLayout(tile); box.setContentsMargins(5, 3, 5, 3); box.setSpacing(0)
            caption = QLabel(title.upper()); caption.setObjectName("ultraStatLabel"); caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—"); value.setObjectName("ultraStatValue"); value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(caption); box.addWidget(value)
            grid.addWidget(tile, index // 4, index % 4)
            self.values[key] = value
        self.root.addLayout(grid)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        value = context.snapshot.casting
        mapping = {
            "caster_level": value.caster_level,
            "save_dc": value.save_dc,
            "magic_skill_bonus": f"{value.magic_skill_bonus:+d}",
            "magic_skill_defense": value.magic_skill_defense,
            "casting_ability_modifier": f"{value.casting_ability_modifier:+d}",
            "concentration_bonus": f"{value.concentration_bonus:+d}",
            "spell_points": f"{context.snapshot.casting_profile.spell_points_current} / {value.spell_points_maximum}",
        }
        for key, label in self.values.items():
            label.setText(str(mapping[key]))


class UltraTraditionalSpellsPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Spells known & prepared")
        self.table = _table(("Level", "Spell", "Prepared", "Used"), stretch=1)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        prepared = context.repository.list_prepared_spells(context.character_id)
        prepared_by_spell: dict[int, tuple[int, int]] = {}
        for record in prepared:
            spell_id = int(getattr(record, "known_spell_id", 0) or 0)
            maximum, used = prepared_by_spell.get(spell_id, (0, 0))
            prepared_by_spell[spell_id] = (
                maximum + int(getattr(record, "prepared_count", 0) or 0),
                used + int(getattr(record, "used_count", 0) or 0),
            )
        self.table.setRowCount(0)
        for spell in context.snapshot.spells:
            if spell.system == "Sphere":
                continue
            row = self.table.rowCount(); self.table.insertRow(row)
            maximum, used = prepared_by_spell.get(spell.id, (0, 0))
            for column, value in enumerate((spell.level, spell.name, maximum or "—", used or "—")):
                self.table.setItem(row, column, _item(value, tooltip=spell.notes, center=column != 1))
        _fit_table(self.table, minimum=5, maximum=16)


class UltraSphereMagicPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Magic spheres")
        self.table = _table(("Sphere", "Talent / effect", "Spell cost", "Action", "Range"), stretch=1)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        sphere_spells = tuple(spell for spell in context.snapshot.spells if spell.system == "Sphere")
        self.table.setRowCount(0)
        for spell in sorted(sphere_spells, key=lambda value: (value.school_or_sphere.casefold(), value.name.casefold())):
            projection = spell_record_presentation(spell, sphere_spells)
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (projection.sphere, projection.name, projection.cost, projection.action, projection.range)
            for column, value in enumerate(values):
                self.table.setItem(row, column, _item(value, tooltip=projection.description, center=column in {2, 3, 4}))
        _fit_table(self.table, minimum=6, maximum=18)


class UltraCharacterBuildPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Character build & class progression")
        identity = QGridLayout(); identity.setHorizontalSpacing(8); identity.setVerticalSpacing(3)
        self.identity: dict[str, QLabel] = {}
        for index, (key, title) in enumerate((
            ("race", "Race"), ("alignment", "Alignment"), ("deity", "Deity"),
            ("size", "Size"), ("player_name", "Player"),
        )):
            identity.addWidget(QLabel(title.upper()), index // 3 * 2, index % 3)
            value = QLabel("—"); value.setObjectName("ultraBuildValue")
            identity.addWidget(value, index // 3 * 2 + 1, index % 3)
            self.identity[key] = value
        self.root.addLayout(identity)
        self.table = _table(("Class", "Archetype(s)", "Level", "Hit Die", "BAB"), stretch=0)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        for key, label in self.identity.items():
            label.setText(str(getattr(context.snapshot.details, key) or "—"))
        self.table.setRowCount(0)
        for class_level in context.snapshot.classes:
            archetypes = [
                str(entry.get("name"))
                for key in context.archetypes_by_level.get(class_level.id, ())
                if (entry := archetype_entry(key)) is not None
            ]
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (
                class_level.class_name,
                ", ".join(archetypes) or "—",
                class_level.level,
                f"d{class_level.hit_die}" if class_level.hit_die else "—",
                class_level.bab_progression,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, _item(value, center=column >= 2))
        _fit_table(self.table, minimum=2, maximum=8)


class UltraAbilityIncreasePanel(UltraCard):
    def __init__(self, owner: "UltraSheetWidget") -> None:
        super().__init__("Base abilities & level increases")
        self.owner = owner
        self.context: UltraSheetContext | None = None
        self._loading = False
        self.summary = QLabel("No level-based increases available yet.")
        self.summary.setObjectName("ultraHint")
        self.root.addWidget(self.summary)
        grid = QGridLayout(); grid.setSpacing(5)
        for column, title in enumerate(("Ability", "Base", "Level increases", "Current")):
            label = QLabel(title.upper()); label.setObjectName("ultraStatLabel")
            grid.addWidget(label, 0, column)
        self.controls: dict[str, QSpinBox] = {}
        self.base_values: dict[str, QLabel] = {}
        self.current_values: dict[str, QLabel] = {}
        for row, (key, _name, abbreviation) in enumerate(ABILITIES, 1):
            code = QLabel(abbreviation); code.setObjectName("abilityCode"); code.setAlignment(Qt.AlignmentFlag.AlignCenter)
            base = QLabel("10"); base.setObjectName("ultraBuildValue"); base.setAlignment(Qt.AlignmentFlag.AlignCenter)
            control = numeric_field(0, 99, width=64)
            control.valueChanged.connect(partial(self._save, key))
            current = QLabel("10"); current.setObjectName("ultraBuildValue"); current.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(code, row, 0); grid.addWidget(base, row, 1); grid.addWidget(control, row, 2); grid.addWidget(current, row, 3)
            self.controls[key] = control; self.base_values[key] = base; self.current_values[key] = current
        self.root.addLayout(grid)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.context = context
        allocations = context.repository.list_ability_score_increases(context.character_id)
        allowance = sum(row.level for row in context.snapshot.classes) // 4
        used = sum(value.points for value in allocations.values())
        self.summary.setText(
            f"Automatic allowance {allowance} · allocated {used} · remaining {allowance - used}"
        )
        self._loading = True
        try:
            for key, control in self.controls.items():
                self.base_values[key].setText(str(context.snapshot.base_abilities[key]))
                control.setValue(allocations.get(key, AbilityScoreIncreaseAllocation(context.character_id, key)).points)
                self.current_values[key].setText(str(context.snapshot.abilities[key].total))
        finally:
            self._loading = False

    def _save(self, ability: str, points: int) -> None:
        if self._loading or self.context is None:
            return
        self.context.repository.update_ability_score_increase(
            AbilityScoreIncreaseAllocation(self.context.character_id, ability, points)
        )
        self.owner.refresh_all()


class UltraTraditionsPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Traditions, drawbacks & choices")
        self.table = _table(("Type", "Name", "Selections / grants"), stretch=2)
        self.root.addWidget(self.table)

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        self.table.setRowCount(0)
        for tradition in context.repository.list_character_traditions(context.character_id):
            choices = json.loads(tradition.choices_json or "{}")
            grants = json.loads(tradition.grants_json or "[]")
            detail = " · ".join(
                value for value in (
                    ", ".join(f"{key}: {value}" for key, value in choices.items()),
                    ", ".join(str(value.get("name") if isinstance(value, dict) else value) for value in grants),
                ) if value
            ) or "—"
            row = self.table.rowCount(); self.table.insertRow(row)
            for column, value in enumerate((tradition.kind, tradition.name, detail)):
                self.table.setItem(row, column, _item(value, tooltip=detail))
        for selection in context.repository.list_class_feature_selections(context.character_id):
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (selection.option_type or "Class choice", selection.name, selection.description or selection.option_key)
            for column, value in enumerate(values):
                self.table.setItem(row, column, _item(value, tooltip=selection.description))
        _fit_table(self.table, minimum=4, maximum=12)


class UltraCompanionPanel(UltraCard):
    def __init__(self, owner: object) -> None:
        super().__init__("Animal companion")
        self.identity = QLabel("No companion configured")
        self.identity.setObjectName("ultraCompanionName")
        self.root.addWidget(self.identity)
        self.stats = QGridLayout(); self.stats.setSpacing(5)
        self.stat_values: dict[str, QLabel] = {}
        for index, (key, title) in enumerate((
            ("level", "Level"), ("hp", "HP"), ("ac", "AC"),
            ("flat", "Flat-Footed"), ("touch", "Touch"), ("bab", "BAB"),
            ("cmb", "CMB"), ("cmd", "CMD"), ("fort", "Fort"),
            ("ref", "Ref"), ("will", "Will"), ("speed", "Land Speed"),
        )):
            tile = QFrame(); tile.setObjectName("ultraStatTile")
            box = QVBoxLayout(tile); box.setContentsMargins(5, 3, 5, 3); box.setSpacing(0)
            caption = QLabel(title.upper()); caption.setObjectName("ultraStatLabel"); caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—"); value.setObjectName("ultraStatValue"); value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(caption); box.addWidget(value)
            self.stats.addWidget(tile, index // 6, index % 6); self.stat_values[key] = value
        self.root.addLayout(self.stats)
        self.abilities = _table(("Ability", "Score", "Modifier"), stretch=0)
        self.attacks = _table(("Attack", "Bonus", "Damage", "Notes"), stretch=3)
        self.skills = _table(("Skill", "Total", "Ability", "Ranks"), stretch=0)
        lower = QHBoxLayout(); lower.setSpacing(10)
        lower.addWidget(self.abilities, 1); lower.addWidget(self.attacks, 2); lower.addWidget(self.skills, 2)
        self.root.addLayout(lower)

    @staticmethod
    def _object(text: str) -> dict:
        try:
            value = json.loads(text or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _list(text: str) -> list[str]:
        try:
            value = json.loads(text or "[]")
            return [str(item) for item in value] if isinstance(value, list) else []
        except (TypeError, ValueError):
            return []

    def refresh_from_context(self, context: UltraSheetContext) -> None:
        record = context.repository.get_animal_companion(context.character_id)
        level = record.effective_level_override
        if level is None:
            level = max(1, context.companion_grant.effective_level + record.effective_level_adjustment)
        progression = companion_progression(level)
        details = self._object(record.details_json)
        ability_increases = details.get("ability_increases", {})
        if not isinstance(ability_increases, dict):
            ability_increases = {}
        statistics = calculate_companion_statistics(
            companion_entry(record.species_key), progression,
            ability_overrides=self._object(record.ability_overrides_json),
            ability_increases=ability_increases,
            skill_ranks=self._object(record.skill_ranks_json),
            details=details,
            feats=self._list(record.feats_json),
        )
        species = companion_entry(record.species_key) or {}
        species_name = species.get("name") or details.get("custom_species_name") or "Custom animal"
        self.identity.setText(
            f"{record.name or 'Unnamed companion'} · {species_name} · "
            f"{statistics.size} {statistics.creature_type}"
        )
        values = {
            "level": progression.level, "hp": f"{record.current_hp} / {statistics.maximum_hp}",
            "ac": statistics.armor_class, "flat": statistics.flat_footed_ac,
            "touch": statistics.touch_ac, "bab": f"{statistics.base_attack_bonus:+d}",
            "cmb": statistics.cmb, "cmd": statistics.cmd,
            "fort": f"{statistics.saves['fortitude']:+d}",
            "ref": f"{statistics.saves['reflex']:+d}",
            "will": f"{statistics.saves['will']:+d}",
            "speed": f"{statistics.speeds.get('land', 0)} ft",
        }
        for key, label in self.stat_values.items(): label.setText(str(values[key]))
        self.abilities.setRowCount(0)
        for key in ("str", "dex", "con", "int", "wis", "cha"):
            row = self.abilities.rowCount(); self.abilities.insertRow(row)
            for column, value in enumerate((key.upper(), statistics.ability_scores[key], f"{statistics.ability_modifiers[key]:+d}")):
                self.abilities.setItem(row, column, _item(value, center=column > 0))
        self.attacks.setRowCount(0)
        for attack in statistics.attacks:
            row = self.attacks.rowCount(); self.attacks.insertRow(row)
            for column, value in enumerate((attack.name, f"{attack.attack_bonus:+d}", attack.damage, attack.notes)):
                self.attacks.setItem(row, column, _item(value, tooltip=attack.notes, center=column in {1, 2}))
        self.skills.setRowCount(0)
        for skill in statistics.skills:
            row = self.skills.rowCount(); self.skills.insertRow(row)
            for column, value in enumerate((skill.name, f"{skill.total:+d}", skill.ability, skill.ranks)):
                self.skills.setItem(row, column, _item(value, center=column > 0))
        _fit_table(self.abilities, minimum=6, maximum=6)
        _fit_table(self.attacks, minimum=4, maximum=8)
        _fit_table(self.skills, minimum=9, maximum=9)


ULTRA_PAGES = (
    ("play", "PLAY"),
    ("features", "FEATURES"),
    ("inventory", "INVENTORY"),
    ("magic", "MAGIC"),
    ("build", "BUILD & REFERENCE"),
    ("companion", "ANIMAL COMPANION"),
)


def _register_builtin_ultra_modules(registry: UltraModuleRegistry) -> None:
    descriptors = (
        UltraModuleDescriptor("play.core", "play", 10, UltraCorePanel, full_width=True, estimated_height=260),
        UltraModuleDescriptor("play.skills", "play", 20, UltraSkillsPanel, estimated_height=920),
        UltraModuleDescriptor("play.attacks", "play", 30, UltraAttacksPanel, estimated_height=280),
        UltraModuleDescriptor("play.movement", "play", 40, UltraMovementPanel, estimated_height=230),
        UltraModuleDescriptor("play.conditions", "play", 50, UltraConditionsPanel, estimated_height=220),
        UltraModuleDescriptor("play.focus", "play", 60, UltraFocusPanel, requires=frozenset({"martial"}), estimated_height=150),
        UltraModuleDescriptor("play.sequence", "play", 70, UltraSequencePanel, requires=frozenset({"sequence"}), estimated_height=170),
        UltraModuleDescriptor("features.special", "features", 10, UltraClassFeaturesPanel, full_width=True, estimated_height=400),
        UltraModuleDescriptor("features.feats_traits", "features", 20, UltraFeatTraitPanel, estimated_height=380),
        UltraModuleDescriptor(
            "features.martial", "features", 30,
            lambda owner: UltraFeaturePanel(owner, "Martial talents", "martial_talents"),
            requires=frozenset({"martial"}), estimated_height=420,
        ),
        UltraModuleDescriptor(
            "features.magic", "features", 40,
            lambda owner: UltraFeaturePanel(
                owner,
                "Magic sphere talents",
                "spells",
                lambda value: getattr(value, "system", "") == "Sphere",
            ),
            requires=frozenset({"magic"}), estimated_height=420,
        ),
        UltraModuleDescriptor("inventory.items", "inventory", 10, UltraEquipmentPanel, full_width=True, estimated_height=520),
        UltraModuleDescriptor("inventory.worn_load", "inventory", 20, UltraWornLoadPanel, estimated_height=420),
        UltraModuleDescriptor(
            "magic.summary", "magic", 10, UltraCastingPanel,
            requires=frozenset({"spellcasting"}), full_width=True, estimated_height=240,
        ),
        UltraModuleDescriptor(
            "magic.traditional", "magic", 20, UltraTraditionalSpellsPanel,
            requires=frozenset({"traditional_spells"}), estimated_height=500,
        ),
        UltraModuleDescriptor(
            "magic.spheres", "magic", 30, UltraSphereMagicPanel,
            requires=frozenset({"magic"}), estimated_height=560,
        ),
        UltraModuleDescriptor("build.character", "build", 10, UltraCharacterBuildPanel, full_width=True, estimated_height=330),
        UltraModuleDescriptor("build.asi", "build", 20, UltraAbilityIncreasePanel, estimated_height=430),
        UltraModuleDescriptor("build.traditions", "build", 30, UltraTraditionsPanel, estimated_height=420),
        UltraModuleDescriptor(
            "companion.record", "companion", 10, UltraCompanionPanel,
            requires=frozenset({"companion"}), full_width=True, estimated_height=760,
        ),
    )
    for descriptor in descriptors:
        # A supplied registry may intentionally replace a built-in panel while
        # retaining its stable key.  Fill only missing defaults so extensions
        # remain authoritative and every widget still receives a complete set.
        if descriptor.key not in registry:
            registry.register(descriptor)


class UltraSheetWidget(QWidget):
    """Independent fixed sheet assembled from capability-aware modules."""

    character_renamed = Signal(int)
    full_rest_requested = Signal()

    def __init__(
        self,
        repository: CharacterRepository,
        parent: QWidget | None = None,
        *,
        module_registry: UltraModuleRegistry | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id: int | None = None
        self.context: UltraSheetContext | None = None
        self.registry = (module_registry or ULTRA_MODULES).copy()
        _register_builtin_ultra_modules(self.registry)
        self.setObjectName("ultraSheet")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.status_header = UltraStatusHeader(self)
        self.status_header.full_rest_requested.connect(self.full_rest_requested)
        root.addWidget(self.status_header)
        self.page_tabs = QTabWidget()
        self.page_tabs.setObjectName("ultraPages")
        self.page_tabs.setDocumentMode(True)
        root.addWidget(self.page_tabs, 1)

        self.module_widgets: dict[str, QWidget] = {}
        self.pages: dict[str, UltraResponsivePage] = {}
        self.page_indices: dict[str, int] = {}
        for page_key, page_label in ULTRA_PAGES:
            values = []
            for descriptor in self.registry.descriptors(page_key):
                widget = descriptor.factory(self)
                widget.setProperty("ultraModuleKey", descriptor.key)
                self.module_widgets[descriptor.key] = widget
                values.append((descriptor, widget))
            page = UltraResponsivePage(tuple(values))
            self.pages[page_key] = page
            self.page_indices[page_key] = self.page_tabs.addTab(page, page_label)

        application = QApplication.instance()
        self._event_filter_application = application
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if forward_editor_wheel_to_page(self, watched, event):
            return True
        return super().eventFilter(watched, event)

    def load_character(self, character_id: int) -> None:
        self.character_id = character_id
        self.refresh_all()

    def refresh_all(self) -> None:
        if self.character_id is None:
            return
        context = build_ultra_context(self.repository, self.character_id)
        self.context = context
        self.status_header.refresh_from_context(context)
        for page_key, page in self.pages.items():
            page.apply_capabilities(context.capabilities)
            for descriptor in self.registry.descriptors(page_key):
                widget = self.module_widgets[descriptor.key]
                if descriptor.is_available(context.capabilities):
                    refresh = getattr(widget, "refresh_from_context", None)
                    if callable(refresh):
                        refresh(context)
        self.page_tabs.setTabVisible(
            self.page_indices["magic"], context.class_capabilities.any_spellcasting
        )
        self.page_tabs.setTabVisible(
            self.page_indices["companion"], "companion" in context.capabilities
        )

    def dispose(self) -> None:
        application = self._event_filter_application
        if application is not None:
            application.removeEventFilter(self)
            self._event_filter_application = None

    def closeEvent(self, event) -> None:
        self.dispose()
        super().closeEvent(event)
