# E2.S2 EV IC-1 Component-Input Scaffold

Status: accepted metadata-only EV component-input scaffold for later IC-1 adapter consumption. This packet does not load EV profile arrays, open held-out or quarantined batches, run net-load/event/`P(E)`, perform capacity screens, select a final low/middle/high branch, produce manuscript numbers, or claim that `M = 1000` or `M = 1200` is sufficient.

## Purpose

This packet closes the EV-side metadata gap between the approved EV candidate libraries/member selections and Agent A's IC-1 `AcceptedComponentAdapterArtifact` boundary. It materializes one fail-closed bridge artifact that references the existing candidate-only EV artifacts rather than copying generated profile arrays.

## Artifact

- Machine-readable artifact: `data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json`.
- Source candidate adapter artifact: `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json`.
- Source candidate member reference: `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json`.
- Source EV-005B selection manifest set: `data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz`.
- Source public capacity readiness artifact: `data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json`.

The scaffold records the 115 IC-1 load-node IDs, 2035 low/middle/high Alkmaar home and public charge-point allocations, EV-008A public capacity-class splits, candidate member counts, duplicate/multiplicity summary provenance from the EV-005B selection manifest set, RNG-001 seed-tree identity, and EV-CAL-001 ordinal calendar mapping metadata.

## IC-1 Bridge

The artifact includes an `ic1_accepted_component_adapter_artifact` record with `kind = ev`, source/member/calendar/node metadata, and provenance fields compatible with Agent A's metadata-only accepted-artifact bridge. It is still not a trajectory adapter output: future consumption must verify the candidate selection manifest checksum, verify candidate processed-file checksums in the consuming worktree, load candidate profiles only, and apply EV-CAL-001 before IC-1 aggregation.

## Guardrails

The artifact is fail-closed by policy: `held_out_access`, `quarantined_access`, `profile_arrays_loaded`, `integrated_analysis_performed`, event/`P(E)` analysis, capacity screens, manuscript numbers, M-sufficiency claims, and final branch selection are all false. The tests rebuild the artifact from current committed metadata and reject unsafe policy drift or selection/allocation mismatches.

## Suggested STATUS Update

`E2.S2 | C | review | EV IC-1 component-input metadata scaffold; candidate-only selections and A-014 allocations bridge to IC-1 accepted-artifact metadata | blocked-by: downstream IC-1 real adapter consumption; held-out adequacy remains unopened; no M-sufficiency claim | PR: see PR body`
