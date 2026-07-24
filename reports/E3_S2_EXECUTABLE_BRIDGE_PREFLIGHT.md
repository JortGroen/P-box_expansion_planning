# E3.S2 Executable Bridge Preflight

Task: E3.S2 IC-1/IC-2 integration readiness.

Status: metadata/preflight only. This packet adds an array-free bridge from the register-backed IC-1 executable-input dry run to the IC-2 loading-trajectory pre-run metadata surface.

## What Changed

`build_executable_loading_bridge_preflight(...)` combines the existing executable-input artifact gate with the merged `LoadingTrajectoryPreRunConfig`. It records G0-A3 threshold and persistence metadata, common planning years, 900-second cadence, component artifact manifest paths where available, and capacity provenance status without building loading arrays or selecting a capacity convention.

The bridge has two separate readiness flags. `ready_for_synthetic_loading_manifest` can be true for tiny accepted fixtures with synthetic capacity provenance. `ready_for_first_real_experiment` remains false while downstream blockers such as A-013, G2, G1-A2 capacity convention, or A-016 scenario consistency remain unresolved.

## Boundary

This is not a real IC-1 or IC-2 run. It does not load annual EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate real net load; does not build real loading trajectories; does not detect events or count episodes; does not compute `P(E)`; does not run a capacity/domain screen; and does not produce manuscript numbers.

No new decision, assumption, data choice, or methodological protocol is introduced. The helper composes already-approved scaffolds and records existing blocker IDs.

## Verification

Focused local verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_evaluator_net_load.py`: 69 passed.

PR validation:

- `.\scripts\task.ps1 ownership`: passed for 4 Agent A-owned changed paths.
- `.\scripts\task.ps1 test-fast`: 545 passed, 2 skipped, 7 deselected.
- `git diff --check`: passed with Git line-ending notices only.
