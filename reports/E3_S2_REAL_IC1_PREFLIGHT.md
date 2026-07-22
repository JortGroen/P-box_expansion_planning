# E3.S2 Real IC-1 Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.

Status: scaffold/readiness only. This packet wires the executable-input gate into
the future adapter-backed NetLoadProvider path so real IC-1 arrays cannot be
requested until baseline, EV, HP, PV/weather, adoption, and flexibility input
artifacts are accepted for the intended use.

## What Changed

`GatedAdapterBackedNetLoadProvider` keeps the public
`get_net_load(scenario, year, time_domain, rho, seed)` shape and wraps the
existing adapter-backed IC-1 harness. It calls `validate_executable_input_gate`
before any adapter is asked for component outputs. The resulting manifestable
gate record is preserved in the returned `NetLoadResult.metadata` when accepted
synthetic fixtures are used.

The gate remains metadata-only: it checks artifact presence, version IDs,
manifest paths, calendar/cadence compatibility, signed register IDs, explicit
blocking IDs for unsigned/scaffold artifacts, and shared HP/PV weather identity.

## Current Blocking IDs

Synthetic tests demonstrate the fail-closed path with unsigned EV selection
blocked by `EV-005B`. Current real integration is also still constrained by
unsigned or not-final component decisions such as local HP scaling (`D-013` /
`HP-LOCAL-SCALING`) and D-004 paired HP/PV validation or cold-spell tolerance
sign-off. `D004-SOURCE-MEMBER-ACCEPTANCE` is now approved for internal
first-screen source/member use, but it does not authorize net-load, event,
`P(E)`, capacity-screen, or manuscript analysis.
## Boundary

This is not a real net-load aggregation run. It does not load real EV, HP, PV,
baseline, adoption, or flexibility arrays; does not run IC-2 event detection;
does not compute `P(E)`; does not produce an E3.S2b capacity-screen result; and
does not generate manuscript numbers.

## Verification

Focused IC-1 tests cover unsigned inputs blocking before adapter calls and
accepted synthetic fixtures passing through the gated provider without event,
threshold, or capacity-screen metadata.

Final local verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_evaluator_net_load.py`: 54 passed.
- `.\scripts\task.ps1 ownership`: passed for 5 Agent A paths.
- `.\scripts\task.ps1 test`: 419 passed, 2 skipped.
- `git diff --check`: passed.



