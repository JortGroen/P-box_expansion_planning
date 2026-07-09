# E1.S1 Grid Inventory

Status: complete for E1.S1 review.

## Scope

E1.S1 covers only:

- load SimBench `1-MV-semiurb--0-sw`
- load SimBench `1-MV-urban--0-sw`
- load CIGRE MV via pandapower
- produce an inventory of buses, transformers, lines, ratings, loads, generation
- run a deterministic pandapower baseline and record convergence

No E1.S2 benchmark, E1.S3 time-series extraction, or overload-event work was run.

## Candidate Grids

| key | source | code | intended role |
| --- | --- | --- | --- |
| `simbench_semiurb` | SimBench | `1-MV-semiurb--0-sw` | primary candidate |
| `simbench_urban` | SimBench | `1-MV-urban--0-sw` | secondary SimBench candidate |
| `cigre_mv` | pandapower networks | `create_cigre_network_mv` | cross-check candidate |

## Implementation Prepared

`src/grid_loader.py` now contains:

- `CandidateGridSpec` metadata for the three E1.S1 candidates
- lazy `load_candidate_grid()` dispatch for SimBench and CIGRE MV
- `run_deterministic_power_flow()` for the deterministic pandapower baseline
- `summarize_grid()` and `inventory_markdown()` helpers for the G0 inventory table

Focused tests in `tests/test_grid_loader.py` verify candidate metadata, unknown-key
handling, inventory summarization, and Markdown rendering without importing the
blocked grid stack.

## Environment Evidence

The original live grid-stack import blocker was resolved by `DEP-001` in
`registers/DECISIONS.md`: the project now uses the per-worktree `.venv` with
`simbench==1.6.2` and `pandapower>=3.4,<4`.

```text
pandapower 3.5.3
simbench 1.6.2
lightsim2grid 0.13.1
```

`src.grid_loader.inventory_rows()` loaded all three candidate grids and ran the
deterministic pandapower baseline power flow for each one.

Run input and evidence:

- `reports/grid_inventory_input.json` records the candidate grid codes and command.
- `reports/grid_inventory_evidence.json` records the git commit, timestamp,
  package versions, candidate grid codes, command, and checksum for this report.

## Inventory Table

| key | role | code | buses | lines | trafos | loads | static_generators | total_load_mw | total_sgen_mw | line_length_km | trafo_s_rated_mva | baseline_converged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `simbench_semiurb` | primary candidate | `1-MV-semiurb--0-sw` | 117 | 121 | 2 | 115 | 121 | 31.64 | 23.799 | 67.28 | 80.0 | true |
| `simbench_urban` | secondary SimBench candidate | `1-MV-urban--0-sw` | 144 | 147 | 2 | 139 | 134 | 49.707 | 13.557 | 37.82 | 126.0 | true |
| `cigre_mv` | cross-check candidate | `create_cigre_network_mv` | 15 | 15 | 2 | 18 | 9 | 44.74215 | 1.71 | 24.95 | 50.0 | true |

## Next Step

Use this inventory as the Agent A input to G0. Do not proceed to E1.S2, E1.S3,
or E1.S4 until their dependencies are satisfied by the registers.
