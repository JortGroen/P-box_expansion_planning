# E5.S4 Independent Cross-Check Plan

Status: scaffold-only plan and executable synthetic package for the p-box/math-core trust certificate. This report designs and records synthetic checks only. It does not run integrated net load, resolve Q-5, introduce signed A-013 values, produce paper results, or provide manuscript numbers.

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

This is not the project overload event and must not be mixed with Q-5 or the integrated four-step import event. The toy deliberately uses a closed-form single-step event so the expected probability is auditable by hand:

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

## Executable Synthetic Package

The E5.S4 package lives in `src/pbox_crosscheck.py` with tests in `tests/test_pbox_crosscheck.py`.

- `GaussianToyParameters`, `gaussian_tail_probability`, and `gaussian_closed_form_bounds` provide the analytic oracle.
- `estimate_gaussian_toy_pbox` routes the Gaussian toy through the existing p-box endpoint pathway using canonical RNG sample identities and `PRE_G3_SYNTHETIC` mode.
- `FiniteHybridState` and `finite_hybrid_bounds` provide a small qualitative hybrid/p-box fixture with exact hand-summed lower/upper event probabilities.

This executable synthetic package does not use real net-load data, the project overload event, Q-5 threshold evidence, signed A-013 values, G3 vertex authorization for paper-facing results, or manuscript numbers.

## Planned Acceptance Matrix

| Check | Synthetic Fixture | Expected Outcome | Blocks Paper Results If Failing |
|---|---|---|---|
| Closed-form Gaussian endpoint values | `L(rho)=mu_0-beta*rho+sigma Z` and single-step `E_toy` | Endpoint p-box probabilities match closed form within 0.01 absolute error | yes |
| Monotone endpoint selection | Same Gaussian fixture with `beta > 0` | Lower endpoint uses `rho_up`; upper endpoint uses `rho_lo` | yes |
| Nested alpha intervals | Trapezoidal fuzzy `rho` with multiple alpha levels | Probability intervals contract as alpha increases | yes |
| CRN identity | Seeded executable Gaussian fixture | Same sample identities across alpha levels and endpoints | yes |
| Baudrit-style reporting discipline | Finite hybrid toy | Alpha-indexed lower/upper bounds only; no defuzzified answer | yes |
| Output-error ordering | Synthetic loading trajectories with endpoint envelopes | Error endpoints act before event detection; probabilities are not shifted | yes |

## Remaining Dependencies

- G3 remains pending; vertex propagation is not authorized for paper-facing results until G3 records the applicable monotonicity verdict.
- Q-5 remains open and blocks integrated event-based scientific analysis.
- G2 and A-013 remain unresolved for numerical Tier-1/grid-error values.
- Capacity denominator and provenance remain unresolved for paper-facing model-error propagation.
