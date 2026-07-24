# E3.S2a EV Generic Loader Manifest Packet

## Purpose

This packet converts the candidate-only EV component-output handoff into a schema-shaped metadata packet for Agent A's generic accepted-artifact preflight without changing Agent A-owned code. It uses the accepted EV artifact index and the checkpointed recovery protocol from PR #260, then emits one generic component-output manifest per declared 2035 Alkmaar branch.

The packet is intentionally fail-closed for the current Agent A NPZ loader. The EV component-output NPZs contain one 115-node array per scenario, while `load_component_adapter_output_from_npz_artifact(...)` currently expects one-dimensional `p_kw`/`q_kvar`/`timestamps` arrays for one node. The blocker is `A-LOADER-MULTI-NODE-EV-OUTPUT-CONTRACT-NOT-YET-SIGNED`: IC-1 needs either an A-owned multi-node component-output contract or an EV-owned per-node export/manifest strategy before real loader execution.

## Produced Metadata

| Scenario | Generic manifest | Generic manifest SHA-256 | Ignored EV NPZ | NPZ SHA-256 |
|---|---|---|---|---|
| high | `data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_high.json` | `14071413ade198201822263c033e52ced58408a708e9f6bcaef070a7fa7344e9` | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_high.npz` | `dd95f30d74da00b6fb87c2ced8f402b4d612c59a28e7d1d33e9e82fcd7a805d5` |
| low | `data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_low.json` | `249ba0f52d50d82f392cb80042001bae271043cebdc4f151dd8b981d56d3e43b` | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_low.npz` | `a896794ddd9f004fe945c62a5b84b2b1b6e9381cbecd80b17ca7c749de68ce65` |
| middle | `data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_middle.json` | `38a1aa41c11736476fa9a8d0aa8d9119f1dac711f819dad9302da762de1152c4` | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_middle.npz` | `38081c7f849bb679a19560d1a7f7fd6d8428e35ef6cad2087e4d82a46c1e568d` |

The packet at `data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json` gives Agent A the exact `component_output_manifest_paths_by_kind` and `component_output_manifest_sha256_by_path` values for each branch for preflight bookkeeping. A future IC-1 call must choose the branch explicitly, but current loader execution must remain blocked until the multi-node EV output contract is signed.

## Boundary

The generic manifests are blocked candidate EV component-output metadata, not accepted executable loader artifacts. They preserve EV-005B replacement provenance, EV-CAL-001 calendar mapping, EV-007A/A-014 adoption and node allocation provenance, EV-008A public capacity strata, duplicate/multiplicity records, and source IDs D-002/D-010/D-012.

The committed metadata does not include the ignored NPZ files. A consuming worktree must restore or rebuild them through `data/get_ev_component_outputs.py` and verify their SHA-256 values before array loading.

## Non-Claims

This work does not open held-out or quarantined EV batches, does not call the ElaadNL API, does not certify `M = 1000` or `M = 1200`, does not select the final low/middle/high branch, and does not run net-load aggregation, event detection, `P(E)`, capacity screens, or manuscript-result analysis.
