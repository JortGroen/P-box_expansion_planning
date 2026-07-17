# E2.S2 ElaadNL Set A shape report

## Scope

Single EV-004 Set A candidate probe only: home charge-point profiles with the native car/van mix, simulated_year 2030, batch seed 140201, n_profiles 100. Raw and processed generated profiles are ignored and not redistributed under EV-002.

## Request JSON

```json
{
  "cp_capacity_kw": 11,
  "location_type": "home",
  "n_profiles": 100,
  "profile_type": "cp",
  "seed": 140201,
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

- Annual energy kWh: min 1302.300, median 2079.100, mean 2028.943, p95 2351.095, max 2435.900
- Peak kW: min 11.000, median 11.000, mean 11.000, p95 11.000, max 11.000

## Seed semantics

Members are identified as `(batch seed, returned profile index)`. This report does not interpret a batch seed as a range of per-member seeds. Seed 140001 is reserved by EV-006 for a future same-seed smart-control counterpart, but no smart-control API call was made in this session. This uncontrolled-only probe leaves smart-batch member ordering unverified; actual pairing remains pending per section 7 of the Elaad profile generation spec.

## Source-level verdict

- API runtime seconds: 18.592
- API runtime note: Measured around the HTTPS POST only.
- Observed failed command wall time seconds: not recorded
- Supports proceeding to remaining candidate and held-out generation: True
- Library adequacy proven: False. Adequacy is an EV-005 downstream net-load/evaluator question, not a component-profile statistic.

## Evidence

- Manifest: `data/metadata/elaad_profiles/A_home_vancar_cp_y2030_batchseed140201_n100_manifest.json`
- Raw response checksum: `11abb8ee4d87b0168eb1b416750091a6989001d9ce16dd743ec902932b955c7c` (278788 bytes gzip)
- Processed local checksum: `9d0e1282810fd9c233d95cbe6e7c93db6f2a8c55d8524b2ed95d7b7e500dd8c3` (394077 bytes npz)
