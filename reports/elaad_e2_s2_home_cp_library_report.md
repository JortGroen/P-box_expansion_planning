# E2.S2 ElaadNL Set A home charge-point library report

## Scope

Frozen EV-004 uncontrolled home charge-point library for the native van/car mix, 11 kW charge points, simulated_year 2030. Raw API responses and processed annual members stay in ignored data paths and are not redistributed. This report records source integrity only; it does not declare M=1000 sufficient.

## Generated batches

- Candidate seeds: 140001-140901 step 100 (10 batches, 1000 members)
- Quarantined diagnostic seeds: 141001, 141101 (2 batches, 200 members)
- Held-out seeds: 141201, 141301 (2 batches, 200 members)
- Public Set B generated: False
- Smart Set D generated: False

## Checkpoint and recovery

Re-run data/get_elaad_profiles.py --run-set-a-home-profile-library; verified checkpoints are skipped, saved raw gzip files are recovered without rewriting, and mismatched checksums stop the run. Retries reuse the identical request_json for a batch seed and cannot register a duplicate batch.

## Verification

- Command wall time seconds: 0.059
- Summed recorded API runtime seconds: 239.673
- API runtime note: Sum excludes any batch whose HTTPS runtime was not recorded, including recovered seed 140001.
- Every listed batch has 35,040 timesteps: True
- Every listed batch has 100 profiles: True
- Every listed batch has 100 distinct members: True
- Smart pair order verified: False
- Missing/nonfinite and negative-value checks are recorded in the per-batch manifests.

## Held-out isolation

Seeds 141001 and 141101 are retained as quarantined precriterion diagnostics and may not certify held-out adequacy. Fresh held-out batches 141201 and 141301 were generated, source-validated, checksummed, and archived only. They were not opened for adequacy analysis, and E3.S2a must freeze the criterion before any held-out use. The low-cost replacement does not create a blanket requirement to redo materially expensive work without PI consultation.

## Evidence

- Library manifest: `data/metadata/elaad_profiles/A_home_vancar_cp_y2030_set_a_library_manifest.json`
- Per-batch raw and processed checksums are listed in the manifest.
