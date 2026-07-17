# E2.S2 ElaadNL Set A shape report

## Scope

Single EV-004 Set A candidate probe only: home charge-point profiles with the native car/van mix, simulated_year 2030, batch seed 140001, n_profiles 100. Raw and processed generated profiles are ignored and not redistributed under EV-002.

## Request JSON

```json
{
  "cp_capacity_kw": 11,
  "location_type": "home",
  "n_profiles": 100,
  "profile_type": "cp",
  "seed": 140001,
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

- Annual energy kWh: min 1443.600, median 2011.175, mean 2027.593, p95 2495.992, max 2691.699
- Peak kW: min 11.000, median 11.000, mean 11.000, p95 11.000, max 11.000

## Seed semantics

Members are identified as `(batch seed, returned profile index)`. This report does not interpret a batch seed as a range of per-member seeds. Seed 140001 is reserved by EV-006 for a future same-seed smart-control counterpart, but no smart-control API call was made in this session. This uncontrolled-only probe leaves smart-batch member ordering unverified; actual pairing remains pending per section 7 of the Elaad profile generation spec.

## Source-level verdict

- API runtime seconds: not recorded
- API runtime note: Exact HTTPS runtime was not captured because the first authorized call hit a post-response manifest bug; no second API call was made.
- Observed failed command wall time seconds: 25.834
- Supports proceeding to remaining candidate and held-out generation: True
- Library adequacy proven: False. Adequacy is an EV-005 downstream net-load/evaluator question, not a component-profile statistic.

## Evidence

- Manifest: `data/metadata/elaad_profiles/A_home_vancar_cp_y2030_batchseed140001_n100_manifest.json`
- Raw response checksum: `7ea96ed8a113fd417957107926f4548b9f937dc1bd84703faefc0281e212d3df` (279552 bytes gzip)
- Raw response provenance:
  - initial_saved_wrapper_sha256_gzip_file: `723f72260517455d7981ef814012affb80c72a8b4935e11d661e77f4c6219924`
  - recovery_rewritten_wrapper_sha256_gzip_file: `7ea96ed8a113fd417957107926f4548b9f937dc1bd84703faefc0281e212d3df`
  - sha256_uncompressed_json: `d8dc58745311a772c171f3dee129d98b9c553833119f36e0d3a580dcb2cb7804`
  - note: The initial saved gzip wrapper came from the single authorized API retrieval at `2026-07-17T09:52:03.233106Z`. A later local recovery bug rewrote the ignored gzip wrapper without changing the uncompressed JSON; the rewritten wrapper is the current local raw file, is recorded for audit, and is not a new retrieval.
- Processed local checksum: `e550931ead774e7a9c42a4ff06f221eb1d2c3337bc4f43e57e0ff00bd63a0f2c` (394116 bytes npz)
