# E2.S2 EV Member-Selection Implementation Plan

Task: E2.S2 EV model
Status: planning only; EV-005B not approved
Artifact: `data/metadata/ev_adoption/e2_s2_ev_member_selection_implementation_plan.json`

## Why This Plan Exists

PR #147 proposed EV-005B but did not approve it. The next safe EV step is to
make the future implementation auditable before any real member draws happen.
This packet specifies what IC-1-facing EV member selection should record if the
PI later approves the proposed with-replacement policy.

No member selection, profile-array loading, held-out access, net-load/event
analysis, `P(E)`, manuscript number, or `M` sufficiency claim is produced here.

## Authorization Boundary

The plan is blocked until `EV-005B` is approved or amended in
`registers/DECISIONS.md`. Until then, implementation must not materialize real
per-realization EV source-member draws.

After approval, the intended route is candidate-only member selection from the
committed EV readiness artifacts. The future code should verify candidate
processed-file checksums before profile arrays are loaded in the consuming
worktree, but this planning PR itself does not open those files.

## Planned Inputs After Approval

- `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json`
- `data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json`
- `data/metadata/ev_adoption/e2_s2_ev005_replacement_policy_packet.json`
- `RNG-001` component streams supplied by the whole-system realization context:
  `ev_home` for home selections and `ev_public` for public selections.

The sampler should not accept raw integer seeds. Stream construction belongs in
the calling realization context so alpha, endpoint, and treatment branches share
the same aleatory identity.

## Planned Manifest Fields

Future selection manifests should record at least:

- scenario, planning year, sample index, root seed;
- component ID, component stream ID, component seed;
- node ID, capacity class, and `cp_capacity_kw`;
- selection index and selection count at the node;
- replacement policy ID and replacement-enabled flag;
- source member ID, batch seed, and returned profile index;
- candidate processed path and SHA-256 expectation;
- EV-CAL-001 calendar mapping rule and source-index policy;
- duplicate-within-realization flag and duplicate multiplicity.

## Duplicate-Member Logging

If EV-005B is approved as proposed, duplicate source members are expected
bootstrap multiplicities. They must be logged explicitly, not hidden by
aggregation. The duplicate key should include scenario, sample index, component,
capacity class, and source member ID. The duplicate report should include the
selection indices that reused the same source member.

Duplicate rows do not create new unique source profiles and do not imply that
`M = 1000` home or `M = 1200` public is sufficient. EV-005 finite-library
adequacy remains downstream of IC-1 aggregation and E3.S2a authorization.

## Required Checks Before Future Implementation

- `EV-005B` is approved or amended before real draws.
- Candidate-only artifacts reject held-out and quarantined partitions.
- Candidate processed checksums verify before array loading.
- Scenario/node totals conserve EV-007A/A-014 counts after capacity-class
  allocation.
- Member IDs, seeds, and returned indices are traceable.
- Duplicate-member logging is produced for every realized sample when
  replacement is enabled.

## Explicit Non-Claims

- EV-005B is not approved by this plan.
- No real member draws were performed.
- No held-out or quarantined EV data were accessed.
- No profile arrays were loaded.
- No integrated net-load, event, `P(E)`, capacity-screen, or manuscript result
  was produced.
- No claim is made that any candidate library size is sufficient.
