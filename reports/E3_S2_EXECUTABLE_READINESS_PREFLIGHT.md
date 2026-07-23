# E3.S2 Executable Readiness Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. This packet discovers the component-readiness artifacts currently merged on `origin/main`, including the newest HP executable value-binding decision packet, the PV final-acceptance gate, and the approved PV-CAP-001 installed-capacity source route. It routes those artifacts through the register-backed executable-input dry run and reports which IC-1 input families are accepted, proposed or unsigned, blocked, or missing.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not call IC-2; does not detect threshold events; does not compute `P(E)`; does not produce a capacity-screen result; and does not add manuscript numbers.

The dry run used the version-controlled input `reports/e3_s2_executable_readiness_preflight_input.json` at commit `7408e5b52c21`. The standard claim-source manifest for this preflight packet is `reports/e3_s2_executable_readiness_preflight_manifest.json`.

## Result

Overall ready for executable input assembly: `false`.

Gate-accepted component families: ev, flexibility.
Proposed or unsigned packet families: baseline, hp, pv, adoption.
Gate-blocked component families: baseline, hp, pv, adoption.
Missing component families: none.

| Component | Gate result | Packet status | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | blocked | scaffold present; accepted executable artifact missing | e2_s5_baseline_diversity_readiness_report | -- | E2.S5-BASELINE-EXECUTABLE-ARTIFACT | reports/e2_s5_baseline_diversity_readiness.md |
| ev | accepted | accepted | e2_s2_ev_ic1_candidate_adapter_artifact | EV-003, EV-004, EV-005B, EV-007A, EV-008A, EV-CAL-001 | -- | data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json |
| hp | blocked | proposed executable-value-binding decision packet; approval template only | hp001_alkmaar_gm0361_executable_value_binding_decision_packet | HP-001, D-013, D013-PBL-MAPPING, A-015, WEATHER-001, D004-SOURCE-MEMBER-ACCEPTANCE | E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, value_column, denominator, unit_conversion, sfh_mfh_split, adoption_electrification, d004_paired_weather_acceptance, cold_spell_tolerances | data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json |
| pv | blocked | blocked pending PV-PARAM-001, final paired HP/PV acceptance, and cold-spell acceptance; PV-CAP-001 route approved but executable values pending | d004_pv_final_acceptance_gate_packet | WEATHER-001, D004-MC-001, D004-SOURCE-MEMBER-ACCEPTANCE, PV-CAP-001 | PV-PARAM-001, FINAL-PAIRED-HP-PV-ACCEPTANCE, COLD-SPELL-ACCEPTANCE | data/metadata/weather_pv/d004_pv_final_acceptance_gate_packet.json |
| adoption | blocked | proposed preview; accepted executable per-node adoption artifact missing | e2_s6_a014_alkmaar_allocation_preview | EV-007A, A-014 | E2.S6-PER-NODE-EXECUTABLE-ADOPTION-ARTIFACT | data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json |
| flexibility | accepted | approved scaffold protocol; real flexibility values/results pending | flex001_scaffold_protocol | FLEX-001 | -- | src/flex_aggregator.py |

## Interpretation

The EV candidate adapter metadata and FLEX-001 scaffold protocol are register-backed enough for this metadata gate. That does not open held-out EV data, certify EV library adequacy, approve real flexibility values, or run any event-based analysis.

Baseline, HP, PV/weather, and adoption are not ready for executable IC-1 aggregation. Baseline still lacks an accepted executable adapter artifact. HP now has the proposed `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET` as the newest packet; it is an approval template only, so the current blockers are `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET`, `value_column`, `denominator`, `unit_conversion`, `sfh_mfh_split`, `adoption_electrification`, `d004_paired_weather_acceptance`, and `cold_spell_tolerances`. PV/weather now records that `PV-CAP-001` approves the installed-capacity source route only; concrete D-014 retrieval, numeric capacity values, scenario growth, capacity convention, per-node allocation, `PV-PARAM-001`, final paired HP/PV acceptance, and cold-spell acceptance remain unresolved before executable PV/weather input. Adoption has approved local counts/allocation governance but the discovered preview is not an accepted executable per-node adoption artifact.

## Reproduction

Command: `.\.venv\Scripts\python.exe reports\e3_s2_generate_executable_readiness_preflight.py`
Input SHA-256: `339d6144b521e955e99353aad58a7c048f61ec119f90d1f358eb62975afda646`
Generated from git commit: `7408e5b52c2126e6c57f86856749515876a84825`

Verification for the PR should still use `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test`, and `git diff --check`.
