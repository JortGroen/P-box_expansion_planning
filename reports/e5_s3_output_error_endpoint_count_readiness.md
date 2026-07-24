# E5.S3 Output-Error Endpoint-Count Readiness

Status: synthetic/fail-closed scaffold. This packet does not use real trajectories, estimate real `P(E)`, choose a capacity convention, sign A-013/G2/G3, or produce manuscript numbers.

## What Is Ready

- `e5s3-output-error-endpoint-count-bridge-v1` consumes precomputed lower/upper endpoint event counts by alpha after G1-A2 loading widening and four-step event detection.
- The bridge feeds those counts into the alpha probability estimator, so probabilities and confidence intervals are recomputed from lower/upper counts instead of widened after estimation.
- Serialized payload validation preserves alpha-indexed lower/upper rows, common ordered sample identities across alpha rows, the unwidened `P_net` import direction gate, endpoint-before-event provenance, arbitrary unknown dependence, and forbidden independent error sampling.
- Synthetic tamper tests reject probability-margin fields, independent sampling labels, missing endpoint-count provenance, stale real-use relabeling, tampered probability rows, and stripped blocker manifests.

## Real-Use Blockers

The first paper-facing E5.S3 run remains blocked until the following concrete artifacts or approvals exist:

- signed G2 Tier-1 additive endpoint values and adequacy verdict over the frozen domain;
- signed A-013 grid-error numerical value/form for the run layer;
- approved capacity convention and denominator provenance;
- A-016 scenario-consistency manifest for the integrated 2035 inputs;
- real `LoadingTrajectoryResult` and output-error endpoint-count manifests from Agent A/C runner surfaces;
- G3 approval if any vertex shortcut is claimed for paper-facing probability output.

## Acceptance Notes

The bridge is intentionally count-only. It assumes endpoint event indicators have already been generated from widened loading trajectories under the approved G1-A2 semantics, and it refuses to add model-error margins to probabilities afterward. Toy values in tests exercise validation only and are not scientific assumptions.