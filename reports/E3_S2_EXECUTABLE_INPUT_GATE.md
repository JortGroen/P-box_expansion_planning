# E3.S2 Executable Input Gate

Task: E3.S2 IC-1 NetLoadProvider readiness.

Status: scaffold/readiness only. This packet adds a metadata-only executable-input
gate for future real component integration. It checks whether baseline, EV, HP,
PV/weather, adoption, and flexibility artifacts are present, versioned,
calendar-compatible, and signed enough for their intended use before IC-1 loads
real component trajectories.

## What The Gate Checks

`ExecutableInputArtifact` records one component-family artifact without carrying
P/Q arrays. `validate_executable_input_gate(...)` requires one unique artifact
for each IC-1 integration family: baseline, EV, HP, PV, adoption, and
flexibility. The artifacts must share one `calendar_id`, use the 900-second
IC-1 cadence, cite version IDs, carry manifest/provenance metadata, and prove
HP/PV share one WEATHER-001 weather-driver identity.

For real execution, every required artifact must have `artifact_status =
"accepted"`, cite at least one signed register/decision ID, cite a manifest
path, and list no blocking IDs. Any unsigned or scaffold artifact fails before
arrays can be loaded, and the error reports the blocking register/decision IDs.

## Current Boundary

This is not a real integration run. Synthetic fixtures prove the gate behavior,
including explicit failure for unsigned HP/D-004-style blockers such as `D-013`,
`HP-LOCAL-SCALING`, and `D-004`. The gate prepares later E3.S2b prerequisite
checking, but this PR does not load EV/HP/PV/baseline arrays, assemble real net
load, run IC-2, detect events, compute `P(E)`, produce a capacity-screen result,
or generate manuscript numbers.

## Verification

Focused IC-1 contract tests cover ready metadata, missing component families,
unsigned blockers with decision IDs, calendar mismatch, HP/PV weather mismatch,
missing version IDs, missing signed IDs, missing manifest paths for accepted
artifacts, and non-accepted artifacts without blocking IDs.

Final local verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_evaluator_net_load.py`: 52 passed.
- `.\scripts\task.ps1 ownership`: passed for 5 Agent A paths.
- `.\scripts\task.ps1 test`: 413 passed, 2 skipped.

