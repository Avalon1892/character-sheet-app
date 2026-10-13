"""Verified base Marvelous Item pricing; no catalog or persistence side effects.

Complexity is an already-resolved talent-based value, not a talent count.
Source: https://spheresofpower.wikidot.com/magical-items
"""
from dataclasses import dataclass
from fractions import Fraction
from math import ceil

from app.crafting_rules import CraftingQuote


@dataclass(frozen=True)
class MarvelousItemPrice:
    market_price_gp: Fraction
    save_dc: int
    daily_uses: int | None
    total_uses: int | None


@dataclass(frozen=True)
class MarvelousRequirements:
    blockers: tuple[str, ...]
    bypassed: tuple[str, ...]
    dc_increase: int

    @property
    def eligible(self):
        return not self.blockers


def marvelous_requirements(*, caster_level, sphere_levels, feats, required_spheres,
                            required_talents=(), available_talents=(),
                            advanced_talents=(), protected_requirements=(),
                            available_requirements=(), prohibited_abilities=()):
    """Evaluate explicitly supplied crafting access, independently of Qt.

    Sphere levels must exclude temporary bonuses. Cooperative sources must be
    available for the entire construction period. Advanced talents and protected
    class requirements are never waived. Versatile Crafter can waive base spheres
    and each missing caster level, but not a tradition's prohibited abilities.
    """
    if isinstance(caster_level, bool) or not isinstance(caster_level, int) or caster_level < 1:
        raise ValueError("Item caster level must be a positive integer.")
    levels = {name.casefold(): value for name, value in sphere_levels.items()}
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in levels.values()):
        raise ValueError("Permanent sphere levels must be nonnegative integers.")
    known_feats = {name.casefold() for name in feats}
    known_talents = {name.casefold() for name in available_talents}
    advanced = {name.casefold() for name in advanced_talents}
    requirements = {name.casefold() for name in available_requirements}
    versatile = "versatile crafter" in known_feats
    blockers, bypassed = [], []
    dc_increase = 0
    if not known_feats.intersection({"craft marvelous item", "craft wondrous item"}):
        blockers.append("Requires Craft Marvelous Item (or Craft Wondrous Item).")
    spheres = {name.casefold(): name for name in required_spheres}
    if not spheres or any(not name.strip() for name in spheres):
        raise ValueError("At least one base sphere is required.")
    for sphere in spheres.values():
        level = levels.get(sphere.casefold(), 0)
        if level == 0:
            message = f"Missing base sphere: {sphere}"
            (bypassed if versatile else blockers).append(message)
            if versatile:
                dc_increase += 5
        deficit = max(0, caster_level - level)
        if deficit:
            message = f"{sphere}: permanent caster level {level}, requires {caster_level}"
            (bypassed if versatile else blockers).append(message)
            if versatile:
                dc_increase += 5 * deficit
    for talent in {name.casefold(): name for name in required_talents}.values():
        if talent.casefold() in known_talents:
            continue
        message = f"Missing talent: {talent}"
        if talent.casefold() in advanced:
            blockers.append(message)
        else:
            bypassed.append(message)
            dc_increase += 5
    blockers.extend(f"Missing required feature: {name}" for name in protected_requirements
                    if name.casefold() not in requirements)
    blockers.extend(f"Casting tradition prohibits: {name}" for name in prohibited_abilities)
    return MarvelousRequirements(tuple(blockers), tuple(bypassed), dc_increase)


def marvelous_item_price(caster_level: int, complexity: int | Fraction, *, daily_uses: int = 1,
                         limited_uses: bool = False) -> MarvelousItemPrice:
    """Price the base effect, excluding optional traditions and costly components.

    Five daily uses means unlimited use; limited-use construction instead grants
    fifty total activations. Neither mode implies free spell-point resources.
    """
    for label, value in (("Caster level", caster_level), ("Daily uses", daily_uses)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{label} must be a positive integer.")
    if isinstance(complexity, bool) or not isinstance(complexity, (int, Fraction)) or complexity < 1:
        raise ValueError("Complexity must be an exact value of at least one.")
    if complexity > caster_level:
        raise ValueError("Item caster level must be at least its complexity.")
    if daily_uses > 5:
        raise ValueError("Use five daily uses for unlimited activation.")
    if limited_uses and daily_uses != 1:
        raise ValueError("Limited-total and daily-use construction cannot be combined.")
    base = Fraction(400 * caster_level * complexity)
    return MarvelousItemPrice(
        base * Fraction(5, 2) if limited_uses else base * daily_uses,
        10 + caster_level // 2,
        None if limited_uses or daily_uses == 5 else daily_uses,
        50 if limited_uses else None,
    )


def effect_complexity(*, talent_costs=(), alternative_costs=(), range_steps=0,
                      duration_steps=0, activation="standard", unique_changes=0):
    """Resolve explicit construction contributions, never infer them from prose.

    Talent costs include the talent's own complexity and extra spell points.
    Alternative costs represent mutually exclusive options: the largest is paid
    in full and the others at half cost. Sphere-specific exceptions must supply
    their published costs rather than the general one-point talent default.
    """
    activation_cost = {"standard": 0, "full-round": -1, "move": 3, "swift": 5}
    if activation not in activation_cost:
        raise ValueError("Unsupported activation time.")
    for value in (range_steps, duration_steps, unique_changes):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Construction steps must be integers.")
    costs = tuple(talent_costs)
    alternatives = tuple(alternative_costs)
    for value in (*costs, *alternatives):
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)) or value < 0:
            raise ValueError("Effect contributions must be nonnegative exact values.")
    variable = (sum(alternatives) + max(alternatives)) / Fraction(2) if alternatives else 0
    return max(Fraction(1), Fraction(1 + sum(costs) + variable + range_steps
                                   + 2 * duration_steps + activation_cost[activation]
                                   + unique_changes))


def marvelous_crafting_quote(price: MarvelousItemPrice, caster_level: int, *,
                              missing_talents=0, adventuring=False,
                              distracting=False, requirements=None) -> CraftingQuote:
    """Spheres construction estimate; prerequisite eligibility is checked separately.

    Missing ordinary talents can raise the DC. Base spheres, advanced talents,
    creation feats and protected class requirements cannot use this bypass.
    Adventuring already includes distractions; do not apply both penalties.
    """
    for value in (caster_level, missing_talents):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Crafting values must be nonnegative integers.")
    if caster_level < 1 or price.market_price_gp <= 0:
        raise ValueError("Caster level and price must be positive.")
    if requirements is not None:
        if missing_talents:
            raise ValueError("Use the validated requirements, not a second missing-talent count.")
        if not requirements.eligible:
            raise ValueError("Construction requirements are not met: " + "; ".join(requirements.blockers))
    dc_increase = requirements.dc_increase if requirements is not None else 5 * missing_talents
    days = max(1, ceil(price.market_price_gp / 1000))
    days *= 4 if adventuring else 2 if distracting else 1
    return CraftingQuote(price.market_price_gp / 2, 10 + caster_level + dc_increase,
                         days, "One item per day; materials paid at the start. Missing base spheres and advanced talents cannot be bypassed.")
