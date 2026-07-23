# E2.S4 PV/Weather Readiness Wording And PV Parameter Signoff

## Purpose

This packet tightens the D-004 WEATHER-001 artifact language so it reads as source/member component-input readiness, not final integrated readiness. It also prepares unsigned PV parameter signoff material for PI review.

## D-004 Readiness Wording

The committed D-004 WEATHER-001 artifact now uses source/member wording:

- `artifact_type = accepted_weather_001_source_member_index_for_component_input_gate`;
- `status = accepted_for_source_member_readiness_final_paired_cold_spell_pending`;
- `readiness_scope = source_member_component_input_only_not_final_integrated`;
- `ready_for_source_member_component_input_gate = true`.

The legacy `ready_for_executable_input_gate` boolean remains present for compatibility, but its scope is explicitly recorded as source/member component input only and not final integrated readiness.

## Consumer Gate Hardening

PV/weather consumers can call `assert_pv_weather_artifact_allows_consumer_use`. It allows only `source_member_component_input` from the current D-004 artifact. Requests for `final_paired_hp_pv_acceptance`, `cold_spell_acceptance`, `integrated_analysis`, or unknown uses fail closed while the artifact's blocked gates remain unresolved.

## PV Parameter Packet

The new `data/metadata/weather_pv/d004_pv_parameter_decision_packet.json` proposes `PV-PARAM-001` for PI review. It covers installed-capacity handling, tilt/aspect, losses or performance ratio, temperature coefficient/reference temperature, clipping, and KNMI GHI versus plane-of-array treatment.

No numerical PV parameter is signed here. `PVSystemConfig.require_signed_parameters()` raises unless a config is marked `approved_for_executable_component_use` and carries a signed parameter decision ID.

## Boundaries

This work does not run or approve final paired HP/PV acceptance, cold-spell tolerances, net-load aggregation, event detection, `P(E)`, capacity screens, threshold analysis, or manuscript results.