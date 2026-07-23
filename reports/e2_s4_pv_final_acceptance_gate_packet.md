# E2.S4 PV Final-Acceptance Gate Packet

Status: fail-closed scaffold and PI-facing decision packet. D-004 source/member artifacts remain accepted only for source/member component-input use. This packet does not sign final paired HP/PV acceptance, PV parameters, cold-spell tolerances, net-load integration, event detection, `P(E)`, threshold analysis, capacity screens, or manuscript results.

## Why This Exists

PR #179 made the broad PV/weather preflight explicit. This follow-up makes the next gate sharper: a future first real paired HP/PV acceptance run should not be considered structurally ready unless the member subset, PV parameter signoff, HP weather identity records, and cold-spell tolerance metadata are all explicit.

## Gate Scaffold

`src.pv_model.build_pv_final_acceptance_gate_packet` records three fail-closed checks:

- PV parameters: `PVSystemConfig.require_signed_parameters()` must pass and the signed decision ID must be `PV-PARAM-001`.
- HP/PV identity: each requested `member_id` must have an HP weather identity record matching the accepted D-004 WEATHER-001 member on member ID, shared weather-driver ID, source, UTC span, timestep count, cadence, and content SHA-256.
- Cold-spell metadata: a vague signed status is insufficient. The packet requires named tolerance fields including near-freezing band limits, coldest-window tolerances, response metrics, and a pre-inspection signed flag.

Even when all three checks pass in a future run, the helper only reports `ready_for_first_real_paired_acceptance_run = true`. It always keeps `final_paired_hp_pv_acceptance_signed_by_this_packet = false`.

## Current PI Decisions Still Needed

1. Approve or amend `PV-PARAM-001`.
2. Identify the WEATHER-001 member subset and real HP artifact identity records for the first paired HP/PV acceptance run.
3. Sign exact cold-spell and near-freezing tolerance metadata before inspecting the first real diagnostics.

## Suggested STATUS Update

`E2.S4 PV model and weather inputs | C | in-progress | PV final-acceptance gate scaffold added; D-004 source/member component-input readiness preserved; PV-PARAM-001, real HP/PV identity evidence, cold-spell tolerances, and final integrated gates remain blocked | PR: <this PR>`
