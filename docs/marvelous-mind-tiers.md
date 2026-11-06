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
