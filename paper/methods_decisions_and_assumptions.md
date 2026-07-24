# Standalone Methods Paragraphs for Decisions and Assumptions

This file is the manuscript-facing companion to the project registers. Each
entry is deliberately standalone so it can later be edited and assembled into
the final Methods section. The authority and status of every item remain in
`registers/DECISIONS.md`, `registers/ASSUMPTIONS.md`, and
`registers/DATA_REGISTER.md`; prose here never signs or upgrades a register
entry.

Status labels have the following meaning:

- **Approved:** the paragraph may be used, subject to normal manuscript editing
  and citation verification.
- **Proposed:** the paragraph records the intended defense but must not be used
  as a settled claim before PI sign-off.
- **Not invoked:** the assumption was predeclared but its triggering condition
  did not occur.
- **Pending gate:** no decision exists yet; the placeholder must be replaced in
  the same PR that records the decision.

## Assumption and Inference Inventory

This inventory is a reviewer-facing index of modelling assumptions and inferred
data meanings that materially affect the analysis. It does not replace the
same-ID paragraphs below or the authority of the registers; it is included so
the manuscript methods cannot hide an assumption inside a data-loader choice,
column name, or implementation convention. When an item is only proposed or
inferred, paper-facing results must keep it labelled that way until the PI signs
the corresponding register row.

### Formal Assumption Register Inventory

<!-- assumption-inventory-start -->
| ID | Methods issue to keep visible | Register status |
|---|---|---|
| `A-001` | `P_crit` and sensitivity thresholds used to define decision relevance. | proposed |
| `A-002` | Alpha-grid resolution for fuzzy/p-box reporting. | proposed |
| `A-003` | Benchmark network family and fallback network candidates. | proposed |
| `A-004` | Report alpha-indexed bounds only; no defuzzified probability answer. | proposed |
| `A-005` | Parallel decision-transformer aggregation as one substation asset. | proposed |
| `A-006` | Tier-1 reactive-power treatment through assigned nodal power factors. | proposed |
| `A-007` | Dutch weather applied to German-measured SimBench baseline profiles. | proposed |
| `A-008` | Grid-routing thresholds are case-selection heuristics, not standards. | proposed |
| `A-009` | Superseded EV generator-year fallback. | superseded |
| `A-010` | Superseded combined EV charging-power assumption. | superseded |
| `A-011` | Superseded vehicle-level Elaad profile scaling assumption. | superseded |
| `A-012` | Import/export sign convention and direction-flip episode reset. | proposed |
| `A-013` | Symmetric relative grid-model discrepancy with unknown dependence; numerical values unsigned. | proposed |
| `A-014` | Load-proportional EV adoption allocation across SimBench load nodes. | approved for second-stage use after local totals |
| `A-015` | PBL Startanalyse D-013 suffix/indicator mapping for residential HP scaling. | approved for D-013 indicator mapping only |
| `A-016` | EV/HP/PV 2035 source and scenario-lineage consistency must be checked before integrated analysis. | approved consistency requirement |
<!-- assumption-inventory-end -->

### Additional Modelling and Data-Inference Boundaries

| Scope | Assumption or inference | Current methods treatment |
|---|---|---|
| G0/G0-A1/G0-A3 | The study is scoped to import-direction planning congestion, with a strict persistent `L_import > 1.0` p.u. primary event and `1.1`/`1.2` p.u. sensitivities. | Approved by G0-A1/G0-A3; export congestion is reported as a diagnostic, not solved by the demand-flexibility instrument. |
| G0-A4/EV-004 | The primary planning year is 2035, while the residential ElaadNL behaviour library uses fixed generator year 2030. | Approved distinction; avoids double counting generator-year growth and external 2035 adoption. |
| G1/G1-A2/E5-S3-T1 | Tier-1 is the Monte Carlo evaluator only after G2 validates its envelope; grid-model discrepancy is an interval with arbitrary unknown dependence, not an independent random variable. | Approved protocol; numerical A-013 and G2 Tier-1 values remain unsigned. |
| G1-A2 | Total 80 MVA versus firm 40 MVA capacity remains open until the manifested future-layer screen and any required one-transformer-out AC validation. | Approved protocol; no paper-facing capacity convention has been selected. |
| ALEA-001/ALEA-002 | Known dependence is preserved through complete calendars and paired weather members; congestion and library adequacy are evaluated only after aggregation. | Approved protocol; component percentiles remain diagnostics only. |
| EV-003/EV-005/EV-005B | EV libraries are finite candidate samples; EV-005B approves charge-point-level replacement for candidate member selection only, not proof that `M` is sufficient. | EV-005B is approved only for candidate selection metadata; held-out adequacy and `M` sufficiency remain deferred to E3.S2a. |
| EV-CAL-001 | EV source profiles are mapped to the planning calendar by ordinal timestep, preserving annual sequence but not actual 2035 weekday/holiday identity. | Approved limitation; provenance must record the mismatch. |
| EV-008A/D-012 | Public EV profiles use an equal 25% split across 11/13/15/22 kW AC classes. | Approved for source generation only; it simplifies an NDW snapshot and is not a precise fleet forecast. |
| HP-001/D-003 | When2Heat provides Dutch residential shape/COP trajectories for SFH/MFH space heat and domestic hot water; commercial heat is excluded. | Approved source/technology boundary; local annual scaling and paired-weather acceptance remain separate gates. |
| D-013/HP local scaling | PBL `H23_Vraag_RV_w` and `H24_Vraag_TW_w` are treated as residential space-heat and domestic-hot-water indicators under A-015/D013-PBL-MAPPING, but the exact raw-code meaning is still currently inferred from code pattern plus Startanalyse documentation rather than explicit PBL evidence for those literal labels. | Approved as a transparent assumption for indicator mapping only; annual TWh values, `Referentie_2030` value-column use, SFH/MFH split, 2035 adoption, and executable HP load remain separate gates. |
| D-013/CBS split | HP local heat is split over SFH/MFH using CBS Alkmaar dwelling counts, not measured class-specific heat demand. | Proposed route; count-share versus area-weighted split requires PI sign-off before executable values. |
| D004-MC-001/D004-SOURCE-MEMBER-ACCEPTANCE | KNMI Berkhout is the realized weather path for Alkmaar; hourly `T` and `Q` are expanded to 15-minute members, and PVGIS remains sanity/provenance only. | Approved for internal source/member use; final paired HP/PV validation and cold-spell tolerances remain pending. |
| PV-PARAM-001 | Proposed primary first-pass PV conversion uses capacity supplied by a separate signed capacity route such as PV-CAP-001, KNMI GHI as the realized irradiance basis, PR=0.86 from the PVGIS 14% reference loss, no temperature correction, clipping at supplied capacity, and PV-ORIENT-001 statistical orientation/tilt diversity once the distribution and conversion treatment are signed. | Proposed; fail-closed until PI signoff. |
| D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET | Proposed packet compares PV conversion-source routes after the PI concern with the simple direct-GHI/PR route: pvlib-style statistical-orientation/tilt plane-of-array candidate, PVGIS qualitative calibration/sanity context, and direct-GHI scalar fallback only if explicitly signed. | Proposed packet; formula and values unsigned. |
| D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET | Proposed first-experiment approval checklist separates installed capacity, statistical orientation/tilt distribution, irradiance-to-power conversion, and node allocation before executable PV use. | Proposed packet; executable PV blocked. |
| PV-CAP-001/D-014 | PV installed capacity is anchored to local Alkmaar CBS photovoltaic capacity and scaled to 2035 through a signed II3050/scenario growth factor; D-014 now has retrieved CBS Alkmaar source evidence, retrieved II3050 appendix evidence, an unsigned capacity value-choice packet, an unsigned capacity approval-template packet, an unsigned executable-readiness blocker packet, an unsigned executable preflight guard packet, an unsigned PV-PARAM conversion source-choice packet, an unsigned first-experiment approval packet, and proposed lightweight statistical orientation/tilt packets, while heavy 3DBAG/roof-level geometry is deferred until after the first real experiment. | Approved route; CBS/II3050/value-choice/template/blocker/preflight/conversion-choice/first-experiment approval evidence proposed; executable capacity value, capacity convention, II3050 scenario/growth factor, A-016 consistency, per-node allocation, statistical orientation/tilt source, weights, bins, and conversion treatment remain pending. |
| PV-ORIENT-001 | For the first real experiment, PV orientation and tilt are represented through a typical/statistical distribution rather than per-building, per-roof, or location-specific geometry; source-choice and value-choice packets now prepare unsigned evidence/assumption candidates for PI review. | Approved scope; packets proposed; exact source, weights, bins, capacity-weighting convention, and conversion treatment remain pending. |
| A-016/Scenario consistency | EV, HP, and PV may use different best-available sources, but their 2035 branches must be reconciled and manifested before integrated net-load/event analysis. | Approved consistency requirement; unresolved mismatch is a limitation or escalation, not a silent assumption. |
| EV-007A/A-014/D-010 | Alkmaar municipality is the local proxy for the synthetic SimBench case, and local counts are allocated across grid loads by static `p_mw`. | EV local totals and A-014 allocation are approved; this remains an illustrative-case transfer assumption. |
| A-013 | The candidate `epsilon_grid = 5%` with `2%`/`10%` sensitivities is not empirical or expert-signed. | Proposed only; E9.S5a evidence review is required before numerical use as a scientific claim. |
| E5.S4 | The math-core trust certificate requires both the analytic Gaussian cross-check and a published hybrid-propagation reproduction. | The analytic synthetic fixture now records tolerance, alpha-row nestedness, separate lower/upper CI containment, and no-defuzzification guards in `e5s4-math-core-trust-certificate-v1`; the published Baudrit-style reproduction remains fail-closed until verified source/example provenance is approved and reproduced, and G3 remains pending for paper-facing vertex shortcut claims. |
## Decisions

<!-- methods-id: G0 -->
### G0 - Scope Freeze

**Status: Approved. Decision asset and loading quantity.** The case study treats
the two parallel HV/MV transformers at the SimBench external-grid substation as
one decision transformer because reinforcement is decided at substation-bank
level. Loading is calculated as the magnitude of the complex aggregate
exchange, `abs(sum_i S_i)`, divided by aggregate nameplate. This representation
matches the net power that the upstream system must transfer and can be
evaluated consistently by both the fast summation model and AC power flow. It
is valid only when the units operate as a closed-tie, equal-tap parallel bank;
otherwise the asset must be redefined per section. The inventory identified two
in-service 40 MVA units with closed ties and equal taps, while G2 retains a
per-unit AC check for circulating-current or unequal-sharing effects.

**Status: Approved; primary threshold confirmed by G0-A3.** G0 defines an
overload event as at least four consecutive 15-minute intervals in which
import-direction apparent-power loading exceeds 1.0 p.u. The one-hour
persistence requirement suppresses isolated sampling spikes and reflects that
transformer loading capability is time dependent rather than determined by a
single 15-minute excursion. The primary metric remains the annual probability
of at least one qualifying episode, with a single-step event retained as a
sensitivity.
**Status: Approved. Risk threshold and sampling protocol.** The primary
decision threshold is `P_crit = 10^-2`, evaluated with `N = 10^4` common-random-
number samples over the full alpha grid. A `10^-3` sensitivity uses `N = 10^5`
and the reduced alpha set `{0, 0.5, 1.0}`, with local alpha refinement only when
a decision boundary lies inside an unresolved bracket. The larger sample at
the lower probability keeps binomial relative error of similar order. The
threshold is fixed independently of case selection; cases are made informative
by selecting a declared adoption/scenario and grid branch within the
prospectively frozen 2035 primary year, never by tuning `P_crit` or switching
years after results are seen.

**Status: Approved. Grid and fallback.** The primary network is SimBench
`1-MV-semiurb--0-sw`, with low-voltage demand aggregated at secondary
substations, because it supplies a complete parameterized network and time
series while remaining computationally manageable. Dutch 2030, 2033, and 2035
technology layers are applied to the scenario-0 baseline; SimBench future
scenarios and CIGRE MV are reserved for cross-checks. A predeclared screen may
route the study to `1-MV-urban--0-sw` if the baseline is already above 0.85
p.u. or the no-flexibility 2035 case remains below 0.95 p.u. These values are
case-selection heuristics, not asserted DSO planning standards, and cannot be
changed silently to manufacture an interesting result.

**Status: Approved. Weather ensemble.** Dutch KNMI winters, including at least
one design-cold winter, drive the weather-sensitive technology layers so the
future demand and generation assumptions share a Dutch climatic basis. The
underlying SimBench demand profiles retain their German provenance, but the
heat-pump layer is modeled separately; consequently, the strongest
temperature-sensitive demand component is replaced rather than inherited from
the baseline. This mixed provenance is recorded as an explicit transfer
assumption and is revisited through weather and technology sensitivities.

**Status: Approved. Alpha grid.** Results are evaluated at
`alpha = {0, 0.25, 0.5, 0.75, 1.0}`. Five levels expose how decisions contract
from the full fuzzy support to the core while keeping the Monte Carlo and
reporting burden controlled. Alpha cuts remain nested and share aleatory draws
through common random numbers. No scalar defuzzification is applied, because
that would replace the stated epistemic set with an additional preference
assumption.

<!-- methods-id: G0-A1 -->
### G0-A1 - Import-Direction Congestion Scope

**Status: Approved.** The primary event is conditioned on net import because
the flexibility intervention studied here reduces controllable demand.
Direction-agnostic screening showed that SimBench future-scenario annual peaks
can instead be caused by summer PV export; demand reduction would not be the
appropriate remedy for that regime and can even increase export. Apparent-
power magnitude remains the loading quantity after direction conditioning, so
reactive power and reverse-flow thermal loading are not discarded. Export
exceedance is reported beside every primary result, but feed-in congestion is
treated as a separate planning problem requiring a different flexibility
instrument such as absorption or curtailment.

<!-- methods-id: G0-A2 -->
### G0-A2 - Full-Year Event Evaluation

**Status: Approved.** Tier-1 evaluates every 15-minute interval in the planning
year. Deterministic screening found that import-ranked validation windows would
need 19 to 25 weeks to capture the prescribed near-peak coverage, removing most
of their computational advantage while retaining a risk of missing stochastic
events outside the selected weeks. Because vectorized radial summation is
computationally negligible relative to profile generation and AC validation,
full-year evaluation removes this avoidable approximation. Window sets remain
useful only for selecting AC-validation states and for diagnostic plots.

<!-- methods-id: G0-A3 -->
### G0-A3 - Primary 1.0 P.U. Overload Threshold

**Status: Approved.** The primary congestion event is defined as strict
`L_import > 1.0 p.u.` for four consecutive 15-minute import intervals over the
full planning year. This treats sustained loading above nameplate as the
planning-congestion condition while preserving the already approved
import-direction gate, apparent-power loading quantity, direction-flip reset,
one-hour persistence, and annual-event probability domain. A value exactly equal
to 1.0 p.u. is not counted because the inequality is strict.

The threshold choice is intentionally a planning definition rather than a claim
of transformer failure. IEC 60076-7 and transformer thermal-loading practice
support the broader point that consequences of loading above nameplate are
conditional on duration, ambient conditions, design, and ageing, but the project
does not use IEC or an unverified Dutch DSO passage to justify 1.1 p.u. as the
primary criterion. Instead, `1.1 p.u.` and `1.2 p.u.` are retained as
predeclared sensitivities using the same four-step persistent-event definition.
No separate cumulative-exposure rule is applied to the 1.0-1.1 p.u. band in the
primary analysis, because sustained loading in that band already belongs to the
primary event; adding a cumulative rule would create a different estimand and
would require a separate signed sensitivity design.
<!-- methods-id: G0-A4 -->
### G0-A4 - Primary 2035 Planning Year

**Status: Approved.** The complete primary probabilistic analysis and
decision-reversal benchmark are fixed to planning year 2035 before integrated
results are inspected. This provides a forward case-study horizon at which
electrification growth can be represented without selecting the most
interesting year after observing the outcome. A predeclared deterministic
screen still evaluates 2030, 2033, and 2035 to expose the load trajectory and
test the operating domain, while the earlier years remain supporting inputs to
the later deferral-horizon analysis. G5 may select only a declared
adoption/scenario and grid branch within 2035. If 2035 proves congestion-free
or not flexibility-resolvable, the study records that result and requires a
signed amendment rather than silently switching years or tuning inputs. The
ElaadNL residential profile generator remains fixed at 2030 under EV-004: that
setting supplies a reusable behavior distribution, whereas external adoption
counts and nodal allocation supply the 2035 planning growth. Keeping those two
years conceptually separate avoids counting forecast growth twice.

<!-- methods-id: G1 -->
### G1 - Two-Tier Network Evaluation

**Status: Approved with G2 validation conditions.** Monte Carlo samples are
evaluated by radial summation of downstream net active and reactive power,
while AC power flow is used for deterministic checks and manifested validation
subsets. The measured high-level pandapower `runpp` path required about 105 ms
per solve on the 117-bus primary grid, making billions of time-step solves
impractical through that measured path; this does not establish that all AC
implementations are infeasible. The lower-level TimeSeriesCPP diagnostic
adapted the same primary grid by materializing open line switches as
out-of-service lines, fusing closed bus-bus switches, and mapping the external
grid as the LightSim slack source; the regenerated E1.S2b run measured
0.2325 ms per repeated baseline voltage solve inside a 672-step batch, implying
about 8.15 s for 35,040 voltage solves before scenario construction and
selected result extraction. Tier-1 therefore supplies the Monte Carlo
computational path, but its agreement with pandapower is a G2 hypothesis rather
than an accepted accuracy claim. The corrected TimeSeriesCPP budget and a
held-out near-threshold enclosure test determine the eventual AC-validation
budget and whether Tier-1 remains admissible.

**Status: Approved evidence protocol; remediation pending.** Final experimental
evidence is produced through the IC-5 ExperimentRunner from version-controlled
configuration and is accompanied by a standard `manifest.json` containing the
source revision, configuration hash, random seeds, software versions, and
output checksums. Several early foundation diagnostics predated the full runner
and instead wrote task-specific evidence JSON with substantially similar
provenance. Those files are retained as historical gate evidence, but they are
not treated as final manuscript evidence. Before G2 uses them as inputs, E0.S3b
reproduces the diagnostics through ExperimentRunner, compares the results with
the historical artifacts, and records any discrepancy rather than silently
relabeling an old file as compliant.

<!-- methods-id: G1-A1 -->
### G1-A1 - Model-Output Error Propagation

**Status: Approved framework; amended by G1-A2.** Grid-model discrepancy is
represented as an interval on transformer-loading output, not as a margin added
to an already estimated overload probability. Lower and upper loading
trajectories are classified by the same four-step event detector, and binomial
confidence intervals are computed from the resulting event counts. No
probability distribution or independence assumption is assigned to the
discrepancy; its dependence on inputs, controllability, and time may be
arbitrary within the stated envelope. Tier-1-to-AC approximation error is
estimated separately at G2. G1-A2 supplies the exact mixed relative/additive
composition. This construction preserves the physical episode semantics and
prevents numerical approximation error from being hidden inside the p-box.

<!-- methods-id: G1-A2 -->
### G1-A2 - Grid-Error and Capacity-Screen Protocol

**Status: Approved protocol; the numerical A-013 values remain proposed.** The
grid-model discrepancy is represented by a symmetric relative loading envelope
and the Tier-1-to-pandapower discrepancy by the additive lower and upper
envelopes established at G2. Their conservative endpoint composition is
`L_lower=(1-epsilon_grid)*max(0,L_T1-epsilon_Tier1_minus)` and
`L_upper=(1+epsilon_grid)*(L_T1+epsilon_Tier1_plus)`. This interval admits
arbitrary dependence between both discrepancies and the simulation inputs; it
is therefore propagated as endpoint loading trajectories before the overload-
episode detector, not sampled as independent noise. Direction is gated using
the unwidened active-power sign. No fixed 104 MVA validity ceiling is assumed:
one predeclared manifested screen of the integrated EV, heat-pump, PV,
adoption, and net-load layers defines the future operating domain before
probabilistic results are inspected, after which out-of-domain states are
escalated. That screen reports raw MVA and both the 80 MVA total and 40 MVA firm
ratios. The capacity convention is selected for its planning interpretation
and decision usefulness rather than simply to create congestion. If firm
capacity is selected, a one-transformer-out AC case is required because a
normal-operation flow divided by 40 MVA is only a headroom diagnostic.

<!-- methods-id: E5-S3-T1 -->
### E5-S3-T1 - Output-Error Schema

**Status: Approved with conditions.** The IC-2/IC-3 schema for output-domain
model-error propagation passes validated loading trajectories, unwidened
active-power direction masks, threshold metadata, and time-domain flags from
IC-2 to IC-3 rather than passing only a boolean overload result. Agent A must
provide the shared `LoadingTrajectoryResult` contract and validator before
Agent B implements IC-3 propagation. That validation covers array shapes,
finite values, direction masks, time-domain consistency, threshold,
persistence length, and any supplied import/export diagnostics. IC-3 combines
the G2 additive Tier-1 endpoints and the A-013 symmetric relative grid envelope
as
`L_lower=(1-epsilon_grid)*max(0,L_T1-epsilon_Tier1_minus)` and
`L_upper=(1+epsilon_grid)*(L_T1+epsilon_Tier1_plus)`, applies the import gate from
unwidened `P_net`, and runs the approved consecutive-step event detector on the
lower and upper trajectories. Lower and upper event counts generate the
reported probabilities and confidence intervals; probabilities are not
widened after estimation. Tier-1 error and grid-model error are both parts of
total model-output error; their dependence on inputs, time, and each other is
unknown, so they are not sampled independently, assumed to cancel, or combined
by root-sum-of-squares. Their conservative endpoint envelope is composed before
event detection. Runner configuration and manifests must record timestep
cadence and transformer capacity/denominator provenance. G0-A3 has resolved
Q-5: the primary executable event is strict `L_import > 1.0 p.u.` for four
consecutive 15-minute import steps, with `1.1` and `1.2 p.u.` retained as
sensitivities only. This approval does not resolve total-versus-firm capacity,
G2 error values, numerical A-013 grid-error values, real endpoint records,
A-016 scenario consistency, or G3 where the vertex shortcut is claimed; those
remain blocking dependencies for paper-facing event results.

The E5.S3 T2-T4 scaffold implements this approved endpoint propagation using
synthetic loading trajectories only. It composes the additive Tier-1 and
relative grid-error endpoints on complete loading trajectories, preserves the
unwidened active-power direction gate, and counts lower and upper endpoint
events before estimating probabilities and confidence intervals. Synthetic
alpha-family estimates are returned as separate alpha-indexed lower/upper
probability results; no alpha level is collapsed into a scalar or widened after
estimation. The scaffold does not introduce a signed A-013 value or authorize
integrated event results while G2, A-013, capacity/provenance, real endpoint
records, A-016 scenario consistency, and G3 where the vertex shortcut is
claimed remain unresolved.

The `output-error-paper-readiness-v1` blocker manifest is a synthetic reporting
preflight for this same protocol. It records the requested B-owned result kind,
the final-result prerequisite snapshot, and a checklist for the G1-A2 formula,
trajectory-before-event application, forbidden probability widening, forbidden
independent error sampling, A-013 and G2 approval-or-blocker IDs, capacity
linkage/provenance, and endpoint-record presence. The manifest validator
recomputes the blocker list and `ready_for_paper` flag from those fields and
rejects collapsed probability fields, so a blocked readiness packet cannot be
serialized as a paper-facing p-box result by changing one flag.

<!-- methods-id: RNG-001 -->
### RNG-001 - Seed-Tree and CRN Identity Protocol

**Status: Approved.** The seed-tree protocol derives each whole-system aleatory sample from `(root_seed, sample_index)` and each component stream from that sample seed plus the component name. Component stream identities include root-derived stream information, currently the component seed, so a source-member selection made under one root seed cannot be replayed silently under another. Alpha levels, interval endpoints, and treatment labels are branch metadata only: they reuse the same complete aleatory realization and therefore do not enter the aleatory fingerprint. Manifests record the root seed, sample seed, component stream records, selected source-member IDs, and shared physical driver IDs. CRN reuse is a variance-control and pairing device across analysis branches; it is distinct from physical dependence, which is represented separately by shared drivers such as paired weather members. This approval covers the seed-tree and CRN identity policy only; it does not approve downstream scientific runs, Q-5 threshold semantics, IC schema changes, or any numerical uncertainty values.

<!-- methods-id: FLEX-001 -->
### FLEX-001 - Flexibility Aggregation Scaffold

**Status: Approved scaffold protocol.** The E3.S1 flexibility scaffold treats
controllability `rho` as a deterministic multiplier in `[0, 1]` applied only
to positive import-side demand components that are explicitly marked as
controllable. It preserves complete aligned 15-minute trajectories and optional
timestamp sequences, leaves PV/export and non-controllable components
unchanged, and records per-component metadata describing eligibility,
reduction, rebound, and the reason for any unchanged trajectory. The optional
adjacent-step rebound mode conserves reduced component energy within the
supplied trajectory and is included to test the interface required by the
project plan; it is not a signed behavioral model of flexibility delivery. This
approval covers software plumbing only: it does not sign flexibility-factor
values, fuzzy corners, smart-charging control parameters, final rebound
behavior, event analysis, `P(E)`, capacity screens, manuscript numbers, or the
later E2/E3 manifested experiment path.

<!-- methods-id: ALEA-001 -->
### ALEA-001 - Joint Aleatory Dependency Protocol

**Status: Approved.** Each Monte Carlo sample is constructed as one coherent
planning-year realization on a common timezone-aware 15-minute calendar rather
than as independently shuffled component values. A complete historical weather
member anchored to one KNMI calendar year is selected as a paired multivariate
trajectory, so temperature, irradiance, seasonality, and persistence remain
associated; any supplementary irradiance series must cover the same timestamps
and year, and a typical-year PV reference is not sampled as the realized
weather. The neutral Q-8 `WeatherMember` contract records `member_id`,
`shared_weather_driver_id`, source, UTC/local timestamps, temperature, PV
weather fields, provenance, metadata, and a stable content hash so heat-pump
and PV outputs can prove they consumed the same weather realization. EV and
baseline inputs retain complete temporal paths and are mapped deterministically
to the common season and weekday/weekend calendar before aggregation. This
conditional construction preserves dependencies with an identified physical or
calendar driver without claiming an unsupported full joint probability
distribution. Common random numbers then reuse the complete realization across alpha levels,
controllability endpoints, model-error endpoints, and treatments, but are not
treated as a substitute for physical dependence. Leap-year and daylight-saving
mapping are versioned and tested after the concrete weather files are selected,
and manifests record all weather/profile member IDs and mapping versions. If
held-out tail or dependence diagnostics show material residual dependence that
this construction misses, a shared latent factor, multivariate block bootstrap,
or evidence-fitted copula is introduced only through a separately signed and
manifested sensitivity protocol.

The E2.S5 readiness scaffold implements this ALEA-001 handoff without adding a
new scientific decision: baseline SimBench load, EV charging, heat-pump demand,
and PV generation trajectories are represented as complete ordered 15-minute
paths on the same Europe/Amsterdam planning-year calendar before Agent A
aggregates them through IC-1. Each component contributes a manifestable calendar
footprint with component name, member ID, source ID, UTC timestamps, cadence,
first/last timestamp, and timestamp checksum. HP and PV footprints must also
carry the same `shared_weather_driver_id`, implementing WEATHER-001 before
net-load assembly. The validator checks exact equality to the canonical
local-year UTC axis and rejects shifted, missing, duplicated, or unpaired
components, but it does not compute net load, transformer loading, congestion,
profile-library adequacy, or manuscript numbers. Household-diversity
calibration remains open; this scaffold only preserves the selected baseline
trajectory's temporal and weekday/weekend structure so later diversity choices
cannot be hidden inside timestamp repair.

<!-- methods-id: WEATHER-001 -->
### WEATHER-001 - Shared HP/PV Weather-Member Contract

**Status: Approved.** Heat-pump and PV profiles are generated from one neutral
shared weather-member contract rather than from separate component-local weather
objects. Each weather member carries one canonical UTC/local calendar, source
and member identifiers, provenance and checksum metadata, temperature fields for
heat-pump demand, irradiance or PV-weather fields for PV generation, and a
shared weather-driver identity that downstream manifests can record. This makes
the ALEA-001 physical dependency structural: in one Monte Carlo realization, a
cold or cloudy weather member affects both heat-pump load and PV output through
the same timestamped realization. The alternative of pairing HP and PV only
after generation is rejected because it can hide calendar, timezone, member-ID,
or source mismatches until late integration. The contract is implemented in a
neutral Agent C-owned module, `src/weather_model.py`, with tests in
`tests/test_weather_model.py`, so neither `hp_model.py` nor `pv_model.py`
becomes the owner of the shared interface. This approval does not sign the
D-004 source files, completeness criteria, cold-spell tolerances,
paired-weather acceptance results, net-load/event analysis, `P(E)`, capacity
screens, or manuscript-result numbers.

<!-- methods-id: ALEA-002 -->
### ALEA-002 - Downstream-Only Congestion Evaluation

**Status: Approved; final congestion probability criterion remains governed by
G0 unless amended.** Statistics calculated from an isolated EV, heat-pump, PV,
or baseline library are used only to detect malformed data, missing diversity,
or unstable source summaries. They are not interpreted as congestion because a
component peak can coincide with low or opposing demand elsewhere in the
system. For each realization, all aligned component profiles and scenario
volumes are therefore combined into nodal net load before transformer loading
and the approved import-direction episode detector are evaluated. Candidate
profile-library sizes are compared through nested and held-out integrated runs,
so adequacy is judged by stability of the downstream transformer result rather
than by an EV-only proxy or the ElaadNL interface's pointwise daily percentile.
A downstream p95 may be used as a provisional workflow and convergence
diagnostic while alternative published congestion definitions are reviewed; it
does not replace the G0 primary `P_crit` without a separately signed amendment.

<!-- methods-id: G2 -->
### G2 - Tier-1 Enclosure and Adequacy

**Status: Pending gate.** No manuscript adequacy claim is authorized yet. When
G2 is decided, this paragraph must state the predeclared validation domain, the
held-out near/above-threshold enclosure criterion, the observed Tier-1 error
envelope, its decision impact, and the selected outcome: direct Tier-1,
corrected Tier-1, selective AC, or rejection of Tier-1.

<!-- methods-id: G3 -->
### G3 - Monotonicity Verdict

**Status: Pending gate.** No vertex-shortcut claim is authorized yet. The final
paragraph must report the dense controllability sweep, tested regime, numerical
tolerance, any counterexamples, and whether endpoint propagation or interior
sampling is required.

The E4.S1 dense-rho sweep scaffold remains synthetic-only before G3. Its serialized payload is versioned as `e4s1-synthetic-rho-sweep-v1` and carries an explicit pending-G3 status plus non-claims for real trajectories, real `P(E)`, capacity screening, vertex-shortcut authorization, and manuscript numbers. The validator rejects paper-facing relabeling and collapsed probability fields so the synthetic diagnostic cannot become a paper-facing result by serialization alone.

The E4.S2 scaffold provides a deterministic interior alpha-cut sampling path
for synthetic validation and possible activation if G3 rejects endpoint-only
propagation. It reuses the same canonical sample identities for every rho
candidate within an alpha-cut and reports only alpha-indexed lower and upper probability bounds. Its synthetic `interior-pbox-fallback-report-v1` payload and serialized validator preserve the rho grid, lower/upper extrema, confidence intervals, and pre-G3 non-claims after JSON transport; it does not produce or authorize paper-facing probability results before G3 and downstream event dependencies are resolved.

The E6.S2 decision-layer scaffold is likewise synthetic and pre-G3 only. Given
validated alpha-indexed lower and upper event-probability curves that are
monotone nonincreasing in controllability `rho`, it computes lower and upper
targets by the non-strict condition `rho_star = inf{rho: P(E|rho) <= P_crit}`.
Within a supplied synthetic bracket, the crossing is read by an explicit
piecewise-linear convention; if no supplied point satisfies the criterion, the
target is recorded as `math.inf` rather than replaced by a finite sentinel or a
defuzzified value. Membership readout is reported as bounds over finite
`rho_star` intervals and rejects never-satisfied targets. The procurement-
target framing scaffold compares each finite alpha-indexed `rho_star` interval
with the matching alpha-cut of a synthetic fuzzy delivery envelope and reports
one of four geometric labels: inside envelope, overlapping/monitor, outside
envelope, or never satisfied. These labels preserve the lower/upper target and
delivery-envelope endpoints and do not imply a real procurement decision. This
scaffold does not authorize real net-load/event analysis, paper-facing
`rho_star` values, delivery-envelope claims, or case-selection claims until
G3, Q-5, G2, A-013, and integrated E3 outputs are resolved.

<!-- methods-id: E6.S3 -->
### E6.S3 - Deferral-Horizon Scaffold

**Status: Scaffold-only; no scientific result.** The deferral-horizon scaffold
accepts synthetic year-indexed procurement-target results and summarizes them
separately at each alpha level. For a given alpha, the lower horizon is the
latest supplied year whose `rho_star` interval is fully inside the synthetic
delivery envelope, while the upper or monitoring horizon is the latest supplied
year whose interval is either fully inside or overlaps the envelope. Years
classified as outside the envelope or never satisfied are reported explicitly,
including the first unmet year and the first never-satisfied year when present.
The scaffold preserves the underlying lower and upper `rho_star` endpoints,
delivery-envelope endpoints, and per-year classifications; it does not
interpolate unevaluated years, defuzzify alpha levels, or turn the framing into
a reinforcement decision. Real deferral-horizon use remains blocked until the
primary 2035 p-box and supporting 2030/2033 p-boxes are produced through the
frozen manifested pipeline, and until G3, Q-5, G2, A-013, integrated E3 outputs,
and the G4/flexibility-envelope decision permit paper-facing interpretation.

<!-- methods-id: E6.S4 -->
### E6.S4 - Value-of-Information Scaffold

**Status: Scaffold-only; no economic result.** The value-of-information
scaffold accepts alpha-indexed synthetic decision outputs and caller-supplied
synthetic cost/benefit intervals. For each alpha level, it preserves the
decision-width interval, the deferral-benefit interval, the information-cost
interval, and the resulting net-value interval. Net value is computed by
conservative interval subtraction: the lower endpoint subtracts the upper
information cost from the lower deferral benefit, and the upper endpoint
subtracts the lower information cost from the upper deferral benefit. The
scaffold labels each alpha as net-positive, net-negative, indeterminate, or
not applicable when the synthetic decision output contains no lower or
monitoring horizon. These labels are bookkeeping for synthetic tests only.
They do not approve real reinforcement costs, discount rates, pilot costs,
benefit formulas, value-of-information claims, or manuscript numbers. Real E6.S4
use remains blocked until the relevant E3/E6 outputs are produced through
manifests and the PI signs the required economic assumptions and extracted
cost values.

<!-- methods-id: G4 -->
### G4 - Fuzzy Controllability Elicitation

**Status: Pending gate.** The final paragraph must document the elicitation
protocol, evidence supplied to participants, resulting trapezoid or alternative
membership function, disagreements, PI sign-off, and planned shape sensitivity.

<!-- methods-id: G5 -->
### G5 - Decision-Reversal Case Selection

**Status: Pending gate.** The final paragraph must explain the predeclared case
sweep within the frozen 2035 primary year, selection criteria, rejected
candidates, and why the selected adoption/scenario and grid branch is
decision-informative without tuning `P_crit`, changing the year, or altering
other frozen thresholds.

<!-- methods-id: G6 -->
### G6 - Results Freeze

**Status: Pending gate.** The final paragraph must identify the frozen run
manifests, software/configuration versions, convergence evidence, robustness
checks, and the rule preventing post-freeze numerical or figure changes.

<!-- methods-id: G7 -->
### G7 - Submission Decision

**Status: Pending gate.** This is a governance rather than analytical method
gate. Before approval, the paragraph must record the reproducibility-package
audit, red-team outcome, unresolved limitations, and journal-scope rationale.

<!-- methods-id: DEP-001 -->
### DEP-001 - Software Version Bounds

**Status: Approved.** The reproducible environment uses SimBench 1.6.2 with
pandapower 3.4 or later and below major version 4, matching SimBench's declared
dependency while avoiding a known incompatibility in the older package
combination. Exact installed versions are recorded in each run manifest rather
than inferred from the allowed range. Dependency changes require a separate
decision because solver, data-loader, or result-schema changes can alter both
runtime and numerical output.

<!-- methods-id: EV-001 -->
### EV-001 - EV Charging Profile Source

**Status: Approved route; generated library remains governed by D-002.** EV
charging behavior is obtained through the publicly accessible ElaadNL
Laadprofielengenerator rather than the unavailable historical transaction
dataset. The generator supplies seeded Dutch Outlook-based 15-minute profiles
and therefore supports deterministic regeneration and bootstrap sampling. A
one-profile probe was required before library generation to verify the native
2033 option, timestamp orientation, response shape, and seed behavior. Profile
generation and redistribution remain subject to the terms and provenance rules
recorded under D-002.

<!-- methods-id: EV-002 -->
### EV-002 - ElaadNL Internal-Use and Redistribution Boundary

**Status: Approved.** Generated ElaadNL profiles may be used for internal project
computations when they are retrieved through the publicly accessible
Laadprofielengenerator API, but the project does not commit or redistribute raw
API responses or generated profile libraries. Reproducibility is maintained by
committing generation and retrieval code, exact request configurations, distinct
seed schedules, metadata, checksums, and manifests; generated files stay under
ignored raw or processed data paths. The data-availability statement must direct
readers to regenerate profiles through the public API under the terms applicable
at their retrieval time, and the manuscript must not claim that generated
profiles are openly licensed or redistributable. The unresolved redistribution
terms remain a documented limitation and risk rather than an internal-use
blocker. If later terms explicitly prohibit the intended research use, profile
use stops and the issue escalates to the PI before further analysis.

<!-- methods-id: EV-003 -->
### EV-003 - Direct Empirical EV-Profile Bootstrap

**Status: Approved primary route; replacement rule resolved by EV-005B for candidate member-selection only.**
The EV aleatory layer samples complete annual members directly from the frozen,
checksummed ElaadNL profile library rather than fitting a second behavioral
distribution to generated profiles. This retains the generator's session
timing, duration, seasonality, and serial dependence while keeping each selected
member traceable through its batch seed and returned profile index. Profile
member IDs and seed metadata are stored in experiment manifests rather than
reported as scientific parameters in the manuscript. Finite-library adequacy is
tested against integrated transformer results under ALEA-002 and is reported
separately from Monte Carlo sampling error. EV-005B resolves the
within-realization candidate member-selection rule as charge-point-level
sampling with replacement from verified candidate libraries, with duplicate
selections recorded as bootstrap multiplicities. That approval is limited to
candidate member-selection implementation; held-out adequacy, profile-array
loading for integrated use, and source-library sufficiency remain governed by
EV-005/ALEA-002. If direct bootstrapping cannot satisfy those downstream
conditions, the calibrated stochastic sampler remains an explicit fallback
rather than an unreported substitution.

The EV-to-integration readiness artifact records the approved candidate source
libraries and A-014 allocations in a manifest-only adapter shape for later IC-1
use. It exposes home and public EV component identifiers, candidate batch seeds,
processed-file checksums, source manifest paths, member ID patterns based on
batch seed and returned profile index, and the EV-007A/A-014 per-node charge
point counts. This readiness record does not load generated profile arrays,
open held-out batches, materialize an EV-005B realization, certify `M`,
aggregate net load, evaluate events, estimate `P(E)`, or produce manuscript
numbers. Its calendar note preserves the 2025 ElaadNL source calendar and
requires deterministic mapping onto the common planning-year calendar before
IC-1 aggregation.

The follow-up IC-1 guardrail packet makes that handoff executable without
producing trajectories. It derives candidate-only processed-file checksum
expectations from the readiness artifact, blocks raw, held-out, and quarantined
paths from the adapter preflight, and requires local SHA-256 verification
before any profile arrays are loaded by a future IC-1 EV adapter. It also
records the source-to-planning-year calendar obligation as a blocking
precondition: the complete 2025 Europe/Amsterdam source members must be mapped
onto the G0-A4 2035 common calendar by an approved deterministic procedure
before Agent A can aggregate EV demand with baseline, HP, or PV components.
This guardrail packet still does not choose a realization schedule, certify
`M`, inspect held-out data, load profile arrays, or run event analysis.

The next candidate-adapter artifact materializes the approved EV-007A/A-014
2035 Alkmaar low, middle, and high home/public charge-point allocations as
per-node integer dictionaries alongside compact candidate-library member
metadata for home and public EV profiles. Candidate member identity remains
defined by component, library, batch seed, and returned profile index; the
artifact intentionally avoids expanding or loading profile arrays. Agent C
verified the 22 local candidate processed-file SHA-256 digests as a handoff
precondition, while still requiring any consuming IC-1 worktree to repeat that
byte-level verification before loading ignored NPZ files. The same artifact
points reviewers to a PI decision packet for the unresolved 2025 ElaadNL
source-calendar to 2035 planning-calendar mapping, and blocks implementation
until that deterministic mapping rule is signed.

The EV-CAL-001 calendar-mapping decision is now approved as Option A while keeping
the choice auditable before implementation. It compares ordinal timestep,
weekday-class, source-year computational-calendar, and weather-year matched
routes for moving complete 2025 ElaadNL candidate members onto the common 2035
IC-1 calendar. The route specifies required provenance fields for source member,
batch seed, returned profile index, processed checksum, RNG component stream,
calendar IDs, mapping-rule ID/version, DST/holiday policy, and repeated or
omitted source timesteps. It also predeclares implementation tests for complete
calendar shape, deterministic source-index generation, weekday/season/time
semantics, energy preservation or signed correction, rejection of unsigned rules,
and exclusion of held-out/quarantined partitions. No mapping algorithm is
implemented until the PI signs the rule.

The EV IC-1 accepted-artifact index preflight joins the candidate-only component
output consumption packet with the accepted A-014 executable adoption artifact
as a metadata-only handoff surface for Agent A. It records the exact source
artifact paths and Git-blob SHA-256 values for the EV output packet and A-014
allocation artifact, preserves scenario branch explicitness for low, middle, and
high 2035 Alkmaar branches, exposes the node axis, public EV-008A capacity-class
counts, EV-005B duplicate/multiplicity provenance, and EV-CAL-001 calendar
mapping fields, and requires checksum verification before any ignored EV-only
NPZ is loaded. The index remains blocked for paper-facing integrated use: it
does not open held-out or quarantined batches, certify finite-library adequacy,
select the final branch, aggregate net load, evaluate events, estimate `P(E)`,
run capacity screens, or produce manuscript numbers. It is an Agent A preflight
index, not a scientific result.


<!-- methods-id: EV-CAL-001 -->
### EV-CAL-001 - EV Source-To-Planning Calendar Mapping

**Status: Approved.** EV-CAL-001 maps complete 2025 ElaadNL EV source profiles
to the 2035 planning-year calendar by ordinal timestep index: target timestep
`i` receives source timestep `i`. The rule preserves the full 35,040-step
15-minute demand trajectory, member IDs, batch seed, returned profile index,
source-library identity, processed-checksum provenance, and candidate/held-out
partition separation. It does not preserve actual 2035 weekday/weekend or
holiday labels when those differ from the 2025 source calendar, so mapping
provenance records `weekday_weekend_preserved = false` and
`source_timestamp_index_policy = target_index_i_uses_source_index_i`. This approval authorizes readiness/adapter mapping code only. The candidate member-reference artifact materializes source-member IDs, batch seeds, returned profile indices, processed checksums, component identity, and EV-CAL-001 calendar provenance for home Set A and public Set B without loading profile arrays or selecting a realization. Held-out adequacy, finite-library sufficiency, EV-005B member-selection realization, net-load/event/`P(E)`, capacity-screen, and manuscript-result work remain outside this step.
<!-- methods-id: EV-004 -->
### EV-004 - Fixed Residential Charge-Point Distribution

**Status: Approved.** Residential EV demand is represented by complete annual
uncontrolled charge-point profiles generated for the ElaadNL home location at
11 kW and a fixed prognosis year of 2030. The same behavior distribution is
used in the 2030, 2033, and 2035 planning layers; future growth is introduced
only through independently sourced scenario counts and nodal allocation of
physical home charge points. This separation avoids applying ElaadNL's internal
year-dependent forecasts for vehicle numbers, charge-point numbers, and vehicle
efficiency on top of the project's external adoption scenarios. The generator's
native car/van mixture for home charge-point profiles is retained and is not
reweighted. Conditional on the common calendar and scenario, home charge points
are treated as exchangeable independent draws from the fixed distribution,
while each selected annual trajectory retains its internal chronology. Public
charging is modeled as a separate class and is not governed by this decision.

<!-- methods-id: EV-005 -->
### EV-005 - Finite Profile-Library Uncertainty

**Status: Approved protocol; numerical stopping tolerance pending; candidate replacement resolved by EV-005B.** The archived ElaadNL library is treated as a finite
random sample from an unknown generator distribution rather than as the true
distribution itself. Library size `M`, home-charge-point cohort size `K`, and
whole-system Monte Carlo size `N` therefore have distinct roles: one realization
uses `K` profile selections, `N` controls conditional simulation precision, and
`M` controls the quality of the empirical source distribution. An initial
candidate library of 1,000 profiles is generated as independent distinct-seed
batches but is not declared sufficient by construction. The local Set A archive
contains candidate seeds `140001` through `140901`, quarantined diagnostic seeds
`141001` and `141101`, and fresh disjoint held-out seeds `141201` and `141301`;
the fresh held-out profiles are generated and checksummed but remain isolated
from adequacy analysis until E3.S2a freezes the downstream criterion. Nested
library sizes and disjoint held-out API batches are
propagated through the fully integrated net-load and transformer workflow using
common random numbers, and variation between those results is reported
separately from the Monte Carlo confidence interval conditional on a fixed
library. The library is extended if the predeclared downstream adequacy
criterion fails. Resampling one library cannot detect behavior absent from all
its members, so independent held-out generation is mandatory and ordinary within-library
bootstrapping is only supplementary. EV-005B now fixes the within-realization
candidate member-selection rule as charge-point-level sampling with replacement,
but it does not certify library adequacy or authorize held-out use. The
acceptance tolerance is fixed before the adequacy results are inspected and
is tied to transformer-result or reinforcement-decision stability rather than
to an isolated EV-profile percentile.

The E3.S2a EV held-out adequacy preflight scaffold automates the current
fail-closed boundary before any held-out use. It consumes the accepted EV IC-1
artifact index and the unsigned EV downstream adequacy criterion packet, records
the source metadata checksums and candidate output checksum expectations, and
emits a blocker manifest rather than opening held-out or quarantined batches.
The manifest explicitly blocks execution until the downstream aggregate
criterion is PI-signed, Agent A's IC-1 assembly is accepted, held-out access is
invoked under that signed route, A-016 scenario consistency is resolved, the
final low/middle/high branch is selected or kept explicitly branched in a signed
run design, and candidate output files are verified in the consuming worktree.
The candidate-output checksum check is automated as a checkpointed script step:
it hashes ignored EV component-output NPZ bytes only when those files are
present, writes a resumable verification artifact after each declared scenario,
and otherwise records exact missing paths as a fail-closed blocker. G0-A3 has
resolved Q-5 threshold semantics, so EV readiness no longer treats Q-5 itself
as a blocker; event use still remains blocked by the other unsigned or missing
integrated prerequisites listed above. It loads no profile arrays, runs no
net-load/event/`P(E)` analysis, certifies no `M` sufficiency, and produces no
manuscript number.

<!-- methods-id: EV-005A -->
### EV-005A - Low-Cost Held-Out Replacement

**Status: Approved narrow follow-up.** The precriterion summaries viewed for
seeds `141001` and `141101` do not make those batches scientifically invalid,
but they are conservatively reclassified as
`quarantined_precriterion_diagnostic` and may not certify held-out adequacy.
Because replacement required only two additional API calls, fresh disjoint
held-out seeds `141201` and `141301` were generated under the same EV-004
request. Their committed metadata is limited to request/provenance, checksums,
calendar and shape integrity, finite/nonnegative checks, and distinct-member
counts until E3.S2a freezes its adequacy criterion. This remediation is not a
blanket automatic-redo rule: materially expensive repetition, discarded
evidence, or substantial extra computation still requires PI consultation
before invalidating or repeating work.


<!-- methods-id: EV-005B -->
### EV-005B - Within-Realization EV Replacement Policy

**Status: Approved for candidate member-selection implementation only.**
EV-005B approves charge-point-level sampling with replacement from the verified
candidate ElaadNL profile libraries for each EV component and EV-008A public
capacity class. The approved 2035 Alkmaar EV-007A cohorts exceed the available
candidate library sizes: home charge-point counts are 7,992 to 10,343 versus
`M = 1,000`, and each EV-008A public capacity class requires more than 1,000
physical charge points while only 300 candidate source members exist per class.
Whole-grid no-replacement is therefore rejected for the declared 2035 branches.
Each selected row must preserve the RNG-001 component-stream identity, source
member ID, source-library ID, batch seed, returned profile index, processed-file
checksum, EV-CAL-001 calendar provenance, and duplicate-member multiplicity.
Duplicate source members are interpreted as bootstrap multiplicities for
physical charge points, not as new unique profiles and not as evidence that the
finite library is adequate. This approval does not certify home `M = 1,000` or
public `M = 1,200`, open held-out or quarantined batches, load generated profile
arrays for integrated use, run net-load/event/`P(E)`, produce manuscript
numbers, or bypass the downstream E3.S2a adequacy criterion governed by EV-005
and ALEA-002.
<!-- methods-id: EV-006 -->
### EV-006 - Matched Smart-Charging Counterfactuals

**Status: Approved seed protocol; smart-control role and parameters pending.**
When the ElaadNL smart-charging mode is evaluated, its controlled trajectory is
generated with the same batch seed as the corresponding uncontrolled
trajectory and is paired by returned profile index. ElaadNL documents that a
common seed preserves the annual mileage, energy demand, and charging sessions,
so the paired difference isolates the effect of the charging-control rule rather
than a new draw of charging behavior. The uncontrolled and controlled members
are alternative outcomes for one source realization and are therefore compared
or substituted, never added or resampled as independent charge points. Distinct
seeds remain mandatory between unrelated source batches and between candidate
and held-out libraries. This protocol does not by itself make ElaadNL smart
charging the primary flexibility model or determine its base capacity, ramp
speed, pooling option, or mapping to the uncertain controllability factor; those
choices require separate approval and monotonicity testing.

<!-- methods-id: EV-007 -->
### EV-007 - Local EV Adoption Scaling Route

**Status: Approved.** Local SimBench-grid home and public charge-point totals
are derived from a predeclared representative CBS neighbourhood cluster using
ElaadNL local forecast outputs, not by applying national Outlook totals
directly to the benchmark grid. The cluster is selected by exogenous area and
feeder-scale criteria before congestion results are inspected, so the adoption
layer cannot be tuned after seeing whether the case overloads. National D-010
values remain provenance and scenario context only. A-014 is used only after
local totals exist, as the second-stage rule that distributes those totals
across benchmark load nodes. If local forecast retrieval or justification
fails, a national-adoption-rate scaling with separately sourced local
denominators remains a fallback or sensitivity rather than the primary route.
EV-007A subsequently selects Alkmaar (`GM0361`) as the municipality-level
implementation proxy and signs its retrieved 2035 local Outlook counts as
declared low/middle/high scenario branches. Delft (`GM0503`) was checked as an
available fallback but is not selected. The live neighbourhood-list endpoint
returned HTTP 500 during retrieval, so the accepted proxy is municipality-level
rather than a manually assembled neighbourhood subset.

<!-- methods-id: EV-007A -->
### EV-007A - Alkmaar Local EV Adoption Counts

**Status: Approved.** The local EV adoption layer uses Alkmaar municipality
(`GM0361`) as the representative local proxy for the synthetic SimBench case
study. ElaadNL Outlook Mobiliteit local forecast API values for 2035 are
rounded to integer charge-point counts and carried as three declared branches:
low `7992` home and `4183` public charge points, middle `9386` home and `5127`
public charge points, and high `10343` home and `6138` public charge points.
These branches are used as scenario inputs, not as probabilities and not as a
post-hoc tuning device. The final paper branch is selected later at G5 after
the predeclared capacity screen, within the already frozen 2035 planning year.
National Outlook values remain provenance and scale context only. A-014
materializes these accepted totals across the benchmark load nodes, but this
decision does not itself choose the final case-study branch or produce
congestion, adequacy, `P(E)`, or manuscript results.

<!-- methods-id: EV-008 -->
### EV-008 - Superseded Public Charge-Point Profile Protocol

**Status: Superseded by EV-008A.** EV-008 originally proposed one uncontrolled
ElaadNL public `cp` profile library at 22 kW. That single-capacity design is no
longer the approved primary public EV behavior route. The parts that survive
are the public charge-point sampling unit, `location_type = public`, the native
public car/van mixture, fixed `simulated_year = 2030`, ignored raw/processed
storage, and the EV-003/EV-005 distinction between source-library size and
Monte Carlo count. The reason for superseding the row is that D-012 supports a
charge-point/EVSE/connector-like unit but does not support treating 22 kW as
the unique current Alkmaar representative capacity. A single 22 kW public class
may still be used later only as a clearly labelled future/upper-capacity
sensitivity.

<!-- methods-id: EV-008A -->
### EV-008A - Public Set B Capacity-Stratified Profile Protocol

**Status: Approved for source generation only.** EV-008A replaces the original
single 22 kW public Set B proposal with a small capacity-stratified public
library. Public charging is represented by uncontrolled ElaadNL public `cp`
profiles with native `["van", "car"]` mixing, fixed `simulated_year = 2030`,
and four AC capacity classes: 11, 13, 15, and 22 kW. The physical capacity mix
used for public AC charge-point allocation is a simple equal split across those
classes: 25% each. D-012 shows the observed Alkmaar AC groups are close enough
that equal shares are clearer and more robust than overfitting the small
snapshot differences. The balanced candidate public source library contains
`M = 1200` members from twelve 100-profile API calls: 300 members per class.
The balanced held-out public source library contains `H = 400` members from
four 100-profile API calls: 100 members per class. Candidate seeds are
`152001`, `152101`, `152201`; `152301`, `152401`, `152501`; `152601`, `152701`,
`152801`; and `152901`, `153001`, `153101`. Held-out seeds are `153201`,
`153301`, `153401`, and `153501`. Each member is identified by partition,
capacity class, `cp_capacity_kw`, batch seed, returned profile index, request
checksum, raw and processed checksums, and control mode. The approval
authorizes only source generation and structural validation. The follow-up
public Set B readiness artifact splits approved A-014 public node counts across
the four EV-008A capacity classes with deterministic largest-remainder rounding
while conserving both per-node totals and global class totals, and records the
member, seed, checksum, and EV-CAL-001 provenance fields later required by
IC-1. It does not
approve public smart charging, DC/fast charging, held-out adequacy use,
integrated net-load or event analysis, manuscript results, or a claim that the
generated `M` is sufficient.

<!-- methods-id: COST-001 -->
### COST-001 - Indicative Reinforcement Costs

**Status: Approved source, extracted values pending individual sign-off.**
Indicative Dutch reinforcement costs are taken from the PI-supplied Cicenas
thesis because it documents Stedin/Eneco project context relevant to the case.
The source PDF is retained locally and is neither committed nor redistributed.
Every number used in the analysis must preserve its value, unit, interpretation,
page, table or section, source-status label, and intended calculation. This
traceability separates directly reported values from project interpretation
and prevents an order-of-magnitude planning anchor from being presented as a
universal tariff.

## Assumptions

<!-- methods-id: A-001 -->
### A-001 - Primary and Sensitivity Risk Thresholds

**Status: Proposed row; operational values frozen by G0.** A primary annual
overload-probability threshold of `10^-2` is paired with a `10^-3` sensitivity
to distinguish the central decision from a stricter risk posture without
pretending that one universal DSO threshold exists. Sample sizes increase from
`10^4` to `10^5` at the lower probability so expected event counts and relative
Monte Carlo precision remain comparable. The threshold is not adjusted after
case results are observed.

<!-- methods-id: A-002 -->
### A-002 - Alpha Resolution

**Status: Proposed row; operational grid frozen by G0.** The five-point alpha
grid `{0, 0.25, 0.5, 0.75, 1.0}` provides interpretable support-to-core
resolution while limiting repeated stochastic evaluations. Nested cuts and
common random numbers allow changes across alpha to be attributed to epistemic
contraction rather than unrelated sampling noise. Additional alpha values are
introduced only under a predeclared decision-boundary refinement rule.

<!-- methods-id: A-003 -->
### A-003 - Benchmark Network Family

**Status: Proposed row; primary selection frozen by G0.** Parameterized
SimBench MV networks were selected because the paper requires reproducible
topology, impedances, ratings, and time series for both summation and AC power
flow. The semi-urban network is primary, the urban network is a preauthorized
routing fallback, and CIGRE MV is a robustness case. The benchmark is not
claimed to represent one specific Dutch network; Dutch relevance is introduced
through the technology, weather, and decision framing.

<!-- methods-id: A-004 -->
### A-004 - No Defuzzification

**Status: Proposed standing reporting rule.** Results retain alpha-indexed
lower and upper overload probabilities and their Monte Carlo confidence
intervals. Reporting one defuzzified probability would require an additional
preference or weighting over the epistemic set and could conceal decision
reversals inside that set. Decision metrics are therefore derived from the
family of bounds, and any scalar comparison is tied to an explicitly stated
alpha level rather than presented as the unique probability.

<!-- methods-id: A-005 -->
### A-005 - Parallel Transformer Aggregation

**Status: Proposed, with inventory support and G2 validation pending.** The two
40 MVA units are aggregated by `abs(sum_i S_i) / sum_i S_nom_i` because the
closed ties, equal taps, equal ratings, and in-service states support treatment
as one bank. Under collinear sharing this aggregate equals each unit's loading
and matches Tier-1's available net-exchange quantity. The equivalence can fail
under open sections, unequal taps, or circulating current, so G2 compares the
aggregate result with unit-level AC loading and requires escalation if the
difference is material near the event threshold.

<!-- methods-id: A-006 -->
### A-006 - Reactive Power in Tier-1

**Status: Proposed.** Tier-1 assigns reactive power through a documented nodal
power factor so apparent-power loading can be evaluated when profile sources
primarily supply active power. Flexibility changes active demand and reactive
power follows the assigned factor, preserving a consistent P/Q convention
through aggregation. This is a modeling assumption rather than measured nodal
behavior; its value and sensitivity must be kept separate from grid-model
output error, and G2 tests whether the resulting transformer loading remains
adequate against AC calculations across relevant power factors.

<!-- methods-id: A-007 -->
### A-007 - Dutch Weather on the SimBench Baseline

**Status: Proposed.** KNMI weather is combined with the German-origin SimBench
baseline to maintain climatic consistency with Dutch heat-pump and PV layers.
The transfer is acceptable only because weather-sensitive heating demand is
introduced explicitly rather than inferred from the baseline profile. The
remaining baseline is treated as weakly weather-coupled, and the mixed
provenance is disclosed as an external-validity limitation rather than hidden
inside stochastic variation.

<!-- methods-id: A-008 -->
### A-008 - Grid-Routing Thresholds

**Status: Proposed.** The 0.85 p.u. baseline and 0.95 p.u. no-flexibility-2035
thresholds are used only to reject cases that are already congested or never
approach congestion. They create a reproducible route between predeclared
benchmark networks and protect against silent case tuning. They are not derived
from regulation, transformer thermal capability, or a DSO investment standard
and are not interpreted as scientific thresholds in the results.

<!-- methods-id: A-009 -->
### A-009 - 2033 EV Generator Fallback

**Status: Superseded by EV-004.** A fallback mapping from 2033 to a 2035 EV
behavior library was predeclared in case the ElaadNL API did not accept a native
2033 simulation year. EV-004 instead fixes one 2030 residential charge-point
behavior distribution across all planning layers and assigns scenario growth
to external charge-point counts, so neither native 2033 behavior nor this
fallback is used in the primary residential model.

<!-- methods-id: A-010 -->
### A-010 - EV Charging Power

**Status: Superseded as a combined assumption.** EV-004 approves an 11 kW
connection capacity for the fixed home charge-point class. This is a capacity
ceiling rather than continuous demand; coincidence, arrivals, dwell times, and
delivered energy remain profile-driven. The earlier 22 kW public value and 7.4
kW home sensitivity are not approved by EV-004 and may not be treated as signed
scientific inputs without a separate decision.

<!-- methods-id: A-011 -->
### A-011 - Elaad Profile Scaling

**Status: Superseded by EV-004.** The earlier proposal used vehicle-level home
profiles and scaled them by the number of EVs with home-charging access. The
approved residential model instead uses one charge-point profile per physical
home charge point and scales it by externally sourced home charge-point counts.
No additional home-share factor or vehicle-per-charge-point multiplier is
applied after sampling because the fixed charge-point distribution already
contains ElaadNL's utilization and vehicle-mixture assumptions. This convention
is checked by comparing aggregated nodal energy with the sum of the
selected library members.

<!-- methods-id: A-012 -->
### A-012 - Power-Flow Direction Convention

**Status: Proposed row; semantics frozen by G0-A1.** Positive `P_net` denotes
import from the upstream grid into the MV area, negative `P_net` denotes export,
and zero belongs to neither directional event. Direction only gates the event;
loading in either direction remains the magnitude of complex apparent power.
A direction change resets the consecutive-step counter, preventing separate
import episodes from being joined across an intervening export interval. The
unconditioned magnitude is retained for screening so reverse-flow stress
remains visible.

<!-- methods-id: A-016 -->
### A-016 - Cross-Source 2035 Scenario Consistency

**Status: Approved consistency requirement.** The 2035 EV, heat-pump, and PV layers may draw on different best-available Dutch sources because no single source cleanly supplies all local quantities needed for this synthetic DSO case. EV counts are anchored to ElaadNL Outlook, HP scaling is built from When2Heat shape/COP evidence plus PBL/CBS local heat-demand evidence, and PV installed capacity is routed through CBS local capacity and II3050 scenario growth. Before any executable integrated net-load or event analysis, each component artifact and the integration manifest must therefore record source lineage, source year, planning year, scenario label, scaling factor or adoption branch, and an explicit consistency check across the EV/HP/PV choices. HP-001 enforces this as a separate final-readiness approval key, `scenario_source_consistency`: even a future signed annual HP value-binding record is not sufficient for integrated HP use until this consistency approval, D-004 paired-weather acceptance, and cold-spell tolerances are also recorded. If those choices cannot be reconciled as one coherent 2035 case, the mismatch is reported as a limitation or escalated for a signed amendment; it must not be hidden behind a shared `low`, `middle`, or `high` label.

<!-- methods-id: A-013 -->
### A-013 - Grid-Model Output Discrepancy

**Status: Proposed; no numerical sign-off.** The illustrative DSO use case
assumes a planning model populated with mostly correct topology and asset data,
transformer-level measurements or forecasts, and forecast or allocated lower-
level injections; it does not assume dense measurements, model calibration, or
distribution state estimation. A symmetric relative interval places physical
loading within `(1 +/- epsilon_grid)` times modeled loading. The candidate 5%
reference and 2%/10% sensitivities are author-specified scenarios, not an
empirical bound, confidence interval, expert consensus, or value currently
established by literature. No mechanism-by-mechanism percentage inventory is
used to manufacture that value. A targeted evidence review must instead record
each source's measurement boundary, model conditioning, operating domain, and
comparability before the PI signs a number. Input uncertainties represented
elsewhere are excluded, matched solver-to-solver numerical differences are an
implementation check, and arbitrary unknown dependence is admitted. The
applicability domain is frozen from the manifested integrated future-layer
screen before probabilistic results are inspected; out-of-domain states are
reported rather than silently extrapolated. Until A-013 is signed, Methods and
results may describe the protocol and sensitivity scenarios but may not call
5% a scientifically established grid-model error.

<!-- methods-id: A-014 -->
### A-014 - EV Adoption Allocation Across Benchmark Load Nodes

**Status: Approved for second-stage use after EV-007 local totals are
established.** A-014 is a within-grid allocation rule only. Once E2.S6 derives
approved local SimBench-grid home and public charge-point totals from the
EV-007 CBS neighbourhood-cluster route, the project distributes each local
total across the 115 in-service `net.load` rows in proportion to each row's
static active load `p_mw`. Fractional allocations are converted to physical
nonnegative integer counts by largest-remainder rounding, with ties resolved by
node ID for deterministic reruns. The rule must not be applied directly to the
national ElaadNL Outlook totals recorded under D-010, and it does not itself
select the local cluster or approve public-charging behavior profiles. The
current A-014 preview applied this deterministic rounding rule to the Alkmaar
values that EV-007A later accepted. The same 115 node weights are now
materialized in `configs/scenarios.yaml`, so `adoption_node_allocations` can
return deterministic home/public per-node counts for each declared
low/middle/high branch. This is still an adoption-layer input only: the
materialized allocation does not choose the final paper branch, open EV
held-out adequacy data, run net-load integration, perform event analysis, or
produce manuscript results.

<!-- methods-id: A-015 -->
### A-015 - D-013 PBL Indicator Mapping Assumption

**Status: Approved for D-013 indicator mapping only.** A-015 records a
transparent source-use assumption for the PBL Startanalyse 2025 Alkmaar fields
used by the HP-001 local scaling route. The project treats `_w` as
woningen/residential and `_u` as utiliteit/non-residential; treats
`H23_Vraag_RV_w` as residential space-heating demand intensity; treats
`H24_Vraag_TW_w` as residential domestic-hot-water demand intensity; and keeps
`H22_Vraag_totaal_w` as a residential total-demand diagnostic. The units are
interpreted as `[GJ/weq/jaar]`. This mapping is currently inferred from PBL's
documented H01/H02/H03 energy-demand concepts, the documented 2025
woningen/utiliteit split, the official Alkmaar CSV schema, and ASA25 template
context. No explicit PBL evidence was found that defines these literal raw
suffixes and H22/H23/H24 labels. The assumption is therefore manuscript-facing:
readers must be able to see that the interpretation is signed and traceable,
but not directly documented by a PBL column dictionary. A-015 does not approve
`Referentie_2030` as an executable value column, SFH/MFH splitting, annual TWh
values, 2035 HP adoption/electrification, D-004/cold-spell acceptance, net-load
integration, event analysis, `P(E)`, capacity-screen conclusions, or manuscript
results.

## Data and Evidence Choices

<!-- methods-id: D-001 -->
### D-001 - SimBench Network and Baseline Profiles

**Status: Approved for benchmark use by G0 and DEP-001.** SimBench supplies
the network topology, electrical parameters, equipment ratings, and baseline
time series needed for a fully reproducible benchmark. The package-installed
data are referenced by version rather than copied into the repository, and
each run manifest records the exact package version. SimBench's German
provenance is retained explicitly; it provides a parameterized test system, not
evidence that the selected network is a measured Dutch feeder.

<!-- methods-id: D-002 -->
### D-002 - ElaadNL EV Profiles

**Status: Internal-use approved by EV-002; redistribution unresolved.** Seeded
15-minute EV charging profiles are requested from the ElaadNL
Laadprofielengenerator using version-controlled request metadata and ignored
raw-output paths. The one-profile probe accepted native `simulated_year = 2033`,
returned 35,040 UTC timestamps, and exposed `demands_kw` as a time-major array
with one value per timestamp for the single requested profile. A historical
vehicle-level batch accepted `simulated_year = 2030`, seed `130001`, and
`n_profiles = 100`; it returned 100 distinct members, still identified only as
`(batch seed, returned profile index)` rather than independent per-profile
seeds. EV-004 supersedes that request as the primary residential model, so the
historical batch is retained for API and shape diagnostics only. The first
EV-004 home charge-point probe used `simulated_year = 2030`, seed `140001`,
native `["van", "car"]` vehicle mixing, 11 kW capacity, and 100 uncontrolled
profiles; it returned 35,040 timestamps and 100 distinct members with returned
indices available for planned pairing, with no missing, non-finite, or
negative demand values. Because no smart-control batch was generated, this
uncontrolled-only probe does not verify that a future smart batch preserves
member ordering; actual pairing remains pending per section 7 of the Elaad
profile generation specification. The full EV-004 Set A local archive then
generated candidate seeds `140101` through `140901`, quarantined diagnostic
seeds `141001` and `141101`, and fresh held-out seeds `141201` and `141301`
using the same fixed home charge-point request. Together
with the previously recovered seed `140001`, the candidate archive contains
1,000 distinct members, the quarantined diagnostic archive contains 200
members, and the fresh held-out archive contains 200 distinct members.
The fresh held-out batches were generated, source-validated, checksummed, and
archived only; behavioral summaries are not committed for them and they have
not been opened for adequacy analysis. Set A
generation does not establish EV-005 library adequacy, which is tested only
after downstream net-load aggregation and transformer evaluation. The
authorized retrieval timestamp for seed `140001` is
`2026-07-17T09:52:03.233106Z`; the initial saved gzip wrapper checksum is
`723f72260517455d7981ef814012affb80c72a8b4935e11d661e77f4c6219924`, while a
later local recovery bug produced wrapper checksum
`7ea96ed8a113fd417957107926f4548b9f937dc1bd84703faefc0281e212d3df` without
changing the uncompressed JSON checksum
`d8dc58745311a772c171f3dee129d98b9c553833119f36e0d3a580dcb2cb7804`; the later
wrapper is recorded for audit only and is not a new retrieval.
The Set A library manifest is
`data/metadata/elaad_profiles/A_home_vancar_cp_y2030_set_a_library_manifest.json`;
the source-level report is `reports/elaad_e2_s2_home_cp_library_report.md`.
The superseded public Set B decision packet is recorded in
`data/metadata/elaad_profiles/B_public_vancar_cp_y2030_decision_packet.json`
and `reports/e2_s2_public_profile_decision_packet.md`. The follow-up EV-008A
amendment packet is recorded in
`data/metadata/elaad_profiles/B_public_vancar_cp_y2030_amendment_packet.json`
and `reports/e2_s2_ev008_public_profile_amendment_packet.md`; it signs the
equal-mix capacity-stratified public design for source generation and structural
validation only. Under that signed protocol, the public Set B source library
was generated locally as uncontrolled public `cp` profiles with the native
van/car mix, simulated year 2030, and equal 25% class shares at 11, 13, 15, and
22 kW. The candidate archive contains 1,200 distinct members from seeds
`152001` through `153101` in the approved per-class schedule, and the held-out
archive contains 400 distinct members from seeds `153201`, `153301`, `153401`,
and `153501`. Each of the 16 public batches returned 35,040 UTC timestamps, 100
profiles, 100 distinct member IDs, and no missing, non-finite, or negative
demand values. The public Set B library manifest is
`data/metadata/elaad_profiles/B_public_vancar_cp_y2030_set_b_library_manifest.json`;
the source-level report is `reports/elaad_e2_s2_public_set_b_library_report.md`.
Public Set B artifacts record only structural validation and provenance: no
public smart-charging, DC/fast charging, behavioral/tail adequacy analysis,
integrated net-load or event analysis, manuscript result, or claim that
`M = 1200` is sufficient is made.
Generated raw responses and converted local profile outputs remain
uncommitted and unredistributed; committed artifacts are limited to
retrieval/generation code, request configurations, seed schedules, metadata,
checksums, manifests, and shape reports. Readers must regenerate profiles
through the public API under the terms in force at retrieval time. Because
generated-profile redistribution terms remain unresolved, D-002 may not be
described as openly licensed or redistributable, and any explicit future
prohibition of this research use stops profile use pending PI escalation.

<!-- methods-id: D-003 -->
### D-003 - Heat-Pump Profiles

**Status: Approved for HP-001 internal shape/COP source use; final integrated
HP acceptance pending.** Temperature-dependent heat-pump demand is based on the
When2Heat dataset so heating behavior is tied to an openly documented empirical
profile source rather than invented load shapes. Source retrieval, checksum,
hourly-to-15-minute conversion, and COP treatment must be manifested before
use. The concrete source file is OPSD When2Heat package version
`2023-07-27`, single-index `when2heat.csv`, because that file contains the
hourly heat-profile, heat-demand, and COP columns consumed by the E2.S3 loader
without requiring the larger full archive. The prepared retrieval workflow
streams to a temporary raw file, records resumable checkpoint metadata, computes
the concrete SHA-256 after completion, and atomically promotes the file only
after the download has completed. After PI approval to run the retrieval, Agent
C downloaded `when2heat.csv` from the OPSD package URL on
2026-07-21T09:12:33Z, producing a 328400976-byte local raw file with SHA-256
`f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`. HP-001
approves this source for the first-pass Dutch residential space-heat and
domestic-hot-water shape/COP boundary. Space heating uses
`NL_heat_profile_space_SFH` and `NL_heat_profile_space_MFH` with
`NL_COP_ASHP_radiator`; domestic hot water uses
`NL_heat_profile_water_SFH` and `NL_heat_profile_water_MFH` with
`NL_COP_ASHP_water`. The implemented E2.S3 parser treats selected When2Heat
heat-profile columns as average MW per annual TWh and
requires the annual TWh scaling for each component to be passed explicitly, so
adoption or building-stock volumes are not hidden as defaults. The loader now
uses the real OPSD single-index CSV dialect explicitly (`;` delimiter and comma
decimals), reads the UTC timestamp column for the canonical calendar, records
the local timestamp column for provenance, and preserves selected heat/COP
column names plus OPSD unit metadata. Each component is divided by its matching
When2Heat COP column before aggregation, preserving distinct COP treatment for
space and water heating where those columns are selected. Hourly source values
are downscaled to 15 minutes by repeating the average-power value into four
quarter-hour intervals, which preserves energy and does not interpolate new
peaks. The resulting profile must match the
externally supplied shared weather/PV member on the canonical 15-minute UTC
calendar, preserving `shared_weather_driver_id`, `member_id`, source, optional
local calendar, and provenance or metadata so HP and PV outputs can be audited
as products of the same weather realization. The HP scaffold also rejects
weather inputs that lack an aligned PV/irradiance weather field and records the
PV weather field names in the heat-pump identity record; this is compatibility
scaffolding for the future shared weather contract, not a final contract
implementation. The heat-pump module does not sample weather independently or
shuffle timesteps. Commercial heat, local annual HP scaling for both space and
domestic hot water, WEATHER-001 implementation over accepted D-004 weather
members, numerical cold-spell tolerances, real paired-weather acceptance,
integrated event analysis, capacity-screen evidence, and manuscript results
remain separately blocked.

<!-- methods-id: E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN -->
### E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN - Heat-Pump Cold-Spell And Paired-Weather Acceptance Design

**Status: Approved predeclared design; numerical tolerances pending.** The E2.S3 cold-spell
and paired-weather acceptance design specifies how the project will later
evaluate whether When2Heat-derived heat-pump profiles are acceptable for use
with the ALEA-001 shared weather construction. The design requires HP and PV
outputs to preserve matching `member_id`, `shared_weather_driver_id`,
source/provenance, calendar records, and a future weather-content identity from
the same shared weather realization. It also predeclares the calendar,
cold-spell, and temperature-response diagnostics that a later acceptance report
must produce: complete 15-minute UTC/local calendar checks, coldest rolling
seven-day and three-day temperature windows, HP peak and COP timing, HP load
inside and outside cold windows, near-freezing diagnostics around 0 degrees C
to expose possible ASHP defrost or COP stress, winter/top-load overlap, and
paired plots and tables linking temperature, HP load, COP, and PV irradiance.
Including the near-freezing diagnostic prevents the source check from assuming
that the coldest absolute temperature is always the hardest heat-pump operating
condition. This paragraph and
the design packet do not approve D-004, do not set numerical acceptance
tolerances, do not run the check, and do not authorize net-load integration,
event analysis, `P(E)`, capacity-screen evidence, manuscript claims, or any
probability result. Final integrated D-003/D-004 acceptance remains pending
until WEATHER-001 is implemented, real D-004 weather members and checksums
exist, PI-signed tolerances and the exact near-freezing band are recorded before
inspection, the predeclared acceptance report is generated from committed code
and source metadata, and the PI explicitly accepts or escalates the resulting
evidence.

<!-- methods-id: E2-S3-HP-TECH-SCALING-DECISION-PACKET -->
### E2-S3-HP-TECH-SCALING-DECISION-PACKET - Heat-Pump Technology And Scaling Decision Packet

**Status: Proposed decision packet; HP-001 boundary approved separately.** The
E2.S3 heat-pump technology and scaling packet organizes the unresolved choices
that remain before real heat-pump integration: whether SFH/MFH/COM classes
remain separate through every downstream stage, whether annual thermal scaling
comes from When2Heat `heat_demand_*` evidence or from another registered
source, and how local 2035 heat-pump adoption volumes are derived. HP-001 now
approves the first-pass residential source/technology boundary: SFH/MFH space
heat with ASHP radiator COP plus SFH/MFH domestic hot water with ASHP water COP.
Commercial heat remains outside the primary run. The packet keeps all annual
TWh candidates as source-backed proposals rather than approved 2035, local,
electric-demand, or manuscript values. It also records that WEATHER-001
implementation, concrete D-004 members, final D-004 signoff, PI-signed
cold-spell tolerances, local annual HP scaling, and a real paired-weather
acceptance report remain blocking before final E2.S3 acceptance. This paragraph
and packet leave D-004
unsigned, do not set final numerical tolerances, do not run paired-weather
acceptance, and do not authorize net-load integration, event analysis, `P(E)`,
capacity-screen evidence, probability analysis, or manuscript-result claims.

<!-- methods-id: HP-001 -->
### HP-001 - First-Pass Residential HP Source And Technology Boundary

**Status: Approved.** The first full-analysis heat-pump boundary represents
residential electrification as space heating plus domestic hot water. This
matches the household story more closely than space heating alone: a home that
fully moves away from gas must also supply hot water electrically or through an
equivalent non-gas route. The source/technology route uses Dutch normalized
When2Heat space-heat profiles for single-family and multi-family houses
(`NL_heat_profile_space_SFH` and `NL_heat_profile_space_MFH`) converted with
the air-source heat-pump radiator COP series (`NL_COP_ASHP_radiator`), plus
Dutch residential water-heat profiles (`NL_heat_profile_water_SFH` and
`NL_heat_profile_water_MFH`) converted with the ASHP water COP series
(`NL_COP_ASHP_water`). SFH/MFH and space/water remain separate components until
aggregation so their provenance, annual scaling, and any later sensitivity
remain visible. Commercial heat is excluded from the primary run because its
building-stock boundary, adoption route, and service-area interpretation are
less aligned with the residential neighbourhood case; it may enter later only
through a signed sensitivity. The national When2Heat `heat_demand_*` columns
are retained as diagnostic/source anchors but are not adopted as the local 2035
annual HP scaling by default. Agent C must still propose a local annual HP
scaling or adoption route for both residential space heat and domestic hot
water before real integrated HP load is used. The E2.S3 scaffold exposes this
boundary through explicit component metadata: each selected component records
its shape column, COP column, end use, building class, annual TWh input, and
provenance before any aggregation. WEATHER-001 implementation, D-004
acceptance, cold-spell tolerances, event analysis, `P(E)`, and manuscript
results remain blocked.

<!-- methods-id: E2-S3-HP-LOCAL-SCALING-ROUTE-PACKET -->
### E2-S3-HP-LOCAL-SCALING-ROUTE-PACKET - HP-001 Local Annual Scaling Route

**Status: Proposed packet; values unsigned.** The local annual heat-pump
scaling route separates HP-001's approved residential shape/COP boundary from
the still-unsigned local 2035 annual thermal volumes. The proposed route derives
four explicit component inputs, SFH space heat, MFH space heat, SFH domestic
hot water, and MFH domestic hot water, from a PI-signed local service-area
proxy, source-backed residential stock or heat-demand denominators, and a
signed 2035 heat-pump adoption/electrification scenario. The resulting annual
TWh values would be passed explicitly into the HP-001 helper and preserved in
component provenance before aggregation; commercial heat remains outside the
primary route. National When2Heat `heat_demand_*` totals remain diagnostic
anchors unless the PI separately signs them as a local scaling source. This
packet proposes source classes, formulas, and sensitivity axes only. It does
not sign any external HP scaling source, annual TWh value, adoption count,
D-004 acceptance, cold-spell tolerance, net-load integration, event analysis,
`P(E)`, capacity-screen result, Q-5-dependent threshold result, or manuscript
number.

<!-- methods-id: E2-S3-HP-SOURCE-PROXY-CLARIFICATION -->
### E2-S3-HP-SOURCE-PROXY-CLARIFICATION - HP-001 Local Scaling Source And Proxy

**Status: Proposed packet; route not yet approved.** The HP-001 local scaling
source/proxy clarification packet narrows the unsigned annual-scaling route by
asking the PI to choose a local service-area proxy, a first retrieval source
bundle, and an adoption interpretation before any values are calculated. Agent
C recommends Alkmaar municipality `GM0361` for geographic consistency with
EV-007A and D-004, CBS StatLine dwelling-stock-by-type evidence for the
`SFH/MFH` denominator, and PBL Startanalyse 2025 Alkmaar evidence for local
heat-transition and heat-demand context. The packet explicitly treats national
or current heat-pump statistics as context unless a separate 2035 adoption
source is signed, and it treats Startanalyse pathway evidence as suitability
unless the PI signs it as adoption. This packet does not retrieve data, approve
any source, compute or sign annual TWh values, set D-004 acceptance,
cold-spell tolerances, event analysis, `P(E)`, capacity-screen results,
Q-5-dependent threshold work, or manuscript numbers.


<!-- methods-id: E2-S3-HP-SOURCE-USE-DECISION-PACKET -->
### E2-S3-HP-SOURCE-USE-DECISION-PACKET - HP-001 D-013 Source-Use Decision Packet

**Status: Proposed source-use packet; annual values unsigned.** This packet
classifies the retrieved D-013 CBS/PBL evidence before any HP-001 annual heat
values are calculated. CBS StatLine 85035NED is proposed as the Alkmaar
`GM0361` dwelling-stock and SFH/MFH crosswalk source, subject to PI approval of
the proxy/year rule. PBL Startanalyse 2025 Alkmaar is treated as
pathway/suitability and building-stock context unless the PI later signs exact
heat-demand columns, units, and formulas; the current cheap schema evidence does
not itself prove a useful-thermal space/DHW split or 2035 adoption. CBS StatLine
85523NED remains national/current heat-pump context only. The associated HP
readiness code may preserve component traces and build review-limited profiles,
but executable integrated HP loads require signed annual-scaling provenance for
every SFH/MFH and space/water component. This proposed packet does not sign
D-004, annual TWh values, HP adoption, cold-spell tolerances, net-load/event
analysis, `P(E)`, capacity screens, manuscript numbers, or probability results.

<!-- methods-id: E2-S3-HP-SCALING-RETRIEVAL-ROUTE -->
### E2-S3-HP-SCALING-RETRIEVAL-ROUTE - HP-001 Alkmaar Public-Source Retrieval Route

**Status: Approved retrieval/checksum route; values unsigned.** The HP-001
Alkmaar scaling retrieval route binds the earlier local-scaling source/proxy
packet to an auditable public-source workflow without authorizing any annual
heat-pump volume. It approves CBS StatLine 85035NED as dwelling-stock/type
evidence for SFH/MFH denominators, PBL Startanalyse aardgasvrije buurten 2025
Alkmaar as local heat-demand and heat-transition pathway evidence subject to
schema inspection, and CBS StatLine 85523NED as national/current heat-pump
context only. The scientific purpose of the route is to separate three roles
that could otherwise be conflated: local heat-demand evidence, pathway or
suitability evidence, and unsigned 2035 heat-pump adoption. Future retrieval
must store raw public files under ignored `data/raw/hp_scaling/`, write
source-by-source byte size, SHA-256, URL, timestamp, and checkpoint metadata
under `data/metadata/hp_scaling/`, and preserve SFH/MFH plus space/DHW
traceability for the four HP-001 residential components before aggregation.
The PI-supplied private student thesis may guide discovery of public underlying
sources only; it is not cited, quoted, committed, or used as value provenance.
This approval authorizes retrieval, checksum recording, and schema inspection
for D-013. It does not calculate or execute annual TWh values, sign 2035
adoption, approve D-004, run paired-weather acceptance, or authorize net-load,
event, `P(E)`, threshold, capacity-screen, manuscript, or probability results.
<!-- methods-id: D-004 -->
### D-004 - Weather and PV Inputs

**Status: Approved for internal first-screen source/member use; final paired/cold-spell acceptance pending.** KNMI observations provide the Dutch weather ensemble,
while PVGIS supplies the solar-generation reference used to construct or check
PV profiles. The E2.S4 support code records official PVGIS/KNMI retrieval
endpoints, a metadata-only raw retrieval execution plan, target raw/metadata
paths, checksum policy, checkpoint/resume requirements, and PI long-run notice
text. After PI approval for a narrow checksum-recording retrieval, Agent C
retrieved the proposed Alkmaar/Berkhout bundle
`d004_alkmaar_berkhout_2014_2023_v1`: PVGIS 5.3 `PVGIS-SARAH3` seriescalc and
TMY JSON responses at the exogenous Alkmaar GM0361 representative point
`52.63167,4.74861`, plus KNMI station 249 Berkhout validated hourly station
ZIPs for 2011-2020 and 2021-2030. The committed D-004 metadata records the raw
file paths, source URLs, file sizes, SHA-256 checksums, and the boundary that
PVGIS outputs are calibration or validation references only. A later
source-readiness memo and metadata file verify that the four local raw files
still match those checksums, that KNMI station 249 has complete hourly `T` and
`Q` rows for 2014-2023, and that the PVGIS-SARAH3 Alkmaar hourly series covers
exactly the same 2014-2023 years. These records are proposed for PI review; they
do not sign the KNMI hourly source-use evidence, create accepted 15-minute
weather members, or authorize manuscript claims. Per ALEA-001, each later
usable weather member must carry one timezone-aware, complete, chronological
UTC/local calendar plus paired temperature and irradiance channels, so heat-pump
and PV integration can consume the same weather-member identity through
WEATHER-001. PV conversion parameters and PVGIS sanity-check tolerances are
supplied explicitly by the caller; a PVGIS typical-year reference is used for
calibration or validation only, not as an independently sampled realized weather
path. Seasonal energy and peak timing are checked against PVGIS output before
integration. The PI-approved `D004-MC-001` member-construction rule uses UTC
calendar-year members, Europe/Amsterdam local timestamps derived from the UTC
axis, zero-order expansion of KNMI temperature, energy-preserving expansion of
KNMI hourly `Q` into 15-minute GHI, and PVGIS as calibration/validation
provenance only. Agent C has now implemented that approved builder and written
metadata-only member records for 2014-2023, including member IDs,
shared-weather-driver IDs, UTC/local calendar metadata, source-file checksums,
and WEATHER-001 content hashes; raw source files remain ignored and no processed
array store is committed. A follow-up readiness-diagnostics artifact validates
the committed member manifest, raw-file checksum continuity where the ignored
local files are present, UTC/local cadence consistency, KNMI-Q energy
preservation, finite/nonnegative weather channels, PVGIS/KNMI seasonal and peak
diagnostics without signed tolerances, and shared HP/PV weather-driver identity
as PI-review evidence only. A subsequent proposed acceptance packet
packages the concrete source files and checksums, member completeness and
calendar evidence, KNMI `T`/`Q` conversion checks, PVGIS provenance boundary,
seasonal and peak diagnostics, and explicit PI questions about source/member
acceptance and unsigned sanity criteria. A paired-weather acceptance scaffold then records what source/member evidence could be accepted now if the PI agrees and what remains blocked by unsigned PVGIS seasonal/peak criteria, paired HP/PV validation, cold-spell tolerances, and later integrated analysis. A subsequent acceptance/tolerance packet makes those governance gates explicit for PI review: exact source/member audit checks appear satisfied for review, while PVGIS seasonal/peak criteria, paired HP/PV validation rules, and cold-spell numerical tolerances remain unsigned. A concise PI recommendation packet proposed signing source/member acceptance separately, using qualitative PVGIS seasonal/peak sanity for that gate, requiring exact WEATHER-001 identity/calendar equality before HP/PV paired diagnostics, and leaving HP cold-spell numerical tolerances to the HP acceptance lineage. The PI approved that recommendation for internal first-screen source/member use on 2026-07-22: KNMI remains the realized weather path, PVGIS remains qualitative sanity/provenance only, exact WEATHER-001 identity/calendar equality is required for paired HP/PV use, and numerical cold-spell tolerances remain deferred to the HP/cold-spell decision. A committed WEATHER-001 source/member component-input artifact now exposes the accepted 2014-2023 member index, preserving `D004-SOURCE-MEMBER-ACCEPTANCE`, member IDs, content hashes, calendar IDs, cadence, and shared weather-driver IDs while explicitly retaining final paired/cold-spell and integrated-analysis blockers. D-004 final paired/cold-spell acceptance remains pending until the
PI accepts the concrete files, versions, checksums, source-use evidence,
completeness checks, PVGIS seasonal and peak-timing sanity checks, and final
integrated HP/PV acceptance.


<!-- methods-id: D004-SOURCE-MEMBER-ACCEPTANCE -->
### D004-SOURCE-MEMBER-ACCEPTANCE - D-004 Source/Member Acceptance For Internal First-Screen Use

**Status: Approved for internal first-screen source/member use; final paired/cold-spell acceptance pending.** The PI approved the D-004 recommendation packet on 2026-07-22. The approved scope accepts `d004_alkmaar_berkhout_2014_2023_v1` as the KNMI/PVGIS source/member bundle for internal first-screen use: KNMI station 249 Berkhout is the realized 2014-2023 WEATHER-001 weather path, PVGIS-SARAH3 remains qualitative seasonal/peak sanity and provenance/calibration context only, and paired HP/PV use requires exact WEATHER-001 identity/calendar equality before diagnostics are judged. The equality prerequisite covers `member_id`, `shared_weather_driver_id`, `source`, UTC span, timestep count, cadence, and `content_sha256`. Numerical cold-spell tolerances remain deferred to the HP/cold-spell acceptance decision. This approval does not run final paired HP/PV validation, approve cold-spell tolerances, authorize net-load integration, event analysis, `P(E)`, capacity screens, or manuscript results.

<!-- methods-id: PV-PARAM-001 -->
### PV-PARAM-001 - PV Conversion Parameter Signoff Packet

**Status: Proposed; unsigned fail-closed scaffold only.** The PV/weather readiness layer records `PV-PARAM-001` as the proposed primary first-pass PV conversion parameter set after D-004 source/member acceptance. As amended by PV-ORIENT-001, the first-experiment template `pv_param_001_first_pass_statistical_geometry_ghi_pr086_no_temp_clipped_v1` keeps the lightweight route but replaces a single fixed geometry with a typical/statistical orientation-and-tilt distribution once that distribution and its conversion treatment are signed. The template still requires signed `installed_capacity_kw` per node or fleet from a separate capacity route such as PV-CAP-001, uses accepted WEATHER-001 KNMI `Q`-derived `ghi_w_per_m2` as the realized irradiance basis, maps the approved PVGIS reference request loss setting of 14% to `performance_ratio = 0.86`, disables PV temperature correction with `temperature_coefficient_per_c = 0.0` and `reference_temperature_c = 25.0`, and clips nonnegative output at installed capacity. This is a proposed first-screen simplification and not empirical PV performance evidence. Until the PI signs this parameter decision, `PVSystemConfig` can support scaffold and unit-test calculations but its guard method raises before signed executable PV input use. This proposed packet does not approve installed-capacity source, numeric capacity, capacity convention, 2035 scaling, per-node allocation, exact orientation/tilt distribution values, final paired HP/PV acceptance, cold-spell tolerances, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, or manuscript results.
<!-- methods-id: D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET -->
### D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET - PV-PARAM Conversion Source Choice

**Status: Proposed packet; formula and values unsigned.** This packet prepares a PI-facing choice layer for amending or replacing the disputed first-pass PV-PARAM conversion route before executable PV generation. It compares three unsigned candidates: a pvlib-style plane-of-array route using signed statistical orientation/tilt classes and the realized WEATHER-001 KNMI `ghi_w_per_m2` path, PVGIS-SARAH3 reference output as qualitative calibration/sanity context only, and a direct-GHI scalar fallback only if the PI explicitly signs that simplification. The packet records what each route can and cannot prove, the required approvals for transposition or direct-GHI treatment, decomposition, albedo, losses/performance ratio, temperature correction, clipping and capacity convention, D-014 capacity artifact, node allocation, and A-016 scenario consistency. PVGIS remains provenance/calibration context rather than a realized sampled weather path, and PV-ORIENT-001 continues to block building-, roof-, 3DBAG-, or PV-map-level geometry before the first experiment. This packet does not approve `PR = 0.86`, a direct-GHI formula, pvlib or plane-of-array implementation, any numerical PV capacity/growth/orientation value, allocation, PV output, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or final paired HP/PV acceptance.
<!-- methods-id: D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET -->
### D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET - First-Experiment PV Approval Packet

**Status: Proposed packet; executable PV blocked.** This packet is a PI-facing approval checklist for the first executable PV experiment. It consumes checksummed proposed inputs for the D-014 capacity approval template, the PV-ORIENT-001 orientation/tilt source and value-choice packets, the PV-PARAM conversion source-choice packet, and the executable PV preflight guard. Its purpose is to keep four decision layers separate before any PV profile can be produced: installed capacity and 2035 growth under PV-CAP-001/D-014, statistical orientation/tilt source and class values under PV-ORIENT-001, irradiance-to-power conversion under PV-PARAM-001 or a signed amendment, and node allocation under a later allocation rule. The executable gate remains false until signed capacity, signed statistical distribution, signed conversion parameters, A-016 scenario consistency, signed node allocation, and final paired HP/PV acceptance exist. The packet preserves the lightweight first-experiment scope: typical/statistical orientation and tilt only, with building-, roof-, 3DBAG-, and PV-map-level geometry deferred to later work. It does not approve a PV capacity value, II3050 growth factor, DC/AC convention, orientation/tilt bins or weights, PR value, efficiency, conversion formula, node allocation, PV output, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or final paired HP/PV acceptance.

<!-- methods-id: PV-CAP-001 -->
### PV-CAP-001 - PV Installed-Capacity Source Route

**Status: Approved route; executable values pending.** PV installed capacity is treated as a separate modelling input from the irradiance-to-power conversion. The approved route anchors present-day capacity to a concrete Alkmaar CBS photovoltaic-capacity source, then scales that local anchor to the frozen 2035 planning layer using a signed Netbeheer Nederland II3050/scenario growth factor. This matches the project story that a DSO would start from local asset/adoption information rather than infer installed capacity from the weather model. DEGO, CBS building/geography data, Zonnedakje, 3DBAG, and the PI-supplied Kostas thesis may support source discovery, spatial allocation, or roof-geometry workflow design only if the exact data, license, retrieval path, and provenance are registered first. However, PV-ORIENT-001 defers building-level roof geometry from the first real experiment; those sources may inform later refinements, while the first experiment uses only a typical/statistical orientation-and-tilt distribution after its source and weights are signed. The decision does not by itself approve a numeric capacity, CBS row/year/field, II3050 growth value, DC/AC convention, per-node allocation, PV-PARAM-001 conversion parameters, statistical orientation/tilt weights, net-load/event analysis, `P(E)`, capacity screens, or manuscript results.



<!-- methods-id: D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE -->
### D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE - CBS Alkmaar PV Capacity Anchor Evidence

**Status: Proposed evidence; values unsigned.** This packet records the first concrete source evidence for the PV-CAP-001 local capacity anchor without selecting an executable capacity value. The retrieval queries CBS StatLine/OData table `85005NED` for Alkmaar municipality `GM0361`, stores the ignored raw OData bundle under `data/raw/pv_capacity/`, and commits metadata with the exact query URLs, raw bundle SHA-256 and size, table modification timestamp, topic fields and units, period keys and statuses, sector/category keys, all retrieved Alkmaar rows, and row candidates for PI review. The evidence shows that the table provides panel capacity in `kWp`, inverter capacity in `kW`, installation counts, and municipal Alkmaar rows across definitive and provisional periods, but those observations do not by themselves decide whether the executable anchor should use a definitive or provisional period, all sectors or homes only, panel/DC or inverter/AC convention, or any specific row. II3050 scenario scaling, node allocation, statistical orientation/tilt values, PV-PARAM conversion treatment, final PV output, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, and final paired HP/PV acceptance remain unsigned and outside this evidence packet. PV-ORIENT-001 is preserved: no roof, building, 3DBAG, or PV-map geometry evidence is retrieved or used for the first-experiment path.


<!-- methods-id: D014-II3050-PV-GROWTH-EVIDENCE -->
### D014-II3050-PV-GROWTH-EVIDENCE - II3050 PV Growth Evidence

**Status: Proposed evidence; values unsigned.** This packet records the concrete Netbeheer Nederland source evidence for the PV-CAP-001 scenario-growth side without selecting an executable growth factor. The retrieval downloads the public `Bijlagen II3050 eindrapport` PDF to ignored raw storage, commits metadata with the exact publication and PDF URLs, raw SHA-256 `7bcfe6607464590df3b755b6a9e531409927b100f1a79f15faba00d67d7c95ce`, file size `14784688` bytes, citation/license route, and Table A.1 `Zon PV*` row candidates. The packet lists 2035 candidate scenario columns `KA`, `ND`, and `IA` in GW and records denominator/formula options for PI review, but those observations do not decide which scenario corresponds to the project branch, whether the denominator should be II3050's 2019 reference or a CBS-anchor-year crosswalk, or whether a uniform national growth factor is acceptable for Alkmaar. CBS anchor period/field/convention, II3050 scenario column, growth denominator, growth formula/value, scenario consistency, node allocation, statistical orientation/tilt values, PV-PARAM conversion treatment, final PV output, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, and final paired HP/PV acceptance remain unsigned and outside this evidence packet. PV-ORIENT-001 is preserved: no roof, building, 3DBAG, or PV-map geometry evidence is retrieved or used for the first-experiment path.


<!-- methods-id: D014-PV-CAPACITY-VALUE-CHOICE-PACKET -->
### D014-PV-CAPACITY-VALUE-CHOICE-PACKET - PV Capacity Value-Choice Packet

**Status: Proposed packet; values unsigned.** This packet combines the retrieved CBS Alkmaar anchor evidence and Netbeheer Nederland II3050 PV growth evidence into a PI-facing decision layer without computing or approving an executable PV capacity. It lists candidate equations for local 2035 installed PV capacity, including DC panel-capacity and AC inverter-capacity variants, CBS period/sector/field operands, II3050 2035 scenario-column operands, and denominator/formula alternatives. The packet recommends for PI review a source-year-consistent DC panel-capacity route: use a CBS `kWp` panel-capacity operand and scale it by a signed II3050 `Zon PV*` 2035-to-reference growth ratio, while keeping the output explicitly labelled as `installed_capacity_kwp_dc` until PV-PARAM-001 or an amendment decides how that capacity convention maps into the PV conversion model. This recommendation is not a sign-off. A-016 remains a blocker because EV, HP, and PV sources use different scenario systems; II3050 `KA`/`ND`/`IA` columns must not be silently equated with ElaadNL or HP branches. The PI must still approve the CBS period, sector/category, field, unit and DC/AC convention, II3050 scenario column, growth denominator, formula and value, scenario-consistency mapping, node allocation, statistical orientation/tilt source and weights, and PV-PARAM conversion before executable PV input is produced. No PV generation, net-load/event analysis, `P(E)`, threshold analysis, capacity screen, manuscript number, roof/building/3DBAG/PV-map geometry, or final paired HP/PV acceptance is produced by this packet.


<!-- methods-id: D014-PV-CAPACITY-APPROVAL-TEMPLATE -->
### D014-PV-CAPACITY-APPROVAL-TEMPLATE - PV Capacity Approval Template

**Status: Proposed template; values unsigned.** This packet defines the contract that a later PI-signed D-014 executable PV capacity artifact must satisfy, but it does not instantiate that artifact or approve any value. It is derived from the D014-PV-CAPACITY-VALUE-CHOICE-PACKET metadata checksum and lists required fields for the artifact identity, installed-capacity value and DC/AC convention, CBS Alkmaar anchor operand, II3050 scenario-growth operand, A-016 scenario-consistency mapping, node allocation, statistical orientation/tilt dependency, PV-PARAM conversion dependency, and audit checksums. The executable gate is deliberately false: unsigned templates cannot provide installed capacity to PV generation. A later signed artifact must record the exact CBS row/period/sector/field, capacity unit, II3050 scenario and denominator, growth-factor formula/value, A-016 mapping, allocation rule, statistical orientation/tilt distribution, and PV-PARAM decision before executable PV input is allowed. This template does not approve final PV capacity, growth factor, orientation/tilt values, node allocation, PV generation, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, roof/building/3DBAG/PV-map geometry, or final paired HP/PV acceptance.


<!-- methods-id: D014-PV-EXECUTABLE-READINESS-BLOCKERS -->
### D014-PV-EXECUTABLE-READINESS-BLOCKERS - PV Executable Readiness Blockers

**Status: Proposed blocker manifest; executable PV blocked.** This packet records the current boundary between accepted PV/weather component inputs and executable first-experiment PV generation. It checksums the accepted D-004 WEATHER-001 weather input artifact and the unsigned D-014/PV capacity, orientation/tilt, and PV-PARAM review artifacts, then exposes a single fail-closed gate: source/member weather readiness is available, but executable PV generation is not authorized. The remaining blockers are the PI-signed D-014 capacity artifact, A-016 scenario-consistency mapping across EV/HP/PV sources, statistical orientation/tilt source and values under PV-ORIENT-001, PV-PARAM conversion approval or amendment, node allocation provenance, and final paired HP/PV plus HP cold-spell acceptance decisions. This packet does not approve PV capacity, growth factor, orientation/tilt values, allocation, conversion parameters, PV output, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or roof/building/3DBAG/PV-map geometry before the first experiment.


<!-- methods-id: D014-PV-EXECUTABLE-PREFLIGHT-GUARD -->
### D014-PV-EXECUTABLE-PREFLIGHT-GUARD - PV Executable Preflight Guard

**Status: Proposed preflight guard; executable PV blocked.** This packet turns the D014-PV-EXECUTABLE-READINESS-BLOCKERS manifest into a deterministic fail-closed preflight result for future PV/integration wiring. It checksums the blocker manifest, records that D-004 source/member weather readiness is available, and carries the unresolved D-014 capacity, A-016 scenario-consistency, PV-ORIENT, PV-PARAM, allocation, and final paired/cold-spell blocker IDs forward. If invoked as an executable PV preflight, the only authorized behavior is to abort with the blocker manifest; producing a PV profile or any downstream number remains forbidden. Proposed and unsigned tokens are allowed only as non-executable metadata describing the blockers. This packet does not approve PV capacity, growth factor, orientation/tilt values, allocation, conversion parameters, PV output, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or roof/building/3DBAG/PV-map geometry before the first experiment.

<!-- methods-id: D014-PV-CAPACITY-SOURCE-VALUE-PACKET -->
### D014-PV-CAPACITY-SOURCE-VALUE-PACKET - PV Capacity Source/Value Packet

**Status: Proposed packet; values unsigned.** The D-014 source/value packet turns the approved PV-CAP-001 route into a concrete PI review checklist without retrieving raw capacity data or approving any value. It proposes CBS StatLine/OData table 85005NED as the Alkmaar `GM0361` installed-PV anchor, records schema probes for table metadata, fields, periods, regions, and sector/size-class codes, and uses a `TypedDataSet` row-filter template over Alkmaar, source period, and sector/size class. It separately identifies the Netbeheer Nederland II3050 edition 2 appendices as the source to inspect for the 2035 PV growth-factor row and scenario column. The packet requires later signed approval for source checksums, Alkmaar geography, CBS period, capacity field, DC/AC capacity convention, II3050 scenario and growth-factor value, node allocation, statistical orientation/tilt source and weights, and PV-PARAM conversion before executable PV input can be produced. PV-ORIENT-001 defers optional 3DBAG, DEGO, Zonnedakje, and building-geography roof-geometry work until after the first real experiment unless a later signed amendment reopens that scope. This packet does not approve numeric installed capacity, a growth factor, per-node allocation, the `PR = 0.86` conversion scalar, a statistical geometry distribution, net-load/event analysis, `P(E)`, capacity screens, or manuscript results.

<!-- methods-id: PV-ORIENT-001 -->
### PV-ORIENT-001 - First-Experiment PV Orientation/Tilt Scope

**Status: Approved scope; exact values and formula pending.** For the first real experiment, PV orientation and tilt are represented through a typical/statistical distribution rather than through building-specific roof geometry. This choice keeps the first integrated experiment tractable while avoiding the unrealistic implication that all PV capacity has the same south-facing 35-degree geometry. The distribution must be source-backed and signed before executable PV generation, and the implementation must manifest the source, bin definitions, weights, and whether the distribution changes the irradiance conversion or remains a parameter attached to the PV component. The source-choice packet proposes candidate sources but signs none of them. Per-building, per-roof, location-specific 3DBAG extraction, and the fuller PV-map/pvlib workflow are deferred until after the first go/no-go result. This paragraph records a scope decision only; it does not approve distribution values, a GHI-to-plane transposition rule, installed capacity, allocation, PV-PARAM-001, net-load/event analysis, `P(E)`, capacity screens, or manuscript results.

<!-- methods-id: D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET -->
### D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET - PV Orientation/Tilt Source Choice

**Status: Proposed packet; source and values unsigned.** This packet prepares the PI decision needed before PV-ORIENT-001 can become executable. It proposes candidate evidence sources for the first-experiment statistical PV orientation-and-tilt distribution while preserving the ban on building-level, roof-level, location-level, and 3DBAG per-roof extraction before the first real experiment. The primary empirical candidate is Killinger et al. (2018), which analyzes PV-system metadata including tilt, azimuth, capacity, and yield across large international datasets and approximates parameter distributions by cluster. A Dutch regional rooftop-PV study is listed as local plausibility context, and Ramadhani et al. (2023) is listed as an open statistical-method template if the PI accepts a transfer assumption from Swedish rooftop-facet evidence. PVGIS can support class-wise sanity checks, and pvlib or an equivalent transparent formula can support later conversion implementation, but neither supplies class weights. JRC/DBSM, 3DBAG, and other building-level PV-map routes remain deferred future improvements. The packet does not choose a final source, approve class bins, representative angles, class weights, capacity-weighting convention, capacity value, node allocation, `PR = 0.86`, direct-GHI or plane-of-array conversion, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or final paired HP/PV acceptance.



<!-- methods-id: D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET -->
### D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET - PV Orientation/Tilt Value Choice

**Status: Proposed packet; values unsigned.** This packet turns the PV-ORIENT-001 source-choice work into concrete, PI-reviewable statistical orientation-and-tilt class values without making them executable. It keeps Killinger et al. (2018) as the preferred empirical extraction route if Netherlands-relevant distribution parameters can be accessed and cited, and records a five-class symmetric rooftop prior only as an explicit assumption fallback for first-screen review. The fallback uses capacity-weight fractions and representative azimuth/tilt candidates, but those numbers are not source-extracted evidence and cannot drive executable PV until the PI signs the source or assumption ID, bins, representative angles, weight basis, weight-sum tolerance, capacity convention, D-014 capacity artifact, node allocation, and PV-PARAM conversion treatment. PV-CAP-001 remains the separate installed-capacity route through the CBS Alkmaar anchor and II3050/scenario growth factor. PV-PARAM-001 remains proposed/fail-closed and this packet does not approve `PR = 0.86`, direct-GHI conversion, a plane-of-array or pvlib route, per-building/roof-level extraction, 3DBAG/PV-map work before the first experiment, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or final paired HP/PV acceptance.

<!-- methods-id: D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET -->
### D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET - Statistical PV Orientation/Tilt Packet

**Status: Proposed packet; values unsigned.** The first-experiment PV geometry route is narrowed to statistical orientation and tilt classes only. Building-level, roof-level, and location-level extraction, including a specific 3DBAG per-roof workflow, is deferred to later sensitivity or validation work because the PI judged that route too intensive before the first real experiment. The proposed packet records the future artifact shape for a signed class table: class IDs, declared azimuth basis, tilt, capacity-weight fractions, source or assumption IDs, installed-capacity input reference, capacity convention, PV conversion config ID, and provenance. It does not approve any class bins, class weights, capacity weighting convention, capacity value, DC/AC convention, per-node allocation, `PR = 0.86`, direct-GHI conversion, pvlib/PVGIS-style plane-of-array formula, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, manuscript numbers, or final paired HP/PV acceptance. PV-CAP-001 remains the separate capacity route through CBS Alkmaar and II3050/scenario scaling; PVGIS remains sanity/provenance only unless a later signed decision amends its role.
<!-- methods-id: D004-MC-001 -->
### D004-MC-001 - D-004 Weather-Member Construction Rule

**Status: Approved; authorizes builder implementation only.** The approved
D004-MC-001 construction rule converts the approved D-004 Alkmaar/Berkhout raw
bundle into one WEATHER-001 member per UTC calendar year for 2014-2023. Each
member uses a timezone-aware 15-minute UTC axis, derives Europe/Amsterdam
local timestamps from those same instants, interprets KNMI `HH` as UT
hour-ending slots with `HH=24` mapped to 00:00 UTC on the following date, and
carries member IDs `d004_alkmaar_berkhout_<YEAR>_v1` plus shared weather-driver
IDs `d004_alkmaar_berkhout_2014_2023_v1:<YEAR>`. Station 249 KNMI `T` is
converted from tenths of a degree Celsius to `temperature_c = T / 10` and
repeated over the four represented quarter-hour timestamps. Station 249 KNMI
`Q` is converted from hourly `J/cm2` to hourly-average
`ghi_w_per_m2 = Q * 10000 / 3600` and repeated across the four quarter-hour
sub-intervals, preserving the source hourly radiation energy without inventing
an unobserved within-hour solar shape. PVGIS-SARAH3 seriescalc and TMY files
are copied into provenance only as calibration or validation references, not as
realized sampled weather paths. A later sensitivity may use energy-preserving
within-hour irradiance interpolation, but the primary first-pass rule remains
hourly KNMI `Q` repeated across four quarter-hours. This approval does not sign
final D-004 source acceptance, set PVGIS seasonal or peak tolerances, run HP/PV
paired acceptance, or authorize cold-spell acceptance, net-load integration,
event analysis, `P(E)`, capacity screens, manuscript claims, or probability
results. The builder implementation and metadata records do not expand the
approved scientific rule: they only materialize the signed UTC-year,
block-constant first-pass construction and record auditable member/content
identity for later WEATHER-001 consumers.

<!-- methods-id: D-005 -->
### D-005 - Flexibility Delivery Evidence

**Status: Proposed citation row.** Observed flexibility-delivery statistics
from Mueller and Jansen are used as an empirical anchor for the practical
controllability elicitation, not as a probability distribution copied directly
into the model. The reported range and central delivery behavior inform the
candidate fuzzy support and core; G4 separately records expert interpretation
and signs the membership function. This separation prevents one pilot study
from being treated as universally representative of future Dutch flexibility.

<!-- methods-id: D-006 -->
### D-006 - Procurement Interpretation

**Status: Proposed citation row.** Article 32 of Directive (EU) 2019/944 is used
to frame the required controllability level as a transparent flexibility-
procurement target available to a DSO before reinforcement. The regulation
motivates the decision interpretation but does not supply numerical overload
thresholds, flexibility performance, or costs; those quantities remain
separately evidenced and uncertain.

<!-- methods-id: D-007 -->
### D-007 - Transformer Loading Rationale

**Status: Proposed citation row.** IEC 60076-7 provides the engineering basis
for treating transformer loading as time-dependent and for distinguishing a
persistent episode from an isolated 15-minute exceedance. The project does not
claim to implement a full hot-spot thermal model or derive an exact emergency
rating from the standard. Instead, the one-hour event and single-step
sensitivity make the simplified planning proxy explicit and test its influence.

<!-- methods-id: D-008 -->
### D-008 - Dutch Cost Anchors

**Status: Source approved; extracted values pending.** Reinforcement-cost
anchors are extracted from the locally supplied Cicenas thesis under a strict
provenance scheme. Every value retains its physical unit, project context,
page and table reference, interpretation status, and PI approval. Values are
used as indicative planning inputs and subjected to economic sensitivity; they
are not generalized beyond the documented Stedin/Eneco context or presented as
current regulated prices.

<!-- methods-id: D-009 -->
### D-009 - DFMP Probability-to-Possibility Transform

**Status: Approved citation/protocol source for E7.S1.** The elicitation workflow uses
the probability-to-possibility transformation of Dubois, Foulloy, Mauris, and
Prade to convert finite probability evidence into a possibility, or fuzzy-
membership, distribution. A possibility grade is not a probability and is not
a percentile: grade 1 means that a state is among the most plausible and is not
excluded by the evidence, not that the state is certain. The DFMP transform
returns the tightest, maximally specific possibility distribution that still
conservatively contains the original probability model, meaning that every
event `A` satisfies `P(A) <= Pi(A)`, where `Pi(A)` is the maximum possibility
grade among the states in `A`. For normalized finite masses `p_i`, the default
formula is `pi_i = sum(p_j for p_j <= p_i)`; if separate plausibility scores are
supplied, the same cumulative rule is applied over states with no greater
score. Equal probability masses, or equal supplied scores, receive equal
possibility grades rather than arbitrary rank-order splits. The implementation
is checked against the paper's Example 4.1, where the maximally specific
transform of the stated piecewise-linear density gives `pi(-1.5)=0.3`. This
approval covers only the citation/protocol source and the implemented
maximally specific finite DFMP convention; E7.S2 and G4 still determine the
input probabilities, flexibility values, and fuzzy corners before any paper
result uses them.

<!-- methods-id: D-010 -->
### D-010 - ElaadNL Outlook Mobility Adoption Counts

**Status: Source-approved for EV-007A local counts.** E2.S6 records EV
charging-infrastructure projections from the official ElaadNL Outlook
Mobiliteit scenariotool/API. The first D-010 use records national December
`charging_infrastructure` values for 2030, 2033, and 2035 under the low,
middle, and high scenarios; these national records are not physical
charge-point counts for the SimBench grid and must not flow into nodal
allocation. The second use records the EV-007A-approved Alkmaar (`GM0361`)
municipality local-count workflow for 2035, using the same home/public
locations and low/middle/high scenarios. Delft (`GM0503`) is recorded only as a
checked fallback municipality. The source site identifies the scenariotool as
providing forecasts down to CBS-neighbourhood level, supplies report and model
background pages, states that the outlook is assumption-based and indicative
with a 24-month validity note, identifies Scenariotool v1.0.0 as last updated
on 9 June 2026, and licenses the site under CC BY-NC-ND 4.0. The committed
config and metadata record exact query strings, UTC retrieval time, raw floating
API values, nearest-integer rounded counts, and response checksums without
redistributing raw dashboard data. The frozen minimal evidence packet
`data/metadata/ev_adoption/d010_elaad_outlook_minimal_evidence.json` collects
the approved Alkmaar API/schema evidence in one reviewable artifact: six local
queries, their response hashes, the 26-row response-shape note, the selected
2035/December row fields, the rounding rule, and the no-raw-redistribution
boundary. Public behavior profiles are separately governed by the EV-008A
capacity-stratified generation protocol.

<!-- methods-id: D-011 -->
### D-011 - II3050 Scenario Framing

**Status: Proposed.** Netbeheer Nederland's II3050 edition 2 eindrapport,
published on 11 October 2023 according to the Netbeheer Nederland publication
page, is recorded as scenario-framing evidence for 2030-2050 infrastructure
planning. It justifies treating adoption pathways as scenario inputs relevant
to network planning, but E2.S6 does not extract numerical EV charge-point
counts from II3050. Keeping D-011 separate prevents a broad infrastructure-
scenario report from being mistaken for a numeric source of home or public
charge-point counts, while still documenting the wider Dutch planning context
in which the ElaadNL Outlook scenarios are considered.

<!-- methods-id: D-012 -->
### D-012 - NDW/DOT-NL Public Charging Inventory

**Status: Proposed contextual evidence; not executable unless promoted.** D-012
records NDW/DOT-NL laadpunten open data as current infrastructure context for
the public-charging unit and capacity questions that informed EV-008A. The
source is used only as a decision packet unless a later PI decision promotes it
to an executable data source; it is not a profile library, adoption-count source,
or congestion input: raw live NDW responses are not committed, and no ElaadNL
public Set B profile is generated by this evidence packet. The OCPI full
dataset exposes a hierarchy of locations, EVSEs, and connectors, including
connector `max_electric_power`; the GeoJSON bbox endpoint provides a smaller
spatial cross-check. For Alkmaar, the committed metadata records both an exact
`city == Alkmaar` slice and a broader Alkmaar-area bbox because the OCPI file
does not expose a CBS municipality code. Therefore D-012 can support the
interpretation that one public ElaadNL `cp` member should correspond to a
charge-point/EVSE/connector-like unit rather than a pole, while exact `GM0361`
municipality counts require a separate boundary join. The observed current
connector-power distribution includes substantial 11 kW-ish, 13 kW, 15 kW, and
22 kW-ish groups, so D-012 weakens any claim that 22 kW is the unique
representative current Alkmaar public capacity. It therefore provides contextual
support for the EV-008A choice to use an amended equal-mix capacity-stratified
public profile design instead of treating 22 kW as the only current-fleet
representative capacity. D-012 does not itself approve capacity weights, count
units, or any future inventory-to-grid allocation unless a later PI decision
explicitly promotes that use.





<!-- methods-id: E2-S3-HP001-EXECUTABLE-VALUE-BINDING-BRIEF -->
### E2-S3-HP001-EXECUTABLE-VALUE-BINDING-BRIEF - HP-001 Executable Value-Binding Decision Brief

**Status: Proposed brief; executable annual values and final paired acceptance unsigned.** The HP-001 executable value-binding decision brief restates the merged packet as simple PI approval options: approve or amend PBL `Referentie_2030`, PBL `I11_woningequivalenten [Woning]`, GJ/year-to-TWh/year conversion by division by `3,600,000`, the CBS 85035NED SFH/MFH split rule, and the 2035 HP service/adoption/electrification route for residential space heat plus domestic hot water. Its candidate adoption options are unsigned scenario choices only: a `0.50` first-pass service fraction, a `0.25`/`0.50`/`0.75` low/mid/high scenario set, a PBL pathway sensitivity using `A08_Aandeel_eWP_GJ` with `A07_Aandeel_eWP_WEQ` and `A02_Aansl_eWP` diagnostics, or a future external public source. The fractions are not source-estimated adoption values, not probabilities, and not executable annual HP TWh. Final HP use remains blocked on separately signed D-004 paired-weather acceptance and cold-spell numerical tolerances. This brief does not approve annual HP values, net-load/event analysis, `P(E)`, threshold/capacity-screen results, manuscript numbers, or probability results.
<!-- methods-id: E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET -->
### E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET - HP-001 Executable Value-Binding Decision Packet

**Status: Proposed packet; executable annual values and final paired acceptance unsigned.** The HP-001 executable value-binding packet is an approval template, not an approval. It asks the PI to approve or amend the remaining annual value-binding choices: PBL `Referentie_2030` value-column use, PBL `I11_woningequivalenten [Woning]` denominator use, GJ/year-to-TWh/year conversion by division by `3,600,000`, CBS 85035NED count-share allocation over SFH/MFH, and the 2035 HP service/adoption/electrification scenario for space heat and domestic hot water. It also keeps final integrated HP use blocked on separately signed D-004 paired-weather acceptance evidence and cold-spell numerical tolerances. The generated candidate record remains fail-closed with blank approval IDs and a non-approved status, so the HP adapter rejects it until a later signed record is committed. This packet does not approve annual HP TWh values, D-004 paired-weather or cold-spell acceptance, net-load/event analysis, `P(E)`, threshold/capacity-screen results, manuscript numbers, or probability results.
<!-- methods-id: E2-S3-HP001-READINESS-APPROVAL-CHECKLIST -->
### E2-S3-HP001-READINESS-APPROVAL-CHECKLIST - HP-001 Final-Readiness Approval Checklist

**Status: Proposed checklist; executable annual values and final paired acceptance unsigned.** The HP-001 readiness checklist separates the approvals that still block integrated heat-pump use after HP-001 and A-015/D013-PBL-MAPPING. The annual value-binding group requires explicit PI approval for PBL `Referentie_2030` value-column use, `I11_woningequivalenten [Woning]` denominator use, GJ-to-TWh conversion by division by `3,600,000`, the CBS 85035NED SFH/MFH count-share split, and the 2035 HP service/adoption/electrification scenario. The weather-acceptance group separately requires final D-004 paired-weather acceptance evidence and signed cold-spell numerical tolerances. The implementation scaffold can list missing approval keys and raises until all required IDs are present, so approved shape/COP and indicator mapping cannot by themselves create executable integrated HP inputs. This checklist does not approve annual HP TWh values, D-004 paired-weather or cold-spell acceptance, net-load/event analysis, `P(E)`, threshold/capacity-screen results, manuscript numbers, or probability results.
<!-- methods-id: E2-S3-HP001-VALUE-BINDING-READINESS -->
### E2-S3-HP001-VALUE-BINDING-READINESS - HP-001 Value-Binding Readiness Packet

**Status: Proposed packet; executable annual values unsigned.** The HP-001 value-binding readiness packet prepares the future handoff from D-013 local-scaling evidence into the guarded HP component configuration without approving the values. It records candidate PBL `Referentie_2030`, `I11_woningequivalenten [Woning]`, GJ-to-TWh conversion, CBS 85035NED count-share allocation, and four unsigned SFH/MFH by space/DHW component value drafts before any 2035 HP adoption/electrification multiplier. The accompanying adapter, `hp001_local_scaling_config_from_value_binding_record`, is fail-closed: it rejects the current proposed packet and returns `HP001LocalScalingConfig` only if a later record is explicitly marked `approved_for_executable_value_binding` and carries approval IDs for value-column use, denominator use, unit conversion, SFH/MFH split, and adoption/electrification. This packet does not approve annual TWh values, D-004 or cold-spell acceptance, net-load/event analysis, `P(E)`, threshold/capacity-screen results, manuscript numbers, or probability results.
<!-- methods-id: E2-S3-HP001-SCALING-FORMULA-CONFIG -->
### E2-S3-HP001-SCALING-FORMULA-CONFIG - HP-001 Local Scaling Formula/Config Guard

**Status: Proposed packet; executable annual values unsigned.** The HP-001 local scaling formula/config packet records the remaining decisions needed after A-015/D013-PBL-MAPPING approved only the PBL indicator mapping assumption. The proposed route would use PBL `Referentie_2030` values from `Alkmaar_strategie.csv`, multiply the approved residential space and domestic-hot-water indicators by `I11_woningequivalenten [Woning]`, convert GJ/year to TWh/year by division by `3,600,000`, split each end use over SFH/MFH using CBS 85035NED count shares unless another split is signed, and then apply a separately signed 2035 HP service/adoption/electrification multiplier. The implementation scaffold is fail-closed: `HP001LocalScalingConfig` records candidate choices and values, but `hp001_components_from_local_scaling_config` raises until approval IDs are present for value-column use, denominator use, unit conversion, SFH/MFH split, and 2035 adoption/electrification. This packet does not approve annual TWh values, D-004 or cold-spell acceptance, net-load/event analysis, `P(E)`, threshold/capacity-screen results, manuscript numbers, or probability results.

<!-- methods-id: E2-S3-HP-LOCAL-SCALING-SOURCE-USE-PROPOSAL -->
### E2-S3-HP-LOCAL-SCALING-SOURCE-USE-PROPOSAL - HP-001 D-013 Local Scaling Source-Use Proposal

**Status: Partly resolved by D013-PBL-MAPPING; values unsigned.** The D-013 local scaling source-use proposal uses the retrieved CBS/PBL schema evidence to define a candidate route for later HP-001 annual thermal scaling, without making any value executable. D013-PBL-MAPPING and A-015 approve the narrow source-use assumption that `_w` means woningen/residential, `_u` means utiliteit/non-residential, `H23_Vraag_RV_w` is residential space-heating demand intensity, `H24_Vraag_TW_w` is residential domestic-hot-water demand intensity, and `H22_Vraag_totaal_w` is a residential total-demand diagnostic, all in `[GJ/weq/jaar]`. The exact raw-code meaning remains currently inferred from the raw-code pattern, the Dutch abbreviations for `ruimteverwarming` and `tapwater`, and Startanalyse documentation that explains the base heat-demand indicators and the 2025 woning/utiliteit split; no explicit PBL evidence was found for these literal raw labels.

The still-unsigned candidate conversion would multiply those intensities by PBL `I11_woningequivalenten [Woning]` and convert GJ to TWh, then allocate space and water separately to SFH/MFH using a PI-signed CBS 85035NED class split for Alkmaar `GM0361`. The packet records CBS `2026JJ00` `Eengezinswoningen totaal` and `Meergezinswoningen totaal` as denominator/crosswalk evidence and gives unsigned illustrative count-share and area-weighted allocations only to make the PI decision concrete. A separate signed 2035 HP adoption/electrification multiplier remains required before HP component values can be used. This proposal does not approve `Referentie_2030` as an executable value column, unit conversions beyond the A-015 indicator-unit interpretation, split rules, annual TWh values, adoption fractions, D-004 acceptance, cold-spell tolerances, net-load/event analysis, `P(E)`, threshold or capacity-screen analysis, manuscript numbers, or probability results.

<!-- methods-id: D013-PBL-MAPPING -->
### D013-PBL-MAPPING - D-013 PBL Startanalyse Indicator Mapping Assumption

**Status: Approved transparent assumption; executable values and adoption unsigned.** D013-PBL-MAPPING records the PI decision to use the PBL Startanalyse 2025 Alkmaar residential indicator mapping as an explicit assumption rather than as an undocumented loader convention. The mapping treats `_w` as woningen/residential, `_u` as utiliteit/non-residential, `H23_Vraag_RV_w` as residential space-heating demand intensity, `H24_Vraag_TW_w` as residential domestic-hot-water demand intensity, and `H22_Vraag_totaal_w` as a residential total-demand diagnostic, with units `[GJ/weq/jaar]`. The evidence basis is inferential: PBL documents H01/H02/H03 heat-demand concepts, documents that the 2025 municipal data distinguish woningen and utiliteit, and the official Alkmaar CSV schema and ASA25 template context are consistent with this interpretation, but no explicit PBL evidence was found that defines the literal H22/H23/H24 `_w` labels. The manuscript must therefore present this as a signed modelling/data assumption. This decision unlocks column naming for later HP-001 source-use work, but it does not approve value-column selection, formula use, annual HP TWh inputs, 2035 adoption/electrification, D-004 or cold-spell acceptance, net-load/event analysis, `P(E)`, capacity-screen conclusions, or manuscript results.

<!-- methods-id: E2-S3-HP-SCALING-SCHEMA-INSPECTION -->
### E2-S3-HP-SCALING-SCHEMA-INSPECTION - D-013 HP Scaling Schema Inspection

**Status: Proposed schema-inspection evidence; values unsigned.** The D-013
inspection workflow can refresh schema metadata from already retrieved CBS/PBL
raw files without network access or value extraction. For the PBL Startanalyse
2025 Alkmaar ZIP, it records full small-file CSV row counts, column
classifications, and `Code_Indicator`/`Eenheid` pairs, including heat-demand-like
H-series indicators such as `H01_Vraag_totaal`, `H02_Vraag_RV`, and
`H03_Vraag_TW` with unit `[GJ/weq/jaar]`. It also records candidate residential
building-type columns that could support a later PI-reviewed SFH/MFH crosswalk.
This evidence helps the PI decide whether PBL can support local heat-demand
scaling or should remain pathway/suitability context only. It does not select
columns, convert units, approve a space/DHW split, sign 2035 adoption, produce
annual TWh values, sign D-004, run cold-spell or paired-weather acceptance, run
net-load/event analysis, estimate `P(E)`, or produce manuscript numbers.

<!-- methods-id: D-014 -->
### D-014 - PV Installed-Capacity Source Bundle

**Status: Proposed source/value packet; CBS anchor and II3050 evidence retrieved; value-choice, approval-template, executable-readiness blocker, preflight guard, PV-PARAM conversion source-choice, and first-experiment approval packets prepared; executable values pending.** D-014 records the public-source bundle needed to implement PV-CAP-001. The primary candidate local anchor is CBS StatLine/OData table 85005NED for Alkmaar `GM0361`, because it is public, regionally disaggregated, and reports installed PV capacity and installation counts by sector and size class. The D-014 source/value packet records exact schema probes and row-filter templates, and D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE now records a retrieved/checksummed CBS Alkmaar OData bundle with schema and row candidates; however, the source period, selected sector/category, selected field, units, and DC/AC convention remain unsigned. D014-II3050-PV-GROWTH-EVIDENCE now records a retrieved/checksummed Netbeheer Nederland II3050 appendix PDF with Table A.1 `Zon PV*` candidate 2035 scenario columns; however, the scenario column, denominator, formula, and growth-factor value remain unsigned. D014-PV-CAPACITY-VALUE-CHOICE-PACKET combines those evidence packets into unsigned equations, convention recommendations, and A-016 scenario-consistency approval keys for PI review. D014-PV-CAPACITY-APPROVAL-TEMPLATE defines the fail-closed field contract for the later signed capacity artifact but contains no executable value. D014-PV-EXECUTABLE-READINESS-BLOCKERS records the current guard state: accepted D-004 weather source/member artifacts exist, while PV capacity, scenario consistency, orientation/tilt values, PV-PARAM conversion, allocation, and final paired/cold-spell gates still block executable PV generation. D014-PV-EXECUTABLE-PREFLIGHT-GUARD automates the next fail-closed preflight result and requires abort-with-blocker behavior if executable PV is requested too early. D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET and D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET then turn the remaining conversion and first-experiment signoff questions into proposed PI review surfaces without authorizing PV generation. PV-ORIENT-001 approves only the first-experiment scope: represent PV orientation and tilt through a typical/statistical distribution rather than building-specific roof geometry. A separate D-014 statistical orientation/tilt packet proposes the fail-closed class-table artifact shape; it does not approve source, bins, weights, or conversion treatment. 3DBAG, DEGO, CBS building-geography tables, Zonnedakje, and the separate PV-map methodology are deferred roof-geometry or allocation improvement sources unless explicitly registered and signed later. Before executable PV input uses this bundle, the project must record the exact retrieved files or API queries, checksums, selected geography, selected source year, selected capacity field and DC/AC convention, II3050 growth factor, per-node allocation rule, statistical orientation/tilt source and weights, and signed PV-PARAM conversion decision. D-014 does not approve any installed-capacity number, allocation, orientation/tilt distribution value, net-load/event analysis, `P(E)`, capacity-screen result, or manuscript number.
<!-- methods-id: D-013 -->
### D-013 - HP-001 Alkmaar Local Scaling Source Bundle

**Status: Approved retrieval/checksum route and indicator mapping assumption; values unsigned.** D-013 records
public source evidence for later deriving local annual heat-pump scaling inputs
for HP-001 in Alkmaar municipality `GM0361`. CBS StatLine 85035NED has now
been retrieved as filtered Alkmaar dwelling-stock/type evidence, with metadata
recording table version, periods 2021-2026, the SFH/MFH crosswalk to
`Eengezinswoningen totaal` and `Meergezinswoningen totaal`, byte size, URL, and
SHA-256 checksum. PBL Startanalyse aardgasvrije buurten 2025 `Alkmaar.zip` has
been retrieved from the public municipality data portal and inspected cheaply at
ZIP-directory and CSV-header level; the metadata records the `Alkmaar_bebouwing`,
`Alkmaar_strategie`, and `Alkmaar_totaalbebouwing` CSV schemas as evidence for
future heat-demand/pathway/suitability review. CBS StatLine 85523NED has been
retrieved as national/current heat-pump context only, not as a local 2035
adoption source. The retrieval manifest and per-source metadata record exact
URLs, byte sizes, SHA-256 checksums, timestamps, raw ignored paths, and resume
checkpoint state. A-015/D013-PBL-MAPPING approves the PBL residential indicator mapping as a transparent assumption, while leaving value-column use and annual scaling choices unsigned. This source bundle keeps local heat demand,
suitability/pathway evidence, and unsigned 2035 heat-pump adoption separate so
pathway suitability cannot become adoption volume by implication. The four
HP-001 components, SFH/MFH crossed with space/DHW, retain separate
annual-scaling provenance before aggregation. The PI-supplied private student
thesis is not a D-013 source and may be used only as confidential
source-discovery guidance for public underlying sources. D-013 does not approve
annual TWh values, 2035 HP adoption, final scaling choices, D-004 acceptance,
paired-weather cold-spell checks, net-load integration, event analysis, `P(E)`,
threshold runs, capacity-screen results, manuscript numbers, or probability
results.
<!-- methods-id: OWN-001 -->
### OWN-001 - Machine-Enforced Agent Ownership

**Status: Approved project-governance protocol.** Role ownership is enforced
from a versioned path policy through a planned-path preflight before editing,
a complete worktree check before local tests, and a pull-request status check.
Core implementation modules and their tests have exclusive
owners, while registers, methods prose, and task reports retain the shared
access needed for traceability. Unassigned paths fail closed. Cross-boundary
work is normally split so the owning agent supplies its own change; an
exception is accepted only when the PI has already merged an exact branch,
role, task, and path authorization into the base branch. Loading policy and
exceptions from that base revision prevents a pull request from granting
itself additional access. This governance check reduces accidental module
coupling and unreviewed interface changes but does not replace scientific,
test, manifest, or PI-sign-off review. Maintainer branches are defined by the
base policy as well. The sole code-level bootstrap exception is the initial
`codex/ownership-enforcement` pull request when neither policy file exists on
its base; after that first merge, the same branch is governed by the base
policy like every other branch.
