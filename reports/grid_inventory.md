# E1.S1 Grid Inventory

Status: blocked on live grid-stack import.

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

## Blocker Evidence

The live grid-stack import did not complete in this worktree environment:

```text
python -u -c "print('start'); import simbench as sb; print('simbench imported', getattr(sb, '__version__', 'unknown'))"
```

Observed output after several minutes:

```text
start
```

The process remained inside `import simbench`; therefore no SimBench network could
be loaded and no deterministic `pandapower.runpp()` convergence evidence could be
produced in this session.

## Inventory Table

The inventory table is intentionally not filled with guessed values. It must be
generated from `src.grid_loader.inventory_rows()` once the grid-stack import is
working.

| key | role | code | buses | lines | trafos | loads | static_generators | total_load_mw | total_sgen_mw | line_length_km | trafo_s_rated_mva | baseline_converged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `simbench_semiurb` | primary candidate | `1-MV-semiurb--0-sw` | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |
| `simbench_urban` | secondary SimBench candidate | `1-MV-urban--0-sw` | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |
| `cigre_mv` | cross-check candidate | `create_cigre_network_mv` | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |

## Next Step

Resolve the Python/grid-stack import hang, then run the live inventory and
baseline convergence pass for the three candidate grids.
