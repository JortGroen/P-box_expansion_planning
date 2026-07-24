# E3.S2a EV Per-Node Manifest Index Preflight

## Purpose

The merged EV per-node export runner can split each candidate-only 115-node EV component-output NPZ into one one-dimensional node artifact. This follow-up adds the deterministic manifest-index layer that Agent A can later consume to enumerate those per-node manifests without accepting the old multi-node wrapper as loadable.

## Current Clean-Worktree Result

The committed preflight at `data/metadata/ev_adoption/e3_s2a_ev_per_node_manifest_index_preflight.json` is intentionally blocked. It enumerates 345 expected units: 3 declared 2035 EV branches (`high`, `low`, `middle`) x 115 SimBench load nodes. No per-node NPZ/manifests are present in this clean worktree, so `verified_per_node_unit_count = 0` and `missing_per_node_unit_count = 345`.

## Guardrails

The builder verifies repository-relative paths, per-node manifest checksums, NPZ checksums, current Agent A single-node 1D loader-contract fields, candidate-only status, and false flags for held-out/quarantined/API/integrated analysis/event/capacity/final-branch/M-sufficiency claims. It rejects unsafe approval/status tokens and stale generic or multi-node paths. Scenario/node filters remain allowed for synthetic fixtures and diagnostics, but a filtered index is never marked real-loader-ready for the first experiment; real readiness requires the full declared 3 x 115 scope.

## Resume

After restoring or rebuilding the ignored source multi-node EV component-output NPZs and running the per-node export, rerun:

```powershell
.\.venv\Scripts\python.exe data\get_ev_component_outputs.py write-per-node-index --generic-loader-packet data\metadata\ev_adoption\e3_s2a_ev_ic1_generic_component_output_manifest_packet.json --per-node-index-path data\metadata\ev_adoption\e3_s2a_ev_per_node_manifest_index_preflight.json
```

If the full split or checksum sweep is expected to exceed about 15 minutes in that worktree, send the required long-run notice first. This report does not open held-out or quarantined EV data, does not run integrated net-load/event/P(E), does not select a final branch, and does not claim candidate library sufficiency.
