from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.building_blocks.actions import ACTIONS, ActionContext
from app.building_blocks.bindings import BINDINGS
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import BlockRegistry, CELL_TYPE_REGISTRY
from app.building_blocks.schemas import (
    BlockDefinition,
    BlockInstance,
    CellDefinition,
    CellOverride,
)
from app.custom_trackers import CustomTrackerResolver, display_number
from app.database import CharacterRepository
from app.formulas import DEFAULT_FORMULA_ENGINE, FormulaError


def _cell_style(style: dict[str, Any]) -> str:
    allowed = {
        "background": "background-color",
        "foreground": "color",
        "border_color": "border-color",
        "border_width": "border-width",
        "font_size": "font-size",
        "font_weight": "font-weight",
    }
    rules = []
    for key, css_key in allowed.items():
        value = style.get(key)
        if value in (None, ""):
            continue
        suffix = "px" if key in {"border_width", "font_size"} and str(value).isdigit() else ""
        rules.append(f"{css_key}: {value}{suffix}")
    if style.get("border_color") and not style.get("border_width"):
        rules.append("border-width: 1px")
    if style.get("border_color"):
        rules.append("border-style: solid")
    if style.get("bold"):
        rules.append("font-weight: bold")
    if style.get("italic"):
        rules.append("font-style: italic")
    return "; ".join(rules)


class RuntimeBlockWidget(QFrame):
    """Renders one user block snapshot without owning character rules data."""

    def __init__(
        self,
        repository: CharacterRepository,
        presentation: BuildingBlockRepository,
        character_id: int,
        instance: BlockInstance,
        definition: BlockDefinition,
        action_callbacks: dict[str, Callable],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("runtimeBuildingBlock")
        self.repository = repository
        self.presentation = presentation
        self.character_id = character_id
        self.instance = instance
        self.definition = definition
        self.action_callbacks = action_callbacks
        self.cells: dict[str, QWidget] = {}
        self._last_runtime_size = QSize(instance.width, instance.height)
        self.overrides = {
            item.cell_key: item
            for item in presentation.list_cell_overrides(instance.id)
        }
        self.setProperty("blockInstanceId", instance.id)
        self.setProperty("blockTemplateKey", definition.key)
        # Runtime blocks already use absolute canvas coordinates. Mark them as
        # managed freeform boxes so canvas sizing and scrolling include them
        # immediately, even before Build Mode has ever been opened.
        self.setProperty("freeformManaged", True)
        self.setGeometry(instance.x, instance.y, instance.width, instance.height)
        self.setStyleSheet(_cell_style({**definition.style, **instance.style}))
        title = QLabel(definition.name.upper(), self)
        title.setObjectName("runtimeBlockTitle")
        title.setGeometry(0, 0, max(100, instance.width), 26)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title = title
        self._build_cells()
        self.show()

    def _effective(self, cell: CellDefinition) -> CellOverride:
        return self.overrides.get(cell.key) or CellOverride(
            0, self.instance.id, cell.key, cell.x, cell.y, cell.width, cell.height,
            True, cell.anchored, cell.group_id, cell.binding, cell.formula,
            cell.action, dict(cell.config), dict(cell.style),
        )

    def _build_cells(self) -> None:
        for cell in self.definition.cells:
            override = self._effective(cell)
            widget = self._widget_for(cell, override)
            widget.setProperty("cellKey", cell.key)
            widget.setProperty("cellType", cell.cell_type)
            widget.setProperty("cellAnchored", override.anchored)
            widget.setProperty("cellGroup", override.group_id)
            widget.setGeometry(override.x, override.y, override.width, override.height)
            widget.setVisible(override.visible)
            widget.setStyleSheet(_cell_style({**cell.style, **override.style}))
            if isinstance(widget, QLabel):
                alignment = str(({**cell.style, **override.style}).get("alignment") or "left")
                widget.setAlignment({
                    "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    "center": Qt.AlignmentFlag.AlignCenter,
                    "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                }.get(alignment, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
            self.cells[cell.key] = widget

    def _widget_for(self, cell: CellDefinition, override: CellOverride) -> QWidget:
        config = {**cell.config, **override.config}
        binding = override.binding or cell.binding
        formula = override.formula or cell.formula
        action = override.action or cell.action
        if cell.cell_type == "label":
            widget = QLabel(str(config.get("text", cell.label)), self)
            widget.setWordWrap(bool(config.get("word_wrap", True)))
            return widget
        if cell.cell_type == "formula":
            widget = QLabel(self._formula_text(formula), self)
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.setToolTip(formula)
            return widget
        if cell.cell_type == "text":
            widget = QLineEdit(self)
            widget.setPlaceholderText(cell.label)
            value = self._read_binding(binding, config.get("value", ""))
            widget.setText(str(value if value is not None else ""))
            widget.setReadOnly(bool(binding and not self._binding_editable(binding)))
            widget.editingFinished.connect(
                lambda key=cell.key, control=widget, bind=binding: self._save_value(key, bind, control.text())
            )
            return widget
        if cell.cell_type == "number":
            widget = QDoubleSpinBox(self)
            widget.setRange(float(config.get("minimum", -1_000_000_000)), float(config.get("maximum", 1_000_000_000)))
            widget.setDecimals(int(config.get("decimals", 0)))
            widget.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            widget.setValue(float(self._read_binding(binding, config.get("value", 0)) or 0))
            widget.setReadOnly(bool(binding and not self._binding_editable(binding)))
            widget.editingFinished.connect(
                lambda key=cell.key, control=widget, bind=binding: self._save_value(key, bind, control.value())
            )
            return widget
        if cell.cell_type == "checkbox":
            widget = QCheckBox(cell.label, self)
            widget.setChecked(bool(self._read_binding(binding, config.get("value", False))))
            widget.toggled.connect(
                lambda value, key=cell.key, bind=binding: self._save_value(key, bind, value)
            )
            return widget
        if cell.cell_type == "dropdown":
            widget = QComboBox(self)
            options = [str(value) for value in config.get("options", ())]
            widget.addItems(options)
            value = str(self._read_binding(binding, config.get("value", "")) or "")
            if value and widget.findText(value) < 0:
                widget.addItem(value)
            if value:
                widget.setCurrentText(value)
            widget.currentTextChanged.connect(
                lambda value, key=cell.key, bind=binding: self._save_value(key, bind, value)
            )
            return widget
        if cell.cell_type == "button":
            widget = QPushButton(str(config.get("text", cell.label or "Action")), self)
            widget.clicked.connect(lambda _checked=False, key=action, cfg=config: self._execute_action(key, cfg))
            return widget
        if cell.cell_type == "table":
            widget = QTableWidget(self)
            data = self._read_binding(binding, config.get("data", {"columns": (), "rows": ()}))
            columns = list(data.get("columns", ())) if isinstance(data, dict) else []
            rows = list(data.get("rows", ())) if isinstance(data, dict) else []
            widget.setColumnCount(len(columns))
            widget.setHorizontalHeaderLabels([str(value) for value in columns])
            widget.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column, value in enumerate(row):
                    widget.setItem(row_index, column, QTableWidgetItem(str(value)))
            widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            return widget
        try:
            descriptor = CELL_TYPE_REGISTRY.get(cell.cell_type)
        except ValueError:
            descriptor = None
        if descriptor is not None and descriptor.runtime_factory is not None:
            return descriptor.runtime_factory(
                self,
                cell,
                {
                    "config": config,
                    "binding": binding,
                    "formula": formula,
                    "action": action,
                    "runtime": self,
                },
            )
        return QLabel(f"Unsupported cell: {cell.cell_type}", self)

    def resizeEvent(self, event) -> None:
        old = self._last_runtime_size
        new = event.size()
        if self.cells and old.width() > 0 and old.height() > 0 and new != old:
            scale_x = new.width() / old.width()
            scale_y = new.height() / old.height()
            for key, widget in self.cells.items():
                cell = next(item for item in self.definition.cells if item.key == key)
                override = self._effective(cell)
                if not override.anchored:
                    continue
                geometry = widget.geometry()
                widget.setGeometry(
                    round(geometry.x() * scale_x),
                    round(geometry.y() * scale_y),
                    max(20, round(geometry.width() * scale_x)),
                    max(18, round(geometry.height() * scale_y)),
                )
        self._last_runtime_size = QSize(new)
        if hasattr(self, "title"):
            self.title.setGeometry(0, 0, max(100, new.width()), 26)
        super().resizeEvent(event)

    def persist_cell_geometry(self) -> None:
        """Persist final anchored geometry once a parent resize has finished."""
        for cell in self.definition.cells:
            widget = self.cells.get(cell.key)
            if widget is None:
                continue
            override = self._effective(cell)
            geometry = widget.geometry()
            self.presentation.save_cell_override(replace(
                override,
                x=geometry.x(),
                y=geometry.y(),
                width=geometry.width(),
                height=geometry.height(),
                visible=widget.isVisible(),
            ))

    def _read_binding(self, binding: str, fallback: Any) -> Any:
        if not binding:
            return fallback
        try:
            return BINDINGS.resolve(self.repository, self.character_id, binding)
        except (KeyError, ValueError):
            return fallback

    def _binding_editable(self, binding: str) -> bool:
        descriptor = BINDINGS.get(binding)
        if descriptor is None:
            descriptor = next((item for item in BINDINGS.all(self.repository, self.character_id) if item.key == binding), None)
        return bool(descriptor and descriptor.editable)

    def _formula_text(self, formula: str) -> str:
        if not formula:
            return "—"
        try:
            resolver = CustomTrackerResolver(self.repository, self.character_id)
            return display_number(DEFAULT_FORMULA_ENGINE.evaluate(formula, resolver.base_values, resolver.resolve_reference))
        except FormulaError as error:
            return f"Formula error: {error}"

    def _save_value(self, cell_key: str, binding: str, value: Any) -> None:
        if binding:
            try:
                BINDINGS.write(self.repository, self.character_id, binding, value)
            except (KeyError, ValueError) as error:
                QMessageBox.warning(self, "Cannot update value", str(error))
                return
            refresh = self.action_callbacks.get("refresh")
            if refresh:
                refresh()
            return
        cell = next(item for item in self.definition.cells if item.key == cell_key)
        override = self._effective(cell)
        config = dict(override.config)
        config["value"] = value
        self.presentation.save_cell_override(replace(override, config=config))

    def _execute_action(self, action: str, config: dict[str, Any]) -> None:
        try:
            ACTIONS.execute(action, ActionContext(
                self.repository, self.character_id, config, self.action_callbacks
            ))
        except ValueError as error:
            QMessageBox.warning(self, "Action unavailable", str(error))

    def refresh_values(self) -> None:
        geometry = self.geometry()
        self.setParent(None)
        self.deleteLater()
        # Controller recreates the widget; retained for a stable public seam.
        self.setGeometry(geometry)


class BlockRuntimeController:
    def __init__(
        self,
        sheet,
        customization,
        character_repository: CharacterRepository,
        presentation: BuildingBlockRepository,
        registry: BlockRegistry,
        action_callbacks: dict[str, Callable],
    ) -> None:
        self.sheet = sheet
        self.customization = customization
        self.character_repository = character_repository
        self.presentation = presentation
        self.registry = registry
        self.action_callbacks = action_callbacks
        self.character_id: int | None = None
        self.widgets: dict[int, RuntimeBlockWidget] = {}
        self.canvases: dict[str, QWidget] = {
            "build": sheet.builder_canvas,
            "core": sheet.core_canvas,
            "inventory": sheet.inventory_canvas,
            "magic": sheet.magic_canvas,
        }
        self.nested_editor = None
        self.history = None

    def set_nested_editor(self, editor) -> None:
        self.nested_editor = editor

    def set_history(self, history) -> None:
        self.history = history

    def set_canvases(self, canvases: dict[str, QWidget]) -> None:
        self.canvases = dict(canvases)

    def load_character(self, character_id: int) -> None:
        self.character_id = character_id
        self.presentation.ensure_character(character_id, self.registry)
        self.refresh()

    def refresh(self) -> None:
        for instance_id, widget in tuple(self.widgets.items()):
            self.sheet.custom_sections.pop(f"block-instance:{instance_id}", None)
            widget.setParent(None)
            widget.deleteLater()
        self.widgets.clear()
        if self.character_id is None:
            return
        for instance in self.presentation.list_instances(self.character_id):
            definition = self._definition(instance)
            if definition is None:
                continue
            if definition.builtin:
                section = self.sheet.custom_sections.get(definition.section_key)
                if section is not None:
                    section.setProperty("blockInstanceId", instance.id)
                    section.setProperty("blockInstanceKey", instance.instance_key)
                    section.setProperty("blockInstanceVisible", instance.visible)
                    rule_available = section.property("ruleAvailable")
                    section.setVisible(
                        instance.visible and rule_available is not False
                    )
                    canvas = self.canvases.get(instance.tab_key)
                    current_canvas = self.customization.section_canvases.get(section)
                    if canvas is not None and current_canvas is not canvas:
                        self.customization.place_section_freeform(
                            section,
                            canvas,
                            QRect(instance.x, instance.y, instance.width, instance.height),
                        )
                continue
            if not instance.visible:
                continue
            canvas = self.canvases.get(instance.tab_key)
            if canvas is None:
                continue
            widget = RuntimeBlockWidget(
                self.character_repository, self.presentation, self.character_id,
                instance, definition, self.action_callbacks, canvas,
            )
            widget.raise_()
            widget.setProperty("blockInstanceKey", instance.instance_key)
            self.widgets[instance.id] = widget
            self.sheet.custom_sections[f"block-instance:{instance.id}"] = widget
        self.sheet.custom_sections_changed.emit()
        self.customization.sync_sections()
        if self.nested_editor is not None:
            self.nested_editor.apply_overrides()

    def _definition(self, instance: BlockInstance) -> BlockDefinition | None:
        definition = self.registry.get(instance.template_key)
        if definition is not None:
            return definition
        return BlockDefinition.from_dict(instance.template_snapshot) if instance.template_snapshot else None

    def add_block(self, definition: BlockDefinition, tab_key: str) -> int:
        if self.character_id is None:
            raise ValueError("Open a character first.")
        result = {"id": 0}
        def operation() -> None:
            result["id"] = self.presentation.add_instance(
                self.character_id, definition, tab_key
            )
            self.refresh()
        if self.history is None:
            operation()
        else:
            self.history.record("Add sheet block", operation)
        return result["id"]

    def remove_block(self, definition: BlockDefinition, tab_key: str) -> int:
        """Hide one placed instance while retaining its template and data."""

        if self.character_id is None:
            raise ValueError("Open a character first.")
        matches = [
            instance
            for instance in self.presentation.list_instances(
                self.character_id, tab_key
            )
            if instance.template_key == definition.key and instance.visible
        ]
        if not matches:
            raise ValueError("This block is not on the selected tab.")
        instance_id = matches[-1].id
        self.set_visible(instance_id, False)
        return instance_id

    def set_visible(self, instance_id: int, visible: bool) -> None:
        operation = lambda: (
            self.presentation.set_instance_visible(instance_id, visible),
            self.refresh(),
        )
        if self.history is None:
            operation()
        else:
            self.history.record(
                "Restore sheet block" if visible else "Remove sheet block",
                operation,
            )

    def move(self, instance_id: int, tab_key: str) -> None:
        operation = lambda: (
            self.presentation.move_instance(instance_id, tab_key),
            self.refresh(),
        )
        if self.history is None:
            operation()
        else:
            self.history.record("Move sheet block to another tab", operation)

    def save_widget_geometry(self, widget: QWidget) -> None:
        if not widget.property("blockInstanceId"):
            return
        geometry = widget.geometry()
        self.presentation.update_instance_geometry(
            int(widget.property("blockInstanceId")),
            geometry.x(), geometry.y(), geometry.width(), geometry.height(),
        )
        if isinstance(widget, RuntimeBlockWidget):
            widget.persist_cell_geometry()
        elif self.nested_editor is not None:
            self.nested_editor.persist_block_cells(widget)
