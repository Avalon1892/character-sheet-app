"""Default visible columns for the built-in sheet blocks.

These profiles affect presentation only.  Full rules data stays in the saved
record, edit dialog, hover text, and details panel.  New sheet types can define
different profiles without changing repositories or automation.
"""

from __future__ import annotations

from app.feature_registry import FeatureKind
from app.ui.components import TableColumn


FEATURE_TABLE_COLUMNS: dict[FeatureKind, tuple[TableColumn, ...]] = {
    FeatureKind.FEAT: (
        TableColumn("Feat", stretch=True),
        TableColumn("Type", 180),
    ),
    FeatureKind.TRAIT: (
        TableColumn("Trait", stretch=True),
        TableColumn("Type", 145),
    ),
    FeatureKind.MARTIAL_TALENT: (
        TableColumn("Talent", stretch=True),
        TableColumn("Sphere", 95),
        TableColumn("Type", 115),
    ),
}


MAGIC_RECORD_COLUMNS = (
    TableColumn("Name", 120),
    TableColumn("Spell Cost", 72),
    TableColumn("ACTION", 68),
    TableColumn("Description", stretch=True),
    TableColumn("Sphere", 70),
    TableColumn("Duration", 78),
    TableColumn("Range", 90),
    TableColumn("Save", 65),
    TableColumn("SR", 34),
)


TRADITIONAL_SPELL_COLUMNS = (
    TableColumn("Spell", stretch=True),
    TableColumn("Spell Level", 78),
    TableColumn("School", 135),
    TableColumn("Casting Time", 105),
    TableColumn("Range", 125),
)


SPELL_SLOT_COLUMNS = (
    TableColumn("Class", stretch=True),
    TableColumn("Level", 55),
    TableColumn("Available", 72),
    TableColumn("Prepared", 72),
    TableColumn("Open", 55),
)


PREPARED_SPELL_COLUMNS = (
    TableColumn("Spell", stretch=True),
    TableColumn("Class", 120),
    TableColumn("Level", 55),
    TableColumn("Prepared", 72),
    TableColumn("Remaining", 78),
    TableColumn("Source", 72),
)


EQUIPMENT_RECORD_COLUMNS = (
    TableColumn("Item", stretch=True),
    TableColumn("State / Slot", 105),
    TableColumn("Qty", 42),
    TableColumn("Value / Weight", 100),
    TableColumn("Defense / Notes", 150),
)


WORN_RECORD_COLUMNS = (
    TableColumn("Slot", 90),
    TableColumn("Item", stretch=True),
    TableColumn("Weight", 68),
    TableColumn("Bonus / Notes", 170),
)
