# E3.S2 Executable Readiness Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. PR #215 discovers the component-readiness artifacts currently merged on `origin/main`, including the accepted metadata-only EV IC-1 component input scaffold, the EV candidate checksum preflight, the newest HP executable value-binding decision packet, the PV final-acceptance gate, the approved PV-CAP-001 installed-capacity source route, the PV-ORIENT-001 first-experiment scope decision, the proposed D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET, and the IC-1/IC-2 executable bridge preflight. It routes those artifacts through the register-backed executable-input dry run and reports which IC-1 input families are accepted, proposed or unsigned, blocked, or missing.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not call IC-2; does not detect threshold events; does not compute `P(E)`; does not produce a capacity-screen result; and does not add manuscript numbers.

The dry run used the version-controlled input `reports/e3_s2_executable_readiness_preflight_input.json` at commit `a8b31567acb5`. The standard claim-source manifest for this preflight packet is `reports/e3_s2_executable_readiness_preflight_manifest.json`.

## Result

Overall ready for executable input assembly: `false`.

Gate-accepted component families: ev, flexibility.
Proposed or unsigned packet families: baseline, hp, pv, adoption.
Gate-blocked component families: baseline, hp, pv, adoption.
Missing component families: none.

| Component | Gate result | Packet status | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | blocked | scaffold present; accepted executable artifact missing | e2_s5_baseline_diversity_readiness_report | -- | E2.S5-BASELINE-EXECUTABLE-ARTIFACT | reports/e2_s5_baseline_diversity_readiness.md |
| ev | accepted | accepted | e2_s2_ev_ic1_component_input_scaffold | EV-003, EV-004, EV-005, EV-005B, EV-007A, EV-008A, EV-CAL-001, A-014 | -- | data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json |
| hp | blocked | proposed executable-value-binding decision packet; approval template only | hp001_alkmaar_gm0361_executable_value_binding_decision_packet | HP-001, D-013, D013-PBL-MAPPING, A-015, WEATHER-001, D004-SOURCE-MEMBER-ACCEPTANCE | E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, value_column, denominator, unit_conversion, sfh_mfh_split, adoption_electrification, d004_paired_weather_acceptance, cold_spell_tolerances | data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json |
| pv | blocked | blocked pending PV-PARAM-001, D-014 value/source packets, final paired HP/PV acceptance, and cold-spell acceptance; PV-CAP-001/PV-ORIENT-001 route and scope approved but executable values pending | d004_pv_final_acceptance_gate_packet | WEATHER-001, D004-MC-001, D004-SOURCE-MEMBER-ACCEPTANCE, PV-CAP-001, PV-ORIENT-001 | PV-PARAM-001, D-014, D014-PV-CAPACITY-SOURCE-VALUE-PACKET, D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET, FINAL-PAIRED-HP-PV-ACCEPTANCE, COLD-SPELL-ACCEPTANCE | data/metadata/weather_pv/d004_pv_final_acceptance_gate_packet.json |
| adoption | blocked | proposed preview; accepted executable per-node adoption artifact missing | e2_s6_a014_alkmaar_allocation_preview | EV-007A, A-014 | E2.S6-PER-NODE-EXECUTABLE-ADOPTION-ARTIFACT | data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json |
| flexibility | accepted | approved scaffold protocol; real flexibility values/results pending | flex001_scaffold_protocol | FLEX-001 | -- | src/flex_aggregator.py |

## Interpretation

The accepted metadata-only EV IC-1 component input scaffold and FLEX-001 scaffold protocol are register-backed enough for this metadata gate. The EV row now carries the merged candidate checksum preflight provenance, which verified candidate processed files by SHA-256 without loading arrays. That does not open held-out EV data, certify EV library adequacy, approve real flexibility values, or run any event-based analysis.

Baseline, HP, PV/weather, and adoption are not ready for executable IC-1 aggregation. Baseline still lacks an accepted executable adapter artifact. HP now has the proposed `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET` as the newest packet; it is an approval template only, so the current blockers are `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET`, `value_column`, `denominator`, `unit_conversion`, `sfh_mfh_split`, `adoption_electrification`, `d004_paired_weather_acceptance`, and `cold_spell_tolerances`. PV/weather now records that `PV-CAP-001` approves the installed-capacity source route and `PV-ORIENT-001` approves statistical orientation/tilt scope only; concrete D-014 retrieval, numeric capacity values, scenario growth, capacity convention, per-node allocation, statistical orientation/tilt source/weights, `PV-PARAM-001`, final paired HP/PV acceptance, and cold-spell acceptance remain unresolved before executable PV/weather input. Adoption has approved local counts/allocation governance but the discovered preview is not an accepted executable per-node adoption artifact.

The merged IC-1/IC-2 bridge preflight confirms that G0-A3 metadata can be carried forward as strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps, with `1.1` and `1.2` only as explicit sensitivities. PR #215 does not build loading trajectories or evaluate that threshold.

## Reproduction

Command: `.\.venv\Scripts\python.exe reports\e3_s2_generate_executable_readiness_preflight.py`
Input SHA-256: `bd560b23aff38ab47ddb9625fe2ae4dbb9662516e1b3373edd85f635d85914d7`
Generated from git commit: `a8b31567acb5714abf34c3644251087d98478a6d`

Verification for PR #215 should still use `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test-fast`, and `git diff --check`.
