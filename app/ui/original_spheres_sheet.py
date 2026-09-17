"""Faithful four-page presentation of the original Spheres character sheet."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QFont, QFontMetricsF, QHelpEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QInputDialog,
    QScrollArea,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.database import CharacterRepository
from app.models import ALIGNMENTS, SIZES
from app.rules import class_bab
from app.services.sheet_presentation import (
    CharacterSheetSnapshot,
    build_character_sheet_snapshot,
)
from app.item_enchantments import item_market_price


ASSET_ROOT = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "sheet_types"
    / "original_spheres"
)


@dataclass(frozen=True, slots=True)
class PageText:
    x: float
    y: float
    width: float
    height: float
    text: str
    font_size: int = 13
    bold: bool = False
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft
    tooltip: str = ""
    edit_key: str = ""
    wrap: bool = False


def _text(
    x: float,
    y: float,
    width: float,
    height: float,
    value: object,
    *,
    size: int = 13,
    bold: bool = False,
    center: bool = False,
    tooltip: str = "",
    edit_key: str = "",
    wrap: bool = False,
) -> PageText:
    return PageText(
        x,
        y,
        width,
        height,
        str(value),
        size,
        bold,
        (
            Qt.AlignmentFlag.AlignCenter
            if center
            else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        ),
        tooltip,
        edit_key,
        wrap,
    )


def _signed(value: int, *, blank_zero: bool = False) -> str:
    if blank_zero and not value:
        return ""
    return f"{value:+d}"


def _weight(value: float) -> str:
    return f"{value:g}"


class OriginalSpheresPage(QWidget):
    edit_requested = Signal(str)

    def __init__(
        self,
        artwork: Path,
        logical_size: tuple[int, int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("originalSpheresArtworkPage")
        self.setFixedSize(*logical_size)
        self._artwork = QPixmap(str(artwork))
        self._items: tuple[PageText, ...] = ()

    def set_items(self, items: list[PageText]) -> None:
        self._items = tuple(items)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.drawPixmap(self.rect(), self._artwork)
        painter.setPen(Qt.GlobalColor.black)
        for item in self._items:
            font = QFont("Arial")
            font.setPixelSize(item.font_size)
            font.setBold(item.bold)
            painter.setFont(font)
            flags = item.alignment
            # The artwork uses compact, single-line cells.  Word wrapping made
            # even two-character numeric values take the multi-line layout path
            # in Qt, which shifts their apparent baseline at some display scale
            # factors.  Only opt into wrapping for a genuinely multi-line cell.
            if item.wrap:
                flags |= Qt.TextFlag.TextWordWrap
                painter.drawText(
                    QRectF(item.x, item.y, item.width, item.height),
                    int(flags),
                    item.text,
                )
                continue
            # Qt's flag-based single-line vertical alignment can move by one
            # or two device pixels at different Windows scale factors.  The
            # original sheet has very tight printed boxes, so position the
            # baseline from the actual glyph metrics and clip it to its cell.
            rect = QRectF(item.x, item.y, item.width, item.height)
            metrics = QFontMetricsF(font)
            text_width = metrics.horizontalAdvance(item.text)
            if item.alignment & Qt.AlignmentFlag.AlignHCenter:
                x = rect.center().x() - text_width / 2.0
            elif item.alignment & Qt.AlignmentFlag.AlignRight:
                x = rect.right() - text_width
            else:
                x = rect.left()
            baseline = rect.center().y() + (metrics.ascent() - metrics.descent()) / 2.0
            painter.save()
            painter.setClipRect(rect)
            painter.drawText(x, baseline, item.text)
            painter.restore()
        painter.end()
        super().paintEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            item = self._item_at(event.position().x(), event.position().y())
            if item is not None and (item.tooltip or item.edit_key):
                message = item.tooltip
                if item.edit_key:
                    message = (message + "\n\n" if message else "") + "Double-click to edit."
                QToolTip.showText(event.globalPos(), message, self)
                return True
        return super().event(event)

    def mouseDoubleClickEvent(self, event) -> None:
        item = self._item_at(event.position().x(), event.position().y())
        if item is not None and item.edit_key:
            self.edit_requested.emit(item.edit_key)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _item_at(self, x: float, y: float) -> PageText | None:
        for item in reversed(self._items):
            if QRectF(item.x, item.y, item.width, item.height).contains(x, y):
                return item
        return None


class OriginalSpheresSheetWidget(QWidget):
    """Original page geometry backed by the same repository and rule services."""

    character_renamed = Signal(int)

    def __init__(
        self, repository: CharacterRepository, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id: int | None = None
        self.snapshot: CharacterSheetSnapshot | None = None
        self.setObjectName("originalSpheresSheet")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.page_tabs = QTabWidget()
        self.page_tabs.setObjectName("originalSpheresPages")
        self.page_tabs.setDocumentMode(True)
        layout.addWidget(self.page_tabs)

        self.core_page = self._add_page(
            "1   CORE", ASSET_ROOT / "core.png", (1208, 1575)
        )
        self.inventory_page = self._add_page(
            "2   INVENTORY & FEATURES",
            ASSET_ROOT / "inventory.png",
            (1208, 1575),
        )
        self.spheres_page = self._add_page(
            "3   SPHERES", ASSET_ROOT / "spheres.png", (1208, 1575)
        )
        self.companion_page = self._add_page(
            "4   COMPANION", ASSET_ROOT / "companion.png", (1575, 1208)
        )
        for page in (
            self.core_page,
            self.inventory_page,
            self.spheres_page,
            self.companion_page,
        ):
            page.edit_requested.connect(self._edit_value)

    def _add_page(
        self, label: str, artwork: Path, logical_size: tuple[int, int]
    ) -> OriginalSpheresPage:
        page = OriginalSpheresPage(artwork, logical_size)
        scroll = QScrollArea()
        scroll.setObjectName("originalSpheresScroll")
        scroll.setWidget(page)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.page_tabs.addTab(scroll, label)
        return page

    def load_character(self, character_id: int) -> None:
        self.character_id = character_id
        self.refresh_all()

    def refresh_all(self) -> None:
        if self.character_id is None:
            return
        self.snapshot = build_character_sheet_snapshot(
            self.repository, self.character_id
        )
        self.core_page.set_items(self._core_items(self.snapshot))
        self.inventory_page.set_items(
            self._inventory_items(
                self.snapshot,
                self.repository.list_item_enchantments(self.character_id),
            )
        )
        self.spheres_page.set_items(self._spheres_items(self.snapshot))
        # Companion-specific rules data does not exist in the character model;
        # keeping the original fourth page blank is faithful and avoids inventing it.
        self.companion_page.set_items([])

    def _core_items(self, sheet: CharacterSheetSnapshot) -> list[PageText]:
        items = [
            _text(493, 133, 548, 22, sheet.summary.name, size=16, bold=True, edit_key="name"),
            _text(493, 170, 264, 18, sheet.details.race, edit_key="details:race"),
            _text(764, 170, 68, 18, sheet.details.size, center=True, edit_key="details:size"),
            _text(493, 205, 264, 18, sheet.details.deity, edit_key="details:deity"),
            _text(764, 205, 68, 18, sheet.details.alignment, center=True, edit_key="details:alignment"),
            _text(71, 229, 410, 20, sheet.details.player_name, edit_key="details:player_name"),
        ]
        for index, class_level in enumerate(sheet.classes[:4]):
            y = 257 + index * 36
            items.extend(
                (
                    _text(494, y, 303, 25, class_level.class_name, bold=True),
                    _text(806, y, 55, 25, sheet.casting.caster_level if index == 0 else "", center=True),
                    _text(868, y, 56, 25, class_bab(class_level), center=True),
                    _text(995, y, 52, 25, f"d{class_level.hit_die}" if class_level.hit_die else "", center=True),
                    _text(1055, y, 53, 25, class_level.level, center=True),
                )
            )

        ability_rows = (
            ("strength", 366),
            ("dexterity", 400),
            ("constitution", 434),
            ("intelligence", 468),
            ("wisdom", 502),
            ("charisma", 536),
        )
        for ability, y in ability_rows:
            result = sheet.abilities[ability]
            applied = [item for item in result.contributions if item.applied]
            enhancement = sum(item.value for item in applied if item.bonus_type == "enhancement")
            temporary = sum(item.value for item in applied if item.bonus_type == "temporary")
            misc = sum(
                item.value
                for item in applied
                if item.bonus_type not in {"base", "enhancement", "temporary"}
            )
            items.extend(
                (
                    _text(113, y, 40, 29, _signed(result.ability_modifier), size=14, bold=True, center=True),
                    _text(151, y, 51, 29, result.total, size=15, bold=True, center=True),
                    _text(213, y, 58, 29, sheet.base_abilities[ability], center=True, edit_key=f"ability:{ability}"),
                    _text(279, y, 60, 29, _signed(enhancement, blank_zero=True), center=True),
                    _text(347, y, 61, 29, _signed(misc, blank_zero=True), center=True),
                    _text(415, y, 61, 29, _signed(temporary, blank_zero=True), center=True),
                )
            )

        for index, skill in enumerate(sheet.skills):
            y = 660 + index * 19.45
            if y > 1368:
                break
            items.extend(
                (
                    _text(236, y, 18, 18, "X" if skill.state.class_skill else "", size=9, center=True),
                    _text(260, y, 37, 18, _signed(skill.result.total), size=11, bold=True, center=True, tooltip=skill.definition.name),
                    _text(336, y, 38, 18, skill.state.ranks or "", size=11, center=True),
                    _text(378, y, 39, 18, _signed(skill.state.misc_bonus, blank_zero=True), size=11, center=True),
                )
            )

        hp = sheet.hit_points
        combat = sheet.combat
        items.extend(
            (
                _text(496, 476, 61, 34, _signed(combat["initiative"].total), size=18, bold=True, center=True),
                _text(810, 486, 95, 30, f"{sheet.base_speed} ft", size=15, bold=True, center=True),
                _text(496, 548, 58, 31, sheet.displayed_hit_point_maximum, size=16, bold=True, center=True, edit_key="hp:maximum"),
                _text(701, 548, 92, 31, hp.current, size=16, bold=True, center=True, edit_key="hp:current"),
                _text(496, 584, 159, 28, hp.nonlethal, center=True, edit_key="hp:nonlethal"),
                _text(662, 584, 130, 28, hp.temporary, center=True, edit_key="hp:temporary"),
                _text(494, 688, 58, 35, combat["ac"].total, size=18, bold=True, center=True),
                _text(494, 738, 58, 35, combat["flat_footed_ac"].total, size=18, bold=True, center=True),
                _text(494, 785, 58, 35, combat["touch_ac"].total, size=18, bold=True, center=True),
                _text(494, 879, 58, 35, _signed(combat["fortitude"].total), size=16, bold=True, center=True),
                _text(494, 928, 58, 35, _signed(combat["reflex"].total), size=16, bold=True, center=True),
                _text(494, 976, 58, 35, _signed(combat["will"].total), size=16, bold=True, center=True),
                _text(494, 1131, 61, 34, _signed(combat["cmb"].total), size=17, bold=True, center=True),
                _text(494, 1180, 61, 34, combat["cmd"].total, size=17, bold=True, center=True),
            )
        )
        for index, condition in enumerate([item for item in sheet.conditions if item.enabled][:9]):
            items.append(
                _text(815, 864 + index * 22, 295, 21, condition.name, size=11, tooltip=condition.notes)
            )
        for index, attack in enumerate(sheet.attacks[:3]):
            y = 1280 + index * 66
            items.extend(
                (
                    _text(493, y, 278, 20, attack.record.name, size=11, bold=True, tooltip=attack.record.notes),
                    _text(776, y, 137, 20, _signed(attack.result.attack_bonus), size=11, center=True),
                    _text(917, y, 134, 20, attack.result.damage_display, size=11, center=True),
                    _text(1053, y, 55, 20, attack.record.attack_type, size=10, center=True),
                    _text(493, y + 25, 615, 18, attack.record.notes, size=10),
                )
            )
        items.extend(
            (
                _text(575, 1451, 56, 31, sheet.casting.spell_points_maximum, size=16, bold=True, center=True),
                _text(636, 1451, 82, 31, sheet.casting_profile.spell_points_current, center=True, edit_key="casting:spell_points_current"),
                _text(723, 1451, 63, 31, sheet.casting_profile.spell_points_temporary, center=True, edit_key="casting:spell_points_temporary"),
                _text(887, 1451, 67, 34, _signed(sheet.casting.magic_skill_bonus), size=17, bold=True, center=True),
                _text(959, 1451, 67, 34, sheet.casting.magic_skill_defense, size=17, bold=True, center=True),
            )
        )
        return items

    def _inventory_items(self, sheet: CharacterSheetSnapshot, enchantments=()) -> list[PageText]:
        items: list[PageText] = []
        for index, equipment in enumerate(sheet.equipment[:29]):
            y = 158 + index * 28.4
            items.extend(
                (
                    _text(89, y, 238, 22, equipment.name, size=11, tooltip=equipment.notes),
                    _text(
                        329, y, 54, 22,
                        f"{item_market_price(equipment, enchantments):g}",
                        size=10, center=True,
                    ),
                    _text(386, y, 51, 22, _weight(equipment.weight * equipment.quantity), size=10, center=True),
                )
            )

        sphere_records = [
            (record.name, record.notes)
            for record in sheet.spells
            if record.system == "Sphere"
        ] + [(record.name, record.notes) for record in sheet.martial_talents]
        for index, (name, notes) in enumerate(sphere_records[:22]):
            items.append(_text(445, 158 + index * 28.4, 338, 18, name, size=11, tooltip=notes))

        features = (
            [(record.name, record.notes) for record in sheet.feats]
            + [(record.name, record.notes) for record in sheet.traits]
            + [
                (feature.name, f"{feature.class_name} level {feature.level}\n{feature.description}")
                for feature in sheet.class_features
            ]
        )
        for index, (name, notes) in enumerate(features[:22]):
            items.append(_text(793, 158 + index * 28.4, 341, 18, name, size=11, tooltip=notes))

        drawback_lines = []
        if sheet.casting_profile.tradition_boons:
            drawback_lines.append("Boons: " + sheet.casting_profile.tradition_boons)
        if sheet.casting_profile.tradition_drawbacks:
            drawback_lines.append("Drawbacks: " + sheet.casting_profile.tradition_drawbacks)
        drawback_lines.extend(
            record.name
            for record in sheet.spells
            if "drawback" in record.catalog_category.casefold()
        )
        drawback_lines.extend(
            record.name
            for record in sheet.martial_talents
            if "drawback" in record.catalog_category.casefold()
        )
        for index, value in enumerate(drawback_lines[:6]):
            items.append(_text(445, 817 + index * 28, 687, 18, value, size=11))

        armor = next((item for item in sheet.equipment if item.category == "Armor"), None)
        shield = next((item for item in sheet.equipment if item.category == "Shield"), None)
        weapons = [item for item in sheet.equipment if item.category == "Weapon"]
        if armor:
            items.extend(
                (
                    _text(94, 1033, 200, 18, armor.name, size=11, bold=True, tooltip=armor.notes),
                    _text(94, 1068, 53, 18, armor.ac_bonus + armor.enhancement_bonus, size=10, center=True),
                    _text(150, 1068, 55, 18, armor.max_dex_bonus if armor.max_dex_bonus is not None else "", size=10, center=True),
                    _text(207, 1068, 55, 18, armor.armor_check_penalty, size=10, center=True),
                )
            )
        if shield:
            items.extend(
                (
                    _text(443, 1033, 205, 18, shield.name, size=11, bold=True, tooltip=shield.notes),
                    _text(556, 1068, 55, 18, shield.ac_bonus + shield.enhancement_bonus, size=10, center=True),
                    _text(614, 1068, 55, 18, shield.armor_check_penalty, size=10, center=True),
                )
            )
        for index, weapon in enumerate(weapons[:2]):
            y = 1108 + index * 88
            items.extend(
                (
                    _text(158, y, 480, 22, weapon.name, size=11, bold=True, tooltip=weapon.notes),
                    _text(94, y + 30, 50, 20, weapon.weapon_damage_type, size=10),
                    _text(146, y + 30, 55, 20, weapon.weapon_range, size=10),
                    _text(642, y + 30, 138, 20, weapon.weapon_damage_dice, size=10, center=True),
                )
            )

        worn = [
            item
            for item in sheet.equipment
            if item.state in {"worn", "armor", "shield"} or item.equipped
        ]
        for index, item in enumerate(worn[:16]):
            items.append(_text(850, 1019 + index * 28, 283, 22, item.name, size=11, tooltip=item.notes))

        capacity = sheet.carrying_capacity
        items.extend(
            (
                _text(101, 1328, 97, 31, _weight(capacity.light), center=True),
                _text(101, 1385, 97, 31, _weight(capacity.medium), center=True),
                _text(101, 1442, 97, 31, _weight(capacity.heavy), center=True),
                _text(345, 1470, 92, 24, _weight(sheet.total_weight), bold=True, center=True),
                _text(529, 1282, 236, 20, sheet.currency.copper, center=True, edit_key="currency:copper"),
                _text(529, 1304, 236, 20, sheet.currency.silver, center=True, edit_key="currency:silver"),
                _text(529, 1326, 236, 20, sheet.currency.gold, center=True, edit_key="currency:gold"),
                _text(529, 1348, 236, 20, sheet.currency.platinum, center=True, edit_key="currency:platinum"),
            )
        )
        return items

    def _spheres_items(self, sheet: CharacterSheetSnapshot) -> list[PageText]:
        profile = sheet.casting_profile
        casting = sheet.casting
        items = [
            _text(163, 136, 56, 32, casting.spell_points_maximum, size=16, bold=True, center=True),
            _text(283, 136, 79, 32, profile.spell_points_current, center=True, edit_key="casting:spell_points_current"),
            _text(367, 136, 91, 32, profile.spell_points_temporary, center=True, edit_key="casting:spell_points_temporary"),
            _text(190, 218, 45, 30, _signed(casting.casting_ability_modifier), size=16, bold=True, center=True),
            _text(321, 185, 56, 31, profile.casting_class_levels, center=True),
            _text(321, 220, 56, 31, casting.caster_level, center=True),
            _text(76, 300, 58, 34, casting.save_dc, size=17, bold=True, center=True),
            _text(76, 371, 58, 34, casting.save_dc, size=17, bold=True, center=True),
            _text(76, 449, 70, 39, _signed(casting.magic_skill_bonus), size=18, bold=True, center=True),
            _text(242, 449, 70, 39, casting.magic_skill_defense, size=18, bold=True, center=True),
            _text(76, 526, 70, 39, _signed(casting.concentration_bonus), size=18, bold=True, center=True),
            _text(227, 585, 46, 38, sheet.martial_focus.current, size=16, bold=True, center=True),
            _text(278, 585, 46, 38, sheet.martial_focus.maximum, size=16, bold=True, center=True),
        ]
        tradition_lines = [
            profile.tradition_name,
            profile.tradition_boons,
            profile.tradition_drawbacks,
            profile.tradition_notes,
        ]
        for index, value in enumerate(line for line in tradition_lines if line):
            items.append(_text(73, 692 + index * 50, 385, 37, value, size=11))

        implements = [
            item
            for item in sheet.equipment
            if "implement" in f"{item.name} {item.notes}".casefold()
            or "spell engine" in f"{item.name} {item.notes}".casefold()
        ]
        for index, item in enumerate(implements[:8]):
            items.append(_text(73, 1110 + index * 51, 385, 35, item.name, size=11, tooltip=item.notes))

        sphere_names = list(sheet.sphere_statistics)
        for index, sphere in enumerate(sphere_names[:8]):
            y = 127 + index * 182
            statistics = sheet.sphere_statistics[sphere]
            sphere_spells = [
                spell
                for spell in sheet.spells
                if spell.system == "Sphere" and spell.school_or_sphere == sphere
            ]
            items.extend(
                (
                    _text(474, y + 6, 285, 24, sphere, size=14, bold=True),
                    _text(771, y + 38, 56, 31, statistics.save_dc, size=16, bold=True, center=True),
                    _text(771, y + 135, 56, 31, statistics.caster_level, size=16, bold=True, center=True),
                )
            )
            talents = [
                spell
                for spell in sphere_spells
                if spell.catalog_category != "Base Sphere"
            ]
            for talent_index, talent in enumerate(talents[:10]):
                column = 0 if talent_index < 5 else 1
                row = talent_index if talent_index < 5 else talent_index - 5
                x = 474 if column == 0 else 832
                items.append(
                    _text(
                        x,
                        y + 47 + row * 30,
                        288,
                        18,
                        talent.name,
                        size=10,
                        tooltip=talent.notes,
                    )
                )
        return items

    def _edit_value(self, key: str) -> None:
        if self.character_id is None or self.snapshot is None:
            return
        sheet = self.snapshot
        if key == "name":
            value, accepted = QInputDialog.getText(
                self, "Character name", "Name", text=sheet.summary.name
            )
            if accepted and value.strip():
                self.repository.rename_character(self.character_id, value)
                self.character_renamed.emit(self.character_id)
        elif key.startswith("details:"):
            field = key.split(":", 1)[1]
            current = str(getattr(sheet.details, field))
            if field == "size":
                options = list(SIZES)
                value, accepted = QInputDialog.getItem(
                    self,
                    "Size",
                    "Size",
                    options,
                    options.index(current) if current in options else 0,
                    False,
                )
            elif field == "alignment":
                options = list(ALIGNMENTS)
                value, accepted = QInputDialog.getItem(
                    self,
                    "Alignment",
                    "Alignment",
                    options,
                    options.index(current) if current in options else 0,
                    False,
                )
            else:
                value, accepted = QInputDialog.getText(
                    self, field.replace("_", " ").title(), field.replace("_", " ").title(), text=current
                )
            if accepted:
                self.repository.update_character_details(replace(sheet.details, **{field: value}))
        elif key.startswith("ability:"):
            ability = key.split(":", 1)[1]
            value, accepted = QInputDialog.getInt(
                self,
                ability.title(),
                "Base score",
                sheet.base_abilities[ability],
                1,
                99,
            )
            if accepted:
                self.repository.update_ability_score(self.character_id, ability, value)
        elif key.startswith("hp:"):
            field = key.split(":", 1)[1]
            current = (
                sheet.displayed_hit_point_maximum
                if field == "maximum"
                else int(getattr(sheet.hit_points, field))
            )
            value, accepted = QInputDialog.getInt(
                self,
                "Hit Points",
                field.title(),
                current,
                -999 if field == "current" else 0,
                9999,
            )
            if accepted:
                hp = sheet.hit_points
                if field == "maximum":
                    hp = replace(hp, maximum=value, auto_calculate=False)
                else:
                    hp = replace(hp, **{field: value})
                self.repository.update_hit_points(hp)
        elif key.startswith("casting:"):
            field = key.split(":", 1)[1]
            current = int(getattr(sheet.casting_profile, field))
            value, accepted = QInputDialog.getInt(
                self, "Spell Points", field.replace("_", " ").title(), current, 0, 9999
            )
            if accepted:
                self.repository.update_casting_profile(
                    replace(sheet.casting_profile, **{field: value})
                )
        elif key.startswith("currency:"):
            field = key.split(":", 1)[1]
            current = int(getattr(sheet.currency, field))
            value, accepted = QInputDialog.getInt(
                self, "Currency", field.title(), current, 0, 999999999
            )
            if accepted:
                self.repository.update_currency_purse(
                    replace(sheet.currency, **{field: value})
                )
        self.refresh_all()
