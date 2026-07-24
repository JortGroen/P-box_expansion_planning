# E3.S2 Real-Artifact Assembly Preflight Scaffold

Task: E3.S2 IC-1 integration readiness.

Status: scaffold/preflight only. This branch adds a path/checksum-aware dossier helper around the existing register-backed executable-input gate and the IC-1/IC-2 bridge preflight. It is intended to let a future runner prove which metadata artifacts were present, checksummed, accepted, blocked, or missing before any real component arrays are opened.

## What Changed

`build_real_artifact_assembly_preflight(...)` composes the merged executable-input dry run with the loading-trajectory bridge metadata. It validates metadata packet paths, optional SHA-256 expectations, downstream blocker IDs, capacity provenance presence, and the existing accepted/blocked component states. Synthetic tests show a tiny accepted fixture can pass this dossier, while checksum mismatches and current-project-style unsigned baseline/HP/PV/adoption blockers fail closed.

## Boundary

No real EV, HP, PV, baseline, adoption, or flexibility trajectories are loaded. No net-load aggregation, IC-2 real execution, event detection, event counts, `P(E)`, capacity/domain conclusion, G2 result, G3 verdict, or manuscript number is produced. G0-A3 threshold metadata remains metadata only: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps, with `1.1` and `1.2` as sensitivities.

## Current Blockers

The scaffold preserves the current fail-closed boundary. Real execution still needs accepted executable baseline, HP value binding, PV/weather value and pairing packets, adoption per-node artifacts, A-013/G2, capacity-convention/domain provenance, and scenario-consistency inputs. The newly merged D014 PV orientation/tilt value-choice packet remains proposed and does not make executable PV input ready.
