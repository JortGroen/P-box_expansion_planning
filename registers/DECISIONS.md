# DECISIONS.md

Signed PI decisions live here. Agents may append proposed rows, but they never
write a PI sign-off.

| ID | Date | Gate/topic | Decision | Rationale | Evidence | Status | PI sign-off |
|---|---|---|---|---|---|---|---|
| G0 | 2026-07-09 | Scope freeze | Approved: see detailed G0 entry below. | Required before gated scope-specific work; freezes overload event, P_crit handling, grid/fallback choice, weather scope, and primary alpha grid. | E0 registers; E1.S1 grid inventory PR #2; G0 scope-freeze text approved by PI. | approved | PI approved in chat, 2026-07-09 |
| G0-A1 | 2026-07-10 | Event direction and critical windows amendment | Primary overload event is consumption-driven import congestion: apparent-power magnitude conditioned on net import direction. Direction-agnostic `abs(S)` remains the screening metric, and export-direction exceedance is reported beside primary results. Fixed winter windows are retired in favor of adaptive import-loading-ranked windows. | E1.S3 showed direction-agnostic annual maxima in SimBench scenarios 1/2 are summer midday export/PV peaks, while scenario 0 winter windows miss much of the annual near-peak shoulder. The study's flexibility construct is demand-reduction, so feed-in congestion needs a distinct absorption/curtailment instrument and remains out of scope. | E1.S3 PR #10; `reports/critical_weeks_validation.md`; PI amendment text in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G1 | TBD | Foundation validated | Pending: compute budget, adaptive import-window choice, and IC schema freeze | Required before relying on runtime budget and contracts | E1.S2 benchmark; E1.S3 profile report; E1.S3b import-window diagnostic | pending | -- |
| G2 | TBD | Tier equivalence | Pending: summation primary vs AC primary | Determines overload evaluator strategy | E3.S3 tier comparison | pending | -- |
| G3 | TBD | Monotonicity verdict | Pending: vertex shortcut vs interior sampling | Critical compute shortcut | E4.S1 monotonicity report | pending | -- |
| G4 | TBD | Elicitation sign-off | Pending: fuzzy controllability corners | Paper hinge assumption | E7.S2 worksheet | pending | -- |
| G5 | TBD | Case selection | Pending: decision-reversal benchmark case | Money figure depends on divergent treatments | E8.S1 case sweep | pending | -- |
| G6 | TBD | Results freeze | Pending: paper numbers locked to manifests | Required before manuscript finalization | E9 robustness; E10.S1 figure dry-run | pending | -- |
| G7 | TBD | Submission | Pending: approve Applied Energy submission | Final paper gate | Manuscript, repro package, red-team report | pending | -- |
| DEP-001 | 2026-07-09 | Dependency pin update | Use `simbench==1.6.2` and `pandapower>=3.4,<4` in the `.venv` requirements. | Upstream SimBench 1.6.2 declares `pandapower>=3.4.0`; avoids the older `simbench==1.6.1` / `pandapower==3.5.3` top-level `compare_arrays` import break. | PI review of upstream `simbench` `pyproject.toml`; `.venv` metadata check; `.\scripts\task.ps1 test`; direct import check for `pandapower`, `simbench`, and `lightsim2grid`. | approved | PI approved in chat, 2026-07-09 |
| EV-001 | 2026-07-10 | D-002 EV charging data source | Use the ElaadNL Laadprofielengenerator generated-profile route in `reports/elaad_profile_generation_spec.md` for D-002 instead of the unavailable historical ElaadNL/EVnetNL transaction dataset. First implementation step is a one-profile API probe; bulk profile-library generation waits until API semantics and terms-of-use notes are recorded. | The current ElaadNL download page exposes a Charging Energy Hubs neighbourhood opportunity workbook, not session/profile behavior data. The generator provides accessible, seeded, 15-minute Dutch Outlook-based EV charging profiles suitable for a frozen profile library or calibration target. | PI-provided profile-generation spec; local inspection of `data_CEH_kansrijkheid_2026Q1.xlsx`; ElaadNL dashboard/API URLs in D-002. | approved | PI approved in chat, 2026-07-10 |
| COST-001 | 2026-07-10 | D-008 Cicenas thesis unit-cost source | Use the PI-supplied local Cicenas 2025 thesis PDF as the D-008 source for unit-cost extraction. The PDF must not be committed or redistributed. Every extracted number must record value, unit, exact meaning/context, thesis page, table/appendix/section label if available, source status (Stedin-confirmed, thesis-derived, or interpreted), intended project use, and PI sign-off before manuscript use. | The professor of the thesis is involved in the project, and the PI confirmed that thesis-derived unit costs are acceptable if every number is exactly traceable and cited wherever used. | Local raw file `data/raw/cicenas_2025_thesis.pdf`, sha256 `96EF9625BA0AFEE2910189A61967943BA3BCD460AE3AC080B847C4D8DD7D99C0`; literature-review anchor line 133. | approved | PI approved in chat, 2026-07-10 |

## G0 - Scope Freeze - 2026-07-09 - signed: PI approved in chat

Authority: this entry supersedes all illustrative examples of the overload
event, P_crit handling, and grid choice in the project plan and the actionable
plan. G0-A1 amends the event direction and critical-window rules below. Changes
to any item below require a new signed entry.

### 1. Decision Asset And Terminology

Canonical term = "decision transformer" in all code, configs, registers, and
prose. In the SimBench case study this is the HV/MV transformer bank at the
external-grid substation of the primary grid; the motivating MV/LV
neighbourhood case maps onto the same construction because the method is
level-agnostic. Exact pandapower element index(es) must be recorded in the
E1.S1 inventory and appended to this entry.

If parallel units exist, loading is defined as:

```text
L(t) = abs(sum_i S_i(t)) / sum_i S_nom_i
```

where `S_i(t)` is complex apparent power through unit `i`. This is the raw
magnitude of the complex net substation exchange over summed nameplate. G0-A1
conditions the primary event on import direction, while retaining this
direction-agnostic magnitude as the screening metric and for export-side
reporting. Tier-1 computes the magnitude from aggregated downstream net P and
Q.

Validity condition (see `ASSUMPTIONS.md` `A-005`): busbar-parallel identical
units, closed bus-tie, equal taps, and no circulating-current modeling, under
which aggregate loading equals each unit's individual loading. G2 must confirm
per-unit versus aggregate loading agreement within the summation-vs-AC
tolerance using pandapower `res_trafo.loading_percent`.

If the station has an open tie or separate MV sections, escalate: the decision
asset becomes a single section's transformer and aggregate loading is not used.

### 2. Overload Event E

As amended by G0-A1, let `S_net(t) = P_net(t) + jQ_net(t)` be the aggregate
complex power through the decision transformer, with `P_net(t) > 0` denoting
net import from the upstream grid into the MV area. The loading quantities are:

```text
L_import(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) > 0
            = 0                           otherwise

L_export(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) < 0
            = 0                           otherwise
```

`P_net(t) = 0` belongs to neither direction and is captured only by the
unconditioned screening metric `abs(S_net(t)) / S_nom,agg`.

Event `E` operates on `L_import`: at least 4 consecutive 15-minute steps with
`L_import(t) > 1.0` p.u., meaning at least 1 hour, within the critical window
of the planning year. A direction flip resets the episode counter. Every
results table reports export-direction exceedance of `L_export` alongside
`P(E)`.

`P(E)` is the probability, over the aleatory ensemble, that the planning year
contains at least 1 qualifying episode.

Justification: DSO loading-percent language, with congestion defined at more
than 100% loading, plus IEC 60076-7 cyclic thermal tolerance, which makes a
lone 15-minute excursion thermally meaningless. The single-step variant, any
one 15-minute step above 1.0 p.u., is retained as an E9 sensitivity only.

Scope statement for the manuscript: this study addresses consumption-driven
(`afname`) congestion deferral. Feed-in (`invoeding`) congestion is a distinct
planning problem with a distinct flexibility instrument such as absorption or
curtailment, and is out of scope except for transparent reporting.

### 3. P_crit And Sensitivity Protocol

Primary: `P_crit = 1e-2`, `N = 1e4` aleatory samples, full alpha grid from
item 6, and Tier-2 AC validation applies to this analysis.

Sensitivity: `P_crit = 1e-3`, `N = 1e5`, reduced alpha set `{0, 0.5, 1.0}`,
Tier-1 summation only, no AC validation at `1e-3`, and common random numbers
shared with the primary run. Local refinement is pre-authorized: add
`alpha = 0.25` or `alpha = 0.75` only if alpha_star under `1e-3` falls in a
bracket whose endpoints yield different decisions.

`P_crit` is frozen. Case interestingness is achieved at G5 by case selection:
year, adoption scenario, feeder/grid. It is never achieved by threshold
adjustment.

### 4. Grid And Fallback

Primary: SimBench `1-MV-semiurb--0-sw`, with LV aggregated at secondary
substations. Baseline topology and profiles are SimBench scenario 0.
Technology layers for 2030, 2033, and 2035 come from II3050/ElaadNL-derived
`scenarios.yaml`, meaning Dutch adoption on validated topology. SimBench
scenarios 1 and 2 are appendix cross-checks only. CIGRE MV is a robustness
cross-check.

Pre-authorized fallback to `1-MV-urban--0-sw` is allowed if and only if the
deterministic screen, computed at E1.S1/E3 before any Monte Carlo, shows either:

```text
L_base > 0.85 p.u.
```

where `L_base` is the max 15-minute loading of the decision transformer under
SimBench scenario-0 profiles, deterministic, full year, using the G0-A1 primary
import-direction loading, indicating the grid is already congested and no
deferral question exists; or:

```text
L_2035^(rho=0) < 0.95 p.u.
```

where `L_2035^(rho=0)` is the max import-direction loading under the 2035
adoption layer with zero flexibility over the G0-A1 adaptive critical-window
screen, indicating electrification never threatens the limit and no
reinforcement question exists.

Screen thresholds are routing heuristics for grid selection, not scientific
claims (see `ASSUMPTIONS.md` `A-008`). If `1-MV-urban--0-sw` fails the same
screen, escalate to the PI. Pre-considered options are to rescale the adoption
layer within the documented II3050 bandwidth, or to move the decision asset.
No silent tuning is allowed.

### 5. Weather

KNMI historical winters, including at least one design-cold winter, form the
aleatory weather ensemble. Coherence is with the Dutch scenario/profile layer
II3050, ElaadNL, and MFFBAS, not with the topology's German provenance (see
`ASSUMPTIONS.md` `A-007`).

### 6. Alpha Grid, Primary

Primary alpha grid: `{0, 0.25, 0.5, 0.75, 1.0}`. Use five levels, endpoint
vertex propagation per level once G3 confirms monotonicity, and nested-cut
common-random-number sample reuse.

### Assumptions Spawned By G0

Create as proposed rows in `ASSUMPTIONS.md`, PI to sign:

- `A-005`: parallel-unit collinearity / equal split / equal taps, verified
  empirically at G2.
- `A-006`: constant nodal power factor supplies Q for `abs(S)` in Tier-1; the
  flexibility aggregator adjusts P with Q following the power factor. This
  feeds the event definition directly.
- `A-007`: Dutch KNMI weather drives German-measured SimBench baseline
  profiles, justified because heating load is modeled separately through the
  heat-pump layer, leaving baseline demand weakly weather-coupled.
- `A-008`: fallback screen thresholds 0.85 and 0.95 p.u. are routing
  heuristics, not scientific claims.

### Open Items To Append After E1.S1 Follow-Up

- Decision-transformer element index(es) and unit count.
- Bus-tie configuration: closed parallel confirmed, or open-tie escalation.
- Fallback screen results: `L_base`, `L_2035^(rho=0)`, and resulting grid
  choice.

## G0-A1 - Event Direction And Critical Windows Amendment - 2026-07-10 - signed: PI approved in chat

Authority: this entry amends G0 item 2, the G0 fallback-screen loading
interpretation, and the critical-window examples in the project/actionable
plans. Where it conflicts with earlier text, this entry wins.

### 2a. Event Direction And Loading Quantity

Let `S_net(t) = P_net(t) + jQ_net(t)` be the aggregate complex power through
the decision transformer. Tier-1 computes this as the sum of downstream nodal
net P and Q. `P_net(t) > 0` denotes net import from the upstream grid into the
MV area.

```text
L_import(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) > 0
            = 0                           otherwise

L_export(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) < 0
            = 0                           otherwise
```

Convention: `P_net(t) = 0` belongs to neither direction. It is captured by the
unconditioned screening metric `abs(S_net(t)) / S_nom,agg`, which is retained
for E1.S3/E9.S3 screens.

The overload event `E` operates on `L_import`: at least 4 consecutive
15-minute steps with `L_import(t) > 1.0` p.u. A direction flip resets the
episode counter; this is the intended semantics for consumption congestion.
Every results table reports the export-direction exceedance of `L_export`
alongside `P(E)`.

Thermal correctness note: `abs(S)` is the loading quantity in both directions;
`sign(P_net)` is only the direction gate.

Manuscript scope statement: this study addresses consumption-driven (`afname`)
congestion deferral. Feed-in (`invoeding`) congestion is a distinct problem
with a distinct flexibility instrument and is out of scope, evidenced by the
E1.S3 screen.

### 2. Critical Windows

The fixed-winter-window assumption is retired. Critical windows are selected
adaptively per `(scenario, year, technology layer)` from the import-direction
loading ranking: use top-K import-ranked weeks plus 1 margin week. Choose K
from the coverage-vs-K curve to reach at least 95% of the annual top-672
import-loading steps on the deterministic screen where feasible. If the 95%
target is not feasible with a practical K, escalate the K/runtime trade-off at
G1 rather than silently lowering the criterion.

The deterministic screen is necessary but not sufficient: selected windows
must be re-validated against the Monte Carlo layer at G2/G3, after E2/E3 supply
the stochastic net-load pipeline.

### 3. G3 Linkage

Monotonicity of `P(E)` in controllable demand reduction `rho` is claimed and
tested for the import-direction event only. The E1.S3 direction-agnostic
screen confirmed that export/PV feed-in can bind in SimBench future scenarios.
If export congestion is ever brought into scope, it requires the interior
sampling path and a distinct fuzzy flexibility instrument for absorption or
curtailment.
