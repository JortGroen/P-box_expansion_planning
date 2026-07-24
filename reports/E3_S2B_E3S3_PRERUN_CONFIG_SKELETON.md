# E3.S2b/E3.S3 Pre-Run Config Skeleton

Task: E3.S2b/E3.S3 pre-run scaffold support.

Status: scaffold/configuration only. This packet adds a small manifest-ready guard around synthetic `LoadingTrajectoryResult` fixtures so later runner work can prepare E3.S2b future-layer screen and E3.S3 AC-validation wiring without accidentally producing a scientific screen, event result, capacity conclusion, or G2 tier-comparison claim.

## What Changed

`LoadingTrajectoryPreRunConfig` records the intended pre-run purpose, planned years, 900-second cadence, governed G0-A3 event metadata, and the still-pending G1-A2/E3.S2b capacity-convention status. The governed threshold fields are metadata only: primary `L_import > 1.0 p.u.` for four consecutive 15-minute import steps, with `1.1` and `1.2 p.u.` sensitivities listed but not evaluated.

`prepare_loading_trajectory_prerun_manifest(...)` validates synthetic `LoadingTrajectoryResult` fixtures through the shared IC-2 validator and emits array-free manifest metadata. It accepts only non-primary `window_set` fixtures, rejects full-year primary-probability payloads, and rejects legacy boolean overload payloads so IC-3/G2 setup cannot consume a precomputed event flag by mistake.

## Boundary

This packet does not load real IC-1 net-load arrays, aggregate real component trajectories, call an event detector, calculate `P(E)`, run a capacity/domain screen, compare Tier-1 against AC, choose total versus firm capacity, sign A-013/G2 values, or produce manuscript numbers. It is synthetic-fixture plumbing for future runner configuration only.

No new scientific decision, assumption, data choice, or manuscript-number protocol is introduced. The scaffold implements existing G0-A3, G0-A4, G1-A2, and E5-S3-T1 guardrails as executable validation metadata.

## Verification

Focused local verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_evaluator_loading_trajectory.py`: 12 passed.

Final local validation:

- `.\scripts\task.ps1 ownership`: passed for 4 Agent A paths.
- `.\scripts\task.ps1 test-fast`: 507 passed, 2 skipped, 7 deselected.
- `git diff --check`: passed with line-ending warnings only.
