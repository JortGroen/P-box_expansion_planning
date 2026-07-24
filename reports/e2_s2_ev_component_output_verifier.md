# E2.S2 EV Component-Output Verifier

Status: candidate-only handoff reproducibility scaffold for Agent A IC-1 preflight use.

## Purpose

PR #219 committed the EV candidate-only component-output manifest while keeping the actual low/middle/high EV-only NPZ outputs ignored under `data/processed/elaad_profiles/component_outputs/`. This verifier makes that handoff reproducible in another worktree: it either verifies the ignored NPZs against the committed manifest or rebuilds them from committed metadata after rechecking candidate processed-profile SHA-256 hashes.

## Command

```powershell
.\.venv\Scripts\python.exe data\get_ev_component_outputs.py verify
.\.venv\Scripts\python.exe data\get_ev_component_outputs.py rebuild
```

`verify` checks existing ignored component-output files against `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json`. `rebuild` loads the committed component-input scaffold, checksum preflight, and EV-005B candidate-selection manifest set, verifies all candidate processed-profile NPZ checksums before any array loading, materializes the three ignored EV-only 2035 branch outputs, and compares their NPZ SHA-256 values to the committed component-output manifest.

## Fail-Closed Behavior

A clean worktree without the ignored EV artifacts fails closed. The command prints exact missing paths and instructs the user to restore the ignored candidate processed-profile NPZs from the verified local artifact store, or ask the PI before regenerating ElaadNL source batches. It never downloads data, calls the ElaadNL API, opens held-out/quarantined batches, or substitutes regenerated evidence silently.

## Boundaries

This is not net-load assembly and not a capacity or congestion result. It does not certify home `M = 1000` or public `M = 1200`, choose a final low/middle/high branch, run event analysis, estimate `P(E)`, run capacity screens, or produce manuscript numbers. It preserves EV-005B, EV-CAL-001, RNG-001, EV-007A/A-014, EV-008A, source-member, seed, checksum, duplicate/multiplicity, and candidate-only provenance already committed upstream.

## Local Check

In this clean task worktree, `verify` intentionally reported the three missing ignored component-output NPZ paths and the rebuild instruction. Synthetic tests cover successful rebuild/manifest comparison and both missing-output and missing-candidate fail-closed paths without requiring real Elaad profile arrays in CI.
