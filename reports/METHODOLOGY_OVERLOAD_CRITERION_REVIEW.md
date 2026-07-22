# Review of the Proposed Overload-Criterion Methodology

**Reviewed document:** `methodology_overload_criterion.md`  
**Review date:** 2026-07-20  
**Status:** Review advice; not an approved project decision

## Overall assessment

The proposal has a strong central direction, but it should not be adopted
unchanged. The following choices are supported:

- Use loading strictly above `1.0 p.u.` as the primary overload threshold.
- Retain `1.1 p.u.` and `1.2 p.u.` as predeclared sensitivity thresholds.
- Keep `P_crit = 10^-2` as the primary probability threshold and `10^-3` as a
  sensitivity.
- Interpret loading above nameplate as congestion, rather than as immediate
  transformer failure.

This is more defensible than retaining the currently provisional `1.1 p.u.`
primary threshold without a verified source, and it provides a credible route
for resolving Q-5. The Monte Carlo section nevertheless requires substantial
revision before it becomes project policy or manuscript text.

## Required corrections

### 1. Preserve the one-hour event definition

The proposal writes the event as `E = {S > S_n}`, which can be read as a
single-step exceedance. The project event is the occurrence of at least four
consecutive 15-minute import-direction loading values above the threshold.

Define the annual persistence statistic as

\[
Y = \max_t \min\{L_{\mathrm{import}}(t),
                  L_{\mathrm{import}}(t+1),
                  L_{\mathrm{import}}(t+2),
                  L_{\mathrm{import}}(t+3)\}.
\]

The event at threshold `tau` is then

\[
E_\tau = \{Y > \tau\}.
\]

This definition exactly represents four consecutive 15-minute exceedances.
Because non-import intervals have zero import loading, a direction change also
resets the episode. Any probability-quantile equivalence must refer to this
annual episode statistic `Y`, not to an ambiguously defined annual loading.

### 2. Remove the two-route stopping rule

For a fixed threshold, probability and quantile certification are equivalent:

\[
P(Y > \tau) \leq P_{\mathrm{crit}}
\quad\Longleftrightarrow\quad
Q_Y(1-P_{\mathrm{crit}}) \leq \tau.
\]

The exceedance count is the empirical distribution function evaluated at the
threshold. The probability and quantile routes therefore do not supply two
independent sources of information. Stopping when either route certifies does
not provide a principled speed advantage and complicates error control.

Use the Bernoulli exceedance probability as the primary decision estimator.
Quantiles may still be reported as descriptive outputs.

### 3. Choose fixed-sample or genuinely sequential inference

Clopper-Pearson intervals are exact for a fixed sample size, but ordinary
Clopper-Pearson intervals are not anytime-valid when repeatedly inspected. The
proposal currently combines fixed-sample exact intervals with optional
stopping as though they were one procedure.

For the first complete analysis, the recommended approach is:

- Run the frozen `N = 10^4` primary analysis.
- Calculate Clopper-Pearson intervals at the final sample size.
- Use `N = 10^5` for the later `P_crit = 10^-3` sensitivity.
- Introduce sequential stopping only if a compute benchmark demonstrates that
  its added complexity produces worthwhile savings.

If early stopping is later implemented, it must use a genuine Bernoulli
confidence sequence or a predeclared group-sequential procedure with controlled
error spending. Repeated checks of `z * SE` are not sufficient.

### 4. Correct the sample-size interpretation

At the relevant probability thresholds:

- `N = 10^4` at `p = 0.01` gives approximately 10% relative standard error.
- `N = 10^5` at `p = 0.001` gives approximately 10% relative standard error.

These correspond to approximately a +/-20% relative 95% interval, not
"+/-10% accuracy." Approximately +/-10% relative precision at 95% confidence
would require roughly:

- 38,000 samples at `p = 0.01`;
- 384,000 samples at `p = 0.001`.

The existing budgets may remain as computational design choices, but their
precision must be described accurately.

### 5. Narrow the IEC claim

The statement that IEC 60076-7 permits `1.5 p.u.` normal cyclic loading and
`1.8 p.u.` emergency loading is too general for the project transformer. The
standard treats operation above nameplate as conditional on transformer type,
ambient temperature, hot-spot temperature, thermal ageing, and operating
circumstances. It is not blanket permission to operate the case-study HV/MV
transformer bank at those values.

A defensible statement is:

> Exceeding nameplate is not automatically an asset failure; its consequences
> depend on the applicable transformer design, thermal conditions, and ageing.

The exact IEC loading category applicable to the decision transformer should be
verified before quoting numerical cyclic or emergency limits.

### 6. Demote importance sampling

Betge et al. found cross-entropy importance sampling useful primarily for
assets serving fewer than roughly 50-80 customers. That result does not by
itself establish applicability to this project's aggregated, dependent,
full-year profile model.

Importance sampling should remain a conditional future optimization. It should
be considered only if conventional Monte Carlo is shown to be a material
computational bottleneck, and it must then be validated against conventional
Monte Carlo or analytically checkable cases with correct likelihood weighting.

### 7. Do not freeze the proposed indifference zone

An unresolved or monitor outcome is scientifically sensible when sampling
uncertainty prevents a decision. However, the proposed `delta = 0.5`, producing
the interval `[0.005, 0.015]` around `P_crit = 0.01`, is not yet justified.

Keep the indifference-zone width open until it can be tied to decision
consequences, a declared computational budget, or another defensible protocol.
Monte Carlo inconclusiveness and epistemic overlap of the p-box bounds should
also remain distinguishable in the reported results.

### 8. State p-box decision certification explicitly

For each alpha level, the project should distinguish the following outcomes:

- **Deferral certified:** the sampling upper confidence limit for the upper
  overload-probability bound is below `P_crit`.
- **Reinforcement certified:** the sampling lower confidence limit for the
  lower overload-probability bound is above `P_crit`.
- **Epistemically ambiguous:** the lower and upper p-box probabilities fall on
  different sides of `P_crit` after sampling uncertainty is controlled.
- **Sampling unresolved:** the available simulation budget cannot confidently
  locate the relevant probability bound relative to `P_crit`.

The manuscript must state whether confidence guarantees are marginal for each
reported bound or simultaneous across alpha levels, endpoints, and scenarios.

## Recommended project decision

Amend G0-A3 as follows:

1. Define the primary event as strict `L_import > 1.0 p.u.` for four
   consecutive 15-minute steps in the full planning year.
2. Retain the same persistent event at `1.1 p.u.` and `1.2 p.u.` as
   predeclared sensitivities, to be run after the first complete analysis.
3. Retain the single-step event as a separate sensitivity.
4. Keep `P_crit` unchanged and prohibit selecting the threshold that produces
   the most interesting result.
5. Use final-sample Clopper-Pearson intervals for the first analysis.
6. Defer sequential stopping, the indifference-zone width, and importance
   sampling until their need and implementation have been separately approved.

The threshold recommendation is suitable for adoption after formal PI approval.
The proposed Monte Carlo methodology is not yet suitable for adoption without
the corrections above.

## Sources checked

- IEC, *IEC 60076-7:2018 - Loading guide for mineral-oil-immersed power
  transformers*: https://webstore.iec.ch/en/publication/34351
- Betge, Droste, Heres, and Tindemans (2021), *Efficient Assessment of
  Electricity Distribution Network Adequacy with the Cross-Entropy Method*:
  https://doi.org/10.1109/PowerTech46648.2021.9494891
- Howard, Ramdas, McAuliffe, and Sekhon (2021), *Time-uniform, nonparametric,
  nonasymptotic confidence sequences*:
  https://doi.org/10.1214/20-AOS1991
- Howard and Ramdas (2022), *Sequential estimation of quantiles with
  applications to A/B testing and best-arm identification*:
  https://doi.org/10.3150/21-BEJ1388
