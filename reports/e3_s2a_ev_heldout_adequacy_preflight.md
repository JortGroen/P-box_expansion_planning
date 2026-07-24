# E3.S2a EV Held-Out Adequacy Preflight Scaffold

## Purpose

This PR adds the EV-side automation that will later guard candidate-vs-held-out EV library adequacy testing. The scaffold consumes the accepted EV IC-1 artifact index and the existing unsigned downstream adequacy criterion packet, then writes a blocker manifest instead of touching held-out data or producing a result.

## Artifact

- `data/metadata/ev_adoption/e3_s2a_ev_heldout_adequacy_preflight_blockers.json`
- Artifact type: `e3_s2a_ev_heldout_adequacy_preflight_blocker_manifest`
- Status: `blocked_before_held_out_access`
- Regeneration command without local checksum scan: `./.venv/Scripts/python.exe data/get_ev_adequacy_preflight.py`
- Checkpointed candidate-output checksum command: `./.venv/Scripts/python.exe data/get_ev_adequacy_preflight.py --verify-candidate-output-checksums`
- Checksum checkpoint artifact: `data/metadata/ev_adoption/e3_s2a_ev_candidate_component_output_checksum_preflight.json`

## What The Preflight Checks

The builder validates that the EV accepted-artifact index remains candidate-only and fail-closed, verifies the criterion packet is still non-executable, checks low/middle/high scenario coverage, requires source manifest/checksum fields, records output NPZ checksum expectations without loading arrays, optionally hashes the ignored candidate component-output files in a checkpointed/resumable step, and emits blocker rows for unresolved prerequisites. If the ignored NPZ files are absent, the checksum step records exact missing paths and keeps the adequacy preflight blocked.

## Current Blockers

The committed manifest includes blockers for the unsigned downstream aggregate adequacy criterion, Agent A IC-1 assembly not yet accepted, held-out access not explicitly invoked, A-016 scenario consistency not resolved, final low/middle/high branch not selected, candidate output checksums not verified in the consuming worktree because the ignored NPZ files are absent, and inherited EV accepted-index blockers including M sufficiency and integrated assembly. Q-5 is resolved by G0-A3 and is no longer listed as an EV readiness blocker; event use still requires the approved threshold semantics to be implemented in the later integrated path.

## Non-Claims

This scaffold does not open held-out or quarantined EV batches, make new ElaadNL API calls, load profile arrays, run net-load aggregation, event detection, `P(E)`, threshold analysis, capacity screens, or produce manuscript numbers. It does not claim home `M=1000` or public `M=1200` are sufficient.

## Validation

- `./.venv/Scripts/python.exe -m py_compile data/get_ev_adequacy_preflight.py src/ev_model.py tests/test_ev_model.py`: passed.
- `./.venv/Scripts/python.exe -m pytest tests/test_ev_model.py -q -k "readiness_guardrail or adequacy_preflight or e3_s2a_ev_heldout or candidate_output_checksum_preflight"`: 8 passed, 106 deselected.
- `./.venv/Scripts/python.exe -m pytest tests/test_methods_registry.py -q`: 4 passed.
- `./scripts/task.ps1 ownership`: passed for Agent C paths.
- `./scripts/task.ps1 test-fast`: 684 passed, 2 skipped, 7 deselected.
- `git diff --check`: passed; Git reported only line-ending normalization warnings.
