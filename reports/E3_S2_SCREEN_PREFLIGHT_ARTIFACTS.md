# E3.S2 Screen Preflight Artifacts

Task: E3.S2 IC-1 NetLoadProvider readiness.

Status: scaffold/readiness only. This packet adds the next metadata layer behind
the executable-input gate for future E3.S2b screen preparation. It defines a
manifestable preflight config and validates the required baseline, EV, HP,
PV/weather, adoption, and flexibility artifacts before any real IC-1 arrays can
be assembled.

## What Changed

`FutureLayerScreenPreflightConfig` records the planned screen axes, node set,
time domain, timestep cadence, and metadata without carrying trajectories or
results. `validate_future_layer_screen_preflight(...)` combines that config with
the executable-input gate and returns a manifest-ready prerequisite record only
when every required artifact is present, accepted, versioned, manifest-linked,
calendar-compatible, and signed for the intended use.

Missing artifacts can now report explicit blocker IDs via
`missing_artifact_blockers`, so future E3.S2b configs can fail with actionable
messages such as `EV-005B`, `D-013`, `HP-LOCAL-SCALING`,
`D004-SOURCE-MEMBER-ACCEPTANCE`, or `WEATHER-001` rather than a vague missing
input error.

## Current Boundary

This is not a screen run. It does not load real component arrays, assemble real
net load, call IC-2, detect events, compute `P(E)`, report threshold outcomes,
produce capacity-screen values, or generate manuscript numbers. It only prepares
manifest fields and fail-closed prerequisite validation for a later runner path.

`D004-SOURCE-MEMBER-ACCEPTANCE` is approved for internal first-screen
source/member use, but final paired HP/PV validation and cold-spell tolerance
sign-off remain separate from this scaffold. EV member selection/use and HP local
annual scaling remain fail-closed unless their required PI decisions/artifacts
are accepted.

## Verification

Focused IC-1 tests cover accepted synthetic preflight metadata, missing artifact
blockers, unsigned artifact blockers, invalid rho config, and invalid blocker
metadata.

Final local verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_evaluator_net_load.py`: 58 passed.
- `.\scripts\task.ps1 ownership`: passed for 5 Agent A paths.
- `.\scripts\task.ps1 test`: 425 passed, 2 skipped.
- `git diff --check`: passed.
