from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

from app.custom_trackers import CustomTrackerResolver
from app.database import CharacterRepository
from app.models import ABILITIES, SKILLS
from app.rules import total_bab
from app.services.character_calculations import CharacterCalculationService


Getter = Callable[[CharacterRepository, int], Any]
Setter = Callable[[CharacterRepository, int, Any], None]


@dataclass(frozen=True, slots=True)
class BindingDescriptor:
    key: str
    name: str
    value_type: str
    getter: Getter
    setter: Setter | None = None
    category: str = "Character"

    @property
    def editable(self) -> bool:
        return self.setter is not None


class BindingRegistry:
    def __init__(self) -> None:
        self._items: dict[str, BindingDescriptor] = {}

    def register(self, descriptor: BindingDescriptor) -> None:
        if not descriptor.key or descriptor.key in self._items:
            raise ValueError(f"Duplicate or empty binding: {descriptor.key}")
        self._items[descriptor.key] = descriptor

    def get(self, key: str) -> BindingDescriptor | None:
        return self._items.get(key)

    def all(self, repository: CharacterRepository | None = None, character_id: int | None = None) -> tuple[BindingDescriptor, ...]:
        dynamic: list[BindingDescriptor] = []
        if repository is not None and character_id is not None:
            for tracker in repository.list_custom_trackers(character_id):
                if tracker.tracker_type == "calculated":
                    dynamic.append(BindingDescriptor(
                        f"trackers.{tracker.key}.value", tracker.name, "number",
                        lambda repo, cid, key=tracker.key: CustomTrackerResolver(repo, cid).resolve_tracker(key).value,
                        category="Custom trackers",
                    ))
                else:
                    dynamic.extend((
                        BindingDescriptor(
                            f"trackers.{tracker.key}.current", f"{tracker.name} — Current", "number",
                            lambda repo, cid, tracker_id=tracker.id: next(item.current_value for item in repo.list_custom_trackers(cid) if item.id == tracker_id),
                            lambda repo, cid, value, tracker_id=tracker.id: repo.set_custom_tracker_values(cid, tracker_id, current_value=float(value)),
                            "Custom trackers",
                        ),
                        BindingDescriptor(
                            f"trackers.{tracker.key}.temporary", f"{tracker.name} — Temporary", "number",
                            lambda repo, cid, tracker_id=tracker.id: next(item.temporary_value for item in repo.list_custom_trackers(cid) if item.id == tracker_id),
                            lambda repo, cid, value, tracker_id=tracker.id: repo.set_custom_tracker_values(cid, tracker_id, temporary_value=float(value)),
                            "Custom trackers",
                        ),
                    ))
        return tuple(sorted((*self._items.values(), *dynamic), key=lambda item: (item.category.casefold(), item.name.casefold())))

    def resolve(self, repository: CharacterRepository, character_id: int, key: str) -> Any:
        descriptor = self.get(key)
        if descriptor is None:
            descriptor = next((item for item in self.all(repository, character_id) if item.key == key), None)
        if descriptor is None:
            raise KeyError(f"Unknown binding: {key}")
        return descriptor.getter(repository, character_id)

    def write(self, repository: CharacterRepository, character_id: int, key: str, value: Any) -> None:
        descriptor = self.get(key)
        if descriptor is None:
            descriptor = next((item for item in self.all(repository, character_id) if item.key == key), None)
        if descriptor is None:
            raise KeyError(f"Unknown binding: {key}")
        if descriptor.setter is None:
            raise ValueError(f"Binding is read-only: {key}")
        descriptor.setter(repository, character_id, value)


BINDINGS = BindingRegistry()


def _ability_score(ability: str) -> Getter:
    return lambda repo, cid: CharacterCalculationService(repo, cid).ability_result(ability).total


def _ability_modifier(ability: str) -> Getter:
    return lambda repo, cid: CharacterCalculationService(repo, cid).ability_result(ability).ability_modifier


for ability, name, _code in ABILITIES:
    BINDINGS.register(BindingDescriptor(
        f"abilities.{ability}.score", f"{name} score", "number", _ability_score(ability),
        lambda repo, cid, value, key=ability: repo.update_ability_score(cid, key, int(value)),
        "Abilities",
    ))
    BINDINGS.register(BindingDescriptor(
        f"abilities.{ability}.modifier", f"{name} modifier", "number", _ability_modifier(ability),
        category="Abilities",
    ))


def _hp(field: str) -> Getter:
    return lambda repo, cid: getattr(repo.get_hit_points(cid), field)


def _set_hp(field: str) -> Setter:
    return lambda repo, cid, value: repo.update_hit_points(replace(repo.get_hit_points(cid), **{field: int(value)}))


for field, label in (
    ("maximum", "Hit Points — Maximum"),
    ("current", "Hit Points — Current"),
    ("temporary", "Hit Points — Temporary"),
    ("nonlethal", "Hit Points — Nonlethal"),
):
    BINDINGS.register(BindingDescriptor(f"hit_points.{field}", label, "number", _hp(field), _set_hp(field), "Health"))


def _casting_statistics(repo: CharacterRepository, cid: int):
    sequence = repo.get_prodigy_sequence(cid)
    return CharacterCalculationService(
        repo, cid, sequence_active=sequence.active, sequence_links=sequence.current,
    ).casting_statistics()


def _spell_points(field: str) -> Getter:
    def getter(repo: CharacterRepository, cid: int):
        profile = repo.get_casting_profile(cid)
        if field == "maximum":
            return _casting_statistics(repo, cid).spell_points_maximum
        return getattr(profile, f"spell_points_{field}")
    return getter


def _set_spell_points(field: str) -> Setter:
    return lambda repo, cid, value: repo.update_casting_profile(
        replace(repo.get_casting_profile(cid), **{f"spell_points_{field}": int(value)})
    )


for field in ("maximum", "current", "temporary"):
    BINDINGS.register(BindingDescriptor(
        f"spell_points.{field}", f"Spell Points — {field.title()}", "number",
        _spell_points(field), None if field == "maximum" else _set_spell_points(field), "Resources",
    ))

for field in ("maximum", "current"):
    BINDINGS.register(BindingDescriptor(
        f"martial_focus.{field}", f"Martial Focus — {field.title()}", "number",
        lambda repo, cid, key=field: getattr(repo.get_martial_focus(cid), key),
        lambda repo, cid, value, key=field: repo.update_martial_focus(
            replace(repo.get_martial_focus(cid), **{key: int(value)})
        ),
        "Resources",
    ))

BINDINGS.register(BindingDescriptor(
    "character.level", "Total character level", "number",
    lambda repo, cid: sum(item.level for item in repo.list_class_levels(cid)), category="Character",
))

for target, label in (
    ("initiative", "Initiative"),
    ("ac", "Armor Class"),
    ("flat_footed_ac", "Flat-footed Armor Class"),
    ("touch_ac", "Touch Armor Class"),
    ("fortitude", "Fortitude save"),
    ("reflex", "Reflex save"),
    ("will", "Will save"),
    ("cmb", "Combat Maneuver Bonus"),
    ("cmd", "Combat Maneuver Defense"),
):
    BINDINGS.register(BindingDescriptor(
        f"combat.{target}", label, "number",
        lambda repo, cid, key=target: CharacterCalculationService(repo, cid).combat_results()[key].total,
        category="Combat",
    ))


def _skill_ranks(skill_key: str) -> Getter:
    return lambda repo, cid: repo.list_skill_states(cid)[skill_key].ranks


def _set_skill_ranks(skill_key: str) -> Setter:
    return lambda repo, cid, value: repo.update_skill_state(
        cid,
        replace(repo.list_skill_states(cid)[skill_key], ranks=int(value)),
    )


for skill in SKILLS:
    BINDINGS.register(BindingDescriptor(
        f"skills.{skill.key}.total", f"{skill.name} — Total", "number",
        lambda repo, cid, key=skill.key: CharacterCalculationService(repo, cid).skill_result(key).total,
        category="Skills",
    ))
    BINDINGS.register(BindingDescriptor(
        f"skills.{skill.key}.ranks", f"{skill.name} — Ranks", "number",
        _skill_ranks(skill.key), _set_skill_ranks(skill.key), "Skills",
    ))
BINDINGS.register(BindingDescriptor(
    "character.bab", "Base attack bonus", "number",
    lambda repo, cid: total_bab(repo.list_class_levels(cid)), category="Character",
))
BINDINGS.register(BindingDescriptor(
    "favored_class.hp", "Favored class — HP", "number",
    lambda repo, cid: sum(item.hp_bonus for item in repo.list_favored_class_bonuses(cid).values()),
    category="Character",
))
BINDINGS.register(BindingDescriptor(
    "favored_class.skill_points", "Favored class — Skill points", "number",
    lambda repo, cid: sum(item.skill_point_bonus for item in repo.list_favored_class_bonuses(cid).values()),
    category="Character",
))
for mode, label in (
    ("land_speed", "Land speed"),
    ("armor_speed", "Speed with armor"),
    ("fly_speed", "Fly speed"),
    ("swim_speed", "Swim speed"),
    ("climb_speed", "Climb speed"),
    ("burrow_speed", "Burrow speed"),
    ("teleport_speed", "Teleport distance"),
):
    BINDINGS.register(BindingDescriptor(
        f"movement.{mode}", label, "number",
        lambda repo, cid, key=mode: CharacterCalculationService(repo, cid).movement_results()[key],
        lambda repo, cid, value, key=mode: repo.update_movement_profile(
            replace(repo.get_movement_profile(cid), **{key: int(value)})
        ),
        "Movement",
    ))
BINDINGS.register(BindingDescriptor(
    "casting.caster_level", "Effective caster level", "number",
    lambda repo, cid: _casting_statistics(repo, cid).caster_level,
    category="Magic",
))


def _rows(*columns: str, source: Callable[[CharacterRepository, int], list]) -> Getter:
    def getter(repo: CharacterRepository, cid: int):
        return {"columns": list(columns), "rows": source(repo, cid)}
    return getter


BINDINGS.register(BindingDescriptor(
    "table.skills", "Skills table", "table",
    _rows("Skill", "Ranks", "Class", source=lambda repo, cid: [
        [state.name, state.ranks, "Yes" if state.class_skill else ""]
        for state in repo.list_skill_states(cid).values()
    ]), category="Tables",
))
BINDINGS.register(BindingDescriptor(
    "table.feats", "Feats table", "table",
    _rows("Feat", "Active", source=lambda repo, cid: [[item.name, "Yes" if item.enabled else "No"] for item in repo.list_feats(cid)]), category="Tables",
))
BINDINGS.register(BindingDescriptor(
    "table.traits", "Traits table", "table",
    _rows("Trait", "Active", source=lambda repo, cid: [[item.name, "Yes" if item.enabled else "No"] for item in repo.list_traits(cid)]), category="Tables",
))
BINDINGS.register(BindingDescriptor(
    "table.equipment", "Equipment table", "table",
    _rows("Item", "Qty", "Equipped", source=lambda repo, cid: [[item.name, item.quantity, "Yes" if item.equipped else "No"] for item in repo.list_equipment(cid)]), category="Tables",
))
