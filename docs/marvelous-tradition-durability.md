# Crafting-tradition item durability

The designer accepts optional pre-tradition hardness and maximum item HP under
Item settings. These inputs describe the physical item, including any other
adjustments the user has already included; the designer does not infer material,
thickness, enhancement bonus, or character HP.

The shared rules calculation applies Resilient to City Construction and Evil
Artifice: hardness +2 and maximum item HP multiplied by 1.25, rounded down with
a minimum of 1. Diviner's Sight and the published Fragile drawback halve both
values, rounded down. Repeated copies do not halve the same value repeatedly.
Custom drawbacks with the same name do not acquire this automation. Fragile and
Resilient remain incompatible.

Unknown inputs remain unknown. The calculated durability and its explanation
appear in the live item description; a locked description stays locked. The
stored blueprint retains the original inputs, so reopening or changing tradition
does not compound the adjustment. Durability itself adds no new price modifier.
There is no item-damage, repair-calendar, critical-hit rolling, or character-HP
mutation in this feature.

Coverage includes exact rounding, partial/unspecified inputs, invalid values,
published versus custom identities, conflicts, live updates, display locks, atomic
invalid-plan rejection, and actual inventory save/reopen.

Validation passed: 1,253 shared rules/access/presentation tests, 311 designer UI
tests and 105 item/resource/project/import/Moldable integration tests. The final
focused durability/compatibility run passed 16 tests. Parchment and Dark previews
were inspected. No full application suite or desktop/portable deployment was
performed for this checkpoint.

The overall designer goal is not complete. Remaining work includes unreviewed
sphere cost/mode conversions, complex effect combinations, companion access,
and special-material/tradition pricing that still lacks sufficient inputs.

Sources:
- https://spheresofpower.wikidot.com/magical-items (Resilient, Fragile and sample traditions)
- https://legacy.aonprd.com/coreRulebook/gettingStarted.html (rounding)
