# E4/E5 Real-Input Readiness Guard

Status: synthetic/fail-closed guard implementation; no real experiment and no paper-facing result.

This packet adds `e4-e5-real-input-readiness-v1`, a machine-readable preflight for the future E4.S1/E5.S3 runner/report boundary. The preflight does not run trajectories or estimate `P(E)`. It validates whether a future payload carries clean signed/provenance references for G2 Tier-1 endpoint values, A-013 grid-error value/form, capacity convention and denominator provenance, A-016 scenario consistency, real `LoadingTrajectoryResult` manifests, real output-error endpoint records, and G3 if a vertex shortcut is claimed.

The guard fails closed. Missing prerequisites become deterministic `blocker_keys`; stale-looking approval IDs containing tokens such as `proposed`, `pending`, `unsigned`, `placeholder`, `synthetic`, `TODO`, or `TBD` are rejected rather than accepted as blockers. Output records must be under `alpha_endpoint_records` and pass the existing alpha-indexed lower/upper endpoint validator. Top-level scalar or collapsed outputs such as `probability_bounds`, `event_count_bounds`, `probability_rows`, `p_hat`, or `defuzzified_probability` are rejected.

No real trajectories, real `P(E)`, real rho sweep, capacity convention choice, A-013/G2 numerical value, G3 verdict, decision-engine output, or manuscript number were produced.