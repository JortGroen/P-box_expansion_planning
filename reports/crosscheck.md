# E5.S4 Independent Cross-Check Plan

Status: scaffold-only plan and executable synthetic package for the p-box/math-core trust certificate. This report designs and records synthetic checks only. It does not run integrated net load, use the real G0-A3 overload threshold, introduce signed A-013 values, produce paper results, or provide manuscript numbers.

## Purpose

E5.S4 is the trust-certificate step for the uncertainty and decision math core. Before any paper-facing p-box result is produced, the implementation must pass:

1. an analytic toy case with a closed-form `P(E | rho)` that the p-box propagation can reproduce to the E5.S4 tolerance; and
2. a qualitative Baudrit-style hybrid-propagation cross-check showing that the code preserves aleatory/epistemic separation, reports alpha-indexed bounds, and does not collapse the result to one defuzzified probability.

## Cross-Check 1: Analytic Gaussian Toy Case

### Synthetic Model

Use a one-step synthetic loading variable

```text
L(rho) = mu_0 - beta * rho + sigma * Z,
Z ~ Normal(0, 1), beta > 0.
```

The event for this trust-certificate toy is the synthetic single-step event

```text
E_toy(rho): L(rho) > c_toy.
```

This is not the project overload event and must not be mixed with the G0-A3 four-step import event or its `1.0`, `1.1`, and `1.2 p.u.` threshold protocol. The toy deliberately uses a closed-form single-step event so the expected probability is auditable by hand:

```text
P(E_toy | rho) = 1 - Phi((c_toy - mu_0 + beta * rho) / sigma),
```

with `Phi` the standard-normal CDF.

### P-Box Expectation

For any alpha-cut `[rho_lo(alpha), rho_up(alpha)]`, `P(E_toy | rho)` is monotone decreasing in `rho` when `beta > 0`. Therefore:

```text
P_lower(alpha) = P(E_toy | rho_up(alpha))
P_upper(alpha) = P(E_toy | rho_lo(alpha)).
```

The executable test compares the existing vertex p-box pathway against these closed-form endpoint values with a 0.01 absolute-error tolerance. The comparison is a synthetic math-core certificate only; it is not evidence about the real feeder, threshold, capacity convention, or model-error magnitude.

### Randomness And Reproducibility

The random variable is only `Z`. The executable scaffold uses deterministic normal quantiles indexed by canonical `sample_seed(root_seed, sample_index)` identities. The same sample identities are replayed for every alpha level and rho endpoint. The closed-form values remain the oracle.

### Manifestable Analytic Certificate

The executable scaffold now emits a JSON-stable synthetic certificate for this analytic toy. Each row records the alpha cut, rho endpoints, closed-form lower/upper oracle probabilities, estimated lower/upper p-box probabilities, and absolute errors against a predeclared tolerance. The manifest records the root seed, sample count, tolerance, pass/fail flag, and explicit non-claims: it is synthetic-only, reports alpha-indexed lower/upper probabilities only, makes no G3 paper-facing vertex claim, and contains no real `P(E)`, capacity-screen, or manuscript result.

This certificate is a runner/report readiness surface rather than a scientific result. It is intended to fail closed if the analytic p-box path drifts outside tolerance or if the payload is relabeled as paper-facing.

## Cross-Check 2: Finite Hybrid P-Box Toy

The qualitative Baudrit-style hybrid propagation check is executable as a finite hybrid toy, while remaining synthetic and not a published-example reproduction. A finite aleatory state list carries explicit probability masses, and epistemic uncertainty enters only through the fuzzy `rho` alpha-cuts.

The toy event is

```text
E_finite(rho): state.value - rho > c_finite.
```

Because the event is decreasing in `rho`, each alpha-cut again gives

```text
P_lower(alpha) = sum p_i for states where state_i.value - rho_up(alpha) > c_finite
P_upper(alpha) = sum p_i for states where state_i.value - rho_lo(alpha) > c_finite.
```

The fixture uses three finite states whose probabilities sum to one. The tests hand-check the resulting alpha-indexed intervals, verify nestedness from support to core, and verify that no scalar defuzzified probability is exposed. Aleatory uncertainty stays in state probabilities; epistemic uncertainty stays in alpha-indexed lower/upper probability bounds.


## Cross-Check 3: Output-Error Endpoint Ordering Toy

This synthetic fixture exercises the E5.S3/G1-A2 output-error machinery inside the E5.S4 trust-certificate package. It uses short hand-computable loading trajectories that satisfy the shared `LoadingTrajectoryResult` contract, then builds manifest-ready endpoint-count records through the output-error path.

The toy envelope keeps all values synthetic and explicitly unsigned. For each trajectory, the lower and upper loading endpoints are composed before event detection, the import mask is taken from the unwidened `P_net` sign, and lower/upper event probabilities are derived only from lower/upper endpoint event counts. One fixture has no raw four-step event but becomes an upper-endpoint event after widening; another has high loading but an unwidened direction flip, so it still fails the four-consecutive-import event. This verifies the ordering and direction-gate invariants without running real net-load data or selecting A-013/G2 values.

Alpha support is checked by evaluating separate alpha-indexed toy sample sets while requiring the same ordered sample identifiers at every alpha level. The check is about CRN identity and reporting discipline only: it does not defuzzify, infer monotonicity, or authorize the G3 vertex shortcut for paper-facing results.


## Cross-Check 4: Synthetic Monotonicity And Bootstrap-CI Scaffold

This scaffold prepares the E4.S1/G3 trust-certificate machinery without running a real rho sweep. It consumes synthetic fixed-CRN boolean event indicators indexed by `rho`, computes point probabilities, attaches deterministic rank-bootstrap intervals from explicit resample-index fixtures, and reports adjacent monotonicity violations as diagnostics only.

The helper is intentionally not a G3 decision engine. A clean synthetic sweep shows that the diagnostic can preserve a nonincreasing event-probability pattern, while a second hand-computable fixture shows that a local increase is reported as a violation tuple. No real E3 trajectories, real `P(E)`, capacity convention, A-013/G2 values, or paper-facing vertex shortcut claim enters this check.

## Executable Synthetic Package

The E5.S4 package lives in `src/pbox_crosscheck.py` with tests in `tests/test_pbox_crosscheck.py`.

- `GaussianToyParameters`, `gaussian_tail_probability`, and `gaussian_closed_form_bounds` provide the analytic oracle.
- `estimate_gaussian_toy_pbox` routes the Gaussian toy through the existing p-box endpoint pathway using canonical RNG sample identities and `PRE_G3_SYNTHETIC` mode.
- `build_gaussian_crosscheck_manifest` emits a JSON-stable analytic certificate with alpha-indexed oracle/estimate rows, absolute errors, a tolerance guard, and explicit synthetic-only non-claims.
- `FiniteHybridState` and `finite_hybrid_bounds` provide a small qualitative hybrid/p-box fixture with exact hand-summed lower/upper event probabilities.
- `OutputErrorToyTrajectory` and `output_error_alpha_crosscheck_records` provide a synthetic output-error ordering check with manifest-ready endpoint counts and alpha-level CRN identity.
- `bootstrap_probability_interval` and `monotonicity_sweep_from_events` provide synthetic fixed-CRN rho-sweep diagnostics with deterministic rank-bootstrap intervals and explicit violation reporting.

This executable synthetic package does not use real net-load data, the project overload event, G0-A3 threshold sensitivities, signed A-013 values, G3 vertex authorization for paper-facing results, or manuscript numbers.

## Planned Acceptance Matrix

| Check | Synthetic Fixture | Expected Outcome | Blocks Paper Results If Failing |
|---|---|---|---|
| Closed-form Gaussian endpoint values | `L(rho)=mu_0-beta*rho+sigma Z` and single-step `E_toy` | Endpoint p-box probabilities match closed form within 0.01 absolute error | yes |
| Manifestable Gaussian certificate | Same Gaussian fixture serialized through `build_gaussian_crosscheck_manifest` | JSON-stable alpha rows record oracle/estimate errors, pass/fail tolerance, sample metadata, and synthetic-only non-claims | yes |
| Monotone endpoint selection | Same Gaussian fixture with `beta > 0` | Lower endpoint uses `rho_up`; upper endpoint uses `rho_lo` | yes |
| Nested alpha intervals | Trapezoidal fuzzy `rho` with multiple alpha levels | Probability intervals contract as alpha increases | yes |
| CRN identity | Seeded executable Gaussian fixture | Same sample identities across alpha levels and endpoints | yes |
| Baudrit-style reporting discipline | Finite hybrid toy | Alpha-indexed lower/upper bounds only; no defuzzified answer | yes |
| Output-error ordering | Synthetic loading trajectories with endpoint envelopes | Error endpoints act before event detection; probabilities are not shifted | yes |
| Output-error CRN identity | Alpha-indexed synthetic loading samples with explicit sample IDs | Same ordered sample identities are preserved across alpha levels | yes |
| Synthetic monotonicity sweep | Boolean toy event indicators over a rho grid | Probabilities are ordered, local violations are reported, and no G3 verdict is emitted | yes |
| Bootstrap-CI helper | Explicit synthetic resample-index fixtures | Rank-bootstrap interval endpoints are deterministic and hand-computable | yes |

## Remaining Dependencies

- G3 remains pending; vertex propagation is not authorized for paper-facing results until G3 records the applicable monotonicity verdict.
- Q-5 is resolved by G0-A3, but this synthetic trust certificate does not use the real project threshold protocol.
- G2 and A-013 remain unresolved for numerical Tier-1/grid-error values.
- Capacity denominator and provenance remain unresolved for paper-facing model-error propagation.
