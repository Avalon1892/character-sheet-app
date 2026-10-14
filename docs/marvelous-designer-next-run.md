# Custom Marvelous designer — active requirements

The user's latest priority is the designer, not construction-calendar automation. Preserve existing project data and APIs, but do not add round/day tracking to satisfy this UI request.

## Implemented checkpoint

- A permanently visible, wrapping cost formula below the designer preview. It obtains values from the existing authoritative quote, including daily/unlimited/50-use, slotless and separate/mixed power pricing.
- Formula and price update through existing control signals; invalid designs show an explicit error rather than a stale formula.
- The designer summary no longer displays crafting days. Existing project functionality is unchanged.
- `Add effects…` now reuses the shared searchable magic catalog/basket, restricted to enabled effective catalog talents of the currently selected sphere. This includes real saved Moldable selections and other shared effective projections; base spheres/drawbacks are excluded. Old unrestricted add controls are hidden but retained internally for safe saved-plan restoration and prerequisite insertion. Picking confirms draft contributions only, prevents duplicate additions, recalculates price, and cancellation writes nothing. Permanent creation eligibility is intentionally unchanged. Cross-sphere powers still use the existing additional-power designer; full automatic talent/SP/prerequisite coverage remains incomplete.
- Effective-access verification: 52 crafting-access/UI/Moldable tests passed; shared catalogs 23 passed plus 7 subtests; after adding confirmation/cancellation regression, UI 26 passed in 14.96 seconds. Actual saved Moldable-to-crafting integration is covered by 11 passing Exploitant tests in 7.09 seconds.
- Added a central item-card editor for name, slot, CL, save DC, activation, uses, price and description. Each field has a persisted lock; unlocking immediately restores the calculated projection. Overrides are explicitly display-only and cannot alter price/resource rules. Existing original name/slot/description controls still set the inventory values. Service validation rejects malformed overrides before writes. The final Pathfinder-style typography/descriptor coverage and three-column layout are not complete.
- Card/resource/UI validation: **57 passed in 31.64 seconds**, including save/reopen, unlock/recompute and invalid-override/no-write cases. Rendered Parchment and Dark; inspected Parchment, which still needs width/height refinement (right-edge lock labels and tall control stack). Do not claim final visual QA complete.
- Validation: 51 existing designer/pricing/multiple-effect tests passed in 13.30 seconds; after adding explicit slotless/50-use/separate/mixed formula coverage, all 25 pricing tests passed in 0.23 seconds.

## Required next (not implemented yet)

1. Three-column designer: left tradition/effect controls, central Pathfinder-style item template, right drawback controls. Keep the cost formula unobtrusive but always visible.
2. Choose a crafting tradition per design, using the existing optional-tradition catalog without changing character-level selections. Apply reviewed boons/drawbacks to price/effect where supported; expose unsupported mechanics honestly. Existing `tradition_costs` is only a helper, not integrated selection/payment.
3. Add effects from currently accessible effective talents, including Moldable Talents via the shared effective-selection provider. Do not confuse temporary design access with permanent creation eligibility. Preserve saved contributions that are no longer currently accessible rather than silently deleting them.
4. Automate effect talent/SP cost and reviewed prerequisite chains (including the user's Teleport Beacon example after source verification), with required selections/choices clearly requested. Existing mappings cover only subsets.
5. Add published and custom drawbacks, with validated custom complexity reductions and live price updates. Reuse catalog identities; custom reductions require explicit review rather than pretending they are published rules.
6. Central item template dynamically displays name, slot, CL/aura/descriptors, uses, price and description. Provide manual overrides and per-field locks for every displayed field. Persist locks/overrides additively in blueprint metadata. Display overrides must not silently change resource/mechanical values; distinguish them clearly.
7. Verify save/reopen, unlock/recompute, cancellation/no writes, dynamic changes, effective Moldable selection and both retained themes. Run relevant regression tests and inspect the actual designer visually before declaring this goal complete.

The full active goal is not complete. Broader Marvelous implementation history and gaps remain in `marvelous-items-next-run.md`.
