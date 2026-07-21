# E2.S3 Heat-Pump Model Report

Status: scaffold/review-limited. No concrete external When2Heat file was
downloaded in this PR, and no real paired-weather cold-spell acceptance
evidence exists yet.

## Scope Boundary

- Implemented only E2.S3 heat-pump data/model support.
- Did not implement PV, KNMI/PVGIS weather retrieval, net-load integration, congestion/event analysis, or EV adequacy.
- D-003 remains proposed. `data/get_when2heat.py --download ...` can retrieve a concrete OPSD file and write checksum metadata, but the DATA_REGISTER row is not updated here because no concrete file checksum is selected in this PR.
- Coordinated against the C.PV/weather branch `agent-c/E2.S4-pv-weather-inputs`
  at `74e686b`, which defines a paired weather member with temperature,
  irradiance, UTC/local timestamps, source, metadata, and
  `shared_weather_driver_id`.

## Implementation

- `data/get_when2heat.py` now records OPSD When2Heat 2023-07-27 metadata by default and supports opt-in retrieval/checksum metadata for `datapackage`, `csv`, or `zip` files.
- `src/hp_model.py` loads selected When2Heat hourly heat-demand/COP components, converts normalized heat profiles from MW/TWh to thermal kW with an explicit annual TWh scale, divides each component by its matching COP, and aggregates electric kW.
- Hourly data are downscaled to 15 minutes by zero-order hold. Because values are average power, repeating each hourly value four times preserves energy exactly.
- The final heat-pump profile must align exactly to the externally supplied
  shared weather/PV member on a 15-minute UTC calendar. The model requires and
  preserves `shared_weather_driver_id`, `member_id`, source, UTC timestamps,
  optional local timestamps, and metadata/provenance. It also requires at least
  one aligned PV/irradiance weather field on the supplied member and records the
  PV weather field names in `HeatPumpProfile.weather_identity_record()` for
  direct HP/PV audit.
- The neutral shared weather contract module is still not imported here because
  PR #43 does not yet provide `src/weather_model.py`; C.PV/weather should own
  that implementation once the shared-weather path ownership blocker is
  resolved.

## Cold-Week Sanity

`cold_week_sanity_check` identifies the coldest rolling seven-day temperature window and reports whether maximum HP electric demand falls inside it. The committed test uses a synthetic design-cold week and verifies the peak coincides with the cold spell. This is scaffold evidence only; a real D-003/KNMI paired-weather cold-week check remains pending concrete weather and When2Heat file selection.

## Verification

- Focused tests cover metadata-only and checksum retrieval paths without internet access, component-wise COP conversion, hourly-to-15-minute energy preservation, exact shared-weather/calendar alignment, preservation of audit identity fields including PV weather field names, rejection of temperature-only weather objects, and the cold-week sanity diagnostic.
- `.\.venv\Scripts\python.exe -m pytest tests\test_hp_model.py tests\test_methods_registry.py` passed 13 tests after the shared-weather compatibility revision.
- Final `.\scripts\task.ps1 ownership` and `.\scripts\task.ps1 test` results are recorded in the PR #44 validation section.
- This report contains no manuscript result, no congestion probability, and no signed data-source claim.
