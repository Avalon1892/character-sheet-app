from __future__ import annotations


THEME_LABELS = {
    "classic": "Classic Parchment",
    "dark": "Dark Mode",
}
DEFAULT_THEME = "classic"


def normalize_theme(theme: str) -> str:
    return theme if theme in THEME_LABELS else DEFAULT_THEME


def style_sheet(theme: str = DEFAULT_THEME) -> str:
    theme = normalize_theme(theme)
    style = """
        QMainWindow, QWidget {
            background: #e2e4e5;
            color: #24282b;
            font: 9pt 'Segoe UI';
        }
        QMenuBar, QMenu { background: #f5f5f2; color: #272b2e; }
        QMenuBar::item:selected, QMenu::item:selected { background: #656b6f; color: white; }
        #sidebar { background: #363b3f; border-right: 3px solid #858b8e; }
        #sidebar QLabel { color: #f4f4f1; }
        #sidebar #muted { color: #c0c5c7; }
        QListWidget { background: #2c3033; border: 1px solid #555b5f; color: #f3f3ef; outline: none; }
        QListWidget::item { padding: 10px; border-bottom: 1px solid #464b4e; }
        QListWidget::item:hover { background: #4d5357; }
        QListWidget::item:selected { background: #737a7e; color: white; }
        QPushButton {
            min-height: 21px;
            padding: 4px 9px;
            border: 1px solid #9ca1a4;
            border-radius: 1px;
            background: #f2f2ef;
            color: #25292c;
        }
        QPushButton:hover { background: #ffffff; border-color: #5f666a; }
        QPushButton:pressed { background: #d8dbdc; }
        #primaryButton { color: white; background: #5d6367; border: 1px solid #43484b; font-weight: 700; }
        #primaryButton:hover { background: #737a7e; }
        #dangerButton { color: #9b302c; font-weight: 600; }
        QLabel[validationError="true"] { color: #b42318; font-weight: 600; }
        #heroTitle { color: #353a3d; font: 700 23pt 'Georgia'; }
        #pageSubtitle { color: #676e72; font-weight: 600; }
        QListWidget#creationStepList {
            background: #f0f1f0;
            color: #353a3d;
            border: 1px solid #b8bdc0;
            border-radius: 4px;
            padding: 7px;
            outline: none;
        }
        QListWidget#creationStepList::item {
            min-height: 34px;
            padding: 5px 8px;
            border: none;
            border-radius: 3px;
            font-weight: 700;
        }
        QListWidget#creationStepList::item:hover { background: #e7eaeb; }
        QListWidget#creationStepList::item:selected {
            background: #62686c;
            color: #ffffff;
        }
        QStackedWidget#creationPages {
            background: #f7f7f4;
            border: 1px solid #b8bdc0;
            border-radius: 4px;
        }
        QLabel#creationPageTitle {
            color: #353a3d;
            font: 700 16pt 'Georgia';
            padding-bottom: 3px;
            border-bottom: 2px solid #62686c;
        }
        QFrame#creationChoiceCard, QFrame#creationSummary {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
            border-radius: 4px;
        }
        QLabel#creationSummaryName {
            color: #353a3d;
            font: 700 17pt 'Georgia';
            padding: 8px 2px 2px 2px;
        }
        QLabel#creationAbilitySummary {
            padding: 9px 5px;
            background: #f0f1f0;
            border: 1px solid #c6cacc;
            font-weight: 700;
        }
        QLabel#creationLargeChoice { font: 700 16pt 'Georgia'; padding: 6px 0; }
        QLabel#creationColumnHeader { color: #676e72; font-weight: 700; }
        QLabel#creationAbilityName {
            min-width: 44px;
            padding: 6px 8px;
            color: #ffffff;
            background: #62686c;
            font: 700 10pt 'Georgia';
        }
        QLabel#creationRacialAdjustment {
            min-width: 54px;
            padding: 6px 8px;
            color: #4a5054;
            background: #e7eaeb;
            border: 1px solid #c6cacc;
            font-weight: 700;
        }
        QLabel#creationFinalScore {
            min-width: 64px;
            padding: 5px 9px;
            color: #353a3d;
            background: #fbfbf8;
            border: 2px solid #62686c;
            font: 700 13pt 'Georgia';
        }
        QLabel#creationScoreCost {
            padding: 7px 9px;
            color: #454b4e;
            background: #eee5cd;
            border-left: 3px solid #8b613d;
            font-weight: 700;
        }
        QTextBrowser#creationReview {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
            padding: 12px;
        }
        QWidget#characterLibraryPage, QWidget#characterLibraryCards,
        QScrollArea#characterLibraryScroll {
            background: #f7f7f4;
            border: none;
        }
        QLabel#libraryTitle {
            color: #353a3d;
            font: 700 25pt 'Georgia';
        }
        QLabel#librarySubtitle {
            color: #676e72;
            font: 600 10pt 'Segoe UI';
        }
        QPushButton#characterLibraryCard, QPushButton#createCharacterCard {
            min-width: 218px;
            min-height: 150px;
            padding: 14px;
            background: #fbfbf8;
            color: #353a3d;
            border: 2px solid #b8bdc0;
            border-radius: 6px;
            font: 700 12pt 'Segoe UI';
        }
        QPushButton#characterLibraryCard:hover {
            background: #f0f1f0;
            border-color: #62686c;
        }
        QPushButton#createCharacterCard {
            color: #62686c;
            border-style: dashed;
            font: 700 14pt 'Segoe UI';
        }
        QPushButton#createCharacterCard:hover {
            background: #f0f1f0;
            color: #353a3d;
            border-color: #62686c;
        }
        #mutedText { color: #72787b; font-size: 8pt; }
        QFrame#floatingNoteOverlay { background: transparent; border: none; }
        QFrame#floatingNotePageRail { background: transparent; border: none; }
        QToolButton#floatingNotePageTab, QToolButton#floatingNoteAddPage {
            min-width: 30px; max-width: 30px; min-height: 28px; max-height: 28px;
            padding: 0; margin: 0; border: 1px solid #34393c;
            border-right: none; border-radius: 3px 0 0 3px;
            background: #f0f1f0; color: #34393c; font: 700 9pt 'Segoe UI';
        }
        QToolButton#floatingNotePageTab:checked {
            background: #34393c; color: #ffffff;
        }
        QToolButton#floatingNoteAddPage {
            background: #62686c; color: #ffffff; font-size: 13pt;
        }
        QFrame#floatingSheetNote {
            background: #fbfbf8;
            border: 2px solid #34393c;
            border-radius: 4px;
        }
        QFrame#floatingNoteTitleBar {
            background: #34393c;
            border: none;
            border-top: 5px solid #202427;
        }
        QToolButton#floatingNotePin, QToolButton#floatingNoteClose {
            min-width: 22px; max-width: 22px; min-height: 20px; max-height: 20px;
            padding: 0; background: transparent; border: none;
            color: #ffffff; font: 700 13pt 'Segoe UI';
        }
        QToolButton#floatingNoteClose { color: #202427; background: #ffffff; border-radius: 9px; }
        QToolButton#floatingNotePin:checked { background: #ffffff; color: #202427; border-radius: 3px; }
        QToolButton#floatingNoteToolbarToggle {
            min-width: 34px; min-height: 14px; max-height: 16px;
            padding: 0; border: none; background: rgba(0, 0, 0, 38);
            color: rgba(0, 0, 0, 150); font: 700 8pt 'Segoe UI';
        }
        QFrame#floatingNoteToolbar {
            background: #f0f1f0; border: none; border-bottom: 1px solid #a9aeb1;
        }
        QTextEdit#floatingNoteEditor {
            background: #fbfbf8; color: #202427; border: none;
            padding: 7px; font: 11pt 'Georgia';
        }
        QLabel#floatingNoteResizeHandle {
            color: #ffffff; background: #34393c; border: 1px solid #202427;
            border-radius: 8px; font: 8pt 'Segoe UI';
        }
        #sheetScroll { border: none; background: #d4d7d8; }
        QWidget#builderPage, QWidget#corePage, QWidget#inventoryPage, QWidget#magicPage {
            background: #f7f7f4;
        }
        #sheetMasthead {
            background: #fafaf7;
            border: none;
            border-bottom: 3px solid #5f6569;
        }
        #sheetBrand { color: #34393c; font: 700 22pt 'Georgia'; }
        #sheetBrandSubtitle { color: #747a7d; font: 700 8pt 'Segoe UI'; letter-spacing: 2px; }
        #sheetEdition { color: #62686c; font: 700 8pt 'Segoe UI'; }
        QFrame#auditStatusBar {
            min-height: 28px;
            background: #f0f1f0;
            border: none;
            border-bottom: 1px solid #c1c5c7;
        }
        QFrame#auditStatusBar[auditState="valid"] {
            background: #e5ece7; border-bottom: 2px solid #33553d;
        }
        QFrame#auditStatusBar[auditState="choice"] {
            background: #cbdde8; border-bottom: 2px solid #3c4f5a;
        }
        QFrame#auditStatusBar[auditState="warning"] {
            background: #eee5cd; border-bottom: 2px solid #8b613d;
        }
        QFrame#auditStatusBar[auditState="error"] {
            background: #f2dddd; border-bottom: 2px solid #8d3733;
        }
        QLabel#auditStatusText { font-weight: 700; }
        QPushButton#auditStatusButton { min-height: 18px; padding: 2px 10px; }
        QFrame#auditResolutionPanel {
            background: #eee5cd;
            border: 1px solid #b89a62;
        }
        QTabWidget#sheetPages::pane { border: none; background: #d4d7d8; }
        QTabWidget#sheetPages QTabBar::tab {
            min-width: 185px;
            min-height: 30px;
            padding: 4px 18px;
            margin: 0;
            background: #b9bdc0;
            color: #34393c;
            border: none;
            border-right: 1px solid #dfe1e2;
            font-weight: 700;
        }
        QTabWidget#sheetPages QTabBar::tab:hover { background: #cdd0d2; }
        QTabWidget#sheetPages QTabBar::tab:selected { background: #5d6367; color: white; }
        QFrame#ultraStatusHeader {
            background: #fafaf7;
            border: none;
            border-bottom: 3px solid #5f6569;
        }
        QLabel#ultraCharacterName { color: #353a3d; font: 700 18pt 'Georgia'; }
        QLabel#ultraCharacterClasses { color: #676e72; font-weight: 600; }
        QFrame#ultraStatusChip, QFrame#ultraResourceChip {
            min-width: 58px;
            background: #f0f1f0;
            border: 1px solid #c1c5c7;
            border-radius: 4px;
        }
        QLabel#ultraStatusLabel, QLabel#ultraStatLabel {
            color: #72787b;
            font: 700 7pt 'Segoe UI';
        }
        QLabel#ultraStatusValue { color: #202427; font: 700 12pt 'Georgia'; }
        QLabel#ultraResourceTotal { color: #202427; font: 700 13pt 'Georgia'; }
        QTabWidget#ultraPages::pane { border: none; background: #d4d7d8; }
        QTabWidget#ultraPages QTabBar::tab {
            min-width: 128px;
            min-height: 30px;
            padding: 4px 14px;
            background: #b9bdc0;
            color: #34393c;
            border: none;
            border-right: 1px solid #dfe1e2;
            font-weight: 700;
        }
        QTabWidget#ultraPages QTabBar::tab:hover { background: #cdd0d2; }
        QTabWidget#ultraPages QTabBar::tab:selected { background: #5d6367; color: white; }
        QScrollArea#ultraScroll, QWidget#ultraPage { background: #f7f7f4; border: none; }
        QFrame#ultraCard {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
            border-radius: 4px;
        }
        QLabel#ultraCardTitle {
            min-height: 24px;
            padding: 2px 8px;
            background: #62686c;
            color: white;
            border: none;
            font: 700 10pt 'Segoe UI';
        }
        QFrame#ultraStatTile {
            min-height: 54px;
            background: #f0f1f0;
            border: 1px solid #c1c5c7;
            border-radius: 3px;
        }
        QLabel#ultraStatValue { color: #202427; font: 700 15pt 'Georgia'; }
        QLabel#ultraStatDetail { color: #555b5f; font: 700 8pt 'Segoe UI'; }
        QLabel#ultraHint { color: #676e72; font: 600 8pt 'Segoe UI'; }
        QLabel#ultraBuildValue {
            min-height: 24px;
            padding: 2px 5px;
            color: #202427;
            background: #f0f1f0;
            border-bottom: 1px solid #a9aeb1;
            font-weight: 600;
        }
        QLabel#ultraCompanionName { color: #353a3d; font: 700 17pt 'Georgia'; }
        QTableWidget#ultraTable {
            background: #f7f7f4;
            alternate-background-color: #e8eaeb;
            gridline-color: transparent;
            border: 1px solid #aeb3b6;
            border-radius: 3px;
        }
        QTableWidget#ultraTable::item {
            padding: 4px 6px;
            border-bottom: 1px solid #d1d4d5;
        }
        QWidget#sheetSection {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
        }
        QFrame#customTrackerBlock {
            min-height: 92px;
            background: #f0f1f0;
            border: 2px solid #858b8e;
            border-radius: 3px;
        }
        QFrame#runtimeBuildingBlock, QFrame#blockDesignerCanvas {
            background: #fbfbf8;
            border: 2px solid #858b8e;
            border-radius: 3px;
        }
        QLabel#runtimeBlockTitle {
            min-height: 24px;
            padding: 1px 8px;
            background: #62686c;
            color: white;
            font: 700 10pt 'Segoe UI';
        }
        QLabel#sectionTitle {
            min-height: 23px;
            padding: 2px 8px;
            background: #62686c;
            color: white;
            border: none;
            font: 700 10pt 'Segoe UI';
        }
        QLabel#minorTitle { color: #454b4e; font: 700 9pt 'Segoe UI'; }
        QFrame#dialogSection {
            background: #f0f1f0;
            border: 1px solid #b8bdc0;
            padding: 8px;
        }
        QLabel#formulaHelp {
            min-height: 30px;
            padding: 7px 9px;
            background: #e7eaeb;
            color: #4a5054;
            border-left: 3px solid #62686c;
        }
        QLabel#formulaResult {
            min-height: 20px;
            padding: 2px 6px;
            background: #e5ece7;
            color: #33553d;
            border: 1px solid #9caf9f;
            font-weight: 700;
        }
        QLabel#formulaResult[formulaError="true"] {
            background: #f2dddd;
            color: #8d3733;
            border-color: #bd8581;
        }
        QTreeWidget#formulaCompletionPopup {
            background: #fbfbf8;
            color: #292e31;
            border: 2px solid #62686c;
            outline: none;
            alternate-background-color: #edf0f0;
        }
        QTreeWidget#formulaCompletionPopup::item {
            min-height: 23px;
            padding: 2px 5px;
        }
        QTreeWidget#formulaCompletionPopup::item:selected {
            background: #62686c;
            color: white;
        }
        QTreeWidget#formulaCompletionPopup QHeaderView::section {
            background: #d8dcdd;
            color: #34393c;
            border: none;
            border-bottom: 1px solid #858b8e;
            padding: 4px 6px;
            font-weight: 700;
        }
        QFrame#statCard { background: #f0f1f0; border: 1px solid #c1c5c7; }
        QFrame#miniStatCard { background: #f0f1f0; border: 1px solid #c7cbcd; }
        QScrollArea#spellBookScroll, QWidget#traditionalSpellBookPage,
        QWidget#sphereSpellBookPage {
            background: #f7f7f4;
            border: none;
        }
        QFrame#spellBookSection {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
            border-radius: 3px;
        }
        QLabel#spellBookSectionTitle {
            min-height: 22px;
            padding: 2px 7px;
            background: #62686c;
            color: white;
            font: 700 9pt 'Segoe UI';
        }
        QFrame#spellBookEntry {
            min-height: 84px;
            background: #f0f1f0;
            border: 1px solid #c7cbcd;
            border-radius: 3px;
        }
        QFrame#spellBookEntry[available="false"] {
            background: #e8eaeb;
            border-color: #d1d4d5;
        }
        QLabel#spellBookEntryName {
            color: #202427;
            font: 700 10pt 'Segoe UI';
        }
        QLabel#spellBookUsage {
            color: #555b5f;
            font: 700 8pt 'Segoe UI';
        }
        QLabel#spellBookAtWillOption {
            min-height: 21px;
            padding: 4px 9px;
            background: #e8eaeb;
            color: #555b5f;
            border: 1px solid #9ca1a4;
            border-radius: 1px;
            font: 700 8pt 'Segoe UI';
        }
        QScrollArea#martialBookScroll, QWidget#martialBookPage,
        QScrollArea#inventoryOrganizerScroll, QWidget#inventoryOrganizerCanvas {
            background: #f7f7f4;
            border: none;
        }
        QFrame#martialBookSection, QFrame#inventoryOrganizerCategory,
        QFrame#inventoryOrganizerContainer {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
            border-radius: 3px;
        }
        QLabel#martialBookSectionTitle, QLabel#inventoryOrganizerCategoryTitle {
            min-height: 22px;
            padding: 2px 7px;
            background: #62686c;
            color: white;
            font: 700 9pt 'Segoe UI';
        }
        QFrame#martialBookEntry {
            min-height: 76px;
            background: #f0f1f0;
            border: 1px solid #c7cbcd;
            border-radius: 3px;
        }
        QFrame#martialBookEntry[available="false"] {
            background: #e8eaeb;
            border-color: #d1d4d5;
        }
        QLabel#martialBookEntryName {
            color: #202427;
            font: 700 10pt 'Segoe UI';
        }
        QLabel#martialFocusRequirement {
            color: #8d3733;
            font: 700 8pt 'Segoe UI';
        }
        QLabel#inventoryOrganizerSubcategory {
            padding: 3px 5px;
            color: #444a4e;
            border-bottom: 1px solid #a9aeb1;
            font: 700 8pt 'Segoe UI';
        }
        QLabel#inventoryOrganizerContainerCategory {
            padding: 4px 6px 2px 6px;
            color: #444a4e;
            border-top: 2px solid #a9aeb1;
            font: 700 8pt 'Segoe UI';
        }
        QListWidget#inventoryOrganizerList {
            background: #f0f1f0;
            color: #202427;
            border: 1px solid #c7cbcd;
        }
        QListWidget#inventoryOrganizerList::item {
            padding: 5px 7px;
            border-bottom: 1px solid #c7cbcd;
        }
        QListWidget#inventoryOrganizerList::item:selected {
            background: #62686c;
            color: white;
        }
        QFrame#imbueCard {
            background: #eef0ef;
            border: 2px solid #858b8e;
            border-radius: 3px;
        }
        QComboBox#imbueSelector { font-weight: 700; }
        QTextBrowser#codexBrowser {
            background: #fbfbf8;
            border: 1px solid #b8bdc0;
            padding: 12px;
        }
        QLabel#statCode { color: #444a4e; font: 700 9pt 'Segoe UI'; }
        QLabel#statTotal { color: #202427; font: 700 20pt 'Georgia'; }
        QLabel#miniStatTotal { color: #252a2d; font: 700 15pt 'Georgia'; }
        QLabel#statModifier { color: #555b5f; font: 700 9pt 'Segoe UI'; }
        QLabel#resourceTotal { color: #2f3538; font: 700 28pt 'Georgia'; }
        QLabel#resourceTotalSmall { color: #353a3d; font: 700 13pt 'Georgia'; }
        QLabel#recordName {
            min-height: 28px;
            padding: 0 6px;
            color: #292e31;
            border-bottom: 2px solid #7a8083;
            font: 700 16pt 'Georgia';
        }
        QLabel#focusReady {
            min-height: 30px;
            background: #637a68;
            color: white;
            border: 2px solid #46584a;
            font: 700 11pt 'Segoe UI';
        }
        QLabel#focusSpent {
            min-height: 30px;
            background: #96615c;
            color: white;
            border: 2px solid #704641;
            font: 700 11pt 'Segoe UI';
        }
        QLabel#focusCounter {
            color: #2f3538;
            font: 700 15pt 'Georgia';
        }
        QLabel#focusPips {
            color: #62686c;
            font: 700 11pt 'Segoe UI';
            letter-spacing: 1px;
        }
        QFrame#movementCard {
            min-height: 74px;
            background: #f0f1f0;
            border: 1px solid #c1c5c7;
            border-radius: 3px;
        }
        QProgressBar#healthBar {
            min-height: 58px;
            background: #d4d7d8;
            color: #202427;
            border: 2px solid #62686c;
            border-radius: 7px;
            text-align: center;
            font: 700 16pt 'Segoe UI';
        }
        QProgressBar#healthBar::chunk {
            border-radius: 4px;
            background: #4f8f5b;
        }
        QProgressBar#healthBar[healthState="warning"]::chunk {
            background: #c89b2c;
        }
        QProgressBar#healthBar[healthState="critical"]::chunk {
            background: #b6423d;
        }
        QProgressBar#healthBar[healthState="empty"]::chunk {
            background: transparent;
        }
        QFrame#initiativeCard {
            min-height: 58px;
            background: #f0f1f0;
            border: 1px solid #c1c5c7;
            border-radius: 4px;
        }
        QLabel#initiativeTotal {
            background: #fbfbf8;
            color: #202427;
            border: 2px solid #62686c;
            border-radius: 7px;
            font: 700 18pt 'Georgia';
        }
        QLabel#movementMode {
            color: #555b5f;
            font: 700 8pt 'Segoe UI';
        }
        QLabel#movementTotal {
            min-height: 34px;
            color: #202427;
            font: 700 18pt 'Georgia';
        }
        QSpinBox#hpAdjustmentAmount {
            min-height: 30px;
            font: 700 13pt 'Georgia';
        }
        QSpinBox[primaryHpField="true"],
        QLineEdit[primaryHpField="true"],
        QLabel[primaryHpField="true"] {
            font: 700 18pt 'Georgia';
        }
        QPushButton#damageButton {
            min-width: 82px;
            background: #a94842;
            border-color: #78312d;
            color: white;
            font-weight: 700;
        }
        QPushButton#damageButton:hover { background: #bc5750; }
        QPushButton#healButton {
            min-width: 72px;
            background: #4f8f5b;
            border-color: #35623e;
            color: white;
            font-weight: 700;
        }
        QPushButton#healButton:hover { background: #61a36d; }
        QLabel#movementSource {
            color: #777d80;
            font: 600 7pt 'Segoe UI';
        }
        QFrame#movementEditorPanel {
            background: #eef0f0;
            border: 1px solid #b8bdc0;
            border-radius: 3px;
        }
        QLabel#loadLight, QLabel#loadMedium, QLabel#loadHeavy, QLabel#loadOverloaded {
            min-height: 28px;
            color: white;
            font-weight: 700;
        }
        QLabel#loadLight { background: #637a68; }
        QLabel#loadMedium { background: #9b854d; }
        QLabel#loadHeavy { background: #a76d43; }
        QLabel#loadOverloaded { background: #9a4f4b; }
        QFrame#sequenceTracker {
            background: #eef0ef;
            border: 2px solid #858b8e;
        }
        QLabel#sequenceCounter {
            min-width: 105px;
            color: #353b3e;
            font: 700 20pt 'Georgia';
        }
        QLabel#sequenceActive {
            min-width: 150px;
            min-height: 28px;
            background: #637a68;
            color: white;
            border: 2px solid #46584a;
            font-weight: 700;
        }
        QLabel#sequenceInactive {
            min-width: 150px;
            min-height: 28px;
            background: #7a8083;
            color: white;
            border: 2px solid #5c6265;
            font-weight: 700;
        }
        QWidget#sequenceOptionPanel {
            background: #f0f1f0;
            border: 1px solid #b8bdc0;
        }
        QWidget#catalogDetails {
            background: #f6f6f3;
            border: 1px solid #b8bdc0;
        }
        QFrame#catalogSelectionBasket {
            background: #f6f6f3;
            border: 2px solid #9ca1a4;
        }
        QListWidget#catalogSelectionQueue {
            background: #fbfbf8;
            color: #25292c;
            border: 1px solid #b8bdc0;
        }
        QListWidget#catalogSelectionQueue::item {
            padding: 7px;
            border-bottom: 1px solid #d1d4d5;
        }
        QListWidget#catalogSelectionQueue::item:hover {
            background: #eef0f0;
        }
        QListWidget#catalogSelectionQueue::item:selected {
            background: #62686c;
            color: white;
        }
        QLabel#catalogTalentTitle {
            color: #3c4245;
            font: 700 16pt 'Georgia';
        }
        QListWidget#catalogSphereList {
            background: #3e4347;
            color: white;
            border: 1px solid #62686c;
        }
        QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QPlainTextEdit {
            min-height: 20px;
            padding: 2px 5px;
            border: 1px solid #a9aeb1;
            border-bottom: 2px solid #777d80;
            border-radius: 0;
            background: #ffffff;
            selection-background-color: #70777b;
        }
        QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #4f565a; }
        QSpinBox:disabled, QLineEdit:disabled { background: #e3e5e5; color: #747a7d; }
        QSpinBox, QDoubleSpinBox { padding-right: 25px; }
        QSpinBox#baseAbilityInput { padding-right: 5px; }
        QSpinBox#baseAbilityInput::up-button,
        QSpinBox#baseAbilityInput::down-button {
            width: 0;
            min-width: 0;
            border: none;
            background: transparent;
        }
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 22px;
            min-height: 12px;
            background: #e1e3e3;
            border: none;
            border-left: 1px solid #a9aeb1;
            border-bottom: 1px solid #b9bdc0;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 22px;
            min-height: 12px;
            background: #e1e3e3;
            border: none;
            border-left: 1px solid #a9aeb1;
            border-top: 1px solid #b9bdc0;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
            background: #c8ccce;
        }
        QCheckBox::indicator { width: 14px; height: 14px; }
        QTableWidget {
            background: #fbfbf9;
            alternate-background-color: #eef0f0;
            gridline-color: #c5c9cb;
            border: 1px solid #b5babd;
            selection-background-color: #cbdde8;
            selection-color: #202427;
        }
        QTableWidget::item { padding: 2px 4px; }
        QTableWidget#recordTable, QTableWidget#skillRecordTable,
        QTableWidget#sequenceTable, QTableWidget#classRecordTable {
            background: #f7f7f4;
            alternate-background-color: #e8eaeb;
            gridline-color: transparent;
            border: 1px solid #aeb3b6;
            border-radius: 3px;
        }
        QTableWidget#recordTable::item, QTableWidget#skillRecordTable::item,
        QTableWidget#sequenceTable::item, QTableWidget#classRecordTable::item {
            padding: 5px 7px;
            border-bottom: 1px solid #d1d4d5;
        }
        QTableWidget#skillRecordTable::item:selected,
        QTableWidget#sequenceTable::item:selected,
        QTableWidget#recordTable::item:selected {
            background: #cbdde8;
            color: #202427;
        }
        QHeaderView::section {
            min-height: 24px;
            padding: 2px 4px;
            background: #686e72;
            color: white;
            border: none;
            border-right: 1px solid #8d9396;
            border-bottom: 1px solid #4d5356;
            font-weight: 700;
        }
        QScrollBar:vertical { background: #d9dcdd; width: 13px; margin: 0; }
        QScrollBar::handle:vertical { background: #9ba1a4; min-height: 28px; border: 2px solid #d9dcdd; }
        QScrollBar:horizontal { background: #d9dcdd; height: 13px; margin: 0; }
        QScrollBar::handle:horizontal { background: #9ba1a4; min-width: 28px; border: 2px solid #d9dcdd; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
        QFrame#abilityRow {
            background: #f0f1f0;
            border: none;
            border-bottom: 1px solid #c1c5c7;
        }
        QLabel#abilityCode {
            min-width: 54px;
            color: white;
            background: #62686c;
            padding: 4px 2px;
            font: 700 12pt 'Georgia';
        }
        QLabel#abilityName { color: #555b5f; font: 600 8pt 'Segoe UI'; }
        QLabel#abilityModifierBubble {
            min-width: 34px; min-height: 34px; max-width: 34px; max-height: 34px;
            border: 2px solid #62686c;
            border-radius: 18px;
            background: #fbfbf8;
            color: #202427;
            font: 700 11pt 'Georgia';
        }
        QLabel#formulaText { color: #777d80; font: 600 8pt 'Segoe UI'; }
        QLabel#sheetSubTitle {
            min-height: 21px;
            padding: 2px 7px;
            background: #686e72;
            color: white;
            font: 700 10pt 'Georgia';
        }
        QFrame#formulaRow {
            background: #fbfbf8;
            border: none;
            border-bottom: 2px solid #a9aeb1;
        }
        QLabel#formulaName {
            color: #444a4e;
            font: 700 8pt 'Segoe UI';
        }
        QLabel#formulaTotal {
            min-height: 48px;
            background: #fbfbf8;
            border: 2px solid #62686c;
            border-radius: 7px;
            color: #202427;
            font: 700 18pt 'Georgia';
        }
        QLabel#prodigyClassSummary {
            min-height: 25px;
            padding: 3px 8px;
            background: #62686c;
            color: white;
            font: 700 10pt 'Segoe UI';
        }
        QFrame#compactAbilityRow {
            background: #f0f1f0;
            border: none;
            border-bottom: 1px solid #c1c5c7;
        }
        QLabel#compactAbilityModifier {
            min-width: 50px;
            min-height: 34px;
            border: 2px solid #62686c;
            border-radius: 18px;
            background: #fbfbf8;
            color: #202427;
            font: 700 12pt 'Georgia';
        }
        QLabel#compactAbilityScore {
            min-width: 62px;
            min-height: 34px;
            color: #202427;
            font: 700 17pt 'Georgia';
        }
        QLabel#sequenceEffect {
            min-width: 235px;
            color: #444a4e;
            font: 700 8pt 'Segoe UI';
        }
        QToolTip {
            padding: 9px;
            border: 2px solid #62686c;
            background: #fbfbf8;
            color: #202427;
            font: 10pt 'Segoe UI';
        }
        QLabel#baseBadge {
            background: #62686c; color: white; padding: 2px 6px;
            border-radius: 7px; font: 700 7pt 'Segoe UI';
        }
    """

    if theme == "classic":
        replacements = {
            "#e2e4e5": "#ddd2b4", "#24282b": "#241b13",
            "#f5f5f2": "#eee5cd", "#272b2e": "#2b2015",
            "#656b6f": "#9f4634", "#363b3f": "#63382d",
            "#858b8e": "#b78d4d", "#2c3033": "#4d2e27",
            "#f3f3ef": "#f4df91", "#4d5357": "#75483c",
            "#737a7e": "#9f4634", "#9ca1a4": "#b28f58",
            "#f2f2ef": "#eadfc3", "#25292c": "#2a2015",
            "#5d6367": "#9f4634", "#43484b": "#713123",
            "#d4d7d8": "#d5c8a6", "#f7f7f4": "#ddd2b4",
            "#fafaf7": "#e5d9bb", "#5f6569": "#8e3f30",
            "#fbfbf8": "#e3d8bc", "#b8bdc0": "#b69b69",
            "#62686c": "#9f4634", "#f0f1f0": "#ded2b3",
            "#c1c5c7": "#b79d6a", "#ffffff": "#f4ead1",
            "#a9aeb1": "#b19666", "#777d80": "#8b613d",
            "#686e72": "#9f4634", "#eef0f0": "#d6c9a9",
            "#e8eaeb": "#d7caa9", "#cbdde8": "#f0d69a",
            "#202427": "#241b13", "#d1d4d5": "#c3ad7b",
            "#b9bdc0": "#cbb98d", "#34393c": "#2b2015",
            "#dfe1e2": "#ede4cf", "#cdd0d2": "#d7caa9",
            "#aeb3b6": "#b69b69",
        }
    elif theme == "dark":
        replacements = {
            "#e2e4e5": "#17191b", "#24282b": "#e9ecee",
            "#f5f5f2": "#23272a", "#272b2e": "#edf0f1",
            "#656b6f": "#7d8790", "#363b3f": "#101214",
            "#858b8e": "#66717a", "#2c3033": "#191c1f",
            "#f3f3ef": "#eef1f2", "#4d5357": "#343a3f",
            "#737a7e": "#46535d", "#9ca1a4": "#59636a",
            "#f2f2ef": "#30353a", "#25292c": "#eef1f2",
            "#5d6367": "#526b7a", "#43484b": "#7892a1",
            "#d4d7d8": "#111315", "#f7f7f4": "#1b1e21",
            "#fafaf7": "#202428", "#5f6569": "#6f7c84",
            "#fbfbf8": "#202428", "#b8bdc0": "#454c51",
            "#62686c": "#465b68", "#f0f1f0": "#272c30",
            "#c1c5c7": "#475057", "#ffffff": "#15181a",
            "#a9aeb1": "#59636a", "#777d80": "#80909a",
            "#686e72": "#3c4f5a", "#eef0f0": "#24292d",
            "#e8eaeb": "#292f34", "#cbdde8": "#3f5867",
            "#202427": "#f2f4f5", "#d1d4d5": "#3d4449",
            "#353a3d": "#edf0f1", "#676e72": "#b7bec3",
            "#72787b": "#aeb6bc", "#444a4e": "#dfe4e7",
            "#555b5f": "#c6cdd1", "#e1e3e3": "#343a3f",
            "#b9bdc0": "#30363a", "#34393c": "#eef1f2",
            "#dfe1e2": "#41484d", "#cdd0d2": "#3a4247",
            "#aeb3b6": "#454c51",
            "#c8ccce": "#495159", "#e3e5e5": "#292e32",
            # Secondary surfaces and foregrounds are intentionally listed
            # explicitly. Leaving one of these light-theme colors untouched
            # can create pale text on a pale cell (or dark text on a dark
            # card) in less frequently opened dialogs and sheet modules.
            "#e7eaeb": "#262c30", "#e5ece7": "#243129",
            "#33553d": "#b5d8bd", "#9caf9f": "#54715b",
            "#eee5cd": "#3a3324", "#8b613d": "#d0aa73",
            "#f2dddd": "#3a2425", "#8d3733": "#f0a4a0",
            "#bd8581": "#7e4d4a", "#292e31": "#edf1f3",
            "#edf0f0": "#242a2e", "#d8dcdd": "#343b40",
            "#4a5054": "#cbd2d6", "#454b4e": "#d8dde0",
            "#eef0ef": "#242a2d", "#c7cbcd": "#465057",
            "#f6f6f3": "#1f2326", "#3c4245": "#dfe4e7",
            "#70777b": "#526b7a", "#b5babd": "#454c51",
            "#fbfbf9": "#202428", "#7a8083": "#87939b",
            "#2f3538": "#e8ecee", "#353b3e": "#edf1f3",
            "#252a2d": "#edf1f3", "#747a7d": "#aeb7bc",
            "#46584a": "#66816d", "#704641": "#855956",
            "#9b302c": "#ffaaa3", "#b42318": "#ffaaa3",
        }
    else:
        replacements = {}
    for old, new in replacements.items():
        style = style.replace(old, new)
    return style
