# E3.S2a EV Generic Loader Manifest Packet

## Purpose

This packet converts the candidate-only EV component-output handoff into Agent A's generic accepted-artifact loader manifest shape without changing Agent A-owned code. It uses the accepted EV artifact index and the checkpointed recovery protocol from PR #260, then emits one generic component-output manifest per declared 2035 Alkmaar branch.

## Produced Metadata

| Scenario | Generic manifest | Generic manifest SHA-256 | Ignored EV NPZ | NPZ SHA-256 |
|---|---|---|---|---|
| high | `data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_high.json` | `3f0c944f66ae8c0200e3e55e58df487f0e40b6867a8f761aa1792f13a30be77d` | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_high.npz` | `dd95f30d74da00b6fb87c2ced8f402b4d612c59a28e7d1d33e9e82fcd7a805d5` |
| low | `data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_low.json` | `d3edde0cdc73f926fea965ce78746bf430477a3443d899c0b7a37915a6a4249e` | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_low.npz` | `a896794ddd9f004fe945c62a5b84b2b1b6e9381cbecd80b17ca7c749de68ce65` |
| middle | `data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_middle.json` | `1ee2e222815e42da576d74a785de24c3920d5a2f400dea859c73307fb6fd4fe2` | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_middle.npz` | `38081c7f849bb679a19560d1a7f7fd6d8428e35ef6cad2087e4d82a46c1e568d` |

The packet at `data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json` gives Agent A the exact `component_output_manifest_paths_by_kind` and `component_output_manifest_sha256_by_path` values for each branch. A future IC-1 call must choose the branch explicitly.

## Boundary

The generic manifests are accepted only as candidate EV component-output loader metadata. They preserve EV-005B replacement provenance, EV-CAL-001 calendar mapping, EV-007A/A-014 adoption and node allocation provenance, EV-008A public capacity strata, duplicate/multiplicity records, and source IDs D-002/D-010/D-012.

The committed metadata does not include the ignored NPZ files. A consuming worktree must restore or rebuild them through `data/get_ev_component_outputs.py` and verify their SHA-256 values before array loading.

## Non-Claims

This work does not open held-out or quarantined EV batches, does not call the ElaadNL API, does not certify `M = 1000` or `M = 1200`, does not select the final low/middle/high branch, and does not run net-load aggregation, event detection, `P(E)`, capacity screens, or manuscript-result analysis.
