# E2.S2 EV Component-Output Consumption Packet

## Purpose

This packet turns the merged EV candidate-only component-output manifest into a fail-closed handoff description for future IC-1 real-artifact assembly. It does not load profile arrays, does not run net-load aggregation, and does not authorize paper-facing adequacy use. It tells a future Agent A generic loader which ignored EV-only NPZ component outputs may be consumed after checksum verification.

## Artifact

Machine-readable packet: `data/metadata/ev_adoption/e2_s2_ev_ic1_component_output_consumption_packet.json`

The packet records:

- the three declared 2035 Alkmaar branches: `low`, `middle`, and `high`;
- output NPZ paths and SHA-256 values from `e2_s2_ev_ic1_candidate_component_output_manifest.json`;
- the 115 SimBench load-node IDs and node-axis order expected in the NPZ files;
- EV-CAL-001 ordinal source-to-planning calendar mapping, 35,040 timesteps, and 900-second cadence;
- home Set A and public Set B candidate library identities, including public EV-008A capacity strata;
- A-014/EV-007A allocation provenance and EV-005B selection-manifest provenance;
- required status fields and policy guards for candidate-only IC-1 preflight use.

## Consumption Boundary

A future generic IC-1 loader may consume the listed EV-only NPZ files only after verifying each NPZ SHA-256 against the packet and keeping the scenario branch explicit. The packet is not itself a net-load result and does not choose a final low/middle/high paper branch.

The packet remains fail-closed for:

- held-out or quarantined EV profile batches;
- `M=1000` or `M=1200` sufficiency claims;
- integrated net-load aggregation;
- event detection or `P(E)`;
- capacity screens;
- manuscript-result numbers.

## Validation Added

`src.ev_model.ev_ic1_component_output_consumption_packet(...)` validates the component-input scaffold and component-output manifest before emitting the packet. The focused tests check the committed packet against the builder, reject missing scenarios, reject duplicate scenario rows, and reject unsafe policy flags.
