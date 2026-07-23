# E2.S4 PV/Weather Paired-Readiness Preflight

Status: PI-facing readiness packet and fail-closed scaffold. D-004 source/member artifacts are accepted for internal source/member component-input use, but final paired HP/PV acceptance, PV parameter signoff, cold-spell tolerances, net-load integration, event detection, `P(E)`, capacity screens, threshold analysis, and manuscript results remain blocked.

## Why This Exists

After the IC-1 PV/weather bridge, the next reversible step is to make the remaining final-use blockers explicit in code and metadata. The project now has accepted D-004 WEATHER-001 source/member artifacts, but those artifacts do not sign PV conversion parameters or prove a real HP artifact has consumed the same weather member.

## Current Evidence That Can Be Carried Forward

The accepted D-004 source/member layer preserves:

- `D004-SOURCE-MEMBER-ACCEPTANCE` for internal first-screen source/member use;
- `WEATHER-001` member IDs, shared weather-driver IDs, content SHA-256 values, cadence, and UTC/local calendar metadata;
- KNMI station 249 Berkhout as the realized weather path under `D004-MC-001`;
- PVGIS-SARAH3 as qualitative seasonal/peak sanity and provenance/calibration context only.

This is enough for component-input metadata consumers to inspect PV/weather provenance. It is not enough for final paired HP/PV acceptance.

## Fail-Closed Scaffold

`src.pv_model.build_pv_paired_readiness_preflight_packet` returns a metadata-only preflight record. It allows the accepted source/member artifact to be inspected, but it reports blockers until all of the following are true:

- `PV-PARAM-001` has signed PV conversion parameters and `PVSystemConfig.require_signed_parameters()` passes;
- a real HP weather identity record matches the D-004 WEATHER-001 member exactly on `member_id`, `shared_weather_driver_id`, source, UTC span, timestep count, cadence, and content SHA-256;
- cold-spell numerical tolerances are signed under the approved E2.S3 cold-spell acceptance design.

Even if those prerequisites are present, the packet only says a final paired acceptance run is structurally ready. It does not sign final acceptance.

## PI Decisions Still Needed

1. Approve or amend `PV-PARAM-001`: installed capacity handling, tilt/aspect or plane-of-array treatment, performance ratio/losses, temperature coefficient/reference temperature, clipping, and KNMI GHI versus plane-of-array treatment.
2. Confirm the HP artifact identity record and WEATHER-001 member subset for the first paired HP/PV acceptance run.
3. Sign numerical cold-spell and near-freezing tolerances before inspecting real paired HP/PV diagnostics.

## Suggested STATUS Update

`E2.S4 PV model and weather inputs | C | in-progress | D-004 source/member artifacts accepted for component-input use; PV paired-readiness preflight scaffold and PI packet added; PV-PARAM-001, real HP/PV paired identity evidence, cold-spell tolerances, and final integrated gates remain blocked | PR: <this PR>`
