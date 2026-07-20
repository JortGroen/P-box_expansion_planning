# E2.S4 PV Model and Weather Inputs

## Scope

Implemented D-004 support for PVGIS/KNMI weather and PV inputs only. This work
does not implement heat-pump demand logic, net-load integration,
congestion/event results, or EV held-out adequacy.

## Implemented

- Added `src/pv_model.py` with a `WeatherMember` representation that carries
  paired temperature and irradiance channels, UTC/local timestamps, and a stable
  shared weather-driver identity for later HP/PV pairing under ALEA-001.
- Added canonical 15-minute Europe/Amsterdam local-year calendar utilities and
  validation for complete chronological weather paths.
- Added deterministic PV generation from explicit `PVSystemConfig` values, with
  seasonal energy summaries, peak timing, and PVGIS-reference sanity checks.
- Extended `data/get_weather_pv.py` with PVGIS/KNMI endpoint builders, SHA-256
  checksum recording for concrete local files, an explicit download helper, and
  a metadata-only retrieval plan.
- Wrote metadata-only D-004 provenance files:
  - `data/metadata/d-004_weather_pv.json`
  - `data/metadata/weather_pv/d004_weather_pv_retrieval_plan.json`

## Data Boundary

No PVGIS or KNMI raw files were downloaded in this task. No concrete file,
station, weather-year bundle, PVGIS request, or checksum selection was made, so
`registers/DATA_REGISTER.md` remains unchanged for D-004. The retrieval plan
records the current official endpoint structure and the checksum policy for
future concrete files, but it is not a PI-signed data selection.

PVGIS typical-year output remains limited to calibration or validation. It is
not represented as an independently sampled realized weather path. Realized
weather members must remain complete, chronological, and paired across
temperature and irradiance channels before downstream integration.

## Verification

Focused tests added in `tests/test_pv_model.py` cover:

- canonical 15-minute local-year calendars, including DST behavior;
- rejection of non-chronological, naive, or invalid weather paths;
- PV generation from explicit weather/config inputs;
- seasonal totals and peak-timing checks against PVGIS-style references;
- PVGIS/KNMI URL builders, retrieval-plan metadata, and local checksum records.

The focused test file passed during implementation. The final repository
ownership and full test gates are recorded in `reports/AGENT_C_LOG.md`.
