# E3.S2a EV Held-Out Adequacy Preflight Scaffold

## Purpose

This PR adds the EV-side automation that will later guard candidate-vs-held-out EV library adequacy testing. The scaffold consumes the accepted EV IC-1 artifact index and the existing unsigned downstream adequacy criterion packet, then writes a blocker manifest instead of touching held-out data or producing a result.

## Artifact

- `data/metadata/ev_adoption/e3_s2a_ev_heldout_adequacy_preflight_blockers.json`
- Artifact type: `e3_s2a_ev_heldout_adequacy_preflight_blocker_manifest`
- Status: `blocked_before_held_out_access`
- Regeneration command: `./.venv/Scripts/python.exe data/get_ev_adequacy_preflight.py`

## What The Preflight Checks

The builder validates that the EV accepted-artifact index remains candidate-only and fail-closed, verifies the criterion packet is still non-executable, checks low/middle/high scenario coverage, requires source manifest/checksum fields, records output NPZ checksum expectations without loading arrays, and emits blocker rows for unresolved prerequisites.

## Current Blockers

The committed manifest includes blockers for the unsigned downstream aggregate adequacy criterion, Agent A IC-1 assembly not yet accepted, held-out access not explicitly invoked, A-016 scenario consistency not resolved, final low/middle/high branch not selected, candidate output checksums not verified in the consuming worktree, and inherited EV accepted-index blockers including M sufficiency and integrated assembly.

## Non-Claims

This scaffold does not open held-out or quarantined EV batches, make new ElaadNL API calls, load profile arrays, run net-load aggregation, event detection, `P(E)`, threshold analysis, capacity screens, or produce manuscript numbers. It does not claim home `M=1000` or public `M=1200` are sufficient.

## Validation

- `./.venv/Scripts/python.exe -m pytest tests/test_ev_model.py -q -k "e3_s2a_ev_heldout or downstream_adequacy_criterion"`: 4 passed, 107 deselected.
- `./.venv/Scripts/python.exe -m pytest tests/test_ev_model.py -q -k "adequacy_preflight"`: 2 passed, 109 deselected.
- `./scripts/task.ps1 ownership`: passed for Agent C paths.
- `./scripts/task.ps1 test-fast`: 665 passed, 2 skipped, 7 deselected.
- `git diff --check`: passed.
