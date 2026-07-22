# E2.S2 Public Set B Capacity Allocation Readiness

Task: E2.S2 EV-to-IC-1 readiness follow-up after EV-CAL-001 and EV-008A.

## Purpose

This packet prepares the approved EV-008A public Set B source library for later IC-1 consumption by materializing a candidate-only capacity-class allocation layer for the approved 2035 Alkmaar public charge-point totals. It does not load profile arrays, open held-out batches, run integrated net-load analysis, estimate events or `P(E)`, produce manuscript numbers, or claim that `M = 1200` is sufficient.

## Inputs

- Source candidate adapter artifact: `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json`.
- Output readiness artifact: `data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json`.
- Governing allocation decision: A-014, static load-node `p_mw` weights with deterministic largest-remainder rounding.
- Governing public profile decision: EV-008A, uncontrolled ElaadNL public `cp` profiles with native `['van', 'car']` mix, simulated year 2030, and equal 25% physical AC capacity mix across 11, 13, 15, and 22 kW classes.
- Calendar mapping rule: EV-CAL-001 ordinal timestep mapping is already approved for readiness mapping; this packet records only capacity allocation metadata.

## Allocation Rule

For each approved Alkmaar scenario, the existing A-014 public per-node counts are preserved. The public total is split across the four EV-008A capacity classes using deterministic largest remainder with stable class-ID tie-breaking. The node-by-class matrix then rounds each node's public count across the same class shares while conserving both row totals (per-node public charge points) and column totals (global capacity-class counts).

This two-way conservation check is intentionally explicit: future IC-1 sampling must not accidentally change the approved local public count or the EV-008A equal-mix class totals before any source-member draw is made.

## Scenario Totals

| Scenario | Public total | public_11kw | public_13kw | public_15kw | public_22kw |
| --- | ---: | ---: | ---: | ---: | ---: |
| low | 4,183 | 1,046 | 1,046 | 1,046 | 1,045 |
| middle | 5,127 | 1,282 | 1,282 | 1,282 | 1,281 |
| high | 6,138 | 1,535 | 1,535 | 1,534 | 1,534 |

All three scenarios retain 115 in-service SimBench load nodes and exact per-node public totals from the candidate adapter artifact.

## Candidate Library Checks

The readiness artifact verifies, from committed metadata only, that public Set B exposes four candidate capacity classes and 300 candidate members per class:

- `public_11kw`: 11 kW, 300 candidate members.
- `public_13kw`: 13 kW, 300 candidate members.
- `public_15kw`: 15 kW, 300 candidate members.
- `public_22kw`: 22 kW, 300 candidate members.

Member traceability remains compact rather than row-expanded: later manifests must record scenario, node ID, capacity class, `cp_capacity_kw`, component ID, library ID, batch seed, returned profile index, source member ID, component stream ID, candidate processed-file checksum, and EV-CAL-001 mapping rule ID.

## Non-Claims

This packet does not inspect behavioral or tail adequacy, does not use held-out public profiles, does not include public smart charging or DC/fast charging, does not choose a final low/middle/high paper branch, and does not certify Set B library adequacy.
