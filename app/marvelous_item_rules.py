"""Verified base Marvelous Item pricing; no catalog or persistence side effects.

Complexity is an already-resolved talent-based value, not a talent count.
Source: https://spheresofpower.wikidot.com/magical-items
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MarvelousItemPrice:
    market_price_gp: int
    save_dc: int
    daily_uses: int | None
    total_uses: int | None


def marvelous_item_price(caster_level: int, complexity: int, *, daily_uses: int = 1,
                         limited_uses: bool = False) -> MarvelousItemPrice:
    """Price the base effect, excluding optional traditions and costly components.

    Five daily uses means unlimited use; limited-use construction instead grants
    fifty total activations. Neither mode implies free spell-point resources.
    """
    for label, value in (("Caster level", caster_level), ("Complexity", complexity),
                         ("Daily uses", daily_uses)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{label} must be a positive integer.")
    if daily_uses > 5:
        raise ValueError("Use five daily uses for unlimited activation.")
    if limited_uses and daily_uses != 1:
        raise ValueError("Limited-total and daily-use construction cannot be combined.")
    base = 400 * caster_level * complexity
    return MarvelousItemPrice(
        base * 5 // 2 if limited_uses else base * daily_uses,
        10 + caster_level // 2,
        None if limited_uses or daily_uses == 5 else daily_uses,
        50 if limited_uses else None,
    )
