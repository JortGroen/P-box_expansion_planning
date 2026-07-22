# E2.S2 EV-To-Integration Readiness

Task: E2.S2 EV model readiness for later IC-1 integration  
Status: metadata/adapter contract only  
Artifact: `data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json`

## Purpose

This packet exposes the approved EV source-library and A-014 allocation inputs
in a clean shape that Agent A can later consume through IC-1. It is a
manifest/provenance and allocation handoff only. It does not load generated
profile arrays, open held-out adequacy batches, aggregate net load, run
threshold/event analysis, estimate `P(E)`, or produce manuscript-result
numbers.

## Candidate EV Source Libraries

The readiness artifact references candidate batches only:

| Component | Library | Candidate members | Candidate seeds | Governing decisions |
|---|---:|---:|---|---|
| `ev_home` | `A_home_vancar_cp_y2030` | 1,000 | `140001` through `140901`, step 100 | EV-003, EV-004, EV-005, EV-006 |
| `ev_public` | `B_public_vancar_cp_y2030_equal_mix` | 1,200 | `152001`-`153101` per EV-008A capacity classes | EV-002, EV-003, EV-005, EV-008A |

Each candidate batch record carries:

- source manifest path;
- processed NPZ path and SHA-256;
- batch seed;
- returned-profile index range;
- member ID pattern `profile_<batch seed>_<returned profile index>`;
- timestamp count `35,040`;
- distinct-member count;
- public capacity class and `cp_capacity_kw` where applicable.

Held-out counts are retained only as sealed metadata: home `H = 200`, public
`H = 400`. `held_out_access = false`, `held_out_unopened_for_adequacy = true`,
and `library_adequacy_proven = false` are enforced in code and tested.

## A-014 Node Allocations

The artifact includes the EV-007A-approved Alkmaar 2035 low/middle/high local
charge-point totals, materialized through approved A-014 static `p_mw` weights
and deterministic largest-remainder rounding across 115 SimBench `net.load`
rows.

| Scenario | Home charge points | Public charge points |
|---|---:|---:|
| low | 7,992 | 4,183 |
| middle | 9,386 | 5,127 |
| high | 10,343 | 6,138 |

For each scenario, the artifact records complete `home_by_node` and
`public_by_node` integer dictionaries and the source provenance from
`configs/scenarios.yaml`.

## Calendar And Sampling Assumptions

The EV profile libraries remain generated on the 2025 local calendar with
15-minute cadence:

- first local timestamp: `2025-01-01T00:00:00+01:00`;
- first UTC timestamp: `2024-12-31T23:00:00+00:00`;
- timestep count: `35,040`;
- profile timezone: `Europe/Amsterdam`;
- planning-layer use: mapped deterministically to the common planning-year
  calendar before IC-1 aggregation.

The artifact preserves EV-003/EV-005 separation:

- source library size `M` is recorded but not certified sufficient;
- future Monte Carlo size `N` remains separate;
- within-realization replacement remains explicit and pending;
- selected source-member IDs must later be recorded with the RNG-001 component
  stream identity.

## What Agent A Can Use Later

Agent A can use the artifact as a metadata/config handoff for a future IC-1 EV
adapter:

1. select only `candidate_batches`;
2. resolve local ignored NPZ paths and verify the committed SHA-256 before
   loading;
3. sample complete members under RNG-001 component streams;
4. apply the approved per-node `K_home` and `K_public` allocations;
5. align the selected complete trajectories to the common calendar before
   aggregation.

The artifact is not itself an IC-1 implementation and does not change the IC-1
schema.

## Explicit Non-Claims

- Held-out EV profiles were not opened for adequacy.
- Candidate profile arrays were not opened to create this artifact.
- No public smart-charging, DC, or fast-charging profiles are included.
- No integrated net-load, transformer loading, threshold, event, `P(E)`,
  capacity-screen, or manuscript-result analysis was performed.
- `M = 1000` for home and `M = 1200` for public are not claimed sufficient.

## Verification

Added tests in `tests/test_ev_model.py` cover:

- candidate-only filtering from library manifests;
- rejection of manifests that expose held-out adequacy or claim library
  sufficiency;
- combination of home/public library artifacts with A-014 allocations;
- stable writing of the readiness JSON;
- committed-artifact checks for candidate counts, policy flags, scenario totals,
  seed provenance, and 115-node allocation dictionaries.

