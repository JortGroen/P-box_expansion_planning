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

**Escalation triggers (agent must stop and ask you):** interface change needed; a test cannot pass without changing the spec; unclear data license; runtime exceeds budget by >2×; results contradict a passed Gate; anything requiring a value not in the registers.

**Control registers** (created in E0, live in `registers/`): `DECISIONS.md` (gate outcomes, signed), `ASSUMPTIONS.md` (id, statement, rationale, owner, status), `DATA_REGISTER.md` (item, source, DOI/URL, license, retrieval script, checksum, verification tag, PI sign-off), `RISKS.md` (§8), `STATUS.md`.

---

## 4. Human decision gates (only YOU can pass these)

| Gate | When | Question you decide | Inputs required from agents | Outcomes |
|---|---|---|---|---|
| **G0 Scope freeze** | end W1 | Approved in `registers/DECISIONS.md`: decision-transformer event E, P_crit primary/sensitivity protocol, grid/fallback rule, KNMI weather ensemble, and primary alpha grid | E0 registers initialized; grid inventory report (E1.S1); G0 assumption rows A-005--A-008 | frozen; changes require a new signed decision |
| **G1 Foundation validated** | end W2 | Is the compute plan real? Approve N budget and time structure | Laptop micro-benchmark (E1.S2); profiles + critical-week validation (E1.S3) | proceed / shrink grid / adjust N |
| **G2 Tier equivalence** | W3–4 | Is summation ≈ AC for transformer loading (tolerance you set, e.g. ≤2%)? | Tier comparison report (E3.S3) | summation primary / AC primary |
| **G3 Monotonicity verdict** | W4 | Is P(E\|ρ) monotone in the demand-peak regime? | Monotonicity report + regime split (E4.S1) | vertex shortcut / interior-sampling fallback / restrict scope to demand-driven regime |
| **G4 Elicitation sign-off** | W7 | The trapezoid corners of ρ̃_flex (the paper's hinge) | Elicitation worksheet + candidate trapezoids (E7.S2) | sign corners into DECISIONS.md |
| **G5 Case selection** | W7–8 | Which case for the decision-reversal benchmark (must sit near the P_crit boundary so treatments genuinely diverge) | Case-sweep candidates (E8.S1) | pick case / demand harder case |
| **G6 Results freeze** | W11 | All paper numbers locked to manifests | Robustness report (E9); figure pipeline dry-run (E10.S1) | freeze / iterate |
| **G7 Submission** | W12 | Submit to Applied Energy | Full manuscript, repro package, red-team report | submit / revise |

---

## 5. Interface contracts (frozen at G1; changes only via you)

These contracts are what let agents work independently. Each has a schema doc + contract tests in `src/contracts/`.

**IC-1 NetLoadProvider** (A provides → B, C consume)
`get_net_load(scenario: str, year: int, window: TimeWindow, rho: float, seed: int) -> ndarray[nodes, timesteps]` (kW, 15-min). Deterministic in `seed` (CRN guarantee). Includes flexibility activation at controllability ρ and configurable rebound.

**IC-2 OverloadEvaluator** (A provides → B consumes)
`evaluate(net_load) -> {loading_series: ndarray, overload: bool}` per the G0 event definition. Tier-1 = radial summation; same signature for the Tier-2 AC implementation (drop-in swap).

**IC-3 PBoxEstimator** (B provides → C consumes)
`estimate(provider, evaluator, alpha_grid, fuzzy_number, N, seed) -> {alpha: (P_lo, P_up, CI_lo, CI_up)}` with model-error interval widening applied.

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
| **E1.S3 Time series & critical weeks** | T1 ingest SimBench full-year 15-min profiles, scenarios 0/1/2; T2 critical-week extractor (top-loading winter weeks per year); T3 validation plot windows-vs-full-year exceedances | `src/profiles.py`, `data/critical_weeks.parquet`, plot | Windows capture ≥95% of annual top-loading steps (checked in E9.S3 full-year screen) |
| **E1.S4 Tier-1 evaluator** | T1 radial downstream summation of net P and Q → loading series L(t) = │Σᵢ Sᵢ(t)│ / Σᵢ S_nom,i (magnitude of complex net substation exchange over summed nameplate — per G0; direction-agnostic, captures reverse-PV flow); T2 overload-event flag per G0 definition; T3 unit tests vs hand-computed toy feeder incl. a reverse-flow case | `src/evaluator_sum.py` + tests | Matches hand calculation exactly on toy case |

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
| **E3.S3 Tier-2 AC harness** | T1 pandapower+lightsim2grid time-series runner (IC-2 drop-in); T2 summation-vs-AC comparison on sampled draws | `reports/tier_comparison.md` | Transformer-loading delta quantified → G2 |
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
| **E5.S3 Model-error widening** | T1 interval widening (two-sourced p-box); config-driven | config + tests | Widening visible & correct on synthetic case |
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
| **E9.S3 Full-year screen** | Tier-2 full-year pass per scenario; window-coverage check; reverse-PV regime screen | report section | Confirms E1.S3 window claim; PV regime flagged if binding |
| **E9.S4 Convergence** | CI-vs-N study; confirm G1 budget adequate | plot | CIs at chosen N within target |

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
| 2 | E1.S3–S4 | E5.S1, E7.S1 | E2.S2–S3 | **G1** (freeze IC schemas) |
| 3 | E3.S1–S2 | E4 prep (sweep spec) | E2.S4–S6 | — |
| 4 | E3.S3–S4 | **E4.S1 monotonicity** | support E4 runs | **G2, G3** |
| 5 | support B | E5.S2–S3 | E7.S2 data side | — |
| 6 | perf tuning | E5.S4 cross-check, E6.S1–S2 | experiment configs | — |
| 7 | — | E6.S3–S5, E7.S4 | E8.S1 case sweep | **G4, G5** |
| 8 | — | supports E8 spec | E8.S2–S3 | — |
| 9 | — | — | E8.S4, E9.S1–S2 | — |
| 10 | — | — | E9.S3–S4 | — |
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
