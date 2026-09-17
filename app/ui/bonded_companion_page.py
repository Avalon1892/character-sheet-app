"""Shared, data-driven page used by Familiar and class-companion providers."""
from __future__ import annotations

from dataclasses import replace
import json

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bonded_companion_rules import (
    BONDED_COMPANION_DEFINITIONS,
    bonded_companion_progression,
    calculate_familiar_statistics,
    familiar_catalog,
    familiar_entry,
)
from app.models import ABILITIES
from app.ui.components import section_title
from app.ui.familiar_dialog import FamiliarCatalogDialog


_DEFINITIONS = {item.key: item for item in BONDED_COMPANION_DEFINITIONS}
_ABILITY_SHORT = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
}


def _ability_modifier(score: int) -> int:
    return (int(score) - 10) // 2


class BondedCompanionPanel(QWidget):
    """Editable presentation over one provider-owned companion record."""

    grant_changed = Signal()

    def __init__(self, repository, companion_key: str, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.companion_key = companion_key
        self.character_id: int | None = None
        self._loading = False
        self._automatic_ability_scores: dict[str, int] = {}
        self._last_refresh: dict = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self._save)
        definition = _DEFINITIONS[companion_key]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(9)
        layout.addWidget(section_title(definition.name.upper()))
        self.source = QLabel()
        self.source.setObjectName("mutedText")
        self.source.setWordWrap(True)
        layout.addWidget(self.source)

        identity = QWidget()
        identity.setObjectName("sheetSection")
        identity_layout = QGridLayout(identity)
        self.name = QLineEdit()
        self.species = QLineEdit()
        self.choose_familiar = QPushButton("Choose Familiar…")
        self.choose_familiar.setVisible(companion_key == "familiar")
        self.current_hp = QSpinBox()
        self.temporary_hp = QSpinBox()
        for control in (self.current_hp, self.temporary_hp):
            control.setRange(0, 999999)
        identity_layout.addWidget(QLabel("Name"), 0, 0)
        identity_layout.addWidget(self.name, 0, 1)
        identity_layout.addWidget(QLabel("Species / form"), 0, 2)
        species_row = QHBoxLayout()
        species_row.setContentsMargins(0, 0, 0, 0)
        species_row.addWidget(self.species, 1)
        species_row.addWidget(self.choose_familiar)
        identity_layout.addLayout(species_row, 0, 3)
        identity_layout.addWidget(QLabel("Maximum HP"), 1, 0)
        self.maximum_hp = QLabel("—")
        self.maximum_hp.setObjectName("calculatedValue")
        self.maximum_hp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        identity_layout.addWidget(self.maximum_hp, 1, 1)
        identity_layout.addWidget(QLabel("Current / Temporary HP"), 1, 2)
        health_row = QHBoxLayout()
        health_row.setContentsMargins(0, 0, 0, 0)
        health_row.addWidget(self.current_hp)
        health_row.addWidget(QLabel("/"))
        health_row.addWidget(self.temporary_hp)
        identity_layout.addLayout(health_row, 1, 3)
        self.pet_stack = QCheckBox(
            "Stack the Beastmastery Pet effective level with the class familiar"
        )
        self.pet_stack.setToolTip(
            "The Pet talent allows this choice when the character also has a familiar "
            "from another source. The combined effective level cannot exceed character level."
        )
        self.pet_stack.setVisible(False)
        identity_layout.addWidget(self.pet_stack, 2, 0, 1, 4)
        layout.addWidget(identity)

        columns = QHBoxLayout()
        columns.setSpacing(9)
        statistics = QWidget()
        statistics.setObjectName("sheetSection")
        stats_layout = QVBoxLayout(statistics)
        stats_layout.addWidget(section_title("STATISTICS & PROGRESSION"))
        self.progression = self._rule_table(("Statistic", "Current"))
        stats_layout.addWidget(self.progression)
        abilities = QGridLayout()
        abilities.addWidget(QLabel("Ability"), 0, 0)
        abilities.addWidget(QLabel("Score"), 0, 1)
        abilities.addWidget(QLabel("Modifier"), 0, 2)
        self.ability_fields: dict[str, QSpinBox] = {}
        self.ability_modifiers: dict[str, QLabel] = {}
        for row, (key, _name, short_name) in enumerate(ABILITIES, 1):
            field = QSpinBox()
            field.setRange(0, 999)
            modifier = QLabel("+0")
            modifier.setAlignment(Qt.AlignmentFlag.AlignCenter)
            abilities.addWidget(QLabel(short_name), row, 0)
            abilities.addWidget(field, row, 1)
            abilities.addWidget(modifier, row, 2)
            self.ability_fields[key] = field
            self.ability_modifiers[key] = modifier
            field.valueChanged.connect(self._save)
        stats_layout.addLayout(abilities)
        columns.addWidget(statistics, 2)

        training = QWidget()
        training.setObjectName("sheetSection")
        training_layout = QFormLayout(training)
        training_layout.addRow(section_title("CREATURE DETAILS & TRAINING"))
        self.creature_details = self._rule_table(("Published statistic", "Current"))
        training_layout.addRow(self.creature_details)
        self.attacks = QPlainTextEdit()
        self.attacks.setPlaceholderText("Additional or adjusted attacks, one per line")
        self.skills = QPlainTextEdit()
        self.skills.setPlaceholderText("Additional skill notes or overrides")
        self.feats = QPlainTextEdit()
        self.feats.setPlaceholderText("Additional or replacement feats")
        self.specials = QPlainTextEdit()
        self.specials.setPlaceholderText("Additional evolutions, powers, or special abilities")
        self.notes = QPlainTextEdit()
        for control in (self.attacks, self.skills, self.feats, self.specials, self.notes):
            control.setMaximumHeight(90)
        training_layout.addRow("Attack adjustments", self.attacks)
        training_layout.addRow("Skill adjustments", self.skills)
        training_layout.addRow("Feat adjustments", self.feats)
        training_layout.addRow("Custom abilities", self.specials)
        training_layout.addRow("Notes", self.notes)
        columns.addWidget(training, 3)
        layout.addLayout(columns)
        layout.addStretch()

        self.name.editingFinished.connect(self._save)
        self.species.editingFinished.connect(self._save)
        self.choose_familiar.clicked.connect(self._choose_familiar)
        self.current_hp.editingFinished.connect(self._save)
        self.temporary_hp.editingFinished.connect(self._save)
        self.pet_stack.toggled.connect(self._pet_stack_changed)
        for control in (self.attacks, self.skills, self.feats, self.specials, self.notes):
            control.textChanged.connect(self._schedule_save)

    @staticmethod
    def _rule_table(headers: tuple[str, str]) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setWordWrap(True)
        return table

    @staticmethod
    def _details(text: str) -> dict:
        try:
            value = json.loads(text or "{}")
        except (TypeError, ValueError):
            return {}
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _populate_rule_table(table: QTableWidget, rows) -> None:
        table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(str(label)))
            table.setItem(row, 1, QTableWidgetItem(str(value)))
        table.resizeRowsToContents()
        table.setFixedHeight(
            table.horizontalHeader().height()
            + sum(table.rowHeight(row) for row in range(len(rows)))
            + 4
        )

    def refresh(
        self,
        character_id: int,
        effective_level: int,
        *,
        variant: str = "standard",
        sources: tuple[str, ...] = (),
        can_stack_pet: bool = False,
        stacks_pet: bool = False,
        master_statistics: dict | None = None,
    ) -> None:
        self._save_timer.stop()
        self.character_id = character_id
        record = self.repository.get_bonded_companion(character_id, self.companion_key)
        details = self._details(record.details_json)
        progression = bonded_companion_progression(self.companion_key, effective_level, variant)
        definition = _DEFINITIONS[self.companion_key]
        familiar_stats = None
        selected_entry = None
        if self.companion_key == "familiar" and master_statistics is not None:
            selected_entry = familiar_entry(str(details.get("familiar_key") or ""))
            if selected_entry is None and record.species:
                selected_entry = next(
                    (
                        entry for entry in familiar_catalog()
                        if str(entry.get("name", "")).casefold() == record.species.casefold()
                    ),
                    None,
                )
            overrides = details.get("abilities", {})
            if not isinstance(overrides, dict):
                overrides = {}
            familiar_stats = calculate_familiar_statistics(
                selected_entry,
                progression,
                master_statistics,
                variant=variant,
                ability_overrides=overrides,
                details=details,
            )
            raw_scores = dict(selected_entry.get("abilities") or {}) if selected_entry else {}
            self._automatic_ability_scores = {
                long_name: int(raw_scores.get(short_name, 10))
                for long_name, short_name in _ABILITY_SHORT.items()
            }
            if variant != "beastmastery_pet" and progression.intelligence is not None:
                self._automatic_ability_scores["intelligence"] = progression.intelligence
        else:
            if self.companion_key == "phantom":
                base_scores = {
                    "strength": 12,
                    "dexterity": 14 + progression.ability_bonus,
                    "constitution": 13,
                    "intelligence": 7,
                    "wisdom": 10,
                    "charisma": 13 + progression.ability_bonus,
                }
                self._automatic_ability_scores = base_scores
            else:
                self._automatic_ability_scores = {
                    key: 10 for key, _name, _short in ABILITIES
                }

        self._loading = True
        try:
            self.name.setText(record.name)
            self.species.setText(record.species)
            self.current_hp.setValue(record.current_hp)
            self.temporary_hp.setValue(record.temporary_hp)
            self.maximum_hp.setText(str(familiar_stats.maximum_hp) if familiar_stats else "—")
            self.pet_stack.setVisible(can_stack_pet)
            self.pet_stack.setChecked(stacks_pet)
            saved_abilities = details.get("abilities", {})
            if not isinstance(saved_abilities, dict):
                saved_abilities = {}
            for ability, field in self.ability_fields.items():
                if familiar_stats is not None:
                    value = int(familiar_stats.abilities[_ABILITY_SHORT[ability]])
                else:
                    value = int(
                        saved_abilities.get(
                            ability, self._automatic_ability_scores.get(ability, 10)
                        )
                    )
                field.setValue(value)
                self.ability_modifiers[ability].setText(f"{_ability_modifier(value):+d}")
            self.attacks.setPlainText(str(details.get("attacks") or ""))
            self.skills.setPlainText(str(details.get("skills") or ""))
            self.feats.setPlainText(str(details.get("feats") or ""))
            self.specials.setPlainText(str(details.get("specials") or ""))
            self.notes.setPlainText(record.notes)
        finally:
            self._loading = False

        if familiar_stats is not None:
            rows = (
                ("Effective familiar level", progression.level),
                ("Type / size", f"{familiar_stats.creature_type} · {familiar_stats.size}"),
                ("Creature HD / effective HD", f"{familiar_stats.hit_dice} / {familiar_stats.effective_hit_dice}"),
                ("Initiative", f"{familiar_stats.initiative:+d}"),
                ("Speed", familiar_stats.speed),
                ("Senses", familiar_stats.senses),
                ("AC / touch / flat-footed", f"{familiar_stats.armor_class} / {familiar_stats.touch_ac} / {familiar_stats.flat_footed_ac}"),
                ("BAB / CMB / CMD", f"{familiar_stats.base_attack_bonus:+d} / {familiar_stats.cmb:+d} / {familiar_stats.cmd}"),
                ("Fort / Ref / Will", f"{familiar_stats.saves['fortitude']:+d} / {familiar_stats.saves['reflex']:+d} / {familiar_stats.saves['will']:+d}"),
                ("Natural armor", f"+{familiar_stats.natural_armor}"),
                ("Spell resistance", familiar_stats.spell_resistance),
                ("Familiar abilities", ", ".join(progression.specials) or "—"),
            )
            creature_rows = tuple(
                (f"Attack · {attack.name}", f"{attack.attack_bonus:+d} · {attack.damage}")
                for attack in familiar_stats.attacks
            ) + (
                ("Published feats", familiar_stats.feats),
                ("Published skills", familiar_stats.skills),
                ("Special qualities", familiar_stats.special_qualities),
                ("Master benefit", familiar_stats.familiar_special),
                ("Catalog source", f"{familiar_stats.ruleset} · {familiar_stats.source}"),
            )
        else:
            rows = (
                ("Effective level", progression.level),
                ("Hit Dice", progression.hit_dice),
                ("BAB", progression.bab),
                ("Fortitude", progression.fortitude),
                ("Reflex", progression.reflex),
                ("Will", progression.will),
                ("Natural armor bonus", f"+{progression.natural_armor}"),
                ("Dexterity / Charisma bonus", f"+{progression.ability_bonus}"),
                ("Natural attack damage", progression.natural_attack_damage),
                ("Intelligence", progression.intelligence if progression.intelligence is not None else "Use creature"),
                ("Skill ranks", progression.skill_ranks if progression.skill_ranks is not None else "Use creature rules"),
                ("Feats", progression.feats if progression.feats is not None else "Use creature rules"),
                ("Ability increases", progression.ability_increases),
                ("Automatic abilities", ", ".join(progression.specials) or "—"),
            )
            creature_rows = ()
        self._populate_rule_table(self.progression, rows)
        self._populate_rule_table(self.creature_details, creature_rows)
        self.source.setText(
            f"{definition.source} · effective level {progression.level}. "
            + (f"Sources: {'; '.join(sources)}. " if sources else "")
            + (
                "Beastmastery Pet retains the animal type and omits its listed familiar benefits. "
                if variant == "beastmastery_pet" else ""
            )
            + "Published progression is automatic; character-specific choices remain editable."
        )
        self._last_refresh = {
            "effective_level": effective_level,
            "variant": variant,
            "sources": sources,
            "can_stack_pet": can_stack_pet,
            "stacks_pet": stacks_pet,
            "master_statistics": master_statistics,
        }

    def _save(self, *_args) -> None:
        if self._loading or self.character_id is None:
            return
        record = self.repository.get_bonded_companion(self.character_id, self.companion_key)
        details = self._details(record.details_json)
        details.update(
            abilities={
                key: control.value()
                for key, control in self.ability_fields.items()
                if control.value() != self._automatic_ability_scores.get(key, 10)
            },
            attacks=self.attacks.toPlainText(),
            skills=self.skills.toPlainText(),
            feats=self.feats.toPlainText(),
            specials=self.specials.toPlainText(),
            beastmastery_pet_stack=self.pet_stack.isChecked(),
        )
        self.repository.update_bonded_companion(
            replace(
                record,
                name=self.name.text(),
                species=self.species.text(),
                current_hp=self.current_hp.value(),
                temporary_hp=self.temporary_hp.value(),
                details_json=json.dumps(details),
                notes=self.notes.toPlainText(),
            )
        )
        for ability, field in self.ability_fields.items():
            self.ability_modifiers[ability].setText(f"{_ability_modifier(field.value()):+d}")

    def _choose_familiar(self) -> None:
        if self.character_id is None or self.companion_key != "familiar":
            return
        record = self.repository.get_bonded_companion(self.character_id, self.companion_key)
        details = self._details(record.details_json)
        dialog = FamiliarCatalogDialog(str(details.get("familiar_key") or ""), self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_entry is None:
            return
        entry = dialog.selected_entry
        details["familiar_key"] = str(entry.get("key") or "")
        details["abilities"] = {}
        self.repository.update_bonded_companion(
            replace(
                record,
                species=str(entry.get("name") or ""),
                details_json=json.dumps(details),
            )
        )
        self.grant_changed.emit()

    def _pet_stack_changed(self, *_args) -> None:
        if self._loading:
            return
        self._save()
        self.grant_changed.emit()

    def _schedule_save(self) -> None:
        if not self._loading:
            self._save_timer.start()
