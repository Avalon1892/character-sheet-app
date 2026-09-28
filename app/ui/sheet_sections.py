from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
    QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.content import entries
from app.feature_registry import FeatureKind
from app.models import (
    ABILITIES,
    ABILITY_KEYS,
    ALIGNMENTS,
    SEQUENCE_OPTION_TYPES,
    SIZES,
    SKILLS,
)
from app.ui.components import (
    FormulaNumberEdit, LayeredHealthBar, TableColumn, action_menu_button, configure_columns, configure_record_table, fit_table_rows,
    numeric_field, section_title, sheet_page,
)
from app.ui.feature_sections import (
    build_feature_details_section, build_saved_feature_section,
)
from app.ui.table_profiles import (
    EQUIPMENT_RECORD_COLUMNS,
    MAGIC_RECORD_COLUMNS,
    PREPARED_SPELL_COLUMNS,
    SPELL_SLOT_COLUMNS,
    TRADITIONAL_SPELL_COLUMNS,
    WORN_RECORD_COLUMNS,
)


COMBAT_LABELS = {
    "initiative": "Initiative",
    "fortitude": "Fortitude",
    "reflex": "Reflex",
    "will": "Will",
    "ac": "Armor Class",
    "touch_ac": "Touch AC",
    "flat_footed_ac": "Flat-Footed AC",
    "cmb": "CMB",
    "cmd": "CMD",
}


class SheetSectionsMixin:
    @staticmethod
    def _new_sheet_page(object_name: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        return sheet_page(object_name)

    def _overview_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        identity_title = self._section_title("CHARACTER")
        layout.addWidget(identity_title)
        name_row = QHBoxLayout()
        name_label = QLabel("NAME")
        name_label.setObjectName("mutedText")
        self.record_character_name = QLabel("—")
        self.record_character_name.setObjectName("recordName")
        name_row.addWidget(name_label)
        name_row.addWidget(self.record_character_name, 1)
        layout.addLayout(name_row)
        identity = QGridLayout()
        self.player_name = QLineEdit()
        self.race = QLineEdit()
        self.race_preset = QComboBox()
        self.race_preset.addItem("Custom", "")
        for preset in entries("races"):
            self.race_preset.addItem(preset["name"], preset["key"])
        self.race_preset.setEditable(True)
        self.race_preset.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.race_preset.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.configure_race = QPushButton("Choose / configure race…")
        self._race_variant_key = ""
        self._race_alternate_trait_keys: tuple[str, ...] = ()
        self._race_trait_choices = ()
        self.race_ability_choice = QComboBox()
        for key, name, _ in ABILITIES:
            self.race_ability_choice.addItem(name, key)
        self.alignment = QComboBox()
        self.alignment.addItems(ALIGNMENTS)
        self.deity = QLineEdit()
        self.size = QComboBox()
        self.size.addItems(SIZES)
        identity.addWidget(QLabel("Player"), 0, 0)
        identity.addWidget(self.player_name, 0, 1)
        identity.addWidget(QLabel("Race"), 0, 2)
        identity.addWidget(self.race, 0, 3)
        identity.addWidget(QLabel("Size"), 0, 4)
        identity.addWidget(self.size, 0, 5)
        identity.addWidget(QLabel("Deity"), 1, 0)
        identity.addWidget(self.deity, 1, 1)
        identity.addWidget(QLabel("Alignment"), 1, 2)
        identity.addWidget(self.alignment, 1, 3)
        identity.addWidget(QLabel("Race preset"), 1, 4)
        identity.addWidget(self.race_preset, 1, 5)
        identity.addWidget(QLabel("Flexible +2"), 2, 4)
        identity.addWidget(self.race_ability_choice, 2, 5)
        identity.addWidget(self.configure_race, 2, 2, 1, 2)
        identity.setColumnStretch(1, 1)
        identity.setColumnStretch(3, 1)
        identity.setColumnStretch(5, 1)
        layout.addLayout(identity)

        for field in (self.player_name, self.deity):
            field.editingFinished.connect(self._save_identity)
        self.race.editingFinished.connect(self._race_name_edited)
        self.alignment.currentTextChanged.connect(self._save_identity)
        self.size.currentTextChanged.connect(self._save_identity)
        self.race_preset.currentIndexChanged.connect(self._race_preset_changed)
        self.race_ability_choice.currentIndexChanged.connect(self._save_identity)
        self.configure_race.clicked.connect(self._configure_race)

        layout.addSpacing(5)
        class_header = QHBoxLayout()
        class_title = self._section_title("CLASS LEVELS")
        class_header.addWidget(class_title)
        class_header.addStretch()
        self.level_summary = QLabel("Total level 0  ·  BAB +0")
        self.level_summary.setObjectName("mutedText")
        class_header.addWidget(self.level_summary)
        layout.addLayout(class_header)

        self.class_table = QTableWidget(0, 9)
        self.class_table.setHorizontalHeaderLabels(
            ("Class", "Archetypes", "Level", "Hit Die", "HP", "BAB", "Fort", "Ref", "Will")
        )
        self.class_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.class_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.class_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.class_table.setAlternatingRowColors(True)
        self.class_table.setObjectName("classRecordTable")
        self.class_table.setShowGrid(False)
        self.class_table.verticalHeader().setVisible(False)
        self.class_table.verticalHeader().setDefaultSectionSize(28)
        self.class_table.setFixedHeight(96)
        self.class_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.class_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.class_table.doubleClicked.connect(self._edit_class)
        layout.addWidget(self.class_table, 1)

        class_actions = QHBoxLayout()
        add_class = QPushButton("+ Add class")
        add_class.setObjectName("primaryButton")
        add_class.clicked.connect(self._add_class)
        edit_class = QPushButton("Edit selected")
        edit_class.clicked.connect(self._edit_class)
        level_up = QPushButton("Level up selected")
        level_up.clicked.connect(self._level_up_class)
        review_advancement = QPushButton("Review advancement")
        review_advancement.clicked.connect(self._review_advancement)
        remove_class = QPushButton("Remove selected")
        remove_class.setObjectName("dangerButton")
        remove_class.clicked.connect(self._remove_class)
        class_actions.addWidget(add_class)
        class_actions.addWidget(edit_class)
        class_actions.addWidget(level_up)
        class_actions.addWidget(review_advancement)
        class_actions.addWidget(remove_class)
        class_actions.addStretch()
        layout.addLayout(class_actions)
        return tab

    def _favored_class_bonus_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("FAVORED CLASS BONUSES"))
        self.favored_class_table = QTableWidget(0, 6)
        self.favored_class_table.setHorizontalHeaderLabels(
            ("Class", "Levels", "+ HP", "+ Skill point", "Manual", "Manual code / note")
        )
        self._configure_table(self.favored_class_table, stretch_column=5)
        for column in (1, 2, 3, 4):
            self.favored_class_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.favored_class_table.setMinimumHeight(92)
        layout.addWidget(self.favored_class_table)
        self.favored_class_summary = QLabel("No class levels yet.")
        self.favored_class_summary.setObjectName("formulaText")
        layout.addWidget(self.favored_class_summary)
        return section

    def _advancement_budget_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("ADVANCEMENT BUDGETS"))
        self.advancement_table = QTableWidget(0, 8)
        self.advancement_table.setHorizontalHeaderLabels((
            "Resource", "Automatic", "Manual ±", "Override", "Total",
            "Used", "Remaining", "Rules basis / note",
        ))
        self._configure_table(self.advancement_table, stretch_column=7)
        for column in range(1, 7):
            self.advancement_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.advancement_table.setMinimumHeight(152)
        layout.addWidget(self.advancement_table)
        return section

    def _ability_score_increase_section(self) -> QWidget:
        """Compact Page 0 allocator for permanent level-based increases."""

        section = QWidget()
        section.setObjectName("sheetSection")
        section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("ABILITY SCORE INCREASES"))
        self.asi_summary = QLabel("No level-based increases available yet.")
        self.asi_summary.setObjectName("formulaText")
        layout.addWidget(self.asi_summary)
        grid = QGridLayout()
        grid.setHorizontalSpacing(7)
        for column, title in enumerate(("ABILITY", "BASE", "ALLOCATED", "CURRENT")):
            label = QLabel(title)
            label.setObjectName("mutedText")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, column)
        self.asi_controls = {}
        self.asi_base_labels = {}
        self.asi_current_labels = {}
        for row, (key, name, abbreviation) in enumerate(ABILITIES, 1):
            code = QLabel(abbreviation)
            code.setObjectName("abilityCode")
            code.setToolTip(name)
            code.setAlignment(Qt.AlignmentFlag.AlignCenter)
            base = QLabel("10")
            base.setObjectName("compactAbilityScore")
            base.setAlignment(Qt.AlignmentFlag.AlignCenter)
            allocation = numeric_field(0, 99, width=64)
            allocation.valueChanged.connect(
                partial(self._save_ability_score_increase, key)
            )
            current = QLabel("10")
            current.setObjectName("compactAbilityScore")
            current.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(code, row, 0)
            grid.addWidget(base, row, 1)
            grid.addWidget(allocation, row, 2)
            grid.addWidget(current, row, 3)
            self.asi_controls[key] = allocation
            self.asi_base_labels[key] = base
            self.asi_current_labels[key] = current
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)
        return section

    def _custom_trackers_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("CUSTOM VALUES & POOLS"))
        self.custom_tracker_table = QTableWidget(0, 6)
        self.custom_tracker_table.setHorizontalHeaderLabels(
            ("Name", "Template", "Current / Value", "Maximum", "Unit", "Formula / Reference")
        )
        configure_record_table(self.custom_tracker_table, 0)
        self.custom_tracker_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2, 3, 4):
            self.custom_tracker_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.custom_tracker_table.setMinimumHeight(150)
        self.custom_tracker_table.doubleClicked.connect(self._edit_custom_tracker)
        layout.addWidget(self.custom_tracker_table, 1)
        actions = QHBoxLayout()
        for label, tracker_type in (
            ("+ Calculated value", "calculated"),
            ("+ Counter", "counter"),
            ("+ Resource pool", "pool"),
        ):
            button = QPushButton(label)
            if tracker_type == "pool":
                button.setObjectName("primaryButton")
            button.clicked.connect(partial(self._add_custom_tracker, tracker_type))
            actions.addWidget(button)
        edit = QPushButton("Edit selected")
        edit.clicked.connect(self._edit_custom_tracker)
        remove = QPushButton("Remove")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self._remove_custom_tracker)
        actions.addWidget(edit)
        actions.addWidget(remove)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _abilities_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("BASE ABILITY SCORES"))
        headings = QHBoxLayout()
        headings.setContentsMargins(2, 0, 4, 0)
        for text, width in (("", 42), ("MOD", 38), ("SCORE", 42), ("BASE", 62)):
            label = QLabel(text)
            label.setObjectName("mutedText")
            label.setFixedWidth(width)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            headings.addWidget(label)
        adjustment_heading = QLabel("ENHANCE / MISC. / TEMP.")
        adjustment_heading.setObjectName("mutedText")
        adjustment_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headings.addWidget(adjustment_heading, 1)
        headings.addSpacing(30)
        layout.addLayout(headings)
        grid = QGridLayout()
        grid.setSpacing(5)
        for index, (key, name, abbreviation) in enumerate(ABILITIES):
            grid.addWidget(self._ability_card(key, name, abbreviation), index, 0)
        layout.addLayout(grid)
        layout.addStretch()
        return tab

    def _ability_card(self, key: str, name: str, abbreviation: str) -> QFrame:
        card = QFrame()
        card.setObjectName("abilityRow")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(0, 3, 4, 3)
        layout.setSpacing(4)
        code = QLabel(abbreviation)
        code.setObjectName("abilityCode")
        code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        code.setToolTip(name)
        code.setFixedWidth(42)
        layout.addWidget(code)

        modifier = QLabel("+0")
        modifier.setObjectName("abilityModifierBubble")
        modifier.setAlignment(Qt.AlignmentFlag.AlignCenter)
        modifier.setFixedSize(36, 36)
        layout.addWidget(modifier)

        total = QLabel("10")
        total.setObjectName("statTotal")
        total.setFixedWidth(42)
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(total)

        base = QSpinBox()
        base.setObjectName("baseAbilityInput")
        base.setRange(0, 999)
        base.setFixedWidth(62)
        base.valueChanged.connect(partial(self._base_score_changed, key))
        layout.addWidget(base)

        adjustments = QLabel("Base score only")
        adjustments.setObjectName("formulaText")
        adjustments.setMinimumWidth(72)
        adjustments.setWordWrap(True)
        layout.addWidget(adjustments, 1)
        breakdown = QPushButton("…")
        breakdown.setToolTip(f"Open {name} calculation breakdown")
        breakdown.setFixedWidth(28)
        breakdown.clicked.connect(partial(self._show_ability_breakdown, key, name))
        layout.addWidget(breakdown)
        self._ability_controls[key] = (base, total, modifier)
        self._ability_adjustment_labels[key] = adjustments
        return card

    def _ability_summary_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        section.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        layout = QVBoxLayout(section)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(3)
        layout.addWidget(self._section_title("ABILITIES"))

        header = QHBoxLayout()
        header.setContentsMargins(3, 0, 3, 0)
        for text, width in (("", 43), ("MOD", 38), ("SCORE", 44)):
            label = QLabel(text)
            label.setObjectName("mutedText")
            label.setFixedWidth(width)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(label)
        adjustment = QLabel("ADJUSTMENTS")
        adjustment.setObjectName("mutedText")
        adjustment.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(adjustment, 1)
        header.addSpacing(30)
        layout.addLayout(header)

        for key, name, abbreviation in ABILITIES:
            row = QFrame()
            row.setObjectName("compactAbilityRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(2, 2, 3, 2)
            row_layout.setSpacing(4)
            code = QLabel(abbreviation)
            code.setObjectName("abilityCode")
            code.setFixedWidth(43)
            code.setAlignment(Qt.AlignmentFlag.AlignCenter)
            code.setToolTip(name)
            modifier = QLabel("+0")
            modifier.setObjectName("compactAbilityModifier")
            modifier.setFixedSize(34, 34)
            modifier.setAlignment(Qt.AlignmentFlag.AlignCenter)
            score = QLabel("10")
            score.setObjectName("compactAbilityScore")
            score.setFixedWidth(44)
            score.setAlignment(Qt.AlignmentFlag.AlignCenter)
            summary = QLabel("Base score only")
            summary.setObjectName("formulaText")
            summary.setWordWrap(False)
            details = QPushButton("…")
            details.setFixedWidth(28)
            details.setToolTip(f"Open {name} calculation breakdown")
            details.clicked.connect(partial(self._show_ability_breakdown, key, name))
            row_layout.addWidget(code)
            row_layout.addWidget(modifier)
            row_layout.addWidget(score)
            row_layout.addWidget(summary, 1)
            row_layout.addWidget(details)
            layout.addWidget(row)
            self._ability_summary_labels[key] = (score, modifier, summary)
        return section


    def _compact_initiative_card(self, *, classic: bool) -> QFrame:
        """Large initiative total placed directly beside the health bar."""

        card = QFrame()
        card.setObjectName("initiativeCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(6)
        label = QLabel("INITIATIVE")
        label.setObjectName("formulaName")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total = QLabel("+0")
        total.setObjectName("initiativeTotal")
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total.setFixedSize(76, 52)
        button = QPushButton("…")
        button.setFixedWidth(30)
        button.setToolTip("Open Initiative calculation breakdown")
        button.clicked.connect(
            partial(self._show_combat_breakdown, "initiative", "Initiative")
        )
        layout.addWidget(label)
        layout.addWidget(total)
        layout.addWidget(button)
        if classic:
            self._classic_combat_labels["initiative"] = total
        else:
            self._combat_labels["initiative"] = total
        return card

    @staticmethod
    def _health_bar() -> LayeredHealthBar:
        """Shared current/maximum HP projection for built-in play blocks."""

        bar = LayeredHealthBar()
        bar.setObjectName("healthBar")
        bar.setRange(0, 1)
        bar.setValue(0)
        bar.setFormat("No HP")
        bar.setTextVisible(True)
        bar.setMinimumHeight(58)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar.setProperty("healthState", "empty")
        return bar

    def _hp_adjustment_row(self, *, classic: bool) -> QHBoxLayout:
        """Compact shared play controls for damage and ordinary healing."""

        row = QHBoxLayout()
        row.setSpacing(6)
        amount = numeric_field(0, 99999, replace_minimum_on_focus=True)
        amount.setObjectName("hpAdjustmentAmount")
        amount.setFixedSize(92, 36)
        amount.setToolTip(
            "Enter an amount, then apply damage or healing. Damage consumes "
            "temporary hit points before current hit points."
        )
        damage = QPushButton("Damage")
        damage.setObjectName("damageButton")
        damage.setFixedHeight(36)
        heal = QPushButton("Heal")
        heal.setObjectName("healButton")
        heal.setFixedHeight(36)
        damage.clicked.connect(
            lambda _checked=False, control=amount: self._apply_hp_adjustment(
                control, healing=False
            )
        )
        heal.clicked.connect(
            lambda _checked=False, control=amount: self._apply_hp_adjustment(
                control, healing=True
            )
        )
        row.addWidget(amount)
        row.addWidget(damage)
        row.addWidget(heal)
        row.addStretch()
        if classic:
            self.classic_hp_adjustment = amount
            self.classic_hp_damage_button = damage
            self.classic_hp_heal_button = heal
        else:
            self.hp_adjustment = amount
            self.hp_damage_button = damage
            self.hp_heal_button = heal
        return row

    def _movement_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)
        heading = QHBoxLayout()
        heading.addWidget(self._section_title("MOVEMENT"), 1)
        self.movement_edit_toggle = QPushButton("Edit bases & rules")
        self.movement_edit_toggle.setCheckable(True)
        self.movement_edit_toggle.setToolTip(
            "Show literal overrides, formulas, fly maneuverability, and notes."
        )
        heading.addWidget(self.movement_edit_toggle)
        layout.addLayout(heading)

        cards = QGridLayout()
        cards.setHorizontalSpacing(6)
        cards.setVerticalSpacing(6)
        self.movement_controls = {}
        self.movement_totals = {}
        self.movement_sources = {}
        modes = (
            ("land_speed", "Land", "Automatic"),
            ("armor_speed", "With armor", "Same as land"),
            ("fly_speed", "Fly", "—"),
            ("swim_speed", "Swim", "—"),
            ("climb_speed", "Climb", "—"),
            ("burrow_speed", "Burrow", "—"),
            ("teleport_speed", "Teleport", "—"),
        )
        for index, (key, label_text, zero_text) in enumerate(modes):
            card = QFrame()
            card.setObjectName("movementCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(7, 5, 7, 5)
            card_layout.setSpacing(1)
            label = QLabel(label_text.upper())
            label.setObjectName("movementMode")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            total = QLabel("—")
            total.setObjectName("movementTotal")
            total.setAlignment(Qt.AlignmentFlag.AlignCenter)
            source = QLabel(zero_text)
            source.setObjectName("movementSource")
            source.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(label)
            card_layout.addWidget(total)
            card_layout.addWidget(source)
            row, column = divmod(index, 4)
            cards.addWidget(card, row, column)
            cards.setColumnStretch(column, 1)
            self.movement_totals[key] = total
            self.movement_sources[key] = source
        layout.addLayout(cards)

        self.movement_edit_panel = QFrame()
        self.movement_edit_panel.setObjectName("movementEditorPanel")
        grid = QGridLayout(self.movement_edit_panel)
        grid.setContentsMargins(7, 7, 7, 7)
        grid.setHorizontalSpacing(7)
        grid.addWidget(QLabel("MODE"), 0, 0)
        grid.addWidget(QLabel("BASE / OVERRIDE / FORMULA"), 0, 1)
        for row, (key, label_text, zero_text) in enumerate(modes, 1):
            label = QLabel(label_text)
            label.setObjectName("formulaName")
            control = FormulaNumberEdit(
                0,
                9999,
                evaluator=self._evaluate_character_formula,
                suggestion_provider=self._character_formula_suggestions,
            )
            control.editor.setPlaceholderText(
                f"{zero_text}, number, or =formula"
            )
            control.preview.setMinimumWidth(54)
            control.editor.editingFinished.connect(self._save_movement)
            grid.addWidget(label, row, 0)
            grid.addWidget(control, row, 1)
            self.movement_controls[key] = control
        self.fly_maneuverability = QComboBox()
        self.fly_maneuverability.addItems(("", "Clumsy", "Poor", "Average", "Good", "Perfect"))
        self.fly_maneuverability.currentTextChanged.connect(self._save_movement)
        grid.addWidget(QLabel("Fly maneuverability"), 8, 0)
        grid.addWidget(self.fly_maneuverability, 8, 1)
        self.movement_notes = QLineEdit()
        self.movement_notes.setPlaceholderText("Movement notes")
        self.movement_notes.editingFinished.connect(self._save_movement)
        grid.addWidget(QLabel("Notes"), 9, 0)
        grid.addWidget(self.movement_notes, 9, 1)
        grid.setColumnStretch(1, 1)
        self.movement_edit_panel.setVisible(False)
        self.movement_edit_toggle.toggled.connect(self.movement_edit_panel.setVisible)
        layout.addWidget(self.movement_edit_panel)
        return section

    def _special_abilities_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(4)
        layout.addWidget(self._section_title("SPECIAL ABILITIES"))
        self.special_ability_table = QTableWidget(0, 2)
        self.special_ability_table.setHorizontalHeaderLabels(("Level", "Ability"))
        self._configure_table(self.special_ability_table, stretch_column=1)
        self.special_ability_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.special_ability_table.verticalHeader().setDefaultSectionSize(24)
        self.special_ability_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.special_ability_table)
        actions = QHBoxLayout()
        add_button = QPushButton("+ Add ability")
        edit_button = QPushButton("Edit selected")
        reset_button = QPushButton("Reset / remove")
        add_button.clicked.connect(self._add_special_ability)
        edit_button.clicked.connect(self._edit_special_ability)
        reset_button.clicked.connect(self._reset_special_ability)
        actions.addWidget(add_button); actions.addWidget(edit_button); actions.addWidget(reset_button)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _proficiencies_section(self) -> QWidget:
        section = QWidget(); section.setObjectName("sheetSection")
        layout = QVBoxLayout(section); layout.setContentsMargins(7,7,7,7); layout.setSpacing(4)
        layout.addWidget(self._section_title("PROFICIENCIES"))
        self.proficiencies_table = QTableWidget(0, 3)
        self.proficiencies_table.setHorizontalHeaderLabels(("Class", "Weapons", "Armor & Shields"))
        self._configure_table(self.proficiencies_table, stretch_column=1)
        self.proficiencies_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.proficiencies_table.setWordWrap(True)
        layout.addWidget(self.proficiencies_table)
        actions = QHBoxLayout()
        edit = QPushButton("Edit selected")
        edit.clicked.connect(self._edit_selected_proficiencies)
        reset = QPushButton("Reset to class rules")
        reset.clicked.connect(self._reset_selected_proficiencies)
        actions.addWidget(edit); actions.addWidget(reset); actions.addStretch()
        layout.addLayout(actions)
        return section

    def _inquisitor_features_section(self) -> QWidget:
        section = QWidget(); section.setObjectName("sheetSection")
        layout = QVBoxLayout(section); layout.setContentsMargins(7,7,7,7); layout.setSpacing(4)
        layout.addWidget(self._section_title("CLASS SYSTEMS & CHOICES"))

        self.inquisitor_resource_summary = QLabel("—")
        self.inquisitor_resource_summary.setObjectName("mutedText")
        self.inquisitor_resource_summary.setWordWrap(True)
        layout.addWidget(self.inquisitor_resource_summary)
        self.inquisitor_resource_table = QTableWidget(0, 5)
        self.inquisitor_resource_table.setHorizontalHeaderLabels(
            ("Feature", "Current", "Maximum", "State", "Selection / Current Effect")
        )
        self._configure_table(self.inquisitor_resource_table, stretch_column=4)
        for column in (1, 2, 3):
            self.inquisitor_resource_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.inquisitor_resource_table.doubleClicked.connect(
            self._configure_class_feature_resource
        )
        layout.addWidget(self.inquisitor_resource_table)
        resource_actions = QHBoxLayout()
        use = QPushButton("Use / spend 1")
        use.setObjectName("primaryButton")
        use.clicked.connect(self._use_class_feature_resource)
        toggle = QPushButton("Activate / end")
        toggle.clicked.connect(self._toggle_class_feature_resource)
        restore = QPushButton("Restore 1")
        restore.clicked.connect(self._restore_class_feature_resource)
        configure = QPushButton("Configure selected")
        configure.clicked.connect(self._configure_class_feature_resource)
        teamwork = QPushButton("Browse teamwork feats")
        teamwork.clicked.connect(self._browse_inquisitor_teamwork_feats)
        self.inquisitor_teamwork_button = teamwork
        resource_actions.addWidget(use)
        resource_actions.addWidget(toggle)
        resource_actions.addWidget(restore)
        resource_actions.addWidget(configure)
        resource_actions.addWidget(teamwork)
        resource_actions.addStretch()
        layout.addLayout(resource_actions)

        self.inquisitor_domain_title = QLabel("CLASS FEATURE CHOICES")
        self.inquisitor_domain_title.setObjectName("minorTitle")
        layout.addWidget(self.inquisitor_domain_title)
        self.inquisitor_domain_note = QLabel(section)
        self.inquisitor_domain_note.hide()
        self.inquisitor_choice_table = QTableWidget(0, 3)
        self.inquisitor_choice_table.setHorizontalHeaderLabels(("Class", "Feature", "Selection"))
        self._configure_table(self.inquisitor_choice_table, stretch_column=2)
        layout.addWidget(self.inquisitor_choice_table)
        self.inquisitor_domain_actions = QWidget()
        actions=QHBoxLayout(self.inquisitor_domain_actions); actions.setContentsMargins(0,0,0,0)
        choose=QPushButton("Choose / change"); choose.clicked.connect(self._choose_class_feature_choice)
        clear=QPushButton("Clear choice"); clear.clicked.connect(self._clear_class_feature_choice)
        actions.addWidget(choose); actions.addWidget(clear); actions.addStretch(); layout.addWidget(self.inquisitor_domain_actions)

        self.class_power_title = QLabel("CLASS POWERS")
        self.class_power_title.setObjectName("minorTitle")
        layout.addWidget(self.class_power_title)
        self.class_power_note = QLabel(section)
        self.class_power_note.hide()
        self.class_power_table = QTableWidget(0, 4)
        self.class_power_table.setHorizontalHeaderLabels(("Class", "Power system", "Selected", "Available"))
        self._configure_table(self.class_power_table, stretch_column=2)
        self.class_power_table.doubleClicked.connect(self._choose_class_powers)
        layout.addWidget(self.class_power_table)
        self.class_power_actions = QWidget()
        power_actions = QHBoxLayout(self.class_power_actions); power_actions.setContentsMargins(0,0,0,0)
        choose_powers = QPushButton("Choose / change powers"); choose_powers.setObjectName("primaryButton")
        choose_powers.clicked.connect(self._choose_class_powers)
        clear_powers = QPushButton("Clear powers"); clear_powers.clicked.connect(self._clear_class_powers)
        power_actions.addWidget(choose_powers); power_actions.addWidget(clear_powers); power_actions.addStretch()
        layout.addWidget(self.class_power_actions)
        return section

    def _animal_identity_section(self) -> QWidget:
        section = QWidget(); section.setObjectName("sheetSection")
        layout = QVBoxLayout(section); layout.setContentsMargins(7,7,7,7); layout.setSpacing(5)
        layout.addWidget(self._section_title("ANIMAL COMPANION"))
        grid = QGridLayout(); grid.setHorizontalSpacing(7); grid.setVerticalSpacing(5)
        self.companion_name = QLineEdit(); self.companion_name.setPlaceholderText("Companion name")
        self.companion_species = QComboBox(); self.companion_species.setEditable(True)
        self.companion_sex = QLineEdit(); self.companion_sex.setPlaceholderText("—")
        self.companion_type = QLineEdit(); self.companion_type.setPlaceholderText("Animal")
        self.companion_description = QLineEdit(); self.companion_description.setPlaceholderText("Short description")
        for column, (label, control, span) in enumerate((
            ("NAME", self.companion_name, 3), ("SPECIES", self.companion_species, 2),
            ("SEX", self.companion_sex, 1),
        )):
            start = sum(item[2] + 1 for item in (("NAME", self.companion_name, 3), ("SPECIES", self.companion_species, 2), ("SEX", self.companion_sex, 1))[:column])
            grid.addWidget(QLabel(label), 0, start); grid.addWidget(control, 0, start + 1, 1, span)
        grid.addWidget(QLabel("TYPE"), 1, 0); grid.addWidget(self.companion_type, 1, 1, 1, 2)
        grid.addWidget(QLabel("DESCRIPTION"), 1, 3); grid.addWidget(self.companion_description, 1, 4, 1, 4)

        self.companion_identity_values = {}
        identity = (("LEVEL", "level"), ("SIZE", "size"), ("SIZE MOD", "size_modifier"),
                    ("HIT DIE", "hit_die"), ("NATURAL ARMOR", "natural_armor"),
                    ("SPELL RESISTANCE", "spell_resistance"), ("DAMAGE REDUCTION", "damage_reduction"))
        for index, (label, key) in enumerate(identity):
            if key == "natural_armor":
                value = numeric_field(-99, 999, width=76)
                value.setToolTip(
                    "Edit the displayed total. The app stores only the adjustment "
                    "and keeps automatic companion progression underneath it."
                )
                value.editingFinished.connect(
                    lambda control=value: self._save_companion_stat_total(
                        "natural_armor", control.value()
                    )
                )
            elif key in {"spell_resistance", "damage_reduction"}:
                value = QLineEdit()
                value.setAlignment(Qt.AlignmentFlag.AlignCenter)
                value.setPlaceholderText("Automatic")
                value.setMaximumWidth(112)
                value.editingFinished.connect(
                    partial(self._save_companion_text_detail, key)
                )
            else:
                value = QLabel("—")
                value.setObjectName("statValue")
                value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.companion_identity_values[key] = value
            stat_row = 2 + index // 4
            stat_column = (index % 4) * 2
            grid.addWidget(QLabel(label), stat_row, stat_column)
            grid.addWidget(value, stat_row, stat_column + 1)

        self.companion_speed_labels = {}
        for index, (label, key) in enumerate((
            ("BASE SPEED", "land"), ("SWIM", "swim"), ("FLY", "fly"),
            ("CLIMB", "climb"), ("BURROW", "burrow"),
        )):
            value = numeric_field(0, 9999, width=92)
            value.setSuffix(" ft")
            value.setToolTip(
                "Edit the current total speed. Use Reset adjustments to return "
                "this movement mode to the species rules."
            )
            value.editingFinished.connect(
                lambda mode=key, control=value: self._save_companion_speed_total(
                    mode, control.value()
                )
            )
            self.companion_speed_labels[key] = value
            grid.addWidget(QLabel(label), 4, index * 2)
            grid.addWidget(value, 4, index * 2 + 1)

        self.companion_max_hp = numeric_field(1, 99999, width=96)
        self.companion_max_hp.setToolTip(
            "Edit the displayed maximum. The difference is stored as a manual "
            "adjustment while Hit Dice and Constitution remain automatic."
        )
        self.companion_max_hp.editingFinished.connect(
            lambda: self._save_companion_stat_total(
                "maximum_hp", self.companion_max_hp.value()
            )
        )
        self.companion_hp = QSpinBox(); self.companion_hp.setRange(-9999,99999)
        self.companion_temp_hp = QSpinBox(); self.companion_temp_hp.setRange(0,99999)
        grid.addWidget(QLabel("MAXIMUM HP"), 5, 0); grid.addWidget(self.companion_max_hp, 5, 1)
        grid.addWidget(QLabel("CURRENT HP"), 5, 2); grid.addWidget(self.companion_hp, 5, 3)
        grid.addWidget(QLabel("TEMPORARY HP"), 5, 4); grid.addWidget(self.companion_temp_hp, 5, 5)

        self.companion_level_adjustment = QSpinBox(); self.companion_level_adjustment.setRange(-20,20)
        self.companion_level_override = QLineEdit(); self.companion_level_override.setPlaceholderText("Automatic")
        grid.addWidget(QLabel("LEVEL ADJUSTMENT"), 6, 0); grid.addWidget(self.companion_level_adjustment, 6, 1)
        grid.addWidget(QLabel("LEVEL OVERRIDE"), 6, 2); grid.addWidget(self.companion_level_override, 6, 3)
        layout.addLayout(grid)
        reset_adjustments = QPushButton("Reset statistic adjustments")
        reset_adjustments.clicked.connect(self._reset_companion_stat_adjustments)
        edit_row = QHBoxLayout()
        edit_row.addStretch()
        edit_row.addWidget(reset_adjustments)
        layout.addLayout(edit_row)
        self.companion_source = QLabel(); self.companion_source.setObjectName("mutedText"); self.companion_source.setWordWrap(True)
        layout.addWidget(self.companion_source)
        for control in (self.companion_name, self.companion_sex, self.companion_type,
                        self.companion_description, self.companion_level_override):
            control.editingFinished.connect(self._save_animal_companion)
        self.companion_species.currentIndexChanged.connect(self._save_animal_companion)
        if self.companion_species.lineEdit() is not None:
            self.companion_species.lineEdit().editingFinished.connect(
                self._save_animal_companion
            )
        self.companion_level_adjustment.valueChanged.connect(self._save_animal_companion)
        self.companion_hp.valueChanged.connect(self._save_animal_companion)
        self.companion_temp_hp.valueChanged.connect(self._save_animal_companion)
        return section

    def _animal_statistics_section(self) -> QWidget:
        section = QWidget(); section.setObjectName("sheetSection")
        layout = QVBoxLayout(section); layout.setContentsMargins(7,7,7,7); layout.setSpacing(5)
        layout.addWidget(self._section_title("ABILITIES, DEFENSES & COMBAT"))
        upper = QHBoxLayout(); upper.setSpacing(8)
        ability_panel = QVBoxLayout(); ability_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        ability_panel.addWidget(self._sheet_subtitle("ABILITY SCORES"))
        self.companion_ability_table = QTableWidget(6,5)
        self.companion_ability_table.setHorizontalHeaderLabels((
            "Ability", "Auto", "ASI", "Override", "Current / Mod"
        ))
        self._configure_table(self.companion_ability_table, stretch_column=0)
        self.companion_ability_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.companion_ability_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.companion_asi_fields = {}
        self.companion_ability_override_fields = {}
        for row, (key, label) in enumerate((
            ("str", "STR"), ("dex", "DEX"), ("con", "CON"),
            ("int", "INT"), ("wis", "WIS"), ("cha", "CHA"),
        )):
            name = QTableWidgetItem(label)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.companion_ability_table.setItem(row, 0, name)
            asi = numeric_field(0, 4, width=58)
            asi.setToolTip("Assign level-earned companion ability increases here.")
            asi.editingFinished.connect(
                lambda ability=key, control=asi: self._save_companion_ability_increase(
                    ability, control.value()
                )
            )
            final_override = numeric_field(-1, 999, width=86)
            final_override.setSpecialValueText("Auto")
            final_override.setToolTip(
                "Optional final-score override. Auto uses species, progression, and ASIs."
            )
            final_override.editingFinished.connect(
                lambda ability=key, control=final_override: self._save_companion_ability_override(
                    ability, control.value()
                )
            )
            self.companion_asi_fields[key] = asi
            self.companion_ability_override_fields[key] = final_override
            self.companion_ability_table.setCellWidget(row, 2, asi)
            self.companion_ability_table.setCellWidget(row, 3, final_override)
        ability_panel.addWidget(self.companion_ability_table)
        self.companion_asi_status = QLabel("No level ability increases available")
        self.companion_asi_status.setObjectName("mutedText")
        ability_panel.addWidget(self.companion_asi_status)
        ability_actions = QHBoxLayout()
        reset = QPushButton("Clear final overrides"); reset.clicked.connect(self._reset_companion_abilities)
        reset_asis = QPushButton("Reset ASIs"); reset_asis.clicked.connect(self._reset_companion_ability_increases)
        ability_actions.addWidget(reset)
        ability_actions.addWidget(reset_asis)
        ability_actions.addStretch()
        ability_panel.addLayout(ability_actions)
        upper.addLayout(ability_panel, 2)

        defense_panel = QVBoxLayout(); defense_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        defense_panel.addWidget(self._sheet_subtitle("SAVING THROWS & ARMOR CLASS"))
        self.companion_defense_table = QTableWidget(3,4)
        self.companion_defense_table.setHorizontalHeaderLabels(("Save","Total","Armor Class","Total"))
        self._configure_table(self.companion_defense_table, stretch_column=2)
        self.companion_defense_total_fields = {}
        for row, (save_label, save_key, ac_label, ac_key) in enumerate((
            ("FORT", "fortitude", "AC", "armor_class"),
            ("REF", "reflex", "FLAT-FOOTED", "flat_footed_ac"),
            ("WILL", "will", "TOUCH", "touch_ac"),
        )):
            self.companion_defense_table.setItem(row, 0, QTableWidgetItem(save_label))
            self.companion_defense_table.setItem(row, 2, QTableWidgetItem(ac_label))
            for column, key in ((1, save_key), (3, ac_key)):
                field = numeric_field(-999, 999, width=76)
                field.setToolTip(
                    "Edit the displayed total; the difference is kept as a manual adjustment."
                )
                field.editingFinished.connect(
                    lambda statistic=key, control=field: self._save_companion_stat_total(
                        statistic, control.value()
                    )
                )
                self.companion_defense_total_fields[key] = field
                self.companion_defense_table.setCellWidget(row, column, field)
        defense_panel.addWidget(self.companion_defense_table)
        upper.addLayout(defense_panel, 3)
        layout.addLayout(upper)

        layout.addWidget(self._sheet_subtitle("COMBAT NUMBERS"))
        self.companion_combat_table = QTableWidget(3,3)
        self.companion_combat_table.setHorizontalHeaderLabels(("Statistic","Total","Calculation"))
        self._configure_table(self.companion_combat_table, stretch_column=2)
        self.companion_combat_total_fields = {}
        for row, (label, key, calculation) in enumerate((
            ("Base Attack Bonus", "base_attack_bonus", "Companion progression + adjustment"),
            ("Combat Maneuver Bonus", "cmb", "BAB + STR + size + adjustment"),
            ("Combat Maneuver Defense", "cmd", "10 + BAB + STR + DEX + size + adjustment"),
        )):
            self.companion_combat_table.setItem(row, 0, QTableWidgetItem(label))
            self.companion_combat_table.setItem(row, 2, QTableWidgetItem(calculation))
            field = numeric_field(-999, 999, width=82)
            field.setToolTip(
                "Edit the displayed total; the difference is kept as a manual adjustment."
            )
            field.editingFinished.connect(
                lambda statistic=key, control=field: self._save_companion_stat_total(
                    statistic, control.value()
                )
            )
            self.companion_combat_total_fields[key] = field
            self.companion_combat_table.setCellWidget(row, 1, field)
        layout.addWidget(self.companion_combat_table)
        layout.addWidget(self._sheet_subtitle("NATURAL ATTACKS"))
        self.companion_attack_table = QTableWidget(0,4)
        self.companion_attack_table.setHorizontalHeaderLabels(("Attack","Attack Bonus","Damage / Effect","Notes"))
        self._configure_table(self.companion_attack_table, stretch_column=2)
        self.companion_attack_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.companion_attack_table)
        self.companion_species_rules = QLabel(); self.companion_species_rules.setWordWrap(True)
        self.companion_species_rules.setObjectName("mutedText"); layout.addWidget(self.companion_species_rules)
        return section

    def _animal_training_section(self) -> QWidget:
        section = QWidget(); section.setObjectName("sheetSection")
        layout = QVBoxLayout(section); layout.setContentsMargins(7,7,7,7); layout.setSpacing(5)
        layout.addWidget(self._section_title("SKILLS, TRICKS & FEATURES"))
        upper = QHBoxLayout(); upper.setSpacing(8)
        skills_panel = QVBoxLayout(); skills_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        skills_panel.addWidget(self._sheet_subtitle("SKILLS"))
        self.companion_skill_table = QTableWidget(0,4)
        configure_columns(self.companion_skill_table, (
            TableColumn("Total", 52),
            TableColumn("Skill", stretch=True),
            TableColumn("Ability", 62),
            TableColumn("Ranks", 52),
        ))
        self.companion_skill_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        skills_panel.addWidget(self.companion_skill_table)
        self.companion_skill_rank_fields = {}
        self.companion_skill_status = QLabel("0 / 0 skill ranks assigned")
        self.companion_skill_status.setObjectName("mutedText")
        skills_panel.addWidget(self.companion_skill_status)
        skill_actions = QHBoxLayout(); add_skill=QPushButton("Set ranks"); remove_skill=QPushButton("Clear ranks")
        add_skill.clicked.connect(self._add_companion_skill); remove_skill.clicked.connect(self._remove_companion_skill)
        skill_actions.addWidget(add_skill); skill_actions.addWidget(remove_skill); skill_actions.addStretch(); skills_panel.addLayout(skill_actions)
        upper.addLayout(skills_panel, 3)
        self.companion_training_tabs = {}
        tricks_panel = QVBoxLayout(); tricks_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        tricks_panel.addWidget(self._sheet_subtitle("TRICKS"))
        tricks = QTableWidget(0,1); tricks.setHorizontalHeaderLabels(("Known trick",))
        self._configure_table(tricks, stretch_column=0); tricks_panel.addWidget(tricks)
        trick_actions=QHBoxLayout(); add_trick=QPushButton("+ Add trick"); remove_trick=QPushButton("Remove")
        add_trick.clicked.connect(partial(self._add_companion_training,"Tricks")); remove_trick.clicked.connect(partial(self._remove_companion_training,"Tricks"))
        trick_actions.addWidget(add_trick); trick_actions.addWidget(remove_trick); trick_actions.addStretch(); tricks_panel.addLayout(trick_actions)
        self.companion_training_tabs["Tricks"] = tricks
        upper.addLayout(tricks_panel, 2)
        layout.addLayout(upper)

        lower = QHBoxLayout(); lower.setSpacing(8)
        for kind in ("Feats", "Special abilities"):
            singular = {"Feats": "Feat", "Special abilities": "Special ability"}[kind]
            panel = QVBoxLayout(); panel.setAlignment(Qt.AlignmentFlag.AlignTop)
            panel.addWidget(self._sheet_subtitle(kind.upper()))
            table = QTableWidget(0,1); table.setHorizontalHeaderLabels((singular,))
            self._configure_table(table, stretch_column=0); panel.addWidget(table)
            actions = QHBoxLayout(); add=QPushButton(f"+ Add {singular.lower()}"); remove=QPushButton("Remove")
            add.clicked.connect(partial(self._add_companion_training,kind)); remove.clicked.connect(partial(self._remove_companion_training,kind))
            actions.addWidget(add); actions.addWidget(remove); actions.addStretch(); panel.addLayout(actions)
            self.companion_training_tabs[kind] = table; lower.addLayout(panel, 1)
        layout.addLayout(lower)
        self.companion_notes = QPlainTextEdit(); self.companion_notes.setPlaceholderText("Companion notes")
        self.companion_notes.setMaximumHeight(90); self.companion_notes.textChanged.connect(self._save_animal_companion)
        layout.addWidget(self.companion_notes)
        return section

    def _combat_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(5)
        layout.addWidget(self._section_title("COMBAT & DEFENSE"))

        resource_title = QLabel("HIT POINTS & INITIATIVE")
        resource_title.setObjectName("sheetSubTitle")
        layout.addWidget(resource_title)
        hp_layout = QGridLayout()
        hp_layout.setHorizontalSpacing(7)
        hp_layout.setVerticalSpacing(4)
        self.hp_bar = self._health_bar()
        health_bar_row = QHBoxLayout()
        health_bar_row.setSpacing(7)
        health_bar_row.addWidget(self.hp_bar, 1)
        health_bar_row.addWidget(self._compact_initiative_card(classic=False))
        hp_layout.addLayout(health_bar_row, 0, 0, 1, 4)
        hp_layout.addLayout(self._hp_adjustment_row(classic=False), 1, 0, 1, 4)
        self.hp_maximum = FormulaNumberEdit(
            0,
            99999,
            evaluator=self._evaluate_hp_max_formula,
            suggestion_provider=self._character_formula_suggestions,
        )
        self.hp_maximum.editor.setPlaceholderText("Maximum or =formula")
        self.hp_current = self._hp_spin(-9999, 99999)
        self.hp_temporary = self._hp_spin(0, 99999)
        self.hp_nonlethal = self._hp_spin(0, 99999)
        for index, (label, control) in enumerate((
            ("Maximum", self.hp_maximum),
            ("Current", self.hp_current),
            ("Temporary", self.hp_temporary),
            ("Nonlethal", self.hp_nonlethal),
        )):
            cell = QVBoxLayout()
            caption = QLabel(label.upper())
            caption.setObjectName("mutedText")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._configure_hp_field(control, primary=True)
            cell.addWidget(caption)
            cell.addWidget(control)
            hp_layout.addLayout(cell, 2, index)
        self.hp_status = QLabel("No HP entered")
        self.hp_status.setObjectName("statCode")
        self.hp_auto = QCheckBox("Automatic maximum")
        self.hp_auto.setToolTip(
            "Uses stored class Hit Die HP plus Constitution for every character level"
        )
        hp_layout.addWidget(self.hp_auto, 3, 0, 1, 2)
        hp_layout.addWidget(
            self.hp_status, 3, 2, 1, 2,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        for column in range(4):
            hp_layout.setColumnStretch(column, 1)
        layout.addLayout(hp_layout)
        self.hp_maximum.editor.editingFinished.connect(self._save_hit_points)
        for control in (self.hp_current, self.hp_temporary, self.hp_nonlethal):
            control.valueChanged.connect(self._save_hit_points)
        self.hp_auto.toggled.connect(self._save_hit_points)

        layout.addWidget(self._sheet_subtitle("ARMOR CLASS"))
        for target in ("ac", "flat_footed_ac", "touch_ac"):
            layout.addWidget(self._combat_card(target, COMBAT_LABELS[target].upper()))

        layout.addWidget(self._sheet_subtitle("SAVES"))
        for target in ("fortitude", "reflex", "will"):
            layout.addWidget(self._combat_card(target, COMBAT_LABELS[target].upper()))

        layout.addWidget(self._sheet_subtitle("COMBAT MANEUVERS"))
        for target in ("cmb", "cmd"):
            layout.addWidget(self._combat_card(target, COMBAT_LABELS[target]))
        self._combat_magic_skill_labels = {}
        self._combat_magic_skill_rows = {}
        for target, title, formula in (
            ("msb", "MSB", "caster level + misc"),
            ("msd", "MSD", "11 + MSB"),
        ):
            row, value = self._magic_skill_row(title, formula)
            row.setVisible(False)
            self._combat_magic_skill_rows[target] = row
            self._combat_magic_skill_labels[target] = value
            layout.addWidget(row)
        layout.addStretch()
        return tab

    @staticmethod
    def _hp_spin(minimum: int, maximum: int) -> QSpinBox:
        control = numeric_field(minimum, maximum)
        control.setMinimumWidth(72)
        return control

    @staticmethod
    def _configure_hp_field(control: QWidget, *, primary: bool) -> None:
        """Let HP editors consume their card instead of staying tiny."""

        control.setMinimumWidth(132 if primary else 118)
        control.setFixedHeight(58 if primary else 40)
        control.setMaximumWidth(16777215)
        control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        targets = [control]
        if isinstance(control, FormulaNumberEdit):
            targets.extend((control.editor, control.preview))
        for target in targets:
            target.setProperty("primaryHpField", primary)
            font = target.font()
            font.setBold(primary)
            if primary:
                font.setFamily("Georgia")
                font.setPointSizeF(18.0)
            target.setFont(font)

    @staticmethod
    def _magic_skill_row(
        title: str, formula_text: str, *, compact: bool = False
    ) -> tuple[QFrame, QLabel]:
        """Read-only MSB/MSD row shared by both built-in combat blocks."""

        card = QFrame()
        card.setObjectName("formulaRow")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("formulaName")
        label.setMinimumWidth(98 if compact else 104)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        total = QLabel("—")
        total.setObjectName("formulaTotal")
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total.setFixedSize(78 if compact else 76, 52)
        formula = QLabel(formula_text)
        formula.setObjectName("formulaText")
        layout.addWidget(label, 1)
        layout.addWidget(total)
        if not compact:
            layout.addWidget(formula, 1)
        else:
            formula.setVisible(False)
        return card, total

    def _combat_card(self, target: str, title: str) -> QFrame:
        card = QFrame()
        card.setObjectName("formulaRow")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("formulaName")
        label.setFixedWidth(112)
        total = QLabel("+0")
        total.setObjectName("formulaTotal")
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total.setFixedSize(76, 52)
        formulae = {
            "initiative": "DEX + misc", "fortitude": "Base + CON + misc",
            "reflex": "Base + DEX + misc", "will": "Base + WIS + misc",
            "ac": "10 + DEX + armor + shield + misc",
            "touch_ac": "10 + DEX + deflection + misc",
            "flat_footed_ac": "10 + armor + shield + misc",
            "cmb": "BAB + STR + size + misc",
            "cmd": "10 + BAB + STR + DEX + size + misc",
        }
        formula = QLabel(formulae[target])
        formula.setObjectName("formulaText")
        button = QPushButton("…")
        button.setToolTip(f"Open {title.title()} calculation breakdown")
        button.setFixedWidth(28)
        button.clicked.connect(partial(self._show_combat_breakdown, target, title))
        layout.addWidget(label)
        layout.addWidget(total)
        layout.addWidget(formula, 1)
        layout.addWidget(button)
        self._combat_labels[target] = total
        return card

    @staticmethod
    def _sheet_subtitle(text: str) -> QLabel:
        title = QLabel(text)
        title.setObjectName("sheetSubTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Subtitles are decorative bars, never content panels.  Keeping their
        # vertical policy fixed prevents a short neighbouring table from
        # stretching a title into a large block of accent colour.
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return title

    def _skills_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        header = QHBoxLayout()
        header.addWidget(self._section_title("SKILLS"), 1)
        self.skill_budget_label = QLabel("Skill ranks —")
        self.skill_budget_label.setObjectName("mutedText")
        self.skill_budget_label.setFixedHeight(27)
        self.skill_budget_label.setMaximumWidth(190)
        self.skill_budget_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.skill_budget_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.skill_budget_label.setToolTip(
            "Automatic skill-rank allowance, assigned ranks, and ranks still available."
        )
        header.addWidget(self.skill_budget_label)
        layout.addLayout(header)

        self.skill_table = QTableWidget(0, 8)
        self.skill_table.setObjectName("skillRecordTable")
        self.skill_table.setHorizontalHeaderLabels(
            ("Skill", "Class", "Bonus", "Ability", "Rk.", "Misc", "ACP", "Notes")
        )
        self._configure_table(self.skill_table, stretch_column=0)
        self.skill_table.verticalHeader().setDefaultSectionSize(23)
        self.skill_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.skill_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 5, 6):
            self.skill_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.skill_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.skill_table.setColumnWidth(4, 36)
        self.skill_table.doubleClicked.connect(self._edit_skill)
        self.skill_table.setToolTip(
            "Double-click a skill to change ranks, class status, governing ability, or notes."
        )
        # In a resized/freeform section the table, not an anonymous spacer,
        # owns the remaining height. This keeps the skill rows usable instead
        # of leaving a large blank footer below a compressed table.
        layout.addWidget(self.skill_table, 1)
        actions = QHBoxLayout()
        edit_button = QPushButton("Edit selected")
        edit_button.setObjectName("primaryButton")
        edit_button.clicked.connect(self._edit_skill)
        actions.addWidget(edit_button)
        actions.addStretch()
        layout.addLayout(actions)
        return tab

    def _feats_tab(self) -> QWidget:
        return build_saved_feature_section(self, FeatureKind.FEAT)

    def _traits_tab(self) -> QWidget:
        return build_saved_feature_section(self, FeatureKind.TRAIT)

    def _feature_details_section(self) -> QWidget:
        return build_feature_details_section(self)

    @staticmethod
    def _fit_feature_table(
        table: QTableWidget, row_count: int, minimum_rows: int, maximum_rows: int
    ) -> None:
        fit_table_rows(table, row_count, minimum_rows, maximum_rows)
        section = table.parentWidget()
        if section is not None and not bool(section.property("freeformManaged")):
            section.setFixedHeight(table.height() + 96)

    def _martial_focus_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("MARTIAL FOCUS"))

        play = QHBoxLayout()
        play.setSpacing(7)
        self.martial_focus_status = QLabel("FOCUSED")
        self.martial_focus_status.setObjectName("focusReady")
        self.martial_focus_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        play.addWidget(self.martial_focus_status, 2)

        focus_readout = QVBoxLayout()
        focus_readout.setSpacing(0)
        self.martial_focus_counter = QLabel("1 / 1")
        self.martial_focus_counter.setObjectName("focusCounter")
        self.martial_focus_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.martial_focus_pips = QLabel("●")
        self.martial_focus_pips.setObjectName("focusPips")
        self.martial_focus_pips.setAlignment(Qt.AlignmentFlag.AlignCenter)
        focus_readout.addWidget(self.martial_focus_counter)
        focus_readout.addWidget(self.martial_focus_pips)
        play.addLayout(focus_readout, 1)

        self.martial_focus_current = QSpinBox()
        self.martial_focus_current.setRange(0, 1)
        self.martial_focus_current.setVisible(False)
        self.martial_focus_maximum = FormulaNumberEdit(
            1,
            99,
            evaluator=self._evaluate_character_formula,
            suggestion_provider=self._character_formula_suggestions,
        )
        self.martial_focus_maximum.editor.setPlaceholderText("Maximum or =formula")
        self.martial_focus_maximum.preview.setMinimumWidth(50)
        spend_button = QPushButton("Spend")
        spend_button.clicked.connect(self._spend_martial_focus)
        regain_button = QPushButton("Regain")
        regain_button.setObjectName("primaryButton")
        regain_button.clicked.connect(self._regain_martial_focus)
        play.addWidget(spend_button)
        play.addWidget(regain_button)
        layout.addLayout(play)

        self.martial_focus_recovery = QLineEdit()
        self.martial_focus_recovery.setPlaceholderText("How this character regains focus")
        self.martial_focus_notes = QLineEdit()
        self.martial_focus_notes.setPlaceholderText("Focus-related notes")
        self.martial_focus_setup = QFrame()
        self.martial_focus_setup.setObjectName("movementEditorPanel")
        setup = QGridLayout(self.martial_focus_setup)
        setup.setContentsMargins(7, 7, 7, 7)
        setup.addWidget(QLabel("Maximum focus"), 0, 0)
        setup.addWidget(self.martial_focus_maximum, 0, 1)
        setup.addWidget(QLabel("Regained through"), 1, 0)
        setup.addWidget(self.martial_focus_recovery, 1, 1)
        setup.addWidget(QLabel("Notes"), 2, 0)
        setup.addWidget(self.martial_focus_notes, 2, 1)
        setup.setColumnStretch(1, 1)
        self.martial_focus_setup.setVisible(False)
        self.martial_focus_setup_toggle = QPushButton("Focus setup")
        self.martial_focus_setup_toggle.setCheckable(True)
        self.martial_focus_setup_toggle.toggled.connect(
            self.martial_focus_setup.setVisible
        )
        layout.addWidget(self.martial_focus_setup_toggle)
        layout.addWidget(self.martial_focus_setup)

        self.martial_focus_current.valueChanged.connect(self._save_martial_focus)
        self.martial_focus_maximum.editor.editingFinished.connect(
            self._martial_focus_maximum_changed
        )
        self.martial_focus_recovery.editingFinished.connect(self._save_martial_focus)
        self.martial_focus_notes.editingFinished.connect(self._save_martial_focus)
        return section

    def _martial_talents_section(self) -> QWidget:
        return build_saved_feature_section(self, FeatureKind.MARTIAL_TALENT)

    def _moldable_talents_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(4)
        self.moldable_talent_title = self._section_title("MOLDABLE TALENTS")
        layout.addWidget(self.moldable_talent_title)
        self.moldable_talent_summary = QLabel("No Moldable Talent slots available.")
        self.moldable_talent_summary.setObjectName("mutedText")
        layout.addWidget(self.moldable_talent_summary)
        self.moldable_talent_table = QTableWidget(0, 3)
        self.moldable_talent_table.setHorizontalHeaderLabels(("Talent", "Sphere", "Type"))
        self._configure_table(self.moldable_talent_table, stretch_column=0)
        self.moldable_talent_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.moldable_talent_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.moldable_talent_table)
        actions = QHBoxLayout()
        self.moldable_talent_change_button = QPushButton("Choose / change talents")
        self.moldable_talent_change_button.setObjectName("primaryButton")
        self.moldable_talent_change_button.clicked.connect(self._change_moldable_talents)
        actions.addWidget(self.moldable_talent_change_button)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _prodigy_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("PRODIGY SEQUENCE"))

        self.prodigy_class_summary = QLabel("PRODIGY CLASS NOT ADDED")
        self.prodigy_class_summary.setObjectName("prodigyClassSummary")
        self.prodigy_class_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prodigy_feature_summary = QLabel()
        self.prodigy_feature_summary.setObjectName("formulaText")
        self.prodigy_feature_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prodigy_feature_summary.setWordWrap(True)
        layout.addWidget(self.prodigy_class_summary)
        layout.addWidget(self.prodigy_feature_summary)

        tracker = QFrame()
        tracker.setObjectName("sequenceTracker")
        tracker_layout = QHBoxLayout(tracker)
        tracker_layout.setContentsMargins(10, 7, 10, 7)
        self.sequence_status = QLabel("NO ACTIVE SEQUENCE")
        self.sequence_status.setObjectName("sequenceInactive")
        self.sequence_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_current = QLabel("0 / 4")
        self.sequence_current.setObjectName("sequenceCounter")
        self.sequence_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_effect = QLabel("INSPIRED SEQUENCE INACTIVE")
        self.sequence_effect.setObjectName("sequenceEffect")
        self.sequence_effect.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_maximum = QSpinBox()
        self.sequence_maximum.setRange(1, 99)
        self.sequence_maximum.setValue(4)
        self.sequence_maximum.setToolTip("Maximum sequence length; normally 4 + 1 per 3 Prodigy levels")
        add_button = QPushButton("+ Link")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_prodigy_link)
        lose_button = QPushButton("− Link")
        lose_button.clicked.connect(self._lose_prodigy_link)
        end_button = QPushButton("End sequence")
        end_button.setObjectName("dangerButton")
        end_button.clicked.connect(self._end_prodigy_sequence)
        tracker_layout.addWidget(self.sequence_status)
        tracker_layout.addWidget(self.sequence_current)
        tracker_layout.addWidget(self.sequence_effect)
        tracker_layout.addWidget(QLabel("Maximum"))
        tracker_layout.addWidget(self.sequence_maximum)
        tracker_layout.addStretch()
        tracker_layout.addWidget(add_button)
        tracker_layout.addWidget(lose_button)
        tracker_layout.addWidget(end_button)
        layout.addWidget(tracker)

        option_columns = QHBoxLayout()
        option_columns.setSpacing(8)
        option_columns.setAlignment(Qt.AlignmentFlag.AlignTop)
        for option_type in SEQUENCE_OPTION_TYPES:
            option_columns.addWidget(self._sequence_option_panel(option_type), 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(option_columns)
        self.sequence_maximum.valueChanged.connect(self._sequence_maximum_changed)
        return section

    def _prodigy_imbue_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("IMBUE SEQUENCE"))
        self.prodigy_imbue_combo = QComboBox()
        self.prodigy_imbue_combo.setObjectName("imbueSelector")
        self.prodigy_imbue_combo.setToolTip(
            "Choose an imbuement granted by one of this Prodigy's magic spheres."
        )
        self.prodigy_imbue_combo.currentIndexChanged.connect(self._imbue_changed)
        layout.addWidget(self.prodigy_imbue_combo)
        card = QFrame()
        card.setObjectName("imbueCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        self.prodigy_imbue_name = QLabel("NO IMBUE SELECTED")
        self.prodigy_imbue_name.setObjectName("minorTitle")
        self.prodigy_imbue_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prodigy_imbue_value = QLabel("—")
        self.prodigy_imbue_value.setObjectName("resourceTotal")
        self.prodigy_imbue_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prodigy_imbue_description = QLabel(
            "Gain a magic sphere on Page 0 to unlock its Prodigy imbuement."
        )
        self.prodigy_imbue_description.setObjectName("mutedText")
        self.prodigy_imbue_description.setWordWrap(True)
        self.prodigy_imbue_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.prodigy_imbue_name)
        card_layout.addWidget(self.prodigy_imbue_value)
        card_layout.addWidget(self.prodigy_imbue_description)
        layout.addWidget(card)
        layout.addStretch()
        return section

    def _sequence_option_panel(self, option_type: str) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sequenceOptionPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel(f"{option_type.upper()}S")
        title.setObjectName("minorTitle")
        layout.addWidget(title)
        table = QTableWidget(0, 2)
        table.setObjectName("sequenceTable")
        table.setHorizontalHeaderLabels(("Name", "Action"))
        self._configure_table(table, stretch_column=0)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.setMinimumHeight(260)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.doubleClicked.connect(partial(self._edit_sequence_option, option_type))
        self.sequence_tables[option_type] = table
        layout.addWidget(table, 1)
        actions = QHBoxLayout()
        use_button = QPushButton(f"Use {option_type.lower()}")
        use_button.setObjectName("primaryButton")
        use_button.clicked.connect(partial(self._use_sequence_option, option_type))
        actions.addWidget(use_button)
        actions.addWidget(action_menu_button((
            ("Add custom", partial(self._add_sequence_option, option_type)),
            ("Edit selected", partial(self._edit_sequence_option, option_type)),
            ("", None),
            ("Remove selected", partial(self._remove_sequence_option, option_type)),
        )))
        actions.addStretch()
        layout.addLayout(actions)
        return panel

    def _casting_play_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)
        self.casting_play_title = self._section_title("MAGIC SUMMARY")
        layout.addWidget(self.casting_play_title)
        self.casting_play_note = QLabel(section)
        self.casting_play_note.hide()
        cards = QGridLayout()
        cards.setSpacing(7)
        self._play_casting_labels: dict[str, QLabel] = {}
        self._play_casting_captions: dict[str, QLabel] = {}
        for index, (key, title) in enumerate((
            ("caster_level", "CASTER LEVEL"),
            ("save_dc", "SPHERE DC"),
            ("msb", "MSB"),
            ("msd", "MSD"),
            ("cam", "CAM"),
            ("concentration", "CONCENTRATION"),
            ("spell_points", "SPELL POINTS"),
        )):
            card = QFrame()
            card.setObjectName("miniStatCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(7, 4, 7, 4)
            caption = QLabel(title)
            caption.setObjectName("mutedText")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—")
            value.setObjectName("miniStatTotal")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(caption)
            card_layout.addWidget(value)
            cards.addWidget(card, index // 2, index % 2)
            self._play_casting_labels[key] = value
            self._play_casting_captions[key] = caption
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        layout.addLayout(cards)
        self.open_spell_book_button = QPushButton("Open Spell Book")
        self.open_spell_book_button.setObjectName("primaryButton")
        self.open_spell_book_button.setToolTip(
            "Open the wide play view for this character's traditional spells and Magic Sphere effects."
        )
        self.open_spell_book_button.clicked.connect(self._open_spell_book)
        layout.addWidget(self.open_spell_book_button)
        return section

    def _magic_range_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)
        layout.addWidget(self._section_title("MAGIC RANGES"))
        self.magic_range_table = QTableWidget(3, 3)
        self.magic_range_table.setHorizontalHeaderLabels(
            ("Range", "Calculation", "Current effective range")
        )
        self._configure_table(self.magic_range_table, stretch_column=1)
        self.magic_range_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.magic_range_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.magic_range_table.verticalHeader().setVisible(False)
        self.magic_range_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.magic_range_table.setFixedHeight(122)
        for row, values in enumerate(
            (
                ("Close", "25 ft + 5 ft per 2 caster levels", "—"),
                ("Medium", "100 ft + 10 ft per caster level", "—"),
                ("Long", "400 ft + 40 ft per caster level", "—"),
            )
        ):
            for column, value in enumerate(values):
                self.magic_range_table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(self.magic_range_table)
        return section

    def _traditions_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("CASTING & MARTIAL TRADITIONS"))
        self.tradition_table = QTableWidget(0, 3)
        self.tradition_table.setHorizontalHeaderLabels(("Type", "Name", "Selected choices"))
        self.tradition_table.setProperty('contentStretchColumns', [1, 2])
        self._configure_table(self.tradition_table, stretch_column=2)
        self.tradition_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tradition_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tradition_table.setMinimumHeight(100)
        layout.addWidget(self.tradition_table)
        tradition_actions = QHBoxLayout()
        add_casting = QPushButton("+ Casting tradition")
        add_casting.setObjectName("primaryButton")
        add_casting.setProperty('prominentAction', True)
        add_casting.clicked.connect(lambda: self._add_tradition("Casting"))
        add_martial = QPushButton("+ Martial tradition")
        add_martial.setObjectName("primaryButton")
        add_martial.setProperty('prominentAction', True)
        add_martial.clicked.connect(lambda: self._add_tradition("Martial"))
        remove_tradition = QPushButton("Remove selected tradition")
        remove_tradition.setObjectName("dangerButton")
        remove_tradition.clicked.connect(self._remove_selected_tradition)
        tradition_actions.addWidget(add_casting)
        tradition_actions.addWidget(add_martial)
        tradition_actions.addWidget(remove_tradition)
        tradition_actions.addStretch()
        layout.addLayout(tradition_actions)
        return section

    def _sphere_build_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPHERES & DRAWBACKS"))
        panels = QHBoxLayout()
        self.magic_sphere_build_panel = QWidget()
        magic_panel = QVBoxLayout(self.magic_sphere_build_panel)
        magic_panel.setContentsMargins(0, 0, 0, 0)
        magic_panel.addWidget(self._section_title("MAGIC SPHERE DRAWBACKS"))
        self.sphere_build_table = QTableWidget(0, 2)
        self.sphere_build_table.setHorizontalHeaderLabels(("Sphere", "Sphere Drawbacks & Choices"))
        self._configure_table(self.sphere_build_table, stretch_column=1)
        self.sphere_build_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.sphere_build_table.setMinimumHeight(180)
        magic_panel.addWidget(self.sphere_build_table)
        actions = QHBoxLayout()
        add = QPushButton("+ Gain base sphere")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add_build_sphere)
        edit_drawbacks = QPushButton("Edit selected drawbacks")
        edit_drawbacks.clicked.connect(self._edit_build_drawbacks)
        remove = QPushButton("Remove selected sphere")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self._remove_build_sphere)
        actions.addWidget(add)
        actions.addWidget(edit_drawbacks)
        actions.addWidget(remove)
        actions.addStretch()
        magic_panel.addLayout(actions)
        panels.addWidget(self.magic_sphere_build_panel, 1)

        self.martial_sphere_build_panel = QWidget()
        martial_panel = QVBoxLayout(self.martial_sphere_build_panel)
        martial_panel.setContentsMargins(0, 0, 0, 0)
        martial_panel.addWidget(self._section_title("MARTIAL SPHERE DRAWBACKS"))
        self.martial_sphere_build_table = QTableWidget(0, 2)
        self.martial_sphere_build_table.setHorizontalHeaderLabels(("Sphere", "Sphere Drawbacks & Choices"))
        self._configure_table(self.martial_sphere_build_table, stretch_column=1)
        self.martial_sphere_build_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.martial_sphere_build_table.setMinimumHeight(180)
        martial_panel.addWidget(self.martial_sphere_build_table)
        martial_actions = QHBoxLayout()
        martial_add = QPushButton("+ Gain base sphere")
        martial_add.setObjectName("primaryButton")
        martial_add.clicked.connect(self._add_martial_build_sphere)
        martial_edit = QPushButton("Edit selected drawbacks")
        martial_edit.clicked.connect(self._edit_martial_build_drawbacks)
        martial_remove = QPushButton("Remove selected sphere")
        martial_remove.setObjectName("dangerButton")
        martial_remove.clicked.connect(self._remove_martial_build_sphere)
        martial_actions.addWidget(martial_add)
        martial_actions.addWidget(martial_edit)
        martial_actions.addWidget(martial_remove)
        martial_actions.addStretch()
        martial_panel.addLayout(martial_actions)
        panels.addWidget(self.martial_sphere_build_panel, 1)
        layout.addLayout(panels)
        return section

    def _spells_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        self.spells_section_title = self._section_title("SPELLS & MAGIC SPHERES")
        layout.addWidget(self.spells_section_title)
        self.spells_section_note = QLabel(section)
        self.spells_section_note.hide()
        self.spell_table = QTableWidget()
        configure_columns(self.spell_table, MAGIC_RECORD_COLUMNS)
        self.spell_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.spell_table.setSortingEnabled(True)
        self.spell_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.spell_table.setMinimumHeight(300)
        self.spell_table.doubleClicked.connect(self._edit_spell)
        self.spell_table.cellClicked.connect(
            lambda *_args: self._select_spell_for_summary("spheres")
        )
        layout.addWidget(self.spell_table, 1)
        actions = QHBoxLayout()
        self.add_magic_button = QPushButton("+ Browse magic")
        self.add_magic_button.setObjectName("primaryButton")
        self.add_magic_button.clicked.connect(self._add_spell)
        edit_button = QPushButton("Edit selected")
        edit_button.clicked.connect(self._edit_spell)
        duration_button = QPushButton("Edit duration")
        duration_button.clicked.connect(self._edit_spell_duration)
        toggle_button = QPushButton("Enable / disable conditional effect")
        toggle_button.clicked.connect(self._toggle_spell)
        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerButton")
        remove_button.clicked.connect(self._remove_spell)
        actions.addWidget(self.add_magic_button)
        actions.addWidget(edit_button)
        actions.addWidget(duration_button)
        actions.addWidget(toggle_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _spells_known_section(self) -> QWidget:
        """Traditional spell repertoire, independent from Spheres effects."""

        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPELLS KNOWN"))
        self.spells_known_table = QTableWidget()
        configure_columns(self.spells_known_table, TRADITIONAL_SPELL_COLUMNS)
        self.spells_known_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.spells_known_table.setSortingEnabled(True)
        self.spells_known_table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.spells_known_table.setMinimumHeight(220)
        self.spells_known_table.doubleClicked.connect(self._edit_known_spell)
        self.spells_known_table.cellClicked.connect(
            lambda *_args: self._select_spell_for_summary("traditional")
        )
        layout.addWidget(self.spells_known_table, 1)
        actions = QHBoxLayout()
        add = QPushButton("+ Add known spell")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add_traditional_spell)
        edit = QPushButton("Edit selected")
        edit.clicked.connect(self._edit_known_spell)
        remove = QPushButton("Remove")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self._remove_known_spell)
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addWidget(remove)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _spell_level_overview_section(self) -> QWidget:
        """Compact, read-only spell progression summary for levels 0–9."""

        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPELLS"))
        self.spell_level_overview_table = QTableWidget(10, 5)
        self.spell_level_overview_table.setObjectName("recordTable")
        self.spell_level_overview_table.setHorizontalHeaderLabels(
            ("Known", "Save DC", "Level", "Per Day", "Bonus")
        )
        self.spell_level_overview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.spell_level_overview_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.spell_level_overview_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.spell_level_overview_table.setAlternatingRowColors(True)
        self.spell_level_overview_table.setShowGrid(False)
        self.spell_level_overview_table.verticalHeader().setVisible(False)
        self.spell_level_overview_table.verticalHeader().setDefaultSectionSize(28)
        header = self.spell_level_overview_table.horizontalHeader()
        header.setHighlightSections(False)
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        fit_table_rows(self.spell_level_overview_table, 10, 10, 10)
        self.spell_level_overview_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.spell_level_overview_table)
        self.spontaneous_slot_usage_panel = QWidget()
        usage_layout = QVBoxLayout(self.spontaneous_slot_usage_panel)
        usage_layout.setContentsMargins(0, 2, 0, 0)
        usage_layout.setSpacing(6)
        self.spontaneous_slot_table = QTableWidget()
        configure_columns(
            self.spontaneous_slot_table,
            (
                TableColumn("Class", stretch=True),
                TableColumn("Lvl", 40),
                TableColumn("Max", 42),
                TableColumn("Used", 44),
                TableColumn("Left", 42),
            ),
        )
        self.spontaneous_slot_table.setMaximumHeight(170)
        usage_layout.addWidget(self.spontaneous_slot_table)
        buttons = QHBoxLayout()
        use_slot = QPushButton("Use slot")
        use_slot.setObjectName("primaryButton")
        use_slot.clicked.connect(self._use_spontaneous_slot)
        restore_slot = QPushButton("Restore slot")
        restore_slot.clicked.connect(self._restore_spontaneous_slot)
        buttons.addWidget(use_slot)
        buttons.addWidget(restore_slot)
        buttons.addStretch()
        usage_layout.addLayout(buttons)
        self.spontaneous_slot_usage_panel.setVisible(False)
        layout.addWidget(self.spontaneous_slot_usage_panel)
        return section

    def _spells_prepared_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPELLS PREPARED"))
        self.spell_slot_table = QTableWidget()
        configure_columns(self.spell_slot_table, SPELL_SLOT_COLUMNS)
        self.spell_slot_table.setMaximumHeight(180)
        layout.addWidget(self.spell_slot_table)
        self.spells_prepared_table = QTableWidget()
        configure_columns(self.spells_prepared_table, PREPARED_SPELL_COLUMNS)
        self.spells_prepared_table.setSortingEnabled(True)
        self.spells_prepared_table.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        self.spells_prepared_table.setMinimumHeight(190)
        self.spells_prepared_table.cellClicked.connect(
            lambda *_args: self._select_spell_for_summary("prepared")
        )
        layout.addWidget(self.spells_prepared_table, 1)
        actions = QHBoxLayout()
        known = QPushButton("+ Prepare known spell")
        known.setObjectName("primaryButton")
        known.clicked.connect(self._prepare_known_spell)
        custom = QPushButton("+ Custom from catalog")
        custom.clicked.connect(self._prepare_custom_spell)
        use = QPushButton("Use one")
        use.clicked.connect(self._use_prepared_spell)
        restore = QPushButton("Restore one")
        restore.clicked.connect(self._restore_prepared_spell)
        quantity = QPushButton("Change copies")
        quantity.clicked.connect(self._change_prepared_spell_count)
        remove = QPushButton("Remove")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self._remove_prepared_spell)
        for button in (known, custom, use, restore, quantity, remove):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _traditional_casting_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("TRADITIONAL SPELLCASTING"))
        cards = QHBoxLayout()
        self.traditional_casting_labels: dict[str, QLabel] = {}
        for key, title in (
            ("classes", "CASTING CLASS"),
            ("method", "METHOD"),
            ("ability", "ABILITY"),
            ("caster_level", "CASTER LEVEL"),
        ):
            card = QFrame()
            card.setObjectName("miniStatCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(7, 4, 7, 4)
            caption = QLabel(title)
            caption.setObjectName("mutedText")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—")
            value.setObjectName("miniStatTotal")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setWordWrap(True)
            card_layout.addWidget(caption)
            card_layout.addWidget(value)
            cards.addWidget(card, 1)
            self.traditional_casting_labels[key] = value
        layout.addLayout(cards)
        return section

    def _spell_point_summary_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPELL POINTS"))
        self.quick_spell_points = QLabel("0 / 0")
        self.quick_spell_points.setObjectName("resourceTotal")
        self.quick_spell_points.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quick_spell_temp = QLabel("No temporary spell points")
        self.quick_spell_temp.setObjectName("mutedText")
        self.quick_spell_temp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.quick_spell_points)
        layout.addWidget(self.quick_spell_temp)
        actions = QHBoxLayout()
        spend = QPushButton("Spend 1")
        spend.clicked.connect(self._spend_spell_point)
        regain = QPushButton("Regain 1")
        regain.clicked.connect(self._regain_spell_point)
        rest = QPushButton("Daily reset")
        rest.setObjectName("primaryButton")
        rest.clicked.connect(self._reset_spell_points)
        actions.addWidget(spend)
        actions.addWidget(regain)
        actions.addWidget(rest)
        layout.addLayout(actions)
        layout.addStretch()
        return section

    def _worn_items_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("WORN ITEMS"))
        from app.ui.equipment_drag import EquipmentDragTable
        self.worn_table = EquipmentDragTable(self, worn=True)
        self.worn_table.equipment_dropped.connect(self._drop_equipment)
        configure_columns(self.worn_table, WORN_RECORD_COLUMNS)
        self.worn_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.worn_table.setMinimumHeight(310)
        self.worn_table.doubleClicked.connect(self._edit_worn_equipment)
        layout.addWidget(self.worn_table, 1)
        actions = QHBoxLayout()
        edit_slots = QPushButton("Edit slots")
        edit_slots.clicked.connect(self._edit_worn_slots)
        edit = QPushButton("Edit selected")
        edit.clicked.connect(self._edit_worn_equipment)
        unequip = QPushButton("Remove")
        unequip.setToolTip("Remove the selected item from use without deleting it.")
        unequip.clicked.connect(self._unequip_worn_equipment)
        actions.addWidget(edit_slots)
        figure = QPushButton("Equipment Figure")
        figure.clicked.connect(self._open_equipment_figure)
        actions.addWidget(figure)
        actions.addWidget(edit)
        actions.addWidget(unequip)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _load_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("LOAD & LIFT"))
        self.load_status = QLabel("LIGHT LOAD")
        self.load_status.setObjectName("loadLight")
        self.load_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.load_status)
        grid = QGridLayout()
        self.load_current = QLabel("0 lb")
        self.load_light = QLabel("0 lb")
        self.load_medium = QLabel("0 lb")
        self.load_heavy = QLabel("0 lb")
        self.load_lift = QLabel("0 lb")
        self.load_drag = QLabel("0 lb")
        self.load_max_dex = QLabel("—")
        self.load_check_penalty = QLabel("—")
        self.load_current_speed = QLabel("—")
        self.load_run = QLabel("×4")
        values = (
            ("Carried", self.load_current),
            ("Light load", self.load_light),
            ("Medium load", self.load_medium),
            ("Heavy load", self.load_heavy),
            ("Lift off ground", self.load_lift),
            ("Push / drag", self.load_drag),
            ("Maximum Dex", self.load_max_dex),
            ("Check penalty", self.load_check_penalty),
            ("Current land speed", self.load_current_speed),
            ("Run", self.load_run),
        )
        for index, (label, value) in enumerate(values):
            grid.addWidget(QLabel(label), index // 2, (index % 2) * 2)
            value.setObjectName("statCode")
            grid.addWidget(value, index // 2, (index % 2) * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)
        layout.addStretch()
        return section

    def _currency_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("CURRENCY"))
        grid = QGridLayout()
        self.currency_controls: dict[str, QSpinBox] = {}
        for index, (key, label) in enumerate(
            (("copper", "CP"), ("silver", "SP"), ("gold", "GP"), ("platinum", "PP"))
        ):
            control = QSpinBox()
            control.setRange(0, 999_999_999)
            control.valueChanged.connect(self._save_currency)
            self.currency_controls[key] = control
            grid.addWidget(QLabel(label), index // 2, (index % 2) * 2)
            grid.addWidget(control, index // 2, (index % 2) * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)
        self.currency_total = QLabel("Total value 0 gp")
        self.currency_total.setObjectName("resourceTotalSmall")
        layout.addWidget(self.currency_total)
        self.currency_notes = QLineEdit()
        self.currency_notes.setPlaceholderText("Gems, debts, valuables, or other currencies")
        self.currency_notes.editingFinished.connect(self._save_currency)
        layout.addWidget(self.currency_notes)
        layout.addStretch()
        return section

    def _casting_profile_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPHERECASTING"))

        form = QGridLayout()
        self.casting_ability = QComboBox()
        for key, name, abbreviation in ABILITIES:
            self.casting_ability.addItem(f"{name} ({abbreviation})", key)
        formula_editor = lambda minimum, maximum: FormulaNumberEdit(
            minimum,
            maximum,
            evaluator=self._evaluate_character_formula,
            suggestion_provider=self._character_formula_suggestions,
        )
        self.casting_class_levels = formula_editor(0, 999)
        self.caster_level = formula_editor(0, 999)
        self.casting_msb_misc = formula_editor(-99, 99)
        self.casting_dc_misc = formula_editor(-99, 99)
        self.casting_concentration_misc = formula_editor(-99, 99)
        controls = (
            ("Casting ability", self.casting_ability),
            ("Casting-class levels", self.casting_class_levels),
            ("Base caster level", self.caster_level),
            ("MSB adjustment", self.casting_msb_misc),
            ("Save DC adjustment", self.casting_dc_misc),
            ("Concentration adjustment", self.casting_concentration_misc),
        )
        for index, (label, control) in enumerate(controls):
            form.addWidget(QLabel(label), index, 0)
            form.addWidget(control, index, 1)
        form.setColumnStretch(1, 1)
        layout.addLayout(form)

        derived = QGridLayout()
        self.casting_cam = QLabel("+0")
        self.casting_save_dc = QLabel("10")
        self.casting_msb = QLabel("+0")
        self.casting_msd = QLabel("11")
        self.casting_concentration = QLabel("+0")
        for index, (label, value) in enumerate(
            (
                ("CAM", self.casting_cam),
                ("Sphere DC", self.casting_save_dc),
                ("MSB", self.casting_msb),
                ("MSD", self.casting_msd),
                ("Concentration", self.casting_concentration),
            )
        ):
            card = QFrame()
            card.setObjectName("miniStatCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 4, 5, 4)
            title = QLabel(label)
            title.setObjectName("mutedText")
            value.setObjectName("miniStatTotal")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(value)
            derived.addWidget(card, index // 3, index % 3)
        layout.addLayout(derived)

        spell_points_title = QLabel("SPELL-POINT POOL")
        spell_points_title.setObjectName("minorTitle")
        layout.addWidget(spell_points_title)
        spell_points = QGridLayout()
        self.spell_points_current = QSpinBox()
        self.spell_points_maximum = formula_editor(0, 99999)
        self.spell_points_temporary = QSpinBox()
        self.spell_points_misc = formula_editor(-9999, 9999)
        for control in (self.spell_points_current, self.spell_points_temporary):
            control.setRange(0, 99999)
        self.spell_points_auto = QCheckBox("Automatic maximum from modular rule sources")
        spell_points.addWidget(QLabel("Current"), 0, 0)
        spell_points.addWidget(self.spell_points_current, 0, 1)
        spell_points.addWidget(QLabel("Maximum"), 1, 0)
        spell_points.addWidget(self.spell_points_maximum, 1, 1)
        spell_points.addWidget(QLabel("Temporary"), 2, 0)
        spell_points.addWidget(self.spell_points_temporary, 2, 1)
        spell_points.addWidget(QLabel("Other adjustment"), 3, 0)
        spell_points.addWidget(self.spell_points_misc, 3, 1)
        spell_points.addWidget(self.spell_points_auto, 4, 0, 1, 2)
        spell_points.setColumnStretch(1, 1)
        layout.addLayout(spell_points)
        self.spell_points_breakdown = QLabel("Manual maximum")
        self.spell_points_breakdown.setObjectName("formulaText")
        self.spell_points_breakdown.setWordWrap(True)
        layout.addWidget(self.spell_points_breakdown)

        tradition_title = QLabel("CASTING TRADITION")
        tradition_title.setObjectName("minorTitle")
        layout.addWidget(tradition_title)
        self.tradition_name = QLineEdit()
        self.tradition_name.setPlaceholderText("Tradition name")
        self.tradition_boons = QLineEdit()
        self.tradition_boons.setPlaceholderText("Boons")
        self.tradition_drawbacks = QPlainTextEdit()
        self.tradition_drawbacks.setPlaceholderText("General and sphere-specific drawbacks")
        self.tradition_drawbacks.setMaximumHeight(70)
        self.tradition_notes = QPlainTextEdit()
        self.tradition_notes.setPlaceholderText("Casting requirements, implements, and notes")
        self.tradition_notes.setMaximumHeight(70)
        layout.addWidget(self.tradition_name)
        layout.addWidget(self.tradition_boons)
        layout.addWidget(self.tradition_drawbacks)
        layout.addWidget(self.tradition_notes)

        actions = QHBoxLayout()
        save = QPushButton("Save casting profile")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save_casting_profile)
        reset = QPushButton("Daily spell-point reset")
        reset.clicked.connect(self._reset_spell_points)
        actions.addWidget(save)
        actions.addWidget(reset)
        actions.addStretch()
        layout.addLayout(actions)

        for control in (
            self.casting_class_levels,
            self.caster_level,
            self.casting_msb_misc,
            self.casting_dc_misc,
            self.casting_concentration_misc,
            self.spell_points_maximum,
            self.spell_points_misc,
        ):
            control.editor.editingFinished.connect(self._save_casting_profile)
        self.spell_points_current.valueChanged.connect(self._save_casting_profile)
        self.spell_points_temporary.valueChanged.connect(self._save_casting_profile)
        self.casting_ability.currentIndexChanged.connect(self._save_casting_profile)
        self.spell_points_auto.toggled.connect(self._save_casting_profile)
        self.tradition_name.editingFinished.connect(self._save_casting_profile)
        self.tradition_boons.editingFinished.connect(self._save_casting_profile)
        return section

    def _sphere_statistics_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("sheetSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.addWidget(self._section_title("SPHERES & EFFECT STATISTICS"))
        self.sphere_stats_table = QTableWidget(0, 8)
        self.sphere_stats_table.setHorizontalHeaderLabels(
            ("Sphere", "CL", "DC", "Talents", "Drawbacks", "CL adj.", "DC adj.", "Notes")
        )
        self._configure_table(self.sphere_stats_table, stretch_column=0)
        self.sphere_stats_table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )
        self.sphere_stats_table.setMinimumHeight(365)
        self.sphere_stats_table.doubleClicked.connect(self._edit_sphere_statistic)
        layout.addWidget(self.sphere_stats_table, 1)
        actions = QHBoxLayout()
        edit = QPushButton("Edit selected sphere")
        edit.setObjectName("primaryButton")
        edit.clicked.connect(self._edit_sphere_statistic)
        reset = QPushButton("Clear adjustment")
        reset.clicked.connect(self._clear_sphere_statistic)
        actions.addWidget(edit)
        actions.addWidget(reset)
        actions.addStretch()
        layout.addLayout(actions)
        return section

    def _conditions_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        tab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = self._section_title("CONDITIONS & EFFECTS")
        layout.addWidget(title)
        self.condition_table = QTableWidget(0, 2)
        self.condition_table.setHorizontalHeaderLabels(("Condition", "Effect"))
        self._configure_table(self.condition_table, stretch_column=1)
        self.condition_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.condition_table.setMinimumHeight(92)
        self.condition_table.setMaximumHeight(170)
        layout.addWidget(self.condition_table)
        actions = QHBoxLayout()
        add_button = QPushButton("+ Add condition")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_condition)
        effect_button = QPushButton("+ Add ongoing effect")
        effect_button.clicked.connect(self._add_ongoing_effect)
        edit_button = QPushButton("Edit selected")
        edit_button.clicked.connect(self._edit_condition_or_effect)
        toggle_button = QPushButton("Enable / disable")
        toggle_button.clicked.connect(self._toggle_condition_or_effect)
        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerButton")
        remove_button.clicked.connect(self._remove_condition)
        actions.addWidget(add_button)
        actions.addWidget(effect_button)
        actions.addWidget(edit_button)
        actions.addWidget(toggle_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        layout.addLayout(actions)
        return tab

    def _equipment_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        header = QHBoxLayout()
        title = self._section_title("INVENTORY & EQUIPMENT")
        self.weight_summary = QLabel("Total weight 0 lb")
        self.weight_summary.setObjectName("mutedText")
        self.inventory_value_summary = QLabel("Inventory value 0 gp")
        self.inventory_value_summary.setObjectName("mutedText")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.weight_summary)
        header.addWidget(self.inventory_value_summary)
        layout.addLayout(header)
        from app.ui.equipment_drag import EquipmentDragTable
        self.equipment_table = EquipmentDragTable(self)
        self.equipment_table.equipment_dropped.connect(self._drop_equipment)
        configure_columns(self.equipment_table, EQUIPMENT_RECORD_COLUMNS)
        self.equipment_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.equipment_table.setMinimumHeight(310)
        self.equipment_table.doubleClicked.connect(self._edit_equipment)
        layout.addWidget(self.equipment_table, 1)
        actions = QHBoxLayout()
        add_button = QPushButton("+ Add item")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_equipment)
        self.open_inventory_button = QPushButton("Open Inventory")
        self.open_inventory_button.setObjectName("primaryButton")
        self.open_inventory_button.setToolTip(
            "Open the wide searchable inventory organizer with automatic and custom categories."
        )
        self.open_inventory_button.clicked.connect(self._open_inventory)
        edit_button = QPushButton("Edit selected")
        edit_button.clicked.connect(self._edit_equipment)
        self.wear_item_button = QPushButton("Wear")
        self.wear_item_button.setToolTip(
            "Wear, wield, or equip the selected item using its natural item state."
        )
        self.wear_item_button.clicked.connect(self._wear_equipment)
        self.remove_item_button = QPushButton("Remove")
        self.remove_item_button.setToolTip(
            "Remove the selected item from use without deleting it from inventory."
        )
        self.remove_item_button.clicked.connect(self._remove_equipment_from_use)
        self.wear_item_button.setEnabled(False)
        self.remove_item_button.setEnabled(False)
        self.equipment_table.itemSelectionChanged.connect(
            self._update_equipment_action_buttons
        )
        actions.addWidget(add_button)
        actions.addWidget(self.open_inventory_button)
        figure = QPushButton("Equipment Figure")
        figure.clicked.connect(self._open_equipment_figure)
        actions.addWidget(figure)
        actions.addWidget(edit_button)
        actions.addWidget(self.wear_item_button)
        actions.addWidget(self.remove_item_button)
        actions.addWidget(
            action_menu_button(
                (
                    ("Change state", self._change_equipment_state),
                    ("Edit item choices", self._edit_equipment_choices),
                    ("Enchant selected", self._enchant_equipment),
                    ("", None),
                    ("Delete from inventory", self._remove_equipment),
                ),
                "More actions",
            )
        )
        actions.addStretch()
        layout.addLayout(actions)
        return tab

    def _attacks_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("sheetSection")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)
        title = self._section_title("WEAPONS & ATTACKS")
        layout.addWidget(title)
        self.attack_table = QTableWidget(0, 6)
        self.attack_table.setHorizontalHeaderLabels(
            ("Attack", "Type", "Attack bonus", "Damage", "Critical", "Notes")
        )
        self._configure_table(self.attack_table, stretch_column=0)
        self.attack_table.setMinimumHeight(210)
        self.attack_table.doubleClicked.connect(self._edit_attack)
        self.attack_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.attack_table, 1)
        actions = QHBoxLayout()
        add_button = QPushButton("+ Add attack")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_attack)
        conditional_button = QPushButton("+ Add conditional attack")
        conditional_button.clicked.connect(self._add_conditional_attack)
        edit_button = QPushButton("Edit selected")
        edit_button.clicked.connect(self._edit_attack)
        roll_button = QPushButton("Roll selected")
        roll_button.clicked.connect(self._roll_attack)
        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerButton")
        remove_button.clicked.connect(self._remove_attack)
        actions.addWidget(add_button)
        actions.addWidget(conditional_button)
        actions.addWidget(edit_button)
        actions.addWidget(roll_button)
        actions.addWidget(remove_button)
        actions.addWidget(
            action_menu_button(
                (("Edit hidden / conditional attacks", self._manage_conditional_attacks),),
                "More",
            )
        )
        actions.addStretch()
        layout.addLayout(actions)
        return tab

    @staticmethod
    def _section_title(text: str) -> QLabel:
        return section_title(text)

    @staticmethod
    def _configure_table(table: QTableWidget, stretch_column: int) -> None:
        configure_record_table(table, stretch_column)

    @staticmethod
    def _weight_text(value: float) -> str:
        return f"{value:g} lb"
