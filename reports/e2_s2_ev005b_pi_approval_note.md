# EV-005B PI Approval Note

Task: E2.S2 EV model
Status: PI approval needed; no implementation activation

## Policy Needed

Approve or amend EV-005B: the within-realization EV member-selection rule for
sampling physical home/public charge points from the candidate ElaadNL source
libraries.

## Recommendation

Approve charge-point-level sampling **with replacement** from the verified
candidate library for each component and EV-008A public capacity class.

Why: approved 2035 Alkmaar cohorts exceed the candidate library sizes. Home
counts are 7,992-10,343 versus `M = 1,000`; public per-class counts exceed
1,000 while each public class has `M = 300`. Whole-grid no-replacement therefore
cannot run for the declared scenarios. With-replacement bootstrap is executable,
keeps duplicate source members explicit as multiplicities, and leaves EV-005
finite-library adequacy to downstream E3.S2a testing.

## What Approval Unlocks

If EV-005B is approved as proposed, Agent C can activate the guarded
candidate-only member-selection interface to produce per-realization selection
manifests with:

- RNG-001 component-stream identity;
- scenario, node, component, capacity class, and selection index;
- source member ID, batch seed, returned profile index, and checksum provenance;
- duplicate-member flags and multiplicities.

Approval does **not** unlock held-out access, profile-array loading for
integrated use, net-load/event/`P(E)` analysis, manuscript numbers, or any
claim that `M = 1,000` home or `M = 1,200` public is sufficient.
