# E2.S3 Heat-Pump Model Report

Status: implementation ready for review; no concrete external When2Heat file was downloaded in this PR.

## Scope Boundary

- Implemented only E2.S3 heat-pump data/model support.
- Did not implement PV, KNMI/PVGIS weather retrieval, net-load integration, congestion/event analysis, or EV adequacy.
- D-003 remains proposed. `data/get_when2heat.py --download ...` can retrieve a concrete OPSD file and write checksum metadata, but the DATA_REGISTER row is not updated here because no concrete file checksum is selected in this PR.

## Implementation

- `data/get_when2heat.py` now records OPSD When2Heat 2023-07-27 metadata by default and supports opt-in retrieval/checksum metadata for `datapackage`, `csv`, or `zip` files.
- `src/hp_model.py` loads selected When2Heat hourly heat-demand/COP components, converts normalized heat profiles from MW/TWh to thermal kW with an explicit annual TWh scale, divides each component by its matching COP, and aggregates electric kW.
- Hourly data are downscaled to 15 minutes by zero-order hold. Because values are average power, repeating each hourly value four times preserves energy exactly.
- The final heat-pump profile must align exactly to an externally supplied `WeatherMember` on a 15-minute UTC calendar. The model records `weather_member_id` and temperature but does not sample weather or shuffle timesteps.

## Cold-Week Sanity

`cold_week_sanity_check` identifies the coldest rolling seven-day temperature window and reports whether maximum HP electric demand falls inside it. The committed test uses a synthetic design-cold week and verifies the peak coincides with the cold spell. A real D-003/KNMI cold-week check remains pending concrete weather and When2Heat file selection.

## Verification

- Focused tests cover metadata-only and checksum retrieval paths without internet access, component-wise COP conversion, hourly-to-15-minute energy preservation, exact weather/calendar alignment, and the cold-week sanity diagnostic.
- `.\.venv\Scripts\python.exe -m pytest tests\test_hp_model.py tests\test_data_sources.py` passed 24 tests.
- `.\scripts\task.ps1 test` passed 138 tests after all E2.S3 edits.
- This report contains no manuscript result, no congestion probability, and no signed data-source claim.
