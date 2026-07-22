## 2026-07-22 00:00 - E2.S4 - in-progress
DID: Confirmed `D004-MC-001` is approved in `registers/DECISIONS.md`, implemented the D-004 WEATHER-001 member builder in `data/get_weather_pv.py`, and generated metadata-only member records for 2014-2023 from the approved Alkmaar/Berkhout KNMI/PVGIS bundle.
VERIFIED: Focused PV/D-004 tests pass locally; generated member manifest records 10 UTC-year members, expected 15-minute row counts, shared weather-driver IDs, content hashes, source checksums, and PVGIS provenance-only status.
OPEN: D-004 final source acceptance, PVGIS seasonal/peak tolerances, HP/PV paired acceptance, cold-spell acceptance, net-load/event/P(E), capacity screens, and manuscript results remain blocked.
NEXT: Run full ownership and test suite, then open/update PR for PI review of the builder and metadata readiness only.
