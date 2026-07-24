# E3.S2 IC-2 Loading-Trajectory Scaffold

Task: E3.S2 IC-1 to IC-2 integration readiness.

Status: scaffold only. This packet adds a trajectory-only Tier-1 route from already validated IC-1 loading-input readiness into the approved `LoadingTrajectoryResult` boundary. It is designed for tiny synthetic fixtures and future runner wiring, not for real annual net-load analysis.

## What Changed

`LoadingTrajectoryCapacityProvenance` records the capacity denominator needed to materialize loading trajectories: aggregate kVA, transformer indices, unit nameplates, source, metadata, and the still-pending G1-A2/E3.S2b capacity-convention status.

`build_tier1_loading_trajectory_scaffold(...)` consumes a `NetLoadLoadingInputReadiness`, validates that it does not carry legacy event/probability outputs, computes downstream P/Q/S and import/export/zero direction-gated loading, and returns a `Tier1LoadingTrajectoryScaffold` satisfying the shared loading-trajectory validator. The manifest metadata carries G0-A3 threshold and persistence as governed metadata only.

## Boundary

This scaffold does not load real component trajectories, aggregate real project net load, count overload episodes, compute `P(E)`, run an E3.S2b capacity/domain screen, compare Tier-1 against AC, choose total versus firm capacity, sign A-013/G2 values, or produce manuscript numbers.

The path fails closed when capacity provenance is missing or malformed, when input readiness advertises unaccepted real arrays, when legacy event/probability metadata appears, or when IC-1 calendar/cadence validation fails.

No new scientific decision, assumption, data choice, or methodological protocol is introduced. The implementation applies already-approved G0-A3, G0-A4, G1-A2, and E5-S3-T1 guardrails.

## Verification

Focused local verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_evaluator_sum.py tests\test_evaluator_loading_trajectory.py`: 33 passed.

PR validation:

- `.\scripts\task.ps1 ownership`: passed for 4 Agent A-owned changed paths.
- `.\scripts\task.ps1 test-fast`: 523 passed, 2 skipped, 7 deselected.
- `git diff --check`: passed with Git line-ending notices only.
