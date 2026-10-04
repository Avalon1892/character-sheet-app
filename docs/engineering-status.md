# Tech & Tinker implementation status

Tech Load Bearer validation: 148 engineering, shared rules, encumbrance, transfer, database, recovery and formula-field tests plus 12 subtests passed. This includes a real carried load changing from Heavy while powered to Overloaded under polymorph suppression. Full isolated suite not repeated for this increment; no deployment.

Tech Load Bearer carrying follow-up: the Tech device now uses the dedicated Body augment/graft slot and shared one-charge timed activation, Energy Efficient Augments, doubled graft periods, expiry and polymorph/Bio/retained-innate exceptions. Its carrying-only effective size increases by one category, two at 7 Craft ranks, and three at 14; purchased grafts use stored item ranks while ordinary and custom graft versions use live Craft ranks. Shared encumbrance/lift/load calculations apply the effective carrying size after Tinker's distinct effective-Strength adjustment, without changing physical size, Strength, AC or existing weapon damage. Over-limit grafts lose the effect and transfer preserves it. The workbench exposes the shared power button. Weapon wield-size validation/penalties, remote-control staggering, drone integration and effective carrying sizes beyond Colossal remain pending; the current standard carrying table caps at Colossal and those cases need rules verification. Source: https://spheresofpower.wikidot.com/tech.

Machinehead custom-graft lifecycle: selected Custom Graft prowess counts now authorize one supported self-maintained graft per selection. The workbench records completed construction without gold expenditure, starts it uncharged, labels it `graft_custom`, and disables creation when allowances are exhausted. These grafts do not count against prepared gadgets, but allocated charges count toward the ordinary Tech charge maximum and can be transferred back to the pool; appliance/contraption recharge and free internal batteries are unavailable. Separate self-implantation uses the existing confirmed surgery and capacity checks. Powered durations double, effects use live Craft ranks, and losing the supporting prowess suppresses the graft without erasing installation or its timer. Export/import preserves the construction and selected allowance. Tests: 108 engineering/database/transfer/recovery/shared-choice/UI tests plus 12 subtests passed, followed by both custom-graft tests and 2 theme subtests after the final exhausted-allowance button check. Full isolated suite not rerun for this increment. No deployment.

Custom Graft rules boundary: the official Machinehead description specifies free construction and normal Tech recharging but no distinct construction duration; recording therefore requires externally confirmed completion and does not invent an automatic duration or skill-check DC. Supported single-talent grafts currently cover Dermal Plating, Clamp Boots, Exo-Skeletal Muscles and Synaptic Reaction Maximizer. Internal Tool, composite/bio-recipient disguise interactions, nonstandard anatomy, Yellow Line/Redline/True Cyborg and the remaining Tech/Tinker devices are still pending. Source: https://spheresofpower.wikidot.com/machinehead.

Machinehead repeatable-choice final validation: 85 shared-choice, UI, architecture, engineering, Armiger-package and transfer tests plus 10 subtests passed after the final budget correction. Full isolated suite not repeated for this increment; no deployment.

Machinehead selection prerequisite: an archetype-only runtime choice provider now exposes Custom Graft alongside existing Armiger prowess options. Each repeated Custom Graft selection consumes a distinct prowess slot; the replaced level-2 slot is not granted, and the original provider cannot supply a second budget. The shared class-choice codec/resolver supports explicitly repeatable options while preserving default duplicate prevention for ordinary choices. The dialog exposes a count control only for repeatable entries, retains counts through search and enforces total slot/point limits. Existing imported class/archetype descriptions are unchanged. Validation: 82 shared-choice, UI, architecture, engineering and Armiger-package tests plus 10 subtests passed before the final zero-budget correction; 17 shared-choice/UI/Armiger tests passed after that correction. Custom Graft construction/recharging is still not automated, and Yellow Line/Redline/True Cyborg remain pending. This completes a prerequisite, not the graft exception itself.

Bio graft construction follow-up: the supported single-talent crafted-graft recorder now accepts an explicit, creation-time Bio Augment flag only with qualifying existing training; the planner exposes it and includes the choice in its confirmation. Bio grafts retain powered effects through ordinary polymorph and survive character transfer. Shared implantation status separately exposes the additional −5 Remote Control susceptibility for worn/implanted bio augments (−10 with an installed graft); unrelated saves are unchanged. Removal clears wearer susceptibility without deleting the constructed item. 63 engineering/transfer tests plus 10 subtests passed. Full isolated suite was not repeated for this increment; the immediately previous run had only the three documented baseline failures. Composite grafts, creature-specific disguise presentation, remote-control action resolution, Machinehead custom grafts and remaining devices are still pending.

Live-limit validation: full isolated run `artifacts/engineering-validation-live-implant-limits/summary.json` and `complete.xml`: 142 modules, 2,045 reported cases, 2,042 passed / 3 failed / 0 errors / 0 skipped (410.91 seconds). All three failures match the retained-innate baseline exactly: archetype count 1830 vs 1887; custom-tracker parent widget; obsolete tradition build-placement assertion with secondary Windows SQLite cleanup lock. The settings-dialog addition was separately followed by the complete final engineering module: 59 tests plus 10 subtests passed, including confirmation/no-write cancellation and one-refresh behavior in Parchment/Dark. No distribution was rebuilt.

Live implantation limits: shared calculations now evaluate saved cybertech usage, genuinely absent scores, manual capacity adjustments and Receptive to Grafts (+half Hit Dice, minimum 1), including resolved class-granted features. Installed grafts are evaluated in surgical order (legacy zero-order records fall back to stable ID); later over-limit grafts retain their slots and timers but lose automatic AC, ability and movement effects. Overload contributes an attributed −4 untyped penalty to all character saves. Conditional −5 Remote Control save susceptibility is exposed separately, not added to unrelated saves. Formula suppression flags, power spending, Clamp Boots controls and resistance agree with live capacity. Deliberately over-limit surgery requires explicit confirmation and displays the post-installation total/capacity and consequences. The new themed Implant limits dialog saves external cybertech, genuinely absent-score flags and verified manual exceptions; cancellation does not write and successful save refreshes once. Remaining: Machinehead custom-graft maintenance and limit-power integration, nonstandard anatomy, complete bio/composite graft construction, remote-control action resolution and remaining individual devices. Full regression run is in progress; focused checks passed (142 tests plus 8 subtests), followed by the final engineering module (59 tests plus 10 subtests).

Machinehead verification follow-up: direct access to its official page still returns a redirect loop, but the primary-source indexed page and bundled archetype description agree on Custom Graft, Yellow Line and Redline. No generic implantation-capacity bonus is stated. Custom Graft instead grants a free, nonsaleable, maintenance-dependent implant recharged through ordinary Tech mechanics, not an appliance's internal battery. Yellow Line/Redline alter Constitution while active, which must feed the same capacity calculation when those powers are implemented. These exceptions remain pending; the manual capacity adjustment is not a substitute for their automation. Sources: https://spheresofpower.wikidot.com/machinehead, https://spheresofpower.wikidot.com/tech, https://spheresofpower.wikidot.com/practitioner-feats.

Implant-profile persistence foundation: cybertech usage, genuinely absent Constitution/Intelligence and an explicit manual capacity adjustment now have additive saved fields, strict validation and backward-compatible export/import. Surgery uses the saved cybertech value by default; the workbench prompts with that value rather than zero. Successful installation atomically records the slot, chronological installation order and confirmed cybertech value; rejected surgery does not overwrite them. Installation checks absent scores and manual adjustments. Legacy installations retain order zero; future ordered projections must use stable record-ID fallback without rewriting history. Validation: 89 engineering/database/transfer/recovery tests plus 8 subtests passed, followed by all 3 new implantation regressions after the absent-score test was added. Full suite not rerun for this increment. Still pending: settings UI, Receptive to Grafts and verified class-specific capacity adjustments, dynamic overload suppression/penalties and deliberately over-limit surgery. Machinehead capacity behavior needs rules verification (official page redirect loop); no class rule was invented. This is not complete implantation automation.

Ability augment validation: 137 engineering, database, transfer, recovery, core-rules, formula, defense and unarmed/enchantment tests plus 17 subtests passed. Covers rank thresholds, failure-safe spending, enhancement stacking, AC/reflex/initiative propagation, slot conflicts, expiry, graft transfer/removal and shared power controls in Parchment/Dark. Full isolated suite has not been rerun after this increment; the previous run immediately before it had only the three documented pre-existing failures.

Ability augment follow-up: Exo-Skeletal Muscles and Synaptic Reaction Maximizer now contribute typed Strength/Dexterity enhancement bonuses through shared calculations (+2, plus +2 per seven Craft ranks). Body/Brain occupancy, one-charge paid periods, Energy Efficient Augments duration, expiry, damage suppression, polymorph/Bio/retained-innate exceptions, crafting as supported single-talent grafts and transfer reuse the existing augment lifecycle. Grafts use stored item ranks and doubled duration. The workbench's shared power control displays the selected augment name. Remote-control failure conditions, drone integration, composition, overload and nonstandard anatomy are still pending; these entries are not fully complete.

Retained-innate validation: 119 focused tests plus 15 subtests passed. Full isolated suite: 142 modules, 2,035 reported cases, 2,032 passed / 3 failed / 0 errors / 0 skipped (525.82 seconds), recorded in `artifacts/engineering-validation-retained-innate/summary.json` and `complete.xml`. All three failures match the previous `engineering-validation-d4ea479` baseline: class/archetype count 1830 vs 1887; custom-tracker parent-widget expectation; obsolete traditions placement assertion with secondary Windows SQLite cleanup failure. No new failing test was found; these unrelated failures were not changed.

Retained-innate polymorph exception: persisted current-form state now distinguishes ordinary polymorph from a transformation retaining innate traits. Shared suppression preserves only implanted graft effects in the latter; ordinary worn augments remain suppressed unless independently crafted as Bio Augments. AC, movement/clamp controls, formula suppression flags and workbench status agree. Ending polymorph clears the exception, and export/import preserves active form state with backward-compatible defaults. This is an explicit rules-state control, not automatic selection or detection of Alteration forms. Full bio-graft construction, overload/capacity adjustments, nonstandard anatomy and remaining devices are still pending.

Graft effects/UI validation: 117 engineering, database, transfer, recovery, core-rules and formula tests plus 13 subtests passed. Includes snapshot AC, doubled duration, clamp eligibility, expiry without uninstallation, polymorph suppression/restoration and cancelled surgical/save dialogs. Full isolated suite has not been rerun for this increment.

Supported graft effects/UI follow-up: Dermal Plating and Clamp Boots grafts now power through the shared charge-spending path, use doubled paid durations and retain construction-rank scaling rather than inheriting live wearer Craft ranks. Shared effect helpers recognize separate implanted slots without marking a graft worn. Expiry leaves surgery state intact; ordinary polymorph suppresses graft effects without refunding charges or pausing timers. The workbench exposes confirmed installation/removal and externally resolved removal saves, labels implanted slots, and preserves usable controls for retained selections after refresh. Crafted appliance/contraption recharge is 15 minutes because their rule grants engineering-kit-equivalent access. Pending: persistent external cybertech usage, absent-score configuration, overload/adjusted capacity, innate-trait-retaining polymorph exceptions, full bio-graft creation, nonstandard anatomy and additional graft devices. The current installation UI explicitly rejects over-limit surgery; this is not completion of the full graft objective.

Surgical-state validation: 109 engineering, database, transfer, recovery and core-rules tests plus 4 subtests passed. Full isolated suite has not been rerun for this increment.

Graft surgical persistence (partial): supported grafts have an additive, dedicated `graft_slot`, separate from worn augment occupancy. Service installation requires explicit confirmation of a willing/helpless subject throughout completed two-hour surgery and checks effective Constitution/Intelligence against installed graft values plus caller-supplied cybertech usage. Currently rejects over-limit installation; persistent cybertech/absent-score configuration, overload behavior and capacity feats remain pending. Installed grafts cannot be abandoned or uninstalled through ordinary device updates. Dedicated removal records the externally resolved Fortitude-save outcome atomically with removal; failed saves progress Fatigued → Exhausted → Unconscious. The Tech source specifies no removal DC, so none is invented. Unconscious is a condition marker, not yet full helpless-target combat automation. Export/import preserves surgery state. Surgical UI, powered graft effects, retained-innate polymorph handling and nonstandard anatomy remain pending; this is not complete graft installation automation.

Graft workbench follow-up: the construction planner now has explicit paid-material/time confirmations and a final Craft-check total. Recording supported single-talent grafts requires a confirmation preview, refreshes the sheet once, labels permanent construction in the roster and disables ordinary wearing. A separate recharge-graft control confirms the completed 15/30-minute procedure and restores the graft's own charge capacity. Composite construction and implantation remain unavailable rather than silently using ordinary augment behavior. Cancellation and completion/recharge UI tests pass; parchment/dark planner coverage is retained.

Permanent-graft recording foundation: repository/service support stores completed single-talent Dermal Plating and Clamp Boots appliance/contraption grafts with separate capped charges. Recording requires crafting prerequisites, GM permission, a successful final check, and explicit externally completed material/time confirmations. Unfinished construction performs no writes; grafts cannot be worn as ordinary augments. Recharge requires explicit completion, pool transfers cannot refund initial charges, and export/import preserves construction type. Backend only: completion/recharge UI, implantation, graft effects, composition and removal remain pending. Validation: 79 engineering/database/transfer/recovery tests and 4 subtests passed. Full suite has not been rerun for this increment.

Updated: 2026-10-04. This is an implementation ledger, not a claim of complete automation.

Energy Efficient Augments follow-up validation: 74 focused engineering, database, transfer and recovery tests plus 2 theme subtests passed. Thresholds, minimum training, paid expiry and invalid duration rejection are covered. Full-suite results below predate this follow-up.

Graft-capacity foundation validation: 41 engineering tests and 2 theme subtests passed, including shared cybertech usage, exact-limit/over-limit cases, missing ability scores and invalid values. No claim of a usable graft installation workflow is made yet.

Creation-specific efficiency validation: 70 engineering, database and transfer tests and 2 theme subtests passed. The regression checks distinguish ordinary devices created before training from efficient devices, preserve constructed efficiency after training is disabled, and preserve the construction flag on export/import.

Clamp Boots follow-up: 76 engineering, database, transfer and recovery tests and 2 theme subtests passed. New coverage checks unpaid clamping rejection, Legs occupancy, paid climb movement, clamp/unclamp, contextual resistance, polymorph suppression, transfer, expiry and removal freeing the slot.

## Implemented in this batch

- Clamp Boots: dedicated Legs augment occupancy, battery-first one-charge powered periods, creation-specific Energy Efficient Augments duration, shared climb movement matching base land speed, immediate-action clamp/free-action unclamp, paid expiry, ordinary polymorph suppression/Bio exception and transfer persistence. Clamped movement is restricted; the conditional half-Craft-ranks circumstance resistance is shown in the unclamp tooltip rather than applied to every save/CMD. Wall/ceiling traversal requires neither hands nor Climb checks. Extendo-limb composition, remote-control actions, grafts and extra-anatomy slots remain pending.

- Energy Efficient Augments records qualifying construction on each newly created Tech augment, requiring enabled training, at least 5 creation ranks and two augment talents. Paid Dermal Plating periods scale to 5/10/30 minutes at 5/10/15 live Craft ranks. Learning the talent later does not retrofit old devices; losing training does not erase constructed efficiency. Older saves default to ordinary construction, transfer preserves the flag, and the roster labels efficient devices. Paid periods are stored at activation and not retroactively resized. Other minute-per-charge augment functions must use the same shared duration helper when implemented.

- Conditional Engineering Workbench on the Crafting page for characters with an active Tech or Tinker base sphere.
- Character-owned, persistent device roster with stable catalog provenance.
- Additive SQLite storage; existing saved characters remain compatible.
- Device creation from currently learned gadget/gizmo talents; Tinker base sphere also unlocks batteries.
- Basic device limits, repeatable Extra Gadgets and Efficient Maintenance bonuses.
- Minor gizmo grouping and additive advanced increases. Selecting those flags is manual: the workbench does not yet validate whether an individual device qualifies.
- Creation-time level and practitioner-modifier snapshots; baseline HP, hardness, saves and DC displayed. Specific device exceptions are not applied.
- Activate, deactivate, deplete and confirmed irreversible abandonment.
- Tinker batteries cannot be deactivated, depletion still uses a limit slot, maintenance restores depleted devices, abandoned devices cannot be restored.
- Tinker batteries can attach to owned non-battery gizmos, multiple batteries can be depleted atomically, and personal battery uses enforce minimum battery level. Battery costs are selected manually; individual talent costs and reload-time reductions are not automated. Import/export remaps battery host identities.
- Tech pool begins empty, recharges by the associated-rank rule, spends without going negative, transfers charges atomically between pool and devices.
- Charges allocated to regular gadgets remain counted against the total pool maximum.
- Tech batteries are created charged, remain outside the pool maximum, attach one per same-system device, and are drained first through atomic device spending. Explicit recharge and detach controls are available; excess pool charging requires confirmation. Abandonment discards battery charges.
- Rest preserves Tech charges and does not silently maintain Tinker batteries.
- Device and resource import/export with ownership checks.
- Persistent device damage, current/max HP, optional hardness subtraction, and automatic deactivation at zero HP. Destroyed devices and batteries cannot activate or supply charges.
- Tinker broken-condition threshold and effective-level penalty, one-minute tool-assisted repairs, and maintenance-based full repair of non-abandoned gizmos. Rest does not perform repairs.
- Augmentation-package Physical Augmentor crafting with a selected Strength/Dexterity/Constitution configuration and explicit wearer state. Active, worn augmentors contribute typed competence bonuses to matching skill checks through shared calculations, including skill ability overrides and broken effective levels. Ability scores are not increased.
- Jet-boosters: creation-time flight/aquatic choice, normal/slow-burn/overdrive modes, atomic battery-first payment, paid durations, live movement/maneuverability, light-load restrictions and equipment-slot conflicts. Explicit game-round advancement expires timed functions; eight-hour rest advances those timers without recharge or maintenance.
- First Tech gadget choices exclude routine talents.
- Timer expiration distinguishes paid Jet-boosters operation (device deactivates) from Tinker temporary enhancements (passive device activation is retained). Supporting-battery identity is stored with ownership/attachment checks and remapped on import. Detaching, abandoning or destroying the supporting battery ends its linked timed effect without disabling the host's passive activation. Function-specific enhancement activation remains pending.
- Personal Field Projector with the Modification package unlocks a separate Tactile Field recipe. Active/attached CMD, Acrobatics and Escape Artist circumstance bonuses are automatic, use effective gizmo level and do not stack multiple copies. One attached battery atomically activates its enhanced bonus for one minute per effective gizmo level. Expiry retains the passive field; the reroll/end control ends enhancement early. Dice/opponent reroll resolution remains manual.
- Pressure Jack unlocks a Strength Load Bearer recipe. Active/worn skill bonuses and carrying-capacity Strength are automatic, including doubled capacity bonus for advanced devices and reduced bonuses when broken. Actual Strength is unchanged; object-breaking size benefits and roll actions remain manual.
- Cognitive Set unlocks a separate Mental Augmentor recipe with Intelligence/Wisdom/Charisma configuration and active/worn competence skill bonuses. Brain Jack/storage, ability-check rolls and battery rerolls remain pending.

## Partial support / manual inputs

- Workbench now has a read-only Augment Graft construction planner for learned Tech augments. It requires explicit GM permission, permanent base/talent ownership, both crafting feats and at least 3 permanent Craft ranks; item ranks cannot exceed permanent ranks and complexity cannot exceed item ranks without Versatile Crafter. Shared rules calculate appliance/contraption material cost, doubled base price, DC, four-hour-block working time (minimum eight hours), calendar days, initial charge capacity, doubled charged durations and default two-hour/value installation. Parchment/dark controls and cancellation perform no writes. Allies/blueprints, drawback restrictions, supplied objects, device-specific implantation exceptions and actual permanent construction/installation/removal remain pending. This planner does not spend gold or create a graft. Validation: 67 engineering/crafting/item-creation tests plus 2 theme subtests passed; additional graft UI coverage passed 3 tests and 2 theme subtests. Full-suite validation above predates this planner.

- Graft implantation now has a tested shared capacity assessment: Constitution/Intelligence use the lower present score, a genuinely absent score is distinct from a score treated as 10, cybertech consumes the same capacity, and overload assessment retains installed records and reports the -4 save penalty. This helper is not yet connected to persisted graft installations or automatic saves; prerequisite/crafting, surgery, graft slots, doubled charged durations and retained-innate polymorph behavior remain unfinished. Official removal text requires a Fortitude save but does not specify its DC in this section; needs rules verification rather than an invented DC.

- Bio augment construction is an explicit per-device, creation-time choice for Tech augments. It checks 10 Craft/Disguise ranks and Hidden Gadget, plus Bio Augment with three augment talents or the Untraceable Gadget alternative. It is made for the current character; other wearers are not yet supported. Constructed bio augments remain effective during polymorph, preserve their identity on transfer and do not retroactively convert ordinary devices. Conditional disguise/detection benefits, remote-control penalties and graft surgery are still pending.

- Explicit character-owned polymorph state now suppresses installed ordinary Tech augment effects without changing saved activation, slot occupancy, charges or paid duration. The workbench shows suppression and formulas expose `devices.device_<id>.suppressed`. State is additive, defaults off for older characters and survives transfer. This currently affects the implemented Dermal Plating path; no blanket Tech-specific suppression is imposed on Tinker. Bio augment/Untraceable Gadget exceptions, innate-trait retention for grafts and automatic linkage to transformation effects remain pending.

- Tech Dermal Plating has a separate persistent Body augment slot with repository ownership/occupancy validation and a unique database constraint. It coexists with ordinary Body-slot equipment. Installation/removal is controlled through wearer state; paid activation atomically spends one charge battery-first for 10 rounds. Shared AC receives a typed natural-armor enhancement based on current Craft ranks, so other natural-armor enhancements do not stack. Expiry deactivates the function, removal ends it, and character transfer preserves the dedicated slot. Donning time/hasty penalties, remote-control suppression, nonstandard anatomy, graft installation and polymorph exceptions remain pending; this is not complete augmentation support.

- Advanced Field Projectors plus Modification and at least 5 associated-skill ranks enables Tactile Field's immediate-action reroll at will. The action requires an active, worn, functioning field and spends no battery or unnecessary refresh when no enhancement is active. Using the existing enhanced-period reroll still ends that period; increasing CMD/skill bonuses still requires a battery. Actual dice resolution remains manual. Other Advanced Field Projectors functions remain pending.

- Defensive Set plus Computation unlocks a separate Resistance Routine recipe, automatically classified as minor. Installation/removal uses owned Tinker host identities and existing transfer remapping. Active functioning routines add the highest applicable insight save bonus to their host's displayed saves (including broken-level changes), never to character saves. AI sharing and nested routine composition remain pending.
- Routine lifecycle follows the host: activation requires an installed, active, functioning host; deactivation/destruction/depletion of that host deactivates its routine. Depleting a battery host performs this in the same transaction. Removal or transfer to an inactive host deactivates the routine, while later repair/maintenance retains stored routine data without silently reactivating it. Import stages routines inactive until host identities are restored. Focused lifecycle/database/transfer validation: 64 tests and 2 theme subtests passed.

- Physical/Mental Augmentor and Load Bearer now have a dedicated one-battery benefiting-check action. It validates active, worn, functioning, correctly configured devices and uses the existing atomic battery depletion path. Actual dice are resolved manually (roll twice and take the higher result); no persistent reroll buff is created. Focused validation: 33 engineering tests and 2 theme subtests passed.

- Associated skill defaults to the existing shared Craft rank provider. Alternative associated skills can be selected in the workbench, but tradition-specific skill-rank grants and skill specialties are not completely automated.
- Practitioner modifier may be manually entered or linked to a chosen ability's live calculated modifier. The workbench recalculates linked values on refresh; creation still stores the required snapshot. Automatic selection of the governing ability from every class/archetype/tradition remains pending; no unrelated class resource ability is assumed to be a practitioner ability.
- Crafting/maintenance duration and batch allowance are calculated and displayed. Timed device functions use explicit game-round advancement; a general campaign clock and crafting session ledger remain pending. Ordinary Tinker gizmos last indefinitely under the current rules; optional GM neglect is not imposed automatically.
- Base package grants can include multiple gizmo types within one talent. Physical Augmentor is now a separate craftable function; other package functions still need function-level recipes.
- Current talent validation still relies on the existing character selection system.
- Workbench maxima are live calculated. The reusable Tech tracker maximum is refreshed when changing pool charges, not on every character edit.
- Losing a base sphere prevents new crafting/resource use, but the saved roster is retained for review rather than deleted.
- Device baseline statistics are frozen at creation. This is intentional for Tinker; Tech device-specific scaling and later upgrades need further verification.

## Still missing

1. Function-level recipes and configurations for remaining gadget/gizmo talents and base packages. Physical Augmentor skill effects are implemented; its ability-check roll integration and battery reroll are still manual.
2. Automatic equipment/attack/AC/save/movement/skill modifiers from installed and activated devices.
3. Tech batteries attached to external technological inventory items. Current hosts are character-owned workbench devices. Nonpositive-modifier pool charging follows the separate printed creator-modifier cap; interpretation needs rules verification because creation explicitly has a minimum of one.
4. Augment/graft slots, installation checks, incompatibilities and polymorph suppression.
5. Drone and mechanoid stat blocks, upgrades, piloting, innate devices and rote functions.
6. AI stat blocks, commands, routines, hosts and installation.
7. Accessories, combined devices, accommodation/secondary-function composition.
8. Tech-specific repair methods, sundering attack resolution, damage-type adjustments, scavenging and detailed upkeep. Current HP and basic Tinker repair/maintenance are implemented; AI/mechanoid exceptions, Redundant Systems and It Just Works remain pending.
9. Timed activation/duration profiles for remaining functions and temporary charges. Jet-boosters' paid periods and expiration are implemented.
10. Project construction costs/times and technical-item creation feat integration.
11. Tinker tradition restrictions/boons, optional variants and skill substitutions.
12. Class/archetype-specific personal gizmos and personal battery-use requirements.
13. Prodigy engineering interactions: effective-level boosts, temporary batteries and their expiry.
14. Direct Martial Book actions for individual saved devices. Shared formula references now expose per-device level/effective level, current/max HP, own charges, remaining paid rounds and state flags; autocomplete includes them and character import remaps device identities in references.
15. Complete rules-safe validation of minor/advanced/exempt devices and alternate construction sources.
16. Automatic handling of all sphere drawbacks and interactions with other spheres.
17. Current website completeness verification. The table below describes bundled entries only.
18. Packaged-runtime verification for this batch. The full isolated suite has run; three pre-existing failures remain separate from engineering work.

## Validation

Latest full isolated run at `d4ea479`: 142 modules, 2,022 cases, 2,019 passing, 3 failures, 0 errors, 0 skipped; 595.02 seconds. Each failure matches the confirmed baseline: archetype count 1,830 versus 1,887, custom-tracker parent placement, and obsolete `PLACEMENTS['build']` tradition ordering with secondary Windows SQLite cleanup lock. Engineering, formulas, movement-related rules, recovery, database, transfer and theme modules passed. Reports: `artifacts/engineering-validation-d4ea479/summary.json` and `complete.xml`. This covers accumulated Bio Augment, polymorph, efficiency construction and Clamp Boots changes; it does not prove completion of remaining device effects or graft installation, and no distribution was rebuilt.

Graft integration follow-up: Craft Augment Graft and Craft Appliances And Contraptions are now shared Spheres Item Creation feat entries with stable keys, prerequisite text, official provenance and clearly marked rule summaries. Feat selection and Codex routing reuse the existing catalog. The manifest version/hash/size were updated without bypassing integrity checks. 21 item-creation, content, feat UI, gizmo reference and catalog-version tests passed. Exact feat-count expectations increased by two, with Pathfinder counts unchanged. This adds prerequisites to selection, not permanent-device construction or graft surgery. Receptive to Grafts already exists as `spheres:receptive-to-grafts` and increases implantation capacity by half Hit Dice (minimum 1); do not duplicate its catalog record. Genuine missing Constitution/Intelligence requires explicit support rather than interpreting the application's numeric default as an absent score. The full isolated run above predates these two catalog additions.

Bio augment follow-up: 68 focused engineering, database and transfer tests plus 2 theme subtests passed; additional alternative-training assertions cover Bio Augment and Untraceable Gadget eligibility. This remains partial augmentation implementation, not a claim that contextual checks or graft installation are complete.

Polymorph follow-up: 74 focused engineering, persistence, transfer and formula tests plus 11 subtests passed. Coverage includes AC suppression/restoration, unchanged installed-device records, per-character ownership, invalid state rejection, formula exposure and transfer of current form state. This does not prove bio/graft exceptions or automatic form selection, and the full suite has not been rerun after this change.

Dermal Plating follow-up: 81 focused engineering, database, transfer, recovery and item-effect tests plus 2 theme subtests passed. Coverage includes ordinary/dedicated slot coexistence, occupied-slot rejection, failed unpaid activation, charge spending, live AC projection, typed non-stacking, expiry and dedicated-slot character transfer. The full suite has not been repeated after this follow-up.

Latest complete isolated run at `54e2f84`: 142 modules, 2,015 cases, 2,012 passing, 3 failures, 0 errors, 0 skipped; 596.79 seconds. The three failures match the confirmed baseline: archetype catalog count (1,830 expected, 1,887 actual), custom-tracker parent placement, and obsolete tradition-placement expectations with a secondary SQLite cleanup lock. No additional regression was found in this run. Reports: `artifacts/engineering-validation-54e2f84/summary.json` and `complete.xml`. This covers the accumulated package-choice, formula, Tactile Field, augmentor battery-action and Resistance Routine changes; it does not establish completeness of unimplemented device functions or packaged runtime behavior.

Current accumulated engineering validation at `1ae99de`: complete isolated suite finished across all 142 modules, 2,003 cases, 2,000 passing, 3 failing, 0 errors and 0 skipped. Failures match the previously reproduced baseline issues: archetype count (1,830 expected versus 1,887 bundled), custom-tracker parent placement, and tradition placement (with secondary database cleanup lock). No new failures were introduced by damage/repair, Physical/Mental Augmentor, Jet-boosters or Load Bearer. Reports: `artifacts/engineering-validation-current/summary.json` and `complete.xml`. This does not prove missing device mechanics or packaged-runtime behavior.

Package-validation follow-up: Physical/Mental Augmentor and Load Bearer recipes now require Augmentation. Expanded Tinkering uses the shared two-package picker, excludes owned packages, validates distinct/unowned choices on permanent add/edit, and saves them for engineering access. Shared flexible-talent validation also checks choices against permanent and earlier staged selections; the temporary picker excludes those packages and cancellation performs no writes. Remaining function-specific package restrictions still need coverage. Focused engineering, catalog redesign and Athletics run: 39 tests and 2 theme subtests passed.

74 focused tests and two theme subtests passed across engineering, database, sphere choices, crafting, skill ranks, recovery, Codex and import/export. The full isolated suite was not run; no assertion is made about its current baseline. Actual workbench renders were inspected in parchment and dark themes.

Tech battery follow-up: full isolated run completed with 1,991 cases, 1,988 passing and 3 failing. All three failures reproduce against the untouched `87b4e8e` baseline: stale archetype count, custom-tracker parent placement, and tradition placement. Latest focused engineering run: 14 tests and 2 theme subtests passed, including the subsequent Tinker battery host-level guard and cancelled-overfill checks. Normal/portable deployment and packaged verification are not yet performed for this follow-up.

Damage/repair follow-up: 51 focused engineering, database, transfer and recovery tests plus 2 theme subtests passed. The parchment workbench render was inspected with a broken gizmo showing current/max HP and effective level. The full isolated suite has not been repeated after this follow-up. Damage-type adjustments are manual before applying hardness; device-specific defensive exceptions and attack/sunder resolution remain pending.

Physical Augmentor follow-up: 58 focused engineering, shared rules, skill-rank, transfer and recovery tests plus 2 theme subtests passed. Configuration and wearer state are additive/defaulted database fields. Device slot validation, duration/expiry, external wearers and alternate construction grants remain pending.

Jet-boosters follow-up: 76 broad focused tests plus 2 theme subtests passed; after additional slot/load/transfer and Athletics Fly-package coverage, all 22 engineering tests and 2 theme subtests passed. A further 19 performance/layout/movement tests and 2 theme subtests passed. The parchment timed-jet dialog was rendered and inspected. The full suite has not yet been repeated. Long Distance Fuel Pack, external/unwilling users, exhaust/hover geometry and equipment-figure display remain pending.

## Verified rule sources

### Installation rules verified for the next implementation

- Tech augments use dedicated slots separate from magic-item and cybertech slots. A slot normally holds one augment; nonstandard anatomy can add limb/sensory slots, but never additional body or brain slots.
- Tech augment donning/removal follows leather armor. Hasty donning adds 2 armor check penalty. Visible augments impose a Disguise penalty of 10 + 2 per donned augment.
- Ordinary Tech augments do not function during polymorph, including augments donned after transformation. Grafts instead follow innate-trait retention. Bio Augment and Untraceable Gadget contain explicit exceptions which must be modeled rather than applying blanket suppression.
- Tinker augmentation installation must use its own rules: worn augmentation donning/removal takes one minute; same-function benefits do not stack, but differently configured augmentations can coexist. Prosthetics have separate fitting/implantation rules. Do not reuse Tech's dedicated-slot or polymorph rules without a Tinker rule supporting that behavior.
- These are verified requirements, not implemented installation behavior. Next work must connect installation state to shared calculations and existing condition/equipment state, with regression coverage for both systems and exceptions.

- [Tech](https://spheresofpower.wikidot.com/tech)
- [Tinker](https://spheresofpower.wikidot.com/tinker)
- [Using Tinker Sphere](https://spheresofpower.wikidot.com/using-tinker-sphere)
- [Mastering Gizmos](https://spheresofpower.wikidot.com/mastering-gizmos)

## Bundled entry ledger

Every entry remains available through existing catalogs/Codex. “Roster” means lifecycle tracking only, not automatic effects.

| Sphere | Entry | Category | Functional status |
| --- | --- | --- | --- |
| Tech | Tech Sphere | Base Sphere | Basic workbench access and calculations |
| Tech | Alternate Element Pack (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Chameleon Suit (gadget, accessory) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Control Harness (accessory, drone, gadget, signal) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Dash Engine (accessory, augment, drone, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Disarmer (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Homing Pack (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Hookshot (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Integrated Armory (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Internal Tool (accessory, augment, drone, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Laser Pack (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Misfire Manager (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Mobile Armor (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Pressure Mechanism (accessory, augment, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Range Amplifier (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Sniper Scope (accessory, augment, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Speed Lever (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Superior Joints (gadget, accessory) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Weapon Upgrade (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Alternative-Craft | Drawback | Reference / existing selection only |
| Tech | Environmental Fuel Source | Drawback | Reference / existing selection only |
| Tech | Expensive Fuel Source | Drawback | Reference / existing selection only |
| Tech | Expensive Gadgets | Drawback | Reference / existing selection only |
| Tech | Explosive Gadgets | Drawback | Reference / existing selection only |
| Tech | Extended Charge | Drawback | Reference / existing selection only |
| Tech | Generated Power | Drawback | Reference / existing selection only |
| Tech | Imbued Gadgets | Drawback | Reference / existing selection only |
| Tech | Incomplete Knowledge | Drawback | Reference / existing selection only |
| Tech | Mana Engineering | Drawback | Reference / existing selection only |
| Tech | Obvious Activation | Drawback | Reference / existing selection only |
| Tech | Specific Drone | Drawback | Reference / existing selection only |
| Tech | Uninsulated | Drawback | Reference / existing selection only |
| Tech | Unsecured | Drawback | Reference / existing selection only |
| Tech | Wired Gadgets | Drawback | Reference / existing selection only |
| Tech | Accessory Suit (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Alt Weapon Mode (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Alternate Element Pack (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Ammo Spitter (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Anatomical Structure (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Antivirus Application (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Artificial Intelligence (drone, gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Auto Injector (augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Automator (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Battery (gadget) | Gadget Talent | Construction, exempt storage, attachment, atomic battery-first spending and explicit recharge; external inventory hosts pending |
| Tech | Camera (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Chameleon Suit (gadget, accessory) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Chemalyzer (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Clamp Boots (augment, drone, gadget) | Gadget Talent | Augment/graft Legs slots, paid climb movement, clamp/unclamp, conditional resistance, live implantation limits, expiry, polymorph and transfer implemented; composition/remote control/nonstandard anatomy pending |
| Tech | Collapsible Vehicle (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Commset (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Compact Shield (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Control Harness (accessory, drone, gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Dash Engine (accessory, augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Dermal Plating (augment, drone, gadget) | Gadget Talent | Augment/graft Body slots, paid typed AC enhancement, stored graft ranks, live implantation limits, expiry, polymorph and transfer automated; composition/remote control/nonstandard anatomy pending |
| Tech | Diga Drill (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Disarmer (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Drone (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Emergency Gear (drone, gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Evac Pack (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Exo-Skeletal Muscles (augment, drone, gadget) | Gadget Talent | Body augment/graft, paid Strength enhancement, typed stacking, live implantation limits, expiry, polymorph and transfer automated; remote-control/drone/composition/anatomy pending |
| Tech | Extendo Appendage (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | External Health Modulator (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Firefighter Equipment (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Gravity Clip (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Homing Pack (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Hookshot (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Integrated Armory (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Internal Tool (accessory, augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Jet-boosters (drone, gadget) | Gadget Talent | Flight/aquatic configuration, paid operating modes, movement, slot checks and timers; fuel pack/external users/hover geometry pending |
| Tech | Laser Pack (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Load Bearer (augment, drone, gadget) | Gadget Talent | Body augment/graft slots, paid size-based carrying benefit, duration, suppression and transfer automated; weapon wield-size/remote-control/drone/beyond-Colossal handling pending |
| Tech | Mechanical Ranged Weaponry (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Mechanical Tool (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Misfire Manager (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Mobile Armor (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Modular Slot (augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Overdrive (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Particle Weapon (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Pneumatic Box (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Pressure Mechanism (accessory, augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Range Amplifier (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Remote Control (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Seeker Missile Cannon (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Self Destructive Device (moddable) | Gadget Talent | Reference / existing selection only |
| Tech | Sensory Set (augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Signal Attenuator (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Signal Cable (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Sniper Scope (accessory, augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Speed Lever (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Superior Joints (gadget, accessory) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Synaptic Reaction Maximizer (augment, drone, gadget) | Gadget Talent | Brain augment/graft, paid Dexterity enhancement, typed stacking, live implantation limits, expiry, polymorph and transfer automated; remote-control/drone/composition/anatomy pending |
| Tech | Targeting Application (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Taser (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Tracker Chip (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Turret (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Tutor (drone, gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Virus (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Weapon Upgrade (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Alchemical Drone | Legendary Talent | Reference / existing selection only |
| Tech | Arcanoscientific Tool (drone, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Artificial Intelligence, Greater (drone, gadget, routine) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Artificial Intelligence, Improved (drone, gadget, routine) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Automatic, Semi-Automatic, and Slow Firing | Legendary Talent | Reference / existing selection only |
| Tech | Bio Augment | Legendary Talent | Reference / existing selection only |
| Tech | Clockwork Drone | Legendary Talent | Reference / existing selection only |
| Tech | Combat Limbs (augment, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Compactor (accessory, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Computer (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Drawback Alleviator (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Energy Efficient Augments | Legendary Talent | Creation-specific persistence, shared duration thresholds and Dermal Plating activation automated; remaining augment functions pending |
| Tech | Extreme Distance Communication (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Generator (drone, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Hammerspace Augment | Legendary Talent | Reference / existing selection only |
| Tech | Hidden Gadget | Legendary Talent | Reference / existing selection only |
| Tech | It Just Works [Jester's HB] | Legendary Talent | Reference / existing selection only |
| Tech | Long Distance Fuel Pack (drone, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Protonic Energypack (accessory, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Return to Sender | Legendary Talent | Reference / existing selection only |
| Tech | Robot Drone | Legendary Talent | Reference / existing selection only |
| Tech | Signal Penetration | Legendary Talent | Reference / existing selection only |
| Tech | Steampowered Drone | Legendary Talent | Reference / existing selection only |
| Tech | Strength Of A Million And Seventy | Legendary Talent | Reference / existing selection only |
| Tech | Superior Mechanical Melee Weaponry (gadget, moddable) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Superior Mechanical Ranged Weaponry | Legendary Talent | Reference / existing selection only |
| Tech | Transporter (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Untraceable Gadget | Legendary Talent | Reference / existing selection only |
| Tech | Vigorous Gadgets | Legendary Talent | Reference / existing selection only |
| Tech | Wireless Charge | Legendary Talent | Reference / existing selection only |
| Tech | Collapsible Drone | Talent | Reference / existing selection only |
| Tech | Combined Augment | Talent | Reference / existing selection only |
| Tech | Efficient Drones | Talent | Reference / existing selection only |
| Tech | Extra Gadgets | Talent | Basic limit bonus automated |
| Tech | Improved User Interface | Talent | Reference / existing selection only |
| Tech | Mass Drone Deployment | Talent | Reference / existing selection only |
| Tech | Momentum Transfer (stance) [Youxia HB] | Talent | Reference / existing selection only |
| Tech | Repairable Drone | Talent | Reference / existing selection only |
| Tech | Standardized Drones | Talent | Reference / existing selection only |
| Tech | Tech Savvy | Talent | Reference / existing selection only |
| Tinker | Tinker Sphere | Base Sphere | Basic workbench access and calculations |
| Tinker | Powerless [SUE] | Drawback | Reference / existing selection only |
| Tinker | Specialized Inventorship [SUE] | Drawback | Reference / existing selection only |
| Tinker | Specific Mechanoids [SUE] | Drawback | Reference / existing selection only |
| Tinker | Tinker Tradition [SUE] | Drawback | Reference / existing selection only |
| Tinker | Armor Modifications (gizmo, modification) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Arsenal Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Aviation Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Cognitive Set (gizmo) [utility] | Gizmo Talent | Mental Augmentor configuration and mental skill bonuses automated; remaining functions pending |
| Tinker | Defensive Set (gizmo) | Gizmo Talent | Resistance Routine recipe, installation and host save bonus automated; other functions and AI sharing pending |
| Tinker | Disruption Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Emergency Gear (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Energy Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Excavation Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Exploration Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Grappling Hook (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Infiltration Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Medical Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Movement Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Personal Field Projector (gizmo, modification) | Gizmo Talent | Tactile Field passive/enhanced bonuses, battery cost, timer and reroll termination automated; actual reroll and other fields pending |
| Tinker | Pressure Jack (gizmo) | Gizmo Talent | Load Bearer recipe, skill bonuses and carrying capacity automated; other functions pending |
| Tinker | Primal Augmentations (augmentation, gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Prosthetics Mastery (augmentation, gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Ranged Set (gizmo, modification) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Repair Kits (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Sensory Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Table: Elemental Infuser | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Lifter Type | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Portable Wall | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Power Plants | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Translator Fluency | Gizmo Talent | Reference / existing selection only |
| Tinker | Technological Weapons (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Transmission Mastery (gizmo, transmission) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Transportation Mastery (gizmo, transportation) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Weapon Modifications (gizmo, modification) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Arsenal (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Augmentation (gizmo, augmentation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Computation (gizmo, computation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Energy Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Excavation (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Field Projectors (gizmo, modification) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Movement (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Prosthetics (gizmo, augmentation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Ranged Set (gizmo, modification) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Transmission (gizmo, transmission) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Transportation (gizmo, transportation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Automation Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Dynamic Repurposing [LG] | Legendary Talent | Reference / existing selection only |
| Tinker | Energy-Attuned Gizmos | Legendary Talent | Reference / existing selection only |
| Tinker | Extra Automatons (computation, transportation) | Legendary Talent | Reference / existing selection only |
| Tinker | Full Integration (gizmo, transportation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Hammerspace (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Magic Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Master Of Technology | Legendary Talent | Reference / existing selection only |
| Tinker | Multimedia Mastery (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Radiation Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Restoration Mastery (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Security Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Spooky Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Table: Advanced Lifter Type | Legendary Talent | Reference / existing selection only |
| Tinker | Table: Distant Teleport | Legendary Talent | Reference / existing selection only |
| Tinker | Table: Turrets | Legendary Talent | Reference / existing selection only |
| Tinker | Teleportation Set (gizmo, transmission) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Disguised Gizmo [utility] | Talent | Reference / existing selection only |
| Tinker | Efficient Maintenance | Talent | Basic limit bonus automated |
| Tinker | Expanded Tinkering | Talent | Reference / existing selection only |
| Tinker | Machine Horde (transportation) | Talent | Reference / existing selection only |
| Tinker | Mass Interface | Talent | Reference / existing selection only |
| Tinker | Multifunctional Gizmos | Talent | Reference / existing selection only |
| Tinker | Redundant Systems | Talent | Reference / existing selection only |
| Tinker | Security Measures [utility] | Talent | Reference / existing selection only |
| Tinker | Tinker Savvy [utility] | Talent | Reference / existing selection only |
