# E2.S4 PV/Weather IC-1 Input Artifact Readiness

## Purpose

This note records the next D-004/PV-weather readiness step after the accepted WEATHER-001 source/member artifact. The change prepares a metadata-only path that lets IC-1 consume the PV/weather component artifact while preserving the accepted D-004 WEATHER-001 identity evidence.

## Implemented Artifact Path

`src.pv_model.build_pv_ic1_executable_input_artifact` converts a loaded `PVWeatherInputArtifact` member into an IC-1 `ExecutableInputArtifact` with:

- `kind = "pv"` and `artifact_status = "accepted"` for D-004 source/member use only;
- signed source/member identifiers `WEATHER-001`, `D004-MC-001`, and `D004-SOURCE-MEMBER-ACCEPTANCE`;
- D-004 member ID, shared weather-driver ID, cadence, source calendar ID, timestep count, and content SHA-256 in IC-1-visible metadata;
- manifest/provenance evidence for the accepted KNMI realized weather path and PVGIS qualitative/provenance-only boundary;
- caller-supplied PV node IDs, because this helper does not perform nodal allocation or net-load assembly.

If a caller supplies an IC-1 planning calendar ID that differs from the D-004 source calendar, the source calendar remains recorded and the override is marked as caller-supplied. This avoids treating historical-to-planning calendar mapping as silently signed by this helper.

## Guardrails

The adapter is metadata-only. It does not load PV trajectories, alter weather arrays, map historical members onto a planning year, run paired HP/PV validation, set cold-spell tolerances, assemble net load, detect events, compute P(E), run capacity screens, or create manuscript results.

The IC-1 artifact provenance keeps the deferred gates visible:

- `final_paired_hp_pv_acceptance`;
- `cold_spell_acceptance`;
- `integrated_analysis`.

## Validation

Focused tests cover:

- IC-1 gate acceptance for the PV component artifact with the D-004 source/member approval IDs;
- preservation of member ID, shared weather-driver ID, calendar ID, cadence, manifest path, and content SHA-256;
- PVGIS recorded as non-realized weather provenance;
- explicit provenance when an IC-1 calendar override is supplied.

Command run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_pv_model.py
```

Result: 42 passed.

