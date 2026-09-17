"""Theme-aware presentation adapter for the shared reference catalog."""
from app.reference_rules import reference_html
from app.ui.refined.theme import PALETTES

def reference_link_color(owner):
    widget = owner
    theme = "classic"
    while widget is not None:
        if hasattr(widget, "theme"):
            theme = widget.theme
            break
        widget = widget.parentWidget()
    return PALETTES.get(theme, PALETTES["classic"]).accent


def reference_document_html(owner, markup):
    """Apply the same readable type and link contrast to collection/index pages."""
    color = reference_link_color(owner)
    return '<div style="font-size:11pt">' + markup.replace('<a ', f'<a style="color:{color}" ') + '</div>'


def reference_details_html(owner, entry, **kwargs):
    return reference_html(entry, link_color=reference_link_color(owner), **kwargs)
