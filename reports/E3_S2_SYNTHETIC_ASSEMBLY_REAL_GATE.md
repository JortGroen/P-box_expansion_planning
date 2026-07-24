# E3.S2 Synthetic IC-1 Assembly and Real-Input Gate

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. This packet proves the IC-1 assembly surface on tiny synthetic fixtures and runs the real-project accepted-artifact gate from current committed metadata through PR #248. It does not open real component arrays.

## Boundary

The synthetic fixture is marked `synthetic_fixture_only`, uses `time_domain=window_set`, and is not in the primary full-year probability domain. It proves common calendar handling, node-axis summation, component provenance, HP/PV weather identity preservation, and import/export-ready P-net sign metadata only.

The real-project gate remains fail-closed. It checks committed metadata packet paths/checksums, register-backed artifact statuses, component-output manifest readiness, common calendar/cadence metadata, HP/PV weather identity metadata, A-016 scenario-consistency blockers, capacity-provenance blockers, and downstream G1/G2/A-013 blockers before any arrays could be accepted.

This packet performs no real net-load aggregation, no IC-2 execution, no threshold evaluation, no event detection/counting, no `P(E)`, no capacity/domain conclusion, and no manuscript-number analysis.

## Synthetic Fixture Result

Synthetic fixture assembly ready: `true`.
Synthetic primary probability domain: `false`.
Synthetic node axis: `node-a, node-b`.
Synthetic timestep count: `4`.
Synthetic net-load shape: `(2, 4)`.
Shared weather IDs: `synthetic_weather_driver_e3_s2_smoke_v1`.

| Component | Component ID | Node | Status | Array path | Array SHA-256 |
| --- | --- | --- | --- | --- | --- |
| baseline | baseline-synthetic-a | node-a | synthetic_fixture | reports/e3_s2_synthetic_assembly_real_gate_fixtures/baseline.npz | f7aa77a03f5c4eb1b7a875dbc5408e2954eadc1d6864cdb767145a7ee84b1e3f |
| ev | ev-synthetic-a | node-a | synthetic_fixture | reports/e3_s2_synthetic_assembly_real_gate_fixtures/ev.npz | 189a450569bc225cb3fc2690433d24568e82935bb02f45ad2f61d3a0347f61bd |
| hp | hp-synthetic-b | node-b | synthetic_fixture | reports/e3_s2_synthetic_assembly_real_gate_fixtures/hp.npz | 08aa5e30fb2176bedfdbd236a466a86aca0f0614427e665593bad1e43bb0a773 |
| pv | pv-synthetic-b | node-b | synthetic_fixture | reports/e3_s2_synthetic_assembly_real_gate_fixtures/pv.npz | 693652950bfd84b0434f451a7244f922b4928b907fc173c9d3425f7851851ba0 |
| adoption | adoption-synthetic-a | node-a | synthetic_fixture | reports/e3_s2_synthetic_assembly_real_gate_fixtures/adoption.npz | f0ecbc8f1183f9bf1d22f4af688c8f571308c3589672e2a4aa6d102856f298cb |
| flexibility | flexibility-synthetic-a | node-a | synthetic_fixture | reports/e3_s2_synthetic_assembly_real_gate_fixtures/flexibility.npz | 395c43491db39c21746b491541aa06fff98f74072bb5738f92f67943c28e2dec |

## Real-Project Gate

Ready for real input execution: `false`.
Real blocker count: `17`.
Blocked component families: `adoption, baseline, ev, flexibility, hp, pv`.
Real metadata source: `reports/e3_s2_accepted_artifact_blocker_preflight_input.json`.
Source checksum policy: `computed_from_current_repository_files_before_no_array_preflight`.

| Component | Blocker code | Blocker IDs | Path |
| --- | --- | --- | --- |
| baseline | component_artifact_gate_blocked | E2.S5-BASELINE-EXECUTABLE-ARTIFACT | -- |
| hp | component_artifact_gate_blocked | E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, value_column, denominator, unit_conversion, sfh_mfh_split, adoption_electrification, d004_paired_weather_acceptance, cold_spell_tolerances | -- |
| pv | component_artifact_gate_blocked | D014-PV-CAPACITY-APPROVAL-TEMPLATE, A-016, PV-ORIENT-001, PV-PARAM-001, future_node_allocation_rule, future_final_paired_acceptance | -- |
| cross-cutting | capacity_provenance_missing | G1-A2-CAPACITY-CONVENTION | -- |
| cross-cutting | downstream_gate_blocked | A-013 | -- |
| cross-cutting | downstream_gate_blocked | G2 | -- |
| cross-cutting | downstream_gate_blocked | G1-A2 | -- |
| cross-cutting | downstream_gate_blocked | A-016 | -- |
| cross-cutting | downstream_gate_blocked | G1-A2-CAPACITY-CONVENTION | -- |
| cross-cutting | downstream_gate_blocked | A016-SCENARIO-CONSISTENCY | -- |
| cross-cutting | calendar_id_mismatch | ALEA-001 | -- |
| baseline | component_output_manifest_missing | E2.S5-BASELINE-COMPONENT-OUTPUT-ARTIFACT | -- |
| ev | component_output_manifest_required_keys_missing | E3.S2-EV-COMPONENT-OUTPUT-SCHEMA | data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json |
| hp | component_output_manifest_missing | HP-001, E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET, D004-PAIRED-HP-PV-ACCEPTANCE | -- |
| pv | component_output_manifest_missing | PV-PARAM-001, D-014, D014-PV-CAPACITY-SOURCE-VALUE-PACKET, D014-PV-CAPACITY-APPROVAL-TEMPLATE, FINAL-PAIRED-HP-PV-ACCEPTANCE | -- |
| adoption | component_output_manifest_missing | E3.S2-ADOPTION-COMPONENT-OUTPUT-MANIFEST | -- |
| flexibility | component_output_manifest_missing | E3.S1-FLEX-REAL-VALUES-NOT-SIGNED | -- |

## Current Main Inputs

The generator consumes the merged Agent A accepted-artifact blocker preflight, the EV accepted-artifact index, the EV held-out adequacy blocker packet from PR #248, the PV executable preflight guard, and the PV executable readiness blocker packet as metadata references only. HP remains blocked unless a later accepted HP component-output artifact appears on main; missing HP accepted component-output artifacts are reported as blockers, not fabricated.

G0-A3 appears only as governed metadata: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with 1.1 and 1.2 as sensitivities. No event logic is run here.

## Reproduction

Command: `.\.venv\Scripts\python.exe reports\e3_s2_generate_synthetic_assembly_real_gate.py`
Input: `reports/e3_s2_synthetic_assembly_real_gate_input.json`
Input SHA-256: `6f9eaf8d2f6a1fb2086cb539ddb7b43a9f602a79006c360de4cbaebc749a7170`
Base real-gate input: `reports/e3_s2_accepted_artifact_blocker_preflight_input.json`
Base real-gate input SHA-256: `e01eb4476780ee81133fb7d03a9ffd288df8ba0ab191024103d3328c009a59f8`
Generated from git commit: `712025a6dc6b5ea35a6c705b522c5d56cfd95b18`
Standard claim-source manifest: `reports/e3_s2_synthetic_assembly_real_gate_manifest.json`
