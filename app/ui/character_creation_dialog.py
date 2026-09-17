"""Logical, rules-aware guided character creation workflow."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSizePolicy,
    QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from app.ability_score_generation import validate_ability_scores
from app.character_creation import CharacterCreationDraft
from app.models import ABILITIES, ALIGNMENTS, CHARACTER_TYPES, SIZES, CharacterDetails, RaceTraitChoice
from app.race_rules import (
    race_modifier_map, racial_choice_specs, resolved_race,
    validate_race_trait_choices,
)
from app.ui.ability_assignment_widget import AbilityAssignmentWidget
from app.ui.dialogs import ClassLevelDialog
from app.ui.race_dialog import RaceCatalogDialog


class GuidedCharacterCreationDialog(QDialog):
    """Create a complete starting shell without duplicating rules services."""

    STEP_NAMES = ("Identity", "Race", "Class", "Abilities", "Review")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create character")
        self.resize(1120, 760)
        self.setMinimumSize(920, 640)
        self._class_dialog: ClassLevelDialog | None = None
        self._race_selection: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        heading = QLabel("CREATE A CHARACTER")
        heading.setObjectName("heroTitle")
        outer.addWidget(heading)
        subtitle = QLabel(
            "Build the rules-ready foundation now. Every selection remains editable on the sheet."
        )
        subtitle.setObjectName("pageSubtitle")
        outer.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.steps = QListWidget()
        self.steps.setObjectName("creationStepList")
        self.steps.setFixedWidth(176)
        self.steps.setSpacing(3)
        for number, name in enumerate(self.STEP_NAMES, 1):
            item = QListWidgetItem(f"{number}   {name}")
            item.setData(Qt.ItemDataRole.UserRole, number - 1)
            self.steps.addItem(item)
        body.addWidget(self.steps)

        self.pages = QStackedWidget()
        self.pages.setObjectName("creationPages")
        self.pages.addWidget(self._identity_page())
        self.pages.addWidget(self._race_page())
        self.pages.addWidget(self._class_page())
        self.pages.addWidget(self._abilities_page())
        self.pages.addWidget(self._review_page())
        body.addWidget(self.pages, 1)

        summary = QFrame()
        summary.setObjectName("creationSummary")
        summary.setMinimumWidth(250)
        summary.setMaximumWidth(300)
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_title = QLabel("CHARACTER SUMMARY")
        summary_title.setObjectName("sectionTitle")
        summary_layout.addWidget(summary_title)
        self.summary_name = QLabel("Unnamed character")
        self.summary_name.setObjectName("creationSummaryName")
        self.summary_name.setWordWrap(True)
        summary_layout.addWidget(self.summary_name)
        self.summary_rules = QLabel("Pathfinder 1e")
        self.summary_rules.setObjectName("mutedText")
        summary_layout.addWidget(self.summary_rules)
        self.summary_identity = QLabel("No ancestry selected")
        self.summary_identity.setWordWrap(True)
        summary_layout.addWidget(self.summary_identity)
        self.summary_class = QLabel("Class can be added later")
        self.summary_class.setWordWrap(True)
        summary_layout.addWidget(self.summary_class)
        self.summary_abilities = QLabel()
        self.summary_abilities.setObjectName("creationAbilitySummary")
        self.summary_abilities.setWordWrap(True)
        summary_layout.addWidget(self.summary_abilities)
        summary_layout.addStretch()
        summary_note = QLabel("Base scores are saved before racial adjustments.")
        summary_note.setObjectName("mutedText")
        summary_note.setWordWrap(True)
        summary_layout.addWidget(summary_note)
        body.addWidget(summary)
        outer.addLayout(body, 1)

        navigation = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._go_back)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("primaryButton")
        self.next_button.clicked.connect(self._go_next)
        self.create_button = QPushButton("Create character")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._accept)
        navigation.addWidget(self.cancel_button)
        navigation.addStretch()
        navigation.addWidget(self.back_button)
        navigation.addWidget(self.next_button)
        navigation.addWidget(self.create_button)
        outer.addLayout(navigation)

        self.steps.currentRowChanged.connect(self._set_step)
        self.pages.currentChanged.connect(self._page_changed)
        self.name.textChanged.connect(self._refresh_summary)
        self.character_type.currentTextChanged.connect(self._refresh_summary)
        self.alignment.currentTextChanged.connect(self._refresh_summary)
        self.ability_assignment.scoresChanged.connect(self._refresh_summary)
        self.steps.setCurrentRow(0)
        self._rebuild_race_distribution()
        self._refresh_racial_adjustments()
        self._refresh_summary()

    @staticmethod
    def _page(title: str, description: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 12, 18, 12)
        heading = QLabel(title.upper())
        heading.setObjectName("creationPageTitle")
        layout.addWidget(heading)
        note = QLabel(description)
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        return page, layout

    def _identity_page(self) -> QWidget:
        page, layout = self._page(
            "Identity",
            "Start with the information that defines the character record. Optional details may be left blank.",
        )
        card = QFrame()
        card.setObjectName("creationChoiceCard")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Character name")
        self.player_name = QLineEdit()
        self.player_name.setPlaceholderText("Optional")
        self.character_type = QComboBox()
        self.character_type.addItems(CHARACTER_TYPES)
        self.alignment = QComboBox()
        self.alignment.addItems(ALIGNMENTS)
        self.deity = QLineEdit()
        self.deity.setPlaceholderText("Optional")
        form.addRow("Character name", self.name)
        form.addRow("Player", self.player_name)
        form.addRow("Rules foundation", self.character_type)
        form.addRow("Alignment", self.alignment)
        form.addRow("Deity", self.deity)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _race_page(self) -> QWidget:
        page, layout = self._page(
            "Race",
            "Choose a catalog race or enter a custom one. If the race grants flexible ability increases, assign them here after making the selection.",
        )
        card = QFrame()
        card.setObjectName("creationChoiceCard")
        card_layout = QVBoxLayout(card)
        form = QFormLayout()
        self.race = QLineEdit()
        self.race.setPlaceholderText("Choose from the catalog or enter a custom race")
        self.race.textEdited.connect(self._custom_race_edited)
        self.size = QComboBox()
        self.size.addItems(SIZES)
        self.size.setCurrentText("Medium")
        self.size.currentTextChanged.connect(self._refresh_summary)
        form.addRow("Race", self.race)
        form.addRow("Size", self.size)
        card_layout.addLayout(form)
        action_row = QHBoxLayout()
        choose = QPushButton("Choose / configure race…")
        choose.setObjectName("primaryButton")
        choose.clicked.connect(self._choose_race)
        clear = QPushButton("Use custom race")
        clear.clicked.connect(self._clear_catalog_race)
        action_row.addWidget(choose)
        action_row.addWidget(clear)
        action_row.addStretch()
        card_layout.addLayout(action_row)
        self.race_summary = QLabel("No catalog race selected")
        self.race_summary.setObjectName("mutedText")
        self.race_summary.setWordWrap(True)
        card_layout.addWidget(self.race_summary)
        layout.addWidget(card)

        self.race_distribution = QFrame()
        self.race_distribution.setObjectName("creationChoiceCard")
        distribution_layout = QVBoxLayout(self.race_distribution)
        distribution_heading = QLabel("RACIAL ABILITY INCREASES")
        distribution_heading.setObjectName("minorTitle")
        distribution_layout.addWidget(distribution_heading)
        self.race_distribution_form = QFormLayout()
        self.race_distribution_form.setSpacing(8)
        distribution_layout.addLayout(self.race_distribution_form)
        self.race_distribution_status = QLabel("")
        self.race_distribution_status.setObjectName("mutedText")
        self.race_distribution_status.setWordWrap(True)
        distribution_layout.addWidget(self.race_distribution_status)
        layout.addWidget(self.race_distribution)
        layout.addStretch()
        return page

    def _class_page(self) -> QWidget:
        page, layout = self._page(
            "First class",
            "Choose the starting class, compatible archetypes, and any required archetype decisions. You may also create the character without a class.",
        )
        card = QFrame()
        card.setObjectName("creationChoiceCard")
        card_layout = QVBoxLayout(card)
        self.class_summary = QLabel("No first class selected")
        self.class_summary.setObjectName("creationLargeChoice")
        self.class_summary.setWordWrap(True)
        card_layout.addWidget(self.class_summary)
        self.class_details = QLabel("A class can be added later from Page 0.")
        self.class_details.setObjectName("mutedText")
        self.class_details.setWordWrap(True)
        card_layout.addWidget(self.class_details)
        row = QHBoxLayout()
        choose = QPushButton("Choose class and archetypes…")
        choose.setObjectName("primaryButton")
        choose.clicked.connect(self._choose_class)
        clear = QPushButton("Clear class")
        clear.clicked.connect(self._clear_class)
        row.addWidget(choose)
        row.addWidget(clear)
        row.addStretch()
        card_layout.addLayout(row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _abilities_page(self) -> QWidget:
        page, layout = self._page(
            "Ability scores",
            "Assign a standard array or enter scores manually. Racial adjustments are previewed but stored separately, so changing race later remains safe.",
        )
        card = QFrame()
        card.setObjectName("creationChoiceCard")
        card_layout = QVBoxLayout(card)
        self.ability_assignment = AbilityAssignmentWidget()
        card_layout.addWidget(self.ability_assignment)
        layout.addWidget(card, 1)
        return page

    def _review_page(self) -> QWidget:
        page, layout = self._page(
            "Review",
            "Review the starting record before it is created. Nothing here locks future editing.",
        )
        self.review = QTextBrowser()
        self.review.setObjectName("creationReview")
        self.review.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.review, 1)
        return page

    def _choose_race(self) -> None:
        dialog = RaceCatalogDialog(self._race_details(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selection = dialog.selection()
        if not selection:
            return
        self._race_selection = dict(selection)
        self.race.setText(str(selection["race_name"]))
        self.size.setCurrentText(str(selection["size"]))
        extras: list[str] = []
        if selection.get("variant_key"):
            extras.append("heritage selected")
        if selection.get("alternate_trait_keys"):
            extras.append(f"{len(selection['alternate_trait_keys'])} alternate trait(s)")
        self.race_summary.setText(
            "Catalog rules active" + (" · " + " · ".join(extras) if extras else "")
        )
        self._rebuild_race_distribution()
        self._refresh_racial_adjustments()
        self._refresh_summary()

    def _custom_race_edited(self) -> None:
        if self._race_selection:
            self._race_selection = {}
            self.race_summary.setText("Custom race · no catalog automation")
            self._rebuild_race_distribution()
            self._refresh_racial_adjustments()
        self._refresh_summary()

    def _clear_catalog_race(self) -> None:
        self._race_selection = {}
        self.race_summary.setText("Custom race · no catalog automation")
        self.race.setFocus()
        self._rebuild_race_distribution()
        self._refresh_racial_adjustments()
        self._refresh_summary()

    def _race_details(self) -> CharacterDetails:
        selection = self._race_selection
        return CharacterDetails(
            -1,
            player_name=self.player_name.text().strip(),
            race=self.race.text().strip(),
            alignment=self.alignment.currentText(),
            deity=self.deity.text().strip(),
            size=self.size.currentText(),
            race_key=str(selection.get("race_key") or ""),
            race_ability_choice=str(selection.get("ability_choice") or ""),
            race_variant_key=str(selection.get("variant_key") or ""),
            race_alternate_trait_keys=tuple(selection.get("alternate_trait_keys") or ()),
            race_trait_choices=tuple(selection.get("trait_choices") or ()),
        )

    def _refresh_racial_adjustments(self) -> None:
        modifiers = race_modifier_map(self._race_details())
        adjustments = {
            ability: sum(modifier.value for modifier in values if modifier.enabled)
            for ability, values in modifiers.items()
        }
        self.ability_assignment.set_racial_adjustments(adjustments)

    def _clear_race_distribution_form(self) -> None:
        while self.race_distribution_form.rowCount():
            self.race_distribution_form.removeRow(0)

    def _rebuild_race_distribution(self) -> None:
        """Render only rules-defined distributable racial ability increases."""

        self._clear_race_distribution_form()
        self._race_trait_ability_controls: dict[tuple[str, str], tuple[QComboBox, ...]] = {}
        details = self._race_details()
        profile = resolved_race(details)
        if profile.entry is None:
            self.race_distribution.hide()
            return

        fixed = [
            f"{int(value):+d} {next((short for key, _name, short in ABILITIES if key == ability), ability.upper())}"
            for ability, value in profile.adjustments.items()
            if ability in {key for key, _name, _short in ABILITIES} and int(value)
        ]
        if fixed:
            fixed_label = QLabel(" · ".join(fixed))
            fixed_label.setObjectName("creationRacialAdjustmentSummary")
            self.race_distribution_form.addRow("Fixed adjustments", fixed_label)

        has_choice = False
        if profile.flexible_bonus:
            has_choice = True
            combo = self._ability_choice_combo(details.race_ability_choice)
            combo.currentIndexChanged.connect(
                lambda _index, field=combo: self._base_racial_ability_changed(field)
            )
            self.race_distribution_form.addRow(
                f"Flexible +{profile.flexible_bonus}", combo
            )
            self._base_racial_ability = combo

        choice_map = {
            (choice.trait_key, choice.choice_key): tuple(choice.values)
            for choice in details.race_trait_choices
        }
        ability_keys = {key for key, _name, _short in ABILITIES}
        for trait, spec in racial_choice_specs(
            profile.entry, details.race_alternate_trait_keys
        ):
            options = {
                str(option.get("key") or "")
                for option in spec.get("options", ())
            }
            if str(spec.get("kind") or "options") != "options" or not options or not options.issubset(ability_keys):
                continue
            has_choice = True
            key = (str(trait.get("key") or ""), str(spec.get("key") or ""))
            selected = choice_map.get(key, ())
            maximum = int(spec.get("maximum", spec.get("count", 1)) or 1)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            controls: list[QComboBox] = []
            for index in range(maximum):
                value = selected[index] if index < len(selected) else ""
                combo = self._ability_choice_combo(value, spec.get("options", ()))
                combo._previous_value = value
                combo.currentIndexChanged.connect(
                    lambda _index, choice_key=key, field=combo, distinct=bool(spec.get("distinct")):
                    self._trait_racial_ability_changed(choice_key, field, distinct)
                )
                row_layout.addWidget(combo, 1)
                controls.append(combo)
            self._race_trait_ability_controls[key] = tuple(controls)
            self.race_distribution_form.addRow(
                f"{trait.get('name', 'Racial trait')} · {spec.get('label', 'Ability')}", row
            )

        self.race_distribution_status.setText(
            "Choose where each flexible racial increase applies. These choices remain separate from base scores."
            if has_choice else "This race has only fixed ability adjustments."
        )
        self.race_distribution.setVisible(bool(fixed or has_choice))

    @staticmethod
    def _ability_choice_combo(
        selected: str = "", options: object = (),
    ) -> QComboBox:
        combo = QComboBox()
        combo.addItem("Choose ability…", "")
        labels = {
            str(option.get("key") or ""): str(option.get("label") or option.get("key") or "")
            for option in options if isinstance(option, dict)
        }
        for key, name, _short in ABILITIES:
            if labels and key not in labels:
                continue
            combo.addItem(labels.get(key, name), key)
        combo.setCurrentIndex(max(0, combo.findData(selected)))
        return combo

    def _base_racial_ability_changed(self, combo: QComboBox) -> None:
        self._race_selection["ability_choice"] = str(combo.currentData() or "")
        self._refresh_racial_adjustments()
        self._refresh_summary()

    def _trait_racial_ability_changed(
        self, key: tuple[str, str], changed: QComboBox, distinct: bool,
    ) -> None:
        controls = self._race_trait_ability_controls.get(key, ())
        values = [str(combo.currentData() or "") for combo in controls]
        chosen = [value for value in values if value]
        if distinct and len(chosen) != len(set(chosen)):
            previous = str(getattr(changed, "_previous_value", "") or "")
            changed.blockSignals(True)
            changed.setCurrentIndex(max(0, changed.findData(previous)))
            changed.blockSignals(False)
            self.race_distribution_status.setText(
                "Each increase from this racial trait must use a different ability."
            )
            return
        changed._previous_value = str(changed.currentData() or "")
        existing = {
            (choice.trait_key, choice.choice_key): choice
            for choice in tuple(self._race_selection.get("trait_choices") or ())
        }
        if chosen:
            existing[key] = RaceTraitChoice(key[0], key[1], tuple(chosen))
        else:
            existing.pop(key, None)
        self._race_selection["trait_choices"] = tuple(existing.values())
        self.race_distribution_status.setText(
            "Racial ability choices updated. The starting-score preview now includes them."
        )
        self._refresh_racial_adjustments()
        self._refresh_summary()

    def _choose_class(self) -> None:
        dialog = ClassLevelDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._class_dialog = dialog
        archetype_count = len(dialog.archetype_keys)
        self.class_summary.setText(f"{dialog.values['class_name']} · level {dialog.values['level']}")
        details = [
            f"d{dialog.values['hit_die']} Hit Die"
            if dialog.values["hit_die"] else "Custom Hit Die"
        ]
        if archetype_count:
            details.append(f"{archetype_count} archetype(s)")
        self.class_details.setText(" · ".join(details))
        self._refresh_summary()

    def _clear_class(self) -> None:
        self._class_dialog = None
        self.class_summary.setText("No first class selected")
        self.class_details.setText("A class can be added later from Page 0.")
        self._refresh_summary()

    def _set_step(self, index: int) -> None:
        if index >= 0 and index != self.pages.currentIndex():
            self.pages.setCurrentIndex(index)

    def _page_changed(self, index: int) -> None:
        self.steps.blockSignals(True)
        self.steps.setCurrentRow(index)
        self.steps.blockSignals(False)
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < self.pages.count() - 1)
        self.create_button.setVisible(index == self.pages.count() - 1)
        if index == self.pages.count() - 1:
            self._refresh_review()

    def _go_back(self) -> None:
        self.pages.setCurrentIndex(max(0, self.pages.currentIndex() - 1))

    def _go_next(self) -> None:
        if not self._validate_step(self.pages.currentIndex()):
            return
        self.pages.setCurrentIndex(min(self.pages.count() - 1, self.pages.currentIndex() + 1))

    def _validate_step(self, index: int) -> bool:
        if index == 0 and not self.name.text().strip():
            QMessageBox.information(self, "Name required", "Enter a character name before continuing.")
            self.name.setFocus()
            return False
        if index == 1:
            race_details = self._race_details()
            profile = resolved_race(race_details)
            if profile.flexible_bonus and not race_details.race_ability_choice:
                QMessageBox.information(
                    self,
                    "Racial ability increase",
                    f"Choose which ability receives the flexible +{profile.flexible_bonus} racial increase.",
                )
                return False
            choice_errors = validate_race_trait_choices(
                profile.entry or {},
                race_details.race_alternate_trait_keys,
                race_details.race_trait_choices,
            )
            if choice_errors:
                QMessageBox.information(
                    self, "Racial trait choice", "\n".join(choice_errors)
                )
                return False
        if index == 3:
            errors = validate_ability_scores(self.ability_assignment.scores())
            if errors:
                QMessageBox.warning(self, "Ability scores", "\n".join(errors))
                return False
        return True

    def _accept(self) -> None:
        if not self._validate_step(0) or not self._validate_step(3):
            return
        self.accept()

    def _refresh_summary(self, *_args) -> None:
        self.summary_name.setText(self.name.text().strip() or "Unnamed character")
        alignment = self.alignment.currentText() or "No alignment"
        self.summary_rules.setText(f"{self.character_type.currentText()} · {alignment}")
        race = self.race.text().strip()
        self.summary_identity.setText(
            f"{race} · {self.size.currentText()}"
            if race else f"No ancestry · {self.size.currentText()}"
        )
        dialog = self._class_dialog
        self.summary_class.setText(
            f"{dialog.values['class_name']} {dialog.values['level']}"
            if dialog else "Class can be added later"
        )
        labels = {
            "strength": "STR", "dexterity": "DEX", "constitution": "CON",
            "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA",
        }
        scores = self.ability_assignment.scores()
        self.summary_abilities.setText(
            "  ·  ".join(f"{labels[key]} {scores[key]}" for key in labels)
        )
        if self.pages.currentIndex() == self.pages.count() - 1:
            self._refresh_review()

    def _refresh_review(self) -> None:
        dialog = self._class_dialog
        race = html.escape(self.race.text().strip() or "Not selected")
        class_name = (
            f"{html.escape(str(dialog.values['class_name']))} level {dialog.values['level']}"
            if dialog else "Not selected"
        )
        archetypes = (
            f"{len(dialog.archetype_keys)} selected" if dialog and dialog.archetype_keys else "None"
        )
        scores = self.ability_assignment.scores()
        rows = "".join(
            f"<tr><td>{name}</td><td><b>{scores[key]}</b></td></tr>"
            for key, name in (
                ("strength", "Strength"), ("dexterity", "Dexterity"),
                ("constitution", "Constitution"), ("intelligence", "Intelligence"),
                ("wisdom", "Wisdom"), ("charisma", "Charisma"),
            )
        )
        self.review.setHtml(
            f"<h1>{html.escape(self.name.text().strip() or 'Unnamed character')}</h1>"
            f"<p><b>Rules:</b> {html.escape(self.character_type.currentText())}<br>"
            f"<b>Player:</b> {html.escape(self.player_name.text().strip() or '—')}<br>"
            f"<b>Race:</b> {race} ({html.escape(self.size.currentText())})<br>"
            f"<b>Alignment:</b> {html.escape(self.alignment.currentText() or '—')}<br>"
            f"<b>Class:</b> {class_name}<br><b>Archetypes:</b> {archetypes}</p>"
            f"<h2>Base ability scores</h2><table cellspacing='6'>{rows}</table>"
            "<p><i>Racial modifiers remain separate and are applied by the live calculation system.</i></p>"
        )

    @property
    def draft(self) -> CharacterCreationDraft:
        dialog = self._class_dialog
        race = self._race_selection
        return CharacterCreationDraft(
            name=self.name.text().strip(),
            character_type=self.character_type.currentText(),
            player_name=self.player_name.text().strip(),
            race=self.race.text().strip(),
            alignment=self.alignment.currentText(),
            deity=self.deity.text().strip(),
            size=self.size.currentText(),
            race_key=str(race.get("race_key") or ""),
            race_ability_choice=str(race.get("ability_choice") or ""),
            race_variant_key=str(race.get("variant_key") or ""),
            race_alternate_trait_keys=tuple(race.get("alternate_trait_keys") or ()),
            race_trait_choices=tuple(race.get("trait_choices") or ()),
            abilities=self.ability_assignment.scores(),
            class_values=(dict(dialog.values) if dialog else None),
            archetype_keys=(dialog.archetype_keys if dialog else ()),
            optional_feature_keys=(dialog.selected_optional_feature_keys if dialog else ()),
            archetype_choice_values=(dialog.archetype_choice_values if dialog else {}),
        )
