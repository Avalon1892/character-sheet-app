"""Refined-only palette and typography tokens. No application-global selectors."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Palette:
    page: str
    surface: str
    text: str
    muted: str
    line: str
    accent: str
    selection: str
    magic: str
    martial: str

PALETTES = {
    "classic": Palette("#EEE7D8", "#FAF7EF", "#302B27", "#5E574D", "#CEC3AF", "#7E493A", "#E4D5BF", "#DAE9F8", "#FBE2D5"),
    "dark": Palette("#171B22", "#242B35", "#F0F1F3", "#B5C0CF", "#3B4757", "#A8C3E0", "#344B63", "#23394B", "#40342F"),
}

def stylesheet(theme="classic", density="comfortable"):
    p = PALETTES.get(theme, PALETTES["classic"])
    pad = 4 if density == "compact" else 7
    # Applied on the Refined root only; descendants inherit these overrides.
    return f"""
    QWidget {{ background: transparent; color: {p.text}; font: 10pt 'Segoe UI'; }}
    QWidget#refinedSheet, QScrollArea, QWidget#refinedCanvas {{ background: {p.page}; }}
    QWidget#sheetSection, QFrame#refinedCard {{ background: {p.surface}; border: 1px solid {p.line}; border-radius: 7px; }}
    QLabel {{ border: none; background: transparent; }}
    QLabel#sectionTitle, QLabel#sheetSectionTitle, QLabel#refinedSectionTitle {{ color: {p.text}; background: transparent; font: 600 13pt 'Segoe UI'; padding: 3px 0; border: none; }}
    QLabel#sheetSubtitle {{ color: {p.muted}; background: transparent; font: 600 10pt 'Segoe UI'; }}
    QLabel#refinedCharacterName {{ font: 700 21pt 'Georgia'; }}
    QLabel#refinedNumber, QPushButton#refinedNumber {{ font: 700 20pt 'Georgia'; }}
    QLabel#refinedModifier {{ font: 600 13pt 'Segoe UI'; color: {p.accent}; padding: 2px; }}
    QLabel#refinedAbilityCode {{ font: 600 12pt 'Segoe UI'; color: {p.accent}; }}
    QLabel[refinedFocusState="true"] {{ border: 1px solid {p.line}; border-radius: 5px; padding: 4px 10px; font: 600 10pt 'Segoe UI'; }}
    QLabel#focusReady[refinedFocusState="true"] {{ background: {p.selection}; color: {p.text}; }}
    QLabel#focusSpent[refinedFocusState="true"] {{ background: {p.page}; color: {p.muted}; }}
    QProgressBar#healthBar {{ font: 700 20pt 'Georgia'; }}
    QFrame#movementCard {{ background: transparent; border: none; }}
    QFrame#refinedMetricGroup {{ background: {p.surface}; border: 1px solid {p.line}; border-top: 3px solid {p.accent}; border-radius: 7px; }}
    QFrame#refinedMetricGroup[magicMetric="true"] {{ background: {p.magic}; border-top-width: 1px; }}
    QLabel#refinedMetricHeading {{ font: 600 11pt 'Segoe UI'; color: {p.text}; padding: 0 2px; }}
    QFrame#refinedMetricCard {{ background: {p.page}; border: 1px solid {p.line}; border-radius: 6px; }}
    QFrame#refinedMetricCard:hover {{ background: {p.selection}; border-color: {p.accent}; }}
    QFrame#refinedMetricCard:focus {{ border: 2px solid {p.accent}; }}
    QLabel#refinedMetricLabel, QLabel#movementMode {{ font: 600 9pt 'Segoe UI'; color: {p.muted}; }}
    QLabel#refinedMetricValue {{ font: 700 24pt 'Georgia'; color: {p.text}; }}
    QLabel#refinedMetricValue[primaryMetric="true"] {{ font-size: 30pt; }}
    QLabel#refinedMetricValue[compactMetric="true"] {{ font-size: 17pt; }}
    QLabel#mutedText, QLabel#formulaText, QLabel#refinedMuted {{ font: 9pt 'Segoe UI'; color: {p.muted}; }}
    QLabel#refinedSearchFeedback {{ font: 9pt 'Segoe UI'; color: {p.muted}; }}
    QFrame#refinedStat {{ background: transparent; border: none; }}
    QPushButton, QToolButton {{ background: {p.surface}; border: 1px solid {p.line}; border-radius: 5px; padding: {pad}px 10px; min-height: 20px; }}
    QPushButton:hover, QToolButton:hover {{ background: {p.selection}; }}
    QPushButton:checked, QToolButton:checked {{ background: {p.selection}; border-color: {p.accent}; color: {p.text}; }}
    QPushButton:focus, QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus {{ border: 2px solid {p.accent}; }}
    QPushButton#primaryButton {{ background: {p.selection}; color: {p.text}; font-weight: 600; }}
    QPushButton#refinedDisclosure {{ color: {p.accent}; background: {p.page}; border: none; font-weight: 600; }}
    QPushButton#dangerButton {{ color: {'#FFB2A7' if theme=='dark' else '#9E302B'}; }}
    QPushButton#damageButton {{ background: #9F4540; color: white; border: none; }}
    QPushButton#healButton {{ background: #36764E; color: white; border: none; }}
    QPushButton:disabled, QToolButton:disabled {{ color: {p.muted}; background: {p.page}; }}
    QLineEdit, QAbstractSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{ background: {p.surface}; border: 1px solid {p.line}; border-radius: 4px; padding: {pad}px; min-height: 22px; selection-background-color: {p.selection}; }}
    QAbstractSpinBox:disabled {{ color: {p.muted}; background: {p.page}; }}
    QTableWidget {{ background: {p.surface}; alternate-background-color: {p.page}; border: none; gridline-color: {p.line}; selection-background-color: {p.selection}; selection-color: {p.text}; }}
    QTableWidget::item {{ padding: {pad}px 5px; border-bottom: 1px solid {p.line}; }}
    QTableWidget::item:selected, QTableWidget::item:selected:!active {{ background: {p.selection}; color: {p.text}; }}
    QTableWidget[refinedCategory]::item:selected {{ background: {p.selection}; color: {p.text}; }}
    QHeaderView::section {{ background: {p.page}; color: {p.muted}; border: none; border-bottom: 1px solid {p.line}; padding: {pad}px 5px; font: 600 9pt 'Segoe UI'; }}
    QTextBrowser {{ background: {p.surface}; color: {p.text}; border: none; padding: 8px; font: 11pt 'Segoe UI'; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {p.muted}; border: none; border-bottom: 3px solid transparent; padding: 10px 18px; min-width: 0px; font: 600 10pt 'Segoe UI'; }}
    QTabBar::tab:selected {{ color: {p.text}; background: {p.surface}; border-bottom: 3px solid {p.accent}; }}
    QSplitter::handle {{ background: {p.line}; }}
    QMenu {{ background: {p.surface}; border: 1px solid {p.line}; }}
    QMenu::item:selected {{ background: {p.selection}; }}
    QComboBox QAbstractItemView {{ background: {p.surface}; color: {p.text}; selection-background-color: {p.selection}; selection-color: {p.text}; outline: none; }}
    QScrollBar:vertical {{ background: {p.page}; width: 12px; border: none; margin: 0px; }}
    QScrollBar::handle:vertical {{ background: {p.line}; border-radius: 5px; min-height: 32px; margin: 2px; }}
    QScrollBar::handle:vertical:hover {{ background: {p.muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QToolTip {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.line}; padding: 8px; }}
    """
