# DECISIONS.md

Signed PI decisions live here. Agents may append proposed rows, but they never
write a PI sign-off.

| ID | Date | Gate/topic | Decision | Rationale | Evidence | Status | PI sign-off |
|---|---|---|---|---|---|---|---|
| G0 | 2026-07-09 | Scope freeze | Approved: see detailed G0 entry below. | Required before gated scope-specific work; freezes overload event, P_crit handling, grid/fallback choice, weather scope, and primary alpha grid. | E0 registers; E1.S1 grid inventory PR #2; G0 scope-freeze text approved by PI. | approved | PI approved in chat, 2026-07-09 |
| G1 | TBD | Foundation validated | Pending: compute budget and IC schema freeze | Required before relying on runtime budget and contracts | E1.S2 benchmark; E1.S3 profile report | pending | -- |
| G2 | TBD | Tier equivalence | Pending: summation primary vs AC primary | Determines overload evaluator strategy | E3.S3 tier comparison | pending | -- |
| G3 | TBD | Monotonicity verdict | Pending: vertex shortcut vs interior sampling | Critical compute shortcut | E4.S1 monotonicity report | pending | -- |
| G4 | TBD | Elicitation sign-off | Pending: fuzzy controllability corners | Paper hinge assumption | E7.S2 worksheet | pending | -- |
| G5 | TBD | Case selection | Pending: decision-reversal benchmark case | Money figure depends on divergent treatments | E8.S1 case sweep | pending | -- |
| G6 | TBD | Results freeze | Pending: paper numbers locked to manifests | Required before manuscript finalization | E9 robustness; E10.S1 figure dry-run | pending | -- |
| G7 | TBD | Submission | Pending: approve Applied Energy submission | Final paper gate | Manuscript, repro package, red-team report | pending | -- |
| DEP-001 | 2026-07-09 | Dependency pin update | Use `simbench==1.6.2` and `pandapower>=3.4,<4` in the `.venv` requirements. | Upstream SimBench 1.6.2 declares `pandapower>=3.4.0`; avoids the older `simbench==1.6.1` / `pandapower==3.5.3` top-level `compare_arrays` import break. | PI review of upstream `simbench` `pyproject.toml`; `.venv` metadata check; `.\scripts\task.ps1 test`; direct import check for `pandapower`, `simbench`, and `lightsim2grid`. | approved | PI approved in chat, 2026-07-09 |

## G0 - Scope Freeze - 2026-07-09 - signed: PI approved in chat

Authority: this entry supersedes all illustrative examples of the overload
event, P_crit handling, and grid choice in the project plan and the actionable
plan. Changes to any item below require a new signed entry.

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

where `S_i(t)` is complex apparent power through unit `i`. This is the
magnitude of the complex net substation exchange over summed nameplate;
direction-agnostic reverse/PV backfeed counts, and Tier-1 computes it from
aggregated downstream net P and Q.

Validity condition (see `ASSUMPTIONS.md` `A-005`): busbar-parallel identical
units, closed bus-tie, equal taps, and no circulating-current modeling, under
which aggregate loading equals each unit's individual loading. G2 must confirm
per-unit versus aggregate loading agreement within the summation-vs-AC
tolerance using pandapower `res_trafo.loading_percent`.

If the station has an open tie or separate MV sections, escalate: the decision
asset becomes a single section's transformer and aggregate loading is not used.

### 2. Overload Event E

Apparent-power loading `L(t)` of the decision transformer exceeds 1.0 p.u. of
nameplate for at least 4 consecutive 15-minute steps, meaning at least 1 hour,
within the critical window of the planning year.

`P(E)` is the probability, over the aleatory ensemble, that the planning year
contains at least 1 qualifying episode.

Justification: DSO loading-percent language, with congestion defined at more
than 100% loading, plus IEC 60076-7 cyclic thermal tolerance, which makes a
lone 15-minute excursion thermally meaningless. The single-step variant, any
one 15-minute step above 1.0 p.u., is retained as an E9 sensitivity only.

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
SimBench scenario-0 profiles, deterministic, full year, indicating the grid is
already congested and no deferral question exists; or:

```text
L_2035^(rho=0) < 0.95 p.u.
```

where `L_2035^(rho=0)` is the max loading in the design-cold critical week
under the 2035 adoption layer with zero flexibility, indicating electrification
never threatens the limit and no reinforcement question exists.

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
