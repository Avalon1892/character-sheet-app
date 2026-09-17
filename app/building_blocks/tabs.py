from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QInputDialog, QTabWidget, QVBoxLayout, QWidget

from app.building_blocks.persistence import BuildingBlockRepository
from app.ui.components import sheet_page


class SheetTabManager(QObject):
    """Projects per-character tab records into the existing QTabWidget."""

    def __init__(self, sheet, presentation: BuildingBlockRepository) -> None:
        super().__init__(sheet)
        self.sheet = sheet
        self.presentation = presentation
        self.history = None
        self.character_id: int | None = None
        self.builtin_pages = {
            "crafting": sheet.crafting_scroll,
            "build": sheet.builder_scroll,
            "core": sheet.core_scroll,
            "inventory": sheet.inventory_scroll,
            "magic": sheet.magic_scroll,
            "companion": sheet.companion_scroll,
        }
        self.canvases = {
            "crafting": sheet.crafting_canvas,
            "build": sheet.builder_canvas,
            "core": sheet.core_canvas,
            "inventory": sheet.inventory_canvas,
            "magic": sheet.magic_canvas,
            "companion": sheet.companion_canvas,
        }
        self.custom_pages: dict[str, tuple[QWidget, QWidget, QVBoxLayout]] = {}
        self.sheet.page_tabs.setMovable(True)
        self._tab_bar = self.sheet.page_tabs.tabBar()
        self._tab_bar.installEventFilter(self)
        self._tab_bar.tabMoved.connect(self._tabs_moved)
        self.sheet.page_tabs.tabBarDoubleClicked.connect(self._rename_at)

    def set_history(self, history) -> None:
        self.history = history

    def eventFilter(self, watched, event) -> bool:
        # Keep this independent of ``sheet``: Qt can deliver a final event while
        # the tab widget is already being destroyed during application shutdown.
        if watched is not self._tab_bar or self.history is None:
            return False
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.history.begin("Reorder sheet tabs")
        elif (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            QTimer.singleShot(0, self.history.commit)
        return False

    def load_character(self, character_id: int) -> None:
        self.character_id = character_id
        self.reload()

    def reload(self) -> None:
        if self.character_id is None:
            return
        while self.sheet.page_tabs.count():
            self.sheet.page_tabs.removeTab(0)
        for key, (page, _canvas, _layout) in tuple(self.custom_pages.items()):
            page.deleteLater()
            self.custom_pages.pop(key, None)
            self.canvases.pop(key, None)
        tabs = self.presentation.list_tabs(self.character_id)
        for tab in tabs:
            if tab.key not in self.builtin_pages and tab.key not in self.custom_pages:
                scroll, canvas, layout = sheet_page("customSheetPage")
                scroll.setProperty("sheetTabKey", tab.key)
                canvas.setProperty("sheetTabKey", tab.key)
                self.custom_pages[tab.key] = (scroll, canvas, layout)
                self.canvases[tab.key] = canvas
        for target_index, tab in enumerate(tabs):
            page = self.builtin_pages.get(tab.key) or self.custom_pages[tab.key][0]
            name = self._display_name(tab.key, tab.name)
            self.sheet.page_tabs.addTab(page, name)
            self.sheet.page_tabs.setTabText(target_index, name)
            available = (
                self.sheet.is_sheet_tab_available(tab.key)
                if hasattr(self.sheet, "is_sheet_tab_available")
                else True
            )
            self.sheet.page_tabs.setTabVisible(
                target_index, tab.visible and available
            )

    def _display_name(self, key: str, saved_name: str) -> str:
        """Adapt untouched built-in names while preserving explicit user renames."""

        automatic_magic_names = {
            "3   MAGIC & SPHERES",
            "3   SPELLCASTING",
            "3   SPELLCASTING & SPHERES",
        }
        if key == "magic" and saved_name in automatic_magic_names:
            resolved = getattr(self.sheet, "default_sheet_tab_name", lambda _key: "")(
                key
            )
            return resolved or saved_name
        return saved_name

    def current_key(self) -> str:
        page = self.sheet.page_tabs.currentWidget()
        for key, builtin in self.builtin_pages.items():
            if page is builtin:
                return key
        for key, values in self.custom_pages.items():
            if page is values[0]:
                return key
        return "build"

    def add_tab(self, name: str = "New Page", source_key: str = "") -> str:
        if self.character_id is None:
            raise ValueError("Open a character first.")
        key = self.presentation.add_tab(self.character_id, name, source_key=source_key)
        self.reload()
        return key

    def rename(self, tab_key: str, name: str) -> None:
        if self.character_id is None:
            return
        self.presentation.rename_tab(self.character_id, tab_key, name)
        self.reload()

    def _rename_at(self, index: int) -> None:
        if index < 0 or self.character_id is None:
            return
        key = self._key_at(index)
        current = self.sheet.page_tabs.tabText(index)
        name, accepted = QInputDialog.getText(self.sheet, "Rename sheet tab", "Tab name", text=current)
        if accepted and name.strip():
            if self.history is None:
                self.rename(key, name)
            else:
                self.history.record(
                    "Rename sheet tab", lambda: self.rename(key, name)
                )

    def _key_at(self, index: int) -> str:
        page = self.sheet.page_tabs.widget(index)
        for key, value in self.builtin_pages.items():
            if page is value:
                return key
        for key, values in self.custom_pages.items():
            if page is values[0]:
                return key
        return ""

    def _tabs_moved(self, _from: int, _to: int) -> None:
        if self.character_id is None:
            return
        keys = [self._key_at(index) for index in range(self.sheet.page_tabs.count())]
        self.presentation.reorder_tabs(self.character_id, [key for key in keys if key])
