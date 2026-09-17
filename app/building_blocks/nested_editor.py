from __future__ import annotations

import uuid
from dataclasses import replace

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFormLayout,
    QGridLayout,
    QLayout,
    QMenu,
    QRubberBand,
    QSizePolicy,
    QWidget,
)

from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.schemas import CellOverride


class _LayoutPlaceholder(QWidget):
    """Non-painting, shrinkable stand-in for a detached layout cell."""

    def __init__(self, preferred: QSize, source: QWidget, parent=None) -> None:
        super().__init__(parent)
        self._preferred = QSize(preferred)
        policy = source.sizePolicy()
        expanding = {
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        }
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding
            if policy.horizontalPolicy() in expanding
            else QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding
            if policy.verticalPolicy() in expanding
            else QSizePolicy.Policy.Preferred,
        )
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setObjectName("buildModeCellPlaceholder")

    def sizeHint(self) -> QSize:
        return QSize(self._preferred)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def paintEvent(self, _event) -> None:
        # Theme selectors must never make Build Mode scaffolding visible.
        return


class NestedCellEditor:
    """Build Mode editor for cells inside built-in and user-created blocks."""

    EDGE = 7

    def __init__(self, sheet, presentation: BuildingBlockRepository, runtime, tab_manager) -> None:
        self.sheet = sheet
        self.presentation = presentation
        self.runtime = runtime
        self.tab_manager = tab_manager
        self.enabled = False
        self.character_id: int | None = None
        self.selected: list[tuple[QWidget, int, str]] = []
        self.bands: list[QRubberBand] = []
        self.drag_origin = QPoint()
        self.starts: dict[QWidget, QRect] = {}
        self.operation = "move"
        self.popup_active = False
        self.history = None
        self._attribute_keys: dict[int, str] = {}
        self._layout_placements: dict[QWidget, dict] = {}
        self._layout_placeholders: dict[QWidget, QWidget] = {}
        self._detached_from_layout: set[QWidget] = set()
        self._parent_resize_block: QWidget | None = None
        self._parent_resize_size = QSize()
        self._parent_resize_cells: dict[QWidget, QRect] = {}
        self._build_attribute_keys()
        self._capture_default_layouts()

    def _build_attribute_keys(self) -> None:
        for name, value in vars(self.sheet).items():
            if isinstance(value, QWidget):
                self._attribute_keys[id(value)] = f"attr:{name}"
            elif isinstance(value, dict):
                for key, child in value.items():
                    if isinstance(child, QWidget):
                        self._attribute_keys[id(child)] = f"attr:{name}.{key}"

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.clear_selection()

    def set_history(self, history) -> None:
        self.history = history

    def load_character(self, character_id: int) -> None:
        self.character_id = character_id
        self.clear_selection()
        self.apply_overrides()

    def handle(self, watched, event) -> bool:
        if not self.enabled or self.character_id is None or not isinstance(watched, QWidget):
            return False
        if self.popup_owns_input(watched):
            # Popup menus must receive their own clicks. Intercepting them here
            # prevents QAction activation and leaves the popup stuck open.
            return False
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Delete
            and self.selected
        ):
            # Keyboard focus often belongs to the window, a detached child, or
            # a table viewport rather than the selected block itself. Treat Del
            # as the context menu's Remove visual cell action globally while
            # cell editing is active.
            self.hide_selected()
            return True
        block = self._block_for(watched)
        if block is None:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                cell = self._cell_for(watched, block)
                self._context_menu(block, cell, event.globalPosition().toPoint())
                return True
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            cell = self._cell_for(watched, block)
            if cell is None:
                self.clear_selection()
                return False
            self._select(cell, block, bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            if self.history is not None:
                self.history.begin("Move or resize sheet cells")
            self.drag_origin = event.globalPosition().toPoint()
            self.starts = {widget: widget.geometry() for widget, _instance, _key in self.selected}
            position = cell.mapFromGlobal(event.globalPosition().toPoint())
            self.operation = "resize" if position.x() >= cell.width() - self.EDGE or position.y() >= cell.height() - self.EDGE else "move"
            return True
        if event.type() == QEvent.Type.MouseMove and self.starts and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.drag_origin
            for widget, _instance, _key in self.selected:
                start = self.starts[widget]
                if self.operation == "resize" and widget is self.selected[0][0]:
                    widget.resize(max(20, start.width() + delta.x()), max(18, start.height() + delta.y()))
                elif self.operation == "move":
                    widget.move(max(0, start.x() + delta.x()), max(0, start.y() + delta.y()))
            self._update_bands()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self.starts:
            self.starts.clear()
            self._persist_selected()
            if self.history is not None:
                self.history.commit()
            return True
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                for widget, geometry in self.starts.items():
                    widget.setGeometry(geometry)
                if self.history is not None:
                    self.history.cancel()
                self.clear_selection()
                return True
        return False

    @staticmethod
    def _inside_menu(widget: QWidget | None) -> bool:
        while widget is not None:
            if isinstance(widget, QMenu):
                return True
            widget = widget.parentWidget()
        return False

    def popup_owns_input(self, widget: QWidget | None) -> bool:
        """True while a menu, rather than the sheet editor, owns this event."""
        return self.popup_active or self._inside_menu(widget)

    def _block_for(self, widget: QWidget) -> QWidget | None:
        current = widget
        blocks = set(self.sheet.custom_sections.values())
        while current is not None:
            if current in blocks and current.property("blockInstanceId"):
                return current
            current = current.parentWidget()
        return None

    def _cell_for(self, watched: QWidget, block: QWidget) -> QWidget | None:
        if watched is block:
            return None
        current = watched
        fallback = watched
        while current is not None and current is not block:
            if current.property("cellKey") or id(current) in self._attribute_keys:
                return current
            name = current.objectName()
            if name and not name.startswith("qt_") and name not in {
                "qt_scrollarea_viewport", "qt_scrollarea_hcontainer", "qt_scrollarea_vcontainer"
            }:
                fallback = current
                break
            current = current.parentWidget()
        return fallback if fallback is not block else None

    def _cell_key(self, widget: QWidget, block: QWidget) -> str:
        if widget.property("cellKey"):
            return str(widget.property("cellKey"))
        if id(widget) in self._attribute_keys:
            return self._attribute_keys[id(widget)]
        if widget.objectName() and not widget.objectName().startswith("qt_"):
            return f"object:{widget.objectName()}"
        parts = []
        current = widget
        while current is not None and current is not block:
            parent = current.parentWidget()
            siblings = [child for child in parent.children() if isinstance(child, QWidget)] if parent else []
            parts.append(f"{type(current).__name__}:{siblings.index(current) if current in siblings else 0}")
            current = parent
        return "path:" + "/".join(reversed(parts))

    def _select(self, widget: QWidget, block: QWidget, additive: bool) -> None:
        instance_id = int(block.property("blockInstanceId"))
        key = self._cell_key(widget, block)
        if not additive:
            self.clear_selection()
        if not any(item[0] is widget for item in self.selected):
            self._detach(widget, block)
            self.selected.append((widget, instance_id, key))
        group_id = str(widget.property("cellGroup") or "")
        if group_id:
            for peer in block.findChildren(QWidget):
                if peer.property("cellGroup") != group_id:
                    continue
                if any(item[0] is peer for item in self.selected):
                    continue
                self._detach(peer, block)
                self.selected.append((peer, instance_id, self._cell_key(peer, block)))
        self._update_bands()

    def _detach(
        self,
        widget: QWidget,
        block: QWidget,
        *,
        preserve_layout_slot: bool = True,
    ) -> None:
        position = widget.mapTo(block, QPoint(0, 0))
        size = widget.size()
        placement = self._layout_placement(widget, block)
        if placement is not None:
            self._layout_placements.setdefault(widget, placement)
            placement["layout"].removeWidget(widget)
            if preserve_layout_slot:
                placeholder = _LayoutPlaceholder(
                    size, widget, placement.get("parent")
                )
                self._insert_at_placement(placeholder, placement)
                placeholder.show()
                self._layout_placeholders[widget] = placeholder
            self._detached_from_layout.add(widget)
        elif widget.parentWidget() is block:
            return
        widget.setParent(block)
        widget.setGeometry(position.x(), position.y(), size.width(), size.height())
        widget.show()
        widget.raise_()

    def _capture_default_layouts(self) -> None:
        """Remember layout slots before Build Mode detaches any built-in cell."""
        visited: set[QLayout] = set()
        for block in self.sheet.custom_sections.values():
            layout = block.layout()
            if layout is not None:
                self._capture_layout(layout, visited)

    def _capture_layout(self, layout: QLayout, visited: set[QLayout]) -> None:
        if layout in visited:
            return
        visited.add(layout)
        for index in range(layout.count()):
            item = layout.itemAt(index)
            child_layout = item.layout()
            if child_layout is not None:
                self._capture_layout(child_layout, visited)
            widget = item.widget()
            if widget is not None and widget not in self._layout_placements:
                self._layout_placements[widget] = self._placement(
                    layout, index, item.alignment()
                )
            if widget is not None and widget.layout() is not None:
                self._capture_layout(widget.layout(), visited)

    def _layout_placement(self, widget: QWidget, block: QWidget) -> dict | None:
        known = self._layout_placements.get(widget)
        if known is not None and known["layout"].indexOf(widget) >= 0:
            return known
        layout = block.layout()
        return self._find_in_layout(layout, widget) if layout is not None else None

    def _find_in_layout(self, layout: QLayout, widget: QWidget) -> dict | None:
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is widget:
                return self._placement(layout, index, item.alignment())
            child_layout = item.layout()
            if child_layout is not None:
                found = self._find_in_layout(child_layout, widget)
                if found is not None:
                    return found
            child_widget = item.widget()
            if child_widget is not None and child_widget.layout() is not None:
                found = self._find_in_layout(child_widget.layout(), widget)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _placement(layout: QLayout, index: int, alignment) -> dict:
        placement = {
            "layout": layout,
            "index": index,
            "alignment": alignment,
            "parent": layout.parentWidget(),
        }
        if isinstance(layout, QBoxLayout):
            placement["stretch"] = layout.stretch(index)
        elif isinstance(layout, QGridLayout):
            row, column, row_span, column_span = layout.getItemPosition(index)
            placement["grid"] = (row, column, row_span, column_span)
        elif isinstance(layout, QFormLayout):
            row, role = layout.getItemPosition(index)
            placement["form"] = (row, role)
        return placement

    @staticmethod
    def _insert_at_placement(widget: QWidget, placement: dict) -> None:
        layout = placement["layout"]
        alignment = placement["alignment"]
        if isinstance(layout, QBoxLayout):
            layout.insertWidget(
                min(int(placement["index"]), layout.count()),
                widget,
                int(placement.get("stretch", 0)),
                alignment,
            )
        elif isinstance(layout, QGridLayout):
            row, column, row_span, column_span = placement["grid"]
            layout.addWidget(widget, row, column, row_span, column_span, alignment)
        elif isinstance(layout, QFormLayout):
            row, role = placement["form"]
            layout.setWidget(row, role, widget)
        else:
            layout.addWidget(widget)
            layout.setAlignment(widget, alignment)

    def _discard_placeholder(self, widget: QWidget) -> None:
        """Remove temporary layout scaffolding without forgetting the slot."""

        placeholder = self._layout_placeholders.pop(widget, None)
        if placeholder is None:
            return
        layout = self._layout_placements.get(widget, {}).get("layout")
        if layout is not None and layout.indexOf(placeholder) >= 0:
            layout.removeWidget(placeholder)
        placeholder.setParent(None)
        placeholder.deleteLater()

    def _restore_widget_to_layout(self, widget: QWidget) -> bool:
        """Give a detached built-in control back to its original Qt layout."""

        placement = self._layout_placements.get(widget)
        if placement is None:
            return False
        layout = placement["layout"]
        placeholder = self._layout_placeholders.get(widget)
        if placeholder is not None:
            placeholder_index = layout.indexOf(placeholder)
            if placeholder_index >= 0:
                placement = {**placement, "index": placeholder_index}
        self._discard_placeholder(widget)
        if layout.indexOf(widget) < 0:
            parent = placement.get("parent")
            if parent is not None:
                widget.setParent(parent)
            self._insert_at_placement(widget, placement)
        widget.setProperty("cellAnchored", True)
        widget.show()
        self._detached_from_layout.discard(widget)
        return True

    def _restore_detached_layouts(self) -> None:
        """Return cells with no active override to their original Qt layout."""
        for widget in tuple(self._detached_from_layout):
            if not self._restore_widget_to_layout(widget):
                self._detached_from_layout.discard(widget)

    def clear_selection(self) -> None:
        self.selected.clear()
        self.starts.clear()
        for band in self.bands:
            band.hide()
            band.deleteLater()
        self.bands.clear()

    def _update_bands(self) -> None:
        while len(self.bands) < len(self.selected):
            band = QRubberBand(QRubberBand.Shape.Rectangle)
            band.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.bands.append(band)
        for index, (widget, _instance, _key) in enumerate(self.selected):
            band = self.bands[index]
            if band.parentWidget() is not widget.parentWidget():
                band.setParent(widget.parentWidget())
            band.setGeometry(widget.geometry().adjusted(-3, -3, 3, 3))
            band.show()
            band.raise_()
        for band in self.bands[len(self.selected):]:
            band.hide()

    def _base_override(self, instance_id: int, key: str, widget: QWidget) -> CellOverride:
        existing = next((item for item in self.presentation.list_cell_overrides(instance_id) if item.cell_key == key), None)
        if existing:
            return existing
        return CellOverride(
            0, instance_id, key, widget.x(), widget.y(), widget.width(), widget.height(),
            widget.isVisible(), bool(widget.property("cellAnchored") if widget.property("cellAnchored") is not None else True),
            str(widget.property("cellGroup") or ""), "", "", "", {}, {},
        )

    def _persist_selected(self) -> None:
        instance_by_id = {item.id: item for item in self.presentation.list_instances(self.character_id)}
        block_by_widget = {
            widget: int(widget.property("blockInstanceId"))
            for widget in self.sheet.custom_sections.values()
            if widget.property("blockInstanceId")
        }
        for widget, origin_instance, key in self.selected:
            override = self._base_override(origin_instance, key, widget)
            parent_block = self._block_for(widget.parentWidget()) or widget.parentWidget()
            target_instance = block_by_widget.get(parent_block, origin_instance)
            config = dict(override.config)
            if target_instance != origin_instance and target_instance in instance_by_id:
                config["parent_instance_key"] = instance_by_id[target_instance].instance_key
            else:
                config.pop("parent_instance_key", None)
            geometry = widget.geometry()
            self.presentation.save_cell_override(replace(
                override,
                x=geometry.x(), y=geometry.y(), width=geometry.width(), height=geometry.height(),
                visible=widget.isVisible(), config=config,
            ))

    def hide_selected(self) -> None:
        def operation() -> None:
            for widget, instance_id, key in self.selected:
                override = self._base_override(instance_id, key, widget)
                self.presentation.save_cell_override(replace(override, visible=False))
                # A placeholder is useful while freely moving a control because
                # it prevents the surrounding layout from jumping mid-drag. It
                # is not content, though, and must not survive deletion: once
                # removed, the native layout should close the vacated space.
                self._discard_placeholder(widget)
                widget.hide()
            self.clear_selection()
        self._record("Remove sheet cell", operation)

    def group_selected(self) -> None:
        if len(self.selected) < 2:
            return
        def operation() -> None:
            group_id = f"group:{uuid.uuid4().hex}"
            for widget, instance_id, key in self.selected:
                override = self._base_override(instance_id, key, widget)
                self.presentation.save_cell_override(replace(override, group_id=group_id))
                widget.setProperty("cellGroup", group_id)
        self._record("Group sheet cells", operation)

    def ungroup_selected(self) -> None:
        def operation() -> None:
            for widget, instance_id, key in self.selected:
                override = self._base_override(instance_id, key, widget)
                self.presentation.save_cell_override(replace(override, group_id=""))
                widget.setProperty("cellGroup", "")
        self._record("Ungroup sheet cells", operation)

    def set_anchored(self, anchored: bool) -> None:
        def operation() -> None:
            restored_layout_cell = False
            for widget, instance_id, key in tuple(self.selected):
                if anchored and widget in self._layout_placements:
                    # For built-in cells, anchoring means returning ownership to
                    # the original responsive layout—not merely scaling the last
                    # freeform rectangle with its parent.
                    self.presentation.delete_cell_override(instance_id, key)
                    widget.setProperty("cellGroup", "")
                    restored_layout_cell = (
                        self._restore_widget_to_layout(widget)
                        or restored_layout_cell
                    )
                    continue
                override = self._base_override(instance_id, key, widget)
                self.presentation.save_cell_override(replace(override, anchored=anchored))
                widget.setProperty("cellAnchored", anchored)
            if restored_layout_cell:
                self.clear_selection()
        self._record(
            "Return sheet cells to parent layout"
            if anchored
            else "Make sheet cells independent",
            operation,
        )

    def restore_hidden(self, instance_id: int) -> None:
        def operation() -> None:
            for override in self.presentation.list_cell_overrides(instance_id):
                if not override.visible:
                    self.presentation.save_cell_override(replace(override, visible=True))
            self.runtime.refresh()
        self._record("Restore hidden sheet cells", operation)

    def persist_block_cells(self, block: QWidget) -> None:
        """Save edited child geometry after a parent resize, never during drag."""
        if not block.property("blockInstanceId"):
            return
        for override, widget in self._overrides_for_block(block):
            geometry = widget.geometry()
            self.presentation.save_cell_override(replace(
                override,
                x=geometry.x(), y=geometry.y(), width=geometry.width(),
                height=geometry.height(), visible=widget.isVisible(),
            ))

    def begin_parent_resize(self, block: QWidget) -> None:
        """Capture built-in freeform cells before their parent starts resizing."""
        self._parent_resize_block = None
        self._parent_resize_cells = {}
        if (
            not block.property("blockInstanceId")
            or block in self.runtime.widgets.values()
        ):
            return
        self._parent_resize_block = block
        self._parent_resize_size = QSize(block.size())
        self._parent_resize_cells = {
            widget: QRect(widget.geometry())
            for override, widget in self._overrides_for_block(block)
            if override.anchored
        }

    def preview_parent_resize(self, block: QWidget) -> None:
        if block is not self._parent_resize_block:
            return
        start = self._parent_resize_size
        if start.width() <= 0 or start.height() <= 0:
            return
        scale_x = block.width() / start.width()
        scale_y = block.height() / start.height()
        for widget, geometry in self._parent_resize_cells.items():
            widget.setGeometry(
                round(geometry.x() * scale_x),
                round(geometry.y() * scale_y),
                max(20, round(geometry.width() * scale_x)),
                max(18, round(geometry.height() * scale_y)),
            )
        self._update_bands()

    def finish_parent_resize(self) -> None:
        self._parent_resize_block = None
        self._parent_resize_size = QSize()
        self._parent_resize_cells = {}

    def cancel_parent_resize(self) -> None:
        for widget, geometry in self._parent_resize_cells.items():
            widget.setGeometry(geometry)
        self._update_bands()
        self.finish_parent_resize()

    def _overrides_for_block(
        self, block: QWidget
    ) -> list[tuple[CellOverride, QWidget]]:
        if self.character_id is None or not block.property("blockInstanceId"):
            return []
        target_id = int(block.property("blockInstanceId"))
        instances = self.presentation.list_instances(self.character_id)
        target = next((item for item in instances if item.id == target_id), None)
        if target is None:
            return []
        result = []
        for instance in instances:
            for override in self.presentation.list_cell_overrides(instance.id):
                parent_key = str(
                    override.config.get("parent_instance_key") or ""
                )
                if parent_key:
                    belongs = parent_key == target.instance_key
                else:
                    belongs = instance.id == target_id
                if not belongs:
                    continue
                widget = self._find_cell(block, override.cell_key)
                if widget is not None:
                    result.append((override, widget))
        return result

    def _context_menu(self, block: QWidget, cell: QWidget | None, global_position: QPoint) -> None:
        # Parent the popup to the sheet, not the edited block. Otherwise the
        # global Build Mode filter sees menu clicks as clicks inside that block.
        menu = self._build_context_menu(block, cell)
        self.popup_active = True
        try:
            menu.exec(global_position)
        finally:
            self.popup_active = False

    def _build_context_menu(self, block: QWidget, cell: QWidget | None) -> QMenu:
        """Compose a menu separately from displaying it for reliable testing."""
        menu = QMenu(self.sheet)
        if cell is not None:
            self._select(cell, block, QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
            menu.addAction("Remove visual cell", self.hide_selected)
            menu.addSeparator()
            menu.addAction("Group selected cells", self.group_selected)
            menu.addAction("Ungroup selected cells", self.ungroup_selected)
            menu.addAction("Anchor to parent", lambda: self.set_anchored(True))
            menu.addAction("Make independently positioned", lambda: self.set_anchored(False))
            targets = menu.addMenu("Move cell to another block")
            for target in self.sheet.custom_sections.values():
                if target is block or not target.property("blockInstanceId") or not target.isVisible():
                    continue
                label = str(target.property("customizationId") or target.objectName() or "Block")
                targets.addAction(label, lambda checked=False, owner=target: self._reparent_selected(owner))
        else:
            instance_id = int(block.property("blockInstanceId"))
            menu.addAction("Remove visual block from character", lambda: self._hide_block(instance_id))
            destinations = menu.addMenu("Move block to tab")
            current_instance = next((item for item in self.presentation.list_instances(self.character_id) if item.id == instance_id), None)
            for tab in self.presentation.list_tabs(self.character_id):
                if not tab.visible or (current_instance and tab.key == current_instance.tab_key):
                    continue
                destinations.addAction(tab.name, lambda checked=False, key=tab.key: self._move_block(instance_id, key))
            menu.addSeparator()
            menu.addAction("Restore hidden cells", lambda: self.restore_hidden(instance_id))
        return menu

    def _hide_block(self, instance_id: int) -> None:
        self._record(
            "Remove sheet block",
            lambda: (
                self.presentation.set_instance_visible(instance_id, False),
                self.runtime.refresh(),
            ),
        )

    def _move_block(self, instance_id: int, tab_key: str) -> None:
        self._record(
            "Move sheet block to another tab",
            lambda: (
                self.presentation.move_instance(instance_id, tab_key),
                self.runtime.refresh(),
            ),
        )

    def _reparent_selected(self, target: QWidget) -> None:
        def operation() -> None:
            offset = 32
            for widget, _instance, _key in self.selected:
                widget.setParent(target)
                widget.move(offset, offset)
                widget.show()
                widget.raise_()
                offset += 16
            self._persist_selected()
            self._update_bands()
        self._record("Move cells to another sheet block", operation)

    def _record(self, description: str, operation) -> object:
        if self.history is None:
            return operation()
        return self.history.record(description, operation)

    def apply_overrides(self) -> None:
        if self.character_id is None:
            return
        # Rebuild from the true layout baseline first. This makes removing an
        # override, switching characters, undoing, and Default Sheet reliable.
        self._restore_detached_layouts()
        instances = {item.id: item for item in self.presentation.list_instances(self.character_id)}
        blocks = {
            int(widget.property("blockInstanceId")): widget
            for widget in self.sheet.custom_sections.values()
            if widget.property("blockInstanceId")
        }
        blocks_by_key = {
            instances[instance_id].instance_key: widget
            for instance_id, widget in blocks.items()
            if instance_id in instances
        }
        for instance_id, block in blocks.items():
            for override in self.presentation.list_cell_overrides(instance_id):
                widget = self._find_cell(block, override.cell_key)
                if widget is None:
                    continue
                target = blocks_by_key.get(str(override.config.get("parent_instance_key") or ""), block)
                self._detach(
                    widget,
                    target,
                    preserve_layout_slot=override.visible,
                )
                widget.setGeometry(override.x, override.y, override.width, override.height)
                widget.setProperty("cellAnchored", override.anchored)
                widget.setProperty("cellGroup", override.group_id)
                widget.setVisible(override.visible)

    def _find_cell(self, block: QWidget, key: str) -> QWidget | None:
        for widget in block.findChildren(QWidget):
            if self._cell_key(widget, block) == key:
                return widget
        return None
