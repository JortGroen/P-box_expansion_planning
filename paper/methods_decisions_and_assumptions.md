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

**Status: Approved. Overload event.** An overload event is defined as at least
four consecutive 15-minute intervals in which import-direction apparent-power
loading exceeds 1.0 p.u. A one-hour persistence requirement suppresses isolated
sampling spikes and reflects that transformer loading capability is time
dependent rather than determined by a single 15-minute excursion. The primary
metric is the annual probability of at least one such episode over the
aleatory ensemble. A single-step event is retained as a sensitivity so that
the influence of the persistence convention remains visible.

**Status: Approved. Risk threshold and sampling protocol.** The primary
decision threshold is `P_crit = 10^-2`, evaluated with `N = 10^4` common-random-
number samples over the full alpha grid. A `10^-3` sensitivity uses `N = 10^5`
and the reduced alpha set `{0, 0.5, 1.0}`, with local alpha refinement only when
a decision boundary lies inside an unresolved bracket. The larger sample at
the lower probability keeps binomial relative error of similar order. The
threshold is fixed independently of case selection; cases are made informative
by selecting scenario and year, never by tuning `P_crit` after results are
seen.

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

<!-- methods-id: G1 -->
### G1 - Two-Tier Network Evaluation

**Status: Approved with G2 validation conditions.** Monte Carlo samples are
evaluated by radial summation of downstream net active and reactive power,
while AC power flow is used for deterministic checks and manifested validation
subsets. The measured high-level pandapower `runpp` path required about 105 ms
per solve on the 117-bus primary grid, making billions of time-step solves
impractical through that measured path; this does not establish that all AC
implementations are infeasible. Tier-1 therefore supplies the computational
path, but its agreement with pandapower is a G2 hypothesis rather than an
accepted accuracy claim. A lower-level TimeSeriesCPP benchmark and a held-out
near-threshold enclosure test determine the eventual AC-validation budget and
whether Tier-1 remains admissible.

<!-- methods-id: G1-A1 -->
### G1-A1 - Model-Output Error Propagation

**Status: Approved framework; numerical envelopes remain proposed.** Grid-
model discrepancy is represented as an interval on transformer-loading output,
not as a margin added to an already estimated overload probability. The lower
and upper loading trajectories are classified by the same four-step event
detector, and binomial confidence intervals are computed from the resulting
event counts. No probability distribution or independence assumption is
assigned to the discrepancy; its dependence on inputs, controllability, and
time may be arbitrary within the stated envelope. Tier-1-to-AC approximation
error is estimated separately at G2 and combined only on compatible quantities
and units. This construction preserves the physical episode semantics and
prevents numerical approximation error from being hidden inside the p-box.

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
sweep, selection criteria, rejected candidates, and why the selected case is
decision-informative without tuning `P_crit` or other frozen thresholds.

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

**Status: Proposed row; fallback not invoked by current evidence.** A fallback
mapping from 2033 to the 2035 EV behavior library was predeclared in case the
ElaadNL API did not accept a native 2033
simulation year. The one-profile probe accepted `simulated_year = 2033`, so the
fallback is not used. Native 2033 behavior is retained, avoiding an unnecessary
assumption that per-vehicle charging behavior is unchanged between 2033 and
2035.

<!-- methods-id: A-010 -->
### A-010 - EV Charging Power

**Status: Proposed.** Home and public charging profiles use nominal connection
powers of 11 kW and 22 kW, respectively, matching the profile-generator
configuration selected for the primary library. These values define possible
charging power, while coincidence, arrival, dwell time, and delivered energy
remain profile-driven; they therefore do not imply that every vehicle charges
at nameplate simultaneously. A 7.4 kW home sensitivity is retained to test
whether the connection-power convention materially changes aggregate peaks.

<!-- methods-id: A-011 -->
### A-011 - Elaad Profile Scaling

**Status: Proposed.** A generated home `ev` profile already represents the
home-charging share embedded in the generator's charging mix. Nodal aggregation
therefore multiplies it by the number of EVs with home access without applying
a second home-share factor. Public `cp` profiles scale with public charge-point
count. This convention prevents systematic undercounting through duplicate mix
weights and is checked by comparing aggregated nodal energy with the sum of the
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
distribution state estimation. A candidate symmetric relative interval places
physical loading within `(1 +/- epsilon_grid)` times modeled loading. A 5%
reference value with 2% and 10% sensitivities is draft manuscript wording, not
an empirical bound or confidence interval. Input uncertainties represented
elsewhere are excluded, matched solver-to-solver numerical differences are an
implementation check, and the interval is applied before episode detection
with arbitrary dependence on inputs and time. The transformer measurement
boundary, mechanism ownership, human review, and final values must be signed
before this paragraph becomes manuscript authority.

## Data and Evidence Choices

<!-- methods-id: D-001 -->
### D-001 - SimBench Network and Baseline Profiles

**Status: Proposed data row; use governed by G0 and DEP-001.** SimBench supplies
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
with one value per timestamp for the single requested profile. Generated raw
responses, converted libraries, and parquet outputs remain uncommitted and
unredistributed; committed artifacts are limited to retrieval/generation code,
request configurations, seed schedules, metadata, checksums, manifests, and the
library plan. Readers must regenerate profiles through the public API under the
terms in force at retrieval time. Because generated-profile redistribution terms
remain unresolved, D-002 may not be described as openly licensed or
redistributable, and any explicit future prohibition of this research use stops
profile use pending PI escalation.

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
and timezone-aware conversion. Their combination provides Dutch climatic
coherence for temperature- and irradiance-driven technologies, while seasonal
energy and peak timing are checked against PVGIS output before integration.

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


