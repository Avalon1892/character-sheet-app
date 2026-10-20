# Fate conditional word item modes

The custom item designer now supports eighteen ordinary Fate words.
This update adds Align Object, Axe You a Question, Enmity, Malice, and
Villainy's marking-only modes through the existing cost and effect controls.

- Align Object distinguishes divine-focus and aligned-weapon choices.
- Axe retains size-dependent damage and its once-per-round repeated trigger.
- Enmity preserves consecutive, target-dependent alignment effects.
- Malice distinguishes attacker/victim and retaliation modes without guessing
  the applicable casting ability modifier.
- Villainy's repeatable paid ally support is not included in marking-only modes.

Conditional-word validation: 1,162 shared rules, access and presentation tests passed, plus all
six Fate UI tests. The focused conditional-mode group passed 22 checks.

## Metaphysical Cloak

All nine alignments are available in concentration and sustained-hour modes.
Eligibility uses one step on each alignment axis, not a single combined step.
The preview lists qualifying caster/user alignments without assuming the item
crafter is its eventual user. Unknown alignment is not treated as neutral.
The effect does not change actual alignment, actions or code of conduct.

Focused validation covers all 81 reference/selected alignment pairs, all 18
modes, exact prices, duration changes and saved selections. Operational use still
requires checking the applicable caster/user; no live alignment is changed.
The complete shared regression run passed 1,190 tests; all seven Fate UI tests
also passed. The complete application suite was not rerun.

Remaining Fate work includes native immediate-action words,
Hallow, repeated ally-support accounting, advanced effects and multi-motif
combinations. This is not complete all-sphere automation. No deployment was made.

Rules source: https://spheresofpower.wikidot.com/fate
