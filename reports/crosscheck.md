# E5.S4 Independent Cross-Check Plan

Status: scaffold-only plan for the p-box/math-core trust certificate. This
report designs synthetic checks only. It does not run integrated net load,
resolve Q-5, introduce signed A-013 values, produce paper results, or provide
manuscript numbers.

## Purpose

E5.S4 is the trust-certificate step for the uncertainty and decision math
core. Before any paper-facing p-box result is produced, the implementation
must pass:

1. an analytic toy case with a closed-form `P(E | rho)` that the p-box
   propagation can reproduce to the E5.S4 tolerance; and
2. a qualitative Baudrit-style hybrid-propagation cross-check showing that the
   code preserves aleatory/epistemic separation, reports alpha-indexed bounds,
   and does not collapse the result to one defuzzified probability.

## Cross-Check 1: Analytic Gaussian Toy Case

### Synthetic Model

Use a one-step synthetic loading variable

```text
L(rho) = mu_0 - beta * rho + sigma * Z,
Z ~ Normal(0, 1),
```

where `rho` is the fuzzy controllability parameter and larger `rho` reduces
loading. The event for this trust-certificate toy is the synthetic single-step
event

```text
E_toy(rho): L(rho) > c_toy.
```

This is not the project overload event and must not be mixed with Q-5 or the
integrated four-step import event. The toy deliberately uses a closed-form
single-step event so the expected probability is auditable by hand:

```text
P(E_toy | rho) = 1 - Phi((c_toy - mu_0 + beta * rho) / sigma),
```

with `Phi` the standard-normal CDF.

### P-Box Expectation

For any alpha-cut `[rho_lo(alpha), rho_up(alpha)]`, `P(E_toy | rho)` is
monotone decreasing in `rho` when `beta > 0`. Therefore:

```text
P_lower(alpha) = P(E_toy | rho_up(alpha))
P_upper(alpha) = P(E_toy | rho_lo(alpha)).
```

The acceptance test should compare implemented p-box endpoint estimates
against these closed-form values and require absolute error below 0.01. The
comparison is a synthetic math-core certificate only; it is not evidence about
the real feeder, threshold, capacity convention, or model-error magnitude.

### Randomness And Reproducibility

The random variable is only `Z`. A future executable version may use a fixed
deterministic quadrature or a seeded Monte Carlo draw from the canonical
RNG-001 sample tree. If Monte Carlo is used, the same sample identities must be
replayed for every alpha level and rho endpoint. The closed-form values above
remain the oracle.

## Cross-Check 2: Baudrit-Style Hybrid Propagation

This Baudrit-style hybrid propagation check is qualitative until a primary
citation fixture is approved for executable reproduction.

The qualitative cross-check should reproduce the behavior expected from
hybrid propagation of aleatory and epistemic uncertainty:

- each alpha-cut of the fuzzy input produces a lower/upper probability interval;
- intervals are nested as alpha increases;
- no scalar defuzzified probability is reported as the answer;
- aleatory uncertainty stays in probabilities or confidence intervals, while
  epistemic uncertainty stays in alpha-indexed bounds;
- output-domain model-error endpoints, when included, widen loading
  trajectories before event detection rather than shifting probabilities after
  estimation;
- lower and upper events produce separate counts, probabilities, and
  confidence intervals.

For a synthetic decreasing event model, the Baudrit-style qualitative fixture
can use the same fuzzy `rho` alpha-cuts as the Gaussian toy. The expected shape
is nested probability intervals that contract from the fuzzy support to the
core. A future written comparison should cite the approved project citation
base before calling it a published-example reproduction; until then this is a
qualitative scaffold, not a citation claim.

## Planned Acceptance Matrix

| Check | Synthetic Fixture | Expected Outcome | Blocks Paper Results If Failing |
|---|---|---|---|
| Closed-form Gaussian endpoint values | `L(rho)=mu_0-beta*rho+sigma Z` and single-step `E_toy` | Endpoint p-box probabilities match closed form within 0.01 absolute error | yes |
| Monotone endpoint selection | Same Gaussian fixture with `beta > 0` | Lower endpoint uses `rho_up`; upper endpoint uses `rho_lo` | yes |
| Nested alpha intervals | Trapezoidal fuzzy `rho` with multiple alpha levels | Probability intervals contract as alpha increases | yes |
| CRN identity | Seeded executable version of the Gaussian fixture | Same sample identities across alpha levels and endpoints | yes |
| Baudrit-style reporting discipline | Qualitative hybrid fixture | Alpha-indexed lower/upper bounds only; no defuzzified answer | yes |
| Output-error ordering | Synthetic loading trajectories with endpoint envelopes | Error endpoints act before event detection; probabilities are not shifted | yes |

## Executable Synthetic Scaffold

The first executable synthetic scaffold implements only the Gaussian toy comparison. It
uses deterministic normal quantiles indexed by canonical `sample_seed(root_seed,
sample_index)` identities, then routes those synthetic event indicators through
the existing p-box endpoint pathway. The acceptance criterion is the planned
0.01 absolute-error tolerance against the closed-form endpoint values. This is
still synthetic trust-certificate machinery only: it does not use real net-load
data, the project overload event, Q-5 threshold evidence, signed A-013 values,
or manuscript numbers.

## Remaining Dependencies

- G3 remains pending; vertex propagation is not authorized for paper-facing
  results until G3 records the applicable monotonicity verdict.
- Q-5 remains open and blocks integrated event-based scientific analysis.
- G2 and A-013 remain unresolved for numerical Tier-1/grid-error values.
- Capacity denominator and provenance remain unresolved for paper-facing
  model-error propagation.
