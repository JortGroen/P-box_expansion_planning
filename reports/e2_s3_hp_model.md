# E2.S3 Heat-Pump Model Report

Status: HP-001 implementation scaffold. D-003 When2Heat `2023-07-27`
`when2heat.csv` is approved for internal Dutch residential shape/COP source use
under HP-001, and the HP loader can parse the real CSV dialect. Local annual HP
scaling, Q-8/D-004 paired-weather acceptance, cold-spell tolerances, and final
integrated HP acceptance remain unresolved.

## Scope Boundary

- Implemented only E2.S3 heat-pump data/model support.
- Did not implement PV, KNMI/PVGIS weather retrieval, net-load integration, congestion/event analysis, or EV adequacy.
- D-003 is approved only for HP-001 internal residential shape/COP source use.
  OPSD package `2023-07-27`, file `when2heat.csv`, is recorded with concrete
  checksum metadata in
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- HP-001 includes SFH/MFH residential space heat plus domestic hot water.
  Commercial `COM` heat remains outside the primary run and may enter only
  through a later signed sensitivity.
- Coordinated against the C.PV/weather branch `agent-c/E2.S4-pv-weather-inputs`
  at `74e686b`, which defines a paired weather member with temperature,
  irradiance, UTC/local timestamps, source, metadata, and
  `shared_weather_driver_id`.

## Implementation

- `data/get_when2heat.py` now records OPSD When2Heat 2023-07-27 metadata by default, writes a no-download D-003 source-selection plan, and supports opt-in retrieval/checksum metadata for `datapackage`, `csv`, or `zip` files.
- `src/hp_model.py` loads selected When2Heat hourly heat-demand/COP components from the real OPSD single-index CSV dialect (`;` delimiter, comma decimals), converts normalized heat profiles from MW/TWh to thermal kW with an explicit annual TWh scale, divides each component by its matching COP, and aggregates electric kW.
- `hp001_residential_when2heat_components` represents the approved HP-001
  residential boundary directly: `NL_heat_profile_space_SFH` and
  `NL_heat_profile_space_MFH` with `NL_COP_ASHP_radiator`, plus
  `NL_heat_profile_water_SFH` and `NL_heat_profile_water_MFH` with
  `NL_COP_ASHP_water`. The helper requires caller-supplied annual TWh values
  for both SFH and MFH in both end uses; those values are not invented or
  approved by the helper.
- Each `When2HeatComponent` now records its shape column, COP column, end use,
  building class, annual TWh input, and provenance so components remain
  separately auditable before aggregation.
- The loader records source metadata for the CSV dialect, timestamp columns,
  selected heat/COP columns, units, row count loaded, and first/last UTC/local
  timestamp values so later HP/PV audit has the D-003 source context.
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

`cold_week_sanity_check` identifies the coldest rolling seven-day temperature window and reports whether maximum HP electric demand falls inside it. The committed test uses a synthetic design-cold week and verifies the peak coincides with the cold spell. This is scaffold evidence only; a real D-003/shared-weather paired cold-week check remains pending Q-8/shared weather contract resolution and PI-reviewed source assumptions.

## Verification

- Focused tests cover metadata-only and checksum retrieval paths without internet access, real When2Heat CSV dialect parsing via small fixtures, optional three-row local raw-file sampling when the ignored D-003 CSV is present, HP-001 SFH/MFH space and domestic-hot-water component construction, component-wise COP conversion, per-component traceability before aggregation, hourly-to-15-minute energy preservation, exact shared-weather/calendar alignment, preservation of audit identity fields including PV weather field names, rejection of temperature-only weather objects, and the cold-week sanity diagnostic.
- Final `.\scripts\task.ps1 ownership` and `.\scripts\task.ps1 test` results are recorded in the PR validation section for this follow-up branch.
- This report contains no manuscript result, no congestion probability, and no signed data-source claim.
