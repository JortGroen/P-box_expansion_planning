# E2.S2 ElaadNL Set A shape report

## Scope

EV-004 Set A `candidate` batch: home charge-point profiles with the native car/van mix, simulated_year 2030, batch seed 140901, n_profiles 100. Raw and processed generated profiles are ignored and not redistributed under EV-002.

## Request JSON

```json
{
  "cp_capacity_kw": 11,
  "location_type": "home",
  "n_profiles": 100,
  "profile_type": "cp",
  "seed": 140901,
  "simulated_year": 2030,
  "start_datetime": "2025-01-01T00:00:00+01:00",
  "step_size_s": 900,
  "stop_datetime": "2026-01-01T00:00:00+01:00",
  "timezone": "CET",
  "vehicle_types": [
    "van",
    "car"
  ]
}
```

## Shape and timezone

- Timesteps: 35040
- Profiles: 100
- Distinct returned members: 100
- Returned indices available for planned pairing: True
- Smart pair order verified: False
- First UTC timestamp: `2024-12-31T23:00:00+00:00`
- First local timestamp: `2025-01-01T00:00:00+01:00`
- Last local timestamp: `2025-12-31T23:45:00+01:00`
- Missing/nonfinite values: 0
- Negative values: 0

## Summary statistics

- Annual energy kWh: min 1201.400, median 2022.975, mean 2035.050, p95 2515.267, max 2790.399
- Peak kW: min 11.000, median 11.000, mean 11.000, p95 11.000, max 11.000

## Seed semantics

Members are identified as `(batch seed, returned profile index)`. This report does not interpret a batch seed as a range of per-member seeds. Seed 140001 is reserved by EV-006 for a future same-seed smart-control counterpart, but no smart-control API call was made in this session. This uncontrolled-only probe leaves smart-batch member ordering unverified; actual pairing remains pending per section 7 of the Elaad profile generation spec.

## Source-level verdict

- API runtime seconds: 17.523
- API runtime note: Measured around the HTTPS POST only.
- Observed failed command wall time seconds: not recorded
- Supports proceeding to remaining candidate and held-out generation: True
- Library adequacy proven: False. Adequacy is an EV-005 downstream net-load/evaluator question, not a component-profile statistic.

## Evidence

- Manifest: `data/metadata/elaad_profiles/A_home_vancar_cp_y2030_batchseed140901_n100_manifest.json`
- Raw response checksum: `e2b6153301528ee705b94baca10d3fce8e7d872b0326bbf1203ad736deffb955` (279033 bytes gzip)
- Processed local checksum: `f355f90d31628af38850069ffec4413513f949d0b30c363e3204e14a7d99a231` (394145 bytes npz)
