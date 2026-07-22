# E3.S2a EV Adequacy Criterion Decision Packet

Task: E3.S2a integrated library adequacy
Status: PI decision required before held-out EV use
Artifact: `data/metadata/ev_adoption/e3_s2a_ev_adequacy_criterion_packet.json`

## Why This Packet Exists

EV-005 requires candidate and held-out ElaadNL libraries to remain disjoint, and ALEA-002 requires profile-library adequacy to be assessed after complete net-load aggregation rather than by EV-only profile summaries. This packet frames the downstream criterion that must be signed before any held-out EV batches are opened for adequacy.

## Recommended Route

Agent C recommends Option A in the packet: an integrated event-probability and decision-stability criterion. Under this route, candidate-library and held-out-library results would be compared only after IC-1 aggregation, EV-CAL-001 calendar mapping, RNG-001 common-random-number design, and G0-A3 event detection are in place. The PI must sign numerical probability-bound tolerances, the near-`P_crit` decision-stability rule, and the replicate/CRN design before results are inspected.

## Alternatives

Option B adds integrated loading-distribution diagnostics, such as quantiles or episode-count diagnostics, as a supplement. It may help diagnose why a criterion passes or fails, but it should not replace event/decision stability unless the PI signs that different estimand.

Option C uses EV-only annual-energy, peak, or sustained-load tails. The packet explicitly does not recommend this as a primary criterion because it would conflict with ALEA-002. It may remain a source-quality diagnostic only.

## Preconditions Before Held-Out Access

- IC-1 can aggregate baseline, EV, HP, PV, adoption, and flexibility on one common calendar.
- EV-CAL-001 mapping is applied to loaded candidate and held-out trajectories.
- RNG-001 component streams and CRN design are fixed for the adequacy comparison.
- EV-005 within-realization replacement or no-replacement policy is signed for the tested cohort sizes.
- G0-A3 threshold/event semantics are implemented by the downstream evaluator.
- PI signs numerical tolerances before held-out adequacy results are inspected.

## Non-Claims

This packet does not sign the criterion, open held-out profiles, load generated profile arrays, run integrated net-load/event/`P(E)` analysis, claim home `M = 1000` or public `M = 1200` sufficient, or produce manuscript numbers.
