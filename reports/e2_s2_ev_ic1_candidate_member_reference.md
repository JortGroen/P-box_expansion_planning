# E2.S2 EV IC-1 Candidate Member Reference

Task: E2.S2 EV-to-IC-1 readiness
Artifact: `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json`

## Purpose

This packet materializes the candidate-only EV source-member reference table that Agent A can use before real IC-1 consumption. It expands the committed candidate batch ranges into explicit source-member rows while keeping generated profile arrays ignored and unopened.

## What Is Ready

The artifact exposes:

- 1,000 residential home Set A candidate members from EV-004/EV-005.
- 1,200 public Set B candidate members from EV-008A.
- Public Set B capacity-class counts of 300 candidate members each for `public_11kw`, `public_13kw`, `public_15kw`, and `public_22kw`.
- Scenario-node requirements for the three EV-007A Alkmaar 2035 branches across 115 load nodes: 345 node rows total.
- Public node requirements split by EV-008A capacity class using the existing A-014/public Set B readiness artifact.
- EV-CAL-001 ordinal calendar mapping provenance for every candidate member row.

Each candidate member row records partition, component ID, library ID, source member ID, batch seed, returned profile index, capacity class where applicable, `cp_capacity_kw`, processed path, processed SHA-256, timestep count, EV-CAL-001 rule/version, source and target calendar IDs, source-index policy, weekday/weekend limitation, and control mode.

## IC-1 Use Boundary

This artifact does not select members for a Monte Carlo realization. It tells IC-1 which candidate members are eligible and how many home/public/public-capacity-class members each scenario-node requires. A later Agent A or integration step must still verify local processed-file checksums in its consuming worktree, apply RNG-001 component streams, record selected source-member IDs and stream identities, and map loaded candidate trajectories through EV-CAL-001 before aggregation.

## Non-Claims

No held-out adequacy batches were opened or used. No profile arrays were loaded. This artifact does not materialize an EV-005B member-selection realization; it only records eligible candidate members and required counts. No low/middle/high paper branch was selected. No net-load, congestion, event, `P(E)`, capacity-screen, or manuscript-result analysis was run. The artifact does not claim that home `M = 1000` or public `M = 1200` is sufficient.
