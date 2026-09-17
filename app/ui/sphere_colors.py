"""Stable, subtle sphere hues shared by book groups and sheet tables."""
from functools import lru_cache
from hashlib import sha256
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget


# Familiar neighboring groups get deliberately separated hues; new spheres
# automatically receive a stable fallback without changing existing colors.
HUE_OFFSETS = {
    'athletics': 18, 'boxing': -18, 'equipment': 0, 'open hand': 30,
    'warp': -18, 'weather': 18, 'alteration': -6,
}

@lru_cache(maxsize=512)
def sphere_surface(kind, sphere, theme, base):
    color = QColor(base)
    name = sphere.strip().casefold()
    if not name:
        return color.name()
    hue, saturation, lightness, alpha = color.getHslF()
    # Stable across sessions and catalog updates; no dependence on row order.
    offset = HUE_OFFSETS.get(name, int.from_bytes(sha256(name.encode()).digest()[:2], 'big') % 45 - 22) / 360
    return QColor.fromHslF((hue + offset) % 1, saturation, lightness, alpha).name()


def style_sphere_group(widget, sphere, kind, context):
    widget.setProperty("sphereName", sphere)
    widget.setProperty("sphereKind", kind)
    while context is not None and not hasattr(context, "theme"):
        context = context.parentWidget()
    _apply(widget, getattr(context, "theme", "classic"))


def _apply(widget, theme):
    from app.ui.refined.theme import PALETTES
    palette = PALETTES.get(theme, PALETTES['classic'])
    kind = widget.property('sphereKind')
    color = sphere_surface(kind, widget.property('sphereName'), theme, getattr(palette, kind))
    widget.setStyleSheet(f'#{widget.objectName()} {{ background: {color}; color: {palette.text}; border: 1px solid {palette.line}; border-radius: 4px; padding: 4px 8px; }}')


def refresh_sphere_colors(root, theme):
    for widget in root.findChildren(QWidget):
        if widget.property('sphereKind') in ('magic', 'martial'):
            _apply(widget, theme)
