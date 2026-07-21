# E2.S2 ElaadNL Set B public equal-mix library report

## Scope

EV-008A source generation only: uncontrolled public ElaadNL `cp` profiles with the native van/car mix, simulated_year 2030, and four AC capacity classes at equal 25% physical mix. Raw API responses and processed annual members stay in ignored data paths and are not redistributed. This report records structural validation only; it does not inspect held-out adequacy, run integrated analysis, or declare the candidate M sufficient.

## Generated batches

| Capacity class | kW | Candidate seeds | Candidate members | Held-out seeds | Held-out members |
|---|---:|---|---:|---|---:|
| `public_11kw` | 11 | 152001, 152101, 152201 | 300 | 153201 | 100 |
| `public_13kw` | 13 | 152301, 152401, 152501 | 300 | 153301 | 100 |
| `public_15kw` | 15 | 152601, 152701, 152801 | 300 | 153401 | 100 |
| `public_22kw` | 22 | 152901, 153001, 153101 | 300 | 153501 | 100 |

- Candidate members: 1200
- Held-out members: 400
- Public smart charging generated: False
- DC/fast charging generated: False
- Integrated analysis performed: False
- M sufficiency claimed: False

## Checkpoint and recovery

Re-run data/get_elaad_profiles.py --run-public-set-b-equal-mix-library; verified checkpoints are skipped, saved raw gzip files are recovered without rewriting, and mismatched request/config/checksums stop the run. Retries reuse the identical request_json for a batch seed and cannot register a duplicate batch.

## Structural verification

- Command wall time seconds for latest manifest-writing command: 0.000
- Summed recorded API runtime seconds: 243.529
- Every listed batch has 35,040 timesteps: True
- Every listed batch has 100 profiles: True
- Every listed batch has 100 distinct members: True
- Every listed batch has zero missing/nonfinite values: True
- Every listed batch has zero negative values: True
- Smart pair order verified: False

## Held-out isolation

Held-out public batches are generated and source-validated only. They remain blocked for adequacy or tail analysis until E3.S2a freezes a downstream criterion. No behavioral annual-energy, peak, percentile, congestion, event, or P(E) conclusion is drawn from held-out data in this packet.

## Evidence

- Library manifest: `data/metadata/elaad_profiles/B_public_vancar_cp_y2030_set_b_library_manifest.json`
- Per-batch raw and processed checksums are listed in the manifest.
