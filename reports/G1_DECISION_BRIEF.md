# G1 Decision Brief: Foundation, Compute Budget, And Time Domain

> **Amendment notice (2026-07-13):** G1-A1 in `registers/DECISIONS.md`
> amends the model-error and G2 interpretation. Grid-model error is an
> expert-specified output interval applied before event detection; G2 now
> estimates a held-out-tested Tier-1 approximation envelope. See
> `reports/G1_A1_MODEL_ERROR_AMENDMENT_PROPOSAL.md`.

Date: 2026-07-10  
Prepared for: PI G1 review  
Decision status: approved by PI in chat on 2026-07-10; recorded in `registers/DECISIONS.md` as G0-A2 and G1

## 1. Decision To Make

G1 asks whether the project foundation is credible enough to build the Monte
Carlo and interface layer on top of it.

The concrete G1 questions are:

1. What is the primary time domain for `P(E)`?
2. Is AC power flow feasible inside the Monte Carlo loop?
3. If AC feasibility is not established, is the two-tier design still justified?
4. What AC validation budget should be assumed now?
5. Do the current grid loading screens suggest a case-suitability problem?
6. What interface shape should downstream agents freeze against?

## 2. Approved Decision Summary

G1 is approved with an important change to the time domain. The Tier-1
summation evaluator is the Monte Carlo inner-loop evaluator and runs over the
full planning year. Adaptive import-ranked WindowSets remain useful, but only
for AC-validation subset selection and diagnostics.

The earlier phrase "full AC is infeasible" is explicitly not approved. The
evidence shows only that the benchmarked high-level pandapower `runpp` path is
too slow for the Monte Carlo loop. The lower-level `lightsim2grid`
`TimeSeriesCPP` path remains untested and must be benchmarked before G2 fixes
the AC validation budget.

## 3. Approved G1 Decision Text

```text
## G1 — Foundation validated — 2026-07-10 — signed: PI approved in chat

APPROVED: Two-tier compute architecture. Tier-1 radial summation (per G0-A1
direction semantics) is the Monte Carlo inner-loop evaluator — approved because
it is near-exact for the transformer criterion and computationally negligible.
AC power flow serves deterministic checks and validation subsets. NOTE: the
E1.S2 benchmark establishes only that the pandapower runpp path (~105 ms/solve,
117 buses) cannot host the MC loop; it does NOT establish infeasibility of
lightsim2grid's lower-level path, whose flag showed no speedup and likely never
engaged. No "AC infeasible" claim may appear in the manuscript.

APPROVED WITH CHANGE: Fixed winter windows rejected (E1.S3 evidence). However,
adaptive windows spanning 19–25 weeks (36–48% of year) defeat their compute
purpose in Tier-1. Tier-1 therefore runs the FULL planning year; the event
definition drops the window clause (G0-A2: P(E) = P(≥1 qualifying episode in
the planning year)). WindowSet is retained in IC-1/IC-2 for AC-validation
subset selection and diagnostics only.

CONDITIONS (before G2):
C1. Benchmark the lightsim2grid TimeSeriesCPP adapter properly and diagnose
    the absent runpp speedup; report the corrected AC validation budget.
C2. Headroom diagnostic memo: substation transformer ratings; peak import MVA
    vs total AND firm (n-1) aggregate nameplate; implied 2035 load multiplier
    under both definitions. Flags the anticipated G0-item-4 escalation and the
    firm-capacity redefinition option for PI decision.
C3. Agent A proceeds to E1.S4 with G0-A1 semantics (import/export/screening
    series, direction-flip episode reset) and the full-year event scope.

UNCHANGED FROM DRAFT: export exceedance reported alongside all primary
results; no Dutch 2030/33/35 window/loading claims before E2/E3; no vertex
use before G3; Agent C remains blocked on D-002 (ElaadNL terms).
```

## 4. Evidence: AC Benchmark

Primary grid: SimBench `1-MV-semiurb--0-sw`, 117 buses.

Measured median AC solve times through the pandapower `runpp` API:

| Solve path | Median time per solve |
|---|---:|
| native pandapower `runpp` | 104.938 ms |
| `lightsim2grid=True` via `runpp` | 108.295 ms |

Interpretation:

- These timings are statistically and practically similar.
- This is not what a raw 20x faster C++ backend should look like.
- The result likely means either the fast solver did not engage, or the
  measurement is dominated by pandapower-side conversion and result-writing.
- Therefore the correct finding is not "AC is infeasible." The correct finding
  is "the benchmarked high-level AC path is too slow for full-loop MC."

The installed `lightsim2grid.timeSerie` module exposes `TimeSeriesCPP`, but the
documented high-level `TimeSerie` helper was not available. No lower-level
adapter was benchmarked in E1.S2.

Practical AC validation budget under the benchmarked `runpp` path:

| AC solve count | Approx native runtime |
|---:|---:|
| 1,000 | 1.75 min |
| 10,000 | 17.49 min |
| 100,000 | 2.91 h |

Full-loop AC runtime under the benchmarked `runpp` path:

| Case | AC solves | Approx native runtime |
|---|---:|---:|
| Primary full AC, `T=96`, N=1e4, 5 alpha levels, 2 endpoints | 9.6M | 279.83 h |
| Primary full AC, `T=672`, N=1e4, 5 alpha levels, 2 endpoints | 67.2M | 1958.84 h |
| 1e-3 sensitivity full AC, `T=96`, N=1e5, 3 alpha levels, 2 endpoints | 57.6M | 1679.00 h |

But if a lower-level path achieved 0.5 ms/solve, 9.6M solves would take about
80 minutes. At 0.08 ms/solve, it would take about 13 minutes. That possibility
is untested, not ruled out.

G1 implication:

- Keep the two-tier architecture.
- Do not justify it by claiming all AC is infeasible.
- Justify it by saying Tier-1 is the right primary evaluator for the transformer
  summation criterion, and high-level AC is currently only practical for
  validation subsets.
- Require a `TimeSeriesCPP` benchmark before G2 fixes the AC validation budget.

## 5. Evidence: Fixed Winter Windows Failed

The original plan used fixed winter critical weeks. E1.S3 tested whether those
windows captured annual top-loading steps using direction-agnostic apparent
loading.

| Scenario | Finding |
|---|---|
| 0 | Annual peak was winter, but fixed winter windows captured only 58.3% / 45.8% / 42.9% of top 24 / 96 / 672 annual steps. |
| 1 | Annual direction-agnostic peak was outside winter, around July midday; top 24 and top 96 winter coverage were 0%. |
| 2 | Annual direction-agnostic peak was outside winter, around July midday; top 24 and top 96 winter coverage were 0%. |

Interpretation:

- Scenario 0 showed a window-tuning issue: the very top steps were winter
  concentrated, but the near-peak shoulder spread across the year.
- Scenarios 1 and 2 exposed a reverse-PV/export regime under direction-agnostic
  loading.
- This led to G0-A1: the primary event is import-direction consumption
  congestion; export/feed-in loading remains a reported side metric.

Conclusion: fixed winter windows should remain rejected.

## 6. Evidence: Adaptive Import Windows Work, But Should Not Be The Primary Domain

G0-A1 defines import/export loading as:

```text
L_import(t) = abs(S_net(t)) / S_nom,agg if P_net(t) > 0, else 0
L_export(t) = abs(S_net(t)) / S_nom,agg if P_net(t) < 0, else 0
P_net(t) = 0 belongs to neither direction
```

Agent A PR #15 applied this split and selected adaptive import-ranked windows.
Target: cover at least 95% of annual top-672 import-loading steps on the
deterministic screen. Proposal: top-K weeks plus 1 margin week.

| Scenario | Annual top import loading | Base K for 95% | Margin | Selected K | Selected coverage |
|---|---:|---:|---:|---:|---:|
| 0 | 0.159145 p.u. | 24 | 1 | 25 weeks | 96.4% |
| 1 | 0.150356 p.u. | 21 | 1 | 22 weeks | 97.0% |
| 2 | 0.188443 p.u. | 18 | 1 | 19 weeks | 97.5% |

Export side metric:

| Scenario | Max export loading | Export max timestamp | Export episodes above 1.0 p.u. |
|---|---:|---|---:|
| 0 | 0.135013 p.u. | 2016-05-29 12:45 UTC | 0 |
| 1 | 0.440427 p.u. | 2016-07-25 11:30 UTC | 0 |
| 2 | 0.533511 p.u. | 2016-07-25 11:30 UTC | 0 |

Interpretation:

- The G0-A1 direction split is working and produces transparent import/export
  diagnostics.
- Adaptive import windows satisfy the deterministic 95% top-672 coverage
  target.
- However, the selected windows cover 19 to 25 weeks, about 36% to 48% of the
  year.
- At that size, windows no longer buy enough Tier-1 compute savings to justify
  making the primary probability an approximate windowed quantity.

Recommendation:

- Run Tier-1 Monte Carlo over the full planning year.
- Use adaptive import WindowSets for AC validation subsets and diagnostics.
- Record this as a G0-A2 amendment because current G0/G0-A1 language still
  refers to the event occurring within selected critical windows.

## 7. Evidence: Transformer Headroom Warning

The E1.S3b annual peak import loadings are low:

| Scenario | Annual peak import loading vs total nameplate |
|---|---:|
| 0 | 0.159145 p.u. |
| 1 | 0.150356 p.u. |
| 2 | 0.188443 p.u. |

The E1.S1 inventory records aggregate transformer rating as 80 MVA for the
primary decision transformer bank. Approximate peak import MVA is therefore:

| Scenario | Peak import MVA vs total 80 MVA |
|---|---:|
| 0 | 12.7 MVA |
| 1 | 12.0 MVA |
| 2 | 15.1 MVA |

G0's suitability screen says the case becomes uninteresting if
`L_2035^(rho=0) < 0.95 p.u.`. With current deterministic SimBench import peaks,
the Dutch 2035 layer would need a large multiplier to threaten the limit:

| Scenario | Multiplier needed to reach 0.95 p.u. under total-nameplate denominator |
|---|---:|
| 0 | about 6.0x |
| 1 | about 6.3x |
| 2 | about 5.0x |

If the denominator is reinterpreted as firm N-1 capacity for two identical
parallel units, the effective p.u. loading doubles, but the required multiplier
is still substantial:

| Scenario | Approx loading vs firm half-bank capacity | Multiplier to reach 0.95 p.u. |
|---|---:|---:|
| 0 | 0.318 p.u. | about 3.0x |
| 1 | 0.301 p.u. | about 3.2x |
| 2 | 0.377 p.u. | about 2.5x |

Interpretation:

- The current primary grid may have too much transformer headroom for the
  reinforcement-deferral question.
- This does not invalidate G1 compute architecture, but it does warn that case
  suitability may fail later.
- The denominator question matters: total installed nameplate answers "thermal
  aggregate loading"; firm N-1 capacity may better match planning/security
  headroom for a parallel transformer bank.

Required follow-up before E3/G5 confidence:

Ask Agent A for a one-page transformer-headroom diagnostic:

1. Transformer count and individual ratings at the decision substation.
2. Peak import MVA under scenario 0/1/2.
3. Loading versus aggregate nameplate and versus firm N-1 capacity.
4. Load-growth multiplier needed for the 2035 no-flex layer to reach 0.95 p.u.
   under both denominator conventions.
5. Whether this triggers G0 fallback/escalation.

## 8. What G1 Approved

- Tier-1 radial summation as the primary Monte Carlo evaluator.
- Full-year Tier-1 evaluation for the primary annual `P(E)` metric.
- AC power flow for deterministic checks and validation subsets.
- Adaptive import WindowSets for AC validation and diagnostics.
- Export-direction exceedance reporting next to import-event results.
- IC-1/IC-2 support for both full-year and WindowSet evaluation.

Provisional / conditioned before G2:

- AC validation budget under the current `runpp` path: 10,000 to 100,000 solves.
- Larger AC validation budgets remain possible if a lower-level TimeSeriesCPP
  benchmark succeeds.

Guardrails:

- The statement "full AC is infeasible" without qualification.
- Fixed winter windows as the primary time structure.
- Adaptive windows as the primary Tier-1 Monte Carlo domain.
- Any final Dutch 2030/2033/2035 case suitability claim before the technology
  layer and headroom diagnostic exist.
- Any use of the vertex shortcut for paper results before G3.

## 9. Immediate Next Steps

1. Merge Agent A PR #15 as evidence if it is still open.
2. Merge the G0-A2/G1 decision update so all agents see the signed gate state.
3. Assign Agent A two short follow-ups before G2:
   - solver-engagement / TimeSeriesCPP benchmark;
   - transformer-headroom diagnostic.
4. Then assign Agent A to E1.S4 with full-year and WindowSet support.
5. Keep Agent C blocked on D-002 generated-profile terms before bulk EV profile
   generation.
