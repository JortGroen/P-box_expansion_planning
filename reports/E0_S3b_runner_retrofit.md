# E0.S3b ExperimentRunner Compliance Retrofit

Status: runner reproduction complete for review. This report marks the
standard `experiments/e1_*/manifest.json` files as the active claim-source
manifests while retaining the historical custom evidence for traceability.

Historical diagnostic thresholds are preserved as executed. In particular,
the E1.S3b import-window diagnostic remains labeled at its configured
`threshold_pu = 1.0`; it is not relabeled as the provisional G0-A3
`1.1 p.u.` working event.

## Migrated Diagnostics

| task_id | adapter | manifest | historical_threshold_pu | checksum_matches |
| --- | --- | --- | --- | --- |
| E1.S1 | e1.s1.grid_inventory.v1 | experiments/e1_s1_grid_inventory/manifest.json | not_applicable | 0/2 |
| E1.S2 | e1.s2.laptop_benchmark.v1 | experiments/e1_s2_laptop_benchmark/manifest.json | not_applicable | 0/3 |
| E1.S3 | e1.s3.critical_weeks.v1 | experiments/e1_s3_critical_weeks/manifest.json | not_applicable | 3/5 |
| E1.S3b | e1.s3b.import_window.v1 | experiments/e1_s3b_import_window/manifest.json | 1 | 4/6 |
| E1.S1b | e1.s1b.transformer_headroom.v1 | experiments/e1_s1b_transformer_headroom/manifest.json | not_applicable | 1/3 |
| E1.S2b | e1.s2b.timeseriescpp_benchmark.v1 | experiments/e1_s2b_timeseriescpp_benchmark/manifest.json | not_applicable | 0/3 |

## Discrepancy Summary

- E1.S1: fresh runner reproduction records a new config path, timestamp, commit, and output paths; runner-normalized report path/content differs from the historical narrative report; numeric inventory rows are reproduced in grid_inventory_rows.json
- E1.S2: fresh runner reproduction records a new config path, timestamp, commit, and output paths; fresh wall-clock benchmark rerun has new timestamps and timing measurements; runner report is normalized and timing values are a fresh rerun
- E1.S3: fresh runner reproduction records a new config path, timestamp, commit, and output paths; runner output paths and manifest references differ from the retained historical report
- E1.S3b: fresh runner reproduction records a new config path, timestamp, commit, and output paths while preserving threshold_pu=1.0; runner output paths and manifest references differ from the retained historical report
- E1.S1b: fresh runner reproduction records a new config path, timestamp, commit, and output paths; runner output paths and manifest references differ from the retained historical report
- E1.S2b: fresh runner reproduction records a new config path, timestamp, commit, hardware context, and output paths; fresh wall-clock benchmark rerun has new timestamps, hardware/runtime context, and timing measurements; runner output paths and timing values differ from the retained historical report

## Boundaries

- Q-5 remains open before integrated event-based scientific analysis or
  manuscript event results.
- No G0, G0-A3, G1, G2, IC schema, epsilon, or capacity-denominator decision
  is changed by this retrofit.
- Timing diagnostics are fresh wall-clock reproductions, so their numeric
  timing files are expected to differ from retained historical evidence.
