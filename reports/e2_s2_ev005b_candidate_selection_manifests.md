# E2.S2 EV-005B Candidate Member-Selection Manifests

Task: E2.S2 EV model
Status: candidate-only metadata materialized under approved EV-005B
Artifact: `data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz`

## Why This Exists

EV-005B now approves charge-point-level sampling with replacement from the verified candidate EV profile libraries. This packet materializes the first candidate-only member-selection manifest set for the approved EV-007A/A-014 2035 Alkmaar low, middle, and high declared branches.

The artifact is compressed deterministic JSON metadata. It records member selections and provenance only; it does not open generated profile arrays.

## Materialized Sample Identity

- RNG protocol: `RNG-001`
- Root seed: `20260722`
- Sample index: `0`
- Home component stream: `ev_home`
- Public component stream: `ev_public`
- Materialized timestamp: `2026-07-22T17:45:00Z`
- Compressed artifact size: 1,385,206 bytes
- Compressed artifact SHA-256: `4580e6a99ef70f9bf63083ce8d3561898f9c855129d87f6300ccde5a5264cce9`

This is an IC-1 readiness realization, not a manuscript Monte Carlo result and not a signed production run schedule.

## Declared Branch Totals

| Scenario | Home selections | Public selections | Public 11 kW | Public 13 kW | Public 15 kW | Public 22 kW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 7,992 | 4,183 | 1,046 | 1,046 | 1,046 | 1,045 |
| middle | 9,386 | 5,127 | 1,282 | 1,282 | 1,282 | 1,281 |
| high | 10,343 | 6,138 | 1,535 | 1,535 | 1,534 | 1,534 |

The full manifest contains 43,169 selected charge-point rows across 115 in-service SimBench load nodes per scenario.

## Provenance Fields

Each selected row records the scenario node, component, public capacity class where relevant, node-local and realization-level selection indices, source member ID, library ID, candidate partition, control mode, batch seed, returned profile index, processed candidate path, processed SHA-256 expectation, duplicate flag, and duplicate multiplicity.

Shared manifest metadata records the RNG-001 component stream records, EV-005B replacement policy, EV-CAL-001 ordinal calendar mapping, and blocked-analysis guardrails.

## Explicit Non-Claims

- No held-out or quarantined EV batches were opened or used.
- No profile arrays were loaded.
- No net-load, threshold, event, `P(E)`, capacity-screen, or manuscript-result analysis was run.
- No claim is made that home `M = 1000` or public `M = 1200` is sufficient.
- No final low/middle/high paper branch is selected.
