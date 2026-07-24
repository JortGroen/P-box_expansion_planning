# E2.S6 A-014 Executable EV Adoption Artifact

## Purpose

This artifact promotes the PI-approved EV-007A Alkmaar 2035 local home/public charge-point totals and approved A-014 static `p_mw` node allocation rule into an executable per-node adoption input for future IC-1 assembly.

Machine-readable artifact: `data/metadata/ev_adoption/e2_s6_a014_alkmaar_executable_adoption_artifact.json`

## What Is Materialized

The artifact records the declared 2035 `low`, `middle`, and `high` Alkmaar branches without selecting a final paper branch:

- low: 7,992 home and 4,183 public charge points;
- middle: 9,386 home and 5,127 public charge points;
- high: 10,343 home and 6,138 public charge points.

For each branch, counts are allocated across the 115 in-service SimBench `net.load` rows using A-014 static `p_mw` weights and deterministic largest-remainder rounding. The artifact includes node IDs, node weights, per-node home/public counts, total-conservation checks, EV-007A source-response provenance, and links to the historical preview artifact.

## Boundary

This is an adoption-count artifact only. It does not load EV profile arrays, open held-out or quarantined batches, certify `M=1000` or `M=1200`, select the final low/middle/high branch, run net-load aggregation, run event or `P(E)` analysis, perform capacity screens, or produce manuscript numbers.

## Validation Added

`src.ev_model.a014_executable_adoption_artifact(...)` requires approved EV-007A local totals and approved A-014 node weights before producing the artifact. Tests verify committed artifact equality, node-total conservation, nonnegative per-node counts, stable 115-node coverage, and fail-closed behavior when local-count or allocation status is not approved.
