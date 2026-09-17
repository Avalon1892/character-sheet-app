"""Content-led dialog presentation, independent of selections and rules.

Profiles express deliberate starting sizes. Table sizing measures only visible
rows; it never scans catalogs or changes selection, sorting, or stored data.
"""
from dataclasses import dataclass
from PySide6.QtCore import QObject, QEvent, QTimer, Qt
from shiboken6 import isValid
from PySide6.QtWidgets import (
    QDialog, QApplication, QFormLayout, QHeaderView, QTableWidget, QListWidget,
    QTextEdit, QPlainTextEdit, QSplitter, QLabel, QLineEdit, QScrollArea, QSizePolicy,
)


@dataclass(frozen=True)
class DialogProfile:
    width: int
    height: int
    split: tuple[int, ...] = ()


PROFILES = {}
def register(names, width, height, split=()):
    for name in names.split():
        PROFILES[name] = DialogProfile(width, height, split)

register('FeatCatalogDialog TraitCatalogDialog AnimalCompanionFeatCatalogDialog MartialTalentCatalogDialog MagicTalentCatalogDialog ItemCatalogDialog', 1480, 860)
register('TraditionalSpellCatalogDialog ClassCatalogDialog ArchetypeSelectionDialog FamiliarCatalogDialog DrawbackTalentChoiceDialog', 1240, 790, (56, 44))
register('TraditionCatalogDialog OptionalTraditionDialog', 1140, 760, (30, 70))
register('RaceCatalogDialog', 1380, 820, (20, 42, 38))
register('ClassPowerDialog', 1260, 780)
register('CraftingCatalogDialog', 1400, 840, (56, 44))
register('ClassChoiceDialog', 1100, 730)
register('EquipmentDialog', 1160, 790, (54, 46))
register('ItemEnchantmentsDialog', 1160, 790, (54, 46))
register('AttackDialog', 1040, 690)
register('SpellDialog CustomTrackerDialog ClassFeatureStateDialog', 760, 730)
register('CharacterAuditDialog', 1280, 820)
register('CharacterCreationDialog CustomTraditionDialog', 1260, 820)
register('SpellBookDialog MartialBookDialog InventoryOrganizerDialog MoldableTalentsDialog', 1460, 850)
register('SpecialAbilityDialog ProficiencyDialog OngoingEffectDialog SequenceOptionDialog MartialTalentDialog', 760, 560)
register('StatBreakdownDialog', 940, 580)
register('RestConfigurationDialog SphereAcquisitionDialog TraditionChoiceDialog', 900, 740)
register('WornSlotsDialog', 560, 650)
register('CodexDialog', 1380, 850)
register('ClassLevelDialog', 680, 700)
register('SkillDialog FeatChoiceDialog', 620, 420)
register('ConditionDialog ModifierDialog', 560, 240)

NAME_HEADERS = {'name', 'spell name', 'class', 'archetype', 'talent', 'feat', 'trait', 'item', 'property', 'applied property', 'familiar', 'issue', 'source'}
COMPACT_WIDTHS = {'use': 48, 'owned': 58, 'level': 62, 'value': 76, 'quantity': 76, 'cost': 90,
                  'price': 100, 'status': 110, 'ruleset': 112, 'type': 120, 'school': 170,
                  'family': 150, 'severity': 94, 'sheet effect': 180, 'replaces / alters': 230}


class ReadableDialogTable(QObject):
    def __init__(self, table):
        super().__init__(table)
        self.table = table
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.fit)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.verticalHeader().setDefaultSectionSize(34)
        table.viewport().installEventFilter(self)
        table.verticalScrollBar().valueChanged.connect(self.schedule)
        table.model().modelReset.connect(self.schedule)
        table.model().rowsInserted.connect(self.schedule)
        table.horizontalHeader().sectionResized.connect(self.schedule)
        labels = [(table.horizontalHeaderItem(c).text().casefold() if table.horizontalHeaderItem(c) else '') for c in range(table.columnCount())]
        # Leave editable grids and stat breakdown arithmetic under their own layout.
        primary = next((i for i, label in enumerate(labels) if label in NAME_HEADERS), None)
        if primary is not None and table.columnCount() > 1:
            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            for i, label in enumerate(labels):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(i, COMPACT_WIDTHS.get(label, 155))
            header.setSectionResizeMode(primary, QHeaderView.ResizeMode.Stretch)
            for i, label in enumerate(labels):
                if label in ('description', 'reason', 'effect', 'details'):
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.schedule()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.schedule()
        return False

    def schedule(self, *_):
        if isValid(self.timer) and not self.timer.isActive():
            self.timer.start()

    def fit(self):
        table = self.table
        if not isValid(table) or not table.isVisible():
            return
        first = max(0, table.rowAt(0))
        last = table.rowAt(table.viewport().height() - 1)
        if last < 0:
            last = first + 25
        for row in range(first, min(table.rowCount(), last + 2, first + 45)):
            table.resizeRowToContents(row)
            widget_height = max((table.cellWidget(row, column).minimumSizeHint().height() + 6
                                 for column in range(table.columnCount())
                                 if table.cellWidget(row, column) is not None), default=0)
            table.setRowHeight(row, max(34, table.rowHeight(row), widget_height))


def apply_dialog_layout(dialog):
    """One-shot polish on first show; never resets a user's subsequent resize."""
    if dialog.property('contentLayoutApplied') or type(dialog).__module__.startswith('PySide6'):
        return
    dialog.setProperty('contentLayoutApplied', True)
    profile = PROFILES.get(type(dialog).__name__)
    if profile:
        screen = dialog.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        width, height = min(profile.width, area.width() - 48), min(profile.height, area.height() - 64)
        dialog.setMinimumSize(min(640, width), min(400, height))
        dialog.resize(width, height)
    if dialog.layout():
        dialog.layout().setContentsMargins(18, 16, 18, 16)
        dialog.layout().setSpacing(10)
    for form in dialog.findChildren(QFormLayout):
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(9)
    from app.ui.components import FormulaNumberEdit
    for field in dialog.findChildren(FormulaNumberEdit):
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    for editor in dialog.findChildren(QLineEdit):
        if editor.placeholderText().lower().startswith('search'):
            editor.setClearButtonEnabled(True)
    for label in dialog.findChildren(QLabel):
        if len(label.text()) > 85 and not label.text().lstrip().startswith('<'):
            label.setWordWrap(True)
    for view in dialog.findChildren(QListWidget):
        view.setWordWrap(True)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
    for text in [*dialog.findChildren(QTextEdit), *dialog.findChildren(QPlainTextEdit)]:
        text.setMinimumWidth(0)
        text.document().setDocumentMargin(12)
    # Catalogs have their own more specialised, responsive three-panel policy.
    if not hasattr(dialog, 'catalog_presentation'):
        splits = [s for s in dialog.findChildren(QSplitter) if s.orientation() == Qt.Orientation.Horizontal]
        # Dense item forms need a scrollable editor, not clipped lower fields.
        # Keep the description and confirmation controls independently visible.
        if type(dialog).__name__ == 'EquipmentDialog' and splits:
            split = splits[0]
            if not isinstance(split.widget(0), QScrollArea):
                editor = split.widget(0)
                editor.setParent(None)
                scroll = QScrollArea()
                scroll.setObjectName('dialogFormScroll')
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QScrollArea.Shape.NoFrame)
                scroll.setWidget(editor)
                split.insertWidget(0, scroll)
        if profile and profile.split and splits:
            split = splits[0]
            if split.count() == len(profile.split):
                split.setChildrenCollapsible(False)
                split.setHandleWidth(8)
                for i, weight in enumerate(profile.split):
                    split.widget(i).setMinimumWidth(150)
                    split.setStretchFactor(i, weight)
                split.setSizes([weight * 10 for weight in profile.split])
        dialog._readable_tables = [ReadableDialogTable(table) for table in dialog.findChildren(QTableWidget)
                                  if table.editTriggers() == table.EditTrigger.NoEditTriggers]
    if profile:
        if dialog.layout():
            dialog.layout().activate()
        dialog.resize(width, height)
