# E2.S4 D-004 Source/Member Acceptance Decision

Status: PI-approved for internal first-screen source/member use; final paired/cold-spell acceptance pending.

The PI approved the D-004 recommendation as proposed on 2026-07-22. The approved scope accepts the KNMI/PVGIS source/member bundle `d004_alkmaar_berkhout_2014_2023_v1` for internal first-screen use. KNMI station 249 Berkhout remains the realized 2014-2023 WEATHER-001 weather path. PVGIS-SARAH3 remains qualitative seasonal/peak sanity and provenance/calibration context only, not a realized sampled weather member.

Paired HP/PV use requires exact WEATHER-001 identity/calendar equality before diagnostics are judged: `member_id`, `shared_weather_driver_id`, `source`, UTC span, timestep count, cadence, and `content_sha256` must match. Numerical cold-spell tolerances remain deferred to the HP/cold-spell acceptance decision.

This decision does not run final paired HP/PV validation, sign cold-spell tolerances, run net-load/event/`P(E)`, produce capacity screens, or create manuscript numbers.
