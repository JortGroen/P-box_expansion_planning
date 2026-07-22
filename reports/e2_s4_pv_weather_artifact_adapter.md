# E2.S4 PV WEATHER-001 Artifact Adapter

Status: PV/weather component-readiness adapter implemented; final paired HP/PV and cold-spell acceptance remain pending.

This PR adds a PV-side adapter for the accepted D-004 WEATHER-001 input artifact. The adapter loads the committed member index, validates that it is accepted for source/member executable-input use, keeps `D004-SOURCE-MEMBER-ACCEPTANCE` visible, and requires the final paired HP/PV, cold-spell, and integrated-analysis gates to remain blocked.

The adapter preserves member IDs, shared weather-driver IDs, source, UTC span, local span where supplied, timestep count, 900-second cadence, content SHA-256, calendar ID, and PVGIS/KNMI provenance. KNMI remains the realized 2014-2023 WEATHER-001 weather path. PVGIS remains qualitative seasonal/peak sanity and provenance/calibration context only, with `pvgis_realized_weather_path=false`.

PV generation through the adapter first checks the supplied WEATHER-001 member identity against the accepted artifact record. The generated PV profile then carries the source/member acceptance ID, artifact status, calendar ID, PVGIS boundary, shared weather-driver ID, and weather content hash in its identity record for downstream pairing checks.

No final paired HP/PV validation, HP cold-spell tolerance, net-load/event/`P(E)`, capacity-screen, threshold-analysis, or manuscript-result work was run.