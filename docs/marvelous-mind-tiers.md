# Mind charm item tiers

The designer offers a visible lesser/greater/powerful tier selector. Greater
adds the published +1 complexity; powerful adds +3 through a single dedicated
Powerful Charm contribution (+1 talent, +2 SP). That contribution is inserted
when needed and removed when selecting a lower tier. Other effect rows and
locked item text are preserved. Selecting powerful on a legacy contribution
supplies the required minimum costs without reducing larger manual values.
Charged item descriptions include greater Mind's required spell point even
though its complexity is a base conversion, not a talent row. Hallow's required
spell point is included the same way; powerful Mind's two points are not counted
twice. Multi-power charge accounting still explicitly requires review.

Thirty bundled ordinary charm talents have reviewed alternate-charm contribution
defaults: +1 complexity on their own row, with tier conversion paid separately.
Expanded Charm adds +1; Mass Charm adds +2 and projects the caster-level-scaled
target count. Creature-type limits and mind-affecting immunity remain explicit.

Suggestion's three tiers show their request restrictions, conditional saving-throw
penalties and hour-per-caster-level maximum duration, including early completion.
Its lesser once-per-target restriction is not confused with item daily uses.
Other selected charms use their catalog descriptions and explicitly request
duration/timing review; they do not inherit Suggestion's duration or requests.
Cloud/cognition conversions and multiple/alternative charm payloads do not get a
silently invented charm profile. Advanced and complex combinations remain open.

Legacy designs lacking an explicit tier retain their stored costs and previous
manual-review duration. Choosing a tier opts into the new calculation. No normal
spellcasting resources, known talents, character records or catalogs are changed
while previewing a design.

Validation: 1,266 shared rules/access/presentation tests, 312 designer UI tests and
105 item/resource/project/import/Moldable integration tests passed. The focused
Mind checks cover all 30 ordinary charm identities at each tier, exact prices,
prerequisite insertion, legacy/reopen behavior, locks and invalid combinations.
Parchment and Dark previews were inspected. No complete-application suite or
desktop/portable deployment was performed for this checkpoint.
Four final Charged-item cases and the focused Mind UI/rules checks passed after
the shared run; they cover the final charge-display and selector-label changes.

The full designer goal remains incomplete: per-charm duration/timing projections,
cloud/cognition/advanced Mind conversions, other unreviewed sphere costs, complex
combinations, material pricing and companion-access coverage still need work.

Sources:
- https://spheresofpower.wikidot.com/magical-items (Mind item conversions)
- https://spheresofpower.wikidot.com/mind (charm tiers and talents)

## Reviewed ordinary charm payloads

Confusion, Courage, Fear, Enthrall, Sleep and Mind Shield now have structured
duration and effect text for each tier. Courage uses the Ultimate sphere's
minute-per-level greater/powerful duration, not the older Core variant. Its lesser
effect lasts one fixed minute and benefits one roll. Sleep's lesser duration
remains `1d4 rounds`, not an average or a caster-level-scaled duration.

The item card projects scoped numerical bonuses and penalties, temporary HP,
partial-save consequences, waking rules, Enthrall's charm-versus-compulsion
distinction, and Mind Shield's willing-target and repeat-use rules. It does not
mutate a recipient or track turns, repeated saving throws, or waking attempts.
Courage is not assigned an invented Will save. Powerful Mind Shield's applicable
MSD remains an explicit use-time check rather than borrowing the crafter's MSD.

Fixed or rolled durations cannot silently use the ordinary per-level duration
ladder. Known scalable durations use the existing adjustments and price formula.
Unreviewed coexisting modifiers (for example Insanity) retain a duration-review
warning instead of inheriting an incorrect base duration. Legacy designs without
an explicit tier and all locked display fields retain their existing behavior.

Other ordinary charms, clouds, cognition and advanced interactions still need
dedicated payload/duration work; the full designer goal remains active.

Payload checkpoint validation: 1,281 shared rules/access/presentation tests,
313 designer UI tests and 105 item/resource/project/import/Moldable integration
tests passed. Final focused coverage passed 31 checks, with an additional live UI
check of duration-step/price agreement after the shared runs. Both supported
themes were visually inspected. No full application suite or desktop/portable
deployment was performed for this checkpoint.
