# Project Plan (v3) — "When can grid reinforcement wait?"

**Manuscript working title:** *When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility*
**Internal method label:** p-box uncertainty propagation for flexibility-aware distribution grid reinforcement deferral

---

## About this project — orientation for new readers

**The problem in plain terms.** Electrification — electric vehicles, heat pumps, rooftop solar — is pushing local electricity grids toward their limits. The companies that operate these grids (distribution system operators, DSOs) must decide, transformer by transformer, whether to physically reinforce the grid (expensive, slow, and possibly unnecessary) or to wait, relying on *demand-side flexibility*: shifting flexible consumption such as EV charging and heat pumps away from the critical peak hours. The catch is that how much of that flexibility will *actually* be controllable years from now depends on future customer participation, contracts, technology and policy — something nobody can put a trustworthy probability distribution on today.

**What this project does.** We keep the planning rule DSOs already use — the probability of overloading the asset must stay below a threshold P_crit — but we stop pretending a single overload probability can be computed when flexibility is this uncertain. Instead we compute honest *lower and upper bounds* on the overload probability, indexed by how strong an assumption about flexibility one is willing to make (the α-level of a fuzzy number describing controllability). From those bounds we derive four planner-ready quantities (§4): how credible deferral is (α\*), how much controllable flexibility must be secured for deferral to be defensible (ρ\*, a procurement target), how many years reinforcement can safely wait (the deferral horizon), and whether paying for a pilot to learn more is worth it (value of information). A benchmark experiment (§5) shows that the four standard ways of treating this uncertainty each give a different — and individually misleading — answer to the same question; our bounds expose the assumption each of them silently makes.

**Glossary.**

| Term | Meaning here |
|---|---|
| DSO | Distribution system operator — runs the MV/LV grid |
| MV / LV | Medium voltage (10–20 kV) / low voltage (0.4 kV) distribution levels |
| Reinforcement / deferral | Physically upgrading a transformer or cables vs. postponing that investment |
| Decision transformer | The transformer whose reinforcement/deferral is being decided — MV/LV in the motivating use case; the HV/MV unit of the SimBench MV grid in the case study |
| Demand-side flexibility | Shiftable consumption (EV charging, heat pumps, batteries) usable to relieve grid peaks |
| Controllability ρ_flex | Fraction of technically flexible demand that is *practically controllable during grid-critical periods* — this project's key uncertain quantity |
| Aleatory vs. epistemic uncertainty | Natural variability (weather, behaviour) vs. lack of knowledge (future participation); the first is modelled with probabilities, the second with intervals/fuzzy numbers |
| Fuzzy number & α-cut | A stack of nested intervals encoding expert/pilot knowledge; α ∈ [0,1] indexes assumption strength: α=1 the core belief, α=0 the widest plausible range |
| P-box (probability box) | Lower and upper bounds on a probability — here, on the overload probability |
| P_crit | Maximum acceptable overload probability in the planning rule P(overload) ≤ P_crit |
| CRN | Common random numbers — identical random draws across compared cases, so differences reflect assumptions rather than sampling noise |
| VoI | Value of information — what reducing uncertainty (e.g., via a pilot) is worth |
| SimBench / pandapower / lightsim2grid | Open benchmark grid dataset / Python power-system analysis tool / fast power-flow backend |
| EV / HP / PV / DER / DSR | Electric vehicle / heat pump / photovoltaics / distributed energy resources / demand-side response |
| N-1 | Planning rule requiring the system to survive any single component failure |
| IGDT | Info-gap decision theory — a non-probabilistic robustness method (related work) |
| Monte Carlo (MC), N | Random sampling of the aleatory inputs; N = number of samples |

---

## TL;DR

- **The paper's headline is now the DECISION LAYER, not the propagation.** Compute four α-indexed decision metrics — critical α\*, minimum required controllability ρ\* (framed as an EU-Directive-2019/944-Art.-32 procurement target), the 2030/2033/2035 deferral horizon, and p-box width as value-of-information — and prove their worth with a five-treatment **decision-reversal benchmark** that shows the deterministic, single-distribution, worst-case-interval and scenario-minimax methods each reach a *different and individually misleading* defer/reinforce decision, while the fuzzy/p-box method exposes which assumption each one silently makes.
- **Concrete, decisive build:** primary grid = a **SimBench MV grid (semi-urban/urban) with LV aggregated at secondary substations** via the `simbench` 1.6.2 + pandapower >=3.4,<4 stack; **drop the parameter-less Liander grid** for this paper; physics = **two-tier** (net-load summation in the Monte Carlo loop + `lightsim2grid` AC validation subset — native pandapower solves take ~28–37 ms/step, lightsim2grid ~0.17–0.6 ms, ~20× faster); focus on **adaptive import-direction critical windows** per G0-A1, with export/feed-in exceedance reported as a side metric; N = 1e4–1e5 with common random numbers; **P_crit ≈ 1e-2** (1e-3 sensitivity), justified by IEC 60076-7 thermal tolerance and observed <1% DSO exceedance practice, with the honest caveat that no single official Dutch loading-% exists.
- **~12-week single-paper sprint** with an early monotonicity go/no-go gate and the decision layer + decision-reversal + pilot-anchored elicitation on the critical path; target **Applied Energy** (backups IJEPES, SEGAN). Report α-indexed bounds only — **never a single defuzzified number** (Baudrit et al. rule).

---

## Key Findings

1. **The right novelty framing exists and is defensible.** P-box power flow itself is *not* new (multiple published methods exist; §Details/§10), so the contribution must be the decision layer built on top — where no prior distribution-planning study operates.
2. **A German benchmark carrying Dutch data beats a Dutch topology with no parameters.** SimBench provides four statistically-validated MV grids with full-year 15-min time series and three future scenarios, natively in pandapower — everything the per-planning-year overload metric and 2030/33/35 horizon need. The project's own Liander-based Dutch grid (built from Liander open data) has accurate topology but no electrical parameters, so it cannot support AC load flow or a credible overload criterion without fabricated data — a reviewer-attack surface. Dutch character is injected through Dutch adoption/EV/weather data, not topology.
3. **Compute is a laptop problem, not an HPC problem.** With net-load summation in the inner loop and `lightsim2grid` for AC validation, N = 1e4–1e5 samples per (endpoint, α, year) over critical-week windows is feasible in hours on a laptop; the monotonicity/vertex shortcut and common random numbers make it cheaper and more decision-stable.
4. **There is no single published Dutch numeric loading criterion**, but there is enough to justify a transparent choice: IEC 60076-7 permits distribution-transformer cyclic loading to 1.5 p.u. and long-time emergency to 1.8 p.u., [StudyLib](https://studylib.net/doc/25626887/iec-60076-7-2005-power-transformer--part-7--loading-guide...) and a documented DSO practice defines congestion at >100% loading with tolerated exceedance at <1% likelihood [arxiv](https://arxiv.org/pdf/2402.15728) (an explicit P_crit ≈ 0.01).
5. **Every anticipated reviewer attack catalogued in §10 has a specific citable rebuttal** (Ferson & Tucker 2008; Cao et al. 2018 chance-constrained IGDT; the p-box power-flow papers; Aien et al. 2014; Baudrit et al. 2006/2007; Dubois–Foulloy–Mauris–Prade 2004), mapped one-to-one in §10 below.

---

## Details

### 0. Version history
**v3 (this document):** manuscript retitled to *“When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility”*; new-reader orientation and glossary added at the top; Müller & Jansen caveat refreshed after full-text verification. **v2:** restructured the original plan per Section 11 ("Recommended sharpening") and the "Where the biggest gap lies" verdict of the combined literature review. The propagation chain is retained as *infrastructure*; the novelty and the argument now live in the α-indexed decision metrics, the five-treatment decision-reversal benchmark, and the pilot-anchored elicitation. All fuzzy/p-box mathematics from the original plan is preserved; only its framing and the reporting rules change.

### 1. Use case (retained, lightly edited)
A Dutch distribution system operator (DSO) must decide whether reinforcement of an MV/LV area can be **deferred** given uncertain demand growth (EVs, heat pumps), PV, batteries and demand-side flexibility. The conventional metric P(overload) ≤ P_crit is retained but **replaced by lower/upper probability bounds** [P_lower^α(E), P_upper^α(E)] for each α-level of a fuzzy flexibility-controllability assumption. The decision unit is one distribution transformer group or feeder — MV/LV in the motivating neighbourhood use case, instantiated in the case study at the HV/MV transformer of the SimBench MV grid. Throughout, we call this asset the **decision transformer**.

The controllability assumption is a **trapezoidal fuzzy number ρ̃_flex** for the fraction of technically flexible demand that is *practically controllable during grid-critical periods*. Aleatory uncertainties (weather, baseline demand, EV arrival/SoC, household diversity) are probabilistic; grid-model output error is an interval — so the resulting p-box is **two-sourced** (epistemic width from both the fuzzy controllability cuts and the model-error interval).

**Co-simulation chain (retained):** weather → PV/HP models; adoption scenarios → nodal technology adoption + fuzzy flexibility; technology models → EV/HP/PV/battery profiles; nodal flexibility aggregator (applies fuzzy controllability) → adjusted net load; distribution load-flow → transformer/feeder loading; risk post-processor → p-box of overload probability; decision logic compares α-indexed upper bounds with P_crit.

### 2. Uncertainty taxonomy (retained)

| Source | Nature | Representation |
|---|---|---|
| Weather (irradiance, temperature) | aleatory | probabilistic (KNMI/DWD reanalysis-driven) |
| Baseline household demand | aleatory | probabilistic (SimBench/NEDU profiles + diversity) |
| EV charging profiles | aleatory | probabilistic profile library generated with the ElaadNL Laadprofielengenerator, frozen and checksummed per `reports/elaad_profile_generation_spec.md` |
| Household diversity | aleatory | probabilistic |
| Technology adoption share (EV/HP/PV/battery) | deep/scenario | scenario set (II3050 / ElaadNL outlook) |
| Flexibility controllability ρ_flex | epistemic/possibilistic | trapezoidal fuzzy number ρ̃_flex |
| Grid-model output error | epistemic | interval |

Aleatory variables → Monte Carlo; ρ̃_flex → α-cuts; model error → interval widening each α-cut. Output: a p-box on P(overload).

### 3. Mathematical core (retained, with reporting discipline added)
For each α ∈ {0, 0.25, 0.5, 0.75, 1.0}, the α-cut of ρ̃_flex is an interval [ρ_lo^α, ρ_hi^α]. Propagating the endpoints (see §7) through the Monte Carlo aleatory ensemble and widening by the model-error interval yields [P_lower^α(E), P_upper^α(E)]. Stacking cuts gives the p-box and the possibility/necessity (plausibility/belief) measures on the event "P(overload) ≤ P_crit."

**Reporting discipline (Baudrit et al. warning, hard rule):** results are reported as α-indexed bounds and as belief/plausibility pairs. **We never collapse the p-box to a single defuzzified number.** Any scalar is shown only alongside its bracketing bounds.

### 4. HEADLINE CONTRIBUTION — the decision layer (the core of the paper)

**(a) Critical α — α\*.** α\* = inf{α : P_upper^α(E) ≤ P_crit}. Deferral is defensible only if one is willing to assume controllability at possibility level ≥ α\*. Low α\* ⇒ robust deferral; α\* near 1 ⇒ deferral relies on the most optimistic controllability assumption and is fragile.

**(b) Minimum required controllability — ρ\*.** The smallest controllable share with P(E | ρ\*) ≤ P_crit. The membership value μ(ρ\*) read off ρ̃_flex is the **plausibility that deferral is safe**. ρ\* is framed as a **DSO procurement/contracting target**: the controllable-flexibility volume the DSO must secure (market procurement or flexible-connection contracts under **EU Directive 2019/944 Art. 32**, "Incentives for the use of flexibility in distribution networks") for deferral to meet the norm. Achievability is anchored against **Müller & Jansen (2019)**: 0.88 delivery success given enrollment, 40–65% deliverable core during the critical window, 29–90% observed extreme range. If ρ\* exceeds the plausibly contractable level → "reinforce"; if ρ\* sits inside the well-supported core → "defer-with-monitoring" is credible.

**(c) α-indexed deferral horizon.** For target years 2030 / 2033 / 2035, compute the latest year with P_upper^α(E) ≤ P_crit as a function of α — a "safe-deferral frontier" (e.g., deferral to 2033 safe for α ≥ 0.5 but to 2035 requires α ≥ 0.9). Answers "how long can I wait, and how strong an assumption does each extra year require?"

**(d) P-box width as value of information (VoI).** Width P_upper^α − P_lower^α at the decision-relevant α quantifies reducible epistemic uncertainty. Compare *deferral value* (deferred transformer capex, discounted) against *pilot cost*. If the box straddles P_crit and pilot cost < deferral value at stake → **collect-more-data**; else defer / defer-with-monitoring / reinforce.

**Decision logic table (α-indexed):**

| Condition on bounds | Decision |
|---|---|
| P_upper^{α=0}(E) ≤ P_crit (safe even at most pessimistic controllability) | **Defer** |
| P_upper^α ≤ P_crit only for α ≥ α\* (moderate) with narrow p-box | **Defer with monitoring** |
| P_lower^α > P_crit across α (unsafe even optimistically) | **Reinforce** |
| P-box straddles P_crit AND pilot cost < deferral value | **Collect more data** |

### 5. Decision-reversal benchmark experiment ("the money figure")
Same network, same aleatory ensemble, same target year, five treatments of the controllability factor, designed to disagree:
1. **Deterministic full availability** (Tavares & Soares 2020 style) → expected "defer."
2. **Single best-estimate distribution** (e.g. Beta at a point estimate) → "defer"/"defer-with-monitoring," one P.
3. **Pure worst-case interval** (controllability anywhere in [0.29, 0.90], unweighted) → "reinforce."
4. **Discrete scenario minimax** → often "reinforce," brittle to scenario choice.
5. **Fuzzy / p-box (ours)** → α-indexed: "defer-with-monitoring up to α\*, collect-more-data where the box straddles."

Deliverable: one table/figure showing 1–4 give different, individually misleading decisions while the p-box treatment exposes each one's hidden assumption. This is the paper's central empirical claim. The deterministic status quo these treatments bracket is not a straw man: current Dutch DSO-collaborated planning studies still reinforce by a manual, iterative maximum-loading procedure (Cicėnas 2025, with Stedin) — loading-threshold logic with no uncertainty layer at all.

### 6. Pilot-anchored elicitation protocol for ρ̃_flex
Multiplicative decomposition:
ρ̃_flex = (future enrollment share) × (delivery success given enrollment) × (deliverable fraction during critical window)
- **Future enrollment share** — expert/policy, deeply uncertain; from adoption scenarios (II3050 / ElaadNL outlook); widest (α=0) support.
- **Delivery success given enrollment** — 0.88 (Müller & Jansen 2019).
- **Deliverable fraction during critical window** — core [0.40, 0.65], extreme support [0.29, 0.90] (Müller & Jansen 2019).

Where **pilot statistics exist**, build the possibility distribution from data via the **Dubois–Foulloy–Mauris–Prade (2004) probability–possibility transformation** (Reliable Computing 10:273–297, doi:10.1023/B:REOM.0000032115.22510.b5), which yields nested confidence intervals dominating any symmetric distribution with the same mode/support — a defensible, non-arbitrary trapezoid shape. Where only expert bounds exist, set corners directly (core = likely range, support = plausible range).

**Sensitivity on trapezoid shape:** re-run α\*, ρ\*, horizon under (i) triangular, (ii) trapezoidal, (iii) piecewise-convex ("possible but unlikely" tails) shapes; report decision stability or identify flips. Cite Baudrit (2005) that shape subjectivity has far less consequence than arbitrarily selecting a single probability distribution. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0169772207000216)

### 7. Monotonicity / vertex shortcut (computational core)
**Claim:** during demand-driven peaks, overload probability is monotone *decreasing* in controllable share ρ. If it holds:
- **Each α-cut needs only endpoint (vertex) propagation** — evaluate ρ_lo^α and ρ_hi^α only.
- **Nested cuts permit sample reuse** — reuse the aleatory MC sample across α-levels and endpoints via **common random numbers (CRN)**, which also stabilises the *decision* (endpoint/treatment differences aren't swamped by MC noise).

**Verify numerically** (dense ρ sweep on a subset of draws) before relying on it (go/no-go, §11). **Caveat regimes flagged:** (i) *rebound/payback* — shifted EV/HP load creates a secondary peak that can break monotonicity; (ii) *reverse-PV-flow* — high-PV midday flips the binding constraint, where demand controllability acts differently. Where monotonicity fails, fall back to interior sampling on that cut. The **grid-model output-error interval is retained** so the p-box stays two-sourced even where the fuzzy width is narrow.

### 8. Design decisions (resolved with research)

**A. GRID CHOICE.** **Primary: a SimBench MV grid (semi-urban `1-MV-semiurb--0-sw` / urban `1-MV-urban--0-sw`) with LV aggregated at secondary substations**, via `simbench` 1.6.2 (`sb.get_simbench_net(code)`) + pandapower >=3.4,<4.
- The decision transformer in this setup is the HV/MV unit at the SimBench external-grid substation (the method is level-agnostic; the motivating MV/LV neighbourhood case maps onto the same construction). SimBench MV grids model each LV subnetwork as one aggregated load + one aggregated DER at the secondary substation — exactly this abstraction. Four MV grids (rural, semi-urban, urban, commercial) at 10/20 kV, radial, **statistically validated against 74 separately-operated real German MV grids spread over five DSOs totalling about 11,000 km of line** (Meinecke et al., "SimBench—A Benchmark Dataset of Electric Power Systems," *Energies* 13(12):3290, 2020). [ResearchGate](https://www.researchgate.net/publication/342514995_SimBench-A_Benchmark_Dataset_of_Electric_Power_Systems_to_Compare_Innovative_Solutions_Based_on_Power_Flow_Analysis)
- SimBench uniquely ships **full-year 15-min load/generation/storage time series plus three future scenarios (0/1/2)** per grid [MDPI](https://www.mdpi.com/1996-1073/13/12/3290) — serving the per-planning-year overload definition and the 2030/33/35 horizon; native pandapower format.
- Size is laptop-feasible: rural MV `1-MV-rural--0-sw` ≈ 99 buses; urban MV `1-MV-urban--0-sw` ≈ 144 buses.
- **Voltage level & size:** use one MV feeder / MV-LV area with LV loads aggregated at ~10–100 secondary substations (transformer-as-decision-unit + enough aggregated households for diversity + tractability), not a single ~100-household LV feeder.
- **Secondary networks:** CIGRE MV (`pandapower.networks.create_cigre_network_mv(with_der=...)`; 15 buses, 2 transformers, 18 loads) as a recognised cross-check; **IEEE European LV feeder** (built into pandapower; 906 buses / 55 loads, 0.416 kV, one 0.8 MVA MV/LV transformer) [Readthedocs](https://pandapower.readthedocs.io/en/v2.10.0/networks/3phase_grids.html) only as an optional LV-level illustration for the voltage-constrained variant.
- **The project's Liander-derived grid: DROP for the single paper** (or a one-paragraph transferability outlook). No electrical parameters ⇒ no credible AC load flow or overload criterion without fabrication — a reviewer-attack surface. Dutch flavour is better carried by Dutch data on a parameterised benchmark.

**B. POWER FLOW vs POWER SUMMATION — two-tier.**
- **Tier 1 (MC inner loop): net-load power summation over the radial topology** for the transformer-overload criterion. On a radial feeder the transformer apparent power ≈ sum of downstream nodal net loads; losses/reactive effects are second-order for *thermal loading*. Standard in probabilistic hosting-capacity/planning MC studies; vectorised pandas sum ⇒ effectively free ⇒ large N.
- **Tier 2 (validation + voltage variant): full AC power flow in pandapower** on a subset and for any line-loading/voltage criterion in weak feeders, using the **`lightsim2grid` C++ Newton–Raphson backend** (`algorithm='nr'`, `lightsim2grid=True`). [GitHub](https://github.com/e2nIEE/pandapower/blob/develop/doc/powerflow/ac.rst)
- **Runtime & sample-size math:** native pandapower single AC solve on a ~100–300-bus radial net ≈ **28–37 ms** (Wang et al., arXiv 2408.03685, Table 4: 28.72 ms @ 69 nodes, 37.22 ms @ 123 nodes). [arxiv](https://arxiv.org/pdf/2408.03685) `lightsim2grid` (KLU/NR) single solve ≈ **0.17–0.6 ms** on comparable grids (case118 0.167 ms; case_illinois200 0.366 ms; case300 0.593 ms; v0.9.2 benchmark, 2015 laptop i7-6820HQ) [readthedocs](https://lightsim2grid.readthedocs.io/en/v0.9.2/benchmarks_grid_sizes.html) — docs report **"~20 times faster than pandapower"** [Readthedocs](https://lightsim2grid.readthedocs.io/en/latest/benchmarks.html) and a vectorised **TimeSerie module at ~12,277 pf/s (0.08 ms/pf)**. [GitHub](https://github.com/Grid2op/lightsim2grid/blob/master/README.md) [Readthedocs](https://lightsim2grid.readthedocs.io/en/latest/time_series.html) **Sample size:** binomial relative-error RE ≈ √((1−p)/(N·p)); for p=1e-2, ±10% needs N≈1e4; for p=1e-3, N≈1e5. Budget = N × T(critical timesteps) × K(α=5) × 2(endpoints), with T cut by critical-period focus (§C) and CRN reuse ⇒ low-millions AC solves for validation ⇒ hours on a laptop (minutes with lightsim2grid TimeSerie). **HPC only as fallback** if the voltage-constrained full-year variant is pursued.
- **Variance reduction / decision stability:** **common random numbers** across endpoints, α-levels and the five treatments.

**C. TIME STRUCTURE — critical-period focus.** Do *not* run full-year 15-min in the MC inner loop for headline results. Per G0-A1, define the primary overload metric over adaptive critical windows selected from the **import-direction loading** ranking: top-K weeks plus one margin week, with K chosen from a coverage-vs-K curve to capture at least 95% of the annual top-672 import-loading steps on the deterministic screen where feasible. The old fixed-winter-window assumption is retired. Run the full-year 15-min pass once per scenario as a Tier-2 check that the selected windows capture annual import-loading exceedances, and report export/feed-in exceedance as a separate side metric.

**D. DATA-GAPS CHECKLIST (actionable)**

| Need | Recommended open source | Note |
|---|---|---|
| EV charging behaviour | **ElaadNL Laadprofielengenerator** (dashboard https://charging.elaad.nl/; API docs https://api.charging.data.elaad.nl/docs#; project generation spec in `reports/elaad_profile_generation_spec.md`) | Build a frozen, seeded 15-minute EV profile library; bootstrap profiles per node/draw or use as calibration target |
| Heat-pump load + COP | **When2Heat** (Open Power System Data, DOI 10.25832/when2heat; Ruhnau, Hirth & Praktiknjo 2019, *Scientific Data* 6:189, doi:10.1038/s41597-019-0199-y) — 28 European countries incl. NL, hourly; NEDU/MFFBAS Dutch profiles for baseline | Downscale hourly→15-min; temperature-driven for cold spell |
| PV generation | **PVGIS** driven by **KNMI** (NL) or **DWD/ERA5** (SimBench-consistent) | Match weather source to grid provenance |
| Weather | **KNMI open data** (NL); **DWD/ERA5** (SimBench) | Also feeds HP COP and demand |
| Household baseline | **SimBench** 15-min series (native); NEDU (NL); Pecan Street (fallback) | SimBench preferred for consistency |
| Adoption scenarios (NL) | **Netbeheer Nederland II3050** (Editie 2 2023 / Editie 2025 scenarios); **PBL Klimaat- en Energieverkenning**; **ElaadNL outlooks** | Feed enrollment-share layer + horizon |
| Flexibility participation | **Müller & Jansen 2019** (0.88 delivery; 40–65% core; 29–90% range); **GOPACS** realisation; Dutch **capaciteitsbeperkingscontract (CBC)** stats; UK flexibility-tender realisation rates | Anchor ρ̃_flex + ρ\* achievability |
| P_crit / loading criterion | See §E; IEC 60076-7; N-1 sizing rules | No single published Dutch % — flag explicitly |
| Transformer thermal standard | **IEC 60076-7** loading guide | Justifies probabilistic overload criterion |
| Pilot cost & capex (VoI) | **Stedin-confirmed unit costs** (Cicėnas 2025, TU Delft MSc thesis with Stedin/Eneco, DEMOSES): MV transformers ≈ **€25,000–35,000/MVA**; MV cables ≈ **€95,000–170,000/km** (10 kV CS 150 mm²: €95k/km); discrete transformer installations **€0.75–2.0 M each**. Still needed: flexibility pilot/tender cost per MWh | Capex side resolved; pilot cost vs deferred capex remains |

**E. P_crit AND THE THERMAL CRITERION (resolved).**
- **Thermal justification:** **IEC 60076-7** permits, for distribution transformers, **normal cyclic loading to 1.5 p.u.** (top-oil ≤105 °C, hot-spot ≤120 °C) and **long-time emergency loading to 1.8 p.u.** (top-oil ≤115 °C, hot-spot ≤140 °C), [StudyLib](https://studylib.net/doc/25626887/iec-60076-7-2005-power-transformer--part-7--loading-guide...) with the ageing rule that **insulation life roughly halves per ~10 °C hot-spot rise** [Electrical Engineering Portal](https://electrical-engineering-portal.com/guide-to-transformer-specification-compliance-iec-60076-part-1) (IEC 60076-7 loading guide; the standard's more precise rule is a doubling of relative ageing per ~6 °C above a 98 °C hot-spot [Eng-Tips](https://www.eng-tips.com/threads/iec-60076-7-2005-loss-of-life-of-transformers.408598/) for non-thermally-upgraded paper). This is the physical basis for treating *occasional, bounded* overloads as acceptable — i.e. a probabilistic P(overload) ≤ P_crit rather than a hard cap.
- **Planning thresholds:** MV/HV substations are commonly sized to **N-1** so peak load stays **below ~60% of installed transformer capacity** (surviving unit ≤120% of rating on outage). [uspto](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11031773) A concrete DSO operational analogue (Radius, DK; arXiv 2402.15728) uses a **66% loading limit for N-1 security**, defines congestion as >100% loading, and tolerates occasional exceedance with **<1% likelihood** [arxiv](https://arxiv.org/pdf/2402.15728) — an explicit P_crit ≈ 0.01. In Germany n-1 is applied strictly at HV/transmission; [Netzentwicklungsplan](https://www.netzentwicklungsplan.de/en/background/energy-networks) **MV/LV distribution is often planned without full N-1 redundancy**, which is exactly why flexibility-based deferral is interesting there.
- **Netherlands specifics:** strict n-1 ("enkelvoudige storingsreserve") is codified for HV (≥110 kV) in the Netcode; [Officiële Bekendmakingen](https://zoek.officielebekendmakingen.nl/stb-2020-511.html) ACM has granted derogations because holding to n-1 unconditionally [Autoriteit Consument & Markt](https://www.acm.nl/nl/publicaties/besluit-ontheffingen-enkelvoudige-storingsreserve-tennet) was **estimated at about €7 billion of grid investment** ("Kwaliteitsnorm enkelvoudige storingsreserve in het Nederlandse hoogspanningsnet," 2013; [Internetconsultatie](https://www.internetconsultatie.nl/enkelvoudige_storingsreserve/document/5302) cited in Staatsblad 2020, 511). [Officiële Bekendmakingen](https://zoek.officielebekendmakingen.nl/stb-2020-511.html) Dutch DSO MV/LV design uses statistical peak-load models (Velander/Rusck) with per-DSO internal guidelines rather than one published national loading %. **We therefore set P_crit ≈ 1e-2 (with a 1e-3 sensitivity), justified by the <1% exceedance practice and IEC 60076-7 thermal tolerance, and state explicitly that no single official Dutch % exists** — turning a data gap into a transparent modelling choice.

### 9. Tooling & reproducibility (pinned)
**Python 3.12**, **pandapower >=3.4 and <4** (`pandapower.networks` for CIGRE/IEEE-LV), **simbench 1.6.2** (`sb.get_simbench_net`), **lightsim2grid ≥0.9.2** (C++ NR backend), **numba** JIT on, **numpy/pandas/scipy**. The p-box/possibility layer is implemented in-house (thin α-cut propagation, a few hundred lines) with an optional cross-check against an established probability-bounds library. **Code + data availability statement** ready for Applied Energy: public repo, pinned `.venv` setup via `requirements.txt` / `requirements-dev.txt`, SimBench/ElaadNL/When2Heat retrieval scripts (data redistributed only where licences permit; otherwise download scripts + DOIs).

### 10. Threats to validity / reviewer-attack preemption
1. **"Just info-gap/IGDT rebranded."** **Ferson & Tucker (2008), "Probability boxes as info-gap models"** (NAFIPS): nested p-boxes *are* info-gap models for probability distributions, with probability-bounds analysis as the calculus. Position α-cuts as the info-gap horizon made probabilistic; cite **Cao et al. (2018) chance-constrained IGDT** for multi-period expansion planning as the structural precedent mixing random + non-random uncertainty. [arXiv](https://arxiv.org/pdf/1708.07337)
2. **"P-box power flow is not new."** Acknowledge and cite the p-box power-flow papers (e.g. "A probability box representation method for power flow analysis considering both interval and probabilistic uncertainties," *IJEPES/EPSR*; and Aien et al.). Our contribution is the **decision layer** (α\*, ρ\*, horizon, VoI, decision-reversal) they do not address.
3. **"Belief/plausibility already covers this (Aien 2014)."** Cite **Aien et al. (2014)** Bel/Pl power-flow review; we report belief/plausibility on the *decision event* "P(overload) ≤ P_crit," linked to the trapezoid membership via the DS-structure ↔ p-box equivalence.
4. **"Defuzzify to one number."** Refuse explicitly, citing **Baudrit, Dubois & Guyonnet (2006)** and **Baudrit, Couso & Dubois (2007)**: [Springer](https://link.springer.com/rwe/10.1007/978-1-0716-2628-3_413) defuzzifying post-processing destroys the aleatory/epistemic separation. **α-indexed bounds only** (hard rule, §3).
5. **"Convergence/computational rigour"** (Yao 2026 urgency): CRN for stability, binomial CI on the rare-event estimate, monotonicity/vertex shortcut to bound cost, explicit N-vs-CI math (§B); report MC CIs on both p-box edges.

Additional threats: (a) **monotonicity may fail** (rebound, reverse-PV) — numerical verification + interior-sampling fallback; (b) **German-grid / Dutch-data mismatch** — Dutch behaviour/scenarios + CIGRE cross-check; (c) **elicitation subjectivity** — DFMP transformation where data exist + trapezoid-shape sensitivity.

---

## Recommendations

**Stage 1 — Weeks 1–4 (foundation and the gating experiment).**
1. Pin the environment; load the SimBench semi-urban/urban MV grid + time series; reproduce a deterministic annual power flow; extract adaptive import-direction critical windows and export/feed-in side metrics. *Go/no-go: SimBench + lightsim2grid run on the laptop.*
2. Build the aleatory layer (EV ← frozen ElaadNL profile-generator library, HP ← When2Heat, PV ← PVGIS/weather, baseline ← SimBench) and the nodal flexibility aggregator applying ρ.
3. Implement net-load summation + Tier-2 AC validation harness + CRN. *Go/no-go: summation vs AC agree on transformer loading within tolerance.*
4. **Run the monotonicity verification (dense ρ sweep).** *This is the decisive gate:* if overload probability is monotone in ρ in the demand-peak regime, adopt the vertex shortcut; if not (rebound/reverse-PV), switch that cut to interior sampling. This checkpoint sizes the entire compute plan.

**Stage 2 — Weeks 5–9 (the paper's contribution, critical path).**
5. α-cut p-box propagation + model-error interval → two-sourced p-box with MC CIs.
6. Compute the decision layer: **α\*, ρ\*, μ(ρ\*), deferral horizon (2030/33/35), VoI.**
7. Implement the **five-treatment decision-reversal benchmark** on one case → the money figure.
8. Run the **elicitation protocol**: decompose ρ̃_flex, DFMP transform where pilot data exist, trapezoid-shape sensitivity.
9. VoI economics: transformer capex (Stedin-confirmed: €25,000–35,000/MVA; €0.75–2.0 M per discrete transformer installation — Cicėnas 2025) vs pilot cost; finalise the decision table.

**Stage 3 — Weeks 10–12 (hardening and submission).**
10. Robustness: P_crit 1e-2 vs 1e-3; scenario years; trapezoid shapes; CIGRE cross-check.
11. Write-up, figures, code/data availability statement, reviewer-attack section.
12. Internal review → submit under the working title above to **Applied Energy** (primary; expects code/data availability, highlights ≤85 characters, graphical abstract). Backups: **IJEPES** and **SEGAN**.

**Benchmarks/thresholds that would change these recommendations:**
- *If monotonicity fails broadly* (Week 4) → drop the vertex shortcut, cut N or grid size, and consider narrowing to the transformer-only (summation) criterion to preserve laptop feasibility.
- *If the decision-reversal treatments all agree* on the chosen case → re-select a case nearer the P_crit boundary (higher adoption year or weaker feeder) so the treatments genuinely diverge; a benchmark where methods agree has no money figure.
- *If ρ\* falls inside the Müller & Jansen well-supported core (≤0.65)* → lead with "defer-with-monitoring is credible"; *if ρ\* > ~0.9* → lead with "reinforce," since it exceeds the observed delivery envelope.
- *If AC validation diverges from summation by more than a few percent on transformer loading* → the two-tier claim weakens; report AC results as primary and treat summation only as a screening pre-filter.

---

## Caveats

- **No single official Dutch loading/overload-probability % exists** in open sources; Dutch DSO MV/LV design is statistical/internal. The chosen P_crit ≈ 1e-2 (1e-3 sensitivity) is a defensible synthesis of IEC 60076-7 thermal tolerance and documented <1% DSO exceedance practice (Radius, DK), *not* a Dutch statute. State this explicitly in the paper.
- The **60% N-1 sizing rule** and **66% operational limit** come from a patent-background description and a single Danish DSO respectively — illustrative practice, not pan-Dutch regulation. Use them as anchors, not as the criterion itself.
- **Runtime figures** (28–37 ms native pandapower; ~0.17–0.6 ms and "~20×" lightsim2grid; ~12,277 pf/s TimeSerie) are from specific benchmarks (arXiv 2408.03685; lightsim2grid v0.9.2 docs on a 2015 laptop). Real timings depend on grid size, numba warm-up, and conversion overhead (which dominates for small grids); run your own micro-benchmark in Week 1 before committing to N.
- **SimBench is a German dataset.** Its representativeness for Dutch MV/LV is asserted via injected Dutch data, not topology; a reviewer may still object. The CIGRE cross-check and an explicit transferability paragraph are the mitigations.
- **Müller & Jansen (2019) delivery statistics have been verified against the primary full text in this project** (Applied Energy 239:836–845): 40–65% aggregate load reduction in 57 of 67 real experiments (29–90% full observed range), 0.88 empirical response success rate, median prediction error 6.7%. Note they quantify delivery *given enrollment*; the future enrollment share remains the deeply uncertain factor (§6).
- **The Stedin-confirmed unit costs (Cicėnas, 2025)** are labelled “rough cost, confirmed by Stedin” in an MSc-thesis appendix — solid order-of-magnitude anchors for the VoI analysis, but cite them as DSO-confirmed indicative figures, not audited unit prices, and verify against a primary Stedin/Netbeheer Nederland source at proof stage. The thesis's whole-scenario totals (€44M–113M by 2050) are system-wide South-Holland figures and must not be quoted as single-feeder deferral values.
- **Monotonicity is a plausibility claim, not a theorem** — the rebound and reverse-PV regimes are known failure modes and must be tested, not assumed.
- The **IEC 60076-7 ageing rule** is often quoted loosely ("halves per 10 °C"); the standard's precise formulation (relative ageing rate, ~6 °C doubling above a 98 °C reference for non-upgraded paper) should be cited exactly if used quantitatively.
