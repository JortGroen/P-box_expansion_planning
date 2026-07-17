# DECISIONS.md

Signed PI decisions live here. Agents may append proposed rows, but they never
write a PI sign-off. Every row must have a same-ID standalone paragraph block
in `paper/methods_decisions_and_assumptions.md`; pending gates use an explicit
placeholder until the PI records a decision.

| ID | Date | Gate/topic | Decision | Rationale | Evidence | Status | PI sign-off |
|---|---|---|---|---|---|---|---|
| G0 | 2026-07-09 | Scope freeze | Approved: see detailed G0 entry below. | Required before gated scope-specific work; freezes overload event, P_crit handling, grid/fallback choice, weather scope, and primary alpha grid. | E0 registers; E1.S1 grid inventory PR #2; G0 scope-freeze text approved by PI. | approved | PI approved in chat, 2026-07-09 |
| G0-A1 | 2026-07-10 | Event direction and fixed-window rejection amendment | Primary overload event is consumption-driven import congestion: apparent-power magnitude conditioned on net import direction. Direction-agnostic `abs(S)` remains the screening metric, and export-direction exceedance is reported beside primary results. Fixed winter windows are rejected; G0-A2 later assigns primary Tier-1 `P(E)` to the full planning year and retains WindowSets only for AC validation and diagnostics. | E1.S3 showed direction-agnostic annual maxima in SimBench scenarios 1/2 are summer midday export/PV peaks, while scenario 0 winter windows miss much of the annual near-peak shoulder. The study's flexibility construct is demand-reduction, so feed-in congestion needs a distinct absorption/curtailment instrument and remains out of scope. | E1.S3 PR #10; `reports/critical_weeks_validation.md`; PI amendment text in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G0-A2 | 2026-07-10 | Full-year primary event scope | Primary Tier-1 `P(E)` is annual: the probability that the full planning year contains at least one qualifying import-direction overload episode. WindowSet is retained only for IC-1/IC-2 AC-validation subset selection and diagnostics. | E1.S3b adaptive import windows span 19-25 weeks, or 36-48% of the year, defeating their compute purpose for the negligible-cost Tier-1 summation evaluator. Full-year Tier-1 removes window-transfer risk. | E1.S3b import-window diagnostic PR #15; `reports/import_window_diagnostic.md`; `reports/G1_DECISION_BRIEF.md`; PI approved in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G0-A3 | 2026-07-16 | Provisional overload threshold | Use the strict working event `L_import > 1.1 p.u.` for at least four consecutive 15-minute steps. The same 1.1 threshold applies to the single-step sensitivity and export-side exceedance diagnostic. This numerical threshold is provisional: Q-5 must be reviewed and explicitly resolved by the PI before the first integrated event-based scientific analysis or any manuscript result. | Allows the implementation to proceed with the PI-selected 110% one-hour rule while preventing an unverified source or ambiguous hourly interpretation from becoming a settled Dutch DSO claim. Historical evidence generated at 1.0 p.u. remains labeled with its executed threshold and is not relabeled. | PI direction in chat, 2026-07-16; source and exact interpretation pending Q-5. | approved working rule; mandatory pre-analysis review | PI directed in chat, 2026-07-16 |
| G0-A4 | 2026-07-17 | Primary planning year | Freeze 2035 as the primary planning year for the complete probabilistic analysis and decision-reversal benchmark. E3.S2b still screens 2030, 2033, and 2035 deterministically; 2030 and 2033 remain supporting horizon/context and later sensitivity layers. G5 may select the adoption/scenario branch and grid within 2035, but may not select the year after inspecting results. If the predeclared 2035 screen is congestion-free or not flexibility-resolvable, stop and escalate for a signed amendment rather than silently switching years or tuning inputs. EV-004 remains unchanged: the fixed ElaadNL residential behavior library uses generator year 2030 and is reused in the 2035 planning layer. | Selects a forward case-study horizon prospectively, before integrated probabilistic results, while preserving earlier years for trajectory checks and the eventual deferral horizon. Separating planning year from profile-generator year prevents double counting ElaadNL internal forecast growth and the project's external adoption layer. | PI direction in chat, 2026-07-17; EV-004; E3.S2b/G1-A2 capacity-screen protocol. | approved | PI approved in chat, 2026-07-17 |
| G1 | 2026-07-10 | Foundation validated | Approved two-tier architecture: Tier-1 radial summation with G0-A1/G0-A2 semantics is the Monte Carlo inner-loop evaluator; AC power flow serves deterministic checks and validation subsets. Fixed winter windows are rejected, and primary Tier-1 runs the full planning year. No manuscript claim may say "AC infeasible". E1.S2 established that repeated high-level `runpp` is too slow for the MC loop; E1.S2b subsequently established a fast lower-level TimeSeriesCPP path for deterministic AC batches while deferring complete adapter numerical validation to G2. C1 TimeSeriesCPP benchmarking and C2 transformer-headroom diagnostics are complete; Agent A may proceed to E1.S4. | Tier-1 is computationally negligible for the decision-transformer criterion, but its accuracy remains a G2 hypothesis. E1.S3 rejected fixed winter windows; E1.S3b showed adaptive windows are too large to justify a primary windowed probability. E1.S2b makes substantial AC validation practical without supporting an "AC infeasible" or "full AC MC" claim. | E1.S2 benchmark; E1.S2b PR #23 and `reports/BENCHMARK_TIMESERIESCPP.md`; E1.S1b PR #19; E1.S3b import-window diagnostic PR #15; `reports/G1_DECISION_BRIEF.md`; PI amended G1 text in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G1-A1 | 2026-07-13 | Black-box model error and Tier-1 approximation | Grid-model error is an unprobabilized interval on black-box model output, propagated before event detection under arbitrary unknown dependence. Tier-1 approximation error is estimated empirically at G2. Post-hoc probability-margin widening is rejected. G1-A2 supersedes the provisional error-composition and domain wording. | Preserves the intended imprecise-probability story, separates physical-system/model discrepancy from Tier-1-to-pandapower approximation, and retains the compute benefit of Tier-1 without hiding surrogate error. | `reports/G1_A1_MODEL_ERROR_AMENDMENT_PROPOSAL.md`; PI approval in chat, 2026-07-13. | approved | PI approved in chat, 2026-07-13 |
| G1-A2 | 2026-07-14 | Grid-error and capacity-screen protocol | Use a symmetric relative `epsilon_grid` envelope with arbitrary unknown dependence and compose it exactly with the additive G2 Tier-1 envelope before event detection. Reject the fixed 16-104 MVA applicability claim. Derive and freeze the asserted future operating domain from one predeclared manifested E3.S2b screen before probabilistic-result inspection. Keep total 80 MVA and firm 40 MVA capacity conventions open until that screen reports raw MVA and both ratios; selecting firm capacity requires actual one-transformer-out AC validation. | The 104 MVA value was only 1.3 times the current 80 MVA denominator, not a validated boundary. Relative grid error survives a later capacity-convention choice. A single governed future-layer screen can expose whether the total or firm convention yields no congestion, decision-sensitive congestion, or irrecoverable congestion without silently tuning the network after seeing p-box results. | `reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md`; E1.S1b headroom evidence; PI approval in chat, 2026-07-14. | approved | PI approved in chat, 2026-07-14 |
| E5-S3-T1 | 2026-07-17 | Proposed IC-2/IC-3 output-error schema | Proposed: use the current IC-2 loading trajectory payload as the sample-level boundary to IC-3, requiring unwidened `p_net_kw`, `screening_loading_pu`, direction masks, threshold, persistence length, time-domain flag, and primary-domain flag; add an IC-3 `OutputErrorEnvelope` with `epsilon_grid`, `epsilon_tier1_minus`, and `epsilon_tier1_plus`. IC-3 would compose endpoint trajectories by G1-A2, gate direction using unwidened `P_net`, run the episode detector on lower/upper trajectories, and compute probabilities/CIs from lower/upper event counts. | This is the smallest change that avoids boolean-only sample evaluation, keeps current Tier-1 diagnostics backward compatible, supports symmetric/asymmetric/one-sided Tier-1 envelopes, preserves CRN identity, and prevents post-hoc probability widening. | `reports/E5_S3_OUTPUT_ERROR_SCHEMA_PROPOSAL.md`; Q-6. | proposed; pending PI approval | -- |
| ALEA-001 | 2026-07-15 | Joint aleatory dependency protocol | Preserve known dependence through one canonical calendar, complete source trajectories, and one paired multivariate weather member per Monte Carlo realization. HP and PV consume the same aligned weather member; EV and baseline retain complete temporal paths and common weekday/season alignment. Copulas, latent factors, or multivariate block bootstrap are escalation paths only if validation shows the primary conditional construction is inadequate. | Keeps physically understood temperature/irradiance, calendar, serial, and common-driver dependence without inventing an unsupported full joint distribution. It also separates physical dependence from CRN reuse and from the arbitrary-unknown-dependence treatment of model error. | `reports/JOINT_ALEATORY_SAMPLING_PROTOCOL.md`; PI approval in chat, 2026-07-15. | approved | PI approved in chat, 2026-07-15 |
| ALEA-002 | 2026-07-15 | Downstream-only congestion evaluation | Component-level profile statistics are data-quality diagnostics only. Congestion and profile-library adequacy are evaluated after baseline, EV, HP, PV, adoption, and flexibility have been aligned and aggregated into net load and passed through the transformer evaluator. An EV-only sustained-load statistic and the ElaadNL UI p95 curve are not congestion measures. A p95 downstream result may be used provisionally for workflow and convergence checks while the PI reviews published congestion definitions; this does not amend the G0 `P_crit` decision. | Prevents an arbitrary component proxy from determining a system-level reinforcement conclusion and tests finite-library adequacy against the quantity the study ultimately uses. | `reports/JOINT_ALEATORY_SAMPLING_PROTOCOL.md`; PI approval in chat, 2026-07-15. | approved | PI approved in chat, 2026-07-15 |
| G2 | TBD | Tier-1 enclosure and adequacy | Pending: empirical Tier-1 error envelope, held-out near/above-threshold enclosure test, decision impact, and evaluator verdict | Determines Tier-1 primary / corrected Tier-1 / selective AC / Tier-1 rejected | E1.S2b corrected AC budget; E1.S1b headroom brief; E3.S2b frozen future domain/capacity screen; E3.S3 manifested tier comparison | pending | -- |
| G3 | TBD | Monotonicity verdict | Pending: vertex shortcut vs interior sampling | Critical compute shortcut | E4.S1 monotonicity report | pending | -- |
| G4 | TBD | Elicitation sign-off | Pending: fuzzy controllability corners | Paper hinge assumption | E7.S2 worksheet | pending | -- |
| G5 | TBD | Case selection | Pending: 2035 decision-reversal benchmark adoption/scenario and grid case; year is fixed by G0-A4 | Money figure depends on divergent treatments, but the year may not be selected after inspecting results | E8.S1 case sweep | pending | -- |
| G6 | TBD | Results freeze | Pending: paper numbers locked to manifests | Required before manuscript finalization | E9 robustness; E10.S1 figure dry-run | pending | -- |
| G7 | TBD | Submission | Pending: approve Applied Energy submission | Final paper gate | Manuscript, repro package, red-team report | pending | -- |
| DEP-001 | 2026-07-09 | Dependency pin update | Use `simbench==1.6.2` and `pandapower>=3.4,<4` in the `.venv` requirements. | Upstream SimBench 1.6.2 declares `pandapower>=3.4.0`; avoids the older `simbench==1.6.1` / `pandapower==3.5.3` top-level `compare_arrays` import break. | PI review of upstream `simbench` `pyproject.toml`; `.venv` metadata check; `.\scripts\task.ps1 test`; direct import check for `pandapower`, `simbench`, and `lightsim2grid`. | approved | PI approved in chat, 2026-07-09 |
| EV-001 | 2026-07-10 | D-002 EV charging data source | Use the ElaadNL Laadprofielengenerator generated-profile route in `reports/elaad_profile_generation_spec.md` for D-002 instead of the unavailable historical ElaadNL/EVnetNL transaction dataset. First implementation step is a one-profile API probe; bulk profile-library generation waits until API semantics and terms-of-use notes are recorded. | The current ElaadNL download page exposes a Charging Energy Hubs neighbourhood opportunity workbook, not session/profile behavior data. The generator provides accessible, seeded, 15-minute Dutch Outlook-based EV charging profiles suitable for a frozen profile library or calibration target. | PI-provided profile-generation spec; local inspection of `data_CEH_kansrijkheid_2026Q1.xlsx`; ElaadNL dashboard/API URLs in D-002. | approved | PI approved in chat, 2026-07-10 |
| EV-002 | 2026-07-14 | D-002 generated ElaadNL profile use and redistribution boundary | Generated ElaadNL profiles may be used for internal project computations through the publicly accessible Laadprofielengenerator API. Do not commit or redistribute raw API responses or generated profile libraries; keep generated files under ignored `data/raw/` or ignored processed-data paths. Commit only retrieval/generation code, request configurations, distinct seed schedules, metadata, checksums, and manifests. The data-availability statement must direct readers to regenerate profiles through the public API subject to terms applicable at retrieval time. Do not claim generated profiles are openly licensed or redistributable. Record unresolved redistribution terms as a limitation/risk, but they no longer block internal project use. If explicit terms later prohibit this research use, stop and escalate. | Resolves the D-002 terms blocker while preserving a conservative redistribution boundary and reproducibility through code/config/metadata rather than committed generated data. | PI decision in chat, 2026-07-14; D-002 one-profile probe metadata; `reports/elaad_profile_generation_spec.md`. | approved | PI approved in chat, 2026-07-14 |
| EV-003 | 2026-07-15 | Primary EV aleatory representation | Use direct empirical bootstrapping from the frozen, checksummed ElaadNL annual profile library as the primary EV aleatory model. Retain complete annual members and record the selected member IDs and seed metadata in manifests. The fallback calibrated stochastic sampler is not primary, but remains an escalation path if seed semantics, available library size, or held-out downstream adequacy make direct bootstrapping invalid. The exact within-realization replacement rule remains pending until the same-seed warning and adoption cohort sizes are resolved. | Uses the accessible Dutch generator output without introducing an additional fitted behavioral model, while keeping finite-library uncertainty visible and testable under ALEA-002. | EV-001; EV-002; ALEA-001; ALEA-002; `reports/elaad_profile_generation_spec.md`; PI approval in chat, 2026-07-15. | approved | PI approved in chat, 2026-07-15 |
| EV-004 | 2026-07-16 | Fixed residential charge-point distribution | Represent the residential EV layer by one frozen distribution of complete annual, uncontrolled ElaadNL `cp` profiles for `location_type = home`, `cp_capacity_kw = 11`, and `simulated_year = 2030`. Reuse this behavior distribution in the 2030, 2033, and 2035 planning layers; scenario growth changes the externally sourced number and nodal allocation of home charge points, not the profile-generator year. The sampling unit is one physical home charge point, and ElaadNL's native home charge-point car/van mix is retained without reweighting. Conditional on the common ALEA-001 calendar and scenario, home charge points are modeled as exchangeable independent draws from this distribution. Public charging remains a separate profile class and is not fixed by this decision. | Fixing the generator year prevents its internal vehicle-count, charge-point-count, and efficiency forecasts from being varied at the same time as the project's external adoption layer. A charge-point sampling unit also matches the physical quantity counted by the adoption scenario and lets one fixed behavior distribution be reused transparently across planning layers. | ElaadNL `Documentatie Laadprofielengenerator`, 10 November 2025, pp. 5-13; ALEA-001; EV-003; PI approval in chat, 2026-07-16. | approved | PI approved in chat, 2026-07-16 |
| EV-005 | 2026-07-16 | Finite profile-library uncertainty | Treat the frozen library as a finite random sample from an unknown ElaadNL generator distribution. Keep finite-library uncertainty from `M` distinct from conditional Monte Carlo estimation uncertainty from `N`: use independent distinct-seed API batches, nested candidate libraries, disjoint held-out batches, and downstream transformer-result comparisons under CRN. An initial candidate of `M = 1000` home charge-point profiles may be generated in batches, but it is not declared sufficient a priori; extend it if the predeclared downstream adequacy test fails. The numerical adequacy tolerance and the within-realization replacement rule remain pending until E2.S6 supplies the charge-point cohort range and E3.S2a predeclares a decision-relevant criterion. | Increasing `N` can estimate the result under a fixed empirical library very precisely without correcting an unrepresentative library. Independent held-out generation and nested-library stability expose that separate error source while avoiding an unsupported universal formula linking `M`, `K`, and `N`. | `reports/EV_FINITE_LIBRARY_UNCERTAINTY_PROTOCOL.md`; ALEA-002; EV-003; E2.S6; E3.S2a; PI approval in chat, 2026-07-16. | approved | PI approved in chat, 2026-07-16 |
| EV-006 | 2026-07-17 | Matched ElaadNL smart-charging seed protocol | When an ElaadNL smart-charging profile is generated as a counterfactual to an uncontrolled profile, reuse the exact uncontrolled batch seed and pair members by returned profile index. Identify each potential-outcome pair by `(batch_seed, returned_profile_index, control_mode)`. Same-seed uncontrolled and controlled outputs represent the same underlying annual demand and charging sessions under different control; compare or substitute them as a pair, but never sum or resample them as independent physical charge points. Seeds remain distinct between unrelated stochastic source batches, including candidate and held-out libraries. Set D therefore matches uncontrolled Set A batch `140001` instead of using an independent seed. This decision fixes pairing semantics only: it does not approve smart charging as the primary flexibility model or approve its base-capacity, ramp-speed, pooling, or controllability mapping. | ElaadNL explicitly states that a common seed preserves annual mileage, energy demand, and sessions and is useful for studying smart-control impacts, while warning that same-seed profiles must not be added because their sessions are duplicated. Matched treatment/control runs remove behavioral sampling noise from the comparison without violating the independence required when profiles represent different chargers. | ElaadNL `Documentatie Laadprofielengenerator`, 10 November 2025, pp. 6-7 and 14; `reports/elaad_profile_generation_spec.md`; PI instruction in chat, 2026-07-17. | approved seed protocol; smart-control role and parameters pending | PI directed correction in chat, 2026-07-17 |
| COST-001 | 2026-07-10 | D-008 Cicenas thesis unit-cost source | Use the PI-supplied local Cicenas 2025 thesis PDF as the D-008 source for unit-cost extraction. The PDF must not be committed or redistributed. Every extracted number must record value, unit, exact meaning/context, thesis page, table/appendix/section label if available, source status (Stedin-confirmed, thesis-derived, or interpreted), intended project use, and PI sign-off before manuscript use. | The professor of the thesis is involved in the project, and the PI confirmed that thesis-derived unit costs are acceptable if every number is exactly traceable and cited wherever used. | Local raw file `data/raw/cicenas_2025_thesis.pdf`, sha256 `96EF9625BA0AFEE2910189A61967943BA3BCD460AE3AC080B847C4D8DD7D99C0`; literature-review anchor line 133. | approved | PI approved in chat, 2026-07-10 |

## G0 - Scope Freeze - 2026-07-09 - signed: PI approved in chat

Authority: this entry supersedes all illustrative examples of the overload
event, P_crit handling, and grid choice in the project plan and the actionable
plan. G0-A1 amends the event direction rules below. G0-A2 amends the primary
event time domain to the full planning year and demotes WindowSet to AC
validation and diagnostics. G0-A3 supersedes the numerical `1.0 p.u.` event
threshold below with a provisional `1.1 p.u.` working threshold and imposes a
mandatory PI review before integrated event analysis. G0-A4 freezes 2035 as
the primary planning year while retaining 2030 and 2033 as supporting layers.
Changes to any item below require a new signed entry.

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

Historical G0 wording is retained below for traceability. G0-A3 supersedes its
numerical `1.0 p.u.` threshold for future work; historical runs keep the
threshold recorded in their manifests.

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
`L_import(t) > 1.0` p.u., meaning at least 1 hour, over the full planning year
per G0-A2. A direction flip resets the episode counter. Every results table
reports export-direction exceedance of `L_export` alongside `P(E)`.

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

`P_crit` is frozen. Per G0-A4, the primary planning year is also frozen at
2035. Case interestingness is achieved at G5 only by selecting the declared
adoption/scenario branch and feeder/grid within 2035. It is never achieved by
threshold adjustment or by switching the primary year after inspecting
results.

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
adoption layer with zero flexibility over the full planning year using the
G0-A1/G0-A2 import-direction loading semantics, indicating electrification
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

## G0-A1 - Event Direction And Fixed-Window Rejection Amendment - 2026-07-10 - signed: PI approved in chat

Authority: this entry amends G0 item 2, the G0 fallback-screen loading
interpretation, and the critical-window examples in the project/actionable
plans. G0-A2 supersedes the adaptive critical-window language for the primary
Tier-1 probability metric. Where this entry conflicts with earlier text, and
G0-A2 does not further amend it, this entry wins.

G0-A3 later supersedes only the numerical overload threshold in this entry.

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

The fixed-winter-window assumption is retired. G0-A2 records the G1 outcome:
adaptive import-ranked WindowSets are retained for IC-1/IC-2 AC-validation
subset selection and diagnostics only, not for the primary Tier-1 probability
metric.

For diagnostic WindowSets, select adaptively per `(scenario, year, technology
layer)` from the import-direction loading ranking: use top-K import-ranked
weeks plus 1 margin week, with K documented from the coverage-vs-K curve.
These WindowSets do not alter the full-year event definition.

### 3. G3 Linkage

Monotonicity of `P(E)` in controllable demand reduction `rho` is claimed and
tested for the import-direction event only. The E1.S3 direction-agnostic
screen confirmed that export/PV feed-in can bind in SimBench future scenarios.
If export congestion is ever brought into scope, it requires the interior
sampling path and a distinct fuzzy flexibility instrument for absorption or
curtailment.

## G0-A2 - Full-Year Primary Event Scope - 2026-07-10 - signed: PI approved in chat

Authority: this entry amends G0 item 2 and supersedes the G0-A1 adaptive
critical-window language for the primary probability metric. Where it conflicts
with earlier project-plan or actionable-plan text, this entry wins.

G0-A3 later supersedes only the numerical overload threshold in this entry.

Primary `P(E)` is annual: the probability that the full planning year contains
at least one qualifying import-direction overload episode, defined as at least
4 consecutive 15-minute steps with `L_import(t) > 1.0` p.u. A direction flip
resets the episode counter.

Tier-1 Monte Carlo evaluates the full planning year. `WindowSet` remains in
IC-1 and IC-2 for AC-validation subset selection and diagnostics only. It is
not part of the primary Tier-1 event definition.

Rationale: E1.S3b adaptive import windows span 19-25 weeks, or 36-48% of the
year. At that size, they defeat their compute purpose for the vectorized
Tier-1 summation evaluator and introduce avoidable window-transfer risk.
Full-year Tier-1 removes that approximation layer.

## G0-A3 - Provisional 1.1 P.U. Overload Threshold - 2026-07-16 - signed: PI directed in chat

### Authority And Working Event

This entry supersedes the numerical `1.0 p.u.` threshold in G0, G0-A1, and
G0-A2 for future implementation and analysis. It does not alter the import
direction gate, apparent-power loading quantity, direction-flip reset,
four-step persistence rule, full-year probability domain, or `P_crit`.

The working event is:

```text
E = the planning year contains at least 4 consecutive 15-minute steps
    with L_import(t) > 1.1 p.u.
```

The inequality is strict: a value exactly equal to `1.1 p.u.` does not qualify.
The single-step E9 sensitivity and export-side exceedance diagnostic use the
same working `1.1 p.u.` threshold unless a later signed decision states
otherwise.

### Mandatory Pre-Analysis Review

The value is PI-selected but provisional because its supporting source and
precise time-aggregation semantics have not yet been verified. Q-5 must be
explicitly resolved before E3.S2a opens held-out event results, E3.S2b or E3.S3
runs a threshold-based integrated screen, E4 estimates `P(E)`, or any manuscript
result uses this event. The review must establish:

- the exact source and its asset, jurisdiction, and capacity convention;
- whether "one hour" means four consecutive 15-minute exceedances or an hourly
  average;
- whether loading from `1.0` through `1.1 p.u.` needs a separate cumulative-
  exposure criterion; and
- whether `1.1 p.u.` is retained as primary, demoted to sensitivity, or replaced.

Historical evidence generated with a manifested `1.0 p.u.` threshold remains
valid for its stated diagnostic purpose and must not be relabeled as a 1.1-p.u.
run.

## G0-A4 - Primary 2035 Planning Year - 2026-07-17 - signed: PI approved in chat

### Primary And Supporting Years

The complete primary probabilistic analysis and E8 decision-reversal benchmark
use planning year 2035. This year is frozen prospectively, before the integrated
probabilistic results are inspected. E3.S2b still runs the predeclared
deterministic screen for 2030, 2033, and 2035. The 2030 and 2033 layers remain
supporting trajectory checks and inputs to the later deferral-horizon analysis;
they are not alternative primary years available for post-hoc selection.

### Routing Rule

G5 may select the declared adoption/scenario branch and feeder/grid within
2035. If the predeclared screen classifies the 2035 layer as having no relevant
congestion or congestion that is not flexibility-resolvable under the
admissible capacity conventions, work must stop for a signed amendment. Agents
must not silently switch to another year, change a frozen threshold, or tune
network or adoption inputs after inspecting the probabilistic results.

### Profile-Generator Year

This decision does not change EV-004. The primary residential EV behavior
library remains generated with ElaadNL `simulated_year = 2030` and is reused in
the 2035 planning layer. The project's external adoption counts and nodal
allocation represent 2035 growth, avoiding double counting the generator's
internal year-dependent outlook assumptions.

## G1 - Foundation Validated - 2026-07-10 - signed: PI approved in chat

### Approved

Two-tier compute architecture. Tier-1 radial summation, per G0-A1 direction
semantics and G0-A2 full-year event scope, is the Monte Carlo inner-loop
evaluator because it is near-exact for the transformer criterion and
computationally negligible. AC power flow serves deterministic checks and
validation subsets.

The E1.S2 benchmark establishes only that the pandapower `runpp` path,
approximately 105 ms per solve on the 117-bus primary grid, cannot host the
Monte Carlo loop. It does not establish infeasibility of `lightsim2grid`'s
lower-level path, whose flag showed no speedup and likely never engaged. No
"AC infeasible" claim may appear in the manuscript.

### Approved With Change

Fixed winter windows are rejected, based on E1.S3 evidence. However, adaptive
windows spanning 19-25 weeks, or 36-48% of the year, defeat their compute
purpose in Tier-1. Tier-1 therefore runs the full planning year, and the event
definition drops the window clause per G0-A2: `P(E)` is the probability of at
least one qualifying episode in the planning year.

`WindowSet` is retained in IC-1 and IC-2 for AC-validation subset selection and
diagnostics only.

### Conditions Before G2

`C1`: Benchmark the `lightsim2grid` `TimeSeriesCPP` adapter properly and
diagnose the absent `runpp` speedup. Report the corrected AC validation budget.

`C2`: Produce a headroom diagnostic memo: substation transformer ratings; peak
import MVA versus total and firm `(n-1)` aggregate nameplate; implied 2035 load
multiplier under both definitions. The memo must flag the anticipated
G0-item-4 escalation and the firm-capacity redefinition option for PI decision.

`C3`: Agent A proceeds to E1.S4 with G0-A1 semantics
(`import`/`export`/`screening` series and direction-flip episode reset) and
G0-A2 full-year event scope.

### Unchanged From Draft

Export exceedance is reported alongside all primary results. No Dutch
2030/2033/2035 window or loading claims may be made before E2/E3. No vertex
shortcut may be used before G3. Agent C remains blocked on D-002 ElaadNL terms.

## G1-A1 - Black-Box Model Error And Tier-1 Approximation - 2026-07-13 - signed: PI approved in chat

### Authority And Scope

This entry amends G1, the G2 gate, E5.S3, and the behavioral boundary between
IC-2 and IC-3. It supersedes any wording that applies fixed margins directly
to an already estimated overload probability. At G1-A1, exact error values,
units, form, symmetry, the G2 numerical adequacy criterion, and the exact IC
schema change remained deferred; G1-A2 subsequently freezes relative symmetric
grid-error form while retaining the other stated dependencies.

G1's earlier description of Tier-1 as "near-exact" is a hypothesis pending the
G2 held-out enclosure result, not an established manuscript claim.

### Black-Box Grid-Model Error

The project has no field measurements that validate the DSO planning model
directly against physical loading. The grid-model discrepancy `delta_grid` is
therefore an author-specified interval assumption unless later evidence or a
human sign-off supplies stronger provenance; it is not an empirically
determined quantity within this project. Its numerical value, asserted domain,
units/form, and mandatory sensitivity sweep must be recorded in a signed
`ASSUMPTIONS.md` row before paper results use it. Any future empirical
validation must be recorded together with its validated domain.

No probability distribution is assigned to `delta_grid`. The analysis admits
every discrepancy function within the signed envelope, including arbitrary
unknown dependence on aleatory inputs `X`, flexibility controllability `rho`,
and time. This is neither probabilistic independence nor one constant bias.

### Tier-1 Approximation Error And Interval Composition

Tier-1 is a computational approximation to pandapower. G2 shall empirically
characterize

```text
delta_Tier1(X, rho, t) = L_PP(X, rho, t) - L_T1(X, rho, t)
```

over the operating domain used by the paper. G1-A2 later froze
`epsilon_grid` as relative and the Tier-1 enclosure as additive, so a simple
sum of their numerical values is not the current composition. Use the exact
G1-A2 endpoint formulas. If G2 supports asymmetric or one-sided Tier-1
endpoints, that tighter form is retained. No cancellation or root-sum-of-
squares combination is allowed without a later signed dependence model.

### Event And Probability Propagation

The applicable output-error interval is applied to each loading trajectory
before the G0-A1/G0-A2 four-consecutive-step event detector. Lower and upper
event indicators are evaluated from the lower and upper loading endpoints, and
Monte Carlo confidence intervals are computed from those resulting event
counts. Probability estimates or their confidence intervals are never shifted
after estimation to represent grid-model error.

The G0-A1 import/export gate is evaluated on the unwidened `P_net` sign. The
error envelope widens loading magnitude only. The rationale is that direction
ambiguity is confined to the zero crossing, where loading is expected to be
event-irrelevant; G2 must check this and escalate any counterexample.

The pure interval error has the same support at every alpha level and is never
probabilized or defuzzified. Before G3, `rho` still requires the approved
interior-sampling path. If G3 confirms monotonicity, the lower vertex combines
the favorable `rho` endpoint with the lower loading-error endpoint and the
upper vertex combines the adverse `rho` endpoint with the upper loading-error
endpoint.

### Revised G2 Gate

G2 shall use a manifested, domain-covering AC validation design spanning
ordinary, extreme, near-capacity, and overloaded import states; the current
G0-A3 `1.1 p.u.` threshold neighborhood; relevant years, `rho` values, power
factors, and consecutive-step episodes. A held-out near/above-threshold stratum must not be
used to tune an envelope or correction.

A hard enclosure acceptance test on that held-out stratum is frozen in kind.
Its numerical strictness, including whether 100% bracketing is required, must
be signed before the held-out result is inspected. Failure prevents an
unqualified "Tier-1 adequate" verdict.

G2 must recommend exactly one of: Tier-1 adequate; Tier-1 adequate with a
validated correction; selective AC for predeclared threshold-straddling states
or episodes; or Tier-1 rejected. Selective AC must preserve CRN and manifest
discipline and record the promotion rule before execution.

### Envelope Form And Interface, As Amended By G1-A2

G1-A2 selects a relative symmetric grid-error envelope because it is invariant
to the total-versus-firm `(n-1)` `S_nom,agg` convention. The additive Tier-1
endpoints established at G2 remain expressed in the selected loading-p.u.
convention and use the exact mixed composition in G1-A2.

IC-2/IC-3 must retain enough information to apply the interval before episode
classification and to preserve the unwidened direction gate. A boolean-only
sample callback is noncompliant. Agents A and B must propose the smallest
compatible schema change for separate PI approval before E5.S3 implementation.

PR #13 requires revision: its useful configuration and invariant-test
structure may be retained, but probability-domain widening must be replaced by
output-domain trajectory propagation and four-step event tests.

## G1-A2 - Grid-Error And Capacity-Screen Protocol - 2026-07-14 - signed: PI approved in chat

### Authority And Scope

This entry amends G1-A1, A-013, G2, E3.S3, and E5.S3. It freezes the error
form, dependence treatment, composition rule, direction-gate order, and the
process for defining the operating domain and choosing the capacity
convention. It does not sign a numerical value for `epsilon_grid`; the draft
5% reference and 2%/10% sensitivities remain proposed pending evidence review
and a later PI sign-off of A-013.

### Grid-Error Form And Dependence

`epsilon_grid` is a symmetric relative envelope on the physical loading that
would be obtained at the DSO model boundary. Within this project it is an
author-specified scenario assumption, not an empirically measured bound,
confidence interval, or completed expert elicitation. No distribution is
assigned to it. Its dependence on inputs, controllability, time, and Tier-1
error is arbitrary within the envelope; independent sampling, root-sum-of-
squares combination, and a constant-bias interpretation are prohibited.

### Exact Composition

Let `L_T1(t)` be nonnegative Tier-1 loading. Let the G2 additive Tier-1
enclosure be `epsilon_Tier1_minus` and `epsilon_Tier1_plus`, expressed in the
same loading-p.u. convention as `L_T1`. For `0 <= epsilon_grid < 1`, define

```text
L_PP_lower(t) = max(0, L_T1(t) - epsilon_Tier1_minus)
L_PP_upper(t) =        L_T1(t) + epsilon_Tier1_plus

L_lower(t) = (1 - epsilon_grid) * L_PP_lower(t)
L_upper(t) = (1 + epsilon_grid) * L_PP_upper(t)
```

If G2 accepts a symmetric Tier-1 envelope, both Tier-1 endpoints equal
`epsilon_Tier1`. The lower and upper trajectories are passed through the
four-consecutive-step event detector. The import/export gate is evaluated on
the unwidened `P_net` sign before loading is widened. Event probabilities and
Monte Carlo confidence intervals are computed from the endpoint event counts;
probabilities are never widened afterwards.

### Operating Domain

The earlier illustrative `16-104 MVA` or `0.2-1.3 p.u.` applicability range is
rejected. In particular, 104 MVA was only `1.3 * 80 MVA`; no measurement,
simulation result, or primary source established it as a validity boundary.

After EV, heat-pump, PV, adoption, and net-load layers are integrated, E3.S2b
shall run one versioned and manifested deterministic screening experiment over
the predeclared 2030/2033/2035 cases and flexibility endpoints. Before any
probabilistic result is inspected, its input ranges and resulting physical-MVA
span shall define and freeze the asserted operating domain used by A-013 and
the G2 validation design. Later samples outside that domain are flagged and
escalated; they are not silently extrapolated, clipped, or used to refit the
domain.

### Total Versus Firm Capacity

For the present two-unit bank, the candidate denominators remain total
nameplate `80 MVA` and firm `(n-1)` nameplate `40 MVA`. E3.S2b shall report raw
transformer MVA and loading under both conventions for every screened case.
The PI shall then select the convention using planning meaning, Dutch-practice
evidence where available, and whether flexibility can materially change the
decision. A convention shall not be selected solely because it manufactures
an interesting congestion case. If neither convention supports a usable case,
the existing G0 fallback/escalation route applies and any load or network
adjustment must be explicit, sourced, and signed before use.

Dividing normal two-transformer flow by 40 MVA is a headroom diagnostic only.
If firm capacity becomes the primary criterion, E3.S3 must model and validate
the actual one-transformer-out topology with AC power flow; G0/A-005/A-013 and
the G2 domain must then be amended to cover that operating state.
