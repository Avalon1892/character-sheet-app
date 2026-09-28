from __future__ import annotations

import html
import json
import uuid
from functools import partial
from types import SimpleNamespace
from typing import Callable, Iterable, Mapping

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTextBrowser, QScrollArea, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.content import (
    archetype_entries, class_entries, entries, entry_by_key, entry_by_name, feat_categories, feat_entries,
    item_categories, item_entries, item_entry, item_families, item_sources,
    magic_entries, magic_spheres, martial_entries, martial_spheres,
    spell_entries, spell_publishers, spell_sources,
    trait_categories, trait_entries, trait_sources, tradition_entries,
    tradition_rule_entries,
)
from app.archetype_rules import (
    ArchetypeCompatibilityIndex, archetype_choices, validate_archetype_selection,
)
from app.archetype_presentation import archetype_change_labels, archetype_rules_html
from app.class_modifications import resolve_class_profile
from app.class_feature_rules import archetype_optional_features, optional_feature_conflicts
from app.attack_profiles import ATTACK_TEMPLATES, attack_template
from app.catalog_search import CatalogSearchIndex
from app.talent_sorting import talent_category_sort_key, talent_entry_sort_key
from app.database import CharacterRepository
from app.drawback_rules import (
    drawback_bonus_feat_names, drawback_choice_options, drawback_requires_choice,
    drawback_talent_grant, incompatible_drawbacks,
    magic_talent_restriction_reason, martial_talent_restriction_reason, sphere_package_access,
)
from app.models import (
    ABILITIES, ABILITY_KEYS, ATTACK_TYPES, BAB_PROGRESSIONS, BONUS_TYPES, CONDITION_PRESETS,
    CONDITION_RULES_TEXT, ONGOING_EFFECT_SOURCE_TYPES,
    DAMAGE_MULTIPLIERS, EQUIPMENT_BONUS_TYPES, EQUIPMENT_CATEGORIES,
    EQUIPMENT_STATES,
    MARTIAL_TALENT_TYPES, SAVE_PROGRESSIONS, SEQUENCE_OPTION_TYPES, SIZES, SKILLS,
    SPELL_SYSTEMS, STAT_TARGETS, WORN_SLOTS, Attack, ClassLevel, Condition, OngoingEffect,
    CustomTracker, EquipmentItem, Feat, FeatEffect, MartialTalent, SequenceOption, SkillState,
    Spell, SphereStatistic, StatModifier, Trait,
)
from app.class_feature_systems import ResolvedClassFeatureResource
from app.sphere_rules import base_sphere_choice_label, base_sphere_choice_options
from app.presentation import FEATURE_TARGET_LABELS, effect_display
from app.rules import CalculationResult, parse_dice, recommended_hit_points
from app.spell_rules import normalized_spell_class_name, spell_level_for_class
from app.prepared_spell_rules import PreparedCasterCapacity
from app.formulas import DEFAULT_FORMULA_ENGINE, FormulaError, parse_formula
from app.custom_trackers import CustomTrackerResolver, display_number, reference_key
from app.recovery import RecoveryTarget
from app.item_effects import (
    ItemAutomation, automation_for_entry, automation_from_json, automation_json,
    automation_summary, validate_item_choices,
)
from app.item_enchantments import (
    available_enchantments, catalog_enhancement_bonus, enchantment_spec,
    item_price_breakdown, validate_enchantment_addition, weapon_attack_type,
)
from app.ui.components import (
    CatalogSelectionBasket, DebouncedCallback, FormulaLineEdit, FormulaNumberEdit,
    OptionalNumericRangeFilter, TranslucentReorderListWidget,
)
from app.tradition_rules import boon_cost, drawback_value, spell_point_rule_for_unused_drawbacks
from app.athletics_rules import athletics_packages
from app.text_cleanup import repair_mojibake


FEAT_TARGET_LABELS = FEATURE_TARGET_LABELS
SKILL_LABELS = {definition.key: definition.name for definition in SKILLS}


def _formula_number_field(
    minimum: float,
    maximum: float,
    fallback: int | float,
    formula_key: str,
    formulas: dict[str, str] | None,
    evaluator: Callable[[str], float] | None,
    suggestions: Callable[[], tuple] | None,
    *,
    integer: bool = True,
) -> FormulaNumberEdit:
    """Build one consistently initialized numeric formula editor for dialogs."""

    field = FormulaNumberEdit(
        minimum,
        maximum,
        integer=integer,
        evaluator=evaluator,
        suggestion_provider=suggestions,
    )
    field.set_expression((formulas or {}).get(formula_key, ""), fallback)
    return field


class SpecialAbilityDialog(QDialog):
    """Edit a character overlay without mutating the shared rules catalog."""

    def __init__(self, parent=None, *, level=1, name="", description="") -> None:
        super().__init__(parent)
        self.setWindowTitle("Special ability")
        self.resize(620, 440)
        layout = QFormLayout(self)
        self.level = QSpinBox(); self.level.setRange(1, 999); self.level.setValue(level)
        self.name = QLineEdit(name)
        self.description = QPlainTextEdit(description)
        layout.addRow("Level", self.level)
        layout.addRow("Ability", self.name)
        layout.addRow("Description", self.description)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Missing name", "Enter an ability name.")
            return
        self.accept()

    @property
    def values(self) -> dict:
        return {"level": self.level.value(), "name": self.name.text().strip(),
                "description": self.description.toPlainText().strip()}


class ProficiencyDialog(QDialog):
    """Edit a character override while keeping the automatic result visible."""

    def __init__(self, parent=None, *, automatic_weapons="", automatic_armor="",
                 weapons="", armor="", notes="") -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit proficiencies")
        self.resize(680, 470)
        layout = QFormLayout(self)
        automatic = QLabel(
            f"<b>Automatic weapons:</b> {html.escape(automatic_weapons or 'None')}<br>"
            f"<b>Automatic armor:</b> {html.escape(automatic_armor or 'None')}"
        )
        automatic.setWordWrap(True)
        self.weapons = QPlainTextEdit(weapons or automatic_weapons)
        self.armor = QPlainTextEdit(armor or automatic_armor)
        self.notes = QPlainTextEdit(notes)
        self.weapons.setPlaceholderText("Comma-separated weapon proficiencies")
        self.armor.setPlaceholderText("Comma-separated armor and shield proficiencies")
        layout.addRow("Class rules", automatic)
        layout.addRow("Weapons", self.weapons)
        layout.addRow("Armor & shields", self.armor)
        layout.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def values(self) -> dict[str, str]:
        return {
            "weapons": self.weapons.toPlainText().strip(),
            "armor": self.armor.toPlainText().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class RestConfigurationDialog(QDialog):
    """Per-character selection of the registered eight-hour-rest effects."""

    def __init__(
        self,
        targets: tuple[RecoveryTarget, ...],
        enabled: dict[str, bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Full Rest")
        self.resize(650, 620)
        layout = QVBoxLayout(self)
        heading = QLabel("FULL REST EFFECTS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Choose what the general Full Rest action changes for this character. "
            "New tracker types can join this list through the shared recovery registry."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        self.checkboxes: dict[str, QCheckBox] = {}
        current_category = ""
        for target in targets:
            if target.category != current_category:
                current_category = target.category
                category = QLabel(current_category.upper())
                category.setObjectName("minorTitle")
                body_layout.addWidget(category)
            checkbox = QCheckBox(target.name)
            checkbox.setChecked(enabled.get(target.key, target.default_enabled))
            checkbox.setToolTip(target.description)
            body_layout.addWidget(checkbox)
            description = QLabel(target.description)
            description.setObjectName("mutedText")
            description.setWordWrap(True)
            description.setContentsMargins(22, 0, 8, 6)
            body_layout.addWidget(description)
            self.checkboxes[target.key] = checkbox
        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def preferences(self) -> dict[str, bool]:
        return {key: checkbox.isChecked() for key, checkbox in self.checkboxes.items()}


def _feat_effect_display(effect: FeatEffect | dict) -> str:
    return effect_display(effect, SKILL_LABELS)


def _selected_catalog_entries(
    table: QTableWidget, entries_by_key: dict[str, dict], key_column: int = 0
) -> tuple[dict, ...]:
    """Return selected catalog rows in visible order, once per entry."""

    rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
    result = []
    seen: set[str] = set()
    for row in rows:
        cell = table.item(row, key_column)
        key = str(cell.data(Qt.ItemDataRole.UserRole) or "") if cell else ""
        entry = entries_by_key.get(key)
        if entry is not None and key not in seen:
            result.append(entry)
            seen.add(key)
    return tuple(result)


def _update_catalog_add_button(
    button: QPushButton,
    entries: tuple[dict, ...],
    singular: str,
    plural: str,
) -> None:
    count = len(entries)
    button.setEnabled(count > 0)
    button.setText(
        f"Add selected {singular}"
        if count == 1
        else f"Add {count} selected {plural}"
        if count > 1
        else f"Select {plural} to add"
    )


class CatalogBasketDialogMixin:
    """Shared explicit-selection workflow for searchable catalog dialogs."""

    def _install_catalog_basket(
        self,
        browser: QHBoxLayout,
        singular: str,
        plural: str,
        meta_provider: Callable[[dict], str],
        *,
        quantity_mode: bool = False,
    ) -> None:
        self._basket_quantity_mode = quantity_mode
        self.selection_basket = CatalogSelectionBasket(
            singular,
            plural,
            meta_provider=meta_provider,
            quantity_mode=quantity_mode,
            maximum_entries=max(0, int(getattr(self, "selection_limit", 0))),
            parent=self,
        )
        if isinstance(browser, QSplitter):
            browser.addWidget(self.selection_basket)
        else:
            browser.addWidget(self.selection_basket, 2)
        self.results.installEventFilter(self)
        self.selection_basket.changed.connect(self._update_add_button)
        from app.ui.catalog_presentation import CatalogPresentation
        self.catalog_presentation = CatalogPresentation(self, browser)

    def _queue_current_entry(self, *_args) -> None:
        if self._basket_quantity_mode and QApplication.keyboardModifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        self._queue_current_quantity(1)

    def _queue_current_quantity(self, quantity: int) -> None:
        entry = self._current_entry()
        if entry is not None and self._entry_selectable(entry):
            self.selection_basket.add_entry(entry, quantity)

    def _queue_from_modified_click(self, *args) -> None:
        if not self._basket_quantity_mode:
            return
        if args and isinstance(args[0], QTableWidgetItem):
            self.results.setCurrentItem(args[0])
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._queue_current_quantity(10)
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            quantity = self.selection_basket.prompt_quantity(self, "Add")
            if quantity is not None:
                self._queue_current_quantity(quantity)

    def _queued_selectable_entries(self) -> tuple[dict, ...]:
        return tuple(
            entry
            for entry in self.selection_basket.selection_entries
            if self._entry_selectable(entry)
        )

    def _update_add_button(self) -> None:
        count = (
            self.selection_basket.count
            if self._basket_quantity_mode
            else len(self._queued_selectable_entries())
        )
        self.add_button.setEnabled(count > 0)
        self.add_button.setText(f"Add Selected ({count})")

    def _accept_selected(self, *_args) -> None:
        entries = self._queued_selectable_entries()
        if not entries:
            return
        self.selected_entries = entries
        self.selected_entry = entries[0]
        self.accept()

    def _clear_result_selection(self) -> None:
        self.results.blockSignals(True)
        self.results.clearSelection()
        self.results.setCurrentCell(-1, -1)
        self.results.blockSignals(False)
        self.catalog_presentation.schedule()

    def eventFilter(self, watched, event) -> bool:
        if watched is getattr(self, "results", None) and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._queue_current_entry()
                return True
        return super().eventFilter(watched, event)


class CatalogCheckList(QWidget):
    """Searchable, persistent multi-check list for large local rules catalogs."""

    def __init__(
        self,
        entries: Iterable[dict],
        placeholder: str,
        parent: QWidget | None = None,
        changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries = tuple(sorted((dict(entry) for entry in entries), key=lambda item: str(item.get("name", "")).casefold()))
        self._by_key = {str(entry["key"]): entry for entry in self._entries}
        self._counts: dict[str, int] = {}
        self._changed_callback = changed
        self._rebuilding = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)
        splitter = QSplitter()
        self.list = QListWidget()
        self.list.itemChanged.connect(self._item_changed)
        self.list.currentItemChanged.connect(self._show_current)
        self.details = QTextBrowser()
        splitter.addWidget(self.list)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        self.copies = QSpinBox()
        self.copies.setRange(0, 10)
        self.copies.setPrefix("Copies: ")
        self.copies.setToolTip(
            "Use more than one copy only when that drawback, boon, or talent allows it."
        )
        self.copies.valueChanged.connect(self._copies_changed)
        layout.addWidget(self.copies)
        self._refresh()

    def _refresh(self) -> None:
        query = self.search.text().strip().casefold()
        self._rebuilding = True
        try:
            self.list.clear()
            for entry in self._entries:
                haystack = " ".join(
                    str(entry.get(key, ""))
                    for key in ("name", "sphere", "category", "description")
                ).casefold()
                if query and query not in haystack:
                    continue
                item = QListWidgetItem(str(entry.get("name") or "Unnamed"))
                item.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if self._counts.get(str(entry["key"]), 0) > 0
                    else Qt.CheckState.Unchecked
                )
                sphere = str(entry.get("sphere", ""))
                category = str(entry.get("category", ""))
                item.setToolTip(" · ".join(value for value in (sphere, category) if value))
                self.list.addItem(item)
            if self.list.count():
                self.list.setCurrentRow(0)
        finally:
            self._rebuilding = False

    def _item_changed(self, item: QListWidgetItem) -> None:
        if self._rebuilding:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if item.checkState() == Qt.CheckState.Checked:
            self._counts[key] = max(1, self._counts.get(key, 0))
        else:
            self._counts.pop(key, None)
        self.copies.blockSignals(True)
        self.copies.setValue(self._counts.get(key, 0))
        self.copies.blockSignals(False)
        if self._changed_callback is not None:
            self._changed_callback()

    def _show_current(self, item: QListWidgetItem | None, _previous=None) -> None:
        if item is None:
            self.details.clear()
            return
        entry = self._by_key.get(str(item.data(Qt.ItemDataRole.UserRole) or ""), {})
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self.copies.blockSignals(True)
        self.copies.setValue(self._counts.get(key, 0))
        self.copies.blockSignals(False)
        self.details.setHtml(
            f"<h2>{html.escape(str(entry.get('name', '')))}</h2>"
            f"<p><b>{html.escape(str(entry.get('sphere') or entry.get('category') or 'Rules option'))}</b></p>"
            f"<p>{html.escape(str(entry.get('description', ''))).replace(chr(10), '<br>')}</p>"
        )

    def _copies_changed(self, count: int) -> None:
        item = self.list.currentItem()
        if item is None or self._rebuilding:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if count > 0:
            self._counts[key] = int(count)
        else:
            self._counts.pop(key, None)
        self._rebuilding = True
        item.setCheckState(
            Qt.CheckState.Checked if count > 0 else Qt.CheckState.Unchecked
        )
        self._rebuilding = False
        if self._changed_callback is not None:
            self._changed_callback()

    @property
    def selected_entries(self) -> tuple[dict, ...]:
        return tuple(
            self._by_key[key]
            for key, count in self._counts.items()
            if key in self._by_key
            for _copy in range(max(0, int(count)))
        )


class CustomTraditionDialog(QDialog):
    """Data-driven authoring UI for character-owned casting/martial traditions."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.entry: dict | None = None
        self.setWindowTitle(f"Create Custom {kind} Tradition")
        self.resize(1180, 820)
        layout = QVBoxLayout(self)
        heading = QLabel(f"CUSTOM {kind.upper()} TRADITION")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        identity = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tradition name")
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("Concept, source, GM notes, and how the tradition works…")
        self.description_edit.setMaximumHeight(80)
        identity.addRow("Name", self.name_edit)
        identity.addRow("Description", self.description_edit)
        layout.addLayout(identity)

        self.tabs = QTabWidget()
        self.general_drawbacks: CatalogCheckList | None = None
        self.boons: CatalogCheckList | None = None
        if kind == "Casting":
            rules = QWidget()
            rules_layout = QVBoxLayout(rules)
            form = QFormLayout()
            self.casting_ability = QComboBox()
            for key, title in (("intelligence", "Intelligence"), ("wisdom", "Wisdom"), ("charisma", "Charisma")):
                self.casting_ability.addItem(title, key)
            self.magic_type = QComboBox()
            self.magic_type.addItems(("Unclassified", "Arcane", "Divine", "Psychic"))
            form.addRow("Casting ability", self.casting_ability)
            form.addRow("Magic type", self.magic_type)
            rules_layout.addLayout(form)
            rule_pickers = QTabWidget()
            self.general_drawbacks = CatalogCheckList(
                tradition_rule_entries("Casting", "General Drawback"),
                "Search general drawbacks…", changed=self._refresh_balance,
            )
            self.boons = CatalogCheckList(
                tradition_rule_entries("Casting", "Boon"),
                "Search boons…", changed=self._refresh_balance,
            )
            rule_pickers.addTab(self.general_drawbacks, "General Drawbacks")
            rule_pickers.addTab(self.boons, "Boons")
            rules_layout.addWidget(rule_pickers, 1)
            self.balance = QLabel()
            self.balance.setObjectName("formulaText")
            self.balance.setWordWrap(True)
            rules_layout.addWidget(self.balance)
            self.tabs.addTab(rules, "Casting Rules")
        else:
            self.casting_ability = None
            self.magic_type = None
            note = QLabel(
                "A standard martial tradition normally contains two Equipment talents, "
                "an appropriate base sphere (or a choice between two), and one additional "
                "thematic talent. Custom packages remain subject to GM approval."
            )
            note.setWordWrap(True)
            note.setObjectName("mutedText")
            layout.addWidget(note)

        all_entries = magic_entries() if kind == "Casting" else martial_entries()
        base_entries = tuple(entry for entry in all_entries if entry.get("category") == "Base Sphere")
        drawback_entries = tuple(entry for entry in all_entries if entry.get("category") == "Drawback")
        talent_entries = tuple(
            entry for entry in all_entries
            if entry.get("category") not in {"Base Sphere", "Drawback"}
        )
        self.base_picker = CatalogCheckList(base_entries, "Search base spheres…", changed=self._refresh_balance)
        self.talent_picker = CatalogCheckList(talent_entries, "Search talents…", changed=self._refresh_balance)
        self.sphere_drawback_picker = CatalogCheckList(
            drawback_entries, "Search sphere-specific drawbacks…", changed=self._refresh_balance
        )
        self.tabs.addTab(self.base_picker, "Base Spheres")
        self.tabs.addTab(self.talent_picker, "Talents")
        self.tabs.addTab(self.sphere_drawback_picker, "Sphere Drawbacks")
        layout.addWidget(self.tabs, 1)
        self.grant_summary = QLabel()
        self.grant_summary.setObjectName("mutedText")
        self.grant_summary.setWordWrap(True)
        layout.addWidget(self.grant_summary)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_balance()

    def _selected_grants(self) -> tuple[dict, ...]:
        selected = [
            *self.base_picker.selected_entries,
            *self.sphere_drawback_picker.selected_entries,
            *self.talent_picker.selected_entries,
        ]
        by_key = {str(entry["key"]): entry for entry in selected}
        base_by_sphere = {
            str(entry.get("sphere", "")).casefold(): entry
            for entry in (magic_entries() if self.kind == "Casting" else martial_entries())
            if entry.get("category") == "Base Sphere"
        }
        # A talent or sphere drawback cannot be granted without its base sphere.
        # Add that prerequisite automatically so the resulting package is valid.
        for entry in tuple(selected):
            sphere = str(entry.get("sphere", "")).casefold()
            base = base_by_sphere.get(sphere)
            if base is not None:
                by_key.setdefault(str(base["key"]), base)
        order = {"Base Sphere": 0, "Drawback": 1}
        return tuple(sorted(by_key.values(), key=lambda entry: (
            order.get(str(entry.get("category", "")), 2),
            str(entry.get("sphere", "")).casefold(),
            str(entry.get("name", "")).casefold(),
        )))

    def _refresh_balance(self) -> None:
        grants = self._selected_grants() if hasattr(self, "base_picker") else ()
        bases = sum(entry.get("category") == "Base Sphere" for entry in grants)
        drawbacks = sum(entry.get("category") == "Drawback" for entry in grants)
        talents = len(grants) - bases - drawbacks
        if hasattr(self, "grant_summary"):
            self.grant_summary.setText(
                f"Package grants {bases} base sphere(s), {talents} talent(s), and "
                f"{drawbacks} sphere-specific drawback(s). Missing prerequisite base "
                "spheres are included automatically."
            )
        if self.kind != "Casting" or self.general_drawbacks is None or self.boons is None:
            return
        supplied = sum(drawback_value(entry) for entry in self.general_drawbacks.selected_entries)
        spent = sum(boon_cost(entry) for entry in self.boons.selected_entries)
        unused = supplied - spent
        rule = spell_point_rule_for_unused_drawbacks(max(0, unused))
        status = "Valid" if unused >= 0 else f"Needs {-unused} more drawback unit(s)"
        self.balance.setText(
            f"{status} · drawback value {supplied} · boon cost {spent} · "
            f"unused {max(0, unused)}. Spell-point rule: {rule['text']}"
        )

    @staticmethod
    def _grant(entry: dict, kind: str) -> dict:
        return {
            "kind": kind,
            "catalog_key": str(entry["key"]),
            "name": str(entry["name"]),
            "sphere": str(entry.get("sphere", "")),
            "category": str(entry.get("category", "Talent")),
        }

    @staticmethod
    def _names(entries: Iterable[dict]) -> str:
        counts: dict[str, int] = {}
        for entry in entries:
            name = str(entry["name"])
            counts[name] = counts.get(name, 0) + 1
        return ", ".join(
            f"{name} ×{count}" if count > 1 else name
            for name, count in counts.items()
        )

    def _validate(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Name the tradition", "Enter a name for the custom tradition.")
            return
        general = self.general_drawbacks.selected_entries if self.general_drawbacks else ()
        boons = self.boons.selected_entries if self.boons else ()
        supplied = sum(drawback_value(entry) for entry in general)
        spent = sum(boon_cost(entry) for entry in boons)
        if spent > supplied:
            QMessageBox.information(
                self, "Not enough drawbacks",
                f"The selected boons cost {spent} drawback units, but the selected general drawbacks supply {supplied}.",
            )
            return
        unused = supplied - spent
        grants = self._selected_grants()
        grant_kind = "magic" if self.kind == "Casting" else "martial"
        description = self.description_edit.toPlainText().strip()
        self.entry = {
            "key": f"custom-tradition:{uuid.uuid4().hex}",
            "name": name,
            "kind": self.kind,
            "source": "Character custom tradition",
            "source_url": "",
            "description": description,
            "magic_type": self.magic_type.currentText() if self.magic_type else "",
            "casting_ability_options": (
                [str(self.casting_ability.currentData())] if self.casting_ability else []
            ),
            "drawbacks": self._names(general),
            "boons": self._names(boons),
            "general_drawbacks": [
                {"key": entry["key"], "name": entry["name"], "value": drawback_value(entry)}
                for entry in general
            ],
            "selected_boons": [
                {"key": entry["key"], "name": entry["name"], "cost": boon_cost(entry)}
                for entry in boons
            ],
            "spell_point_rule": spell_point_rule_for_unused_drawbacks(unused),
            "fixed_grants": [self._grant(entry, grant_kind) for entry in grants],
            "choice_groups": [],
            "custom": True,
        }
        self.accept()


class TraditionCatalogDialog(QDialog):
    """Searchable catalog picker shared by casting and martial traditions."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.selected_entry: dict | None = None
        self.custom_requested = False
        self._entries = tradition_entries(kind)
        self._filtered = self._entries
        self.setWindowTitle(f"{kind} Tradition Catalog")
        self.resize(1100, 720)
        layout = QVBoxLayout(self)
        heading = QLabel(f"{kind.upper()} TRADITIONS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tradition names and rules…")
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)
        splitter = QSplitter()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show_current)
        self.list.itemDoubleClicked.connect(lambda *_: self._accept_current())
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        splitter.addWidget(self.list)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        button_row = QHBoxLayout()
        custom = QPushButton("+ Create custom tradition…")
        custom.setObjectName("primaryButton")
        custom.clicked.connect(self._create_custom)
        button_row.addWidget(custom)
        button_row.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_current)
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        layout.addLayout(button_row)
        self._refresh()

    def _refresh(self) -> None:
        query = self.search.text().strip().casefold()
        self._filtered = tuple(
            entry for entry in self._entries
            if not query or query in str(entry["name"]).casefold()
            or query in str(entry.get("description", "")).casefold()
            or query in str(entry.get("rules_text", "")).casefold()
        )
        self.list.clear()
        for entry in self._filtered:
            item = QListWidgetItem(str(entry["name"]))
            item.setToolTip(str(entry.get("description", "")))
            self.list.addItem(item)
        if self._filtered:
            self.list.setCurrentRow(0)

    def _show_current(self, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            self.details.clear()
            return
        entry = self._filtered[row]
        grants = "".join(
            f"<li>{html.escape(str(grant['name']))}</li>"
            for grant in entry.get("fixed_grants", ())
        )
        choices = "".join(
            f"<li>{html.escape(str(group['label']))}</li>"
            for group in entry.get("choice_groups", ())
        )
        self.details.setHtml(
            f"<h2>{html.escape(str(entry['name']))}</h2>"
            f"<p>{html.escape(str(entry.get('description', '')))}</p>"
            f"<p><b>Casting ability:</b> {html.escape(', '.join(entry.get('casting_ability_options', ())) or '—')}<br>"
            f"<b>Drawbacks:</b> {html.escape(str(entry.get('drawbacks', '')) or '—')}<br>"
            f"<b>Boons:</b> {html.escape(str(entry.get('boons', '')) or '—')}</p>"
            f"<h3>Fixed grants</h3><ul>{grants or '<li>None</li>'}</ul>"
            f"<h3>Choices</h3><ul>{choices or '<li>None</li>'}</ul>"
            f"<p><a href=\"{html.escape(str(entry.get('source_url', '')))}\">Official rules source</a></p>"
        )

    def _accept_current(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._filtered):
            self.selected_entry = self._filtered[row]
            self.accept()

    def _create_custom(self) -> None:
        dialog = CustomTraditionDialog(self.kind, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.entry is None:
            return
        self.custom_requested = True
        self.selected_entry = dialog.entry
        self.accept()


class TraditionChoiceDialog(QDialog):
    """Resolve catalog-defined choice groups without tradition-specific UI code."""

    def __init__(self, entry: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self._groups: list[tuple[dict, QListWidget]] = []
        self.setWindowTitle(f"Choose options — {entry['name']}")
        self.resize(850, 700)
        layout = QVBoxLayout(self)
        heading = QLabel(str(entry["name"]).upper())
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        for group in entry.get("choice_groups", ()):
            count = int(group.get("count", 1))
            label = QLabel(f"{group.get('label', 'Choose')} — select {count}")
            label.setWordWrap(True)
            label.setObjectName("minorTitle")
            body_layout.addWidget(label)
            picker = QListWidget()
            picker.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection
                if count == 1 else QAbstractItemView.SelectionMode.MultiSelection
            )
            options = list(group.get("options", ()))
            query = group.get("catalog_query") or {}
            if query.get("kind") == "martial":
                spheres = {str(value).casefold() for value in query.get("spheres", ())}
                categories = set(query.get("categories", ()))
                name_contains = str(query.get("name_contains", "")).casefold()
                for candidate in martial_entries():
                    if spheres and str(candidate.get("sphere", "")).casefold() not in spheres:
                        continue
                    if categories and candidate.get("category") not in categories:
                        continue
                    if name_contains and name_contains not in str(candidate.get("name", "")).casefold():
                        continue
                    options.append({"label": candidate["name"], "grants": [{
                        "kind": "martial", "catalog_key": candidate["key"],
                        "name": candidate["name"], "sphere": candidate.get("sphere", ""),
                        "category": candidate.get("category", "Talent"),
                    }]})
            seen: set[str] = set()
            for option in options:
                key = json.dumps(option.get("grants", ()), sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                item = QListWidgetItem(str(option["label"]))
                item.setData(Qt.ItemDataRole.UserRole, option)
                picker.addItem(item)
            picker.setMinimumHeight(min(250, max(75, picker.count() * 24 + 8)))
            body_layout.addWidget(picker)
            self._groups.append((group, picker))
        for _group, picker in self._groups:
            picker.itemSelectionChanged.connect(self._refresh_requirements)
        self._refresh_requirements()
        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _group_is_active(self, group: dict) -> bool:
        condition = group.get("required_when") or {}
        if not condition:
            return True
        source_key = str(condition.get("group", ""))
        required_option = str(condition.get("option", ""))
        source = next((picker for candidate, picker in self._groups if candidate.get("key") == source_key), None)
        return bool(source and any(item.text() == required_option for item in source.selectedItems()))

    def _refresh_requirements(self) -> None:
        for group, picker in self._groups:
            active = self._group_is_active(group)
            picker.setEnabled(active)
            if not active:
                picker.clearSelection()

    def _validate(self) -> None:
        for group, picker in self._groups:
            if not self._group_is_active(group):
                continue
            required = int(group.get("count", 1))
            if len(picker.selectedItems()) != required:
                QMessageBox.information(self, "Complete the choices", f"Select exactly {required} option(s) for:\n{group.get('label', 'Choice')}")
                return
        self.accept()

    @property
    def choices(self) -> dict[str, list[str]]:
        return {
            str(group["key"]): [str(item.text()) for item in picker.selectedItems()]
            for group, picker in self._groups
            if self._group_is_active(group)
        }

    @property
    def grants(self) -> tuple[dict, ...]:
        result = list(self.entry.get("fixed_grants", ()))
        for group, picker in self._groups:
            if not self._group_is_active(group):
                continue
            for item in picker.selectedItems():
                result.extend(dict(grant) for grant in item.data(Qt.ItemDataRole.UserRole).get("grants", ()))
        return tuple(result)

class FeatCatalogDialog(CatalogBasketDialogMixin, QDialog):
    def __init__(
        self,
        owned_feats: list[Feat],
        parent: QWidget | None = None,
        *,
        selection_limit: int = 0,
    ) -> None:
        super().__init__(parent)
        self.selection_limit = max(0, int(selection_limit))
        self.entity_label = "feat"
        self.entity_plural = "feats"
        self.setWindowTitle("Pathfinder & Spheres Feat Catalog")
        self.resize(1640, 860)
        self.custom_requested = False
        self.selected_entry: dict | None = None
        self.selected_entries: tuple[dict, ...] = ()
        self._entries = feat_entries()
        self._entries_by_key = {entry["key"]: entry for entry in self._entries}
        self._owned_keys = {feat.catalog_key for feat in owned_feats if feat.catalog_key}

        layout = QVBoxLayout(self)
        self.catalog_heading = QLabel("PATHFINDER & SPHERES FEAT CATALOG")
        self.catalog_heading.setObjectName("sectionTitle")
        layout.addWidget(self.catalog_heading)
        self.catalog_subtitle = QLabel(
            "Search the complete local catalog. Feats marked Automatic immediately feed "
            "the sheet; Toggle feats can be activated only while their condition applies. "
            "Single-click an entry to read it; double-click it or press Enter to queue it."
        )
        self.catalog_subtitle.setObjectName("mutedText")
        self.catalog_subtitle.setWordWrap(True)
        layout.addWidget(self.catalog_subtitle)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search names, descriptions, prerequisites, types, spheres, or source tags…"
        )
        self.source_filter = QComboBox()
        self.source_filter.addItem("All sources", "")
        self.source_filter.addItem("Pathfinder", "Pathfinder")
        self.source_filter.addItem("Spheres", "Spheres")
        self.automation_filter = QComboBox()
        self.automation_filter.addItem("All feat behavior", "")
        self.automation_filter.addItem("Automatic effects", "automatic")
        self.automation_filter.addItem("Activation toggles", "toggle")
        self.automation_filter.addItem("Rules only", "rules")
        filters.addWidget(QLabel("Find"))
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Source"))
        filters.addWidget(self.source_filter)
        filters.addWidget(QLabel("Sheet behavior"))
        filters.addWidget(self.automation_filter)
        layout.addLayout(filters)

        browser = QHBoxLayout()
        browser.setSpacing(8)
        self.category_list = QListWidget()
        self.category_list.setObjectName("catalogSphereList")
        self.category_list.setFixedWidth(245)
        all_item = QListWidgetItem(f"All feat types  ({len(self._entries)})")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        self.category_list.addItem(all_item)
        for category in feat_categories():
            count = sum(category in entry["categories"] for entry in self._entries)
            item = QListWidgetItem(f"{category}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        self.category_list.setCurrentRow(0)
        browser.addWidget(self.category_list)

        self.results = QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(
            ("Owned", "Feat", "Type", "Source", "Sheet behavior")
        )
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        header = self.results.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        browser.addWidget(self.results, 3)

        details = QWidget()
        details.setObjectName("catalogDetails")
        details.setMinimumWidth(420)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(10, 10, 10, 10)
        self.detail_name = QLabel("Select a feat")
        self.detail_name.setObjectName("catalogTalentTitle")
        self.detail_name.setWordWrap(True)
        self.detail_meta = QLabel()
        self.detail_meta.setObjectName("statCode")
        self.detail_meta.setWordWrap(True)
        self.detail_prerequisites = QLabel()
        self.detail_prerequisites.setObjectName("mutedText")
        self.detail_prerequisites.setWordWrap(True)
        self.detail_automation = QLabel()
        self.detail_automation.setWordWrap(True)
        self.detail_automation.setObjectName("focusReady")
        self.detail_description = QPlainTextEdit()
        self.detail_description.setReadOnly(True)
        self.detail_description.setPlaceholderText("Feat rules appear here.")
        self.detail_source = QLabel()
        self.detail_source.setOpenExternalLinks(True)
        details_layout.addWidget(self.detail_name)
        details_layout.addWidget(self.detail_meta)
        details_layout.addWidget(self.detail_prerequisites)
        details_layout.addWidget(self.detail_automation)
        details_layout.addWidget(self.detail_description, 1)
        details_layout.addWidget(self.detail_source)
        browser.addWidget(details, 2)
        self._install_catalog_basket(
            browser,
            self.entity_label,
            self.entity_plural,
            lambda entry: " · ".join(
                value for value in (
                    str(entry.get("sphere") or ""),
                    ", ".join(entry.get("categories", ())),
                    str(entry.get("source_group") or ""),
                ) if value
            ),
        )
        layout.addLayout(browser, 1)

        actions = QHBoxLayout()
        self.custom_button = QPushButton("+ Custom feat")
        self.custom_button.clicked.connect(self._choose_custom)
        actions.addWidget(self.custom_button)
        actions.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Add Selected (0)")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._accept_selected)
        actions.addWidget(cancel_button)
        actions.addWidget(self.add_button)
        layout.addLayout(actions)

        self.search.textChanged.connect(self._refresh_results)
        self.source_filter.currentIndexChanged.connect(self._refresh_results)
        self.automation_filter.currentIndexChanged.connect(self._refresh_results)
        self.category_list.currentItemChanged.connect(self._refresh_results)
        self.results.itemSelectionChanged.connect(self._show_selected_details)
        self.results.itemDoubleClicked.connect(self._queue_current_entry)
        self._refresh_results()

    @staticmethod
    def _behavior(entry: dict) -> str:
        automation = entry.get("automation", {})
        if not automation.get("effects"):
            return "Rules only"
        if automation.get("activation") == "toggle":
            return "Toggle"
        return "Automatic"

    def _refresh_results(self, *_args) -> None:
        category_item = self.category_list.currentItem()
        category = (
            ""
            if category_item is None
            else str(category_item.data(Qt.ItemDataRole.UserRole) or "")
        )
        source = str(self.source_filter.currentData() or "")
        behavior = str(self.automation_filter.currentData() or "")
        query = self.search.text().strip().casefold()
        self.results.setRowCount(0)
        for entry in self._entries:
            if category and category not in entry["categories"]:
                continue
            if source and entry["source_group"] != source:
                continue
            entry_behavior = self._behavior(entry)
            if behavior == "automatic" and entry_behavior == "Rules only":
                continue
            if behavior == "toggle" and entry_behavior != "Toggle":
                continue
            if behavior == "rules" and entry_behavior != "Rules only":
                continue
            haystack = " ".join(
                (
                    str(entry["name"]),
                    str(entry.get("description", "")),
                    str(entry.get("prerequisites", "")),
                    " ".join(entry["categories"]),
                    " ".join(entry.get("source_tags", ())),
                    str(entry.get("sphere", "")),
                    str(entry["source_group"]),
                )
            ).casefold()
            if query and query not in haystack:
                continue
            row = self.results.rowCount()
            self.results.insertRow(row)
            owned = entry["key"] in self._owned_keys
            values = (
                "Owned" if owned else "",
                str(entry["name"]),
                ", ".join(entry["categories"]),
                str(entry["source_group"]),
                entry_behavior,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, entry["key"])
                if owned and not entry.get("repeatable"):
                    cell.setForeground(Qt.GlobalColor.gray)
                elif entry_behavior == "Toggle":
                    cell.setForeground(Qt.GlobalColor.darkYellow)
                elif entry_behavior == "Automatic":
                    cell.setForeground(Qt.GlobalColor.darkGreen)
                self.results.setItem(row, column, cell)
        self._clear_result_selection()
        self._clear_details(
            f"Select a {self.entity_label}"
            if self.results.rowCount()
            else f"No matching {self.entity_plural}"
        )

    def _current_entry(self) -> dict | None:
        row = self.results.currentRow()
        if row < 0:
            return None
        cell = self.results.item(row, 0)
        if cell is None:
            return None
        return self._entries_by_key.get(str(cell.data(Qt.ItemDataRole.UserRole)))

    def _show_selected_details(self) -> None:
        entry = self._current_entry()
        if entry is None:
            self._clear_details(f"Select a {self.entity_label}")
            return
        self.detail_name.setText(str(entry["name"]))
        meta = f"{entry['source_group']}  •  {', '.join(entry['categories'])}"
        if entry.get("sphere"):
            meta += f"  •  {entry['sphere']}"
        if entry.get("repeatable"):
            meta += "  •  Repeatable"
        self.detail_meta.setText(meta)
        prerequisites = str(entry.get("prerequisites", ""))
        self.detail_prerequisites.setText(
            f"Prerequisites: {prerequisites}" if prerequisites else "No listed prerequisites"
        )
        automation = entry.get("automation", {})
        if automation.get("effects"):
            effect_text = "; ".join(
                _feat_effect_display(effect) for effect in automation["effects"]
            )
            note = str(automation.get("activation_note", ""))
            self.detail_automation.setText(
                f"{self._behavior(entry)}: {effect_text}" + (f"\n{note}" if note else "")
            )
        else:
            self.detail_automation.setText(
                f"Rules only: this {self.entity_label} does not have a safe automatic effect on a statistic currently represented by the sheet."
            )
        self.detail_description.setPlainText(str(entry.get("description", "")))
        url = str(entry.get("source_url", ""))
        self.detail_source.setText(f'<a href="{url}">Open source page</a>' if url else "")
        self._update_add_button()

    def _clear_details(self, title: str) -> None:
        self.detail_name.setText(title)
        self.detail_meta.clear()
        self.detail_prerequisites.clear()
        self.detail_automation.clear()
        self.detail_description.clear()
        self.detail_source.clear()
        self._update_add_button()

    def _entry_selectable(self, entry: dict) -> bool:
        return entry["key"] not in self._owned_keys or bool(entry.get("repeatable"))

    def _selectable_selected_entries(self) -> tuple[dict, ...]:
        return self._queued_selectable_entries()

    def _choose_custom(self) -> None:
        self.custom_requested = True
        self.accept()


_LOW_INTELLIGENCE_ANIMAL_COMPANION_FEATS = frozenset({
    "Acrobatic", "Agile Maneuvers", "Armor Proficiency, Heavy",
    "Armor Proficiency, Light", "Armor Proficiency, Medium", "Athletic",
    "Blind-Fight", "Combat Reflexes", "Devotion against the Unnatural",
    "Diehard", "Disruptive Companion", "Dodge", "Endurance", "Feral Grace",
    "Ferocious Beast", "Ferocious Feint", "Friendly Face", "Great Fortitude",
    "Greater Tenacious Hunter", "Hefty Brute", "Improved Bull Rush",
    "Improved Initiative", "Improved Intercept Blow", "Improved Natural Armor",
    "Improved Natural Attack", "Improved Overrun", "Intercept Blow",
    "Intimidating Prowess", "Iron Will", "Lightning Reflexes",
    "Linnorm Hunter Coordination", "Linnorm Hunter Retreat",
    "Linnorm Hunter Style", "Mobility", "Power Attack", "Reflexive Interception",
    "Run", "Share Feature", "Skill Focus", "Spring Attack", "Stealthy",
    "Tenacious Hunter", "Toughness", "Weapon Finesse", "Weapon Focus",
})


class AnimalCompanionFeatCatalogDialog(FeatCatalogDialog):
    """The shared feat catalog constrained by the animal companion feat rules."""

    def __init__(
        self,
        owned_names: Iterable[str],
        intelligence: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__([], parent)
        self.setWindowTitle("Animal Companion Feat Catalog")
        self.catalog_heading.setText("ANIMAL COMPANION FEATS")
        if int(intelligence) <= 2:
            allowed = _LOW_INTELLIGENCE_ANIMAL_COMPANION_FEATS
            self._entries = tuple(
                entry for entry in feat_entries()
                if str(entry.get("name", "")) in allowed
            )
            rule_note = (
                "With Intelligence 2 or lower, only the published animal companion "
                "feat list is shown."
            )
        else:
            self._entries = feat_entries()
            rule_note = (
                "With Intelligence 3 or higher, any physically usable feat is available; "
                "the companion must still meet its prerequisites."
            )
        self.catalog_subtitle.setText(
            rule_note + " Single-click to read; double-click or press Enter to queue a feat."
        )
        self.search.setPlaceholderText(
            "Search eligible companion feat names, prerequisites, and descriptions…"
        )
        self._entries_by_key = {str(entry["key"]): entry for entry in self._entries}
        owned = {str(name).casefold() for name in owned_names}
        self._owned_keys = {
            str(entry["key"]) for entry in self._entries
            if str(entry.get("name", "")).casefold() in owned
        }
        self.category_list.blockSignals(True)
        self.category_list.clear()
        all_item = QListWidgetItem(f"All feat types  ({len(self._entries)})")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        self.category_list.addItem(all_item)
        categories = sorted({
            str(category)
            for entry in self._entries
            for category in entry.get("categories", ())
        }, key=str.casefold)
        for category in categories:
            count = sum(category in entry.get("categories", ()) for entry in self._entries)
            item = QListWidgetItem(f"{category}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        self.category_list.setCurrentRow(0)
        self.category_list.blockSignals(False)
        self._refresh_results()


class TraitCatalogDialog(FeatCatalogDialog):
    def __init__(self, owned_traits: list[Trait], parent: QWidget | None = None) -> None:
        super().__init__([], parent)
        self.entity_label = "trait"
        self.entity_plural = "traits"
        self.setWindowTitle("Pathfinder & Spheres Trait Catalog")
        self.catalog_heading.setText("PATHFINDER & SPHERES TRAIT CATALOG")
        self.catalog_subtitle.setText(
            "Search the complete local Pathfinder, Spheres of Power, and Spheres of "
            "Might collection. Automatic entries feed safe bonuses and class-skill "
            "grants directly into the sheet. Single-click to read; double-click or press "
            "Enter to queue a trait."
        )
        self.selection_basket.set_entity_labels(self.entity_label, self.entity_plural)
        self.custom_button.setText("+ Custom trait")
        self.search.setPlaceholderText(
            "Search trait names, rules, categories, regions, faiths, or source tags…"
        )
        self.automation_filter.setItemText(0, "All trait behavior")
        self.detail_name.setText("Select a trait")
        self.detail_description.setPlaceholderText("Trait rules appear here.")

        self._entries = trait_entries()
        self._entries_by_key = {entry["key"]: entry for entry in self._entries}
        self._owned_keys = {
            trait.catalog_key for trait in owned_traits if trait.catalog_key
        }

        self.source_filter.blockSignals(True)
        self.source_filter.clear()
        self.source_filter.addItem("All sources", "")
        for source in trait_sources():
            self.source_filter.addItem(source, source)
        self.source_filter.blockSignals(False)

        self.category_list.blockSignals(True)
        self.category_list.clear()
        all_item = QListWidgetItem(f"All trait types  ({len(self._entries)})")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        self.category_list.addItem(all_item)
        for category in trait_categories():
            count = sum(category in entry["categories"] for entry in self._entries)
            item = QListWidgetItem(f"{category}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        self.category_list.setCurrentRow(0)
        self.category_list.blockSignals(False)
        self.results.setHorizontalHeaderLabels(
            ("Owned", "Trait", "Type", "Source", "Sheet behavior")
        )
        self._refresh_results()

class FeatChoiceDialog(QDialog):
    def __init__(
        self,
        choice_type: str,
        label: str,
        attacks: list[Attack],
        equipment: list,
        parent: QWidget | None = None,
        excluded_choices: Iterable[str] = (),
    ) -> None:
        super().__init__(parent)
        self.choice_type = choice_type
        self.setWindowTitle(f"Choose {label.lower()}")
        layout = QVBoxLayout(self)
        note = QLabel(
            "This choice determines where the feat's automatic effect is applied. "
            "You can type a name if the attack or armor has not been added yet."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.selection = QComboBox()
        self.second_selection: QComboBox | None = None
        if choice_type == "skill":
            for definition in SKILLS:
                self.selection.addItem(definition.name, definition.key)
        elif choice_type in {"saving_throw", "saving_throws_two"}:
            self.selection.addItem("Choose…", "")
            for key in ("fortitude", "reflex", "will"):
                self.selection.addItem(key.title(), key)
            if choice_type == "saving_throws_two":
                self.second_selection = QComboBox()
                for index in range(self.selection.count()):
                    self.second_selection.addItem(self.selection.itemText(index), self.selection.itemData(index))
        elif choice_type == "magic_sphere":
            for sphere in sorted(magic_spheres(), key=lambda item: str(item["name"]).casefold()):
                self.selection.addItem(str(sphere["name"]), str(sphere["slug"]))
        elif choice_type == "attack":
            self.selection.setEditable(True)
            for attack in attacks:
                self.selection.addItem(attack.name, attack.name.casefold())
            if self.selection.lineEdit() is not None:
                self.selection.lineEdit().setPlaceholderText("Saved attack or weapon name")
        elif choice_type == "armor":
            self.selection.setEditable(True)
            for item in equipment:
                if item.category == "Armor":
                    self.selection.addItem(item.name, item.name.casefold())
            if self.selection.lineEdit() is not None:
                self.selection.lineEdit().setPlaceholderText("Armor item name")
        elif choice_type == "athletics_packages_two":
            excluded = {value.casefold().strip() for value in excluded_choices}
            options = (
                package for package in ("Climb", "Fly", "Leap", "Run", "Swim")
                if package.casefold() not in excluded
            )
            for package in options:
                self.selection.addItem(package, package)
            self.second_selection = QComboBox()
            for index in range(self.selection.count()):
                self.second_selection.addItem(
                    self.selection.itemText(index), self.selection.itemData(index)
                )
            if self.second_selection.count() > 1:
                self.second_selection.setCurrentIndex(1)
        form.addRow(label, self.selection)
        if self.second_selection is not None:
            form.addRow("Second saving throw" if choice_type == "saving_throws_two" else "Second package", self.second_selection)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def choice(self) -> str:
        if self.second_selection is not None:
            return f"{self.selection.currentText().strip()} / {self.second_selection.currentText().strip()}"
        return self.selection.currentText().strip()

    @property
    def choice_key(self) -> str:
        data = self.selection.currentData()
        return str(data if data else self.choice).strip().casefold()

    @property
    def choice_keys(self) -> tuple[str, ...]:
        if self.choice_type == "saving_throws_two":
            return (str(self.selection.currentData() or ""), str(self.second_selection.currentData() or ""))
        return (self.choice_key,)

    def _accept_if_valid(self) -> None:
        if self.choice_type in {"saving_throw", "saving_throws_two"}:
            keys = self.choice_keys
            if any(key not in {"fortitude", "reflex", "will"} for key in keys) or len(set(keys)) != len(keys):
                QMessageBox.warning(self, "Choice required", "Choose the required number of different saving throws.")
                return
            self.accept()
            return
        if not self.choice:
            QMessageBox.warning(self, "Choice required", "Choose or enter a value.")
            return
        if self.second_selection is not None:
            if self.selection.count() < 2:
                QMessageBox.warning(
                    self, "No packages remain", "Expanded Training requires two unowned packages."
                )
                return
            if self.selection.currentText() == self.second_selection.currentText():
                QMessageBox.warning(
                    self, "Choose two packages", "The two Athletics packages must be different."
                )
                return
        self.accept()

class FeatDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        feat: Feat | Trait | None = None,
        entity_name: str = "Feat",
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog_key = str(getattr(feat, "catalog_key", ""))
        self.catalog_category = str(getattr(feat, "catalog_category", ""))
        self.prerequisites = str(getattr(feat, "prerequisites", ""))
        self.source_url = str(getattr(feat, "source_url", ""))
        self.choice = str(getattr(feat, "choice", ""))
        self.effects = tuple(getattr(feat, "effects", ()))
        self.repeatable = bool(getattr(feat, "repeatable", False))
        self.activation = str(getattr(feat, "activation", "always"))
        self.activation_note = str(getattr(feat, "activation_note", ""))
        self.entity_name = entity_name
        self.setWindowTitle(
            f"Edit {entity_name.lower()}" if feat else f"Add {entity_name.lower()}"
        )
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(
            "e.g. Weapon Focus" if entity_name == "Feat" else "e.g. Reactionary"
        )
        self.target = QComboBox()
        for target in ("",) + STAT_TARGETS:
            self.target.addItem(
                FEAT_TARGET_LABELS.get(target, target.replace("_", " ").title()),
                target,
            )
        self.bonus_type = QComboBox()
        self.bonus_type.addItems(BONUS_TYPES)
        self.bonus_type.setCurrentText("trait" if entity_name == "Trait" else "untyped")
        self.value = _formula_number_field(
            -999,
            999,
            int(getattr(feat, "value", 1)),
            "value",
            formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.notes = QLineEdit()
        form.addRow(entity_name, self.name)
        form.addRow("Bonus target", self.target)
        form.addRow("Bonus type", self.bonus_type)
        form.addRow("Bonus value", self.value)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)
        self.target.currentIndexChanged.connect(self._target_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if feat is not None:
            self.name.setText(feat.name)
            self.target.setCurrentIndex(max(0, self.target.findData(feat.target)))
            self.bonus_type.setCurrentText(feat.bonus_type)
            self.notes.setText(feat.notes)
        self._target_changed()

    def _target_changed(self) -> None:
        has_target = bool(self.target.currentData())
        self.bonus_type.setEnabled(has_target)
        self.value.setEnabled(has_target)

    @property
    def values(self) -> dict:
        target = str(self.target.currentData() or "")
        values = {
            "name": self.name.text().strip(),
            "target": target,
            "bonus_type": self.bonus_type.currentText(),
            "value": int(self.value.value()) if target else 0,
            "notes": self.notes.text(),
        }
        if self.entity_name in {"Feat", "Trait"}:
            values.update(
                {
                    "catalog_key": self.catalog_key,
                    "catalog_category": self.catalog_category,
                    "prerequisites": self.prerequisites,
                    "source_url": self.source_url,
                    "choice": self.choice,
                    "effects": self.effects,
                    "repeatable": self.repeatable,
                    "activation": self.activation,
                    "activation_note": self.activation_note,
                }
            )
        return values

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {"value": self.value.expression if self.target.currentData() else ""}

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(
                self,
                f"{self.entity_name} required",
                f"Enter a {self.entity_name.lower()} name.",
            )
            return
        if self.target.currentData():
            try:
                self.value.value()
            except FormulaError as error:
                QMessageBox.warning(self, "Invalid bonus value", str(error))
                return
        self.accept()

class TraitDialog(FeatDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        trait: Trait | None = None,
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
    ) -> None:
        super().__init__(
            parent,
            trait,
            "Trait",
            formulas=formulas,
            formula_evaluator=formula_evaluator,
            formula_suggestions=formula_suggestions,
        )
        from app.trait_automation import trait_automation
        self._choice_automation = trait_automation(self.name.text(), self.notes.text())
        if self._choice_automation.get("choice_type") in {"saving_throw", "saving_throws_two"}:
            self.save_choice_button = QPushButton(self.choice or "Choose saving throws…")
            self.save_choice_button.clicked.connect(self._choose_saves)
            self.layout().insertWidget(1, self.save_choice_button)

    def _choose_saves(self) -> None:
        from app.trait_automation import selected_trait_effects
        dialog = FeatChoiceDialog(
            self._choice_automation["choice_type"], self._choice_automation["choice_label"], [], [], self,
        )
        for widget, value in zip(
            (dialog.selection, dialog.second_selection), self.choice.casefold().split(" / ")
        ):
            if widget is not None:
                widget.setCurrentIndex(max(0, widget.findData(value)))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.choice = dialog.choice
            self.effects = tuple(selected_trait_effects(self._choice_automation, dialog.choice_keys))
            self.save_choice_button.setText(self.choice)

    def _accept_if_valid(self) -> None:
        from app.trait_automation import selected_trait_effects
        if getattr(self, "_choice_automation", {}).get("choice_type") in {"saving_throw", "saving_throws_two"}:
            try:
                selected_trait_effects(self._choice_automation, tuple(self.choice.casefold().split(" / ")))
            except ValueError as error:
                QMessageBox.warning(self, "Choice required", str(error))
                return
        super()._accept_if_valid()

class MartialTalentCatalogDialog(CatalogBasketDialogMixin, QDialog):
    def __init__(
        self,
        owned_talents: list[MartialTalent],
        parent: QWidget | None = None,
        *,
        selection_limit: int = 0,
    ) -> None:
        super().__init__(parent)
        self.selection_limit = max(0, int(selection_limit))
        self.setWindowTitle("Martial Sphere & Talent Catalog")
        self.resize(1800, 900)
        self.custom_requested = False
        self.selected_entry: dict | None = None
        self.selected_entries: tuple[dict, ...] = ()
        self._entries = martial_entries()
        self._sorted_entries = tuple(sorted(self._entries, key=talent_entry_sort_key))
        self._owned_talents = tuple(owned_talents)
        self._entries_by_key = {entry["key"]: entry for entry in self._entries}
        self._owned_keys = {
            talent.catalog_key for talent in owned_talents if talent.catalog_key
        }
        self._owned_key_counts = {
            key: sum(1 for talent in owned_talents if talent.catalog_key == key)
            for key in self._owned_keys
        }

        layout = QVBoxLayout(self)
        self.catalog_heading = QLabel("MARTIAL SPHERE & TALENT CATALOG")
        self.catalog_heading.setObjectName("sectionTitle")
        layout.addWidget(self.catalog_heading)
        self.catalog_subtitle = QLabel(
            "Choose a sphere on the left, then filter or search its talents. "
            "Selecting a talent or drawback automatically adds its base sphere. "
            "Single-click to read; double-click or press Enter to queue an entry."
        )
        self.catalog_subtitle.setObjectName("mutedText")
        layout.addWidget(self.catalog_subtitle)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search names, descriptions, prerequisites, spheres…")
        self.category = QComboBox()
        self.category.addItem("All categories", "")
        categories = sorted(
            {str(entry["category"]) for entry in self._entries},
            key=talent_category_sort_key,
        )
        for category in categories:
            self.category.addItem(category, category)
        self.automation_filter = QComboBox()
        self.automation_filter.addItem("All sheet behavior", "")
        self.automation_filter.addItem("Automatic effects", "automatic")
        self.automation_filter.addItem("Activation toggles", "toggle")
        self.automation_filter.addItem("Rules only", "rules")
        filters.addWidget(QLabel("Find"))
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Type"))
        filters.addWidget(self.category)
        filters.addWidget(QLabel("Sheet behavior"))
        filters.addWidget(self.automation_filter)
        layout.addLayout(filters)

        browser = QSplitter(Qt.Orientation.Horizontal)
        browser.setChildrenCollapsible(False)
        self.sphere_list = QListWidget()
        self.sphere_list.setObjectName("catalogSphereList")
        self.sphere_list.setMinimumWidth(190)
        self.sphere_list.setMaximumWidth(280)
        all_item = QListWidgetItem(f"All spheres  ({len(self._entries)})")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        self.sphere_list.addItem(all_item)
        for sphere in martial_spheres():
            count = len(martial_entries(sphere["name"]))
            item = QListWidgetItem(f"{sphere['name']}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, sphere["name"])
            self.sphere_list.addItem(item)
        self.sphere_list.setCurrentRow(0)
        browser.addWidget(self.sphere_list)

        self.results = QTableWidget(0, 6)
        self.results.setHorizontalHeaderLabels(
            ("Owned", "Name", "Category", "Sphere", "Sheet behavior", "Prerequisites")
        )
        self._configure_catalog_table()

        details = QWidget()
        details.setObjectName("catalogDetails")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(10, 10, 10, 10)
        self.detail_name = QLabel("Select a sphere or talent")
        self.detail_name.setObjectName("catalogTalentTitle")
        self.detail_name.setWordWrap(True)
        self.detail_meta = QLabel()
        self.detail_meta.setObjectName("statCode")
        self.detail_meta.setWordWrap(True)
        self.detail_prerequisites = QLabel()
        self.detail_prerequisites.setWordWrap(True)
        self.detail_prerequisites.setObjectName("mutedText")
        self.detail_automation = QLabel()
        self.detail_automation.setWordWrap(True)
        self.detail_automation.setObjectName("focusReady")
        self.detail_description = QPlainTextEdit()
        self.detail_description.setReadOnly(True)
        self.detail_description.setPlaceholderText("Rules text appears here.")
        self.detail_source = QLabel()
        self.detail_source.setOpenExternalLinks(True)
        details_layout.addWidget(self.detail_name)
        details_layout.addWidget(self.detail_meta)
        details_layout.addWidget(self.detail_prerequisites)
        details_layout.addWidget(self.detail_automation)
        details_layout.addWidget(self.detail_description, 1)
        details_layout.addWidget(self.detail_source)
        details.setMinimumHeight(210)
        center = QSplitter(Qt.Orientation.Vertical)
        center.setChildrenCollapsible(False)
        center.addWidget(self.results)
        center.addWidget(details)
        center.setStretchFactor(0, 4)
        center.setStretchFactor(1, 2)
        center.setSizes([570, 260])
        browser.addWidget(center)
        self._install_catalog_basket(
            browser,
            "talent",
            "talents",
            lambda entry: " · ".join(
                value for value in (
                    str(entry.get("sphere") or ""),
                    str(entry.get("category") or ""),
                ) if value
            ),
        )
        browser.setStretchFactor(0, 0)
        browser.setStretchFactor(1, 1)
        browser.setStretchFactor(2, 0)
        browser.setSizes([220, 1190, 330])
        layout.addWidget(browser, 1)

        actions = QHBoxLayout()
        self.custom_button = QPushButton("+ Custom talent")
        self.custom_button.clicked.connect(self._choose_custom)
        actions.addWidget(self.custom_button)
        actions.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Add Selected (0)")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._accept_selected)
        self.add_button.setEnabled(False)
        actions.addWidget(cancel_button)
        actions.addWidget(self.add_button)
        layout.addLayout(actions)

        self.search.textChanged.connect(self._refresh_results)
        self.category.currentIndexChanged.connect(self._refresh_results)
        self.automation_filter.currentIndexChanged.connect(self._refresh_results)
        self.sphere_list.currentItemChanged.connect(self._refresh_results)
        self.results.itemSelectionChanged.connect(self._show_selected_details)
        self.results.itemDoubleClicked.connect(self._queue_current_entry)
        self._refresh_results()

    def _configure_catalog_table(self) -> None:
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        header = self.results.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(1, 380)
        self.results.setMinimumWidth(760)

    @staticmethod
    def _behavior(entry: dict) -> str:
        automation = entry.get("automation", {})
        if not automation.get("effects") and not automation.get("provider"):
            return "Rules only"
        if automation.get("activation") == "toggle":
            return "Toggle"
        return "Automatic"

    def _refresh_results(self, *_args) -> None:
        sphere_item = self.sphere_list.currentItem()
        sphere_name = "" if sphere_item is None else str(
            sphere_item.data(Qt.ItemDataRole.UserRole) or ""
        )
        category = str(self.category.currentData() or "")
        behavior = str(self.automation_filter.currentData() or "")
        query = self.search.text().strip().casefold()
        self.results.setRowCount(0)
        for entry in self._sorted_entries:
            if sphere_name and entry["sphere"] != sphere_name:
                continue
            if category and entry["category"] != category:
                continue
            entry_behavior = self._behavior(entry)
            if behavior == "automatic" and entry_behavior == "Rules only":
                continue
            if behavior == "toggle" and entry_behavior != "Toggle":
                continue
            if behavior == "rules" and entry_behavior != "Rules only":
                continue
            haystack = " ".join(
                str(entry.get(field, ""))
                for field in (
                    "name",
                    "sphere",
                    "category",
                    "description",
                    "prerequisites",
                )
            ).casefold()
            if query and query not in haystack:
                continue
            row = self.results.rowCount()
            self.results.insertRow(row)
            automation = entry.get("automation", {})
            repeatable = bool(automation.get("repeatable"))
            repeat_limit = int(automation.get("repeat_limit") or 0)
            owned_count = self._owned_key_counts.get(entry["key"], 0)
            owned = (
                owned_count >= repeat_limit
                if repeatable and repeat_limit
                else entry["key"] in self._owned_keys and not repeatable
            )
            restriction = martial_talent_restriction_reason(entry, self._owned_talents)
            values = (
                (
                    f"{owned_count} / {repeat_limit}"
                    if repeatable and repeat_limit and owned_count
                    else "Owned" if owned else ""
                ),
                str(entry["name"]),
                str(entry["category"]),
                str(entry["sphere"]),
                entry_behavior,
                str(entry.get("prerequisites", "")) or "—",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, entry["key"])
                if owned or restriction:
                    cell.setForeground(Qt.GlobalColor.gray)
                    if restriction:
                        cell.setToolTip(restriction)
                elif entry_behavior == "Toggle":
                    cell.setForeground(Qt.GlobalColor.darkYellow)
                elif entry_behavior == "Automatic":
                    cell.setForeground(Qt.GlobalColor.darkGreen)
                elif entry["category"] == "Drawback":
                    cell.setForeground(Qt.GlobalColor.darkRed)
                elif entry["category"] == "Legendary Talent":
                    cell.setForeground(Qt.GlobalColor.darkYellow)
                self.results.setItem(row, column, cell)
        self._clear_result_selection()
        self._clear_details(
            "Select a sphere or talent"
            if self.results.rowCount()
            else "No matching talents"
        )

    def _current_entry(self) -> dict | None:
        row = self.results.currentRow()
        if row < 0:
            return None
        cell = self.results.item(row, 0)
        if cell is None:
            return None
        return self._entries_by_key.get(str(cell.data(Qt.ItemDataRole.UserRole)))

    def _show_selected_details(self) -> None:
        entry = self._current_entry()
        if entry is None:
            self._clear_details("Select a sphere or talent")
            return
        self.detail_name.setText(str(entry["name"]))
        tags = ", ".join(entry.get("source_tags", []))
        meta = f"{entry['sphere']}  •  {entry['category']}"
        if tags:
            meta += f"  •  {tags}"
        self.detail_meta.setText(meta)
        prerequisites = str(entry.get("prerequisites", ""))
        self.detail_prerequisites.setText(
            f"Prerequisites: {prerequisites}" if prerequisites else "No listed prerequisites"
        )
        automation = entry.get("automation", {})
        if automation.get("effects") or automation.get("provider"):
            effects = "; ".join(
                _feat_effect_display(effect) for effect in automation["effects"]
            ) or "Resolved by the shared Athletics rules provider"
            note = str(automation.get("activation_note", ""))
            self.detail_automation.setText(
                f"{self._behavior(entry)}: {effects}" + (f"\n{note}" if note else "")
            )
        else:
            self.detail_automation.setText(
                "Rules only: this entry has no safe automatic effect on a statistic currently represented by the sheet."
            )
        self.detail_description.setPlainText(str(entry["description"]))
        url = str(entry.get("source_url", ""))
        self.detail_source.setText(f'<a href="{url}">Open source page</a>' if url else "")
        self._update_add_button()

    def _clear_details(self, title: str) -> None:
        self.detail_name.setText(title)
        self.detail_meta.clear()
        self.detail_prerequisites.clear()
        self.detail_automation.clear()
        self.detail_description.clear()
        self.detail_source.clear()
        self._update_add_button()

    def _entry_selectable(self, entry: dict) -> bool:
        automation = entry.get("automation", {})
        repeatable = bool(automation.get("repeatable"))
        repeat_limit = int(automation.get("repeat_limit") or 0)
        if repeat_limit and self._owned_key_counts.get(entry["key"], 0) >= repeat_limit:
            return False
        if (
            automation.get("choice_type") == "athletics_packages_two"
            and len(athletics_packages(self._owned_talents)) > 3
        ):
            return False
        return (
            (
                entry["key"] not in self._owned_keys
                or repeatable
            )
            and not martial_talent_restriction_reason(entry, self._owned_talents)
        )

    def _selectable_selected_entries(self) -> tuple[dict, ...]:
        return self._queued_selectable_entries()

    def _choose_custom(self) -> None:
        self.custom_requested = True
        self.accept()


class DrawbackTalentChoiceDialog(QDialog):
    """Focused single-rule picker for a drawback's constrained bonus talent."""

    def __init__(
        self,
        drawback: dict,
        candidates: Iterable[dict],
        count: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._all = tuple(candidates)
        self._filtered = self._all
        self._by_key = {str(entry["key"]): entry for entry in self._all}
        self.required_count = max(1, int(count))
        self.selected_entries: tuple[dict, ...] = ()
        self.setWindowTitle(f"Choose granted talent — {drawback['name']}")
        self.resize(1120, 720)
        layout = QVBoxLayout(self)
        heading = QLabel(f"{drawback['name']} — GRANTED TALENT")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            f"This drawback restricts its bonus to the options below. Select "
            f"{self.required_count}, then confirm."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search eligible talent names and descriptions…")
        layout.addWidget(self.search)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.results = QTableWidget(0, 3)
        self.results.setHorizontalHeaderLabels(("Talent", "Type", "Prerequisites"))
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
            if self.required_count == 1
            else QAbstractItemView.SelectionMode.MultiSelection
        )
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        header = self.results.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumWidth(360)
        split.addWidget(self.results)
        split.addWidget(self.details)
        split.setSizes([720, 360])
        layout.addWidget(split, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._refresh)
        self.results.itemSelectionChanged.connect(self._show_details)
        self.results.itemDoubleClicked.connect(self._double_clicked)
        self._refresh()

    def _refresh(self) -> None:
        query = self.search.text().strip().casefold()
        self._filtered = tuple(
            entry for entry in self._all
            if not query or query in " ".join(
                str(entry.get(field, ""))
                for field in ("name", "category", "description", "prerequisites")
            ).casefold()
        )
        self.results.setRowCount(0)
        for entry in self._filtered:
            row = self.results.rowCount()
            self.results.insertRow(row)
            for column, value in enumerate((
                str(entry.get("name", "")),
                str(entry.get("category", "")),
                str(entry.get("prerequisites", "")) or "—",
            )):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
                self.results.setItem(row, column, item)
        self.results.clearSelection()
        self.results.setCurrentCell(-1, -1)
        self.details.clear()

    def _selected(self) -> tuple[dict, ...]:
        rows = sorted({index.row() for index in self.results.selectionModel().selectedRows()})
        result = []
        for row in rows:
            item = self.results.item(row, 0)
            entry = self._by_key.get(str(item.data(Qt.ItemDataRole.UserRole))) if item else None
            if entry is not None:
                result.append(entry)
        return tuple(result)

    def _show_details(self) -> None:
        selected = self._selected()
        if not selected:
            self.details.clear()
            return
        entry = selected[-1]
        self.details.setPlainText(
            f"{entry['name']}\n{entry.get('category', '')}\n\n"
            f"{entry.get('description', '')}"
        )

    def _double_clicked(self, *_args) -> None:
        if self.required_count == 1:
            self._accept_selection()

    def _accept_selection(self) -> None:
        selected = self._selected()
        if len(selected) != self.required_count:
            QMessageBox.information(
                self,
                "Complete the granted talent choice",
                f"Select exactly {self.required_count} eligible talent(s).",
            )
            return
        self.selected_entries = selected
        self.accept()


class SphereAcquisitionDialog(QDialog):
    def __init__(
        self,
        owned_spheres: set[str],
        parent: QWidget | None = None,
        fixed_sphere: str = "",
        existing_drawbacks: tuple[tuple[str, str], ...] = (),
        sphere_kind: str = "magic",
        existing_base_choice: str = "",
        owned_catalog_keys: Iterable[str] = (),
    ) -> None:
        super().__init__(parent)
        self._sphere_kind = sphere_kind
        self._spheres = martial_spheres if sphere_kind == "martial" else magic_spheres
        self._entries = martial_entries if sphere_kind == "martial" else magic_entries
        label = "Martial" if sphere_kind == "martial" else "Magic"
        self.setWindowTitle("Edit Sphere Drawbacks" if fixed_sphere else f"Gain {label} Sphere")
        self.resize(760, 650)
        self._drawback_choices: dict[str, str] = dict(existing_drawbacks)
        self._drawback_talent_keys: dict[str, tuple[str, ...]] = {}
        self._owned_catalog_keys = frozenset(str(key) for key in owned_catalog_keys if key)
        self._existing_drawback_keys = set(self._drawback_choices)
        self._changing_choice = False
        self._existing_base_choice = existing_base_choice
        layout = QVBoxLayout(self)
        heading = QLabel("GAIN BASE SPHERE")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Choose any number of sphere-specific drawbacks. Checked drawbacks are all "
            "saved, and drawbacks that require a decision expose that decision below."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.sphere = QComboBox()
        for sphere in self._spheres():
            if fixed_sphere and sphere["name"].casefold() != fixed_sphere.casefold():
                continue
            if fixed_sphere or sphere["name"].casefold() not in owned_spheres:
                self.sphere.addItem(str(sphere["name"]), str(sphere["name"]))
        self.sphere.setEnabled(not bool(fixed_sphere))
        form.addRow("Base sphere", self.sphere)
        self.base_choice_label = QLabel("Starting package")
        self.base_choice = QComboBox()
        form.addRow(self.base_choice_label, self.base_choice)
        layout.addLayout(form)
        layout.addWidget(QLabel("Sphere drawbacks — check every drawback being taken"))
        self.drawbacks = QListWidget()
        self.drawbacks.setMinimumHeight(210)
        layout.addWidget(self.drawbacks)
        choice_form = QFormLayout()
        self.drawback_choice = QComboBox()
        self.drawback_choice.setEditable(True)
        self.drawback_choice.setEnabled(False)
        choice_form.addRow("Selected drawback decision", self.drawback_choice)
        grant_row = QHBoxLayout()
        self.drawback_grant = QLabel("No constrained bonus talent")
        self.drawback_grant.setWordWrap(True)
        self.drawback_grant.setObjectName("mutedText")
        self.change_drawback_grant = QPushButton("Choose granted talent…")
        self.change_drawback_grant.setEnabled(False)
        self.change_drawback_grant.clicked.connect(self._change_granted_talent)
        grant_row.addWidget(self.drawback_grant, 1)
        grant_row.addWidget(self.change_drawback_grant)
        choice_form.addRow("Bonus from drawback", grant_row)
        layout.addLayout(choice_form)
        self.description = QPlainTextEdit()
        self.description.setReadOnly(True)
        self.description.setMinimumHeight(180)
        layout.addWidget(self.description, 1)
        self.sphere.currentIndexChanged.connect(self._sphere_changed)
        self.drawbacks.currentItemChanged.connect(self._drawback_changed)
        self.drawbacks.itemChanged.connect(self._drawback_checked)
        self.drawbacks.itemClicked.connect(self._drawback_clicked)
        self.drawback_choice.currentTextChanged.connect(self._choice_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(self.sphere.count() > 0)
        self._sphere_changed()

    @property
    def sphere_name(self) -> str:
        return str(self.sphere.currentData() or "")

    @property
    def drawback_key(self) -> str:
        selections = self.drawback_selections
        return selections[0][0] if selections else ""

    @property
    def base_sphere_choice(self) -> str:
        return str(self.base_choice.currentData() or self.base_choice.currentText()).strip()

    @property
    def drawback_selections(self) -> tuple[tuple[str, str], ...]:
        result = []
        for row in range(self.drawbacks.count()):
            item = self.drawbacks.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                key = str(item.data(Qt.ItemDataRole.UserRole) or "")
                result.append((key, self._drawback_choices.get(key, "").strip()))
        return tuple(result)

    @property
    def drawback_granted_talents(self) -> dict[str, tuple[str, ...]]:
        selected_keys = {key for key, _choice in self.drawback_selections}
        return {
            key: values for key, values in self._drawback_talent_keys.items()
            if key in selected_keys and values
        }

    def _sphere_changed(self, *_args) -> None:
        self.base_choice.blockSignals(True)
        self.base_choice.clear()
        options = base_sphere_choice_options(self.sphere_name, self._sphere_kind)
        self.base_choice_label.setText(
            base_sphere_choice_label(self.sphere_name, self._sphere_kind)
        )
        for option in options:
            self.base_choice.addItem(option, option)
        if self._existing_base_choice:
            index = self.base_choice.findData(self._existing_base_choice)
            self.base_choice.setCurrentIndex(max(0, index))
        self.base_choice.setVisible(bool(options))
        self.base_choice_label.setVisible(bool(options))
        self.base_choice.blockSignals(False)
        self.drawbacks.blockSignals(True)
        self.drawbacks.clear()
        if not self._existing_drawback_keys:
            self._drawback_choices.clear()
        for entry in self._entries(self.sphere_name):
            if entry["category"] == "Drawback":
                item = QListWidgetItem(str(entry["name"]))
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
                item.setData(Qt.ItemDataRole.UserRole + 1, entry)
                if str(entry["key"]) in self._existing_drawback_keys:
                    item.setCheckState(Qt.CheckState.Checked)
                self.drawbacks.addItem(item)
        self.drawbacks.blockSignals(False)
        self._drawback_talent_keys.clear()
        if self._sphere_kind == "martial" and self.sphere_name == "Athletics":
            limited = any(
                self.drawbacks.item(row).checkState() == Qt.CheckState.Checked
                and str(
                    (self.drawbacks.item(row).data(Qt.ItemDataRole.UserRole + 1) or {}).get("name", "")
                ) == "Limited Athleticism"
                for row in range(self.drawbacks.count())
            )
            self.base_choice.setEnabled(not limited)
        else:
            self.base_choice.setEnabled(True)
        if self.drawbacks.count():
            self.drawbacks.setCurrentRow(0)
        else:
            self.description.setPlainText("This sphere has no bundled drawbacks.")

    def _current_drawback(self) -> tuple[QListWidgetItem | None, dict | None]:
        item = self.drawbacks.currentItem()
        entry = item.data(Qt.ItemDataRole.UserRole + 1) if item is not None else None
        return item, entry if isinstance(entry, dict) else None

    def _drawback_checked(self, item: QListWidgetItem) -> None:
        if item.checkState() == Qt.CheckState.Checked:
            self.drawbacks.setCurrentItem(item)
            entry = item.data(Qt.ItemDataRole.UserRole + 1)
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            options = drawback_choice_options(entry) if isinstance(entry, dict) else ()
            if options and not self._drawback_choices.get(key):
                self._drawback_choices[key] = options[0]
            self._drawback_changed(item)
        else:
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            self._drawback_talent_keys.pop(key, None)
        if self._sphere_kind == "martial" and self.sphere_name == "Athletics":
            limited = any(
                self.drawbacks.item(row).checkState() == Qt.CheckState.Checked
                and str(
                    (self.drawbacks.item(row).data(Qt.ItemDataRole.UserRole + 1) or {}).get("name", "")
                ) == "Limited Athleticism"
                for row in range(self.drawbacks.count())
            )
            self.base_choice.setEnabled(not limited)

    def _drawback_clicked(self, item: QListWidgetItem) -> None:
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if (
            item.checkState() == Qt.CheckState.Checked
            and key not in self._existing_drawback_keys
            and not self._ensure_granted_talent_choice(item)
        ):
            self.drawbacks.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.drawbacks.blockSignals(False)
            self._drawback_talent_keys.pop(key, None)

    def _drawback_changed(self, current, _previous=None) -> None:
        item, entry = self._current_drawback()
        self._changing_choice = True
        try:
            self.drawback_choice.clear()
            if item is None or entry is None:
                self.drawback_choice.setEnabled(False)
                self.description.clear()
                return
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            options = drawback_choice_options(entry)
            requires_choice = drawback_requires_choice(entry)
            self.drawback_choice.setEnabled(requires_choice)
            self.drawback_choice.setEditable(not bool(options))
            if options:
                self.drawback_choice.addItems(options)
                saved = self._drawback_choices.get(key, options[0])
                index = self.drawback_choice.findText(saved)
                self.drawback_choice.setCurrentIndex(max(0, index))
            else:
                self.drawback_choice.addItem(self._drawback_choices.get(key, ""))
                if self.drawback_choice.lineEdit() is not None:
                    self.drawback_choice.lineEdit().setPlaceholderText(
                        "Enter the required material, terrain, creature type, talent, or other choice"
                    )
            requirement = (
                "\n\nDecision required: choose a value above before continuing."
                if requires_choice
                else ""
            )
            self.description.setPlainText(
                repair_mojibake(str(entry["description"])) + requirement
            )
            self._refresh_grant_summary(item, entry)
        finally:
            self._changing_choice = False

    def _choice_changed(self, value: str) -> None:
        if self._changing_choice:
            return
        item, _entry = self._current_drawback()
        if item is not None:
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            self._drawback_choices[key] = value
            self._drawback_talent_keys.pop(key, None)
            entry = item.data(Qt.ItemDataRole.UserRole + 1)
            if isinstance(entry, dict):
                self._refresh_grant_summary(item, entry)

    def _grant_rule(self, item: QListWidgetItem, entry: dict):
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        return drawback_talent_grant(
            entry,
            self._entries(self.sphere_name),
            self._drawback_choices.get(key, ""),
        )

    def _refresh_grant_summary(self, item: QListWidgetItem, entry: dict) -> None:
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        rule = self._grant_rule(item, entry) if self._sphere_kind == "magic" else None
        names_by_key = {
            str(candidate["key"]): str(candidate["name"])
            for candidate in self._entries(self.sphere_name)
        }
        selected = tuple(
            names_by_key.get(value, value)
            for value in self._drawback_talent_keys.get(key, ())
        )
        if selected:
            self.drawback_grant.setText("Granted now: " + ", ".join(selected))
        elif rule and rule.feat_names:
            self.drawback_grant.setText("Granted feat: " + ", ".join(rule.feat_names))
        elif rule and rule.candidates:
            self.drawback_grant.setText(
                f"Choose {rule.count} from {len(rule.candidates)} eligible talent(s)."
            )
        else:
            self.drawback_grant.setText("Unrestricted bonus talent; spend it from the normal talent budget.")
        self.change_drawback_grant.setEnabled(
            bool(rule and rule.candidates and item.checkState() == Qt.CheckState.Checked)
        )

    def _ensure_granted_talent_choice(self, item: QListWidgetItem) -> bool:
        entry = item.data(Qt.ItemDataRole.UserRole + 1)
        if self._sphere_kind != "magic" or not isinstance(entry, dict):
            return True
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        rule = self._grant_rule(item, entry)
        if not rule.candidates or not rule.count:
            self._refresh_grant_summary(item, entry)
            return True
        available = tuple(
            candidate for candidate in rule.candidates
            if str(candidate["key"]) not in self._owned_catalog_keys
        )
        saved = self._drawback_talent_keys.get(key, ())
        available_keys = {str(candidate["key"]) for candidate in available}
        if len(saved) == rule.count and all(value in available_keys for value in saved):
            self._refresh_grant_summary(item, entry)
            return True
        if len(available) < rule.count:
            QMessageBox.warning(
                self,
                "No eligible granted talent",
                f"{entry['name']} requires {rule.count} specific bonus talent(s), but "
                "the available options are already owned or unavailable.",
            )
            return False
        if len(available) == rule.count:
            self._drawback_talent_keys[key] = tuple(str(candidate["key"]) for candidate in available)
            self._refresh_grant_summary(item, entry)
            return True
        picker = DrawbackTalentChoiceDialog(entry, available, rule.count, self)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return False
        self._drawback_talent_keys[key] = tuple(
            str(candidate["key"]) for candidate in picker.selected_entries
        )
        self._refresh_grant_summary(item, entry)
        return True

    def _change_granted_talent(self) -> None:
        item, entry = self._current_drawback()
        if item is None or entry is None:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self._drawback_talent_keys.pop(key, None)
        self._ensure_granted_talent_choice(item)

    def _accept_if_valid(self) -> None:
        if not self.sphere_name:
            return
        entries = {
            str(item["key"]): item
            for item in self._entries(self.sphere_name)
            if item["category"] == "Drawback"
        }
        selected = self.drawback_selections
        selected_names = {str(entries[key]["name"]).casefold() for key, _choice in selected}
        choice_options = base_sphere_choice_options(self.sphere_name, self._sphere_kind)
        if (
            choice_options
            and not self.base_sphere_choice
            and "limited athleticism" not in selected_names
        ):
            QMessageBox.warning(
                self,
                "Starting choice required",
                f"Choose the {base_sphere_choice_label(self.sphere_name, self._sphere_kind).casefold()} granted by this sphere.",
            )
            return
        for key, choice in selected:
            entry = entries[key]
            if drawback_requires_choice(entry) and not choice.strip():
                QMessageBox.warning(
                    self,
                    "Drawback decision required",
                    f"Choose the required option for {entry['name']}.",
                )
                return
            conflicts = incompatible_drawbacks(entry) & selected_names
            if conflicts:
                QMessageBox.warning(
                    self,
                    "Incompatible drawbacks",
                    f"{entry['name']} is incompatible with {', '.join(sorted(conflicts))}.",
                )
                return
            item = next(
                (
                    self.drawbacks.item(row)
                    for row in range(self.drawbacks.count())
                    if str(self.drawbacks.item(row).data(Qt.ItemDataRole.UserRole) or "") == key
                ),
                None,
            )
            if (
                item is not None
                and key not in self._existing_drawback_keys
                and not self._ensure_granted_talent_choice(item)
            ):
                return
        self.accept()

class MagicTalentCatalogDialog(MartialTalentCatalogDialog):
    def __init__(
        self,
        owned_spells: list[Spell],
        parent: QWidget | None = None,
        play_mode: bool = False,
        *,
        selection_limit: int = 0,
    ) -> None:
        self._magic_owned_spells = owned_spells
        super().__init__(owned_spells, parent, selection_limit=selection_limit)
        self.setWindowTitle("Magic Sphere & Talent Catalog")
        self.catalog_heading.setText("MAGIC SPHERE & TALENT CATALOG")
        self.catalog_subtitle.setText(
            "Choose a possessed magic sphere, then select a usable talent or effect. "
            "Base spheres and sphere-specific drawbacks are managed on Page 0."
            if play_mode
            else
            "Choose a magic sphere on the left, then filter or search its talents and drawbacks."
        )
        self.custom_button.setText("+ Custom spell or ability")
        self.search.setPlaceholderText(
            "Search magic talents, advanced talents, drawbacks, prerequisites, spheres…"
        )
        owned_sphere_names = {
            spell.school_or_sphere
            for spell in owned_spells
            if spell.catalog_category == "Base Sphere"
        }
        self._entries = tuple(
            entry
            for entry in magic_entries()
            if not play_mode
            or (
                entry["category"] not in {"Base Sphere", "Drawback"}
                and entry["sphere"] in owned_sphere_names
            )
        )
        self._sorted_entries = tuple(sorted(self._entries, key=talent_entry_sort_key))
        self._entries_by_key = {entry["key"]: entry for entry in self._entries}
        self._owned_keys = {spell.catalog_key for spell in owned_spells if spell.catalog_key}

        self.sphere_list.blockSignals(True)
        self.sphere_list.clear()
        all_item = QListWidgetItem(f"All spheres  ({len(self._entries)})")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        self.sphere_list.addItem(all_item)
        for sphere in magic_spheres():
            count = sum(
                entry["sphere"] == sphere["name"] for entry in self._entries
            )
            if play_mode and not count:
                continue
            item = QListWidgetItem(f"{sphere['name']}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, sphere["name"])
            self.sphere_list.addItem(item)
        universal_count = sum(entry["sphere"] == "Universal" for entry in self._entries)
        if universal_count:
            item = QListWidgetItem(f"Universal Drawbacks  ({universal_count})")
            item.setData(Qt.ItemDataRole.UserRole, "Universal")
            self.sphere_list.addItem(item)
        self.sphere_list.setCurrentRow(0)
        self.sphere_list.blockSignals(False)

        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("All categories", "")
        categories = sorted(
            {str(entry["category"]) for entry in self._entries},
            key=talent_category_sort_key,
        )
        for category in categories:
            self.category.addItem(category, category)
        self.category.blockSignals(False)
        self._refresh_results()

    def _show_selected_details(self) -> None:
        super()._show_selected_details()
        entry = self._current_entry()
        if entry is None or entry.get("category") in {"Base Sphere", "Drawback"}:
            return
        reason = magic_talent_restriction_reason(entry, self._magic_owned_spells)
        if reason:
            self.detail_automation.setText(f"Unavailable because of a sphere drawback:\n{reason}")
            self._update_add_button()

    def _entry_selectable(self, entry: dict) -> bool:
        return (
            super()._entry_selectable(entry)
            and not magic_talent_restriction_reason(entry, self._magic_owned_spells)
        )

    def _accept_selected(self, *_args) -> None:
        super()._accept_selected()


class TraditionalSpellCatalogDialog(QDialog):
    """Fast local browser for first- and third-party traditional spells."""

    RESULT_LIMIT = 350

    def __init__(
        self,
        preferred_classes: tuple[str, ...] = (),
        parent: QWidget | None = None,
        *,
        multi_select: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pathfinder Traditional Spell Catalog")
        self.resize(1320, 780)
        self.selected_entry: dict | None = None
        self.selected_entries: tuple[dict, ...] = ()
        self.multi_select = multi_select
        self.custom_requested = False
        self._entries = spell_entries()
        self._by_key = {str(entry["key"]): entry for entry in self._entries}
        self._index = CatalogSearchIndex(
            self._entries,
            description_fields=("summary", "description", "school", "source"),
        )
        layout = QVBoxLayout(self)
        heading = QLabel("TRADITIONAL SPELL CATALOG")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Pathfinder and third-party spells stay visibly separate. Name search is the fast default; "
            "description search is available when you need rules-text discovery. "
            + (
                "Click rows to select or deselect several spells before adding them."
                if multi_select
                else "Choose one spell for this operation."
            )
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        filters = QGridLayout()
        filters.setColumnStretch(1, 1)
        filters.setColumnStretch(5, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search spell names…")
        self.search.setClearButtonEnabled(True)
        self.search_mode = QComboBox()
        self.search_mode.addItem("Name", "name")
        self.search_mode.addItem("Description", "description")
        self.search_mode.addItem("Name and description", "both")
        self.source = QComboBox()
        self.source.addItem("All rulesets", "")
        for value in spell_sources():
            self.source.addItem(value, value)
        self.publisher = QComboBox()
        self.caster_class = QComboBox()
        self.caster_class.addItem("All class lists", "")
        class_names = sorted(
            {
                str(name)
                for entry in self._entries
                for name in (entry.get("class_levels") or {}).keys()
            },
            key=str.casefold,
        )
        preferred_folded = {normalized_spell_class_name(value) for value in preferred_classes}
        ordered_classes = [value for value in class_names if normalized_spell_class_name(value) in preferred_folded] + [
            value for value in class_names if normalized_spell_class_name(value) not in preferred_folded
        ]
        for value in ordered_classes:
            self.caster_class.addItem(value, value)
        if preferred_classes:
            preferred_index = next(
                (
                    index
                    for index in range(1, self.caster_class.count())
                    if normalized_spell_class_name(str(self.caster_class.itemData(index)))
                    in preferred_folded
                ),
                0,
            )
            self.caster_class.setCurrentIndex(preferred_index)
        self.level_filter = QComboBox()
        self.level_filter.addItem("All levels", -1)
        for level in range(10):
            self.level_filter.addItem(str(level), level)
        filters.addWidget(QLabel("Find"), 0, 0)
        filters.addWidget(self.search, 0, 1, 1, 5)
        filters.addWidget(QLabel("Search in"), 0, 6)
        filters.addWidget(self.search_mode, 0, 7)
        filters.addWidget(QLabel("Class list"), 1, 0)
        filters.addWidget(self.caster_class, 1, 1)
        filters.addWidget(QLabel("Spell level"), 1, 2)
        filters.addWidget(self.level_filter, 1, 3)
        filters.addWidget(QLabel("Ruleset"), 1, 4)
        filters.addWidget(self.source, 1, 5)
        filters.addWidget(QLabel("Publisher"), 1, 6)
        filters.addWidget(self.publisher, 1, 7)
        layout.addLayout(filters)
        self.result_status = QLabel()
        self.result_status.setObjectName("mutedText")
        layout.addWidget(self.result_status)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(("Spell name", "Level", "School", "Ruleset"))
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
            if multi_select
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        self.results.setWordWrap(False)
        self.results.verticalHeader().setVisible(False)
        self.results.verticalHeader().setDefaultSectionSize(28)
        header = self.results.horizontalHeader()
        header.setMinimumSectionSize(58)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results.setColumnWidth(2, 210)
        self.results.setMinimumWidth(650)
        self.results.setSortingEnabled(True)
        self.results.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.details.setMinimumWidth(380)
        splitter.addWidget(self.results)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes((800, 480))
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.add_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.add_button.setText("Add selected spell")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setEnabled(False)
        custom = buttons.addButton("Add custom spell…", QDialogButtonBox.ButtonRole.ActionRole)
        custom.clicked.connect(self._custom)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._debounce = DebouncedCallback(self._refresh, 180, self)
        self.search.textChanged.connect(self._debounce.schedule)
        self.search_mode.currentIndexChanged.connect(self._refresh)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.publisher.currentIndexChanged.connect(self._refresh)
        self.caster_class.currentIndexChanged.connect(self._refresh)
        self.level_filter.currentIndexChanged.connect(self._refresh)
        self.results.itemSelectionChanged.connect(self._show_details)
        self.results.itemSelectionChanged.connect(self._update_add_button)
        self.results.itemDoubleClicked.connect(lambda _item: self._accept())
        self._source_changed()

    def _source_changed(self) -> None:
        current = str(self.publisher.currentData() or "")
        source = str(self.source.currentData() or "")
        self.publisher.blockSignals(True)
        self.publisher.clear()
        self.publisher.addItem("All publishers", "")
        for value in spell_publishers(source or None):
            self.publisher.addItem(value, value)
        self.publisher.setCurrentIndex(max(0, self.publisher.findData(current)))
        self.publisher.blockSignals(False)
        self._refresh()

    def _refresh(self) -> None:
        selected_key = ""
        current = self._current_entry()
        if current is not None:
            selected_key = str(current.get("key") or "")
        source = str(self.source.currentData() or "")
        publisher = str(self.publisher.currentData() or "")
        class_name = str(self.caster_class.currentData() or "")
        level = int(self.level_filter.currentData() if self.level_filter.currentData() is not None else -1)

        def accepted(entry: dict) -> bool:
            if source and entry.get("source_group") != source:
                return False
            if publisher and entry.get("publisher") != publisher:
                return False
            matching_level = spell_level_for_class(entry, class_name) if class_name else None
            if class_name and matching_level is None:
                return False
            effective_level = matching_level if matching_level is not None else int(entry.get("level") or 0)
            return level < 0 or effective_level == level

        result = self._index.search(
            self.search.text(), str(self.search_mode.currentData() or "name"),
            predicate=accepted, limit=self.RESULT_LIMIT,
        )
        self.result_status.setText(
            f"{result.total:,} matching spells"
            + (f" · showing the first {self.RESULT_LIMIT:,}; narrow the search to see more" if result.limited else "")
        )
        self.results.setSortingEnabled(False)
        self.results.setRowCount(len(result.records))
        selected_row = -1
        for row, entry in enumerate(result.records):
            name = QTableWidgetItem(str(entry["name"]))
            name.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
            name.setToolTip(str(entry.get("summary") or entry.get("description") or ""))
            name_font = name.font()
            name_font.setBold(True)
            name.setFont(name_font)
            selected_level = spell_level_for_class(entry, class_name) if class_name else None
            if selected_level is None:
                selected_level = entry.get("level", 0)
            level_item = QTableWidgetItem()
            level_item.setData(Qt.ItemDataRole.EditRole, int(selected_level))
            level_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            values = (
                name,
                level_item,
                QTableWidgetItem(str(entry.get("school") or "")),
                QTableWidgetItem(str(entry.get("source_group") or "")),
            )
            for column, item in enumerate(values):
                self.results.setItem(row, column, item)
            if str(entry.get("key") or "") == selected_key:
                selected_row = row
        self.results.setSortingEnabled(True)
        self.results.sortItems(
            self.results.horizontalHeader().sortIndicatorSection(),
            self.results.horizontalHeader().sortIndicatorOrder(),
        )
        if result.records:
            if selected_row >= 0:
                matching_row = next(
                    (
                        row
                        for row in range(self.results.rowCount())
                        if str(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole)) == selected_key
                    ),
                    0,
                )
                self.results.selectRow(matching_row)
            else:
                self.results.selectRow(0)
        else:
            self.details.setHtml("<p>No spells match these filters.</p>")
            self._update_add_button()

    def _current_entry(self) -> dict | None:
        row = self.results.currentRow()
        if row < 0 or self.results.item(row, 0) is None:
            return None
        return self._by_key.get(str(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole)))

    def _show_details(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        class_levels = ", ".join(f"{name} {level}" for name, level in (entry.get("class_levels") or {}).items())
        descriptors = ", ".join(str(value) for value in entry.get("descriptors", ()))
        self.details.setHtml(
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('source_group') or ''))} · {html.escape(str(entry.get('publisher') or ''))}</b></p>"
            f"<p><b>School:</b> {html.escape(str(entry.get('school') or ''))}"
            + (f" ({html.escape(str(entry.get('subschool')))})" if entry.get("subschool") else "")
            + (f" [{html.escape(descriptors)}]" if descriptors else "")
            + f"<br><b>Class levels:</b> {html.escape(class_levels)}"
            f"<br><b>Casting:</b> {html.escape(str(entry.get('casting_time') or '—'))} · {html.escape(str(entry.get('components') or '—'))}"
            f"<br><b>Range / target:</b> {html.escape(str(entry.get('range') or '—'))} · {html.escape(str(entry.get('target') or '—'))}"
            f"<br><b>Duration:</b> {html.escape(str(entry.get('duration') or '—'))}"
            f"<br><b>Save / SR:</b> {html.escape(str(entry.get('saving_throw') or '—'))} · {html.escape(str(entry.get('spell_resistance') or '—'))}</p>"
            f"<p>{html.escape(str(entry.get('description') or '')).replace(chr(10), '<br>')}</p>"
            f"<p><a href='{html.escape(str(entry.get('source_url') or ''), quote=True)}'>Rules source</a></p>"
        )

    def _selected_entries(self) -> tuple[dict, ...]:
        if not self.multi_select:
            current = self._current_entry()
            return (current,) if current is not None else ()
        return _selected_catalog_entries(self.results, self._by_key)

    def _update_add_button(self) -> None:
        _update_catalog_add_button(
            self.add_button, self._selected_entries(), "spell", "spells"
        )

    def _custom(self) -> None:
        self.custom_requested = True
        self.accept()

    def _accept(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        self.selected_entries = entries
        self.selected_entry = entries[0]
        self.accept()


class PreparedSpellDialog(QDialog):
    """Choose a prepared class, a known/custom spell, and copy count."""

    def __init__(
        self,
        casters: tuple[PreparedCasterCapacity, ...],
        known_spells: tuple[Spell, ...],
        prepared_by_level: dict[tuple[int, int], int],
        custom_entry: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prepare custom spell" if custom_entry else "Prepare known spell")
        self._casters = {caster.class_level_id: caster for caster in casters}
        self._known_spells = tuple(known_spells)
        self._prepared_by_level = prepared_by_level
        self._custom_entry = custom_entry
        layout = QVBoxLayout(self)
        heading = QLabel("PREPARE SPELL")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Custom preparations are intentionally separate from Spells Known and are available for special rules."
            if custom_entry
            else "Only spells already present in Spells Known can be prepared here."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.caster = QComboBox()
        for profile in casters:
            self.caster.addItem(
                f"{profile.class_name} {profile.class_level}", profile.class_level_id
            )
        self.spell = QComboBox()
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 1)
        self.capacity = QLabel()
        self.capacity.setObjectName("mutedText")
        form.addRow("Casting class", self.caster)
        form.addRow("Spell", self.spell)
        form.addRow("Prepared copies", self.quantity)
        form.addRow("Level capacity", self.capacity)
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Prepare")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.caster.currentIndexChanged.connect(self._refresh_spells)
        self.spell.currentIndexChanged.connect(self._refresh_capacity)
        self._refresh_spells()

    def _entry_level(self, caster: PreparedCasterCapacity) -> int:
        if self._custom_entry is None:
            spell = next(
                (item for item in self._known_spells if item.id == self.spell.currentData()),
                None,
            )
            return spell.level if spell is not None else -1
        matched = spell_level_for_class(self._custom_entry, caster.class_name)
        return int(matched if matched is not None else self._custom_entry.get("level") or 0)

    def _refresh_spells(self) -> None:
        caster = self.selected_caster
        self.spell.blockSignals(True)
        self.spell.clear()
        if caster is not None and self._custom_entry is not None:
            level = self._entry_level(caster)
            self.spell.addItem(
                f"{self._custom_entry['name']} (custom, level {level})", "custom"
            )
        elif caster is not None:
            for spell in self._known_spells:
                if 0 <= spell.level < len(caster.slots) and caster.slots[spell.level] > 0:
                    self.spell.addItem(f"{spell.name} — level {spell.level}", spell.id)
        self.spell.blockSignals(False)
        self._refresh_capacity()

    def _refresh_capacity(self) -> None:
        caster = self.selected_caster
        level = self._entry_level(caster) if caster is not None and self.spell.count() else -1
        capacity = caster.slots[level] if caster is not None and 0 <= level < len(caster.slots) else 0
        already = self._prepared_by_level.get((caster.class_level_id, level), 0) if caster else 0
        open_slots = max(0, capacity - already)
        self.quantity.setRange(1, max(1, open_slots))
        self.capacity.setText(
            f"Level {level}: {already} prepared / {capacity} available · {open_slots} open"
            if level >= 0
            else "No eligible spell is available for this class."
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            caster is not None and self.spell.count() > 0 and open_slots > 0
        )

    @property
    def selected_caster(self) -> PreparedCasterCapacity | None:
        return self._casters.get(int(self.caster.currentData() or 0))

    @property
    def values(self) -> dict:
        caster = self.selected_caster
        if caster is None:
            return {}
        level = self._entry_level(caster)
        if self._custom_entry is not None:
            return {
                "class_level_id": caster.class_level_id,
                "known_spell_id": None,
                "name": str(self._custom_entry["name"]),
                "level": level,
                "prepared_count": self.quantity.value(),
                "catalog_key": str(self._custom_entry.get("key") or ""),
                "custom": True,
            }
        return {
            "class_level_id": caster.class_level_id,
            "known_spell_id": int(self.spell.currentData()),
            "prepared_count": self.quantity.value(),
            "custom": False,
        }


class MagicCatalogChoiceDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose magic catalog")
        self.choice = ""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("This character can use both traditional spells and Spheres magic. What do you want to add?"))
        traditional = QPushButton("Traditional Pathfinder spell")
        traditional.setObjectName("primaryButton")
        spheres = QPushButton("Magic sphere talent or effect")
        traditional.clicked.connect(lambda: self._choose("traditional"))
        spheres.clicked.connect(lambda: self._choose("spheres"))
        layout.addWidget(traditional)
        layout.addWidget(spheres)
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        layout.addWidget(cancel)

    def _choose(self, choice: str) -> None:
        self.choice = choice
        self.accept()

class MartialTalentDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, talent: MartialTalent | None = None
    ) -> None:
        super().__init__(parent)
        self.catalog_key = talent.catalog_key if talent is not None else ""
        self.catalog_category = talent.catalog_category if talent is not None else ""
        self.prerequisites = talent.prerequisites if talent is not None else ""
        self.source_url = talent.source_url if talent is not None else ""
        self.choice = talent.choice if talent is not None else ""
        self.effects = talent.effects if talent is not None else ()
        self.activation = talent.activation if talent is not None else "always"
        self.activation_note = talent.activation_note if talent is not None else ""
        self.setWindowTitle("Edit martial talent" if talent else "Add martial talent")
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Berserking, Barrage, Shield Sphere")
        self.sphere = QLineEdit()
        self.sphere.setPlaceholderText("e.g. Berserker, Barrage, Shield")
        self.talent_type = QComboBox()
        self.talent_type.addItems(MARTIAL_TALENT_TYPES)
        self.talent_type.setCurrentText("Talent")
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Description, prerequisites, action, effects, and reminders")
        self.notes.setFixedHeight(120)
        form.addRow("Talent", self.name)
        form.addRow("Sphere", self.sphere)
        form.addRow("Category", self.talent_type)
        form.addRow("Description / Notes", self.notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if talent is not None:
            self.name.setText(talent.name)
            self.sphere.setText(talent.sphere)
            self.talent_type.setCurrentText(talent.talent_type)
            self.notes.setPlainText(talent.notes)

    @property
    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "sphere": self.sphere.text().strip(),
            "talent_type": self.talent_type.currentText(),
            "notes": self.notes.toPlainText(),
            "catalog_key": self.catalog_key,
            "catalog_category": self.catalog_category,
            "prerequisites": self.prerequisites,
            "source_url": self.source_url,
            "choice": self.choice,
            "effects": self.effects,
            "activation": self.activation,
            "activation_note": self.activation_note,
        }

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Talent required", "Enter a martial talent name.")
            return
        self.accept()

class SequenceOptionDialog(QDialog):
    def __init__(
        self,
        option_type: str,
        parent: QWidget | None = None,
        option: SequenceOption | None = None,
    ) -> None:
        super().__init__(parent)
        self.option_type = option_type
        self.setWindowTitle(
            f"Edit {option_type.lower()}" if option else f"Add {option_type.lower()}"
        )
        self.resize(540, 400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(
            {"Opener": "e.g. Attack", "Link": "e.g. Close the Gap", "Finisher": "e.g. Certain Strike"}[option_type]
        )
        self.sphere = QLineEdit()
        self.sphere.setPlaceholderText("Class feature, combat sphere, or magic sphere")
        self.minimum_links = QSpinBox()
        self.minimum_links.setRange(0, 99)
        self.minimum_links.setEnabled(option_type == "Finisher")
        self.action = QLineEdit()
        self.action.setPlaceholderText("e.g. Swift action, Immediate action, Triggered")
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Trigger, effect, requirements, and reminders")
        self.notes.setFixedHeight(140)
        form.addRow(option_type, self.name)
        form.addRow("Source / Sphere", self.sphere)
        form.addRow("Minimum links", self.minimum_links)
        form.addRow("Action", self.action)
        form.addRow("Description", self.notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if option is not None:
            self.name.setText(option.name)
            self.sphere.setText(option.sphere)
            self.minimum_links.setValue(option.minimum_links)
            self.action.setText(option.action)
            self.notes.setPlainText(option.notes)

    @property
    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "option_type": self.option_type,
            "sphere": self.sphere.text().strip(),
            "minimum_links": self.minimum_links.value(),
            "action": self.action.text().strip(),
            "notes": self.notes.toPlainText(),
        }

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(
                self,
                f"{self.option_type} required",
                f"Enter an {self.option_type.lower()} name.",
            )
            return
        self.accept()

class ClassFeatureStateDialog(QDialog):
    """Shared editor for resource-like class feature building blocks."""

    def __init__(
        self,
        resource: ResolvedClassFeatureResource,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.resource = resource
        self.setWindowTitle(f"Configure {resource.name}")
        self.resize(620, 560)
        layout = QVBoxLayout(self)
        heading = QLabel(resource.name.upper())
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        description = QLabel(resource.description)
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.current = QSpinBox()
        self.current.setRange(0, 99999)
        self.current.setValue(resource.current)
        self.maximum_adjustment = QSpinBox()
        self.maximum_adjustment.setRange(-9999, 9999)
        self.maximum_adjustment.setValue(resource.state.maximum_adjustment)
        self.maximum_override = QLineEdit()
        self.maximum_override.setPlaceholderText("Automatic maximum")
        if resource.state.maximum_override is not None:
            self.maximum_override.setText(str(resource.state.maximum_override))
        self.active = QCheckBox("Currently active")
        self.active.setChecked(resource.active)
        form.addRow("Current / remaining", self.current)
        form.addRow("Maximum adjustment", self.maximum_adjustment)
        form.addRow("Maximum override", self.maximum_override)
        form.addRow("State", self.active)
        layout.addLayout(form)

        self.choice_list = QListWidget()
        self.choice_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        selected = {value.casefold() for value in resource.choices}
        for option in resource.choice_options:
            item = QListWidgetItem(option)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if option.casefold() in selected
                else Qt.CheckState.Unchecked
            )
            self.choice_list.addItem(item)
        self.choice_list.itemChanged.connect(self._limit_choices)
        self.custom_choices = QLineEdit()
        extras = [
            value
            for value in resource.choices
            if value.casefold() not in {option.casefold() for option in resource.choice_options}
        ]
        self.custom_choices.setText(", ".join(extras))
        self.custom_choices.setPlaceholderText("Optional custom choice, comma-separated")
        if resource.choice_options or resource.custom_choice_label:
            label = QLabel(
                f"Selections (up to {resource.maximum_choices})"
                if resource.maximum_choices > 1
                else (resource.custom_choice_label or "Selection")
            )
            label.setObjectName("minorTitle")
            layout.addWidget(label)
            if resource.choice_options:
                layout.addWidget(self.choice_list)
            else:
                self.choice_list.hide()
            layout.addWidget(self.custom_choices)
            if resource.custom_choice_label:
                self.custom_choices.setPlaceholderText(resource.custom_choice_label)
        else:
            self.choice_list.hide()
            self.custom_choices.hide()

        self.notes = QPlainTextEdit(resource.state.notes)
        self.notes.setPlaceholderText("Character-specific reminders or house-rule notes")
        self.notes.setFixedHeight(90)
        layout.addWidget(QLabel("Notes"))
        layout.addWidget(self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _checked_choices(self) -> list[str]:
        return [
            self.choice_list.item(index).text()
            for index in range(self.choice_list.count())
            if self.choice_list.item(index).checkState() == Qt.CheckState.Checked
        ]

    def _limit_choices(self, changed: QListWidgetItem) -> None:
        maximum = self.resource.maximum_choices
        if maximum and len(self._checked_choices()) > maximum:
            self.choice_list.blockSignals(True)
            changed.setCheckState(Qt.CheckState.Unchecked)
            self.choice_list.blockSignals(False)

    @property
    def values(self) -> dict:
        choices = self._checked_choices()
        choices.extend(
            value.strip()
            for value in self.custom_choices.text().split(",")
            if value.strip()
        )
        maximum = self.maximum_override.text().strip()
        return {
            "current_value": self.current.value(),
            "maximum_adjustment": self.maximum_adjustment.value(),
            "maximum_override": None if not maximum else int(maximum),
            "active": self.active.isChecked(),
            "choices_json": json.dumps(list(dict.fromkeys(choices))),
            "notes": self.notes.toPlainText(),
        }

    def _accept_if_valid(self) -> None:
        maximum = self.maximum_override.text().strip()
        if maximum:
            try:
                value = int(maximum)
            except ValueError:
                QMessageBox.warning(self, "Invalid maximum", "Enter a whole number or leave the override blank.")
                return
            if value < 0:
                QMessageBox.warning(self, "Invalid maximum", "Maximum cannot be negative.")
                return
        self.accept()


class SpellDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, spell: Spell | None = None) -> None:
        super().__init__(parent)
        self.catalog_key = spell.catalog_key if spell is not None else ""
        self.catalog_category = spell.catalog_category if spell is not None else ""
        self.prerequisites = spell.prerequisites if spell is not None else ""
        self.source_url = spell.source_url if spell is not None else ""
        self.choice = spell.choice if spell is not None else ""
        self.effects = spell.effects if spell is not None else ()
        self.activation = spell.activation if spell is not None else "always"
        self.activation_note = spell.activation_note if spell is not None else ""
        self.setWindowTitle("Edit spell or ability" if spell else "Add spell or ability")
        self.resize(620, 680)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Fireball, Teleport, Destructive Blast")
        self.system = QComboBox()
        self.system.addItems(SPELL_SYSTEMS)
        self.level = QSpinBox()
        self.level.setRange(0, 9)
        self.school_or_sphere = QLineEdit()
        self.school_or_sphere.setPlaceholderText("School, discipline, or magic sphere")
        self.uses_max = QSpinBox()
        self.uses_max.setRange(0, 999)
        self.uses_max.setSpecialValueText("At will")
        self.uses_used = QSpinBox()
        self.uses_used.setRange(0, 0)
        self.casting_time = QLineEdit()
        self.casting_time.setPlaceholderText("e.g. Standard action")
        self.range = QLineEdit()
        self.range.setPlaceholderText("e.g. Close, Touch, 30 ft")
        self.duration = QLineEdit()
        self.duration.setPlaceholderText("e.g. Instantaneous, 1 round/level")
        self.save = QLineEdit()
        self.save.setPlaceholderText("e.g. Reflex half, Will negates")
        self.spell_resistance = QLineEdit()
        self.spell_resistance.setPlaceholderText("e.g. Yes, No")
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Effect, components, costs, augmentations, and reminders")
        self.notes.setFixedHeight(130)
        form.addRow("Spell / Ability", self.name)
        form.addRow("System", self.system)
        form.addRow("Level", self.level)
        form.addRow("School / Sphere", self.school_or_sphere)
        form.addRow("Uses available", self.uses_max)
        form.addRow("Uses already spent", self.uses_used)
        form.addRow("Casting time", self.casting_time)
        form.addRow("Range", self.range)
        form.addRow("Duration", self.duration)
        form.addRow("Saving throw", self.save)
        form.addRow("Spell resistance", self.spell_resistance)
        form.addRow("Description / Notes", self.notes)
        layout.addLayout(form)
        self.uses_max.valueChanged.connect(self._uses_max_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if spell is not None:
            self.name.setText(spell.name)
            self.system.setCurrentText(spell.system)
            self.level.setValue(spell.level)
            self.school_or_sphere.setText(spell.school_or_sphere)
            self.uses_max.setValue(spell.uses_max)
            self.uses_used.setValue(spell.uses_used)
            self.casting_time.setText(spell.casting_time)
            self.range.setText(spell.range)
            self.duration.setText(spell.duration)
            self.save.setText(spell.save)
            self.spell_resistance.setText(spell.spell_resistance)
            self.notes.setPlainText(spell.notes)
        self._uses_max_changed(self.uses_max.value())

    def _uses_max_changed(self, maximum: int) -> None:
        self.uses_used.setMaximum(maximum)
        self.uses_used.setEnabled(maximum > 0)
        if maximum == 0:
            self.uses_used.setValue(0)

    @property
    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "system": self.system.currentText(),
            "level": self.level.value(),
            "school_or_sphere": self.school_or_sphere.text().strip(),
            "uses_max": self.uses_max.value(),
            "uses_used": self.uses_used.value(),
            "casting_time": self.casting_time.text().strip(),
            "range": self.range.text().strip(),
            "duration": self.duration.text().strip(),
            "save": self.save.text().strip(),
            "spell_resistance": self.spell_resistance.text().strip(),
            "notes": self.notes.toPlainText(),
            "catalog_key": self.catalog_key,
            "catalog_category": self.catalog_category,
            "prerequisites": self.prerequisites,
            "source_url": self.source_url,
            "choice": self.choice,
            "effects": self.effects,
            "activation": self.activation,
            "activation_note": self.activation_note,
        }

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Spell required", "Enter a spell or magic ability name.")
            return
        self.accept()

class SkillDialog(QDialog):
    def __init__(
        self,
        skill_name: str,
        state: SkillState,
        parent: QWidget | None = None,
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
        effective_class_skill: bool | None = None,
        specialty: str = "",
        base_skill_key: str = "",
    ) -> None:
        super().__init__(parent)
        self.skill_key = state.skill_key
        self.base_skill_key = base_skill_key
        self.setWindowTitle(f"Edit {skill_name}")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.ranks = QSpinBox()
        self.ranks.setRange(0, 999)
        self.ranks.setValue(state.ranks)
        self.class_skill = QCheckBox("Class skill")
        self.class_skill.setChecked(
            state.class_skill
            if effective_class_skill is None else effective_class_skill
        )
        self.ability = QComboBox()
        self.ability.addItem("Default ability", "")
        for key, name, abbreviation in ABILITIES:
            self.ability.addItem(f"{name} ({abbreviation})", key)
        self.ability.setCurrentIndex(
            max(0, self.ability.findData(state.ability_override))
        )
        self.misc_bonus = _formula_number_field(
            -99,
            99,
            state.misc_bonus,
            "misc_bonus",
            formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.notes = QLineEdit(state.notes)
        self.specialty = QLineEdit(specialty)
        self.specialty.setPlaceholderText(
            "For example: Alchemy, Oratory, or Sailor"
        )
        form.addRow("Ranks", self.ranks)
        form.addRow("", self.class_skill)
        if self.base_skill_key:
            form.addRow("Specialization", self.specialty)
        form.addRow("Ability modifier", self.ability)
        form.addRow("Miscellaneous bonus", self.misc_bonus)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def state(self) -> SkillState:
        return SkillState(
            self.skill_key,
            self.ranks.value(),
            self.class_skill.isChecked(),
            int(self.misc_bonus.value()),
            self.notes.text(),
            str(self.ability.currentData() or ""),
            self.class_skill.isChecked(),
        )

    @property
    def specialization(self) -> str:
        return self.specialty.text().strip() if self.base_skill_key else ""

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {"misc_bonus": self.misc_bonus.expression}

    def _accept_if_valid(self) -> None:
        try:
            self.misc_bonus.value()
        except FormulaError as error:
            QMessageBox.warning(self, "Invalid skill bonus", str(error))
            return
        self.accept()

class ConditionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add condition")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.condition = QComboBox()
        self.condition.addItems(sorted(CONDITION_PRESETS))
        for index in range(self.condition.count()):
            name = self.condition.itemText(index)
            rules = CONDITION_RULES_TEXT.get(name, "")
            if rules:
                self.condition.setItemData(index, rules, Qt.ItemDataRole.ToolTipRole)
        self.notes_input = QLineEdit()
        form.addRow("Condition", self.condition)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def name(self) -> str:
        return self.condition.currentText()

    @property
    def notes(self) -> str:
        return self.notes_input.text()


class OngoingEffectDialog(QDialog):
    """Create one temporary spell/sphere effect and optional stat modifier."""

    def __init__(
        self,
        parent: QWidget | None = None,
        effect: OngoingEffect | None = None,
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit ongoing effect" if effect else "Add ongoing effect")
        self.resize(620, 440)
        layout = QVBoxLayout(self)
        heading = QLabel("ONGOING SPELL / SPHERE EFFECT")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        intro = QLabel(
            "Track a temporary effect independently of conditions. Optionally give it "
            "one typed sheet modifier; rules that cannot be calculated stay in its notes."
        )
        intro.setObjectName("mutedText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.name = QLineEdit()
        self.source_type = QComboBox()
        self.source_type.addItems(ONGOING_EFFECT_SOURCE_TYPES)
        self.duration = QLineEdit()
        self.duration.setPlaceholderText("Rounds remaining, concentration, encounter…")
        self.target = QComboBox()
        self.target.addItem("Rules / notes only", "")
        for target in STAT_TARGETS:
            self.target.addItem(
                FEAT_TARGET_LABELS.get(target, target.replace("_", " ").title()), target
            )
        self.bonus_type = QComboBox()
        self.bonus_type.addItems(BONUS_TYPES)
        self.value = _formula_number_field(
            -9999,
            9999,
            int(getattr(effect, "value", 0)),
            "value",
            formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(100)
        form.addRow("Name", self.name)
        form.addRow("Source", self.source_type)
        form.addRow("Duration / remaining", self.duration)
        form.addRow("Sheet statistic", self.target)
        form.addRow("Bonus type", self.bonus_type)
        form.addRow("Value", self.value)
        form.addRow("Rules / notes", self.notes)
        layout.addLayout(form)
        self.target.currentIndexChanged.connect(self._target_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if effect is not None:
            self.name.setText(effect.name)
            self.source_type.setCurrentText(effect.source_type)
            self.duration.setText(effect.duration)
            self.target.setCurrentIndex(max(0, self.target.findData(effect.target)))
            self.bonus_type.setCurrentText(effect.bonus_type)
            self.notes.setPlainText(effect.notes)
        self._target_changed()

    def _target_changed(self) -> None:
        calculated = bool(self.target.currentData())
        self.bonus_type.setEnabled(calculated)
        self.value.setEnabled(calculated)

    @property
    def values(self) -> dict:
        target = str(self.target.currentData() or "")
        return {
            "name": self.name.text().strip(),
            "source_type": self.source_type.currentText(),
            "duration": self.duration.text().strip(),
            "target": target,
            "bonus_type": self.bonus_type.currentText(),
            "value": int(self.value.value()) if target else 0,
            "notes": self.notes.toPlainText().strip(),
        }

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {"value": self.value.expression if self.target.currentData() else ""}

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Effect required", "Enter an effect name.")
            return
        if self.target.currentData():
            try:
                self.value.value()
            except FormulaError as error:
                QMessageBox.warning(self, "Invalid effect value", str(error))
                return
        self.accept()

class SphereStatisticDialog(QDialog):
    def __init__(
        self,
        statistic: SphereStatistic,
        parent: QWidget | None = None,
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{statistic.sphere} sphere statistics")
        layout = QVBoxLayout(self)
        heading = QLabel(statistic.sphere.upper())
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Adjust only this sphere. The base caster level, casting ability modifier, "
            "and global save-DC adjustment still apply automatically."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.caster_level_bonus = _formula_number_field(
            -99,
            99,
            statistic.caster_level_bonus,
            "caster_level_bonus",
            formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.dc_bonus = _formula_number_field(
            -99,
            99,
            statistic.dc_bonus,
            "dc_bonus",
            formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.notes = QLineEdit(statistic.notes)
        form.addRow("Caster-level adjustment", self.caster_level_bonus)
        form.addRow("Save-DC adjustment", self.dc_bonus)
        form.addRow("Source / notes", self.notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def values(self) -> dict:
        return {
            "caster_level_bonus": int(self.caster_level_bonus.value()),
            "dc_bonus": int(self.dc_bonus.value()),
            "notes": self.notes.text(),
        }

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {
            "caster_level_bonus": self.caster_level_bonus.expression,
            "dc_bonus": self.dc_bonus.expression,
        }

    def _accept_if_valid(self) -> None:
        try:
            self.caster_level_bonus.value()
            self.dc_bonus.value()
        except FormulaError as error:
            QMessageBox.warning(self, "Invalid sphere statistic", str(error))
            return
        self.accept()

class WornSlotsDialog(QDialog):
    """Small character-scoped editor for the ordered worn-slot catalog."""

    def __init__(self, slots: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit worn-item slots")
        self.resize(430, 520)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Each slot can hold one active item. Drag slots to arrange their saved order."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.slot_list = TranslucentReorderListWidget()
        self.slot_list.addItems(slots)
        layout.addWidget(self.slot_list, 1)
        add_row = QHBoxLayout()
        self.slot_name = QLineEdit()
        self.slot_name.setPlaceholderText("New slot name")
        self.slot_name.returnPressed.connect(self._add_slot)
        add = QPushButton("Add slot")
        add.clicked.connect(self._add_slot)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove_slot)
        add_row.addWidget(self.slot_name, 1)
        add_row.addWidget(add)
        add_row.addWidget(remove)
        layout.addLayout(add_row)
        reset = QPushButton("Restore default slots")
        reset.clicked.connect(self._restore_defaults)
        layout.addWidget(reset)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def slots(self) -> tuple[str, ...]:
        return tuple(
            self.slot_list.item(index).text()
            for index in range(self.slot_list.count())
        )

    def _add_slot(self) -> None:
        name = self.slot_name.text().strip()
        if not name:
            return
        if name.casefold() in {value.casefold() for value in self.slots}:
            QMessageBox.warning(self, "Duplicate slot", f"{name} already exists.")
            return
        self.slot_list.addItem(name)
        values = sorted(self.slots, key=str.casefold)
        self.slot_list.clear()
        self.slot_list.addItems(values)
        matches = self.slot_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if matches:
            self.slot_list.setCurrentItem(matches[0])
        self.slot_name.clear()

    def _remove_slot(self) -> None:
        row = self.slot_list.currentRow()
        if row >= 0:
            self.slot_list.takeItem(row)

    def _restore_defaults(self) -> None:
        self.slot_list.clear()
        self.slot_list.addItems(slot for slot in WORN_SLOTS if slot)


class EquipmentDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        item=None,
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
        worn_slots: tuple[str, ...] | None = None,
        enchantments: tuple = (),
        contained_items: tuple = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            f"Edit Item — {getattr(item, 'name', '')}" if item is not None else "Create Item"
        )
        self.resize(1080, 720)
        self._saved_formulas = formulas or {}
        self._catalog_key = str(getattr(item, "catalog_key", ""))
        self._catalog_source = str(getattr(item, "catalog_source", ""))
        self._choices_json = str(getattr(item, "choices_json", "{}"))
        self._automation_json = str(getattr(item, "automation_json", ""))
        self._item_id = int(getattr(item, "id", -1))
        self._enchantments = tuple(enchantments)
        self._contained_items = tuple(contained_items)
        self._fallback_description = str(getattr(item, "notes", "") or "")
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.item_editor_splitter = splitter
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItem("Custom", "")
        for preset in entries("armor"):
            self.preset.addItem(preset["name"], preset["key"])
        self.name = QLineEdit()
        self.category = QComboBox()
        self.category.addItems(EQUIPMENT_CATEGORIES)
        self.quantity = QSpinBox()
        self.quantity.setRange(0, 9999)
        self.quantity.setValue(1)
        self.weight = _formula_number_field(
            0,
            99999,
            float(getattr(item, "weight", 0)),
            "weight",
            self._saved_formulas,
            formula_evaluator,
            formula_suggestions,
            integer=False,
        )
        self.value_gp = _formula_number_field(
            0,
            999_999_999,
            float(getattr(item, "value_gp", 0)),
            "value_gp",
            self._saved_formulas,
            formula_evaluator,
            formula_suggestions,
            integer=False,
        )
        self.equipped = QCheckBox("Currently equipped")
        self.state = QComboBox()
        for value in EQUIPMENT_STATES:
            self.state.addItem(value.replace("_", " ").title(), value)
        self.slot = QComboBox()
        for slot in ("", *(worn_slots or tuple(slot for slot in WORN_SLOTS if slot))):
            self.slot.addItem(slot or "Not worn", slot)
        self.ac_bonus = _formula_number_field(
            0,
            99,
            int(getattr(item, "ac_bonus", 0)),
            "ac_bonus",
            self._saved_formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.bonus_type = QComboBox()
        self.bonus_type.addItems(EQUIPMENT_BONUS_TYPES)
        max_dex_fallback = getattr(item, "max_dex_bonus", None)
        self.max_dex = _formula_number_field(
            -1,
            99,
            -1 if max_dex_fallback is None else int(max_dex_fallback),
            "max_dex_bonus",
            self._saved_formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.max_dex.editor.setPlaceholderText("-1 for no limit, or =formula")
        self.armor_check_penalty = _formula_number_field(
            0,
            99,
            int(getattr(item, "armor_check_penalty", 0)),
            "armor_check_penalty",
            self._saved_formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.notes = QLineEdit()
        self.enhancement_bonus = _formula_number_field(
            0,
            20,
            int(getattr(item, "enhancement_bonus", 0)),
            "enhancement_bonus",
            self._saved_formulas,
            formula_evaluator,
            formula_suggestions,
        )
        self.masterwork = QCheckBox("Masterwork")
        self.weapon_damage_dice = QLineEdit(); self.weapon_damage_type = QLineEdit()
        self.weapon_critical = QLineEdit(); self.weapon_range = QLineEdit()
        form.addRow("Armor/shield preset", self.preset)
        form.addRow("Item", self.name)
        form.addRow("Category", self.category)
        form.addRow("Quantity", self.quantity)
        form.addRow("Weight each (lb)", self.weight)
        form.addRow("Base value each (gp)", self.value_gp)
        form.addRow("Item state", self.state)
        form.addRow("Worn slot", self.slot)
        form.addRow("AC bonus", self.ac_bonus)
        form.addRow("AC bonus type", self.bonus_type)
        form.addRow("Maximum Dex bonus", self.max_dex)
        form.addRow("Armor check penalty", self.armor_check_penalty)
        form.addRow("Enhancement bonus", self.enhancement_bonus)
        form.addRow("", self.masterwork)
        self.market_price = QLabel()
        self.market_price.setObjectName("focusReady")
        self.market_price.setWordWrap(True)
        form.addRow("Calculated market price", self.market_price)
        form.addRow("Weapon damage dice", self.weapon_damage_dice)
        form.addRow("Weapon damage type", self.weapon_damage_type)
        form.addRow("Weapon critical", self.weapon_critical)
        form.addRow("Weapon range", self.weapon_range)
        form.addRow("Notes", self.notes)
        editor_layout.addLayout(form)
        editor_layout.addStretch()
        splitter.addWidget(editor)

        description_box = QWidget()
        description_layout = QVBoxLayout(description_box)
        description_layout.setContentsMargins(10, 0, 0, 0)
        description_title = QLabel("ITEM DESCRIPTION")
        description_title.setObjectName("sectionTitle")
        self.item_description = QTextBrowser()
        self.item_description.setOpenExternalLinks(True)
        self.item_description.setMinimumWidth(340)
        description_layout.addWidget(description_title)
        description_layout.addWidget(self.item_description, 1)
        splitter.addWidget(description_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes((650, 410))
        layout.addWidget(splitter, 1)
        self.category.currentTextChanged.connect(self._category_changed)
        self.category.currentTextChanged.connect(self._update_market_price)
        self.name.textChanged.connect(self._update_market_price)
        self.value_gp.editor.textChanged.connect(self._update_market_price)
        self.enhancement_bonus.editor.textChanged.connect(self._update_market_price)
        self.masterwork.toggled.connect(self._update_market_price)
        self.name.textChanged.connect(self._refresh_item_description)
        self.notes.textChanged.connect(self._refresh_item_description)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.state.currentIndexChanged.connect(
            lambda: self.equipped.setChecked(str(self.state.currentData()) != "stored")
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._category_changed(self.category.currentText())
        if item is not None:
            preset = entry_by_name("armor", item.name)
            if preset is not None:
                self.preset.setCurrentIndex(self.preset.findData(preset["key"]))
            self.name.setText(item.name)
            self.category.setCurrentText(item.category)
            self.quantity.setValue(item.quantity)
            self.weight.set_expression(
                self._saved_formulas.get("weight", ""), item.weight
            )
            self.value_gp.set_expression(
                self._saved_formulas.get("value_gp", ""), item.value_gp
            )
            self.equipped.setChecked(item.equipped)
            self.state.setCurrentIndex(max(0, self.state.findData(item.state)))
            self.slot.setCurrentIndex(max(0, self.slot.findData(item.slot)))
            self.ac_bonus.set_expression(
                self._saved_formulas.get("ac_bonus", ""), item.ac_bonus
            )
            self.bonus_type.setCurrentText(item.bonus_type)
            self.max_dex.set_expression(
                self._saved_formulas.get("max_dex_bonus", ""),
                -1 if item.max_dex_bonus is None else item.max_dex_bonus,
            )
            self.armor_check_penalty.set_expression(
                self._saved_formulas.get("armor_check_penalty", ""),
                item.armor_check_penalty,
            )
            self.notes.setText(item.notes)
            self.enhancement_bonus.set_expression(
                self._saved_formulas.get("enhancement_bonus", ""),
                item.enhancement_bonus,
            )
            self.masterwork.setChecked(item.masterwork)
            self.weapon_damage_dice.setText(item.weapon_damage_dice)
            self.weapon_damage_type.setText(item.weapon_damage_type)
            self.weapon_critical.setText(item.weapon_critical)
            self.weapon_range.setText(item.weapon_range)
        self._update_market_price()
        self._refresh_item_description()

    def _refresh_item_description(self, *_args) -> None:
        entry = item_entry(self._catalog_key) if self._catalog_key else None
        if entry is None:
            preset_key = str(self.preset.currentData() or "")
            entry = entry_by_key("armor", preset_key) if preset_key else None
        description = str(
            (entry or {}).get("description")
            or self.notes.text().strip()
            or self._fallback_description
            or ""
        )
        source = str((entry or {}).get("source") or self._catalog_source or "")
        source_url = str((entry or {}).get("source_url") or "")
        source_html = f"<p><b>Source:</b> {html.escape(source)}</p>" if source else ""
        link_html = (
            f"<p><a href='{html.escape(source_url, quote=True)}'>Open rules source</a></p>"
            if source_url else ""
        )
        contents_rows = "".join(
            "<tr>"
            f"<td>{html.escape(value.category)}</td>"
            f"<td>{html.escape(value.subcategory)}</td>"
            f"<td>{html.escape(value.item.name)}</td>"
            f"<td>{int(value.item.quantity)}</td>"
            "</tr>"
            for value in self._contained_items
        )
        contents_html = (
            "<hr><h3>Contents</h3>"
            "<table cellspacing='6'><tr><th>Category</th><th>Type</th>"
            "<th>Item</th><th>Qty.</th></tr>"
            f"{contents_rows}</table>"
            if contents_rows else ""
        )
        self.item_description.setHtml(
            f"<h2>{html.escape(self.name.text().strip() or 'Item')}</h2>"
            f"<p>{html.escape(description).replace(chr(10), '<br>')}</p>"
            f"{source_html}{link_html}{contents_html}"
        )

    def _update_market_price(self, *_args) -> None:
        try:
            item = SimpleNamespace(
                id=self._item_id,
                name=self.name.text().strip(),
                category=self.category.currentText(),
                value_gp=float(self.value_gp.value()),
                enhancement_bonus=int(self.enhancement_bonus.value()),
                masterwork=self.masterwork.isChecked(),
                catalog_key=self._catalog_key,
            )
            price = item_price_breakdown(item, self._enchantments)
        except (FormulaError, TypeError, ValueError):
            self.market_price.setText("—")
            return
        parts = []
        if price.masterwork_gp:
            parts.append(f"masterwork +{price.masterwork_gp:g} gp")
        if price.enhancement_gp:
            parts.append(f"magic {price.enhancement_gp:+g} gp")
        if price.flat_properties_gp:
            parts.append(f"properties +{price.flat_properties_gp:g} gp")
        detail = f" ({'; '.join(parts)})" if parts else ""
        self.market_price.setText(f"{price.total_gp:g} gp{detail}")

    def _preset_changed(self) -> None:
        preset = entry_by_key("armor", str(self.preset.currentData() or ""))
        if preset is None:
            return
        self.name.setText(preset["name"])
        self._refresh_item_description()
        self.category.setCurrentText(preset["category"])
        self.quantity.setValue(1)
        self.weight.set_value(float(preset["weight"]))
        self.equipped.setChecked(True)
        self.slot.setCurrentIndex(
            self.slot.findData("Armor" if preset["category"] == "Armor" else "Shield")
        )
        self.ac_bonus.set_value(int(preset["ac_bonus"]))
        self.bonus_type.setCurrentText(preset["bonus_type"])
        self.max_dex.set_value(
            -1 if preset["max_dex_bonus"] is None else int(preset["max_dex_bonus"])
        )
        self.armor_check_penalty.set_value(int(preset["armor_check_penalty"]))

    def _category_changed(self, category: str) -> None:
        if category == "Armor":
            self.bonus_type.setCurrentText("armor")
            self.equipped.setChecked(True)
            self.slot.setCurrentIndex(self.slot.findData("Armor"))
            self.state.setCurrentIndex(self.state.findData("armor"))
        elif category == "Shield":
            self.bonus_type.setCurrentText("shield")
            self.equipped.setChecked(True)
            self.slot.setCurrentIndex(self.slot.findData("Shield"))
            self.state.setCurrentIndex(self.state.findData("shield"))
        elif category == "Weapon":
            self.state.setCurrentIndex(self.state.findData("wielded"))

    @property
    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "category": self.category.currentText(),
            "quantity": self.quantity.value(),
            "weight": float(self.weight.value()),
            "equipped": str(self.state.currentData() or "stored") != "stored",
            "ac_bonus": int(self.ac_bonus.value()),
            "bonus_type": self.bonus_type.currentText(),
            "max_dex_bonus": (
                None if self.max_dex.value() == -1 else int(self.max_dex.value())
            ),
            "notes": self.notes.text(),
            "armor_check_penalty": int(self.armor_check_penalty.value()),
            "slot": str(self.slot.currentData() or ""),
            "value_gp": float(self.value_gp.value()),
            "state": str(self.state.currentData() or "stored"),
            "choices_json": self._choices_json,
            "automation_json": self._automation_json,
            "enhancement_bonus": int(self.enhancement_bonus.value()),
            "masterwork": self.masterwork.isChecked(),
            "weapon_damage_dice": self.weapon_damage_dice.text().strip(),
            "weapon_damage_type": self.weapon_damage_type.text().strip(),
            "weapon_critical": self.weapon_critical.text().strip(),
            "weapon_range": self.weapon_range.text().strip(),
        }

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {
            "weight": self.weight.expression,
            "value_gp": self.value_gp.expression,
            "ac_bonus": self.ac_bonus.expression,
            "max_dex_bonus": self.max_dex.expression,
            "armor_check_penalty": self.armor_check_penalty.expression,
            "enhancement_bonus": self.enhancement_bonus.expression,
        }

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Item required", "Enter an item name.")
            return
        try:
            self.weight.value()
            self.value_gp.value()
            self.ac_bonus.value()
            self.max_dex.value()
            self.armor_check_penalty.value()
            self.enhancement_bonus.value()
        except FormulaError as error:
            QMessageBox.warning(self, "Invalid equipment value", str(error))
            return
        self.accept()


class ItemCatalogDialog(CatalogBasketDialogMixin, QDialog):
    """Shared categorized browser for Pathfinder and Spheres equipment."""

    RESULT_LIMIT = 250
    SEARCH_DELAY_MS = 220

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pathfinder & Spheres Item Catalog")
        self.resize(1640, 840)
        self.selected_entry: dict | None = None
        self.selected_entries: tuple[dict, ...] = ()
        self.custom_requested = False
        self._entries = item_entries()
        self._search_index = CatalogSearchIndex(self._entries)
        layout = QVBoxLayout(self)
        heading = QLabel("EQUIPMENT & ITEM CATALOG")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        intro = QLabel(
            "Pathfinder and Spheres items remain separate, then are grouped by item family and category. "
            "Single-click previews; double-click adds 1, Ctrl+click adds 10, and Shift+click asks for a quantity. "
            "Use the same gestures in the selection queue to remove quantities."
        )
        intro.setObjectName("mutedText"); intro.setWordWrap(True); layout.addWidget(intro)
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search item names…")
        self.search_mode = QComboBox()
        self.search_mode.addItem("Name", "name")
        self.search_mode.addItem("Description", "description")
        self.search_mode.addItem("Name and description", "both")
        self.source = QComboBox(); self.source.addItem("All rulesets", "")
        for value in item_sources(): self.source.addItem(value, value)
        self.family = QComboBox(); self.category = QComboBox()
        self.price_range = OptionalNumericRangeFilter(
            "Min Gold", "Max Gold", suffix=" gp"
        )
        filters.addWidget(QLabel("Find")); filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Search in")); filters.addWidget(self.search_mode)
        filters.addWidget(QLabel("Ruleset")); filters.addWidget(self.source)
        filters.addWidget(QLabel("Family")); filters.addWidget(self.family)
        filters.addWidget(QLabel("Category")); filters.addWidget(self.category)
        filters.addWidget(self.price_range)
        layout.addLayout(filters)
        self.result_status = QLabel()
        self.result_status.setObjectName("mutedText")
        layout.addWidget(self.result_status)
        body = QHBoxLayout()
        self.results = QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(("Item", "Ruleset", "Family", "Category", "Price"))
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.details = QTextBrowser(); self.details.setOpenExternalLinks(True); self.details.setMinimumWidth(390)
        body.addWidget(self.results, 3); body.addWidget(self.details, 2)
        self._install_catalog_basket(
            body,
            "item",
            "items",
            lambda entry: " · ".join(
                value for value in (
                    str(entry.get("family") or ""),
                    str(entry.get("category") or ""),
                    str(entry.get("source_group") or ""),
                ) if value
            ),
            quantity_mode=True,
        )
        layout.addLayout(body, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        custom = buttons.addButton("Add custom item…", QDialogButtonBox.ButtonRole.ActionRole)
        self.add_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.add_button.setText("Add Selected (0)")
        self.add_button.setEnabled(False)
        custom.clicked.connect(self._custom); buttons.accepted.connect(self._accept_selected); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search_debounce = DebouncedCallback(
            self._refresh, self.SEARCH_DELAY_MS, self
        )
        self.search.textChanged.connect(self.search_debounce.schedule)
        self.search_mode.currentIndexChanged.connect(self._mode_changed)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.family.currentIndexChanged.connect(self._family_changed)
        self.category.currentIndexChanged.connect(self._refresh)
        self.price_range.changed.connect(self._refresh)
        self.results.itemSelectionChanged.connect(self._show_details)
        self.results.itemClicked.connect(self._queue_from_modified_click)
        self.results.itemDoubleClicked.connect(self._queue_current_entry)
        self._source_changed()

    def _source_changed(self) -> None:
        current = str(self.family.currentData() or "")
        self.family.blockSignals(True); self.family.clear(); self.family.addItem("All families", "")
        for value in item_families(str(self.source.currentData() or "") or None): self.family.addItem(value, value)
        self.family.setCurrentIndex(max(0, self.family.findData(current))); self.family.blockSignals(False)
        self._family_changed()

    def _family_changed(self) -> None:
        current = str(self.category.currentData() or "")
        self.category.blockSignals(True); self.category.clear(); self.category.addItem("All categories", "")
        for value in item_categories(str(self.source.currentData() or "") or None, str(self.family.currentData() or "") or None):
            self.category.addItem(value, value)
        self.category.setCurrentIndex(max(0, self.category.findData(current))); self.category.blockSignals(False)
        self._refresh()

    def _filtered(self):
        query = self.search.text()
        source = str(self.source.currentData() or ""); family = str(self.family.currentData() or ""); category = str(self.category.currentData() or "")
        return self._search_index.search(
            query,
            str(self.search_mode.currentData() or "name"),
            predicate=lambda entry: (
                (not source or entry["source_group"] == source)
                and (not family or entry["family"] == family)
                and (not category or entry["category"] == category)
                and self.price_range.matches(float(entry.get("price_gp") or 0))
            ),
            limit=self.RESULT_LIMIT,
        )

    def _mode_changed(self) -> None:
        mode = str(self.search_mode.currentData() or "name")
        placeholders = {
            "name": "Search item names…",
            "description": "Search item descriptions…",
            "both": "Search item names and descriptions…",
        }
        self.search.setPlaceholderText(placeholders[mode])
        self.search_debounce.flush()

    def _refresh(self) -> None:
        search_result = self._filtered()
        values = search_result.records
        self.result_status.setText(
            f"Showing the first {len(values):,} of {search_result.total:,} matches. Refine the search or filters to see a specific item."
            if search_result.limited
            else f"{search_result.total:,} matching item{'s' if search_result.total != 1 else ''}."
        )
        self.results.setUpdatesEnabled(False)
        self.results.setSortingEnabled(False); self.results.setRowCount(len(values))
        for row, entry in enumerate(values):
            price = f"{entry.get('price_gp', 0):g} gp" if entry.get("price_gp") else "—"
            for column, value in enumerate((entry["name"], entry["source_group"], entry["family"], entry["category"], price)):
                cell = QTableWidgetItem(str(value)); cell.setData(Qt.ItemDataRole.UserRole, entry["key"]); self.results.setItem(row, column, cell)
        self.results.setSortingEnabled(True)
        self.results.setUpdatesEnabled(True)
        self._clear_result_selection()
        self.selected_entry = None
        self.details.setHtml(
            "<p>Select an item to read its rules.</p>"
            if values else "<p>No matching items.</p>"
        )

    def _current_entry(self) -> dict | None:
        row = self.results.currentRow()
        if row < 0 or self.results.item(row, 0) is None:
            return None
        key = str(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole) or "")
        return next((entry for entry in self._entries if entry["key"] == key), None)

    @staticmethod
    def _entry_selectable(_entry: dict) -> bool:
        return True

    def _show_details(self) -> None:
        self.selected_entry = self._current_entry()
        if not self.selected_entry: return
        entry = self.selected_entry
        item_automation = automation_for_entry(entry)
        required_states = sorted({effect.activation.replace("_", " ").title() for effect in item_automation.effects})
        choices = ", ".join(choice.label for choice in item_automation.choices) or "None"
        rules_only = "; ".join(item_automation.rules_only) or "None"
        self.details.setHtml(
            f"<h2>{html.escape(str(entry['name']))}</h2><p><b>{html.escape(str(entry['source_group']))}</b> · "
            f"{html.escape(str(entry['family']))} · {html.escape(str(entry['category']))}</p>"
            f"<p>{html.escape(str(entry.get('description') or 'No description available.'))}</p>"
            f"<p><b>Price:</b> {entry.get('price_gp', 0):g} gp &nbsp; <b>Weight:</b> {entry.get('weight_lb', 0):g} lb</p>"
            f"<p><b>Automation:</b> {html.escape('Requires Choice' if item_automation.status == 'choice' else item_automation.status.replace('_', ' ').title())}</p>"
            f"<p><b>Effects:</b> {html.escape(automation_summary(item_automation))}</p>"
            f"<p><b>Required state:</b> {html.escape(', '.join(required_states) or 'No automatic state requirement')}</p>"
            f"<p><b>Required choices:</b> {html.escape(choices)}</p>"
            f"<p><b>Rules-only portions:</b> {html.escape(rules_only)}</p>"
            f"<p><a href='{html.escape(str(entry.get('source_url', '')))}'>Rules source</a></p>"
        )

    def _custom(self) -> None:
        self.custom_requested = True; self.accept()

    def _accept(self) -> None:
        """Compatibility alias for callers and tests using the old method."""
        self._accept_selected()

    @property
    def values(self) -> dict:
        return self.values_for_entry(self.selected_entry or {})

    @staticmethod
    def values_for_entry(entry: dict) -> dict:
        automation = entry.get("automation") or {}
        item_automation = automation_for_entry(entry)
        raw_slot = str(entry.get("slot") or "")
        slot_lookup = {slot.casefold(): slot for slot in WORN_SLOTS}
        slot = slot_lookup.get(raw_slot.casefold(), "")
        item_type = str(entry.get("item_type") or "").casefold(); bonus_type = str(automation.get("bonus_type") or "untyped")
        if bonus_type == "armor": category = "Armor"
        elif bonus_type == "shield": category = "Shield"
        elif item_type in {"weapon", "ammo"} or "weapon" in str(entry.get("family", "")).casefold(): category = "Weapon"
        elif any(word in item_type for word in ("consumable", "potion", "scroll")): category = "Consumable"
        else: category = "Gear"
        state = "armor" if category == "Armor" else "shield" if category == "Shield" else "wielded" if category == "Weapon" else "worn" if slot else "carried"
        weapon = entry.get("weapon") or {}
        return {
            "name": str(entry.get("name", "")), "category": category,
            "quantity": max(1, int(entry.get("_selection_quantity") or 1)),
            "weight": float(entry.get("weight_lb") or 0), "equipped": state != "stored",
            "ac_bonus": int(automation.get("ac_bonus") or 0),
            "bonus_type": bonus_type if bonus_type in EQUIPMENT_BONUS_TYPES else "untyped",
            "max_dex_bonus": automation.get("max_dex_bonus"), "armor_check_penalty": int(automation.get("armor_check_penalty") or 0),
            "notes": str(entry.get("description") or ""), "slot": slot, "value_gp": float(entry.get("price_gp") or 0),
            "catalog_key": str(entry.get("key") or ""), "catalog_source": str(entry.get("source_group") or ""),
            "state": state, "choices_json": "{}", "automation_json": automation_json(item_automation),
            "enhancement_bonus": catalog_enhancement_bonus(entry), "masterwork": False,
            "weapon_damage_dice": str(weapon.get("damage_dice") or ""),
            "weapon_damage_type": str(weapon.get("damage_type") or ""),
            "weapon_critical": str(weapon.get("critical") or ""),
            "weapon_range": str(weapon.get("range") or ""),
        }


class ItemChoiceDialog(QDialog):
    """Generic editor for any catalog-defined item choice groups."""

    def __init__(self, item_name: str, automation: ItemAutomation, current_json: str = "{}", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._automation = automation
        self.setWindowTitle(f"Item choices — {item_name}")
        layout = QVBoxLayout(self)
        heading = QLabel("ITEM CHOICES"); heading.setObjectName("sectionTitle"); layout.addWidget(heading)
        form = QFormLayout(); self.controls: dict[str, QComboBox] = {}
        try: current = json.loads(current_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError): current = {}
        for choice in automation.choices:
            control = QComboBox()
            if not choice.required: control.addItem("None", "")
            for key, label in choice.options: control.addItem(label, key)
            control.setCurrentIndex(max(0, control.findData(str(current.get(choice.key, "")))))
            self.controls[choice.key] = control; form.addRow(choice.label, control)
        layout.addLayout(form)
        note = QLabel("Choices are stored with this equipment record and immediately update its resolved effects.")
        note.setObjectName("mutedText"); note.setWordWrap(True); layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    @property
    def choices_json(self) -> str:
        return json.dumps({key: str(control.currentData() or "") for key, control in self.controls.items()}, separators=(",", ":"))

    def _accept_if_valid(self) -> None:
        try:
            validate_item_choices(self._automation, json.loads(self.choices_json))
        except ValueError as error:
            QMessageBox.warning(self, "Invalid item choice", str(error))
            return
        self.accept()


class ItemEnchantmentsDialog(QDialog):
    """Manage registry-backed magic properties on one equipment record."""

    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        item: EquipmentItem,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id = character_id
        self.item = item
        self.changed = False
        self.setWindowTitle(f"Enchant — {item.name}")
        self.resize(980, 720)
        layout = QVBoxLayout(self)
        heading = QLabel(f"ENCHANTMENTS · {item.name.upper()}")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Properties are separate reusable rules records. Their effects turn on and "
            "off with the item, and manual attack choices remain available."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.market_price = QLabel()
        self.market_price.setObjectName("focusReady")
        self.market_price.setWordWrap(True)
        layout.addWidget(self.market_price)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(("Applied property", "Cost", "Description"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        browser_title = QLabel("AVAILABLE PROPERTIES")
        browser_title.setObjectName("minorTitle")
        layout.addWidget(browser_title)
        filters = QHBoxLayout()
        self.property_search = QLineEdit()
        self.property_search.setPlaceholderText("Search property names…")
        self.property_category = QComboBox()
        self.property_category.addItem("All compatible types", "")
        self._available_specs = available_enchantments(item)
        for category in sorted({spec.category for spec in self._available_specs}, key=str.casefold):
            self.property_category.addItem(category, category)
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.property_search, 1)
        filters.addWidget(QLabel("Type"))
        filters.addWidget(self.property_category)
        layout.addLayout(filters)

        available_splitter = QSplitter()
        self.available_table = QTableWidget(0, 4)
        self.available_table.setHorizontalHeaderLabels(("Property", "Cost", "Type", "Sheet effect"))
        self.available_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.available_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.available_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.available_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.available_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.available_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.available_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.property_details = QTextBrowser()
        self.property_details.setOpenExternalLinks(True)
        available_splitter.addWidget(self.available_table)
        available_splitter.addWidget(self.property_details)
        available_splitter.setStretchFactor(0, 3)
        available_splitter.setStretchFactor(1, 2)
        layout.addWidget(available_splitter, 2)

        add_row = QHBoxLayout()
        add = QPushButton("+ Add property")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        remove = QPushButton("Remove selected")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self._remove)
        self.available_count = QLabel()
        self.available_count.setObjectName("mutedText")
        add_row.addWidget(self.available_count, 1)
        add_row.addWidget(add)
        add_row.addWidget(remove)
        layout.addLayout(add_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)
        self.property_search.textChanged.connect(self._filter_available)
        self.property_category.currentIndexChanged.connect(self._filter_available)
        self.available_table.currentCellChanged.connect(self._show_available_details)
        self.available_table.doubleClicked.connect(self._add)
        self._filter_available()
        self._refresh()

    @staticmethod
    def _cost_label(spec) -> str:
        return spec.price_text or (
            f"+{spec.bonus_equivalent} bonus" if spec.bonus_equivalent else
            f"+{spec.flat_price_gp:,} gp" if spec.flat_price_gp else "—"
        )

    def _filter_available(self, *_args) -> None:
        query = self.property_search.text().strip().casefold()
        category = str(self.property_category.currentData() or "")
        matches = tuple(
            spec for spec in self._available_specs
            if (not query or query in spec.name.casefold())
            and (not category or spec.category == category)
        )
        self.available_table.setRowCount(len(matches))
        for row, spec in enumerate(matches):
            values = (
                spec.name,
                self._cost_label(spec),
                spec.category,
                "Automatic" if spec.effects else "Rules only",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, spec.key)
                cell.setToolTip(spec.description)
                self.available_table.setItem(row, column, cell)
        self.available_count.setText(
            f"{len(matches):,} of {len(self._available_specs):,} compatible properties"
        )
        if matches:
            self.available_table.selectRow(0)
        else:
            self.property_details.setHtml("<p>No matching compatible properties.</p>")

    def _selected_available_spec(self):
        row = self.available_table.currentRow()
        if row < 0 or self.available_table.item(row, 0) is None:
            return None
        return enchantment_spec(str(self.available_table.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""))

    def _show_available_details(self, *_args) -> None:
        spec = self._selected_available_spec()
        if spec is None:
            return
        restrictions = "".join(f"<li>{html.escape(value)}</li>" for value in spec.restrictions)
        self.property_details.setHtml(
            f"<h2>{html.escape(spec.name)}</h2>"
            f"<p><b>{html.escape(spec.family)} · {html.escape(spec.category)}</b><br>"
            f"<b>Cost:</b> {html.escape(self._cost_label(spec))} &nbsp; "
            f"<b>CL:</b> {html.escape(spec.caster_level or '—')}</p>"
            f"<p>{html.escape(spec.description)}</p>"
            + (f"<p><b>Restrictions</b></p><ul>{restrictions}</ul>" if restrictions else "")
            + f"<p><b>Requirements:</b> {html.escape(spec.requirements or '—')}</p>"
            f"<p><a href='{html.escape(spec.source_url, quote=True)}'>Rules source</a></p>"
        )

    def _refresh(self) -> None:
        self.item = next(
            (
                value for value in self.repository.list_equipment(self.character_id)
                if value.id == self.item.id
            ),
            self.item,
        )
        values = self.repository.list_item_enchantments(
            self.character_id, self.item.id
        )
        price = item_price_breakdown(self.item, values)
        self.market_price.setText(
            f"Current market price: {price.total_gp:g} gp · "
            f"modified bonus +{price.modified_bonus}"
        )
        self.table.setRowCount(len(values))
        for row, value in enumerate(values):
            spec = enchantment_spec(value.key)
            description = spec.description if spec is not None else value.notes
            for column, text in enumerate(
                (
                    value.name,
                    self._cost_label(spec) if spec is not None else f"+{value.bonus_equivalent}",
                    description or "—",
                )
            ):
                cell = QTableWidgetItem(text)
                cell.setData(Qt.ItemDataRole.UserRole, value.id)
                self.table.setItem(row, column, cell)
        if values:
            self.table.selectRow(0)

    def _add(self, *_args) -> None:
        spec = self._selected_available_spec()
        if spec is None:
            QMessageBox.information(
                self, "No compatible property", "No compatible property is selected."
            )
            return
        existing = self.repository.list_item_enchantments(
            self.character_id, self.item.id
        )
        try:
            validate_enchantment_addition(self.item, existing, spec)
            self.repository.add_item_enchantment(
                self.character_id,
                self.item.id,
                spec.key,
                spec.name,
                spec.bonus_equivalent,
                spec.description,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add property", str(error))
            return
        self.changed = True
        self._refresh()

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return
        enchantment_id = int(
            self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        )
        self.repository.delete_item_enchantment(
            self.character_id, enchantment_id
        )
        self.changed = True
        self._refresh()


class AttackDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        attack: Attack | None = None,
        equipment: list[EquipmentItem] | None = None,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        damage_formula_evaluator: Callable[[str], object] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
        conditional: bool = False,
    ) -> None:
        super().__init__(parent)
        self._is_conditional = bool(
            conditional or (attack is not None and attack.visibility_condition.strip())
        )
        self._formula_evaluator = formula_evaluator
        self.setWindowTitle(
            ("Edit Conditional Attack" if attack is not None else "Add Conditional Attack")
            if self._is_conditional
            else ("Edit Attack" if attack is not None else "Add Attack")
        )
        self.resize(900, 540)
        self._profile_key = ""
        self._saved_formulas = formulas or {}
        layout = QVBoxLayout(self)
        heading = QLabel("ATTACK PROFILE")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        intro = QLabel(
            "Link an inventory weapon when possible. Base weapon statistics and "
            "enchantments then update this attack automatically; manual fields remain available."
        )
        intro.setObjectName("mutedText")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        ability_names = [name for _, name, _ in ABILITIES]
        self.preset = QComboBox()
        self.preset.addItem("Custom", "")
        for template in ATTACK_TEMPLATES:
            self.preset.addItem(template.label, template.key)
        for preset in entries("weapons"):
            self.preset.addItem(preset["name"], preset["key"])
        self.linked_weapon = QComboBox()
        self.linked_weapon.addItem("No linked inventory weapon", None)
        self._equipment_by_id = {
            item.id: item
            for item in (equipment or [])
            if item.category == "Weapon"
        }
        for item in self._equipment_by_id.values():
            self.linked_weapon.addItem(item.name, item.id)

        source_frame = QFrame()
        source_frame.setObjectName("dialogSection")
        source_layout = QGridLayout(source_frame)
        source_title = QLabel("QUICK SETUP")
        source_title.setObjectName("minorTitle")
        source_layout.addWidget(source_title, 0, 0, 1, 4)
        source_layout.addWidget(QLabel("Weapon preset"), 1, 0)
        source_layout.addWidget(self.preset, 1, 1)
        source_layout.addWidget(QLabel("Inventory weapon"), 1, 2)
        source_layout.addWidget(self.linked_weapon, 1, 3)
        source_layout.setColumnStretch(1, 1)
        source_layout.setColumnStretch(3, 1)
        layout.addWidget(source_frame)

        self.name = QLineEdit()
        self.attack_type = QComboBox()
        self.attack_type.addItems(ATTACK_TYPES)
        self.ability = QComboBox()
        self.ability.addItems(ability_names)
        self.attack_bonus = FormulaNumberEdit(
            -9999,
            9999,
            evaluator=formula_evaluator,
            suggestion_provider=formula_suggestions,
        )
        self.damage_dice = QLineEdit("1d8")
        self.damage_ability = QComboBox()
        self.damage_ability.addItem("Automatic (rules)", "__automatic__")
        self.damage_ability.addItem("None", None)
        for ability_key, ability_name, _abbreviation in ABILITIES:
            self.damage_ability.addItem(ability_name, ability_key)
        self.damage_multiplier = QComboBox()
        for multiplier in DAMAGE_MULTIPLIERS:
            self.damage_multiplier.addItem(f"×{multiplier:g}", multiplier)
        self.damage_bonus = FormulaNumberEdit(
            -9999,
            9999,
            evaluator=formula_evaluator,
            symbolic_evaluator=damage_formula_evaluator,
            suggestion_provider=formula_suggestions,
        )
        self.critical = QLineEdit("20/x2")
        self.notes = QLineEdit()

        identity = QFrame()
        identity.setObjectName("dialogSection")
        identity_layout = QGridLayout(identity)
        identity_title = QLabel("IDENTITY")
        identity_title.setObjectName("minorTitle")
        identity_layout.addWidget(identity_title, 0, 0, 1, 4)
        identity_layout.addWidget(QLabel("Attack name"), 1, 0)
        identity_layout.addWidget(self.name, 1, 1, 1, 3)
        identity_layout.addWidget(QLabel("Attack type"), 2, 0)
        identity_layout.addWidget(self.attack_type, 2, 1)
        identity_layout.addWidget(QLabel("Notes"), 2, 2)
        identity_layout.addWidget(self.notes, 2, 3)
        identity_layout.setColumnStretch(1, 1)
        identity_layout.setColumnStretch(3, 2)
        layout.addWidget(identity)

        mechanics = QHBoxLayout()
        attack_frame = QFrame()
        attack_frame.setObjectName("dialogSection")
        attack_form = QFormLayout(attack_frame)
        attack_title = QLabel("ATTACK ROLL")
        attack_title.setObjectName("minorTitle")
        attack_form.addRow(attack_title)
        attack_form.addRow("Ability", self.ability)
        attack_form.addRow("Additional bonus", self.attack_bonus)
        attack_hint = QLabel("Total = d20 + BAB + ability + size + this field")
        attack_hint.setObjectName("mutedText")
        attack_hint.setWordWrap(True)
        attack_form.addRow(attack_hint)

        damage_frame = QFrame()
        damage_frame.setObjectName("dialogSection")
        damage_form = QFormLayout(damage_frame)
        damage_title = QLabel("DAMAGE & CRITICAL")
        damage_title.setObjectName("minorTitle")
        damage_form.addRow(damage_title)
        damage_form.addRow("Base dice", self.damage_dice)
        damage_form.addRow("Ability", self.damage_ability)
        damage_form.addRow("Ability multiplier", self.damage_multiplier)
        damage_form.addRow("Additional bonus", self.damage_bonus)
        damage_form.addRow("Critical profile", self.critical)
        mechanics.addWidget(attack_frame, 1)
        mechanics.addWidget(damage_frame, 1)
        layout.addLayout(mechanics)

        formula_help = QLabel(
            "FORMULAS · Enter a number, or start with =. Examples: =floor(bab / 4), "
            "=skillranks.acrobatics, =2 if martial_focus else 0, "
            "=-floor((bab + 3) / 4) if feats.power_attack else 0"
        )
        formula_help.setObjectName("formulaHelp")
        formula_help.setWordWrap(True)
        formula_help.setToolTip(
            "Also available: skills.<skill>, skills.<skill>.ranks, feat.<name>, "
            "abilities.<ability>.modifier, classes.<class>.level, trackers.<key>.<field>."
        )
        layout.addWidget(formula_help)
        self.visibility_condition: FormulaLineEdit | None = None
        if self._is_conditional:
            condition_frame = QFrame()
            condition_frame.setObjectName("dialogSection")
            condition_form = QFormLayout(condition_frame)
            condition_title = QLabel("DISPLAY CONDITION")
            condition_title.setObjectName("minorTitle")
            condition_form.addRow(condition_title)
            self.visibility_condition = FormulaLineEdit(
                suggestion_provider=formula_suggestions,
                require_equals=False,
            )
            self.visibility_condition.setPlaceholderText(
                "e.g. martial_focus and sphere.berserker"
            )
            condition_form.addRow("Show this attack when", self.visibility_condition)
            condition_note = QLabel(
                "The attack is hidden whenever this formula resolves to zero/false and "
                "reappears automatically when its referenced character values change."
            )
            condition_note.setObjectName("mutedText")
            condition_note.setWordWrap(True)
            condition_form.addRow(condition_note)
            layout.addWidget(condition_frame)
        self.attack_type.currentTextChanged.connect(self._type_changed)
        self.damage_ability.currentIndexChanged.connect(
            self._damage_ability_changed
        )
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.linked_weapon.currentIndexChanged.connect(self._equipment_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._type_changed(self.attack_type.currentText())
        if attack is not None:
            ability_names_by_key = {key: name for key, name, _ in ABILITIES}
            self.linked_weapon.setCurrentIndex(
                max(0, self.linked_weapon.findData(attack.equipment_id))
            )
            if attack.profile_key:
                self.preset.setCurrentIndex(
                    max(0, self.preset.findData(f"builtin:{attack.profile_key}"))
                )
            else:
                preset = entry_by_name("weapons", attack.name)
            if not attack.profile_key and preset is not None:
                self.preset.setCurrentIndex(self.preset.findData(preset["key"]))
            self._profile_key = attack.profile_key
            self.name.setText(attack.name)
            self.attack_type.setCurrentText(attack.attack_type)
            self.ability.setCurrentText(ability_names_by_key[attack.ability])
            self.attack_bonus.set_expression(
                self._saved_formulas.get("attack_bonus", ""), attack.attack_bonus
            )
            self.damage_dice.setText(attack.damage_dice)
            self.damage_ability.setCurrentIndex(
                max(
                    0,
                    self.damage_ability.findData(
                        "__automatic__"
                        if attack.damage_ability_mode == "automatic"
                        else attack.damage_ability
                    ),
                )
            )
            multiplier_index = self.damage_multiplier.findData(attack.damage_multiplier)
            self.damage_multiplier.setCurrentIndex(multiplier_index)
            self.damage_bonus.set_expression(
                self._saved_formulas.get("damage_bonus", ""), attack.damage_bonus
            )
            self.critical.setText(attack.critical)
            self.notes.setText(attack.notes)
            if self.visibility_condition is not None:
                self.visibility_condition.setText(attack.visibility_condition)

    def _equipment_changed(self) -> None:
        item = self._equipment_by_id.get(self.linked_weapon.currentData())
        if item is None:
            return
        self._profile_key = ""
        self.name.setText(item.name)
        if item.weapon_damage_dice:
            self.damage_dice.setText(item.weapon_damage_dice)
        if item.weapon_critical:
            self.critical.setText(item.weapon_critical)
        self.attack_type.setCurrentText(weapon_attack_type(item))

    def _preset_changed(self) -> None:
        selected_key = str(self.preset.currentData() or "")
        template = attack_template(selected_key)
        if template is not None:
            values = template.values
            ability_names_by_key = {key: name for key, name, _ in ABILITIES}
            self._profile_key = str(values["profile_key"])
            self.linked_weapon.setCurrentIndex(0)
            self.name.setText(str(values["name"]))
            self.attack_type.setCurrentText(str(values["attack_type"]))
            self.ability.setCurrentText(ability_names_by_key[str(values["ability"])])
            self.attack_bonus.set_value(int(values["attack_bonus"]))
            self.damage_dice.setText(str(values["damage_dice"]))
            self.damage_ability.setCurrentIndex(
                self.damage_ability.findData("__automatic__")
            )
            self.damage_multiplier.setCurrentIndex(
                self.damage_multiplier.findData(float(values["damage_multiplier"]))
            )
            self.damage_bonus.set_value(int(values["damage_bonus"]))
            self.critical.setText(str(values["critical"]))
            self.notes.setText(str(values["notes"]))
            return
        self._profile_key = ""
        preset = entry_by_key("weapons", selected_key)
        if preset is None:
            return
        ability_names_by_key = {key: name for key, name, _ in ABILITIES}
        self.name.setText(preset["name"])
        self.attack_type.setCurrentText(preset["attack_type"])
        self.ability.setCurrentText(ability_names_by_key[preset["ability"]])
        self.damage_dice.setText(preset["damage_dice"])
        self.damage_ability.setCurrentIndex(
            self.damage_ability.findData(preset["damage_ability"])
        )
        self.damage_multiplier.setCurrentIndex(
            self.damage_multiplier.findData(float(preset["damage_multiplier"]))
        )
        self.critical.setText(preset["critical"])

    @staticmethod
    def _ability_key(name: str) -> str | None:
        if name == "None":
            return None
        return next(key for key, full_name, _ in ABILITIES if full_name == name)

    def _type_changed(self, attack_type: str) -> None:
        if attack_type == "Melee":
            self.ability.setCurrentText("Strength")
            self.damage_ability.setCurrentIndex(
                self.damage_ability.findData("strength")
            )
            self.damage_multiplier.setCurrentIndex(DAMAGE_MULTIPLIERS.index(1.0))
        else:
            self.ability.setCurrentText("Dexterity")
            self.damage_ability.setCurrentIndex(
                self.damage_ability.findData(None)
            )
            self.damage_multiplier.setCurrentIndex(DAMAGE_MULTIPLIERS.index(0.0))

    def _damage_ability_changed(self, _index: int = -1) -> None:
        """Keep a newly selected ability from being silently multiplied by zero."""

        ability = self.damage_ability.currentData()
        if ability is None:
            self.damage_multiplier.setCurrentIndex(
                self.damage_multiplier.findData(0.0)
            )
            return
        if float(self.damage_multiplier.currentData() or 0.0) == 0.0:
            self.damage_multiplier.setCurrentIndex(
                self.damage_multiplier.findData(1.0)
            )

    @property
    def values(self) -> dict:
        damage_data = self.damage_ability.currentData()
        return {
            "name": self.name.text().strip(),
            "attack_type": self.attack_type.currentText(),
            "ability": self._ability_key(self.ability.currentText()),
            "attack_bonus": int(self.attack_bonus.value()),
            "damage_dice": self.damage_dice.text().strip(),
            "damage_ability": (
                "strength" if damage_data == "__automatic__" else damage_data
            ),
            "damage_multiplier": self.damage_multiplier.currentData(),
            "damage_bonus": int(self.damage_bonus.value()),
            "critical": self.critical.text().strip(),
            "notes": self.notes.text(),
            "equipment_id": self.linked_weapon.currentData(),
            "profile_key": self._profile_key,
            "damage_ability_mode": (
                "automatic" if damage_data == "__automatic__" else "manual"
            ),
            "visibility_condition": (
                self.visibility_condition.text().strip()
                if self.visibility_condition is not None
                else ""
            ),
        }

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {
            "attack_bonus": self.attack_bonus.expression,
            "damage_bonus": self.damage_bonus.expression,
        }

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Attack required", "Enter an attack name.")
            return
        try:
            parse_dice(self.damage_dice.text())
            self.attack_bonus.value()
            self.damage_bonus.value()
            if self.visibility_condition is not None:
                expression = self.visibility_condition.text().strip()
                if not expression:
                    raise FormulaError("Enter a display condition for this attack.")
                if self._formula_evaluator is None:
                    raise FormulaError("This condition has no character formula context.")
                self._formula_evaluator(expression)
        except (ValueError, FormulaError) as error:
            QMessageBox.warning(self, "Invalid attack value", str(error))
            return
        self.accept()

class CustomTrackerDialog(QDialog):
    TYPE_LABELS = {
        "calculated": "Calculated value",
        "counter": "Usage counter",
        "pool": "Resource pool",
    }

    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        parent: QWidget | None = None,
        tracker: CustomTracker | None = None,
        default_type: str = "pool",
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id = character_id
        self.tracker = tracker
        self._formula_resolver = CustomTrackerResolver(repository, character_id)
        self._key_was_generated = tracker is None
        self.setWindowTitle("Edit custom tracker" if tracker else "Add custom tracker")
        self.resize(720, 590)
        layout = QVBoxLayout(self)
        heading = QLabel("CUSTOM TRACKER")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Formulas use stable names, so moving or resizing a block never breaks its rules. "
            "Example: floor(classes.monk.level / 3) + abilities.wisdom.modifier"
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Spell Points")
        self.key = QLineEdit()
        self.key.setPlaceholderText("spell_points")
        self.tracker_type = QComboBox()
        for key, label in self.TYPE_LABELS.items():
            self.tracker_type.addItem(label, key)
        self.formula = FormulaLineEdit(
            suggestion_provider=self._formula_resolver.context.suggestions,
            require_equals=False,
        )
        self.formula.setPlaceholderText("Leave empty to use the manual maximum")
        self.manual_maximum = QDoubleSpinBox()
        self.manual_maximum.setRange(-1_000_000_000, 1_000_000_000)
        self.manual_maximum.setDecimals(2)
        self.current_value = QDoubleSpinBox()
        self.current_value.setRange(-1_000_000_000, 1_000_000_000)
        self.current_value.setDecimals(2)
        self.temporary_value = QDoubleSpinBox()
        self.temporary_value.setRange(-1_000_000_000, 1_000_000_000)
        self.temporary_value.setDecimals(2)
        self.unit = QLineEdit()
        self.unit.setPlaceholderText("SP, uses, rounds…")
        self.recovery_event = QComboBox()
        self.recovery_event.addItem("No automatic recovery", "none")
        self.recovery_event.addItem("Full Rest (ready for Rest Engine)", "full_rest")
        self.recovery_operation = QComboBox()
        self.recovery_operation.addItem("No change", "none")
        self.recovery_operation.addItem("Set current to maximum", "set_to_max")
        self.recovery_operation.addItem("Reset current to zero", "reset_to_zero")
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(100)
        form.addRow("Name", self.name)
        form.addRow("Reference key", self.key)
        form.addRow("Template", self.tracker_type)
        form.addRow("Formula", self.formula)
        form.addRow("Manual maximum", self.manual_maximum)
        form.addRow("Current", self.current_value)
        form.addRow("Temporary", self.temporary_value)
        form.addRow("Unit", self.unit)
        form.addRow("Recovery event", self.recovery_event)
        form.addRow("Recovery operation", self.recovery_operation)
        form.addRow("Description", self.description)
        layout.addLayout(form)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setObjectName("mutedText")
        layout.addWidget(self.preview)
        reference_help = QLabel(
            "Available roots: character.level, character.bab, classes.&lt;key&gt;.level, "
            "abilities.&lt;ability&gt;.score/modifier, casting.*, spell_points.*, hit_points.*, "
            "martial_focus.*, and trackers.&lt;key&gt;.value/maximum/current/temporary. "
            "Functions: floor, ceil, round, min, max, abs, clamp."
        )
        reference_help.setTextFormat(Qt.TextFormat.RichText)
        reference_help.setWordWrap(True)
        reference_help.setObjectName("mutedText")
        layout.addWidget(reference_help)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name.textChanged.connect(self._name_changed)
        self.key.textEdited.connect(self._key_edited)
        self.tracker_type.currentIndexChanged.connect(self._type_changed)
        self.formula.textChanged.connect(self._update_preview)
        self.manual_maximum.valueChanged.connect(self._update_preview)
        if tracker is not None:
            self.name.setText(tracker.name)
            self.key.setText(tracker.key)
            self.tracker_type.setCurrentIndex(
                max(0, self.tracker_type.findData(tracker.tracker_type))
            )
            self.formula.setText(tracker.formula)
            self.manual_maximum.setValue(tracker.manual_maximum)
            self.current_value.setValue(tracker.current_value)
            self.temporary_value.setValue(tracker.temporary_value)
            self.unit.setText(tracker.unit)
            self.description.setPlainText(tracker.description)
            self.recovery_event.setCurrentIndex(
                max(0, self.recovery_event.findData(tracker.recovery_event))
            )
            self.recovery_operation.setCurrentIndex(
                max(0, self.recovery_operation.findData(tracker.recovery_operation))
            )
        else:
            self.tracker_type.setCurrentIndex(
                max(0, self.tracker_type.findData(default_type))
            )
        self._type_changed()
        self._update_preview()

    def _name_changed(self, value: str) -> None:
        if self._key_was_generated:
            self.key.setText(reference_key(value))

    def _key_edited(self, _value: str) -> None:
        self._key_was_generated = False

    def _type_changed(self, *_args) -> None:
        calculated = self.tracker_type.currentData() == "calculated"
        self.manual_maximum.setEnabled(not calculated and not self.formula.text().strip())
        self.current_value.setEnabled(not calculated)
        self.temporary_value.setEnabled(not calculated)
        self.recovery_event.setEnabled(not calculated)
        self.recovery_operation.setEnabled(not calculated)
        self.formula.setPlaceholderText(
            "Required formula" if calculated else "Optional maximum formula"
        )
        self._update_preview()

    def _update_preview(self, *_args) -> None:
        self.manual_maximum.setEnabled(
            self.tracker_type.currentData() != "calculated" and not self.formula.text().strip()
        )
        formula = self.formula.text().strip()
        if not formula:
            if self.tracker_type.currentData() == "calculated":
                self.preview.setText("A calculated value requires a formula.")
            else:
                self.preview.setText(
                    f"Manual maximum preview: {display_number(self.manual_maximum.value())}"
                )
            return
        try:
            result = DEFAULT_FORMULA_ENGINE.evaluate(
                formula,
                self._formula_resolver.base_values,
                self._formula_resolver.resolve_reference,
            )
            self.preview.setText(f"Current formula preview: {display_number(result)}")
        except FormulaError as error:
            self.preview.setText(f"Formula needs attention: {error}")

    @property
    def values(self) -> dict:
        calculated = self.tracker_type.currentData() == "calculated"
        return {
            "key": self.key.text().strip(),
            "name": self.name.text().strip(),
            "tracker_type": str(self.tracker_type.currentData()),
            "formula": self.formula.text().strip(),
            "manual_maximum": self.manual_maximum.value(),
            "current_value": 0 if calculated else self.current_value.value(),
            "temporary_value": 0 if calculated else self.temporary_value.value(),
            "unit": self.unit.text().strip(),
            "description": self.description.toPlainText().strip(),
            "recovery_event": "none" if calculated else str(self.recovery_event.currentData()),
            "recovery_operation": "none" if calculated else str(self.recovery_operation.currentData()),
        }

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Name required", "Enter a tracker name.")
            return
        try:
            if self.formula.text().strip():
                parse_formula(self.formula.text())
            elif self.tracker_type.currentData() == "calculated":
                raise FormulaError("Calculated values require a formula.")
        except FormulaError as error:
            QMessageBox.warning(self, "Invalid formula", str(error))
            return
        self.accept()


class ClassCatalogDialog(QDialog):
    """Searchable, ruleset-separated class browser used by every class workflow."""

    def __init__(self, selected_key: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose a Pathfinder or Spheres class")
        self.resize(1040, 680)
        self.selected_entry: dict | None = None
        self.custom_requested = False
        self._entries = class_entries()
        self._entries_by_key = {str(entry["key"]): entry for entry in self._entries}
        self._selected_key = (
            f"pathfinder-class:{selected_key}"
            if selected_key and not selected_key.startswith("spheres-class:") and selected_key != "prodigy"
            else selected_key
        )
        layout = QVBoxLayout(self)
        heading = QLabel("CLASS CATALOG")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(
            "Pathfinder and Spheres classes are distinct catalog families. Results are always alphabetical; "
            "use the ruleset and family filters to narrow the list."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search class names or descriptions…")
        self.source = QComboBox()
        self.source.addItem("All rulesets", "")
        self.source.addItem("Pathfinder", "Pathfinder")
        self.source.addItem("Spheres", "Spheres")
        self.category = QComboBox()
        filters.addWidget(QLabel("Find"))
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Ruleset"))
        filters.addWidget(self.source)
        filters.addWidget(QLabel("Family"))
        filters.addWidget(self.category)
        layout.addLayout(filters)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.results = QTableWidget(0, 3)
        self.results.setHorizontalHeaderLabels(("Class", "Ruleset", "Family"))
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.details.setMinimumWidth(380)
        splitter.addWidget(self.results)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        custom = buttons.addButton("Use a custom class…", QDialogButtonBox.ButtonRole.ActionRole)
        custom.clicked.connect(self._custom)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._refresh)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.category.currentIndexChanged.connect(self._refresh)
        self.results.itemSelectionChanged.connect(self._show_details)
        self.results.itemDoubleClicked.connect(lambda _item: self._accept())
        self._source_changed()

    @staticmethod
    def _ruleset(entry: dict) -> str:
        return "Spheres" if str(entry["key"]).startswith("spheres-class:") or entry["key"] == "prodigy" else "Pathfinder"

    def _source_changed(self) -> None:
        current = str(self.category.currentData() or "")
        source = str(self.source.currentData() or "")
        categories = sorted(
            {
                str(entry.get("category") or "Other")
                for entry in self._entries
                if not source or self._ruleset(entry) == source
            },
            key=str.casefold,
        )
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("All families", "")
        for value in categories:
            self.category.addItem(value, value)
        self.category.setCurrentIndex(max(0, self.category.findData(current)))
        self.category.blockSignals(False)
        self._refresh()

    def _refresh(self) -> None:
        query = self.search.text().strip().casefold()
        source = str(self.source.currentData() or "")
        category = str(self.category.currentData() or "")
        matches = [
            entry for entry in self._entries
            if (not source or self._ruleset(entry) == source)
            and (not category or str(entry.get("category") or "") == category)
            and (
                not query
                or query in str(entry["name"]).casefold()
                or query in str(entry.get("summary") or entry.get("description") or "").casefold()
            )
        ]
        matches.sort(key=lambda entry: str(entry["name"]).casefold())
        self.results.setRowCount(len(matches))
        selected_row = -1
        for row, entry in enumerate(matches):
            name = QTableWidgetItem(str(entry["name"]))
            name.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
            name.setToolTip(str(entry.get("summary") or entry.get("description") or ""))
            self.results.setItem(row, 0, name)
            self.results.setItem(row, 1, QTableWidgetItem(self._ruleset(entry)))
            self.results.setItem(row, 2, QTableWidgetItem(str(entry.get("category") or "Other")))
            if entry["key"] == self._selected_key:
                selected_row = row
        if matches:
            self.results.selectRow(selected_row if selected_row >= 0 else 0)
        else:
            self.details.setHtml("<p>No classes match these filters.</p>")

    def _current_entry(self) -> dict | None:
        row = self.results.currentRow()
        if row < 0 or self.results.item(row, 0) is None:
            return None
        return self._entries_by_key.get(str(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole)))

    def _show_details(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        capabilities = ", ".join(str(value).title() for value in entry.get("capabilities", ())) or "Traditional Pathfinder"
        casting = entry.get("casting") or {}
        casting_text = ", ".join(
            str(value) for value in (
                casting.get("sphere_progression"), casting.get("progression"),
                casting.get("type"), casting.get("spells"),
            ) if value
        ) or "None"
        self.details.setHtml(
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(self._ruleset(entry))} · {html.escape(str(entry.get('category') or 'Other'))}</b></p>"
            f"<p><b>Hit Die:</b> d{entry.get('hit_die', 0)} &nbsp; <b>BAB:</b> {html.escape(str(entry.get('bab', '')))} &nbsp; "
            f"<b>Saves:</b> {entry.get('fort')} / {entry.get('reflex')} / {entry.get('will')}</p>"
            f"<p><b>Sheet systems:</b> {html.escape(capabilities)}<br><b>Casting:</b> {html.escape(casting_text)}</p>"
            f"<p>{html.escape(str(entry.get('description') or entry.get('summary') or 'No summary available.'))}</p>"
            f"<p><a href='{html.escape(str(entry.get('source_url') or ''), quote=True)}'>Rules source</a></p>"
        )

    def _custom(self) -> None:
        self.custom_requested = True
        self.accept()

    def _accept(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self.selected_entry = entry
        self.accept()


class ArchetypeSelectionDialog(QDialog):
    """Searchable multi-select browser with live PF1e stacking validation."""

    def __init__(
        self,
        class_key: str,
        selected_keys: tuple[str, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose compatible archetypes")
        self.resize(1240, 760)
        self._entries = tuple(sorted(archetype_entries(class_key), key=lambda entry: str(entry["name"]).casefold()))
        self._by_key = {str(entry["key"]): entry for entry in self._entries}
        self._compatibility_index = ArchetypeCompatibilityIndex(self._by_key)
        self._selected_keys = set(selected_keys)
        self._updating = False
        layout = QVBoxLayout(self)
        heading = QLabel("ARCHETYPES")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search archetype names, replaced features, or descriptions…")
        self.source = QComboBox()
        self.source.addItem("All rulesets", "")
        for value in sorted({str(entry["source_group"]) for entry in self._entries}, key=str.casefold):
            self.source.addItem(value, value)
        filters.addWidget(QLabel("Find"))
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Ruleset"))
        filters.addWidget(self.source)
        layout.addLayout(filters)
        self.compatibility_status = QLabel()
        self.compatibility_status.setObjectName("mutedText")
        self.compatibility_status.setWordWrap(True)
        layout.addWidget(self.compatibility_status)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(("Use", "Archetype", "Replaces / alters", "Ruleset"))
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.details.setMinimumWidth(410)
        splitter.addWidget(self.results)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_compatible)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._refresh)
        self.source.currentIndexChanged.connect(self._refresh)
        self.results.itemSelectionChanged.connect(self._show_details)
        self._refresh()

    @property
    def selected_keys(self) -> tuple[str, ...]:
        order = {str(entry["key"]): index for index, entry in enumerate(self._entries)}
        return tuple(sorted(self._selected_keys, key=lambda key: order.get(key, 999999)))

    def _refresh(self) -> None:
        query = self.search.text().strip().casefold()
        source = str(self.source.currentData() or "")
        matches = [
            entry for entry in self._entries
            if (not source or entry["source_group"] == source)
            and (
                not query
                or query in str(entry["name"]).casefold()
                or query in str(entry.get("replaces") or "").casefold()
                or query in str(entry.get("description") or "").casefold()
            )
        ]
        self._updating = True
        self.results.setRowCount(len(matches))
        for row, entry in enumerate(matches):
            use = QTableWidgetItem()
            use.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            use.setData(Qt.ItemDataRole.UserRole, str(entry["key"]))
            name = QTableWidgetItem(str(entry["name"]))
            name.setToolTip(str(entry.get("summary") or entry.get("description") or ""))
            self.results.setItem(row, 0, use)
            check_container = QWidget()
            check_layout = QHBoxLayout(check_container)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox = QCheckBox()
            checkbox.setChecked(entry["key"] in self._selected_keys)
            checkbox.setToolTip(f"Use {entry['name']}")
            checkbox.toggled.connect(
                partial(
                    self._archetype_toggled,
                    str(entry["key"]),
                    row,
                )
            )
            check_layout.addWidget(checkbox)
            self.results.setCellWidget(row, 0, check_container)
            self.results.setItem(row, 1, name)
            changes = ", ".join(archetype_change_labels(entry)) or "See feature notes"
            change_item = QTableWidgetItem(changes)
            change_item.setToolTip(changes)
            self.results.setItem(row, 2, change_item)
            self.results.setItem(row, 3, QTableWidgetItem(str(entry["source_group"])))
        self._updating = False
        if matches:
            self.results.selectRow(0)
        self._update_compatibility_status()

    def _archetype_toggled(self, key: str, row: int, checked: bool) -> None:
        if self._updating:
            return
        if checked:
            self._selected_keys.add(key)
        else:
            self._selected_keys.discard(key)
        self.results.selectRow(row)
        self._update_compatibility_status()

    def _update_compatibility_status(self) -> None:
        result = self._compatibility_index.validate(self._selected_keys)
        if not self._selected_keys:
            text = "No archetypes selected. Multiple archetypes are allowed when they do not replace or alter the same class feature."
        elif result.compatible:
            text = f"{len(self._selected_keys)} archetype(s) selected; this combination is compatible."
        else:
            text = "Incompatible selection: " + " ".join(result.reasons)
        self.compatibility_status.setText(text)
        self.compatibility_status.setProperty(
            "validationError", not result.compatible
        )
        self.compatibility_status.style().unpolish(self.compatibility_status)
        self.compatibility_status.style().polish(self.compatibility_status)
        self._update_candidate_availability()

    def _update_candidate_availability(self) -> None:
        """Disable only unselected candidates that cannot join the current stack."""

        selected = tuple(self._selected_keys)
        active_brush = self.results.palette().brush(
            QPalette.ColorGroup.Active, QPalette.ColorRole.Text
        )
        disabled_brush = self.results.palette().brush(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text
        )
        for row in range(self.results.rowCount()):
            key_item = self.results.item(row, 0)
            if key_item is None:
                continue
            key = str(key_item.data(Qt.ItemDataRole.UserRole) or "")
            container = self.results.cellWidget(row, 0)
            checkbox = container.findChild(QCheckBox) if container else None
            if checkbox is None:
                continue
            is_selected = key in self._selected_keys
            result = self._compatibility_index.validate((*selected, key))
            available = is_selected or result.compatible
            checkbox.setEnabled(available)
            if is_selected:
                tooltip = "Selected. Uncheck this archetype to remove it."
            elif available:
                tooltip = "Compatible with the currently selected archetypes."
            else:
                tooltip = "Unavailable: " + " ".join(result.reasons)
            checkbox.setToolTip(tooltip)
            brush = active_brush if available else disabled_brush
            for column in range(self.results.columnCount()):
                item = self.results.item(row, column)
                if item is not None:
                    item.setForeground(brush)
            name_item = self.results.item(row, 1)
            if name_item is not None:
                description = str(
                    self._by_key.get(key, {}).get("summary")
                    or self._by_key.get(key, {}).get("description")
                    or ""
                )
                name_item.setToolTip(
                    f"{tooltip}\n\n{description}" if description else tooltip
                )

    def _current_entry(self) -> dict | None:
        row = self.results.currentRow()
        if row < 0 or self.results.item(row, 0) is None:
            return None
        return self._by_key.get(str(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole)))

    def _show_details(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self.details.setHtml(archetype_rules_html(entry))

    def _accept_if_compatible(self) -> None:
        result = self._compatibility_index.validate(self._selected_keys)
        if not result.compatible:
            self._update_compatibility_status()
            return
        self.accept()


class ClassLevelDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        class_level=None,
        level_up: bool = False,
        selected_archetype_keys: tuple[str, ...] = (),
        selected_optional_feature_keys: tuple[str, ...] = (),
        selected_archetype_choices: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Level up class" if level_up else ("Edit class" if class_level else "Add class"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItem("Custom", "")
        for preset in sorted(entries("classes"), key=lambda entry: str(entry["name"]).casefold()):
            self.preset.addItem(preset["name"], preset["key"])
        self.preset.hide()
        self.class_selection = QLineEdit()
        self.class_selection.setReadOnly(True)
        self.class_selection.setPlaceholderText("No catalog class selected")
        self.class_selection.setObjectName("catalogSelection")
        browse_class = QPushButton("Browse classes…")
        browse_class.setObjectName("primaryButton")
        browse_class.clicked.connect(self._browse_classes)
        class_picker = QWidget()
        class_picker_layout = QHBoxLayout(class_picker)
        class_picker_layout.setContentsMargins(0, 0, 0, 0)
        class_picker_layout.addWidget(self.class_selection, 1)
        class_picker_layout.addWidget(browse_class)
        self.class_name = QLineEdit()
        self.class_name.setPlaceholderText("e.g. Fighter, Incanter, Conscript")
        self.level = QSpinBox()
        self.level.setRange(1, 20)
        self.bab = QComboBox()
        self.bab.addItems(BAB_PROGRESSIONS)
        self.fort = QComboBox()
        self.fort.addItems(SAVE_PROGRESSIONS)
        self.reflex = QComboBox()
        self.reflex.addItems(SAVE_PROGRESSIONS)
        self.will = QComboBox()
        self.will.addItems(SAVE_PROGRESSIONS)
        self.hit_die = QComboBox()
        for value in (0, 6, 8, 10, 12):
            self.hit_die.addItem("Custom / none" if value == 0 else f"d{value}", value)
        self.hp_gained = QSpinBox()
        self.hp_gained.setRange(0, 9999)
        self.auto_hp = QCheckBox("Calculate automatically")
        self.auto_hp.setChecked(True)
        form.addRow("Class catalog", class_picker)
        form.addRow("Class name", self.class_name)
        form.addRow("Levels", self.level)
        form.addRow("Hit Die", self.hit_die)
        form.addRow("Class HP", self.auto_hp)
        form.addRow("Hit Die HP total", self.hp_gained)
        form.addRow("BAB progression", self.bab)
        form.addRow("Fortitude", self.fort)
        form.addRow("Reflex", self.reflex)
        form.addRow("Will", self.will)
        layout.addLayout(form)
        archetype_heading = QLabel("ARCHETYPES")
        archetype_heading.setObjectName("sectionTitle")
        layout.addWidget(archetype_heading)
        archetype_note = QLabel(
            "Choose any compatible archetypes for this class. Pathfinder and Spheres "
            "options are documented separately in the Codex."
        )
        archetype_note.setObjectName("mutedText")
        archetype_note.setWordWrap(True)
        layout.addWidget(archetype_note)
        self._selected_archetype_keys = set(selected_archetype_keys)
        self._selected_optional_feature_keys = set(selected_optional_feature_keys)
        self._selected_archetype_choices = {
            str(key): set(str(value) for value in values)
            for key, values in (selected_archetype_choices or {}).items()
        }
        archetype_row = QHBoxLayout()
        self.archetype_summary = QLabel("No archetypes selected")
        self.archetype_summary.setWordWrap(True)
        self.choose_archetypes_button = QPushButton("Choose archetypes…")
        self.choose_archetypes_button.setEnabled(False)
        self.choose_archetypes_button.clicked.connect(self._choose_archetypes)
        archetype_row.addWidget(self.archetype_summary, 1)
        archetype_row.addWidget(self.choose_archetypes_button)
        layout.addLayout(archetype_row)
        self.optional_exchange_container = QWidget()
        self.optional_exchange_layout = QVBoxLayout(self.optional_exchange_container)
        self.optional_exchange_layout.setContentsMargins(0, 2, 0, 4)
        self.optional_exchange_layout.setSpacing(3)
        self.optional_exchange_checkboxes: dict[str, QCheckBox] = {}
        self.archetype_choice_widgets: dict[str, list[QWidget]] = {}
        layout.addWidget(self.optional_exchange_container)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.level.valueChanged.connect(self._level_changed)
        self.hit_die.currentIndexChanged.connect(self._level_changed)
        self.auto_hp.toggled.connect(self._auto_hp_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.class_name.setFocus()
        if class_level is not None:
            preset_index = self.preset.findData(class_level.preset_key)
            if preset_index < 0 and class_level.preset_key.startswith(
                "pathfinder-class:"
            ):
                preset_index = self.preset.findData(
                    class_level.preset_key.removeprefix("pathfinder-class:")
                )
            self.preset.setCurrentIndex(max(0, preset_index))
            self.class_name.setText(class_level.class_name)
            self.level.setValue(class_level.level)
            self.hit_die.setCurrentIndex(max(0, self.hit_die.findData(class_level.hit_die)))
            self.hp_gained.setValue(class_level.hp_gained)
            self.bab.setCurrentText(class_level.bab_progression)
            self.fort.setCurrentText(class_level.fort_progression)
            self.reflex.setCurrentText(class_level.reflex_progression)
            self.will.setCurrentText(class_level.will_progression)
            automatic_hp = bool(
                class_level.hit_die
                and class_level.hp_gained
                == recommended_hit_points(class_level.hit_die, class_level.level)
            )
            self.auto_hp.setChecked(automatic_hp)
            if level_up:
                self.level.setValue(class_level.level + 1)
                if automatic_hp:
                    self.hp_gained.setValue(
                        recommended_hit_points(class_level.hit_die, self.level.value())
                    )
                else:
                    self.hp_gained.setValue(
                        class_level.hp_gained
                        + (class_level.hit_die // 2 + 1 if class_level.hit_die else 0)
                    )
        self._refresh_archetypes()
        self._auto_hp_changed()

    def _browse_classes(self) -> None:
        dialog = ClassCatalogDialog(str(self.preset.currentData() or ""), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.custom_requested:
            self.preset.setCurrentIndex(0)
            self.class_selection.clear()
            self.class_name.setReadOnly(False)
            self.class_name.setFocus()
            return
        entry = dialog.selected_entry
        if entry is None:
            return
        key = str(entry["key"])
        index = self.preset.findData(key)
        if index < 0 and key.startswith("pathfinder-class:"):
            index = self.preset.findData(key.removeprefix("pathfinder-class:"))
        if index >= 0:
            self.preset.setCurrentIndex(index)

    def _choose_archetypes(self) -> None:
        preset_key = str(self.preset.currentData() or "")
        if not preset_key:
            self.archetype_summary.setText("Choose a catalog class before selecting archetypes.")
            return
        dialog = ArchetypeSelectionDialog(
            preset_key, tuple(self._selected_archetype_keys), self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._selected_archetype_keys = set(dialog.selected_keys)
        self._refresh_archetypes()
        self._apply_archetype_profile()

    def _preset_changed(self) -> None:
        preset = entry_by_key("classes", str(self.preset.currentData() or ""))
        if preset is None:
            self.class_selection.clear()
            self.class_name.setReadOnly(False)
            self._selected_archetype_keys.clear()
            self._refresh_archetypes()
            return
        self.class_selection.setText(
            f"{'Spheres' if str(preset['key']).startswith('spheres-class:') or preset['key'] == 'prodigy' else 'Pathfinder'}  ·  {preset['name']}  ·  {preset.get('category', 'Class')}"
        )
        self.class_name.setText(preset["name"])
        self.class_name.setReadOnly(True)
        self.hit_die.setCurrentIndex(self.hit_die.findData(int(preset["hit_die"])))
        self.bab.setCurrentText(preset["bab"])
        self.fort.setCurrentText(preset["fort"])
        self.reflex.setCurrentText(preset["reflex"])
        self.will.setCurrentText(preset["will"])
        if self.auto_hp.isChecked():
            self.hp_gained.setValue(
                recommended_hit_points(int(preset["hit_die"]), self.level.value())
            )
        self._refresh_archetypes()

    def _refresh_archetypes(self) -> None:
        if not hasattr(self, "archetype_summary"):
            return
        preset_key = str(self.preset.currentData() or "")
        available = {str(entry["key"]): entry for entry in archetype_entries(preset_key)}
        self._selected_archetype_keys.intersection_update(available)
        selected = [available[key] for key in self._selected_archetype_keys if key in available]
        selected.sort(key=lambda entry: str(entry["name"]).casefold())
        self.choose_archetypes_button.setEnabled(bool(available))
        self.choose_archetypes_button.setToolTip(
            (
                f"Browse {len(available)} archetype(s) for this class."
                if available
                else "This class has no cataloged archetypes."
            )
        )
        if selected:
            self.archetype_summary.setText(
                "Selected archetypes:\n" + "\n".join(
                    f"- {entry['name']} ({entry['source_group']}) — changes: "
                    f"{', '.join(archetype_change_labels(entry)) or 'see feature notes'}"
                    for entry in selected
                )
            )
        elif available:
            self.archetype_summary.setText(
                f"No archetypes selected · {len(available)} compatible candidates available for review"
            )
        else:
            self.archetype_summary.setText("No archetypes cataloged for this class")
        self._refresh_optional_archetype_features(selected)

    def _refresh_optional_archetype_features(
        self, selected_archetypes: list[dict] | None = None
    ) -> None:
        """Project all opt-in exchanges declared by the selected archetypes."""

        if not hasattr(self, "optional_exchange_layout"):
            return
        while self.optional_exchange_layout.count():
            item = self.optional_exchange_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.optional_exchange_checkboxes.clear()
        self.archetype_choice_widgets.clear()

        preset_key = str(self.preset.currentData() or "")
        available = {str(entry["key"]): entry for entry in archetype_entries(preset_key)}
        selected_archetypes = selected_archetypes or [
            available[key]
            for key in self.archetype_keys
            if key in available
        ]
        exchanges = [
            (archetype, option)
            for archetype in selected_archetypes
            for option in archetype_optional_features(archetype, self.level.value())
        ]
        declared_choices = [
            (archetype, choice)
            for archetype in selected_archetypes
            for choice in archetype_choices(archetype, self.level.value())
        ]
        exchange_keys = {option.key for _archetype, option in exchanges}
        self._selected_optional_feature_keys.intersection_update(exchange_keys)
        declared_choice_keys = {choice.key for _owner, choice in declared_choices}
        self._selected_archetype_choices = {
            key: values for key, values in self._selected_archetype_choices.items()
            if key in declared_choice_keys
        }
        if not exchanges and not declared_choices:
            self.optional_exchange_container.setVisible(False)
            return

        self.optional_exchange_container.setVisible(True)
        if declared_choices:
            heading = QLabel("ARCHETYPE CHOICES")
            heading.setObjectName("minorTitle")
            self.optional_exchange_layout.addWidget(heading)
            note = QLabel(
                "Required decisions granted by the selected archetypes. Choices are saved "
                "with this class entry and can be changed later by editing it."
            )
            note.setObjectName("mutedText")
            note.setWordWrap(True)
            self.optional_exchange_layout.addWidget(note)
            for owner, choice in declared_choices:
                label = QLabel(
                    f"{choice.name} — {owner.get('name', 'Archetype')} "
                    f"(choose {choice.minimum}" +
                    (f"–{choice.maximum}" if choice.maximum != choice.minimum else "") + ")"
                )
                label.setToolTip(choice.description)
                self.optional_exchange_layout.addWidget(label)
                widgets: list[QWidget] = []
                selected_values = self._selected_archetype_choices.setdefault(choice.key, set())
                valid_keys = {option.key for option in choice.options}
                selected_values.intersection_update(valid_keys)
                if choice.maximum == 1:
                    combo = QComboBox()
                    combo.addItem("Choose…", "")
                    for option in choice.options:
                        combo.addItem(option.name, option.key)
                        combo.setItemData(combo.count() - 1, option.description, Qt.ItemDataRole.ToolTipRole)
                    selected_key = next(iter(selected_values), "")
                    combo.setCurrentIndex(max(0, combo.findData(selected_key)))
                    combo.currentIndexChanged.connect(
                        partial(self._single_archetype_choice_changed, choice.key, combo)
                    )
                    self.optional_exchange_layout.addWidget(combo)
                    widgets.append(combo)
                else:
                    for option in choice.options:
                        checkbox = QCheckBox(option.name)
                        checkbox.setChecked(option.key in selected_values)
                        checkbox.setToolTip(option.description)
                        checkbox.toggled.connect(
                            partial(
                                self._multi_archetype_choice_changed,
                                choice.key, option.key, choice.maximum, checkbox,
                            )
                        )
                        self.optional_exchange_layout.addWidget(checkbox)
                        widgets.append(checkbox)
                self.archetype_choice_widgets[choice.key] = widgets

        if exchanges:
            heading = QLabel("OPTIONAL ARCHETYPE EXCHANGES")
            heading.setObjectName("minorTitle")
            self.optional_exchange_layout.addWidget(heading)
            note = QLabel(
                "These options permanently exchange the listed base-class features. "
                "Unavailable choices conflict with another selected archetype."
            )
            note.setObjectName("mutedText")
            note.setWordWrap(True)
            self.optional_exchange_layout.addWidget(note)
        for owner, option in exchanges:
            other_archetypes = [
                entry for entry in selected_archetypes if entry is not owner
            ]
            conflicts = optional_feature_conflicts(option, other_archetypes)
            if conflicts:
                self._selected_optional_feature_keys.discard(option.key)
            checkbox = QCheckBox(f"{option.name} — {owner.get('name', 'Archetype')}")
            checkbox.setChecked(option.key in self._selected_optional_feature_keys)
            checkbox.setEnabled(not conflicts)
            surrendered = ", ".join(option.replaces) or "See rules text"
            tooltip = (
                f"Gives up: {surrendered}\n\n{option.description}"
                if not conflicts
                else "Unavailable because another selected archetype alters or replaces "
                f"the same feature: {', '.join(conflicts)}.\n\n{option.description}"
            )
            checkbox.setToolTip(tooltip)
            checkbox.toggled.connect(
                partial(self._optional_archetype_feature_toggled, option.key)
            )
            self.optional_exchange_layout.addWidget(checkbox)
            self.optional_exchange_checkboxes[option.key] = checkbox

    def _single_archetype_choice_changed(self, key: str, combo: QComboBox, *_args) -> None:
        value = str(combo.currentData() or "")
        self._selected_archetype_choices[key] = {value} if value else set()
        self._apply_archetype_profile()

    def _multi_archetype_choice_changed(
        self, key: str, option_key: str, maximum: int, checkbox: QCheckBox,
        checked: bool,
    ) -> None:
        values = self._selected_archetype_choices.setdefault(key, set())
        if checked and len(values) >= maximum and option_key not in values:
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
            return
        if checked:
            values.add(option_key)
        else:
            values.discard(option_key)
        self._apply_archetype_profile()

    def _apply_archetype_profile(self) -> None:
        preset = entry_by_key("classes", str(self.preset.currentData() or ""))
        if preset is None:
            return
        selected = [
            definition for key in self.archetype_keys
            if (definition := next(
                (entry for entry in archetype_entries(str(preset["key"])) if str(entry["key"]) == key),
                None,
            )) is not None
        ]
        profile = resolve_class_profile(preset, selected, self.archetype_choice_values)
        self.hit_die.setCurrentIndex(max(0, self.hit_die.findData(profile.hit_die)))
        self.bab.setCurrentText(profile.bab_progression)
        self.fort.setCurrentText(profile.fort_progression)
        self.reflex.setCurrentText(profile.reflex_progression)
        self.will.setCurrentText(profile.will_progression)
        if self.auto_hp.isChecked() and profile.hit_die:
            self.hp_gained.setValue(recommended_hit_points(profile.hit_die, self.level.value()))

    def _optional_archetype_feature_toggled(self, key: str, checked: bool) -> None:
        if checked:
            self._selected_optional_feature_keys.add(key)
        else:
            self._selected_optional_feature_keys.discard(key)

    @property
    def archetype_keys(self) -> tuple[str, ...]:
        available_order = {
            str(entry["key"]): index
            for index, entry in enumerate(archetype_entries(str(self.preset.currentData() or "")))
        }
        return tuple(
            sorted(self._selected_archetype_keys, key=lambda key: available_order.get(key, 999999))
        )

    @property
    def selected_optional_feature_keys(self) -> tuple[str, ...]:
        return tuple(
            key for key in self.optional_exchange_checkboxes
            if key in self._selected_optional_feature_keys
        )

    @property
    def archetype_choice_values(self) -> dict[str, tuple[str, ...]]:
        return {
            key: tuple(sorted(values))
            for key, values in self._selected_archetype_choices.items()
            if values
        }

    def _level_changed(self, *_args) -> None:
        hit_die = int(self.hit_die.currentData() or 0)
        if self.auto_hp.isChecked() and hit_die:
            self.hp_gained.setValue(recommended_hit_points(hit_die, self.level.value()))
        self._refresh_optional_archetype_features()

    def _auto_hp_changed(self, *_args) -> None:
        automatic = self.auto_hp.isChecked()
        self.hp_gained.setEnabled(not automatic)
        if automatic:
            self._level_changed()

    @property
    def values(self) -> dict[str, str | int]:
        return {
            "class_name": self.class_name.text().strip(),
            "level": self.level.value(),
            "bab_progression": self.bab.currentText(),
            "fort_progression": self.fort.currentText(),
            "reflex_progression": self.reflex.currentText(),
            "will_progression": self.will.currentText(),
            "preset_key": str(self.preset.currentData() or ""),
            "hit_die": int(self.hit_die.currentData() or 0),
            "hp_gained": self.hp_gained.value(),
        }

    def _accept_if_valid(self) -> None:
        if not self.class_name.text().strip():
            QMessageBox.warning(self, "Class required", "Enter a class name.")
            return
        definitions = {
            str(entry["key"]): entry
            for entry in archetype_entries(str(self.preset.currentData() or ""))
        }
        compatibility = validate_archetype_selection(self.archetype_keys, definitions)
        if not compatibility.compatible:
            self.archetype_summary.setText("Incompatible selection: " + " ".join(compatibility.reasons))
            self.archetype_summary.setProperty("validationError", True)
            self.archetype_summary.style().unpolish(self.archetype_summary)
            self.archetype_summary.style().polish(self.archetype_summary)
            return
        selected_definitions = [definitions[key] for key in self.archetype_keys if key in definitions]
        missing = []
        for archetype in selected_definitions:
            for choice in archetype_choices(archetype, self.level.value()):
                count = len(self._selected_archetype_choices.get(choice.key, ()))
                if count < choice.minimum or count > choice.maximum:
                    missing.append(
                        f"{choice.name} (choose {choice.minimum}"
                        + (f"–{choice.maximum}" if choice.maximum != choice.minimum else "")
                        + ")"
                    )
        if missing:
            self.archetype_summary.setText("Complete archetype choices: " + "; ".join(missing))
            self.archetype_summary.setProperty("validationError", True)
            self.archetype_summary.style().unpolish(self.archetype_summary)
            self.archetype_summary.style().polish(self.archetype_summary)
            return
        self.accept()

class StatBreakdownDialog(QDialog):
    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        target: str,
        title: str,
        result_provider: Callable[[], CalculationResult],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id = character_id
        self.target = target
        self.title = title
        self.result_provider = result_provider
        self.setWindowTitle(f"{title} breakdown")
        self.resize(720, 460)
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setObjectName("sectionTitle")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Source", "Type", "Value", "Status", "Reason"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        add_button = QPushButton("+ Add modifier")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_modifier)
        toggle_button = QPushButton("Enable / disable")
        toggle_button.clicked.connect(self._toggle_modifier)
        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerButton")
        remove_button.clicked.connect(self._remove_modifier)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(add_button)
        actions.addWidget(toggle_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        result = self.result_provider()
        formatted_total = (
            str(result.total) if self.target in ABILITY_KEYS or self.target in {"ac", "cmd"}
            else f"{result.total:+d}"
        )
        self.summary.setText(f"{self.title}: {formatted_total}")
        self.table.setRowCount(0)
        for contribution in result.contributions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                contribution.source,
                contribution.bonus_type.title(),
                f"{contribution.value:+d}",
                "Applied" if contribution.applied else "Not applied",
                contribution.reason,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, contribution.modifier_id)
                if not contribution.applied:
                    item.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(row, column, item)

    def _selected_modifier_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add_modifier(self) -> None:
        if self.target in ABILITY_KEYS:
            default_type = "enhancement"
        elif self.target in {"fortitude", "reflex", "will"}:
            default_type = "resistance"
        elif self.target == "ac":
            default_type = "armor"
        else:
            default_type = "untyped"
        dialog = ModifierDialog(self.title, default_type, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.add_modifier(
            self.character_id, self.target, dialog.source, dialog.bonus_type, dialog.value
        )
        self.refresh()

    def _toggle_modifier(self) -> None:
        modifier_id = self._selected_modifier_id()
        if modifier_id is None:
            QMessageBox.information(self, "Select a modifier", "Select a custom modifier row.")
            return
        modifier = next(
            item
            for item in self.repository.list_modifiers(self.character_id, self.target)
            if item.id == modifier_id
        )
        self.repository.set_modifier_enabled(self.character_id, modifier_id, not modifier.enabled)
        self.refresh()

    def _remove_modifier(self) -> None:
        modifier_id = self._selected_modifier_id()
        if modifier_id is None:
            QMessageBox.information(self, "Select a modifier", "Select a custom modifier row.")
            return
        self.repository.delete_modifier(self.character_id, modifier_id)
        self.refresh()

class ModifierDialog(QDialog):
    def __init__(
        self,
        stat_name: str,
        default_type: str = "untyped",
        parent: QWidget | None = None,
        *,
        formulas: dict[str, str] | None = None,
        formula_evaluator: Callable[[str], float] | None = None,
        formula_suggestions: Callable[[], tuple] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add {stat_name} modifier")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("e.g. Cloak of Resistance")
        self.type_input = QComboBox()
        self.type_input.addItems(BONUS_TYPES)
        self.type_input.setCurrentText(default_type)
        self.value_input = _formula_number_field(
            -99,
            99,
            1,
            "value",
            formulas,
            formula_evaluator,
            formula_suggestions,
        )
        form.addRow("Source", self.source_input)
        form.addRow("Bonus type", self.type_input)
        form.addRow("Value", self.value_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def source(self) -> str:
        return self.source_input.text().strip()

    @property
    def bonus_type(self) -> str:
        return self.type_input.currentText()

    @property
    def value(self) -> int:
        return int(self.value_input.value())

    @property
    def numeric_formulas(self) -> dict[str, str]:
        return {"value": self.value_input.expression}

    def _accept_if_valid(self) -> None:
        if not self.source:
            QMessageBox.warning(self, "Source required", "Enter where this modifier comes from.")
            return
        try:
            value = self.value
        except FormulaError as error:
            QMessageBox.warning(self, "Invalid modifier value", str(error))
            return
        if value == 0:
            QMessageBox.warning(self, "Value required", "Enter a non-zero value.")
            return
        self.accept()
