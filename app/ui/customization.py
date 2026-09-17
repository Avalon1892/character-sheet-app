from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QColorDialog, QHeaderView, QMenu,
    QSizePolicy, QTableWidget, QWidget,
)

from app.ui.table_layout import TableLayoutController
from app.ui.content_scaling import SectionContentScaleController


class SheetCustomizationController(QObject):
    """Presentation-only customization for registered sheet Lego blocks."""

    def __init__(self, window, sheet, sections: dict[str, QWidget], layouts: dict[str, QBoxLayout], *, settings=None):
        super().__init__(window)
        self.window = window
        self.sheet = sheet
        self.sections = sections
        self.layouts = layouts
        self.settings = settings if settings is not None else QSettings("Georg", "Character Sheet App")
        self.build_mode = False
        self.paint_color: QColor | None = None
        self.drag_source: QWidget | None = None
        self.drag_origin = QPoint()
        self.start_geometry = QRect()
        self.drag_operation = "move"
        self.section_canvases: dict[QWidget, QWidget] = {}
        self.canvases = {
            "build": sheet.builder_canvas,
            "core": sheet.core_canvas,
            "inventory": sheet.inventory_canvas,
            "magic": sheet.magic_canvas,
        }
        self.canvas_minimums = {
            canvas: canvas.minimumSize() for canvas in self.canvases.values()
        }
        for key, widget in sections.items():
            widget.setProperty("customizationId", key)
            self.section_canvases[widget] = self._ancestor_canvas(widget)
        self.default_placements = {}
        for widget in sections.values():
            placement = self._find_layout(widget)
            if placement is not None:
                self.default_placements[widget] = (
                    placement[1], placement[2], widget.minimumSize(), widget.maximumSize()
                )
        self.table_layout = TableLayoutController(self.settings, self)
        self.content_scale = SectionContentScaleController(
            self.settings, self.sections, self
        )
        self.nested_editor = None
        self.geometry_saved_callback = None
        self.history = None
        self._register_tables()
        application = QApplication.instance()
        self._event_filter_application = application
        if application is not None:
            application.installEventFilter(self)
        sheet.page_tabs.currentChanged.connect(self._page_changed)
        self._restore_styles_and_sizes()
        self._restore_freeform()

    def dispose(self) -> None:
        """Release the global editing hook when its owning window closes."""

        self.table_layout.dispose()
        if self.nested_editor is not None:
            self.nested_editor.set_enabled(False)
        application = self._event_filter_application
        if application is not None:
            application.removeEventFilter(self)
            self._event_filter_application = None

    def set_build_mode(self, enabled: bool) -> None:
        self.build_mode = enabled
        self.table_layout.set_editing(enabled)
        if enabled:
            self._activate_current_page()
        self.window.statusBar().showMessage(
            "Build Mode: drag boxes freely; resize at their edges. Drag table headers "
            "to reorder/resize columns, or right-click a header to add or remove one."
            if enabled else "Build Mode disabled",
            6000,
        )

    def sync_sections(self) -> None:
        """Register runtime Lego blocks without rebuilding the page controller."""
        live = set(self.sections.values())
        for widget in tuple(self.section_canvases):
            if widget not in live:
                self.section_canvases.pop(widget, None)
        for key, widget in self.sections.items():
            widget.setProperty("customizationId", key)
            if widget not in self.section_canvases:
                self.section_canvases[widget] = self._ancestor_canvas(widget)
                self._prepare_resizable_section(widget)
        self._restore_styles_and_sizes()
        self._restore_freeform()
        QTimer.singleShot(
            0,
            self._activate_current_page
            if self.build_mode
            else self.refresh_canvas_sizes,
        )

    def set_canvases(self, canvases: dict[str, QWidget]) -> None:
        """Accept runtime-created sheet tabs without changing Build Mode logic."""
        self.canvases = dict(canvases)
        for canvas in self.canvases.values():
            self.canvas_minimums.setdefault(canvas, canvas.minimumSize())
        for widget in self.sections.values():
            self.section_canvases[widget] = self._ancestor_canvas(widget)

    def set_content_scale_mode(self, enabled: bool) -> None:
        self.content_scale.set_enabled(enabled)
        self.window.statusBar().showMessage(
            "Proportional resize enabled: resizing a box also scales its text, fields, rows, and controls."
            if enabled
            else "Layout resize enabled: box contents keep their current size.",
            6000,
        )

    def set_nested_editor(self, editor) -> None:
        self.nested_editor = editor

    def set_history(self, history) -> None:
        self.history = history
        self.table_layout.set_history(history)

    def set_geometry_saved_callback(self, callback) -> None:
        self.geometry_saved_callback = callback

    def place_section_freeform(
        self, widget: QWidget, canvas: QWidget, geometry: QRect
    ) -> None:
        current = self._find_layout(widget)
        if current is not None:
            current[1].removeWidget(widget)
        widget.setParent(canvas)
        widget.setProperty("freeformManaged", True)
        self._prepare_resizable_section(widget)
        widget.setGeometry(self._bounded_geometry(canvas, geometry))
        self._apply_effective_visibility(widget)
        self.section_canvases[widget] = canvas
        self._fit_canvas(canvas)

    def set_cell_edit_mode(self, enabled: bool) -> None:
        if self.nested_editor is not None:
            self.nested_editor.set_enabled(enabled)
        self.window.statusBar().showMessage(
            "Cell editing enabled: drag or resize cells; Ctrl-click selects multiple; right-click for grouping, anchoring, moving, and removal."
            if enabled else "Cell editing disabled: Build Mode controls whole boxes.",
            7000,
        )

    @staticmethod
    def _section_may_show(widget: QWidget) -> bool:
        return (
            widget.property("ruleAvailable") is not False
            and widget.property("blockInstanceVisible") is not False
        )

    def _apply_effective_visibility(self, widget: QWidget) -> None:
        widget.setVisible(self._section_may_show(widget))

    def choose_paint_color(self) -> None:
        color = QColorDialog.getColor(parent=self.window, title="Choose sheet block color")
        if color.isValid():
            self.paint_color = color
            self.window.statusBar().showMessage(
                "Color mode: click any sheet box to apply the selected color.", 6000
            )

    def stop_painting(self) -> None:
        self.paint_color = None

    def clear_colors(self) -> None:
        def operation() -> None:
            for key, widget in self.sections.items():
                widget.setStyleSheet("")
                self.settings.remove(f"customization/colors/{key}")
        if self.history is None:
            operation()
        else:
            self.history.record("Clear custom colors", operation)

    def eventFilter(self, watched, event) -> bool:
        # Play-mode paint/layout events need no editing hit tests. This filter
        # is application-wide, including other sheet styles and open dialogs.
        if (not self.build_mode and self.paint_color is None
                and not (self.nested_editor is not None and self.nested_editor.enabled)):
            return False
        if (
            self.nested_editor is not None
            and isinstance(watched, QWidget)
            and self.nested_editor.popup_owns_input(watched)
        ):
            return False
        if self.nested_editor is not None and self.nested_editor.handle(watched, event):
            return True
        if not isinstance(watched, QWidget):
            return False
        section = self._section_for(watched)
        if section is None:
            return False
        if self.paint_color is not None and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                if self.history is None:
                    self._paint(section, self.paint_color)
                else:
                    self.history.record(
                        "Color sheet box",
                        lambda: self._paint(section, self.paint_color),
                    )
                return True
        if not self.build_mode:
            return False
        if self._inside_table_header(watched):
            return False
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self.history is not None:
                self.history.begin("Move or resize sheet box")
            self.drag_source = section
            self.drag_origin = event.globalPosition().toPoint()
            self.start_geometry = section.geometry()
            local = section.mapFromGlobal(self.drag_origin)
            edge = 16
            right = local.x() >= section.width() - edge
            bottom = local.y() >= section.height() - edge
            self.drag_operation = "resize_both" if right and bottom else "resize_width" if right else "resize_height" if bottom else "move"
            if (
                self.drag_operation != "move"
                and self.nested_editor is not None
            ):
                self.nested_editor.begin_parent_resize(section)
            if self.drag_operation != "move" and self.content_scale.enabled:
                self.content_scale.begin(self._key(section), self.start_geometry)
            section.raise_()
            return True
        if event.type() == QEvent.Type.MouseMove and self.drag_source is not None:
            delta = event.globalPosition().toPoint() - self.drag_origin
            geometry = QRect(self.start_geometry)
            if self.drag_operation == "move":
                geometry.moveTo(
                    max(0, self.start_geometry.x() + delta.x()),
                    max(0, self.start_geometry.y() + delta.y()),
                )
            else:
                if self.drag_operation in {"resize_width", "resize_both"}:
                    geometry.setWidth(max(160, self.start_geometry.width() + delta.x()))
                if self.drag_operation in {"resize_height", "resize_both"}:
                    geometry.setHeight(max(90, self.start_geometry.height() + delta.y()))
            geometry = self._bounded_geometry(
                self.section_canvases[self.drag_source], geometry
            )
            self.drag_source.setGeometry(geometry)
            if (
                self.drag_operation != "move"
                and self.nested_editor is not None
            ):
                self.nested_editor.preview_parent_resize(self.drag_source)
            if self.drag_operation != "move" and self.content_scale.enabled:
                self.content_scale.preview(geometry)
            self._fit_canvas(self.section_canvases[self.drag_source])
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self.drag_source is not None:
            source = self.drag_source
            self.drag_source = None
            self.content_scale.finish()
            self._save_geometry(source)
            if self.nested_editor is not None:
                self.nested_editor.finish_parent_resize()
            if self.history is not None:
                self.history.commit()
            return True
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
            and self.drag_source is not None
        ):
            self.drag_source.setGeometry(self.start_geometry)
            self.drag_source = None
            self.content_scale.finish()
            if self.nested_editor is not None:
                self.nested_editor.cancel_parent_resize()
            if self.history is not None:
                self.history.cancel()
            return True
        return False

    def reset_layout(self) -> None:
        self.settings.remove("customization/freeform")
        self.settings.remove("customization/layout")
        self.table_layout.reset()
        self.content_scale.reset()
        self.window.statusBar().showMessage(
            "Default layout will be restored when the application is reopened.", 6000
        )

    def capture_state(self) -> dict[str, str]:
        """Return a portable presentation snapshot for one character."""
        self.table_layout.flush()
        return {
            key.removeprefix("customization/"): str(self.settings.value(key, "") or "")
            for key in self.settings.allKeys()
            if key.startswith("customization/")
        }

    def apply_state(self, state: dict[str, str]) -> None:
        """Apply a character's saved presentation without touching rules state."""
        self.paint_color = None
        self.restore_factory_layout()
        for key, value in state.items():
            self.settings.setValue(f"customization/{key}", str(value))
        for widget in self.sections.values():
            if widget.styleSheet():
                widget.setStyleSheet("")
        self._restore_styles_and_sizes()
        self._restore_freeform()
        self.table_layout.reload()
        self.content_scale.reload()
        for canvas in self.canvases.values():
            self._fit_canvas(canvas)

    def restore_factory_layout(self) -> None:
        """Return registered built-ins to their code-defined layout before applying a character snapshot."""
        self.settings.remove("customization")
        placements = [
            (layout, index, widget, minimum, maximum)
            for widget, (layout, index, minimum, maximum) in self.default_placements.items()
        ]
        for _layout, _index, widget, _minimum, _maximum in placements:
            current = self._find_layout(widget)
            if current is not None:
                current[1].removeWidget(widget)
        for layout, index, widget, minimum, maximum in sorted(
            placements, key=lambda item: item[1]
        ):
            widget.setParent(layout.parentWidget())
            widget.setProperty("freeformManaged", False)
            widget.setMinimumSize(minimum)
            widget.setMaximumSize(maximum)
            if widget.styleSheet():
                widget.setStyleSheet("")
            layout.insertWidget(min(index, layout.count()), widget)
            self._apply_effective_visibility(widget)
            self.section_canvases[widget] = self._ancestor_canvas(widget)

    def _ancestor_canvas(self, widget: QWidget) -> QWidget:
        current = widget.parentWidget()
        while current is not None:
            if current in self.canvases.values():
                return current
            current = current.parentWidget()
        return self.sheet.core_canvas

    def _page_changed(self, _index: int) -> None:
        if self.build_mode:
            QTimer.singleShot(0, self._activate_current_page)
        else:
            # Hidden tabs can receive several visibility and size changes while
            # another page is active. Force one responsive layout pass when the
            # page becomes visible so stale child geometries cannot overlap.
            QTimer.singleShot(0, self.refresh_canvas_sizes)

    def _current_canvas(self) -> QWidget:
        page = self.sheet.page_tabs.currentWidget()
        for canvas in self.canvases.values():
            current = canvas
            while current is not None:
                if current is page:
                    return canvas
                current = current.parentWidget()
        return self.sheet.core_canvas

    def _activate_current_page(self) -> None:
        canvas = self._current_canvas()
        raw = str(self.settings.value("customization/freeform", "{}") or "{}")
        try:
            state = json.loads(raw)
        except (TypeError, ValueError):
            state = {}
        eligible = [
            widget
            for widget in self.sections.values()
            if self.section_canvases[widget] is canvas
            and self._key(widget) not in state
            and not widget.isHidden()
            and self._section_may_show(widget)
        ]
        snapshots = {
            widget: (QRect(widget.mapTo(canvas, QPoint(0, 0)), widget.size()), widget.isHidden())
            for widget in eligible
        }
        for widget in eligible:
            geometry, explicitly_hidden = snapshots[widget]
            current = self._find_layout(widget)
            if current is not None:
                current[1].removeWidget(widget)
            widget.setParent(canvas)
            widget.setProperty("freeformManaged", True)
            self._prepare_resizable_section(widget)
            widget.setMinimumSize(160, 90)
            widget.setMaximumSize(16777215, 16777215)
            widget.setGeometry(self._bounded_geometry(canvas, geometry))
            if not explicitly_hidden:
                self._apply_effective_visibility(widget)
            state[self._key(widget)] = self._geometry_value(widget, canvas)
        self.settings.setValue("customization/freeform", json.dumps(state))
        self._fit_canvas(canvas)

    def _geometry_value(self, widget: QWidget, canvas: QWidget) -> dict:
        page = next((key for key, value in self.canvases.items() if value is canvas), "core")
        geometry = widget.geometry()
        return {"page": page, "x": geometry.x(), "y": geometry.y(), "width": geometry.width(), "height": geometry.height()}

    def _save_geometry(self, widget: QWidget) -> None:
        raw = str(self.settings.value("customization/freeform", "{}") or "{}")
        try:
            state = json.loads(raw)
        except (TypeError, ValueError):
            state = {}
        state[self._key(widget)] = self._geometry_value(widget, self.section_canvases[widget])
        self.settings.setValue("customization/freeform", json.dumps(state))
        if self.geometry_saved_callback is not None and widget.property("blockInstanceId"):
            self.geometry_saved_callback(widget)

    def _restore_freeform(self) -> None:
        raw = str(self.settings.value("customization/freeform", "") or "")
        if not raw:
            return
        try:
            state = json.loads(raw)
        except (TypeError, ValueError):
            return
        # Older Build Mode detached every hidden page before Qt laid it out,
        # saving all of that page's boxes at (0, 0). Discard those invalid
        # page groups so they are captured correctly when first opened.
        by_page: dict[str, list[tuple[str, dict]]] = {}
        for key, value in state.items():
            by_page.setdefault(str(value.get("page", "")), []).append((key, value))
        invalid_pages = {
            page
            for page, entries in by_page.items()
            if len(entries) > 1
            and sum(int(value.get("x", 0)) == 0 and int(value.get("y", 0)) == 0 for _key, value in entries) > 1
        }
        if invalid_pages:
            state = {
                key: value
                for key, value in state.items()
                if str(value.get("page", "")) not in invalid_pages
            }
            self.settings.setValue("customization/freeform", json.dumps(state))
        for key, value in state.items():
            widget = self.sections.get(key)
            canvas = self.canvases.get(str(value.get("page", "")))
            if widget is None or canvas is None:
                continue
            explicitly_hidden = widget.isHidden()
            current = self._find_layout(widget)
            if current is not None:
                current[1].removeWidget(widget)
            widget.setParent(canvas)
            widget.setProperty("freeformManaged", True)
            self._prepare_resizable_section(widget)
            widget.setMinimumSize(160, 90)
            widget.setMaximumSize(16777215, 16777215)
            requested_width = int(value.get("width", widget.width()))
            requested_height = int(value.get("height", widget.height()))
            geometry = QRect(
                int(value.get("x", 0)),
                int(value.get("y", 0)),
                max(
                    160,
                    requested_width
                    if requested_width > 0
                    else widget.sizeHint().width(),
                ),
                max(
                    90,
                    requested_height
                    if requested_height > 0
                    else widget.sizeHint().height(),
                ),
            )
            widget.setGeometry(self._bounded_geometry(canvas, geometry))
            if not explicitly_hidden:
                self._apply_effective_visibility(widget)
            elif not self._section_may_show(widget):
                widget.hide()
            self.section_canvases[widget] = canvas
        for canvas in self.canvases.values():
            self._fit_canvas(canvas)

    def _fit_canvas(self, canvas: QWidget) -> None:
        layout = canvas.layout()
        if layout is not None:
            self._invalidate_layout_tree(layout)
            layout.activate()
        boxes = [
            QRect(widget.mapTo(canvas, QPoint(0, 0)), widget.size())
            for widget, owner in self.section_canvases.items()
            if owner is canvas
            and not widget.isHidden()
            and bool(widget.property("freeformManaged"))
        ]
        baseline = self.canvas_minimums.get(canvas, canvas.minimumSize())
        width = baseline.width()
        height = max(
            baseline.height(),
            layout.minimumSize().height() if layout is not None else 0,
        )
        # The sheet is vertically scrollable by design. Freeform boxes are
        # constrained to the page width, so Build Mode must never manufacture
        # a second horizontal document area around them.
        if boxes:
            height = max(height, max(box.bottom() for box in boxes) + 24)
        canvas.setMinimumSize(width, height)
        canvas.updateGeometry()

    @classmethod
    def _invalidate_layout_tree(cls, layout) -> None:
        """Invalidate nested responsive layouts without moving freeform blocks."""

        for index in range(layout.count()):
            item = layout.itemAt(index)
            child_layout = item.layout()
            if child_layout is not None:
                cls._invalidate_layout_tree(child_layout)
            child = item.widget()
            if child is not None and child.layout() is not None:
                cls._invalidate_layout_tree(child.layout())
        layout.invalidate()

    def _bounded_geometry(self, canvas: QWidget, geometry: QRect) -> QRect:
        baseline = self.canvas_minimums.get(canvas, canvas.minimumSize())
        page_width = max(160, canvas.width(), baseline.width())
        width = min(max(160, geometry.width()), page_width)
        x = min(max(0, geometry.x()), max(0, page_width - width))
        return QRect(x, max(0, geometry.y()), width, max(90, geometry.height()))

    def refresh_canvas_sizes(self) -> None:
        """Recompute every tab after layouts and runtime blocks finish loading."""
        for canvas in self.canvases.values():
            self._fit_canvas(canvas)

    def _register_tables(self) -> None:
        registered: set[QTableWidget] = set()
        for attribute, value in vars(self.sheet).items():
            candidates = (
                [(attribute, value)]
                if isinstance(value, QTableWidget)
                else [
                    (f"{attribute}.{key}", table)
                    for key, table in value.items()
                    if isinstance(table, QTableWidget)
                ]
                if isinstance(value, dict)
                else []
            )
            for table_name, table in candidates:
                if table in registered:
                    continue
                section = self._section_for(table)
                if section is None:
                    continue
                registered.add(table)
                self.table_layout.register(
                    f"{self._key(section)}/{table_name}", table
                )

    @staticmethod
    def _inside_table_header(widget: QWidget) -> bool:
        current: QWidget | None = widget
        while current is not None:
            if isinstance(current, QHeaderView):
                return True
            current = current.parentWidget()
        return False

    @staticmethod
    def _prepare_resizable_section(section: QWidget) -> None:
        for table in section.findChildren(QTableWidget):
            table.setProperty("fillAvailableHeight", True)
            table.setMinimumHeight(44)
            table.setMaximumHeight(16777215)
            table.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )

    def _section_for(self, widget: QWidget | None) -> QWidget | None:
        while widget is not None:
            if widget in self.sections.values():
                return widget
            widget = widget.parentWidget()
        return None

    def _key(self, widget: QWidget) -> str:
        return str(widget.property("customizationId") or "")

    def _paint(self, widget: QWidget, color: QColor) -> None:
        value = color.name(QColor.NameFormat.HexRgb)
        widget.setStyleSheet(f"QWidget[customizationId='{self._key(widget)}'] {{ background-color: {value}; }}")
        self.settings.setValue(f"customization/colors/{self._key(widget)}", value)

    def _resize_menu(self, widget: QWidget, position) -> None:
        menu = QMenu(self.window)
        menu.addAction("Wider", lambda: self._resize(widget, 100, 0))
        menu.addAction("Narrower", lambda: self._resize(widget, -100, 0))
        menu.addSeparator()
        menu.addAction("Taller", lambda: self._resize(widget, 0, 100))
        menu.addAction("Shorter", lambda: self._resize(widget, 0, -100))
        menu.addSeparator()
        menu.addAction("Reset automatic size", lambda: self._reset_size(widget))
        menu.exec(position)

    def _resize(self, widget: QWidget, width_delta: int, height_delta: int) -> None:
        width = max(160, widget.width() + width_delta) if width_delta else widget.maximumWidth()
        height = max(90, widget.height() + height_delta) if height_delta else widget.maximumHeight()
        if width_delta:
            widget.setFixedWidth(width)
        if height_delta:
            widget.setFixedHeight(height)
        self._save_size(widget)

    def _reset_size(self, widget: QWidget) -> None:
        widget.setMinimumSize(0, 0)
        widget.setMaximumSize(16777215, 16777215)
        self.settings.remove(f"customization/sizes/{self._key(widget)}")

    def _save_size(self, widget: QWidget) -> None:
        value = {
            "width": widget.width() if widget.minimumWidth() == widget.maximumWidth() else 0,
            "height": widget.height() if widget.minimumHeight() == widget.maximumHeight() else 0,
        }
        self.settings.setValue(f"customization/sizes/{self._key(widget)}", json.dumps(value))

    def _find_layout(self, widget: QWidget):
        for key, layout in self.layouts.items():
            index = layout.indexOf(widget)
            if index >= 0:
                return key, layout, index
        return None

    def _swap(self, source: QWidget, target: QWidget) -> None:
        source_place = self._find_layout(source)
        target_place = self._find_layout(target)
        if source_place is None or target_place is None:
            return
        source_key, source_layout, source_index = source_place
        target_key, target_layout, target_index = target_place
        source_layout.removeWidget(source)
        target_layout.removeWidget(target)
        if source_layout is target_layout:
            first, second = sorted((source_index, target_index))
            first_widget = target if source_index == first else source
            second_widget = source if source_index == first else target
            source_layout.insertWidget(first, first_widget)
            source_layout.insertWidget(second, second_widget)
        else:
            source_layout.insertWidget(source_index, target)
            target_layout.insertWidget(target_index, source)
        self._save_layout()

    def _save_layout(self) -> None:
        state = {}
        for layout_key, layout in self.layouts.items():
            state[layout_key] = [
                {"section": self._key(layout.itemAt(index).widget()), "index": index}
                for index in range(layout.count())
                if layout.itemAt(index).widget() in self.sections.values()
            ]
        self.settings.setValue("customization/layout", json.dumps(state))

    def _restore_layout(self) -> None:
        raw = str(self.settings.value("customization/layout", "") or "")
        if not raw:
            return
        try:
            state = json.loads(raw)
        except (TypeError, ValueError):
            return
        placements = []
        for layout_key, entries in state.items():
            layout = self.layouts.get(layout_key)
            if layout is None:
                continue
            for entry in entries:
                if isinstance(entry, str):
                    entry = {"section": entry, "index": layout.count()}
                section_key = str(entry.get("section", ""))
                widget = self.sections.get(section_key)
                if widget is not None:
                    placements.append((layout, int(entry.get("index", layout.count())), widget))
        for _layout, _index, widget in placements:
            current = self._find_layout(widget)
            if current is not None:
                current[1].removeWidget(widget)
        for layout, index, widget in sorted(placements, key=lambda item: item[1]):
            layout.insertWidget(min(index, layout.count()), widget)

    def _restore_styles_and_sizes(self) -> None:
        for key, widget in self.sections.items():
            color = str(self.settings.value(f"customization/colors/{key}", "") or "")
            if QColor(color).isValid():
                self._paint(widget, QColor(color))
            raw = str(self.settings.value(f"customization/sizes/{key}", "") or "")
            if not raw:
                continue
            try:
                size = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if int(size.get("width", 0)):
                widget.setFixedWidth(int(size["width"]))
            if int(size.get("height", 0)):
                widget.setFixedHeight(int(size["height"]))
