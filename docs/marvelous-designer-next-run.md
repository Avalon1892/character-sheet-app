# Custom Marvelous designer — active requirements

The user's latest priority is the designer, not construction-calendar automation. Preserve existing project data and APIs, but do not add round/day tracking to satisfy this UI request.

## Implemented checkpoint

- A permanently visible, wrapping cost formula below the designer preview. It obtains values from the existing authoritative quote, including daily/unlimited/50-use, slotless and separate/mixed power pricing.
- Formula and price update through existing control signals; invalid designs show an explicit error rather than a stale formula.
- The designer summary no longer displays crafting days. Existing project functionality is unchanged.
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
