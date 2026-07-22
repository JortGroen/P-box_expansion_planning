# G1 Decision Brief: Foundation, Compute Budget, And Time Domain

> **Threshold note (superseded 2026-07-22):** this report predates Q-5 resolution. G0-A3 now sets the primary event to strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps, with `1.1` and `1.2 p.u.` retained as sensitivities.

> **Amendment notice (2026-07-14):** G1-A1 and G1-A2 in
> `registers/DECISIONS.md` amend the model-error and G2 interpretation.
> Grid-model error is an author-specified symmetric relative scenario applied
> before event detection under unknown dependence; its numerical A-013 value
> remains proposed. G2 estimates held-out-tested additive Tier-1 endpoints,
> and E3.S2b freezes the future domain and informs the total-versus-firm
> capacity choice. See `reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md`.

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

E1.S1b subsequently completed the requested headroom diagnostic in
`reports/transformer_headroom_diagnostic.md`. It establishes the two 40 MVA
units and the low SimBench-only baseline loading, but cannot choose the future
capacity convention because the Dutch EV, heat-pump, PV, and adoption layers
do not yet exist. G1-A2 therefore replaces the old follow-up with E3.S2b: one
manifested integrated future-layer screen reporting raw MVA and both capacity
ratios before p-box inspection.

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
  layers and E3.S2b screen exist.
- Any use of the vertex shortcut for paper results before G3.

## 9. Immediate Next Steps

1. Complete E1.S2b solver-engagement/TimeSeriesCPP benchmarking.
2. Complete E1.S4 and the E2/E3 technology and net-load layers.
3. Run E3.S2b once under its predeclared manifest; then sign the capacity
   convention and asserted domain.
4. Complete E9.S5a and sign or explicitly retain the proposed A-013 numerical
   scenarios.
5. Run the G2 held-out Tier-1 enclosure over the frozen domain.
