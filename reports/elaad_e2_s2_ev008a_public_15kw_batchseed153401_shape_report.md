# E2.S2 ElaadNL EV-008A Set B shape report

## Scope

EV-008A Set B `held_out` batch: public 15 kW charge-point profiles with the native car/van mix, simulated_year 2030, batch seed 153401, n_profiles 100. Raw and processed generated profiles are ignored and not redistributed under EV-002.

## Request JSON

```json
{
  "cp_capacity_kw": 15,
  "location_type": "public",
  "n_profiles": 100,
  "profile_type": "cp",
  "seed": 153401,
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

## Structural-only summary

Behavioral annual-energy, peak, and percentile summaries are intentionally omitted for public Set B source-generation artifacts. EV-008A authorizes structural validation only; adequacy remains downstream under E3.S2a.

## Seed semantics

Members are identified as `(batch seed, returned profile index)`. This report does not interpret a batch seed as a range of per-member seeds. no smart-control API call was made in this session. Smart-batch member ordering remains unverified unless a later signed smart-control counterfactual explicitly authorizes paired same-seed generation.

## Source-level verdict

- API runtime seconds: 60.970
- API runtime note: Measured around the HTTPS POST only.
- Observed failed command wall time seconds: not recorded
- Supports proceeding to remaining candidate and held-out generation: True
- Library adequacy proven: False. Adequacy is an EV-005 downstream net-load/evaluator question, not a component-profile statistic.

## Evidence

- Manifest: `data/metadata/elaad_profiles/B_public_15kw_vancar_cp_y2030_batchseed153401_n100_manifest.json`
- Raw response checksum: `00aec7f2e119e9287ce6ce343a1074d36ea560d3d029fb77e2e37bffad6fb9f4` (923577 bytes gzip)
- Processed local checksum: `f0638c7188c3c0b7d7ac7b174ff5e1483c92a461dc574163c7780d1b498829bd` (907190 bytes npz)
