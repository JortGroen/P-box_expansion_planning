# E3.S2b Integrated Pre-Run Readiness

Task: E3.S2b future-layer capacity/domain screen pre-run design scaffold.
Status: metadata/preflight only. This packet composes the current Agent A IC-1 accepted-artifact gate with E3.S2b launch-shape checks on current `origin/main` through PR #255. It consumes the merged EV accepted index and checksum preflight, PV first-experiment approval/preflight blocker packets, the synthetic IC-1 assembly gate, the accepted-artifact blocker refresh, and Agent B trust/readiness context as metadata only.

## Boundary

This is not a real IC-1 or IC-2 run. It does not load component arrays; aggregate net load; execute IC-2; evaluate thresholds; detect or count events; estimate `P(E)`; choose total versus firm capacity; use A-013/G2 numerical values; classify capacity/domain cases; or produce manuscript numbers.

G0-A3 appears only as governed metadata: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with `1.1` and `1.2` retained only as explicit sensitivities. No threshold is evaluated here.

The version-controlled input is `reports/e3_s2b_integrated_prerun_readiness_input.json`. The claim-source manifest for this pre-run readiness packet is `reports/e3_s2b_integrated_prerun_readiness_manifest.json`.

## Planned E3.S2b Screen Shape

| Field | Value |
| --- | --- |
| Scenarios | low, middle, high |
| Planning years | 2030, 2033, 2035 |
| Rho endpoints | 0.0, 1.0 |
| Planned metadata cases | 18 |
| Timestep cadence | 900 seconds |
| Capacity convention status | pending_g1_a2_e3_s2b |

## Readiness Result

Ready for E3.S2b pre-run launch: `false`.
Ready for accepted-artifact loader execution: `false`.
Blocker count: `25`.
Blocked component families: adoption, baseline, ev, flexibility, hp, pv.
Executable input gate states: adoption: accepted; baseline: blocked; ev: accepted; flexibility: accepted; hp: blocked; pv: blocked.

## Source Metadata Packets

| Component | Artifact | State | Path | Observed SHA-256 |
| --- | --- | --- | --- | --- |
| baseline | e2_s5_baseline_diversity_readiness_report | checksum-verified | reports/e2_s5_baseline_diversity_readiness.md | 35dddc989ff32e313ffcb22c16d26f494596445b6ba1879117168feb285a9d0c |
| ev | e2_s2_ev_ic1_accepted_artifact_index_preflight | checksum-verified | data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json | 927a0c734592ef4defe17c045da9ab14bc6ba8d864fb415262e9811e3ab234b3 |
| hp | hp001_alkmaar_gm0361_executable_value_binding_decision_packet | checksum-verified | data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json | 609a9631498559c6af4926f640e0c00ac9d2cac44aa40e8b3dbf5cd80a952270 |
| pv | D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET | checksum-verified | data/metadata/weather_pv/d014_pv_first_experiment_approval_packet.json | f2048ffcee50e0e770673d49e74d6ff14f50a0ca9a3e269ec5ba58bcb79482b9 |
| adoption | e2_s6_a014_alkmaar_executable_adoption_artifact | checksum-verified | data/metadata/ev_adoption/e2_s6_a014_alkmaar_executable_adoption_artifact.json | 5504d71bda5c388254013690c64407763bb37179a5cd82b6aa1199f216d933ad |
| flexibility | flex001_scaffold_protocol | checksum-verified | src/flex_aggregator.py | 7b07ffb68d8e153593c47cd611f653a2208c37c7836275566e6d783a87a583cb |

## Component-Output Manifest Boundary

| Component | Manifest state | Manifest path | Checksum match |
| --- | --- | --- | --- |
| baseline | missing | -- | -- |
| ev | blocked | data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json | True |
| hp | missing | -- | -- |
| pv | missing | -- | -- |
| adoption | missing | -- | -- |
| flexibility | missing | -- | -- |

## Planned-Year Coverage

| Component | Covered years in current metadata | Missing planned years |
| --- | --- | --- |
| baseline | 2035 | 2030, 2033 |
| ev | 2035 | 2030, 2033 |
| hp | -- | 2030, 2033, 2035 |
| pv | -- | 2030, 2033, 2035 |
| adoption | 2035 | 2030, 2033 |
| flexibility | 2035 | 2030, 2033 |

## Supporting Metadata Consumed

| Label | Path | State | Observed SHA-256 |
| --- | --- | --- | --- |
| accepted_artifact_refresh_input | reports/e3_s2_accepted_artifact_blocker_preflight_input.json | checksum-verified | 374de84d5899286c28f0f36a6a7d11a60483804c35726e762e6cb4f34346da30 |
| accepted_artifact_refresh_manifest | reports/e3_s2_accepted_artifact_blocker_preflight_manifest.json | checksum-verified | 97d7d36ab8757f88f122eae1fd9c1ee09dd7ed524cf947faacad33499180b325 |
| accepted_artifact_refresh_report | reports/E3_S2_ACCEPTED_ARTIFACT_BLOCKER_PREFLIGHT.md | checksum-verified | 26994d0b025a07887f0fd17f71cd21ecb78f15601cdf17671e487569e64e2d86 |
| agent_b_pre_experiment_readiness | reports/pre_experiment_readiness_b.md | checksum-verified | 008048d81de8cf16e0c15beb7966446f209cb57746e240605c27e70407d56013 |
| agent_b_trust_certificate_log | reports/agent_logs/agent-b/E5.S4-trust-certificate-manifest.md | checksum-verified | 4b5b0d09896df272b9c59b081ff2eee65babe02631514af4ae4b5f9d22f3fccb |
| ev_accepted_artifact_index | data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json | checksum-verified | 927a0c734592ef4defe17c045da9ab14bc6ba8d864fb415262e9811e3ab234b3 |
| ev_candidate_output_checksum_preflight | data/metadata/ev_adoption/e3_s2a_ev_candidate_component_output_checksum_preflight.json | checksum-verified | 7fd8b7f02a753867abcb1c5646d4c288f522e7eaa49ad26e88256a4f7746e508 |
| ev_heldout_adequacy_blocker | data/metadata/ev_adoption/e3_s2a_ev_heldout_adequacy_preflight_blockers.json | checksum-verified | 163b780b5235a280e92da80758ef7835b5fe1163a903a62a2ccdf1607a2df97d |
| hp_readiness_approval_checklist | data/metadata/hp_scaling/hp001_alkmaar_gm0361_readiness_approval_checklist.json | checksum-verified | 4a32bbffaf171660e2f80d4ad8f874f2da58b74390008d8481057df2da00034a |
| prior_e3_s2b_e3s3_prerun_skeleton | reports/E3_S2B_E3S3_PRERUN_CONFIG_SKELETON.md | checksum-verified | 27377f319dedaa79ea2a871800602309e77d9087d624ee734410863600344660 |
| pv_executable_preflight_guard | data/metadata/weather_pv/d014_pv_executable_preflight_guard.json | checksum-verified | 9a1df205142f29853b3250f7aa9af882ca818817a7b488a402ef036aee14a5c5 |
| pv_executable_readiness_blockers | data/metadata/weather_pv/d014_pv_executable_readiness_blockers.json | checksum-verified | 9bf7ed48cf266e3292d5bafc179becb0326160329056c9845d5ee9f7e9bc5844 |
| pv_first_experiment_approval_packet | data/metadata/weather_pv/d014_pv_first_experiment_approval_packet.json | checksum-verified | f2048ffcee50e0e770673d49e74d6ff14f50a0ca9a3e269ec5ba58bcb79482b9 |
| synthetic_ic1_assembly_input | reports/e3_s2_synthetic_assembly_real_gate_input.json | checksum-verified | c71272ad9d2e2f70a8eb13f3a140e9dd4f076f1e1a54702e683200a2c4ce4b02 |
| synthetic_ic1_assembly_manifest | reports/e3_s2_synthetic_assembly_real_gate_manifest.json | checksum-verified | 26672f9022a2c10ae4fda1ae8df584e6d8ad6df4cdb3acad0a3250523de1d975 |
| synthetic_ic1_assembly_report | reports/E3_S2_SYNTHETIC_ASSEMBLY_REAL_GATE.md | checksum-verified | f7f2c362ec8ae63a207bc6032ae8af174d21d3002f8b166368e3c22a3e566dab |

## Blocker Manifest

| Component | Code | Blocker IDs | Path | Message |
| --- | --- | --- | --- | --- |
| baseline | component_artifact_gate_blocked | E2.S5-BASELINE-EXECUTABLE-ARTIFACT | -- | component executable-input gate is not accepted |
| hp | component_artifact_gate_blocked | E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, value_column, denominator, unit_conversion, sfh_mfh_split, adoption_electrification, scenario_source_consistency, d004_paired_weather_acceptance, cold_spell_tolerances | -- | component executable-input gate is not accepted |
| pv | component_artifact_gate_blocked | D014-PV-CAPACITY-APPROVAL-TEMPLATE_successor, PV-ORIENT-001_values, PV-PARAM-001_or_signed_amendment, A-016, future_node_allocation_rule, FINAL-PAIRED-HP-PV-ACCEPTANCE | -- | component executable-input gate is not accepted |
| -- | capacity_provenance_missing | G1-A2-CAPACITY-CONVENTION | -- | capacity denominator provenance is required before integrated trajectory acceptance |
| -- | downstream_gate_blocked | A-013 | -- | downstream gate remains unresolved before executable integrated analysis |
| -- | downstream_gate_blocked | G2 | -- | downstream gate remains unresolved before executable integrated analysis |
| -- | downstream_gate_blocked | G1-A2 | -- | downstream gate remains unresolved before executable integrated analysis |
| -- | downstream_gate_blocked | A-016 | -- | downstream gate remains unresolved before executable integrated analysis |
| -- | downstream_gate_blocked | G1-A2-CAPACITY-CONVENTION | -- | downstream gate remains unresolved before executable integrated analysis |
| -- | downstream_gate_blocked | A016-SCENARIO-CONSISTENCY | -- | downstream gate remains unresolved before executable integrated analysis |
| -- | calendar_id_mismatch | ALEA-001 | -- | all executable component artifacts must cite one common ALEA-001 calendar before loader use |
| baseline | component_output_manifest_missing | E2.S5-BASELINE-COMPONENT-OUTPUT-ARTIFACT | -- | accepted component-output manifest is required before artifact-loader execution |
| ev | component_output_manifest_required_keys_missing | E3.S2-EV-COMPONENT-OUTPUT-SCHEMA | data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json | component-output manifest is not in the accepted-artifact loader schema |
| hp | component_output_manifest_missing | HP-001, E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, D004-PAIRED-HP-PV-ACCEPTANCE | -- | accepted component-output manifest is required before artifact-loader execution |
| pv | component_output_manifest_missing | PV-PARAM-001, D-014, D014-PV-CAPACITY-APPROVAL-TEMPLATE, FINAL-PAIRED-HP-PV-ACCEPTANCE | -- | accepted component-output manifest is required before artifact-loader execution |
| adoption | component_output_manifest_missing | E3.S2-ADOPTION-COMPONENT-OUTPUT-MANIFEST | -- | accepted component-output manifest is required before artifact-loader execution |
| flexibility | component_output_manifest_missing | E3.S1-FLEX-REAL-VALUES-NOT-SIGNED | -- | accepted component-output manifest is required before artifact-loader execution |
| baseline | component_year_coverage_incomplete | E3.S2B-BASELINE-YEAR-COVERAGE | -- | component-output manifests must cover every planned E3.S2b screen year before launch |
| ev | component_year_coverage_incomplete | E3.S2B-EV-YEAR-COVERAGE | -- | component-output manifests must cover every planned E3.S2b screen year before launch |
| hp | component_year_coverage_incomplete | E3.S2B-HP-YEAR-COVERAGE | -- | component-output manifests must cover every planned E3.S2b screen year before launch |
| pv | component_year_coverage_incomplete | E3.S2B-PV-YEAR-COVERAGE | -- | component-output manifests must cover every planned E3.S2b screen year before launch |
| adoption | component_year_coverage_incomplete | E3.S2B-ADOPTION-YEAR-COVERAGE | -- | component-output manifests must cover every planned E3.S2b screen year before launch |
| flexibility | component_year_coverage_incomplete | E3.S2B-FLEXIBILITY-YEAR-COVERAGE | -- | component-output manifests must cover every planned E3.S2b screen year before launch |
| -- | scenario_consistency_not_accepted | A-016, A016-SCENARIO-CONSISTENCY | -- | A-016 scenario-consistency manifest must be accepted before launch |
| -- | capacity_prerun_provenance_incomplete | G1-A2, G1-A2-CAPACITY-CONVENTION, E3.S2B-CAPACITY-PROVENANCE | -- | E3.S2b must predeclare capacity provenance fields before any screen can launch |

## Interpretation

The useful current-main state is metadata-rich but still fail-closed. EV has an accepted Agent A-facing index and a checksum preflight, but the ignored candidate NPZ outputs are missing locally and no held-out adequacy result is authorized. Adoption metadata is accepted for declared branches, and FLEX-001 is approved as a scaffold protocol. PV now has first-experiment approval/checklist packets and the executable preflight guard, but PV capacity values, orientation/tilt values, conversion treatment, allocation, A-016 consistency, and final paired HP/PV acceptance remain unsigned. HP still lacks signed annual value binding, final A-016 scenario consistency, paired-weather acceptance, and cold-spell tolerances. Baseline, HP, PV, adoption, and flexibility still lack accepted generic component-output manifests for the IC-1 loader boundary.

The E3.S2b design also records that the future screen must be a predeclared 2030/2033/2035 by low/middle/high by rho-endpoint plan, but current component metadata does not yet cover all planned years. Capacity provenance is absent, and the screen cannot launch until raw MVA reporting under both total and firm conventions can be manifested without selecting a denominator. A-013 and G2 remain downstream blockers for later model-error and Tier-1 validation; this report does not use their numerical values.

## Reproduction

Command: `.\.venv\Scripts\python.exe reports\e3_s2b_generate_integrated_prerun_readiness.py`
Input SHA-256: `26a83efa6a014b56bde3e6ad18a8bb055d987d73c4a35a8bea9df973bbbee366`
Generated from git commit: `63c53c2ba371f75203189133d87c800a612c4c56`
Refresh basis: origin/main through PR #255; #251/#252/#253/#254/#255 consumed as metadata only
