"""Safe presentation cleanup for legacy UTF-8 text decoded as Windows text."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


_DIRECT_REPLACEMENTS = {
    "â": "’",
    "â€™": "’",
    "â": "‘",
    "â€˜": "‘",
    "â": "–",
    "â€“": "–",
    "â": "—",
    "â€”": "—",
    "â": "“",
    "â€œ": "“",
    "â": "”",
    "â€": "”",
    "â¦": "…",
    "â€¦": "…",
    "Â ": " ",
}
_CORRUPTION_MARKERS = ("â", "â€", "Ã", "Â", "ï¿½", "�")


def _corruption_score(value: str) -> int:
    controls = sum(1 for character in value if 0x80 <= ord(character) <= 0x9F)
    return controls * 4 + sum(value.count(marker) * 3 for marker in _CORRUPTION_MARKERS)


def repair_mojibake(value: str) -> str:
    """Repair common double-decoding without altering already-correct Unicode."""

    text = str(value)
    if not any(marker in text for marker in _CORRUPTION_MARKERS):
        return text
    for source, target in _DIRECT_REPLACEMENTS.items():
        text = text.replace(source, target)
    for encoding in ("latin-1", "cp1252"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if _corruption_score(candidate) < _corruption_score(text):
            text = candidate
    return text


def repair_text_tree(value):
    """Return catalog-shaped data with every textual leaf repaired."""

    if isinstance(value, str):
        return repair_mojibake(value)
    if isinstance(value, Mapping):
        return {key: repair_text_tree(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(repair_text_tree(item) for item in value)
    if isinstance(value, list):
        return [repair_text_tree(item) for item in value]
    return value
