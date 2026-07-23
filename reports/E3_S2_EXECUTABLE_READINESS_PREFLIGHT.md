# E3.S2 Executable Readiness Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.  
Status: metadata/preflight only. This packet discovers the component-readiness artifacts currently merged on `origin/main`, routes them through the register-backed executable-input dry run, and reports whether each IC-1 input family is ready, missing, or blocked.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not call IC-2; does not detect threshold events; does not compute `P(E)`; does not produce a capacity-screen result; and does not add manuscript numbers.

The dry run used the version-controlled input `reports/e3_s2_executable_readiness_preflight_input.json` at commit `7366b6f17379`. The standard claim-source manifest for this preflight packet is `reports/e3_s2_executable_readiness_preflight_manifest.json`.

## Result

Overall ready for executable input assembly: `false`.

Ready component families: ev, flexibility.  
Blocked component families: baseline, hp, pv, adoption.  
Missing component families: none.

| Component | State | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- |
| baseline | blocked | e2_s5_baseline_diversity_readiness_report | -- | E2.S5-BASELINE-EXECUTABLE-ARTIFACT | reports/e2_s5_baseline_diversity_readiness.md |
| ev | accepted | e2_s2_ev_ic1_candidate_adapter_artifact | EV-003, EV-004, EV-005B, EV-007A, EV-008A, EV-CAL-001 | -- | data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json |
| hp | blocked | hp001_alkmaar_gm0361_local_scaling_source_use_proposal | -- | D-013, HP-001-LOCAL-SCALING-VALUE-SIGNOFF | data/metadata/hp_scaling/hp001_alkmaar_gm0361_local_scaling_source_use_proposal.json |
| pv | blocked | d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact | WEATHER-001, D004-MC-001, D004-SOURCE-MEMBER-ACCEPTANCE | PV-PARAM-001, D004-PAIRED-HP-PV-VALIDATION, D004-COLD-SPELL-TOLERANCE-SIGNOFF | data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json |
| adoption | blocked | e2_s6_a014_alkmaar_allocation_preview | EV-007A, A-014 | E2.S6-PER-NODE-EXECUTABLE-ADOPTION-ARTIFACT | data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json |
| flexibility | accepted | flex001_scaffold_protocol | FLEX-001 | -- | src/flex_aggregator.py |

## Interpretation

The EV candidate adapter metadata and FLEX-001 scaffold protocol are register-backed enough for this metadata gate. That does not open held-out EV data, certify EV library adequacy, approve real flexibility values, or run any event-based analysis.

Baseline, HP, PV/weather, and adoption are not ready for executable IC-1 aggregation. Baseline still lacks an accepted executable adapter artifact. HP has source and scaling guard material, but D-013 executable values/adoption remain unsigned. D-004 WEATHER-001 source/member material is accepted for internal first-screen source/member use, but PV executable conversion is still blocked by PV-PARAM-001 and paired/cold-spell signoffs. Adoption has approved local counts/allocation governance but the discovered preview is not an accepted executable per-node adoption artifact.

## Reproduction

Command: `.\.venv\Scripts\python.exe reports\e3_s2_generate_executable_readiness_preflight.py`  
Input SHA-256: `12a5d961b0f3bdf9c57e2225f8a3ea75d40ea0a1fed30f608a80324f9c3955a4`  
Generated from git commit: `7366b6f173791dd2af440e4bf0a30c50eb926325`

Verification for the PR should still use `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test`, and `git diff --check`.
