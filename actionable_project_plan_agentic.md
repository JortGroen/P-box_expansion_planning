# Actionable Project Plan — Agentic Execution Edition
## "When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility" (single paper, ~12 weeks)

This document converts Project Plan v2 into an executable work breakdown (Epics → Stories → Tasks) designed for **1–3 AI agents working in parallel** under **human (PI) control of every critical decision**. It is the operating manual: agents read it, you enforce it.

---

## 1. How to use this document

Hierarchy and IDs: **Epic (E#) → Story (E#.S#) → Task (E#.S#.T#)**. Every story has a **Deliverable** (a concrete artifact: module, dataset, report, figure), **Acceptance criteria** (checkable), **Verification** (how trust is established), an **Owner** (Agent A/B/C or HUMAN), and **Dependencies**. Statuses live in `STATUS.md` (one line per story: `todo / in-progress / blocked / review / done`), updated by agents at the end of every working session.

Rule of thumb for granularity: a Task is one agent session (≤ half a day); a Story is 1–4 days; an Epic is 1–3 weeks.

---

## 2. Operating model: humans decide, agents build

**You (PI)** are Accountable for everything and the only party who can: pass a Gate (§4), merge to `main`, sign a register entry (§3), approve a number for the paper, change an interface contract (§5), or approve a new dependency.

**Agent roles** (independent work streams, coupled only through frozen interface contracts):

| Agent | Role | Owns epics | Skills profile |
|---|---|---|---|
| **A — Simulation Engineer** | Grid, physics, performance | E1, E3 (+E4 support) | pandapower, lightsim2grid, profiling, radial-network math |
| **B — Uncertainty & Decision Scientist** | Fuzzy/p-box math, decision layer, monotonicity | E4, E5, E6, E7 (math) | possibility theory, MC statistics, root-finding, invariant testing |
| **C — Data & Experiments Engineer** | Data pipelines, experiment orchestration, paper support | E0, E2, E8, E9, E10 (support) | data wrangling, licensing, plotting, reproducibility tooling |

**Worktree model:** agents do not share a checkout. Keep `P-box_expansion_planning/` on `main` as the PI dashboard, and run implementation in separate sibling Git worktrees:

| Workspace | Branch pattern | Use |
|---|---|---|
| `P-box_expansion_planning/` | `main` | PI review, registers, gate decisions |
| `P-box_expansion_planning-agent-a/` | `agent-a/...` | Agent A implementation |
| `P-box_expansion_planning-agent-b/` | `agent-b/...` | Agent B implementation |
| `P-box_expansion_planning-agent-c/` | `agent-c/...` | Agent C implementation |

If an agent finds itself in the wrong worktree or on the wrong branch prefix, it must stop and ask the PI. It must not fix the situation by switching a shared directory to a different branch.

**Environment model:** each worktree has its own local `.venv`, created with `scripts/setup_venv.ps1` from `requirements-dev.txt`. Agents must not install or run project dependencies from Anaconda `base`; dependency additions or version changes remain PI-approved changes.

**Staffing configurations:**
- **3 agents:** as above; maximum parallelism (timeline in §7).
- **2 agents:** Agent A absorbs E2 (sim + data), Agent B absorbs E8–E9 (uncertainty + experiments); E0/E10 shared. Add ~1–2 weeks.
- **1 agent:** strict sequence E0 → E1 → E2 → E3 → **E4 (gate)** → E5 → E7 → E6 → E8 → E9 → E10. Add ~3–4 weeks.

**Cadence:** each agent ends every session by appending to `reports/AGENT_<X>_LOG.md` (what was done, what was verified, open questions, next step). You do a **weekly review** (30–60 min): read logs, pass/hold gates, sign registers, re-prioritize. Nothing proceeds past a Gate without your explicit entry in `DECISIONS.md`.

---

## 3. Trust framework (non-negotiable rules for all agents)

**T1 — Config-driven, seeded, manifested.** Every experiment runs from a version-controlled YAML config; every run writes `manifest.json` (git commit, config hash, RNG seeds, package versions, wall time, output checksums). A result without a manifest does not exist.

**T2 — Tests before trust.** Every module ships with unit tests; the mathematical core additionally ships with **property/invariant tests**: (i) P_lower ≤ P̂ ≤ P_upper at every α; (ii) bounds **nested** across α (α₁<α₂ ⇒ [P_lo^{α₂},P_up^{α₂}] ⊆ [P_lo^{α₁},P_up^{α₁}]); (iii) CRN reproducibility (same seed ⇒ bit-identical estimates); (iv) energy conservation in the rebound model; (v) decision-table totality (every p-box maps to exactly one decision).

**T3 — Independent cross-checks for critical math.** The p-box/decision core must reproduce (a) an **analytic toy case** (closed-form P(E|ρ), e.g., Gaussian aggregate load vs capacity, where the p-box is computable by hand) to <1% error, and (b) the qualitative behavior of a published hybrid-propagation example (Baudrit et al. 2006). No paper result is produced by code that has not passed this.

**T4 — Two-key rule for every number in the paper.** Any numeric value destined for the manuscript must trace to either a `DATA_REGISTER.md` entry (external data/citations, with source, license, verification tag mirroring the literature review's [V]/[HC] system) or a run manifest (computed results) — **and** carry your sign-off initials in the register. Agents propose; you sign.

**T5 — No silent assumptions.** Any assumption not already in `ASSUMPTIONS.md` triggers a **stop-and-ask**. Forbidden without escalation: inventing data values, changing an interface contract, adding a dependency, altering the overload-event definition, changing P_crit, touching another agent's module.

**T6 — Git/worktree/environment discipline.** Agents work on branches (`agent-a/...`) inside role-specific worktrees and run commands through the worktree-local `.venv`. They open PRs with a filled self-review checklist (tests pass, invariants pass, manifest attached, registers updated); **only you merge to `main`.** The main repository directory is a PI dashboard and must not be used for parallel agent implementation.

**T7 — Anti-fabrication.** Citations may only be drawn from the consolidated literature review's verified list (tags [V]/[V–]/[HC]) or new entries you have signed into `DATA_REGISTER.md`. An agent that cannot source a claim writes `[CITATION NEEDED — escalated]` and moves on.

**T8 — Manuscript rationale travels with every choice.** Every new or changed decision, assumption, data source, or methodological protocol must add or update a same-ID standalone paragraph in `paper/methods_decisions_and_assumptions.md` in the same PR. The paragraph explains the choice, defense, scope, and limitations and carries the register status explicitly. Proposed prose never creates authority; only the signed register does. Automated coverage tests reject registered IDs without a paragraph block.

**Escalation triggers (agent must stop and ask you):** interface change needed; a test cannot pass without changing the spec; unclear data license; runtime exceeds budget by >2×; results contradict a passed Gate; anything requiring a value not in the registers.

**Control registers** (created in E0, live in `registers/`): `DECISIONS.md` (gate outcomes, signed), `ASSUMPTIONS.md` (id, statement, rationale, owner, status), `DATA_REGISTER.md` (item, source, DOI/URL, license, retrieval script, checksum, verification tag, PI sign-off), `RISKS.md` (§8), `STATUS.md`. Their manuscript-facing companion is `paper/methods_decisions_and_assumptions.md` per T8.

---

## 4. Human decision gates (only YOU can pass these)

| Gate | When | Question you decide | Inputs required from agents | Outcomes |
|---|---|---|---|---|
| **G0 Scope freeze** | end W1 | Approved in `registers/DECISIONS.md`: decision-transformer event E, P_crit primary/sensitivity protocol, grid/fallback rule, KNMI weather ensemble, and primary alpha grid; amended by G0-A1 for import-direction semantics and by G0-A2 for full-year primary event scope | E0 registers initialized; grid inventory report (E1.S1); G0 assumption rows A-005--A-008; E1.S3 reverse-PV screen evidence; E1.S3b import-window diagnostic | frozen; changes require a new signed decision |
| **G1 Foundation validated** | end W2 | Approved in `registers/DECISIONS.md`: Tier-1 full-year radial summation is the MC inner-loop evaluator; AC is deterministic/validation only; fixed winter windows rejected; WindowSets retained only for AC validation/diagnostics; no manuscript claim may say "AC infeasible". G1-A1 requires output-domain model-error propagation; G1-A2 freezes symmetric-relative grid-error form, unknown dependence, exact mixed composition, and a future-layer domain/capacity-screen protocol while leaving numerical A-013 values proposed. | Laptop micro-benchmark (E1.S2); profile/window validation (E1.S3, E1.S3b); G1 brief; G1-A1/G1-A2 amendments | proceed with E1.S4; complete C1 TimeSeriesCPP benchmark; integrate E2/E3 layers; run E3.S2b before the denominator/A-013 sign-offs and G2 result inspection |
| **G2 Tier-1 enclosure and adequacy** | W3–4 | Does a predeclared Tier-1 error envelope enclose held-out near/above-threshold pandapower states over the E3.S2b-frozen domain, and does the mixed relative/additive output interval preserve a useful decision? | Corrected AC budget (E1.S2b); headroom brief (E1.S1b); future-layer domain/capacity screen (E3.S2b); manifested domain-covering tier comparison and held-out enclosure test (E3.S3) | Tier-1 primary / corrected Tier-1 / selective AC / Tier-1 rejected; actual outage AC validation required if firm capacity is selected |
| **G3 Monotonicity verdict** | W4 | Is P(E\|ρ) monotone in the demand-peak regime? | Monotonicity report + regime split (E4.S1) | vertex shortcut / interior-sampling fallback / restrict scope to demand-driven regime |
| **G4 Elicitation sign-off** | W7 | The trapezoid corners of ρ̃_flex (the paper's hinge) | Elicitation worksheet + candidate trapezoids (E7.S2) | sign corners into DECISIONS.md |
| **G5 Case selection** | W7–8 | Which case for the decision-reversal benchmark (must sit near the P_crit boundary so treatments genuinely diverge) | Case-sweep candidates (E8.S1) | pick case / demand harder case |
| **G6 Results freeze** | W11 | All paper numbers locked to manifests | Robustness report (E9); figure pipeline dry-run (E10.S1) | freeze / iterate |
| **G7 Submission** | W12 | Submit to Applied Energy | Full manuscript, repro package, red-team report | submit / revise |

---

## 5. Interface contracts (frozen at G1; changes only via you)

These contracts are what let agents work independently. Each has a schema doc + contract tests in `src/contracts/`.

**IC-1 NetLoadProvider** (A provides → B, C consume)
`get_net_load(scenario: str, year: int, time_domain: FullYear | WindowSet, rho: float, seed: int) -> ndarray[nodes, timesteps]` (kW, 15-min). `FullYear` is the primary Tier-1 Monte Carlo domain per G0-A2. `WindowSet` is allowed only for AC-validation subset selection and diagnostics. Deterministic in `seed` (CRN guarantee). Includes flexibility activation at controllability ρ and configurable rebound.

**IC-2 OverloadEvaluator** (A provides → B consumes)
`evaluate(net_load, time_domain: FullYear | WindowSet = FullYear) -> {import_loading_series: ndarray, export_loading_series: ndarray, screening_loading_series: ndarray, overload: bool}` per the G0/G0-A1/G0-A2 event definition. `overload` is the full-year primary event by default: at least 4 consecutive 15-minute import-direction steps above 1.0 p.u., with a direction flip resetting the counter. Tier-1 = radial summation; same semantic signature for the Tier-2 AC implementation (drop-in swap). WindowSet evaluation is diagnostic/validation only.

G1-A1/G1-A2 behavioral amendment: IC-2 must preserve the unwidened `P_net` direction gate and enough trajectory/mask information for an output-error interval to be applied before episode classification. A boolean-only sample callback is noncompliant. Given additive G2 endpoints `e_minus/e_plus` and relative `epsilon_grid`, the endpoint loadings are `(1-epsilon_grid)*max(0, L_T1-e_minus)` and `(1+epsilon_grid)*(L_T1+e_plus)`. The exact schema change remains PI-gated.

**IC-3 PBoxEstimator** (B provides → C consumes)
`estimate(provider, evaluator, alpha_grid, fuzzy_number, N, seed) -> {alpha: (P_lo, P_up, CI_lo, CI_up)}` with the G1-A1/G1-A2 output-error endpoints applied to loading trajectories before event detection. Event counts from the lower/upper loading endpoints produce the probability estimates and MC CIs. Post-hoc probability-margin widening and independent error sampling are forbidden. Exact schema changes remain PI-gated.

**IC-4 DecisionMetrics** (B provides → C consumes)
`decide(pbox_family, P_crit, fuzzy_number, econ: EconParams) -> {alpha_star, rho_star, mu_rho_star, horizon: {year: alpha_min}, VoI, decision: str}`.

**IC-5 ExperimentRunner + manifest schema** (C provides → all)
`run(config.yaml) -> results/ + manifest.json`; treatments (i)–(v) of the decision-reversal benchmark are runner plugins sharing IC-1/IC-2 and CRN seeds.

**IC-6 FigureFactory** (C provides)
Every paper figure/table is generated by `make figures` from manifests only — no hand-entered numbers anywhere in `paper/`.

---

## 6. Work breakdown: Epics → Stories → Tasks

### E0 — Governance & scaffolding (Owner: C; Week 1; blocks everything)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E0.S1 Repo & environment** | T1 repo skeleton (`src/ tests/ configs/ data/ experiments/ registers/ reports/ paper/`); T2 pinned `.venv` setup (`requirements.txt`, `requirements-dev.txt`, Python 3.12, pandapower ≥3.4 and <4, simbench 1.6.2, lightsim2grid ≥0.9.2, numba, numpy/pandas/scipy, pytest, hypothesis, matplotlib); T3 `Makefile` / task wrapper (`make test / run / figures`, `scripts/task.ps1`); T4 CI (pytest+lint) | Repo with green CI | Fresh-clone install + `make test` or `.\scripts\task.ps1 test` passes on your laptop |
| **E0.S2 Control registers** | T1 create the five registers with schemas; T2 seed initial entries (pending G0 items; verified literature tags imported from the consolidated review) | `registers/*` | You can sign an entry; schema fields complete |
| **E0.S3 Run-manifest utility** | T1 manifest writer (git hash, config hash, seeds, versions, checksums); T2 test | `src/manifest.py` + test | Two identical runs ⇒ identical checksums |
| **E0.S4 Agent working agreement** | T1 `AGENTS.md`: definition of done, escalation triggers (§3), forbidden actions, PR checklist | `AGENTS.md` | You approve wording |

### E1 — Simulation foundation (Owner: A; Weeks 1–2)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E1.S1 Grid loading** | T1 load SimBench `1-MV-semiurb--0-sw` + `1-MV-urban--0-sw` + CIGRE MV; T2 inventory (buses, trafos, lines, ratings); T3 deterministic `runpp` baseline | `src/grid_loader.py` + `reports/grid_inventory.md` | Baselines converge; inventory feeds G0 |
| **E1.S2 Laptop micro-benchmark** | T1 time native pandapower vs lightsim2grid single-solve + TimeSerie on the chosen grids; T2 derive feasible N budget table (N × T × K × 2) | `reports/BENCHMARK.md` | Measured ms/solve on *your* laptop; budget table → G1 |
| **E1.S2b TimeSeriesCPP AC benchmark** | G1-C1: T1 build/diagnose the lower-level `lightsim2grid.timeSerie.TimeSeriesCPP` adapter or document why it cannot be used; T2 confirm whether the `runpp` lightsim2grid flag actually engages; T3 report corrected AC validation budget | `reports/BENCHMARK_TIMESERIESCPP.md` | Clear verdict on solver engagement and feasible AC validation solve count before G2; no "AC infeasible" manuscript wording |
| **E1.S1b Transformer headroom diagnostic** | G1-C2: T1 report decision-substation transformer count and ratings; T2 compute peak import MVA versus total aggregate nameplate and firm `(n-1)` nameplate; T3 compute 2035 no-flex load multiplier needed to reach 0.95 p.u. under both denominator conventions; T4 flag G0 item-4 fallback/escalation and any firm-capacity redefinition option | `reports/transformer_headroom_diagnostic.md` | One-page memo gives PI enough information to decide whether the primary case is suitable or needs the G0 fallback/escalation path |
| **E1.S3 Time series & critical weeks** | T1 ingest SimBench full-year 15-min profiles, scenarios 0/1/2; T2 fixed-winter direction-agnostic screen from the original plan; T3 validation plot windows-vs-full-year exceedances | `src/profiles.py`, `data/critical_weeks.csv`, plots | PR #10 evidence generated; fixed-winter windows did not validate and triggered G0-A1 |
| **E1.S3b G0-A1 import-window diagnostic** | T1 add import/export split per G0-A1; T2 re-rank annual weeks by import-direction loading; T3 coverage-vs-K curve for annual top-672 import-loading steps; T4 propose adaptive top-K + 1 margin WindowSets and report export exceedance separately | `src/profiles.py`, updated data/report/manifest | WindowSet diagnostics generated for AC validation/reporting; G0-A2 means they do not define primary `P(E)` |
| **E1.S4 Tier-1 evaluator** | T1 radial downstream summation of net P and Q → `S_net(t) = P_net(t) + jQ_net(t)` and `abs(S_net) / S_nom,agg`; T2 produce full-year import-direction primary loading (`P_net > 0`), export-direction side loading (`P_net < 0`), and direction-agnostic screening loading (`P_net = 0` belongs to neither direction); T3 overload-event flag per G0-A1/G0-A2 over the full planning year, with direction flips resetting the episode counter; T4 support WindowSet evaluation for validation/diagnostics only; T5 unit tests vs hand-computed toy feeder incl. import, reverse-export, and zero-crossing cases; T6 preserve unwidened direction information for G1-A1 output-envelope propagation, with exact IC-2 schema deferred to PI approval | `src/evaluator_sum.py` + tests | Matches hand calculation exactly on toy case; full-year import event semantics tested; reverse-flow case reports export loading but does not trigger primary import event; output path can apply an interval before episode detection without widening export/zero-crossing steps into import |

### E2 — Data & aleatory layer (Owner: C; Weeks 1–3)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E2.S1 Data acquisition** | T1 retrieval scripts: ElaadNL Laadprofielengenerator profile route per `reports/elaad_profile_generation_spec.md`, When2Heat (DOI 10.25832/when2heat), PVGIS/KNMI weather, SimBench profiles; T1b unit-cost extraction from the Cicėnas (2025) thesis appendix (Stedin-confirmed €/MVA and €/km tables); T2 license/API check; T3 checksums + `DATA_REGISTER` entries | `data/get_*.py` + signed register rows | Every dataset/profile library: source, license/terms note, checksum, your sign-off |
| **E2.S2 EV model** | T1 run one-profile ElaadNL generator probe, then create/freeze profile library if EV-001 open items pass; T2 bootstrap sampler over archived profiles or calibrate fallback sampler; T3 validation/QQ and shape reports | `src/ev_model.py` + fit/profile-library report | Probe passes; profile library seeded/checksummed; sampler seeded |
| **E2.S3 HP model** | T1 When2Heat temperature-driven profiles; T2 hourly→15-min downscaling; T3 cold-week sanity check | `src/hp_model.py` + report | Peak coincides with cold spell; COP handling documented |
| **E2.S4 PV model** | T1 PVGIS/KNMI-driven generation; T2 alignment with weather source per G0 | `src/pv_model.py` | Seasonal totals plausible vs PVGIS reference |
| **E2.S5 Baseline & diversity** | T1 SimBench baseline series + household-diversity resampling | `src/baseline_model.py` | Diversity factor in literature range |
| **E2.S6 Adoption scenarios** | T1 II3050 / ElaadNL outlook → nodal adoption shares for 2030/2033/2035; T2 `ASSUMPTIONS` entries per number | `configs/scenarios.yaml` + provenance | Every share traces to a signed register row |

### E3 — Flexibility aggregator & two-tier physics (Owner: A; Weeks 3–4)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E3.S1 Flexibility aggregator** | T1 flexible-fraction per node per tech; T2 apply controllability ρ during critical periods; T3 configurable rebound (none / shift-to-adjacent) | `src/flex_aggregator.py` + tests | Energy conservation test passes with rebound on |
| **E3.S2 IC-1 NetLoadProvider** | T1 implement contract; T2 schema doc; T3 contract tests incl. CRN determinism | `src/contracts/net_load.py` | Same seed ⇒ bit-identical output; schema frozen at G1 |
| **E3.S2b Future-layer capacity and domain screen** | T1 predeclare one runner design after EV/HP/PV/adoption/flexibility integration; T2 run 2030/2033/2035 and declared adoption cases at no-flex and maximum-flex endpoints; T3 report raw import/export MVA, qualifying episodes, and both 80 MVA total and 40 MVA firm ratios; T4 classify each convention as no relevant congestion, decision-sensitive, or not flexibility-resolvable and freeze the resulting input/output domain before p-box inspection; T5 flag that a firm primary choice requires actual one-transformer-out AC validation | `reports/future_layer_capacity_screen.md` + manifest | One versioned experiment informs, but does not silently tune, the denominator and A-013/G2 domains; out-of-domain later samples have an explicit escalation path |
| **E3.S3 Tier-2 AC harness and Tier-1 enclosure** | T1 pandapower+lightsim2grid time-series runner (IC-2 drop-in); T2 predeclare a domain-covering validation design and held-out near/above-threshold stratum; T3 compare Tier-1 vs pandapower residuals on matched inputs through the runner; T4 test the predeclared held-out enclosure criterion without retuning; T5 quantify decision impact and recommend Tier-1 / corrected Tier-1 / selective AC / reject | `reports/tier_comparison.md` + manifest | `epsilon_Tier1` symmetric/asymmetric envelope reported; held-out enclosure verdict is auditable; G2 receives one explicit evaluator recommendation |
| **E3.S4 CRN harness** | T1 seed-tree design (sample × α × endpoint × treatment); T2 test identical aleatory streams across branches | `src/rng.py` + test | Proven identical streams |

### E4 — Monotonicity gate (Owner: B, support A; Week 4) — **CRITICAL PATH**
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E4.S1 Dense ρ sweep** | T1 P(E\|ρ) for ρ∈{0,0.05,…,1} on fixed CRN ensemble; T2 bootstrap CIs; T3 regime split (demand-peak vs PV weeks; rebound on/off) | `reports/monotonicity.md` + figures | Curves + CIs per regime → **G3 verdict is yours** |
| **E4.S2 Fallback stub** | T1 interior-sampling per α-cut implementation (activated only if G3 requires) | `src/pbox_interior.py` | Passes same invariant tests as vertex path |

### E5 — P-box propagation & risk post-processor (Owner: B; Weeks 5–6)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E5.S1 Fuzzy number class** | T1 trapezoid/triangle/piecewise-convex + α-cut extraction; T2 tests vs hand values | `src/fuzzy.py` + tests | Exact match on hand-computed cuts |
| **E5.S2 Vertex propagation (IC-3)** | T1 endpoint propagation per α with binomial CIs; T2 nested-cut sample reuse via CRN; T3 invariant suite (§3 T2 i–iii) | `src/pbox.py` + invariants | All invariants green at N from G1 budget |
| **E5.S3 Output-domain model-error propagation** | T1 Agents A/B propose the smallest G1-A2-compliant IC-2/IC-3 schema change for PI approval; T2 compose the relative symmetric grid envelope with G2 additive endpoints exactly as `L_lo=(1-e_grid)*max(0,L_T1-e_t1_minus)` and `L_up=(1+e_grid)*(L_T1+e_t1_plus)`; T3 apply the unwidened direction gate, then run the four-step detector; T4 test alpha support, arbitrary-dependence endpoints, CRN, counts/CIs, clipping, and asymmetric Tier-1 cases | config + `src/pbox.py` + contract/invariant tests | Synthetic trajectories produce hand-computed event-probability bounds; no probability-margin shifting or independent error sampling remains; signed A-013 and G2 envelope required before paper use |
| **E5.S4 Independent cross-check** | T1 analytic toy case (closed-form P(E\|ρ)) match <1%; T2 qualitative reproduction of Baudrit-style hybrid example | `reports/crosscheck.md` | **Trust certificate for the math core** (required before any paper result) |

### E6 — Decision layer (Owner: B; Weeks 6–7) — **HEADLINE**
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E6.S1 α\*** | T1 α\* = inf{α: P_up^α ≤ P_crit} + edge cases (never/always) | in `src/decision.py` | Unit tests on constructed p-boxes |
| **E6.S2 ρ\* & μ(ρ\*)** | T1 root-find P(E\|ρ\*)=P_crit (uses monotonicity); T2 membership readout; T3 procurement-target framing vs Müller delivery envelope (0.88; 0.40–0.65 core; 0.29–0.90 range) | idem | ρ\* reproducible ±CI under CRN; envelope comparison automated |
| **E6.S3 Deferral horizon** | T1 per-year p-boxes (2030/33/35) → latest safe year as f(α) | horizon table/figure | Monotone-in-year sanity check |
| **E6.S4 VoI** | T1 width at decision α; T2 deferral value (Stedin-confirmed capex — Cicėnas 2025: €25–35k/MVA transformer, €95–170k/km MV cable, €0.75–2.0M per discrete transformer installation; discount rate — `ASSUMPTIONS`, your sign) vs pilot cost | VoI module | Every € value signed in register |
| **E6.S5 Decision engine** | T1 map bounds → {defer / defer+monitor / reinforce / collect-data}; T2 totality + branch tests | decision table impl. | Every branch exercised by a test p-box |

### E7 — Elicitation protocol (Owner: B math, C data, **HUMAN corners**; Weeks 5–7, parallel)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E7.S1 DFMP transform** | T1 implement Dubois–Foulloy–Mauris–Prade probability→possibility; T2 test vs paper example | `src/dfmp.py` + test | Matches published example |
| **E7.S2 Factor worksheet** | T1 decomposition: enrollment (scenarios/policy) × delivery 0.88 × deliverable fraction (core 0.40–0.65, support 0.29–0.90); T2 per-α interval product; T3 candidate trapezoids | `notebooks/elicitation.ipynb` | Every factor sourced to signed register rows |
| **E7.S3 GATE G4** | you sign the corners | `DECISIONS.md` entry | — |
| **E7.S4 Shape sensitivity** | T1 tri/trap/piecewise-convex reruns of α\*, ρ\*, horizon | `reports/shape_sensitivity.md` | Decision stability stated or flips identified |

### E8 — Decision-reversal benchmark (Owner: C runs, B specifies; Weeks 7–9) — **MONEY FIGURE**
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E8.S1 Case sweep** | T1 scan (year × scenario × grid) for cases near P_crit boundary; T2 propose 2–3 candidates with p-box previews | candidate memo → **G5** | Treatments predicted to diverge |
| **E8.S2 Treatments i–iv** | T1 deterministic full availability; T2 single Beta best-estimate; T3 worst-case interval [0.29,0.90]; T4 scenario minimax — all via IC-1/IC-2 + shared CRN | `src/treatments.py` | Same seeds as treatment v; manifests attached |
| **E8.S3 Run & figure** | T1 five treatments on the G5 case; T2 the money figure (method → decision → hidden assumption) | `fig_decision_reversal` + manifests | Decisions genuinely differ; else escalate to G5 re-pick |
| **E8.S4 Narrative** | T1 paper-ready caption naming each method's silent assumption | caption draft | Your editorial approval |

### E9 — Robustness & validation (Owner: C; Weeks 9–10)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E9.S1 P_crit sensitivity** | 1e-2 vs 1e-3 reruns of decision layer | report section | Decisions stable or flips explained |
| **E9.S2 CIGRE cross-check** | full pipeline on CIGRE MV | report section | Qualitative agreement |
| **E9.S3 Full-year and WindowSet validation screen** | Tier-1 full-year screen per scenario; Tier-2 AC validation on WindowSet subsets; export-direction exceedance side screen | report section | Confirms G0-A2 full-year primary event implementation and transparently reports export/feed-in regime if binding |
| **E9.S4 Convergence** | CI-vs-N study; confirm G1 budget adequate | plot | CIs at chosen N within target |
| **E9.S5 Grid-model error sensitivity** | Predeclare and run the signed A-013 `epsilon_grid` alternatives through the output-domain event pipeline with shared CRN | report section + manifests | Shows whether alpha-indexed bounds or decisions change across the PI-approved scenario values; no single value is presented as empirical fact |
| **E9.S5a Grid-model error evidence review** | T1 search primary literature and DSO guidance for aggregate transformer-boundary model error; T2 extract quantity, network level, conditioning/calibration, measurements, domain, statistic/enclosure meaning, and transferability; T3 recommend whether 5% can be sourced or must remain an author-specified scenario | `reports/grid_error_evidence_review.md` | No mechanism inventory or non-comparable result is used as numerical proof; A-013 stays proposed until the PI reviews the evidence |

### E10 — Paper production (Owner: all agents draft, **HUMAN approves every claim**; Weeks 9–12)
| Story | Tasks | Deliverable | Acceptance / Verification |
|---|---|---|---|
| **E10.S1 Figure factory (IC-6)** | `make figures` builds every figure/table from manifests | `paper/figures/` pipeline | Clean rebuild from scratch reproduces all numbers |
| **E10.S2 Manuscript** | T1 Applied Energy skeleton; T2 agents draft sections (intro/related work seeded from the consolidated literature review; methods from this plan; reviewer-attack subsection from review §10); T3 highlights ≤85 chars + graphical abstract; T4 you edit and sign every claim (two-key) | `paper/manuscript.md` | No unsigned numeric claim; citations only from verified list (T7) |
| **E10.S3 Repro package** | T1 repo cleanup + README repro steps; T2 clean-machine/container dry-run; T3 Zenodo deposit prep | repro package | Third party can rebuild the money figure from README alone |
| **E10.S4 Red team** | one agent adversarially reviews the manuscript against review-§10 attacks 1–5 + this plan's threat list | `reports/red_team.md` | Every attack has a written rebuttal in the paper |
| **E10.S5 Gates G6/G7** | results freeze; submission | `DECISIONS.md` | — |

---

## 7. Parallelization & timeline (3-agent configuration)

| Week | Agent A (Simulation) | Agent B (Uncertainty/Decision) | Agent C (Data/Experiments) | Your gates |
|---|---|---|---|---|
| 1 | E1.S1–S2 | (reads plan; drafts invariant specs) | E0 all, E2.S1 | **G0** |
| 2 | E1.S3b, E1.S1b, E1.S2b, E1.S4 | E5.S1, E7.S1 | E2.S2–S3 | **G1** (freeze IC schemas) |
| 3 | E3.S1–S2 | E4 prep (sweep spec) | E2.S4–S6 | — |
| 4 | E3.S3–S4 | **E4.S1 monotonicity** | support E4 runs | **G2, G3** (after G1 C1/C2 evidence) |
| 5 | support B | E5.S2–S3 | E7.S2 data side | — |
| 6 | perf tuning | E5.S4 cross-check, E6.S1–S2 | experiment configs | — |
| 7 | — | E6.S3–S5, E7.S4 | E8.S1 case sweep | **G4, G5** |
| 8 | — | supports E8 spec | E8.S2–S3 | — |
| 9 | — | — | E8.S4, E9.S1–S2 | — |
| 10 | — | — | E9.S3–S5 | — |
| 11 | drafts methods §§ | drafts results §§ | E10.S1, S3 | **G6** |
| 12 | revisions | revisions | E10.S4 red team | **G7 submit** |

**Critical path:** E0 → E1 → E3 → **E4/G3** → E5 → E6 → E8/G5 → E10. Anything not on this path yields if resources are tight.

---

## 8. Risk register (triggers → responses; tracked in `registers/RISKS.md`)

| Risk | Trigger | Response |
|---|---|---|
| Monotonicity fails broadly | G3 evidence | Interior-sampling fallback (E4.S2); restrict claim to demand-driven regime; shrink N or grid |
| Tiers disagree | G2 delta > tolerance | AC primary via lightsim2grid; summation demoted to screening; smaller N |
| Treatments all agree | E8.S3 | Re-pick case nearer P_crit boundary (higher adoption year / weaker feeder) — a benchmark without divergence has no money figure |
| Runtime blowout | >2× budget | lightsim2grid TimeSerie; fewer α levels (K=3); smaller grid; HPC fallback last |
| Data license blocks redistribution | E2.S1 | Ship download scripts + DOIs instead of data; note in availability statement |
| Agent fabrication/drift | any unsigned number or uncited claim | T4/T7 enforcement; PR rejected; register audit |
| Elicitation attacked as arbitrary | reviewer | E7 protocol + shape sensitivity + signed provenance (this is the designed defense) |
| Scope creep | any new idea mid-sprint | Park in `BACKLOG.md`; only you can promote it |

---

## 9. Definition of Done (paper level)

1. Every result figure/table rebuilds from `make figures` on a clean clone (E10.S3 dry-run proof).
2. All invariant suites and the E5.S4 cross-check are green at the frozen N.
3. Every numeric claim in the manuscript carries a register/manifest trace with your sign-off (two-key).
4. All eight gates G0–G7 have signed `DECISIONS.md` entries.
5. The red-team report shows a written rebuttal for review-§10 attacks 1–5.
6. Reporting discipline holds: α-indexed bounds everywhere, no defuzzified single numbers.
7. Submission package (manuscript, highlights, graphical abstract, code/data availability, repro DOI) accepted by you at G7.
