# G1-A2 Grid-Error and Capacity-Screen Protocol

**Status:** protocol approved by the PI in chat on 2026-07-14; numerical
`epsilon_grid` values remain proposed in A-013.

## Decisions Frozen Now

1. Grid-model output discrepancy uses a symmetric relative interval.
2. The discrepancy is unprobabilized and may depend arbitrarily on inputs,
   controllability, time, and Tier-1 error.
3. Error endpoints are applied to loading trajectories before the four-step
   overload detector. Direction is gated by the unwidened `P_net` sign.
4. The fixed `16-104 MVA` (`0.2-1.3 p.u.` on 80 MVA) applicability claim is
   withdrawn. The 104 MVA ceiling was arithmetic, not evidence.
5. One manifested future-layer screen will inform the total-versus-firm
   capacity decision and freeze the asserted operating domain before any
   probabilistic-result inspection.

The candidate 5% reference and 2%/10% sensitivities are not frozen. They are
author-specified scenarios until the evidence review in E9.S5a is complete and
the PI signs A-013.

## DSO Model Boundary

The illustrative user is a DSO with a planning model whose topology and asset
data are mostly correct and whose upstream transformer power is measured or
forecast. Lower-voltage injections may be forecast or spatially allocated.
The story does not assume dense measurement coverage, feeder-level state
estimation, or a calibrated distribution model. It also does not add a
pandapower-versus-commercial-solver term: pandapower instantiates the DSO's
otherwise trusted load-flow calculation for this reproducible case study.

`epsilon_grid` therefore represents residual disagreement between the DSO
planning-model output and physical aggregate transformer loading at this
boundary. Input uncertainties already modeled in the scenario and Monte Carlo
layers are excluded to avoid double counting.

## Exact Error Composition

Let `L_T1(t)` be Tier-1 loading. G2 estimates additive Tier-1-to-pandapower
enclosure endpoints `epsilon_Tier1_minus` and `epsilon_Tier1_plus`. For the
symmetric relative grid-error scenario `epsilon_grid`, use

```text
L_PP_lower(t) = max(0, L_T1(t) - epsilon_Tier1_minus)
L_PP_upper(t) =        L_T1(t) + epsilon_Tier1_plus

L_lower(t) = (1 - epsilon_grid) * L_PP_lower(t)
L_upper(t) = (1 + epsilon_grid) * L_PP_upper(t)
```

For a symmetric G2 envelope, set both Tier-1 endpoints to
`epsilon_Tier1`. This endpoint construction is conservative without assuming
cancellation or independence. It is not replaced by
`epsilon_Tier1 + epsilon_grid`, because one term is additive and the other is
relative.

The import/export gate is evaluated once from unwidened `P_net`. Only the
loading magnitude is widened. The endpoint trajectories then enter the same
four-consecutive-step detector. Monte Carlo estimates and confidence intervals
come from endpoint event counts; no probability is shifted after estimation.

## One Future-Layer Screening Experiment

E3.S2b is one versioned runner experiment with one manifest. It starts only
after the EV, heat-pump, PV, adoption, flexibility, and IC-1 net-load layers
are integrated. Its design is declared before execution and includes:

- the 2030, 2033, and 2035 planning layers;
- all predeclared adoption scenarios used by the paper;
- no-flexibility and predeclared maximum-flexibility endpoints;
- raw peak and episode-level aggregate transformer MVA;
- loading ratios using both total 80 MVA and firm 40 MVA denominators; and
- import and export regimes reported separately.

The report classifies each denominator as producing no relevant congestion,
decision-sensitive congestion, or congestion that the modeled flexibility
cannot resolve. This is a diagnostic, not the final stochastic result. The
input ranges and resulting MVA span are frozen as the asserted operating
domain before p-box results are inspected. Any later sample outside that
domain is flagged and escalated; it is not clipped or used to enlarge the
domain after the fact.

EV and heat-pump layers are expected to increase import demand, while PV can
reduce import or create export peaks. The screen is therefore deferred until
all three layers exist; the scenario-0 SimBench-only headroom result cannot
answer the capacity question.

## Capacity Convention

The current transformer bank contains two 40 MVA units. The candidates are:

| Convention | Denominator | Meaning |
|---|---:|---|
| Total | 80 MVA | Normal-operation aggregate installed nameplate under G0 |
| Firm `(n-1)` | 40 MVA | Capacity remaining after loss of one unit |

The existing baseline peak is 12.7316 MVA, equal to 0.159 p.u. total or 0.318
p.u. firm. It is not a future Dutch loading result. The PI will decide the
primary convention after E3.S2b using its planning interpretation, available
Dutch-practice evidence, and whether flexibility can materially change the
decision. The denominator must not be selected solely to create congestion.
If neither produces a scientifically useful case, G0's documented fallback or
escalation process applies; any load or network change must be explicit,
sourced, and approved.

A 40 MVA denominator applied to normal two-unit flow is only a headroom screen.
If firm capacity becomes primary, E3.S3 must run an actual one-transformer-out
AC topology and G0, A-005, A-013, and the G2 validation domain must be amended
before results use it.

## Practice Anchors and Source Status

| Anchor | Verified source | Permitted interpretation |
|---|---|---|
| 66% operational limit | Unterluggauer et al. (2023), *Sustainable Energy, Grids and Networks* 35, 101085, [doi:10.1016/j.segan.2023.101085](https://doi.org/10.1016/j.segan.2023.101085); [DTU record and manuscript](https://orbit.dtu.dk/en/publications/impact-of-cost-based-smart-electric-vehicle-charging-on-urban-low/) | Danish Radius low-voltage operational limit for N-1 security. The reported `<1%` exceedance belongs to one modeled grid; it is not a Dutch rule or direct derivation of `P_crit`. |
| Approximately 60% installed-capacity anchor | ABB patent US 11,031,773, [official USPTO PDF](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11031773) | Patent-background description only. Retain as an illustrative anchor; re-verify the exact passage and page before manuscript citation. |
| Dutch MV/LV practice | No universal open numerical criterion verified in the current evidence set | Prioritize Dutch primary evidence in E9.S5a. Do not relabel Danish or patent material as Dutch practice. |

The repository previously linked an unrelated withdrawn arXiv record for the
Radius claim; that citation is removed by this amendment.

## Evidence Review for the 5% Scenario

The current search did not identify a primary source establishing a universal
`+/-5%` aggregate-transformer-loading error for an uncalibrated DSO planning
model. Two relevant but non-decisive sources illustrate the evidence gap:

- Thakar et al. (2023), [doi:10.1109/OAJPE.2023.3285888](https://doi.org/10.1109/OAJPE.2023.3285888),
  report feeder-head agreement within approximately 5% for a detailed,
  measurement-informed and tuned distribution representation. This shows that
  5% can be attainable under stronger information conditions; it does not
  establish an enclosure for this project's uncalibrated-model story.
- Blakely, Reno, and Peppanen (2019),
  [doi:10.1109/PVSC40753.2019.8980833](https://doi.org/10.1109/PVSC40753.2019.8980833),
  document common utility distribution-model errors and their material effect
  on analysis, but do not provide one transferable aggregate percentage.

E9.S5a must search primary literature and DSO guidance and extract, for every
candidate number: measured quantity, network level, model conditioning,
measurement density, operating range, statistic or enclosure meaning, and
transferability to this model boundary. Until then, 5% is a transparent
sensitivity reference, not a scientifically backed error value.
