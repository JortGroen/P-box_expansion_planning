# E2.S2/E2.S6 EV IC-1 Accepted-Artifact Index Preflight

## Purpose

This packet adds a metadata-only EV index for future Agent A IC-1 preflight. It joins the merged EV component-output consumption packet with the accepted A-014 Alkmaar adoption artifact, so a future generic loader can verify that the EV NPZ output manifest, per-node adoption allocations, scenario branches, source decisions, and remaining blockers belong to one coherent candidate-only EV handoff.

## Artifact

- `data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json`
- Artifact type: `ev_ic1_accepted_artifact_index_preflight`
- Status: `accepted_ev_metadata_index_for_agent_a_preflight_blocked_for_integrated_results`
- Source artifacts:
  - `data/metadata/ev_adoption/e2_s2_ev_ic1_component_output_consumption_packet.json`
  - `data/metadata/ev_adoption/e2_s6_a014_alkmaar_executable_adoption_artifact.json`

## What The Index Checks

The builder rejects unsafe or mismatched inputs before producing the index. It verifies candidate-only policy flags, held-out/quarantined closure, no integrated analysis, no event or `P(E)` work, no capacity screen, no manuscript numbers, no `M` sufficiency claim, no final branch selection, 2035 planning-year metadata, EV-CAL-001 ordinal calendar provenance, identical 115-node axes, exact low/middle/high scenario coverage, A-014 total conservation, and public EV-008A capacity-class total conservation.

The index records scenario-level output NPZ paths and SHA-256 values from the consumption packet, but it does not load those ignored NPZ files. A future consuming worktree must verify the index and source artifact checksums, then verify each output NPZ checksum before any EV array use.

## Non-Claims

This packet does not open held-out or quarantined EV batches, certify home `M=1000` or public `M=1200` adequacy, select the final low/middle/high paper branch, run net-load aggregation, evaluate overload events, estimate `P(E)`, run capacity screens, or produce manuscript numbers.

## Remaining Blockers

- `E3.S2a-EV-HELD-OUT-ADEQUACY-NOT-RUN`
- `EV-005-M-SUFFICIENCY-NOT-CERTIFIED`
- `G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED`
- `IC-1-INTEGRATED-NET-LOAD-ASSEMBLY-NOT-RUN`
- `A-016-CROSS-COMPONENT-SCENARIO-CONSISTENCY-NOT-YET-CHECKED`

## Validation

- `./.venv/Scripts/python.exe -m pytest tests/test_ev_model.py -q -k "accepted_artifact_index"`: 4 passed, 103 deselected.
- `./.venv/Scripts/python.exe -m pytest tests/test_ev_model.py -q -k "component_output_consumption_packet or a014_executable_adoption_artifact or accepted_artifact_index"`: 11 passed, 96 deselected.
- `./scripts/task.ps1 ownership`: passed for Agent C paths.
- `./scripts/task.ps1 test-fast`: 654 passed, 2 skipped, 7 deselected.
- `git diff --check`: passed.
