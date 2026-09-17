from __future__ import annotations

import json
import math
from dataclasses import dataclass

from PySide6.QtCore import QMargins, QRect, QSettings, QSize, QTimer
from PySide6.QtWidgets import QLayout, QTableWidget, QWidget


@dataclass(frozen=True)
class _WidgetMetrics:
    font_size: float
    minimum: QSize
    maximum: QSize
    style_sheet: str


@dataclass(frozen=True)
class _LayoutMetrics:
    margins: QMargins
    spacing: int


class SectionContentScaleController:
    """Scales a Lego block's presentation without touching character rules.

    Geometry remains owned by :class:`SheetCustomizationController`.  This
    controller only owns the relative size of the widgets and layouts inside a
    registered block, which makes proportional resizing an optional build-mode
    operation instead of a second layout implementation.
    """

    MINIMUM_SCALE = 0.55
    MAXIMUM_SCALE = 2.50

    def __init__(
        self,
        settings: QSettings,
        sections: dict[str, QWidget],
        parent=None,
    ) -> None:
        self.settings = settings
        self.sections = sections
        self.enabled = False
        self._widget_metrics: dict[str, dict[QWidget, _WidgetMetrics]] = {}
        self._layout_metrics: dict[str, dict[QLayout, _LayoutMetrics]] = {}
        self._table_rows: dict[str, dict[QTableWidget, int]] = {}
        self._scales = self._load()
        self._active_key = ""
        self._start_geometry = QRect()
        self._start_scale = 1.0
        # The main window applies its theme after the sheet is composed.  Wait
        # until then so the captured baseline reflects the active theme.
        QTimer.singleShot(0, self.restore)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def begin(self, key: str, geometry: QRect) -> None:
        self._ensure_baseline(key)
        self._active_key = key
        self._start_geometry = QRect(geometry)
        self._start_scale = self.scale_for(key)

    def preview(self, geometry: QRect) -> float:
        if not self._active_key:
            return 1.0
        start_area = max(1, self._start_geometry.width() * self._start_geometry.height())
        area = max(1, geometry.width() * geometry.height())
        factor = self._start_scale * math.sqrt(area / start_area)
        factor = max(self.MINIMUM_SCALE, min(self.MAXIMUM_SCALE, factor))
        self.apply(self._active_key, factor)
        return factor

    def finish(self) -> None:
        if self._active_key:
            self._save()
        self._active_key = ""

    def scale_for(self, key: str) -> float:
        return float(self._scales.get(key, 1.0))

    def apply(self, key: str, factor: float) -> None:
        if key not in self.sections:
            return
        self._ensure_baseline(key)
        factor = max(self.MINIMUM_SCALE, min(self.MAXIMUM_SCALE, float(factor)))
        self._scales[key] = factor
        for widget, metrics in self._widget_metrics[key].items():
            font = widget.font()
            if metrics.font_size > 0:
                font.setPointSizeF(max(5.0, metrics.font_size * factor))
                widget.setFont(font)
                # The application themes specify font sizes through Qt style
                # sheets, which take precedence over QWidget.setFont().  A
                # small local declaration is therefore required for the
                # proportional mode to be visible.
                scaled_font = max(5.0, metrics.font_size * factor)
                prefix = metrics.style_sheet.rstrip()
                if widget is not self.sections[key]:
                    widget.setStyleSheet(
                        f"{prefix}\nfont-size: {scaled_font:.2f}pt;".strip()
                    )
            widget.setMinimumSize(
                self._scaled_dimension(metrics.minimum.width(), factor),
                self._scaled_dimension(metrics.minimum.height(), factor),
            )
            maximum_width = self._scaled_maximum(metrics.maximum.width(), factor)
            maximum_height = self._scaled_maximum(metrics.maximum.height(), factor)
            widget.setMaximumSize(maximum_width, maximum_height)
        for layout, metrics in self._layout_metrics[key].items():
            margins = metrics.margins
            layout.setContentsMargins(
                round(margins.left() * factor),
                round(margins.top() * factor),
                round(margins.right() * factor),
                round(margins.bottom() * factor),
            )
            if metrics.spacing >= 0:
                layout.setSpacing(max(0, round(metrics.spacing * factor)))
        for table, row_height in self._table_rows[key].items():
            table.verticalHeader().setDefaultSectionSize(
                max(16, round(row_height * factor))
            )
        self.sections[key].updateGeometry()

    def restore(self) -> None:
        for key, factor in tuple(self._scales.items()):
            if key in self.sections and abs(float(factor) - 1.0) > 0.001:
                self.apply(key, float(factor))

    def reset(self) -> None:
        for key in tuple(self._scales):
            if key in self.sections:
                self.apply(key, 1.0)
        self._scales.clear()
        self.settings.remove("customization/contentScales")

    def reload(self) -> None:
        for key in tuple(self._scales):
            if key in self.sections:
                self.apply(key, 1.0)
        self._scales = self._load()
        self.restore()

    def _ensure_baseline(self, key: str) -> None:
        if key in self._widget_metrics or key not in self.sections:
            return
        section = self.sections[key]
        widgets = [
            widget
            for widget in [section, *section.findChildren(QWidget)]
            if widget.objectName() != "buildModeCellPlaceholder"
        ]
        self._widget_metrics[key] = {
            widget: _WidgetMetrics(
                widget.font().pointSizeF(),
                widget.minimumSize(),
                widget.maximumSize(),
                widget.styleSheet(),
            )
            for widget in widgets
        }
        layouts = [section.layout(), *section.findChildren(QLayout)]
        self._layout_metrics[key] = {
            layout: _LayoutMetrics(layout.contentsMargins(), layout.spacing())
            for layout in layouts
            if layout is not None
        }
        self._table_rows[key] = {
            table: table.verticalHeader().defaultSectionSize()
            for table in section.findChildren(QTableWidget)
        }

    @staticmethod
    def _scaled_dimension(value: int, factor: float) -> int:
        return 0 if value <= 0 else max(1, round(value * factor))

    @staticmethod
    def _scaled_maximum(value: int, factor: float) -> int:
        if value >= 16777215:
            return 16777215
        return max(1, round(value * factor))

    def _load(self) -> dict[str, float]:
        raw = str(self.settings.value("customization/contentScales", "{}") or "{}")
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if not isinstance(values, dict):
            return {}
        result = {}
        for key, value in values.items():
            try:
                result[str(key)] = max(
                    self.MINIMUM_SCALE, min(self.MAXIMUM_SCALE, float(value))
                )
            except (TypeError, ValueError):
                continue
        return result

    def _save(self) -> None:
        self.settings.setValue(
            "customization/contentScales",
            json.dumps({key: round(value, 4) for key, value in self._scales.items()}),
        )
