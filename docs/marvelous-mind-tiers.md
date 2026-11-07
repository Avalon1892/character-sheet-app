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

## Additional emotion and truthfulness profiles

Calm, Candor, Flabbergast and Incense now project their three tiers into the live
item card. Calm keeps its suppression (not dispelling), defensive exception and
early-ending conditions. Flabbergast and Incense distinguish their full-duration
conditions from the fixed one-minute or one-round successful-save consequences.
Candor distinguishes truthful speech from compelled answers. Powerful Candor
shows a single-question effect and a repeat restriction based on the recipient's
Wisdom score, without substituting the crafter's score or inventing a duration.
Its duration cannot use the ordinary per-caster-level adjustment ladder.

These projections reuse the existing tier costs, prerequisite row, live quote and
locked-field behavior. They do not apply conditions to a recipient or add clocks.
Twenty other ordinary charms, clouds, cognition and advanced/modifier interactions
still need reviewed profiles. Other sphere-cost, tradition/material, complex
combination and companion-access gaps remain; this is not completion of the full
custom designer goal.

Source: https://spheresofpower.wikidot.com/mind (Ultimate charm descriptions).

## Communication, protection and sensory profiles

Innocence, Recommend, Speechless, Utterances, Vision and Wrack now have reviewed
tier-specific payloads and durations. Recommend and Utterances project their own
caster-level breakpoints. Recommend keeps its real-risk and next-turn trigger;
Utterances keeps range, extra-save, verbal-component and actual-user skill-rank
restrictions explicit. Innocence distinguishes emotion/fear penalty conversion
from ignored severance penalties and does not manufacture a target-dependent bonus.

Speechless shows the published day-per-level greater/powerful duration without
adding days to the ordinary construction-duration ladder. Language selection and
selective word/subject restrictions remain use-time decisions. Spellcasting is
not suppressed, and telepathic interference does not become generic immunity to
mental attacks. Innocence, Recommend and Speechless do not invent saving throws
absent from their individual published text.

Vision preserves its sense/subject limits, unfamiliar-stimulus and invisibility
prohibitions, pain-save bonus and repeat saves. Wrack separates its one-round stun
from its round-per-level nausea and successful-save sickness. No target records,
resources, rounds or days are tracked or changed by these item-card projections.

Sixteen of the thirty bundled ordinary charms now have dedicated profiles. The
fourteen remaining are Amnesia, Cerebral Strike, Command, Disrupt Focus, Esteem,
Fascinate, Gestures, Hostility, Inception, Inspiration, Mind Spy, Paralyze, Project
Thoughts and Read Mind. Clouds, cognition, advanced/modifier interactions and the
broader sphere-cost, tradition/material, combination and companion-access gaps
remain open. The full designer goal is not complete; no deployment is included.

Sources:
- https://spheresofpower.wikidot.com/mind (Ultimate charm descriptions)
- https://legacy.aonprd.com/coreRulebook/gettingStarted.html (default rounding)

## Control, concentration and telepathy profiles

Command, Disrupt Focus, Gestures, Paralyze, Project Thoughts and Read Mind now
have dedicated tier profiles. Command preserves its next-turn lesser action,
bounded concentration, action limits and free-action repeat saves. Paralyze uses
a fixed one-round lesser duration and full-round repeat-save actions for its
stronger tiers, rather than conflating those saves with Command's free action.
Disrupt Focus calculates its duration floor and the known part of its
concentration DC while leaving the invoking user's casting modifier explicit.
Its lesser/greater early-ending rule does not incorrectly end the powerful tier.

Gestures projects somatic failure and skill penalties, plus held-versus-worn
object restrictions, trip substitutions and the actual participants' attack of
opportunity limits. It does not borrow the crafter's capabilities or introduce
round tracking. Project Thoughts and Read Mind preserve word/language limits,
voluntary replies, unwilling-target saves, repeat-question behavior and their
explicit repeatable lesser-charm exceptions. The item's own daily uses remain a
separate resource.

Single messages/readings and concentration-bounded effects do not inherit a
generic per-level duration or an adjustable construction-duration ladder. A
lesser emotional-state reading has no sustained duration invented for it.
Existing locks, saved drafts and tier complexity arithmetic are unchanged.

Twenty-two bundled ordinary charms now have profiles. The eight remaining are
Amnesia, Cerebral Strike, Esteem, Fascinate, Hostility, Inception, Inspiration and
Mind Spy. Inspiration's native immediate trigger requires item-activation rules
verification: the Mind construction entry does not explicitly repeat Fate's
native-word casting-time exception, so this checkpoint does not grant it for
free. Clouds, cognition, advanced/modifier interactions and the broader designer
gaps listed above remain open. No full-goal completion or deployment is claimed.

Sources:

- https://spheresofpower.wikidot.com/mind (Ultimate charm descriptions)
- https://spheresofpower.wikidot.com/magical-items (Mind versus Fate conversions)

## Memory, influence and sensory-link profiles

Amnesia, Inception, Esteem, Fascinate, Hostility and Mind Spy now have dedicated
tier profiles. Memory alteration does not silently become an hour-per-level
Suggestion effect or a paid permanency adjustment. Amnesia shows the affected
memory window separately; Inception preserves original memories, belief checks,
contradictory-evidence saves and resistance modifiers. Restoration text follows
the Ultimate descriptions, including Restore Senses in the powerful-tier Life
Break Enchantment paths, rather than substituting the older Core wording.

Esteem calculates its single-check competence bonus and its 1 + CL/5 hour/day
window, detection DC and per-target daily/weekly limits. It does not grant a
bonus to every check or reduce the item's daily uses to the per-target limit.
Fascinate distinguishes damage ending the greater charm from damage permitting
a new save against the powerful charm. Hostility lists Heroic and Brutal as
alternative optional packages, preserving ordinary rage restrictions, the
Heroic exceptions, self-damage dice and the absence of post-rage fatigue.

Mind Spy separates the hour/day/week-per-level link lifetime from its much
shorter round/minute/hour-per-level sensory-use allowance. Separate uses allow
new saves; consecutive rounds do not. The designer does not track observation
time, erase memories, apply rage bonuses or mutate target records. Existing
locked item fields and tier construction prices remain unchanged.

Twenty-eight ordinary charm profiles are covered. Cerebral Strike still needs
review of its tier-specific damage minimum/floor semantics, and Inspiration
still needs its item-activation conversion resolved. Clouds, cognition,
advanced/modifier interactions and the broader designer gaps remain open. No
completion of the full goal, full-application test claim or deployment is made.

Source: https://spheresofpower.wikidot.com/mind (Ultimate charm descriptions).

## Inspiration native trigger

The published Inspiring Crest provides direct item evidence for Inspiration's
immediate, after-roll/before-result trigger. Its CL 2, one-use, 1,600 gp price
also matches the ordinary +1 alternate-charm construction conversion without a
swift-action surcharge. This supports the specifically scoped Inspiration
conversion; it is not treated as a blanket timing exception for all Mind talents.

Explicit-tier, fixed reviewed Inspiration designs now retain that native timing.
All three tiers project their competence bonus (+2, +2d4, or +2d4 plus half CL,
minimum +1) as a single-roll effect. Dice are not averaged, and the duration is
not a scalable per-level interval. Prices and the visible formula use the
existing tier costs and explain the native timing. Manual display locks survive
reopening. Legacy drafts and unreviewed coexisting modifiers do not opt into the
new timing automatically.

Mixed powers cannot borrow Inspiration's immediate timing to accelerate an
ordinary standard-action effect for free. Explicit activation adjustments keep
their existing costs, but receive a timing-review notice because a slower or
otherwise changed activation does not automatically preserve the original
trigger. Existing Fate native-word labels and behavior are preserved.

Twenty-nine ordinary charms now have profiles. Cerebral Strike's powerful-tier
minimum and ability-score-floor interpretation still needs rules verification;
the other previously documented designer gaps remain open. No full-goal
completion or deployment is included.

Sources:

- https://spheresofpower.wikidot.com/marvelous-items (Inspiring Crest)
- https://spheresofpower.wikidot.com/mind (Inspiration tiers)
- https://spheresofpower.wikidot.com/magical-items (construction adjustments)
