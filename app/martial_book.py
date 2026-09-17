"""Rules-facing projection and focus actions for the optional Martial Book."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from app.content import martial_entry
from app.services.character_calculations import CharacterCalculationService
from app.exploitant_rules import effective_martial_talents


FOCUS_NONE = "none"
FOCUS_MAINTAIN = "maintain"
FOCUS_EXPEND = "expend"

_EXPEND_FOCUS = re.compile(
    r"(?:"
    r"\bexpend(?:s|ed|ing)?\b(?:(?!\b(?:regain|restore)\b)[^.!?]){0,70}?\bmartial\s+focus(?:es)?\b"
    r"|\bspend(?:s|spent|ing)?\b(?:(?!\b(?:regain|restore)\b)[^.!?]){0,70}?\bmartial\s+focus(?:es)?\b"
    r"|\bexpenditure\s+of\s+(?:(?:your|their|a)\s+)?martial\s+focus\b"
    r"|\bmartial\s+focus(?:es)?\b[^.!?]{0,35}?\b(?:is|are)\s+expended\b"
    r")",
    re.IGNORECASE,
)
_MAINTAIN_FOCUS = re.compile(
    r"(?:"
    r"\b(?:while|when|if|as\s+long\s+as|so\s+long\s+as)\b"
    r"(?:(?![.!?]).){0,100}?\b(?:have|possess|maintain|are\s+maintaining)"
    r"(?:\s+your)?\s+martial\s+focus\b"
    r"|\bwhile\s+(?:you\s+are\s+)?martially\s+focused\b"
    r"|\brequires?\s+(?:you\s+to\s+have\s+)?(?:your\s+)?martial\s+focus\b"
    r")",
    re.IGNORECASE,
)


def martial_focus_usage(text: str, *, explicit: str = "") -> str:
    """Classify focus use through one future-friendly rules seam.

    Catalog entries may eventually provide ``automation.focus_usage``. Until
    then the normalized local rules text is interpreted here, never in Qt.
    """

    explicit = explicit.strip().casefold()
    if explicit in {FOCUS_NONE, FOCUS_MAINTAIN, FOCUS_EXPEND}:
        return explicit
    if _EXPEND_FOCUS.search(text):
        return FOCUS_EXPEND
    if _MAINTAIN_FOCUS.search(text):
        return FOCUS_MAINTAIN
    return FOCUS_NONE


@dataclass(frozen=True, slots=True)
class MartialBookEntry:
    key: str
    name: str
    sphere: str
    category: str
    description: str
    focus_usage: str = FOCUS_NONE
    enabled: bool = True

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (self.name, self.sphere, self.category, self.description)
        ).casefold()

    @property
    def focus_label(self) -> str:
        if self.focus_usage == FOCUS_EXPEND:
            return "Expends martial focus"
        if self.focus_usage == FOCUS_MAINTAIN:
            return "Requires martial focus"
        return "No martial-focus cost"


@dataclass(frozen=True, slots=True)
class MartialBookActionResult:
    changed: bool
    message: str


class MartialBookService:
    """Expose owned talents and bounded martial-focus spending."""

    def __init__(self, repository, character_id: int) -> None:
        self.repository = repository
        self.character_id = character_id

    def focus(self):
        return CharacterCalculationService(
            self.repository, self.character_id
        ).resolved_martial_focus()

    def entries(self) -> tuple[MartialBookEntry, ...]:
        result = []
        for talent in effective_martial_talents(self.repository, self.character_id):
            category = str(talent.catalog_category or talent.talent_type)
            if category in {"Base Sphere", "Drawback", "Tradition"}:
                continue
            catalog = martial_entry(talent.catalog_key) if talent.catalog_key else None
            automation = dict((catalog or {}).get("automation") or {})
            rules_text = "\n\n".join(
                value
                for value in (
                    talent.prerequisites,
                    talent.activation_note,
                    talent.notes,
                )
                if value
            )
            result.append(
                MartialBookEntry(
                    key=(
                        f"moldable:martial:{abs(talent.id)}"
                        if talent.id < 0 else f"martial:{talent.id}"
                    ),
                    name=(
                        f"{talent.name} — {talent.choice}"
                        if talent.choice else talent.name
                    ),
                    sphere=talent.sphere or "Other",
                    category=category or "Talent",
                    description=rules_text or "No description available.",
                    focus_usage=martial_focus_usage(
                        rules_text,
                        explicit=str(automation.get("focus_usage") or ""),
                    ),
                    enabled=bool(talent.enabled),
                )
            )
        return tuple(
            sorted(result, key=lambda item: (item.sphere.casefold(), item.name.casefold()))
        )

    def use_talent(self, key: str) -> MartialBookActionResult:
        entry = next((item for item in self.entries() if item.key == key), None)
        if entry is None or not entry.enabled or entry.focus_usage != FOCUS_EXPEND:
            return MartialBookActionResult(False, "That talent does not spend martial focus here.")
        focus = self.repository.get_martial_focus(self.character_id)
        if focus.current <= 0:
            return MartialBookActionResult(False, "No martial focus remains.")
        self.repository.update_martial_focus(replace(focus, current=focus.current - 1))
        return MartialBookActionResult(True, f"Used {entry.name} and expended martial focus.")
