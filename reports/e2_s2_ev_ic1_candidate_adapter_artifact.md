# E2.S2 EV IC-1 Candidate Adapter Artifact

Task: E2.S2 EV-to-IC-1 readiness  
Status: candidate-only metadata and preflight layer  
Artifact: `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json`

## Purpose

This packet materializes the next EV handoff layer for future IC-1 integration.
It combines approved 2035 Alkmaar A-014 node allocations, candidate EV
source-library metadata, and checksum preconditions in one machine-readable
shape. It is still a readiness artifact, not an IC-1 adapter run.

## A-014 Per-Node Allocations

The artifact carries the EV-007A-approved 2035 Alkmaar local-grid totals for
the three declared branches:

| Scenario | Home charge points | Public charge points |
|---|---:|---:|
| low | 7,992 | 4,183 |
| middle | 9,386 | 5,127 |
| high | 10,343 | 6,138 |

For each scenario, the artifact includes complete integer `home_by_node` and
`public_by_node` dictionaries across the 115 in-service SimBench load nodes.
The recorded totals are conserved after deterministic A-014 largest-remainder
rounding. This does not choose the final low/middle/high paper branch.

## Candidate Library Metadata

The artifact references candidate source libraries only:

| Component | Candidate members | Candidate batch files |
|---|---:|---:|
| `ev_home` | 1,000 | 10 |
| `ev_public` | 1,200 | 12 |

Each batch record preserves:

- component ID and library ID;
- batch seed;
- processed NPZ path;
- expected processed-file SHA-256;
- returned profile index range `0` to `99`;
- member ID pattern `profile_<batch_seed>_<returned_profile_index:03d>`;
- capacity class for public batches where applicable.

Member rows are represented compactly rather than expanded into 2,200 JSON
records. The source-member identity remains reconstructable as
`(component_id, library_id, batch_seed, returned_profile_index)`.

## Checksum Verification

Agent C verified the 22 candidate processed-file SHA-256 digests in the local
worktree at `2026-07-22T08:46:58.458237Z`. Verification read file bytes only
and did not parse NPZ profile arrays.

The artifact still requires Agent A or any future consuming IC-1 worktree to
repeat checksum verification before loading ignored local processed-profile
files. This matters because the generated profile files are intentionally not
committed or redistributed.

## Calendar Mapping Status`n`nThe source profiles remain on the 2025 ElaadNL Europe/Amsterdam calendar with`n35,040 15-minute timesteps. The target planning layer is 2035 per G0-A4.`nEV-CAL-001 is now approved and implemented as ordinal timestep mapping from the`ncomplete 2025 source sequence to the 2035 planning sequence. This artifact`nrecords approved mapping metadata; actual candidate profile loading and mapped`ntrajectory construction still happen later in the consuming IC-1 worktree after`nlocal checksum verification.

## Explicit Non-Claims

- Held-out EV adequacy batches were not opened.
- Real candidate profile arrays were not loaded.
- `M = 1000` home and `M = 1200` public are not certified sufficient.
- No within-realization replacement rule was chosen.
- No net-load, congestion, threshold/event, `P(E)`, capacity-screen, or
  manuscript-result analysis was performed.

## Suggested IC-1 Consumption Order

1. Load `e2_s2_ev_ic1_candidate_adapter_artifact.json`.
2. Verify local candidate processed-file SHA-256 digests against the artifact.
3. Confirm the PI-signed calendar mapping rule and construct the common 2035
   calendar.
4. Only then load candidate NPZ arrays for RNG-001 component-stream sampling.
5. Emit EV IC-1 component outputs with source-member IDs and stream identity in
   provenance.
