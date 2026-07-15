# E2.S2 ElaadNL Set A shape report

## Scope

Single PI-authorized Set A request only: home passenger-car EV profiles, simulated_year 2030, seed 130001, n_profiles 100. Raw and processed generated profiles are ignored and not redistributed under EV-002.

## Request JSON

```json
{
  "cp_capacity_kw": 11,
  "location_type": "home",
  "n_profiles": 100,
  "profile_type": "ev",
  "seed": 130001,
  "simulated_year": 2030,
  "start_datetime": "2025-01-01T00:00:00+01:00",
  "step_size_s": 900,
  "stop_datetime": "2026-01-01T00:00:00+01:00",
  "timezone": "CET",
  "vehicle_types": "car"
}
```

## Shape and timezone

- Timesteps: 35040
- Profiles: 100
- Distinct returned members: 100
- First UTC timestamp: `2024-12-31T23:00:00+00:00`
- First local timestamp: `2025-01-01T00:00:00+01:00`
- Last local timestamp: `2025-12-31T23:45:00+01:00`
- Missing/nonfinite values: 0
- Negative values: 0

## Summary statistics

- Annual energy kWh: min 87.850, median 730.875, mean 610.599, p95 893.230, max 983.000
- Peak kW: min 11.000, median 11.000, mean 11.000, p95 11.000, max 11.000

## Seed semantics

Members are identified as `(batch seed, returned profile index)`. This report does not claim that seed 130001 expands into independent seeds 130001-130100.

## Evidence

- Manifest: `data/metadata/elaad_profiles/A_home_car_ev_y2030_seed130001-130100_manifest.json`
- Raw response checksum: `ff6c5be5e8ca220987a62ce0c83eee264c8c9be1950ee8e575fedeb16dc6828d`
- Processed local checksum: `c6f5eaec5ecf435075a079efb2d8694e73adea176499dfd8372230e7896cd22a`
