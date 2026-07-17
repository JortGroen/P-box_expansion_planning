> **Provenance:** AI-generated research report supplied by the PI on
> 2026-07-17 from
> `C:/Users/jortgroen/Downloads/ev_home_charge_profile_pool_size_methodology_report.md`.
> Original SHA-256:
> `91AA3A2BB2CA489B2B6B656F80496D54D993FF582F16CA7C7178A47B323ED57E`.
>
> **Status:** Advisory research note only. It does not amend EV-003, EV-004,
> EV-005, ALEA-001, ALEA-002, or any approved sample-size protocol. Numerical
> rules and independence claims in the supplied text require evidence and PI
> sign-off before use.

## Project Review

### Useful Later

- The distinction between finite-library size `M` and downstream Monte Carlo
  count `N`, complete-trajectory resampling, nested library sizes, common random
  numbers, and full-model confirmation agrees with EV-005.
- The identity `M(1-p)` is a useful descriptive warning about how few source
  members occupy an individual-profile tail. It is not a sample-size formula
  for the downstream transformer statistic.
- Caching profile contributions, multinomial/count-based aggregation, and
  multi-fidelity screening may become useful if the integrated evaluator is
  more expensive than expected.
- A move from p95 diagnostics to p99/p99.9 would require a fresh tail-adequacy
  design. The report's warning that ordinary bootstrap cannot invent missing
  behavior supports the existing held-out and escalation rules.

### Do Not Adopt Without Further Evidence

- The report cites no statistical sources. Its `0.1` Monte Carlo-to-pool error
  ratio, tail counts `k = 20/50`, pool doubling rule, and decision-change
  probability are unsupported design heuristics rather than derived criteria.
- It assumes individual profiles returned by the API are independent. Until
  ElaadNL multi-profile seed semantics are resolved, EV-005 correctly treats a
  complete API batch as the resampling and leave-out unit.
- Profile-only adequacy is not sufficient for this project, even in the
  report's additive/independent case. ALEA-002 requires final acceptance after
  baseline, EV, HP, PV, adoption, flexibility, net load, and transformer-event
  evaluation.
- A common calendar is required, but the project must not invent an EV-weather
  pairing or conditional dependence that the source data do not identify.
- The final scientific target is the signed annual overload event probability
  `P(E)`. Downstream p95 is currently a convergence diagnostic, so selecting a
  library solely for the "most demanding quantile" would answer the wrong
  question.
- The planned `M = 1000` candidate plus `H = 200` held-out members cannot by
  itself establish an `M` versus `2M` result. A true doubling comparison becomes
  available only if the sequential protocol authorizes additional generation.

The supplied report follows unchanged below.

---

# Determining the Required Pool Size for EV Home Charge Profiles

## 1. Purpose

This report defines a methodology for determining the required size of a reusable pool of annual EV home charge profiles obtained through the Elaad API.

Each draw from the Elaad API is assumed to return one complete annual EV home charge profile with a temporal resolution of 15 minutes. A non-leap year therefore contains

\[
T = 365 \times 24 \times 4 = 35{,}040
\]

time steps.

The objective is to use a finite pool of independently generated annual EV home charge profiles to populate multiple input dimensions in a Monte Carlo simulation. The required pool size depends on:

1. the computational cost of uncertainty propagation;
2. the degree of linearity of the model;
3. the dependence between the EV home charge profile uncertainty and other uncertainties;
4. the output quantile of interest, such as p95, p99, or p99.9.

The methodology distinguishes between:

- \(X\): the uncertainty represented by annual EV home charge profiles sampled from the pool;
- \(U\): all other uncertain inputs or model parameters;
- \(Y\): the model output.

The general model is written as

\[
Y = g(X,U).
\]

The output of interest is a high quantile of \(Y\), denoted by

\[
q_p(Y),
\]

where \(p\) may be \(0.95\), \(0.99\), or \(0.999\).

---

## 2. Pool-based sampling of annual profiles

Let

\[
\mathbf Z_m =
\left(
Z_m(1),\ldots,Z_m(T)
\right)
\]

denote the \(m\)-th annual EV home charge profile obtained from the Elaad API.

A pool of size \(M\) is

\[
\mathcal P_M =
\left\{
\mathbf Z_1,\ldots,\mathbf Z_M
\right\}.
\]

The corresponding empirical distribution is

\[
\widehat F_M
=
\frac{1}{M}
\sum_{m=1}^{M}
\delta_{\mathbf Z_m}.
\]

For a Monte Carlo realization with \(d\) EV home charge profiles, one annual trajectory is selected for each dimension:

\[
I_j \sim \operatorname{Uniform}\{1,\ldots,M\},
\qquad
X_j = \mathbf Z_{I_j}.
\]

The annual profiles must be resampled as complete trajectories. The 15-minute values should not be sampled independently because this would destroy:

- temporal autocorrelation;
- daily charging patterns;
- weekday and weekend structure;
- seasonal variation;
- the timing and duration of charging peaks.

Increasing the number of Monte Carlo realizations improves the numerical approximation under \(\widehat F_M\), but it does not add information about the true profile distribution. Only increasing \(M\) introduces additional independent annual EV home charge profiles.

---

## 3. Factors governing the pool-size strategy

The appropriate pool-size determination method depends on three binary characteristics.

### 3.1 Propagation cost

- **1a: Very cheap propagation**
  Large Monte Carlo samples, repeated bootstraps, and repeated analyses for several pool sizes are computationally feasible.

- **1b: Slightly more expensive propagation**
  Repeated full-model evaluations remain possible but should be reduced using caching, precomputation, surrogate models, or multi-fidelity analysis.

### 3.2 Model structure

- **2a: Simple sum**
  The model can be represented approximately as

  \[
  Y = g_X(X)+g_U(U)+c.
  \]

  The contribution of the EV home charge profiles can therefore be evaluated separately.

- **2b: Quite linear but not perfect**
  The model is approximately additive but includes weak interactions or mild nonlinearities:

  \[
  Y =
  g_X(X)+g_U(U)+r(X,U),
  \]

  where \(r(X,U)\) is expected to be small but may still affect the upper tail.

### 3.3 Dependence between uncertainties

- **3a: Fully independent**
  The EV home charge profile uncertainty \(X\) is independent of \(U\).

- **3b: Weak dependence**
  A limited dependence exists between \(X\) and \(U\), for example through weather, season, charging behaviour, tariff structure, calendar effects, or scenario assumptions.

---

## 4. Complete decision matrix

| Propagation cost | Model | Relation between \(X\) and \(U\) | Pool-size determination | Final verification | Methodological assessment |
|---|---|---|---|---|---|
| **1a: Very cheap** | **2a: Simple sum** | **3a: Independent** | Determine \(M\) using the propagated EV home charge profile contribution \(V=g_X(X)\) alone. For each candidate \(M\), use a very large number of profile combinations and bootstrap complete annual profiles. Evaluate convergence of the target quantile and the CDF around that quantile. | Run the full Monte Carlo analysis once with the selected \(M^\star\). Perform a limited comparison between \(M^\star\) and \(2M^\star\). | This is the strongest case for separate pool-size determination. Adding independent uncertainty through an additive model will not normally amplify CDF approximation error. |
| **1a: Very cheap** | **2a: Simple sum** | **3b: Weak dependence** | Preserve the dependence between the annual EV home charge profile and \(U\). Use paired, conditional, or stratified resampling. Determine \(M\) using the combined quantity \(g_X(X)+g_U(U)\), not using \(g_X(X)\) alone. | Compare the dependence-preserving analysis with an independence sensitivity case. Repeat the \(M^\star\) versus \(2M^\star\) comparison for the final quantile. | The model contributions may be evaluated separately, but the samples should not be combined independently unless the dependence has been represented explicitly. |
| **1a: Very cheap** | **2b: Quite linear** | **3a: Independent** | Use the EV home charge profile contribution alone as an initial screen. Then evaluate all plausible candidate pool sizes under the full \(X,U\) uncertainty model. Use common random numbers across pool sizes. | Select \(M^\star\) based on convergence of the full-output quantile. Confirm with \(2M^\star\). | Because propagation is cheap, the final pool size should be determined using the actual full model rather than relying only on approximate linearity. |
| **1a: Very cheap** | **2b: Quite linear** | **3b: Weak dependence** | Conduct the pool-size study directly under the full joint or conditional uncertainty model. Bootstrap dependence-preserving units, such as profile–scenario pairs or profile–driver blocks. | Perform full \(M^\star\) versus \(2M^\star\) validation and an independence sensitivity analysis. | This is the most rigorous option when propagation is cheap. Profile-only determination should not be used as the final justification. |
| **1b: Slightly more expensive** | **2a: Simple sum** | **3a: Independent** | Precompute or cache \(g_X(\mathbf Z_m)\) for every EV home charge profile in the pool. Determine \(M\) from the cached contributions through bootstrap and large-scale local recombination. Combine the profile and other uncertainty contributions by sample addition or convolution. | Evaluate selected full-model cases only. Compare \(M^\star\) and \(2M^\star\) using identical \(U\) samples. | Efficient and well justified. The additive structure should be exploited to avoid repeated full-model evaluations. |
| **1b: Slightly more expensive** | **2a: Simple sum** | **3b: Weak dependence** | Precompute profile responses within dependence strata or conditional states. For example, cache \(g_X(\mathbf Z_m\mid C)\), where \(C\) is a weather, scenario, tariff, or calendar class. Use conditional or stratified bootstrap. | Validate \(M^\star\) and \(2M^\star\) for the conditional states that contribute most strongly to the upper tail. | Efficient when the weak dependence can be represented by a small number of conditioning variables. |
| **1b: Slightly more expensive** | **2b: Quite linear** | **3a: Independent** | Use a linear approximation or inexpensive surrogate to screen candidate pool sizes. Apply the full model only at selected sizes, such as \(M^\star/2\), \(M^\star\), and \(2M^\star\). Use common random numbers. | Confirm the final quantile using the actual model at \(M^\star\) and \(2M^\star\). Allocate additional runs around the target quantile. | A multi-fidelity strategy is appropriate. Separate determination is useful for screening, but the final choice should use the actual model. |
| **1b: Slightly more expensive** | **2b: Quite linear** | **3b: Weak dependence** | Use a dependence-preserving surrogate or multi-fidelity model. Screen candidate pool sizes with the surrogate while retaining paired or conditional \(X,U\) samples. Allocate expensive evaluations adaptively near the upper-tail region. | Full-model confirmation at \(M^\star\) and \(2M^\star\) is essential. Test sensitivity to the assumed dependence model. | This is the most demanding case. A profile-only study is suitable only as a preliminary screening step. |

---

## 5. Condensed decision rules

| Situation | Can the pool size be determined from the EV home charge profiles alone? |
|---|---|
| Simple sum and independence | **Yes** |
| Simple sum and weak dependence | **Only conditionally**, with dependence-preserving sampling |
| Nearly linear, independent, and very cheap propagation | Only as an initial screen; use the full output for the final choice |
| Nearly linear, independent, and somewhat more expensive propagation | Use linear or surrogate screening followed by full-model confirmation |
| Nearly linear with weak dependence | Generally **no**, except as a preliminary screening step |

---

## 6. Why the target quantile matters

The required pool size depends strongly on whether the final analysis concerns p95, p99, or p99.9.

For a target quantile \(p\), the probability mass above the quantile is

\[
1-p.
\]

A pool containing \(M\) independently generated annual EV home charge profiles contains, on average,

\[
M(1-p)
\]

profiles in the corresponding upper-tail region.

| Target quantile | Upper-tail probability | Expected number of pool profiles in the upper tail |
|---:|---:|---:|
| p95 | \(0.05\) | \(0.05M\) |
| p99 | \(0.01\) | \(0.01M\) |
| p99.9 | \(0.001\) | \(0.001M\) |

Examples are shown below.

| Pool size \(M\) | Expected profiles above p95 | Expected profiles above p99 | Expected profiles above p99.9 |
|---:|---:|---:|---:|
| 200 | 10 | 2 | 0.2 |
| 500 | 25 | 5 | 0.5 |
| 1,000 | 50 | 10 | 1 |
| 2,000 | 100 | 20 | 2 |
| 5,000 | 250 | 50 | 5 |
| 20,000 | 1,000 | 200 | 20 |

These values are diagnostic rather than formal sample-size requirements. The p99 or p99.9 of the final aggregated output does not necessarily correspond directly to the same quantile of an individual EV home charge profile. Nevertheless, the table indicates how little direct empirical information a small pool contains about very high quantiles.

---

## 7. Indicative tail-coverage requirements

Suppose at least \(k\) expected annual EV home charge profiles are required in the relevant upper-tail region. Then

\[
M \geq \frac{k}{1-p}.
\]

For \(k=20\):

| Quantile | Indicative minimum \(M\) |
|---:|---:|
| p95 | 400 |
| p99 | 2,000 |
| p99.9 | 20,000 |

For \(k=50\):

| Quantile | Indicative minimum \(M\) |
|---:|---:|
| p95 | 1,000 |
| p99 | 5,000 |
| p99.9 | 50,000 |

These values should not be interpreted as universal minimum pool sizes. They indicate the order of magnitude required for direct, nonparametric representation of increasingly rare annual profile behaviour.

A pool that is sufficient for p95 may be inadequate for p99 and is likely to be inadequate for p99.9 unless the final system output is substantially smoothed through aggregation or other uncertainty contributions.

---

## 8. Recommended method by target quantile

| Target quantile | Recommended approach |
|---|---|
| **p95** | Use trajectory-level bootstrap and sequential pool-size doubling. Compare \(q_{0.95,M}\) with \(q_{0.95,2M}\). Standard nonparametric pool construction may be sufficient. |
| **p99** | Add explicit upper-tail coverage diagnostics. Use bootstrap together with subsampling from a larger master pool where possible. Apply stricter \(M\) versus \(2M\) stability criteria. |
| **p99.9** | A purely empirical pool may require thousands or tens of thousands of independent annual profiles. Consider targeted profile generation, stratification, importance sampling, or a justified tail model. Ordinary bootstrap cannot generate extreme profile types that are absent from the original pool. |

---

## 9. Pool-size determination procedure

### 9.1 Candidate pool sizes

Use a sequential sequence such as

\[
M \in
\{50,100,200,400,800,\ldots\}.
\]

If sampling without replacement is required within a Monte Carlo realization, the implementation additionally requires

\[
M \geq d,
\]

where \(d\) is the number of EV home charge profiles used simultaneously. This is an implementation constraint, not a statistical sufficiency criterion.

### 9.2 Bootstrap complete annual profiles

For each candidate \(M\), construct bootstrap pools

\[
\mathcal P_M^{(b)}
=
\left\{
\mathbf Z_{I_1^{(b)}},\ldots,
\mathbf Z_{I_M^{(b)}}
\right\},
\]

where complete annual EV home charge profiles are sampled with replacement.

For each bootstrap pool, propagate a large number of profile combinations and estimate the target quantile:

\[
\widehat q_{p,M}^{(b)}.
\]

The spread of

\[
\widehat q_{p,M}^{(1)},\ldots,
\widehat q_{p,M}^{(B)}
\]

estimates the uncertainty caused by the finite pool.

### 9.3 Make propagation error negligible

Because propagation is assumed to be cheap or moderately cheap, the number of downstream Monte Carlo samples \(N\) should be selected so that

\[
\operatorname{SE}_{\mathrm{MC}}
\ll
\operatorname{SE}_{\mathrm{pool}}.
\]

A practical criterion is

\[
\operatorname{SE}_{\mathrm{MC}}
\leq
0.1\operatorname{SE}_{\mathrm{pool}}.
\]

Common random numbers should be used when comparing pool sizes. The same random selections of \(U\) and the same local sampling uniforms should be reused, where possible, so that differences are primarily caused by the pool size.

---

## 10. Recommended stopping criteria

Retain the smallest pool size \(M^\star\) that satisfies all of the following criteria.

### 10.1 Quantile stability

\[
\left|
\widehat q_{p,2M}
-
\widehat q_{p,M}
\right|
\leq
\varepsilon_q.
\]

The tolerance \(\varepsilon_q\) should be expressed in a physically meaningful output unit.

### 10.2 Bootstrap uncertainty

\[
\text{bootstrap half-width for }
\widehat q_{p,M}
\leq
\varepsilon_{\mathrm{pool}}.
\]

### 10.3 Negligible downstream Monte Carlo error

\[
\operatorname{SE}_{\mathrm{MC}}
\leq
0.1\operatorname{SE}_{\mathrm{pool}}.
\]

### 10.4 Decision stability

If the quantile is used for a planning or reinforcement decision, require

\[
P(
\text{decision changes under pool resampling}
)
\leq
\alpha_{\mathrm{decision}}.
\]

Typical output-specific tolerances may be expressed in:

- kW or MW;
- percentage transformer loading;
- hours of overload;
- probability of exceeding a planning threshold;
- change in the selected reinforcement decision.

---

## 11. Recommended workflow

A practical workflow is as follows.

1. Generate an initial master pool of annual EV home charge profiles through the Elaad API.
2. Evaluate candidate pool sizes using nested subsets or repeated subsamples.
3. Propagate complete annual profiles while preserving their 15-minute temporal structure.
4. Evaluate p95, p99, and p99.9 simultaneously during the pool-size study.
5. Use profile-only determination as the final method only when the model is a simple additive sum and \(X\) and \(U\) are independent.
6. When propagation is cheap, evaluate candidate pool sizes directly under the complete uncertainty model.
7. When propagation is more expensive, use caching, precomputation, linear approximations, or surrogate models for screening.
8. Preserve weak dependence through conditional, paired, or stratified resampling.
9. Select \(M^\star\) based on bootstrap uncertainty, \(M\)-versus-\(2M\) convergence, and decision stability.
10. Perform a final confirmation using \(2M^\star\), particularly when p99 or p99.9 is reported.

---

## 12. Main methodological recommendation

The pool size should be selected for the most demanding quantile that may reasonably be used in the final study.

If p95 is used for pool-size calibration and the study later changes to p99 or p99.9, the pool-size assessment should be repeated. A pool that adequately represents central and moderately high output quantiles may still contain insufficient information about rare annual EV home charge profile behaviour.

For the strongest methodological justification:

- use complete annual EV home charge profiles from the Elaad API as the statistical sampling units;
- make downstream Monte Carlo error negligible;
- determine pool size from the propagated output quantile rather than from profile-level summary statistics alone;
- preserve any dependence between the EV home charge profiles and other uncertainties;
- confirm the selected pool size using a larger pool;
- report p95, p99, and p99.9 convergence separately.

---

## 13. Suggested manuscript wording

> A finite library of annual EV home charge profiles was generated through the Elaad API. Each profile comprised one full year at 15-minute resolution and was treated as one independent trajectory-level observation. The required library size was determined sequentially by evaluating increasing pool sizes and quantifying pool-induced uncertainty through trajectory-level resampling. Downstream Monte Carlo sampling was made sufficiently large for numerical propagation error to be negligible relative to finite-pool uncertainty. Pool adequacy was assessed using convergence of the p95, p99, and p99.9 output quantiles, bootstrap uncertainty intervals, and stability under pool-size doubling. Dependence between the EV home charge profiles and other uncertain inputs was retained through conditional or paired sampling where applicable.
