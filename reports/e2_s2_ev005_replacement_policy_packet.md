# E2.S2 EV-005 Replacement Policy Packet

Task: E2.S2 EV model
Status: PI decision required before EV member-selection implementation
Artifact: `data/metadata/ev_adoption/e2_s2_ev005_replacement_policy_packet.json`

## Why This Packet Exists

EV-005 deliberately left the within-realization EV replacement rule unsigned.
That rule now blocks executable IC-1 EV sampling: Agent A can consume candidate
library metadata only after the project knows whether a realization may select
the same ElaadNL source member more than once.

This packet frames that choice using the already approved 2035 Alkmaar EV-007A
cohort totals, EV-008A public capacity classes, EV-CAL-001 calendar mapping,
and RNG-001 component-stream discipline. It does not implement sampling or load
profile arrays.

## Cohort And Library Context

Approved 2035 Alkmaar local-grid cohorts exceed the available candidate source
members:

| Scenario | Home K | Public K | Public per-class K range |
|---|---:|---:|---:|
| low | 7,992 | 4,183 | 1,045-1,046 |
| middle | 9,386 | 5,127 | 1,281-1,282 |
| high | 10,343 | 6,138 | 1,534-1,535 |

The candidate libraries contain `M = 1,000` home members and `M = 300` members
per public EV-008A capacity class. Whole-grid no-replacement sampling is
therefore not executable for the approved 2035 branches.

## Recommended Unsigned Option

Agent C recommends PI review of Option A: charge-point-level sampling with
replacement from the verified candidate library for the relevant component and,
for public charging, capacity class.

Under this option, duplicate source members inside one realization are explicit
bootstrap multiplicities. Future manifests must preserve scenario, node,
component, capacity class, selection index, source member ID, batch seed,
returned profile index, processed checksum, replacement flag, and RNG-001
component-stream identity.

This recommendation is not a sufficiency claim. EV-005 finite-library adequacy
still belongs to the downstream E3.S2a comparison after IC-1 aggregation and
before any held-out adequacy use.

## Alternatives

Option B, whole-grid no-replacement sampling, is scientifically simple but not
executable because all approved home and public class cohorts exceed their
candidate library sizes.

Option C, node-local no-replacement with cross-node reuse, may avoid duplicate
members inside a single node, but it still reuses source members across the
same realization and hides that reuse behind a less direct rule. Agent C does
not recommend it over explicit bootstrap multiplicity.

## Non-Claims

- No policy is signed by this packet.
- No held-out or quarantined EV batches were opened.
- No generated profile arrays were loaded.
- No integrated net-load, event, `P(E)`, capacity-screen, or manuscript result
  was produced.
- No claim is made that home `M = 1,000` or public `M = 1,200` is sufficient.

## PI Decision Needed

Approve, amend, or reject EV-005B before EV IC-1 member-selection code
materializes real per-realization source-member draws.
