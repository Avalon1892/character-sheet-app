"""Named, data-only starting arrangements for the customizable sheet."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True, slots=True)
class SectionPlacement:
    page: str
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True)
class SheetLayoutPreset:
    key: str
    label: str
    character_types: frozenset[str]
    placements: dict[str, SectionPlacement]

    def presentation_state(self) -> dict[str, str]:
        if self.key == "factory" and not self.placements:
            return {}
        state = {"preset": self.key}
        if self.placements:
            state["freeform"] = json.dumps(
                {
                    key: placement.to_dict()
                    for key, placement in self.placements.items()
                },
                sort_keys=True,
            )
        return state


# Default Spheres uses the responsive code-defined composition.  Build Mode
# detaches these same blocks into freeform geometry only after the user asks to
# customize them.  Keeping the preset marker while omitting fixed coordinates
# makes new sheets fit the available viewport without weakening customization.
DEFAULT_SPHERES_PLACEMENTS: dict[str, SectionPlacement] = {}


SHEET_LAYOUT_PRESETS = {
    "factory": SheetLayoutPreset(
        "factory",
        "Default",
        frozenset({"Pathfinder 1e"}),
        {},
    ),
    "default_spheres": SheetLayoutPreset(
        "default_spheres",
        "Default Spheres",
        frozenset({"Spheres"}),
        DEFAULT_SPHERES_PLACEMENTS,
    ),
}


def layout_preset_for_character_type(character_type: str) -> SheetLayoutPreset:
    for preset in SHEET_LAYOUT_PRESETS.values():
        if character_type in preset.character_types:
            return preset
    return SHEET_LAYOUT_PRESETS["factory"]
