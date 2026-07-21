# E2.S2 ElaadNL EV-008A Set B shape report

## Scope

EV-008A Set B `candidate` batch: public 11 kW charge-point profiles with the native car/van mix, simulated_year 2030, batch seed 152201, n_profiles 100. Raw and processed generated profiles are ignored and not redistributed under EV-002.

## Request JSON

```json
{
  "cp_capacity_kw": 11,
  "location_type": "public",
  "n_profiles": 100,
  "profile_type": "cp",
  "seed": 152201,
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

- API runtime seconds: not recorded
- API runtime note: Exact HTTPS runtime was not captured because the first authorized call hit a post-response manifest bug; no second API call was made.
- Observed failed command wall time seconds: not recorded
- Supports proceeding to remaining candidate and held-out generation: True
- Library adequacy proven: False. Adequacy is an EV-005 downstream net-load/evaluator question, not a component-profile statistic.

## Evidence

- Manifest: `data/metadata/elaad_profiles/B_public_11kw_vancar_cp_y2030_batchseed152201_n100_manifest.json`
- Raw response checksum: `2cc47786fba0c844c8ef7e6f7a0283e287ebbbdbbeb8783be67fb7f2800a1966` (439835 bytes gzip)
- Processed local checksum: `d6af85428f4e34b8a7b1a87a5f661317e3ee61d370a57e91450a28fdfd48ea22` (590418 bytes npz)
