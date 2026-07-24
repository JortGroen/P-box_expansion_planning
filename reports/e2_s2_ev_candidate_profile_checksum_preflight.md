# E2.S2 EV Candidate Profile Checksum Preflight

Status: candidate-only checksum preflight for future IC-1 EV component loading. This packet verifies local ignored candidate processed-profile files by SHA-256 before any array use. It does not load profile arrays, open held-out or quarantined batches, run net-load/event/`P(E)`, perform capacity screens, select a final low/middle/high branch, produce manuscript numbers, or claim that `M = 1000` or `M = 1200` is sufficient.

## Artifact

- Machine-readable artifact: `data/metadata/ev_adoption/e2_s2_ev_candidate_profile_checksum_preflight.json`.
- Source scaffold: `data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json`.
- Source readiness artifact: `data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json`.

## Verification

Agent C verified 22 candidate processed NPZ files at `2026-07-24T09:23:09.181847Z` by hashing file bytes only. The check covered 2200 candidate members: 1000 home members and 1200 public members. Public Set B remains capacity-stratified with {'public_11kw': 300, 'public_13kw': 300, 'public_15kw': 300, 'public_22kw': 300}.

Every observed SHA-256 matched the committed expected SHA-256 from the candidate readiness metadata. The ignored processed files remain local and unredistributed; future Agent A IC-1 consumption must reverify checksums in its consuming worktree before loading arrays.

## Boundary

This is still a preflight artifact, not a component-output trajectory. It records that candidate file integrity is ready for later IC-1 loading under EV-005B and EV-CAL-001. It preserves candidate/held-out separation and keeps all downstream adequacy, event, probability, capacity, final-branch, and manuscript claims blocked.
