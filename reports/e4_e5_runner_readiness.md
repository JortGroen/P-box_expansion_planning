# E4/E5 Synthetic Runner-Readiness Scaffold

Status: synthetic/fail-closed scaffold only. This packet does not run real trajectories, estimate real `P(E)`, run a real rho sweep, choose a capacity convention, sign A-013 or G2 values, approve G3, produce decision-engine outputs, or create manuscript numbers.

## Purpose

The B-owned runner-readiness scaffold records how future real `LoadingTrajectoryResult` outputs can plug into the E4.S1/E5.S3 math layer once the upstream artifacts and signed gates exist. It is intentionally array-free at the manifest boundary: synthetic fixtures are evaluated through the approved G1-A2 output-error endpoint path, and the resulting packet stores alpha-indexed lower/upper event counts, probabilities, confidence intervals, and sample identities.

## Implemented Synthetic Packet

`src/pbox_runner_readiness.py` defines `e4-e5-synthetic-runner-readiness-v1`. The packet combines:

- output-error endpoint event counts from validated synthetic `LoadingTrajectoryResult` fixtures;
- alpha-indexed lower/upper probability bounds and separate confidence intervals;
- ordered sample indices reused across alpha levels as the CRN identity check;
- optional synthetic dense-rho monotonicity diagnostics from `src/pbox_monotonicity.py` with matching sample count;
- explicit invariants that output-error endpoints are applied before event detection, the direction gate uses unwidened `P_net`, probability widening is forbidden, independent error sampling is forbidden, and defuzzification is forbidden;
- a real-use blocker manifest that remains present even when the synthetic packet is internally valid.

The synthetic tests include a hand-computed endpoint-count fixture, a direction-flip fixture proving the unwidened import gate resets the four-step episode detector, and tamper regressions for false paper-facing relabeling, scalar collapsed probability fields, post-hoc probability-widening metadata, broken sample identity, missing blockers, and mismatched rho-sweep sample count.

## Real-Use Blockers

The companion `e4-e5-real-runner-blocker-v1` packet fails closed until all real-use prerequisites exist. The blocker list is:

- missing signed G2 Tier-1 endpoints;
- unsigned A-013 grid-error value/form;
- missing capacity convention and denominator provenance;
- missing real `LoadingTrajectoryResult` manifests;
- missing real output-error endpoint records;
- missing A-016 scenario consistency manifest;
- G3 monotonicity verdict pending where vertex shortcut is claimed.

This packet is a future runner/report boundary guard, not a substitute for the missing artifacts or PI decisions.
