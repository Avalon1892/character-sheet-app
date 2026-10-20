# Fate word item modes

The custom item designer now has catalog-backed draft profiles and cost defaults
for all twenty-four ordinary Fate Word Talents. Operational automation is partial.
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

## Native immediate-action words

Bargain, Bless, Borrow Luck, Borrow Trouble, Conjunction and Curse now use their
native immediate timing by default, with one SP included in their contribution.
There is no swift-action surcharge for native timing. Explicit full-round, move
and swift construction adjustments retain their published costs.

The formula, card, editor label and saved-design interpretation share the timing
resolver. Stored `standard` continues to mean the default construction timing;
no schema change is needed. Mixed activations cannot accelerate a differently
timed power for free. Individual triggers and target eligibility still require
verification at use; the designer does not roll dice or apply live effects.
Shrieking Strike cannot contain a normally immediate word, even after an explicit
activation change. Instill Fate rejects concentration and normally immediate
words. Ordinary Shrieking Strike still requires a standard action or slower.

Validation: all twelve Marvelous-item modules passed 1,607 tests. The final
shared-rule run passed 1,220 tests, including thirteen compatibility cases added
after the full run began. This is not a complete-application test run.

Remaining Fate work includes
Hallow, repeated ally-support accounting, advanced effects and multi-motif
combinations. This is not complete all-sphere automation. No deployment was made.

Rules source: https://spheresofpower.wikidot.com/fate
