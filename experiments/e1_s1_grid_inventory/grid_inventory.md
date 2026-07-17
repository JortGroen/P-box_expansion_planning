# E1.S1 Grid Inventory Runner Reproduction

Status: ExperimentRunner reproduction of the accepted E1.S1 inventory.

This artifact preserves the grid-inventory diagnostic as a runner-managed
claim source. It does not run overload-event analysis and has no p.u.
threshold to relabel under G0-A3.

## Evidence

- Runner config: `experiments/e1_s1_grid_inventory/runner_config.json`
- Historical input: `reports/grid_inventory_input.json`
- Command: `.\.venv\Scripts\python.exe -m src.runner experiments/e1_s1_grid_inventory/runner_config.json`

| key | role | code | buses | lines | trafos | loads | static_generators | total_load_mw | total_sgen_mw | line_length_km | trafo_s_rated_mva | baseline_converged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| simbench_semiurb | primary candidate | 1-MV-semiurb--0-sw | 117 | 121 | 2 | 115 | 121 | 31.64 | 23.799 | 67.28 | 80 | True |
| simbench_urban | secondary SimBench candidate | 1-MV-urban--0-sw | 144 | 147 | 2 | 139 | 134 | 49.707 | 13.557 | 37.82 | 126 | True |
| cigre_mv | cross-check candidate | create_cigre_network_mv | 15 | 15 | 2 | 18 | 9 | 44.7421 | 1.71 | 24.95 | 50 | True |
