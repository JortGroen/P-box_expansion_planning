# Agent B Pre-Experiment Readiness Summary

Status: synthetic/scaffold-only readiness summary. This report does not run real
trajectories, estimate real `P(E)`, choose a capacity convention, sign A-013 or
G2 values, authorize G3, or produce manuscript numbers.

## B-Owned Guardrails Ready

- P-box vertex propagation is implemented as synthetic/pre-G3 or explicitly
  `G3_APPROVED`; paper-facing vertex output is blocked unless G3 is recorded
  and the rows carry `G3_APPROVED` mode.
- Output-error propagation scaffold composes G1-A2 loading endpoints before
  event detection, preserves the unwidened `P_net` import gate, and builds
  endpoint event-count probability records without post-hoc probability
  widening.
- Paper-facing p-box probability and decision-result report payloads require
  G2 Tier-1 envelope approval, signed A-013 grid-error value, approved capacity
  convention, nonempty capacity denominator provenance, and manifested
  output-error endpoint records.
- Serialized `guarded-pbox-report-v1` payload validation rejects missing guard
  fields, result-kind mismatches, collapsed probability rows, inconsistent
  paper-facing flags, endpoint-record claim mismatches, and stripped G3 vertex
  evidence.
- Decision-layer scaffolds for alpha/rho/procurement/deferral/VoI remain
  alpha-indexed lower/upper and do not expose an independent paper-facing
  serializer; future decision presentation should pass through the guarded
  p-box reporting boundary.

## Gates Still Blocking Paper-Facing Outputs

- G2 is pending: no approved Tier-1 endpoint values or adequacy verdict exist.
- A-013 is pending: no signed numerical grid-error value is available for real
  output-error propagation.
- Capacity convention and denominator provenance remain open until the
  future-layer capacity/domain screen resolves the total-versus-firm choice and
  records provenance.
- Real endpoint records are absent: no real validated loading trajectories have
  been widened and classified into lower/upper event indicators through the
  runner.
- G3 is pending: endpoint-only vertex shortcut cannot be used for paper-facing
  outputs until the monotonicity verdict approves it.

## Exact Inputs B Needs Before Real E4/E5 Runs

From Agent A:

- Manifested validated `LoadingTrajectoryResult` outputs for the relevant real
  integrated trajectories, including loading arrays, finite-value validation,
  unwidened import/export direction masks, threshold, persistence length,
  timestep cadence, and import/export diagnostics required by E5-S3-T1.
- G2 Tier-1-vs-AC enclosure evidence over the frozen operating domain,
  including the approved additive Tier-1 lower/upper endpoint values or a
  declared selective-AC/rejection route.
- Capacity/denominator provenance produced by the future-layer capacity/domain
  screen, including whether total or firm capacity is selected and any required
  one-transformer-out AC validation if firm capacity is primary.

From Agent C:

- Runner-manifested real E3 integrated sample outputs with root/sample seed
  identity, component-stream provenance, scenario/adoption/flexibility labels,
  weather/member IDs, and output checksums.
- E3 library-adequacy acceptance evidence for the finite source libraries and
  held-out diagnostics before B treats the integrated aleatory ensemble as
  paper-facing input.
- Runner/report integration that consumes B's `guarded-pbox-report-v1` boundary
  instead of serializing p-box probability or decision rows directly.

From the PI/registers:

- Signed A-013 grid-error value/form for the run layer.
- Signed G2 verdict and Tier-1 endpoint policy.
- Signed capacity convention and denominator provenance.
- Signed G3 monotonicity verdict before any paper-facing vertex shortcut use.
- Any G5/G6 case-selection or results-freeze decisions required before final
  manuscript-facing outputs.

## Next B Action Once Inputs Arrive

B can then run the synthetic-tested E5 path on manifested real inputs: apply the
approved output-error endpoints to complete loading trajectories before event
detection, compute lower/upper event counts and confidence intervals, validate
or replace vertex propagation according to G3, and emit guarded alpha-indexed
p-box/decision payloads through the runner/report boundary.