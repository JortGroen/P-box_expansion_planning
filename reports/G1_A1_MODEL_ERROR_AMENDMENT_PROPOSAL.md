# G1-A1 - Amendment: Black-Box Model Error and Tier-1 Approximation

> **Superseded in part (2026-07-14):** G1-A2 replaces the earlier expert-
> provenance wording, fixed applicability-domain examples, and simple additive
> composition when `epsilon_grid` is relative and Tier-1 error is
> additive. The approved current protocol is
> `reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md`. This file is retained as
> the historical G1-A1 rationale.

**Date:** 2026-07-13

**Status:** approved by the PI in chat and mirrored into `registers/DECISIONS.md`

**Amends:** G1 compute architecture, G2 tier-equivalence gate, E5.S3 model-error widening, and the IC-2/IC-3 behavioral boundary

**G1-A2 status:** symmetry and relative form for `epsilon_grid` are now frozen;
its numerical values remain proposed. G2 still determines the additive Tier-1
endpoints.

## 1. Reason for the Amendment

The scientific story originally introduced an interval `+-epsilon_grid` for
the output error of the pandapower grid model, which is treated as a black box.
This project has no field measurements that empirically validate the DSO model
against physical loading. `epsilon_grid` is therefore author-specified unless
later evidence or human review supplies a stronger provenance. It must be
carried in `ASSUMPTIONS.md` with a mandatory sensitivity sweep and an explicit
asserted domain. Any future empirical validation must be recorded together
with its validated domain.
Tier-1 radial summation was introduced later as a fast approximation to
pandapower for the Monte Carlo inner loop; `epsilon_Tier1`, unlike
`epsilon_grid`, can be determined empirically within this project.

The current E5.S3 proposal widens already estimated overload probabilities by
fixed additive probability margins. That is not the same uncertainty. An
interval on grid-model output must be applied to the loading output before the
four-consecutive-step overload event is classified. Its effect on event
probability is then obtained through the Monte Carlo ensemble and may be highly
nonlinear near the 1.0 p.u. threshold.

## 2. Black-Box Error Model, As Amended by G1-A2

Let:

- `X` denote all aleatory inputs;
- `rho` denote flexibility controllability;
- `t` denote a 15-minute timestep;
- `L_true(X, rho, t)` denote the unknown real loading quantity used by the
  overload event;
- `L_PP(X, rho, t)` denote the corresponding pandapower output; and
- `L_T1(X, rho, t)` denote the Tier-1 output.

The symmetric relative grid-model envelope is

```text
(1 - epsilon_grid) * L_PP <= L_true <= (1 + epsilon_grid) * L_PP
```

The Tier-1 approximation discrepancy is

```text
delta_Tier1(X, rho, t) = L_PP(X, rho, t) - L_T1(X, rho, t)
delta_Tier1(X, rho, t) in [-epsilon_Tier1, +epsilon_Tier1]
```

Neither discrepancy is assigned a probability distribution. In particular,
neither error is sampled independently for each Monte Carlo realization.
Because their dependence on `X`, `rho`, time, and each other is unknown, the
analysis admits every discrepancy function that remains inside its applicable
envelope. For `epsilon_grid`, that envelope and its asserted domain come from
A-013 once signed; for `epsilon_Tier1`, they come from the G2 validation.
This is arbitrary or unknown dependence, not an assumption of probabilistic
independence and not an assumption of one constant bias.

G1-A2 composes the relative grid envelope with additive Tier-1 endpoints as

```text
L_PP_lower = max(0, L_T1 - epsilon_Tier1_minus)
L_PP_upper = L_T1 + epsilon_Tier1_plus
L_true_lower = (1 - epsilon_grid) * L_PP_lower
L_true_upper = (1 + epsilon_grid) * L_PP_upper
```

This is conservative under unknown dependence because it allows both errors to
attain their adverse endpoints together. If G2 establishes an asymmetric or
one-sided Tier-1 discrepancy, its separate endpoints are retained.

## 3. Proposed Event and Probability Propagation

The combined output-error interval is applied to the loading series before the
event detector is called. It is not added to or subtracted from a probability
after Monte Carlo estimation.

For each aleatory sample year and fixed `rho`:

- the lower event indicator is true only when at least four consecutive
  15-minute steps remain above the overload threshold under the lower loading
  endpoint;
- the upper event indicator is true when at least four consecutive 15-minute
  steps exceed the threshold under the upper loading endpoint; and
- the G0-A1 import-direction gate and direction-flip reset continue to apply.

The G0-A1 direction gate is evaluated on the **unwidened `P_net` sign**. The
loading-error envelope widens the magnitude used by the event detector; it does
not change import into export or vice versa. Direction misclassification is
confined to the neighborhood of the `P_net = 0` crossing, where `abs(S_net)` is
far below the overload threshold and therefore event-irrelevant. This
assumption must be checked in the G2 validation data and escalated if a
counterexample is observed.

If the eventual error representation is additive import-loading p.u., this is
implemented as:

```text
lower loading series = L_T1 - epsilon_total
upper loading series = L_T1 + epsilon_total
```

The Monte Carlo frequencies of the lower and upper event indicators produce
the model-error-aware probability bounds. Monte Carlo confidence intervals are
computed from those event counts; they are not shifted after estimation.

For an alpha-cut `[rho_L^alpha, rho_U^alpha]`, the formal bounds are

```text
P_lower^alpha(E) = inf over rho and admissible discrepancy functions of P_X(E)
P_upper^alpha(E) = sup over rho and admissible discrepancy functions of P_X(E)
```

Before G3, the existing interior-sampling path remains necessary for `rho`.
After G3 confirms monotonic decrease of the import-overload event in `rho`, and
for an event monotone in loading error, the vertices reduce to:

```text
P_lower^alpha(E) = P_X(E(L_T1(rho_U^alpha) - epsilon_total))
P_upper^alpha(E) = P_X(E(L_T1(rho_L^alpha) + epsilon_total))
```

The pure interval error has the same support at every alpha level. It adds
epistemic width but is not itself defuzzified or probabilized.

## 4. Revised Purpose of G2

G2 shall do more than state that Tier-1 and pandapower are broadly equivalent.
It shall empirically characterize the Tier-1 approximation envelope over the
operating domain used by the paper.

The G2 validation design shall include, at minimum:

- low, medium, near-capacity, and overloaded import states;
- the neighborhood of the 1.0 p.u. threshold;
- ordinary and extreme annual states across the selected planning years;
- multiple flexibility-controllability values;
- relevant active/reactive-power and power-factor conditions;
- consecutive-step episodes as well as isolated peaks; and
- a documented held-out near/above-threshold stratum not used to tune an
  envelope or correction.

For every selected state, G2 shall evaluate Tier-1 and pandapower on the same
inputs and record the residual on the same loading quantity. The experiment
must run through the project runner and produce a manifest.

A hard enclosure acceptance test on the held-out near/above-threshold stratum
is frozen in kind by this amendment: the proposed Tier-1 envelope must bracket
the pandapower result according to a predeclared criterion. The numerical
strictness of that criterion, including whether it requires 100% bracketing,
is set and signed at G2 before the held-out result is inspected. Failure of the
signed criterion prevents an unqualified "Tier-1 adequate" verdict.

G2 shall report:

1. the observed symmetric maximum-absolute envelope or justified asymmetric
   envelope for `delta_Tier1`;
2. residual behavior versus loading level, power factor, year, and `rho`;
3. the effect of composing the G2 Tier-1 endpoints with `epsilon_grid` per
   G1-A2 on the overload probability bounds and downstream decision
   categories; and
4. one of the following PI recommendations:

   - **Tier-1 adequate:** the approximation envelope is small enough to use
     Tier-1 throughout the Monte Carlo analysis;
   - **Tier-1 adequate with correction:** a simple, validated correction
     materially reduces a structured residual before interval widening;
   - **Selective AC required:** pandapower is run only for states or episodes
     whose Tier-1 interval straddles the event threshold, with the promotion
     rule predeclared and the same CRN and manifest discipline as the primary
     experiment; or
   - **Tier-1 rejected:** the approximation is too large or irregular for the
     primary evaluator.

No numerical adequacy threshold is frozen by this proposal. That threshold and
the G2 conclusion require PI approval.

## 5. Compute Rationale

The G0/G1 primary design has `N = 10,000`, five alpha levels, two fuzzy
endpoints, and 35,040 timesteps per full planning year. A literal full-AC inner
loop would therefore request up to approximately 3.504 billion AC solves before
deduplication or optimization.

At the E1.S2 high-level pandapower benchmark of about 105 ms per solve, that is
approximately 11.7 serial years. In contrast, 10,000 validation solves take
about 17.5 minutes and 100,000 take about 2.9 hours through that same measured
path. The corrected TimeSeriesCPP benchmark may improve both figures, but it
does not change the basic advantage of a bounded validation subset over a
full-AC Monte Carlo loop.

The primary difficulty in estimating `epsilon_Tier1` is therefore coverage of
the relevant operating domain, not raw runtime. The Tier-1 result shall be
described as an empirical validation envelope. Questions about formal
confidence or global guarantees belong in the limitations discussion unless a
later PI decision strengthens the protocol. `epsilon_grid` remains an
author-specified assumption unless future field validation or a signed human
elicitation is added.

## 6. Consequences for E5.S3 and the Interfaces

E5.S3 shall implement output-domain interval propagation. Fixed additive
probability margins such as

```text
P_lower' = P_lower - margin_lower
P_upper' = P_upper + margin_upper
```

do not represent the stated grid-model error and shall not be used for this
purpose.

The IC-2/IC-3 boundary must retain enough information to apply the model-error
interval before episode classification. A boolean-only sample evaluator that
discards the loading series is insufficient. Agent A and Agent B shall propose
the smallest compatible schema or callback change; the exact interface change
requires separate PI approval before implementation.

PR #13 (`E5.S3 Model-error widening`) therefore requires revision before
merge. Its useful configuration and invariant-testing structure may be retained,
but probability-domain widening must be replaced with loading-output-domain
propagation and tests of the four-step event semantics.

## 7. Deferred Choices

The following remain open for a later PI decision based on the empirical source
and implementation burden:

- whether `epsilon_grid` is expressed on loading p.u., MVA, or underlying
  active/reactive power;
- whether each envelope is absolute, relative, symmetric, or asymmetric;
- the numerical values of `epsilon_grid` and `epsilon_Tier1`;
- the operating-domain coverage and adequacy threshold used at G2; and
- whether a negligible `epsilon_Tier1` is shown separately in the manuscript
  or absorbed into one composite output-error envelope.

The envelope-form decision must be made jointly with the pending decision on
the aggregate-nameplate convention, including total versus firm `(n-1)`
capacity. Additive and relative loading envelopes can both be implemented as
threshold shifts near `L = 1.0`; implementation simplicity therefore does not
distinguish them. An additive p.u. envelope depends on the selected
`S_nom,agg` denominator and may need rescaling or refitting if that convention
changes. A relative envelope on the physical loading ratio is invariant to the
nameplate convention. This invariance consideration must appear in the later
PI decision brief; neither form is provisionally selected here.

If `epsilon_Tier1` is material, it may not simply be omitted while Tier-1 is
used for the primary results. The acceptable alternatives are to include it,
reduce it with a validated correction, use selective AC evaluation, or abandon
Tier-1 as the primary evaluator. If it is negligible under the signed G2
criterion, it may remain a minor computational-validation detail rather than a
headline uncertainty source.

## 8. Approved Decision Summary

> **G1-A1 - Black-box model-error and Tier-1 approximation amendment -
> 2026-07-13 - signed: PI approved in chat**
>
> `epsilon_grid` is an author-specified interval on the black-box model output,
> not an additive margin on overload probability. It is carried in
> `ASSUMPTIONS.md` with a mandatory sensitivity sweep and explicit asserted
> domain; the numerical row remains proposed until PI sign-off. Any future
> empirical validation is recorded with its validated domain. The interval is
> propagated on the loading series before the
> G0-A1/G0-A2 event detector. No probability distribution or independence
> assumption is assigned to the discrepancy; all dependence on aleatory inputs,
> flexibility controllability, and time that is consistent with the interval is
> admitted.
>
> Tier-1 is treated as a computational approximation to pandapower. G2 shall
> estimate its empirical output-error envelope on a manifested, domain-covering
> AC validation subset. A hard enclosure test on a held-out near/above-threshold
> stratum is required, with its numerical strictness signed before inspection.
> G1-A2 composes the relative symmetric grid envelope with the additive G2
> Tier-1 endpoints using the exact formulas in the current protocol. E5.S3
> shall recompute lower and upper event indicators from the corresponding
> loading endpoints; post-hoc probability-margin widening is rejected.
>
> The G0-A1 import/export direction gate uses the unwidened `P_net` sign; the
> interval widens loading magnitude only. G1-A2 freezes relative symmetric
> grid-error form and the future-domain protocol. Numerical values, the G2
> adequacy criterion, the capacity convention, and the exact IC-2/IC-3 schema
> remain subject to later PI approval.
