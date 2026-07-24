# E3.S2a EV Per-Node Export Strategy

## Purpose

PR #265 correctly kept the EV generic component-output packet fail-closed because each declared 2035 EV scenario is currently one ignored multi-node NPZ with shape `115 x 35040`, while Agent A's current accepted NPZ artifact loader expects one node with one-dimensional `p_kw`, `q_kvar`, and `timestamps` arrays.

This task adds the EV-owned resolution route: `data/get_ev_component_outputs.py export-per-node` splits verified multi-node EV component-output NPZs into one scenario/node work unit at a time, producing per-node NPZ files and per-node manifests that match Agent A's current one-node loader boundary once a future signed executable route allows accepted status.

## Runner Behavior

The runner consumes `data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json` and requires the merged candidate-only, held-out-closed EV packet. Before reading any source array it verifies the source multi-node NPZ SHA-256 against the generic packet. It rejects unsafe approval/source tokens, duplicate scenario records, duplicate or mismatched node IDs, checksum mismatches, and any attempt to write `artifact_status = accepted` without an explicit future approval flag.

Each successful work unit writes:

- one ignored per-node NPZ under `data/processed/elaad_profiles/component_outputs/per_node/`;
- one metadata manifest under `data/metadata/ev_adoption/per_node_component_output_manifests/`;
- a checkpoint update under `data/metadata/ev_adoption/e3_s2a_ev_per_node_export_preflight.json`.

Existing per-node outputs are skipped only when the existing manifest and file checksum agree with the current source multi-node checksum.

## Current Worktree Result

The clean Agent C worktree does not contain the ignored source multi-node EV component-output NPZs, so no real per-node outputs were created. The committed preflight/blocker manifest records the exact missing source artifacts:

| Scenario | Required source NPZ | SHA-256 |
|---|---|---|
| high | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_high.npz` | `dd95f30d74da00b6fb87c2ced8f402b4d612c59a28e7d1d33e9e82fcd7a805d5` |
| low | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_low.npz` | `a896794ddd9f004fe945c62a5b84b2b1b6e9381cbecd80b17ca7c749de68ce65` |
| middle | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_middle.npz` | `38081c7f849bb679a19560d1a7f7fd6d8428e35ef6cad2087e4d82a46c1e568d` |

Resume command after restoring those ignored NPZs:

```powershell
.\.venv\Scripts\python.exe data\get_ev_component_outputs.py export-per-node --generic-loader-packet data\metadata\ev_adoption\e3_s2a_ev_ic1_generic_component_output_manifest_packet.json --checkpoint-path data\metadata\ev_adoption\e3_s2a_ev_per_node_export_preflight.json
```

If the full 3 scenario x 115 node export is expected to exceed about 15 minutes in the consuming worktree, issue the project LONG-RUN NOTICE before launching it. The runner is already checkpointed at one scenario/node per work unit.

## Non-Claims

This work does not open held-out or quarantined EV batches, does not call the ElaadNL API, does not certify `M = 1000` or `M = 1200`, does not choose the final low/middle/high branch, does not run net-load aggregation, event detection, `P(E)`, capacity screens, or manuscript-result analysis, and does not edit Agent A-owned loader code.