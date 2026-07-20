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

**Status: Approved historical basis; numerical threshold superseded by
G0-A3.** G0 originally defined an overload event as at least four consecutive
15-minute intervals in which import-direction apparent-power loading exceeds
1.0 p.u. The one-hour persistence requirement suppresses isolated sampling
spikes and reflects that transformer loading capability is time dependent
rather than determined by a single 15-minute excursion. G0-A3 retains this
structure but provisionally changes the numerical threshold to 1.1 p.u. The
primary metric remains the annual probability of at least one qualifying
episode, with a single-step event retained as a sensitivity.

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
### G0-A3 - Provisional 1.1 P.U. Overload Threshold

**Status: Approved working rule; mandatory PI review before scientific
analysis.** The executable event threshold is provisionally set to a strict
`L_import > 1.1 p.u.` for four consecutive 15-minute intervals. This retains
the approved import-direction, apparent-power, one-hour-persistence, and
full-year semantics while allowing temporary loading between nameplate and
110% not to trigger the binary event. The same threshold is used for the
single-step sensitivity and export-side exceedance diagnostic. The project
does not yet present 110% as a Dutch DSO standard or as a value derived from
IEC 60076-7. Before integrated event analysis, the PI must verify the source,
asset and capacity convention, determine whether one hour means four
consecutive quarter-hour exceedances or an hourly average, and decide whether
the 100-110% band requires a separate cumulative-exposure rule. Historical
diagnostics retain their manifested 1.0-p.u. threshold and are not
reinterpreted as evidence under this working rule.

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
cadence and transformer capacity/denominator provenance. This approval does
not resolve Q-5, total-versus-firm capacity, G2 error values, or numerical
A-013 grid-error values; those remain blocking dependencies for paper-facing
event results.

<!-- methods-id: RNG-001 -->
### RNG-001 - Seed-Tree and CRN Identity Protocol

**Status: Proposed; pending PI approval.** The proposed seed-tree protocol derives each whole-system aleatory sample from `(root_seed, sample_index)` and each component stream from that sample seed plus the component name. Component stream identities include root-derived stream information, currently the component seed, so a source-member selection made under one root seed cannot be replayed silently under another. Alpha levels, interval endpoints, and treatment labels are branch metadata only: they reuse the same complete aleatory realization and therefore do not enter the aleatory fingerprint. Manifests record the root seed, sample seed, component stream records, selected source-member IDs, and shared physical driver IDs. CRN reuse is a variance-control and pairing device across analysis branches; it is distinct from physical dependence, which is represented separately by shared drivers such as paired weather members. This paragraph proposes the policy for PI review and does not by itself approve downstream scientific runs, Q-5 threshold semantics, IC schema changes, or any numerical uncertainty values.
<!-- methods-id: ALEA-001 -->
### ALEA-001 - Joint Aleatory Dependency Protocol

**Status: Approved.** Each Monte Carlo sample is constructed as one coherent
planning-year realization on a common timezone-aware 15-minute calendar rather
than as independently shuffled component values. A complete historical weather
member anchored to one KNMI calendar year is selected as a paired multivariate
trajectory, so temperature, irradiance, seasonality, and persistence remain
associated; any supplementary irradiance series must cover the same timestamps
and year, and a typical-year PV reference is not sampled as the realized
weather. The heat-pump and PV models consume that same aligned member. EV and baseline inputs retain
complete temporal paths and are mapped deterministically to the common season
and weekday/weekend calendar before aggregation. This conditional construction
preserves dependencies with an identified physical or calendar driver without
claiming an unsupported full joint probability distribution. Common random
numbers then reuse the complete realization across alpha levels,
controllability endpoints, model-error endpoints, and treatments, but are not
treated as a substitute for physical dependence. Leap-year and daylight-saving
mapping are versioned and tested after the concrete weather files are selected,
and manifests record all weather/profile member IDs and mapping versions. If
held-out tail or dependence diagnostics show material residual dependence that
this construction misses, a shared latent factor, multivariate block bootstrap,
or evidence-fitted copula is introduced only through a separately signed and
manifested sensitivity protocol.

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

**Status: Approved primary route; within-realization replacement rule pending.**
The EV aleatory layer samples complete annual members directly from the frozen,
checksummed ElaadNL profile library rather than fitting a second behavioral
distribution to generated profiles. This retains the generator's session
timing, duration, seasonality, and serial dependence while keeping each selected
member traceable through its batch seed and returned profile index. Profile
member IDs and seed metadata are stored in experiment manifests rather than
reported as scientific parameters in the manuscript. Finite-library adequacy is
tested against integrated transformer results under ALEA-002 and is reported
separately from Monte Carlo sampling error. Whether members may be resampled
with replacement inside one system realization remains unresolved until the
generator's same-seed warning and the scenario-specific EV/charge-point cohort
sizes are reconciled. If direct bootstrapping cannot satisfy those conditions,
the calibrated stochastic sampler remains an explicit fallback rather than an
unreported substitution.

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

**Status: Approved protocol; numerical stopping tolerance and within-realization
replacement rule pending.** The archived ElaadNL library is treated as a finite
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
its members, so independent held-out generation is mandatory and ordinary
within-library bootstrapping is only supplementary.
The acceptance tolerance is fixed before the adequacy results are inspected and
is tied to transformer-result or reinforcement-decision stability rather than
to an isolated EV-profile percentile.

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

**Status: Proposed.** Temperature-dependent heat-pump demand is based on the
When2Heat dataset so heating behavior is tied to an openly documented empirical
profile source rather than invented load shapes. Source retrieval, checksum,
hourly-to-15-minute conversion, and COP treatment must be manifested before
use. Cold-period validation checks that demand peaks under physically plausible
temperature conditions and that temporal downscaling does not manufacture
additional energy.

<!-- methods-id: D-004 -->
### D-004 - Weather and PV Inputs

**Status: Proposed.** KNMI observations provide the Dutch weather ensemble,
while PVGIS supplies the solar-generation reference used to construct PV
profiles. Both sources are retrieved through scripts with file-level checksums
and timezone-aware conversion. Per ALEA-001, a sampled temperature member and
any supplementary irradiance series must cover the same historical timestamps;
a PVGIS typical-year reference is used for calibration or validation, not as an
independently sampled weather realization. Their combination provides Dutch
climatic coherence for temperature- and irradiance-driven technologies, while
seasonal energy and peak timing are checked against PVGIS output before
integration.

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


