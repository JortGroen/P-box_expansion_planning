# E3.S2 Current-Main Real-Artifact Assembly Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. This packet instantiates `build_real_artifact_assembly_preflight(...)` from the current committed metadata surface on `origin/main` after PR #221, #222, and #223. It reports which component packet references are accepted, unsigned, blocked, missing, or checksum-unverified before any component arrays are opened.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not execute IC-2; does not detect or count events; does not compute `P(E)`; does not produce a capacity/domain conclusion; and does not add manuscript numbers.

The dry run used the version-controlled input `reports/e3_s2_real_artifact_assembly_preflight_input.json` at commit `34e8412431ef`. The standard claim-source manifest for this preflight packet is `reports/e3_s2_real_artifact_assembly_preflight_manifest.json`.

## Result

Overall ready for real-artifact assembly: `false`.

Accepted component families: ev, flexibility.
Unsigned/scaffold component families: baseline, hp, pv, adoption.
Gate-blocked component families: baseline, hp, pv, adoption.
Missing component families: none.
Checksum-verified source packet paths: none.
Checksum-unverified source packet paths: reports/e2_s5_baseline_diversity_readiness.md, data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json, data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json, data/metadata/weather_pv/d004_pv_final_acceptance_gate_packet.json, data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json, src/flex_aggregator.py.
Checksum-mismatched source packet paths: none.
Missing source packet paths: none.

| Component | Gate result | Packet status | Source packet status | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | blocked | scaffold present; accepted executable artifact missing | checksum-unverified | e2_s5_baseline_diversity_readiness_report | -- | E2.S5-BASELINE-EXECUTABLE-ARTIFACT | reports/e2_s5_baseline_diversity_readiness.md |
| ev | accepted | accepted | checksum-unverified | e2_s2_ev_ic1_component_input_scaffold | EV-003, EV-004, EV-005, EV-005B, EV-007A, EV-008A, EV-CAL-001, A-014 | -- | data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json |
| hp | blocked | proposed executable-value-binding decision packet; approval template only | checksum-unverified | hp001_alkmaar_gm0361_executable_value_binding_decision_packet | HP-001, D-013, D013-PBL-MAPPING, A-015, WEATHER-001, D004-SOURCE-MEMBER-ACCEPTANCE | E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, value_column, denominator, unit_conversion, sfh_mfh_split, adoption_electrification, d004_paired_weather_acceptance, cold_spell_tolerances | data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json |
| pv | blocked | blocked pending PV-PARAM-001, D-014 value/source packets including CBS anchor value choice, final paired HP/PV acceptance, and cold-spell acceptance; PV-CAP-001/PV-ORIENT-001 route and scope approved but executable values pending | checksum-unverified | d004_pv_final_acceptance_gate_packet | WEATHER-001, D004-MC-001, D004-SOURCE-MEMBER-ACCEPTANCE, PV-CAP-001, PV-ORIENT-001 | PV-PARAM-001, D-014, D014-PV-CAPACITY-SOURCE-VALUE-PACKET, D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE, D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET, FINAL-PAIRED-HP-PV-ACCEPTANCE, COLD-SPELL-ACCEPTANCE | data/metadata/weather_pv/d004_pv_final_acceptance_gate_packet.json |
| adoption | blocked | proposed preview; accepted executable per-node adoption artifact missing | checksum-unverified | e2_s6_a014_alkmaar_allocation_preview | EV-007A, A-014 | E2.S6-PER-NODE-EXECUTABLE-ADOPTION-ARTIFACT | data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json |
| flexibility | accepted | approved scaffold protocol; real flexibility values/results pending | checksum-unverified | flex001_scaffold_protocol | FLEX-001 | -- | src/flex_aggregator.py |

| Component | Artifact | Source packet status | Exists | Observed SHA-256 | Expected SHA-256 | Path |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | e2_s5_baseline_diversity_readiness_report | checksum-unverified | true | 35dddc989ff32e313ffcb22c16d26f494596445b6ba1879117168feb285a9d0c | -- | reports/e2_s5_baseline_diversity_readiness.md |
| ev | e2_s2_ev_ic1_component_input_scaffold | checksum-unverified | true | 4556c9b4494bd7ff4dfb534792e51b557290b714c63f10a54e03c5ddbca49b97 | -- | data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json |
| hp | hp001_alkmaar_gm0361_executable_value_binding_decision_packet | checksum-unverified | true | 609a9631498559c6af4926f640e0c00ac9d2cac44aa40e8b3dbf5cd80a952270 | -- | data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json |
| pv | d004_pv_final_acceptance_gate_packet | checksum-unverified | true | e88761b7735681ea1a3f59445617899d6dcc4f723779661115c3a99d1b85b94a | -- | data/metadata/weather_pv/d004_pv_final_acceptance_gate_packet.json |
| adoption | e2_s6_a014_alkmaar_allocation_preview | checksum-unverified | true | a36563243e52c7b0f4cb169f151324784937d2374e5f68891db2a1e05408fc7f | -- | data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json |
| flexibility | flex001_scaffold_protocol | checksum-unverified | true | 7b07ffb68d8e153593c47cd611f653a2208c37c7836275566e6d783a87a583cb | -- | src/flex_aggregator.py |

## Interpretation

EV and flexibility are the only gate-accepted component families in this metadata preflight. EV remains metadata-only: candidate checksum provenance is recorded, PR #224 EV component-output verifier availability is `pending_open_pr_224_not_merged`, no held-out EV data are opened, and no candidate profile arrays are loaded. FLEX-001 is approved only as a scaffold protocol; real flexibility values/results remain outside this packet.

Baseline, HP, PV/weather, and adoption remain blocked before executable IC-1 aggregation. Baseline lacks an accepted executable adapter artifact. HP still needs the signed HP annual value binding choices, D-004 paired-weather acceptance, and cold-spell tolerances. PV/weather includes the newly merged D-014 CBS Alkmaar PV-capacity anchor evidence from PR #222 and the existing final-acceptance gate packet, but PV-PARAM-001, D-014 value/source choices, final paired HP/PV acceptance, cold-spell acceptance, scenario growth, capacity convention, per-node allocation, and statistical orientation/tilt values remain unsigned. Adoption still lacks an accepted executable per-node artifact.

The bridge preserves G0-A3 as governed metadata only: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with `1.1` and `1.2` only as explicit sensitivities. A-013, G2, G1-A2 capacity/domain provenance, A-016 scenario consistency, and the missing capacity-convention/domain choices remain downstream blockers; no threshold is evaluated here.

## Reproduction

Command: `.\.venv\Scripts\python.exe reports\e3_s2_generate_real_artifact_assembly_preflight.py`
Input SHA-256: `37bc5223f5995b8be436f0740aa962cb8d36f09b55cf0af67e29ea4b2b399f1f`
Generated from git commit: `34e8412431ef04bb5fb8d35cefa74ff3cc74f5e5`

Verification for this PR should use focused `tests/test_evaluator_net_load.py`, `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test-fast`, and `git diff --check`.
