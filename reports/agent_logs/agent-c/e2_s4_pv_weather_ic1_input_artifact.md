# Agent C Log: E2.S4 PV/Weather IC-1 Input Artifact

## Scope

Prepared the PV/weather executable-input artifact path for IC-1 consumption using the accepted D-004 WEATHER-001 source/member artifact. Scope stayed within PV/weather readiness and did not touch final paired HP/PV validation, cold-spell tolerance decisions, net-load/event analysis, P(E), capacity screens, or manuscript results.

## Changes

- Added a PV/weather-to-IC-1 metadata adapter in `src/pv_model.py`.
- Extended `PVWeatherInputArtifact` to carry audited evidence artifact paths from the existing metadata JSON.
- Preserved D-004 source/member approval ID, WEATHER-001/D004-MC-001 register IDs, member ID, shared weather-driver ID, cadence, source calendar ID, timestep count, content SHA-256, KNMI realized-weather provenance, and PVGIS qualitative/provenance-only boundary in the emitted IC-1 artifact.
- Added tests in `tests/test_pv_model.py` for IC-1 gate compatibility and explicit calendar-override provenance.

## Validation

Focused PV tests passed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_pv_model.py
```

Full ownership and test gates are run before PR publication.

## Suggested STATUS Update

E2.S4 PV model | C | review-limited | 2/3 | PV/weather artifact can emit IC-1 executable-input metadata while preserving D-004 WEATHER-001 identity/provenance; final paired HP/PV and cold-spell acceptance remain blocked | PR: pending

