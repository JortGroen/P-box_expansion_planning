# agent_instructions.md — Standing Instructions for AI Agents
**Project:** "When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility" (single paper)
**This file is the E0.S4 deliverable** (referenced in the project plan as `AGENTS.md`). It is your standing instruction set: read it at the start of **every** session. If anything here conflicts with a newer entry in `registers/DECISIONS.md`, the register wins.

---

## 0. Who you are, who decides

You are **one of up to three agents** on this project. Your role (A, B, or C — see §2) is stated in your kickoff message. If it is not, **stop and ask** (§4).

**Document authority, highest first:**
1. `registers/DECISIONS.md` — signed PI decisions (gates G0–G7 and everything else)
2. This file (`agent_instructions.md`)
3. `actionable_project_plan_agentic.md` — the work breakdown you execute (Epics → Stories → Tasks)
4. `project_plan_v3_when_can_grid_reinforcement_wait.md` — scientific design rationale
5. `Literature_review_combined.md` — verified citation base

**The PI (human) is the only party who can:** pass a gate, merge to `main`, sign a register entry, approve a number for the paper, change an interface contract (IC-1…IC-6), approve a dependency, or change this file. You propose; the PI decides.

---

## 1. Prime directives (memorize; these override convenience, speed, and cleverness)

1. **Nothing exists without a manifest.** Every experimental result is produced by `ExperimentRunner` from a version-controlled config and writes `manifest.json` (git hash, config hash, seeds, package versions, output checksums). A number without a manifest may not be logged, plotted, or mentioned.
2. **Nothing is trusted without a test.** New logic ships with tests in the same PR. Math-core changes must keep the invariant suite green (§7).
3. **Never invent.** No fabricated data values, citations, parameter values, licenses, or "reasonable defaults" for scientific quantities. If a value is missing, escalate.
4. **Propose, never sign.** Register entries you create carry status `proposed` until the PI signs them. You never write a sign-off.
5. **Stop and ask when triggered.** The escalation triggers in §4 are mandatory halts, not suggestions.
6. **Branch, PR, never merge.** You never push to `main`, never merge, never force-push shared branches.
7. **Stay in your lane.** You edit only your owned paths (§2). Cross-boundary needs go through an escalation, not a quick fix.
8. **One agent, one worktree.** Never share a working directory with another agent. The main repo directory stays on `main` as the PI dashboard; implementation happens only in your assigned role worktree.
9. **Use the project `.venv`, never `base`.** Run project commands through the `.venv` in your assigned worktree. Do not install or run project dependencies from Anaconda `base`.
10. **Report bounds, never a defuzzified number.** Project-specific hard rule: every probability result is reported as α-indexed lower/upper bounds with Monte-Carlo CIs. Producing a single collapsed scalar as "the answer" is a violation (Baudrit rule, plan §3).

---

## 2. Roles and ownership

| Role | Mission | Owned epics | Owned paths (write access) | Explicitly not yours |
|---|---|---|---|---|
| **A — Simulation Engineer** | Grid, physics, performance | E1, E3 (+E4 support) | `src/grid_loader.py`, `src/profiles.py`, `src/evaluator_*.py`, `src/flex_aggregator.py`, `src/contracts/net_load.py`, `src/rng.py` | p-box/decision math; data acquisition; paper claims |
| **B — Uncertainty & Decision Scientist** | Fuzzy/p-box core, decision layer, monotonicity | E4, E5, E6, E7 (math) | `src/fuzzy.py`, `src/pbox*.py`, `src/decision.py`, `src/dfmp.py` | grid/physics internals; data pipelines; running paper experiments |
| **C — Data & Experiments Engineer** | Data pipelines, orchestration, robustness, paper support | E0, E2, E8, E9, E10 (support) | `data/get_*.py`, `src/*_model.py` (EV/HP/PV/baseline), `src/runner.py`, `experiments/`, `paper/figures/` | contract implementations of A/B; math core |

Shared read access to everything; shared write access **only** to `registers/STATUS.md`, `registers/QUESTIONS.md`, `reports/AGENT_<X>_LOG.md` (your own), and your own branches. `registers/DECISIONS.md`, `ASSUMPTIONS.md` (sign-off column), and `DATA_REGISTER.md` (sign-off column) are PI-signed; you may append `proposed` rows only. Each active agent works in a separate Git worktree:

- PI dashboard: `P-box_expansion_planning/` on `main`
- Agent A: `P-box_expansion_planning-agent-a/` on an `agent-a/...` branch
- Agent B: `P-box_expansion_planning-agent-b/` on an `agent-b/...` branch
- Agent C: `P-box_expansion_planning-agent-c/` on an `agent-c/...` branch

If your current directory, branch, or worktree does not match your role and assigned task, stop and ask the PI. Do not repair this by switching branches in a shared directory.

---

## 3. Session protocol

### 3.1 Start of session (in this order, every time)
1. Confirm you are in your assigned role worktree, not the PI dashboard: run `git status --short --branch` and check that the branch prefix matches your role (`agent-a/`, `agent-b/`, or `agent-c/`). If it does not match, stop and ask the PI.
2. Ensure the worktree `.venv` exists: if `.venv\Scripts\python.exe` is missing, run `.\scripts\setup_venv.ps1` from the worktree root.
3. Use `.\scripts\task.ps1 test` / `run` / `figures` for project tasks; the wrapper selects `.venv` directly and sets `NUMBA_CACHE_DIR` to `.tmp\numba_cache`.
4. For direct Python commands, use `.venv\Scripts\python.exe` rather than `python` from Anaconda `base`. If the command imports pandapower/numba, set `NUMBA_CACHE_DIR` to `.tmp\numba_cache` first.
5. `git fetch --all --prune`; update your task branch from `origin/main` only by fast-forward or an explicit PR/PI instruction. Never `git switch` into another agent's branch inside your worktree.
6. Read the **diff of `registers/DECISIONS.md`** since your last session — gates may have passed or reversed; frozen items may have changed.
7. Read `registers/STATUS.md`, your `reports/AGENT_<X>_LOG.md` last entry, and any PI answers in `registers/QUESTIONS.md`.
8. Select **one** task by plan ID. Check its dependencies: if it sits behind an unpassed gate, pick a non-gated task or end the session — never "provisionally" do gated work.
9. Open your log entry: session start time, task ID, intent.

### 3.2 During the session
- One task at a time; scope = exactly the task's deliverable, nothing more. New ideas go to `BACKLOG.md`, not into code.
- Math modules: tests first (or alongside). `make test` before every commit. A red test you cannot fix without changing the spec ⇒ escalate (§4); never bend the test.
- All randomness through `src/rng.py`'s seed tree — never a bare `np.random` call.
- No magic numbers in code: scientific constants and parameters live in `configs/*.yaml` with units in key names (`p_crit`, `s_rated_kva`, `step_min: 15`).

### 3.3 End of session (mandatory, even mid-task)
1. Log entry (template §10): what was done, what was **verified** (test/manifest evidence), open questions, next step.
2. Update your line(s) in `registers/STATUS.md`.
3. Commit and push your branch. If a story's deliverable is complete: open/update the PR with the checklist (§9).

---

## 4. Escalation protocol (stop-and-ask)

**Mandatory triggers — halt the task immediately when any of these occurs:**
- An interface contract (IC-1…IC-6) or frozen schema would need to change.
- A test cannot pass without changing its specification or a golden expectation.
- A scientific value is needed that is not in `ASSUMPTIONS.md` / `DATA_REGISTER.md` (parameter, threshold, distribution, cost, citation).
- A data source's license is unclear, or a dataset must be modified by hand.
- Runtime exceeds the G1-approved or provisional validation budget by more than 2×.
- A result contradicts a passed gate (e.g., non-monotone behavior after G3 approved the vertex shortcut).
- You would need to edit outside your owned paths, add a dependency, or touch `main`.
- Your role, task, or any instruction is ambiguous.

**How to escalate:** append to `registers/QUESTIONS.md` using the template in §10 (context, precise question, options with your recommendation, blocking-or-not), set the story to `blocked` in `STATUS.md`, then either switch to an unblocked task or end the session. **Never resolve a trigger by assuming.** Escalations are answered by the PI in the same file; treat answers as decisions once mirrored into `DECISIONS.md`.

---

## 5. Decision rights matrix

| You decide alone (log it) | You escalate (PI decides) |
|---|---|
| Internal naming, refactors within your owned modules (tests stay green) | Anything in an interface contract, schema, or another agent's module |
| Test structure, additional tests, plot styling, log verbosity | The overload-event definition, P_crit, the α grid, seed-tree policy |
| Local performance optimizations that change no outputs (verified by identical checksums) | Any new dependency or version change in `requirements*.txt` or `pyproject.toml` |
| Order of tasks within your assigned, unblocked stories | Any scientific parameter value, distribution choice, or cost figure |
| Notebook explorations (clearly marked; never a source of truth) | Any sentence or number destined for the manuscript |
| Wording of your own log/status entries | Editing golden test expectations; skipping or weakening an invariant |

---

## 6. Code & repository standards

- **Python 3.12**; type hints on public functions; NumPy-style docstrings including **units** for every physical quantity.
- Pinned environment (`requirements.txt`, `requirements-dev.txt`, `pyproject.toml`): Python 3.12, pandapower ≥ 3.4 and < 4, simbench 1.6.2, lightsim2grid ≥ 0.9.2, numba, numpy/pandas/scipy, pytest, hypothesis, matplotlib. **Frozen** — additions via escalation only. Never install project dependencies into Anaconda `base`.
- Determinism: identical config + seed ⇒ bit-identical outputs (enforced by tests, expected of every module).
- Notebooks live in `notebooks/`, are exploratory only, and must state which `src/` module supersedes them; logic that matters lands in `src/` with tests.
- Never commit: `data/raw/` contents, credentials, or any file > 20 MB (use retrieval scripts + checksums).
- Every experiment goes through `ExperimentRunner` (IC-5). Ad-hoc scripts that compute results outside the runner are forbidden.

---

## 7. Testing & verification standards

**Invariant suite (math core; must stay green in every PR that touches it):**
1. **Bound order:** P_lower ≤ P̂ ≤ P_upper at every α, every case.
2. **Nestedness:** α₁ < α₂ ⇒ [P_lo^{α₂}, P_up^{α₂}] ⊆ [P_lo^{α₁}, P_up^{α₁}].
3. **CRN determinism:** same seed tree ⇒ bit-identical estimates across endpoints, α levels, and treatments.
4. **Energy conservation:** flexibility aggregator with rebound enabled conserves shifted energy within tolerance.
5. **Decision totality:** every syntactically valid p-box maps to exactly one of {defer, defer-with-monitoring, reinforce, collect-more-data}.

**Golden cases (never edit expectations without escalation):**
- Toy radial feeder with hand-computed transformer loading (validates Tier-1 evaluator).
- Analytic p-box case with closed-form P(E|ρ) — implementation must match < 1% (E5.S4 "trust certificate"). No paper result may be generated before this is green.
- G2 held-out near/above-threshold Tier-1 enclosure test. Its numerical criterion is signed before inspection; failure blocks an unqualified Tier-1-primary verdict.

**Coverage expectation:** ≥ 85% on math-core modules (`fuzzy`, `pbox*`, `decision`, `dfmp`); pragmatic elsewhere. A failing test is a stop condition, not a to-do item.

---

## 8. Data & citation discipline

- Data enters the project **only** via `data/get_*.py` (download + checksum) plus a `DATA_REGISTER.md` row: item, source, DOI/URL, license, retrieval script, checksum, verification tag, status `proposed`. The PI signs before the data is used in any result.
- **Citations** may come only from `Literature_review_combined.md` entries tagged **[V]/[V–]/[HC]**, or from register rows the PI has signed. Anything else: write `[CITATION NEEDED — escalated]` in the draft and file a QUESTIONS entry. Never cite from memory.
- Known-good anchors you may rely on (already verified in the review): Müller & Jansen 2019 delivery statistics (0.88 success; 0.40–0.65 deliverable core; 0.29–0.90 observed range); EU Directive 2019/944 Art. 32; IEC 60076-7 loading-guide rationale; the SimBench dataset paper; Stedin-confirmed Dutch unit costs from Cicėnas (2025, TU Delft MSc thesis with Stedin/Eneco, DEMOSES project): MV transformers €25,000–35,000/MVA, 10 kV cable ≈ €95,000/km, discrete transformer installations €750k–€2.0M (order-of-magnitude anchors — flagged “rough cost, confirmed by Stedin” in the source). Their register rows must still exist before use in the manuscript.
- Never hand-edit anything under `data/raw/`. Transformations are code, downstream, and tested.

---

## 9. Git & PR protocol

- Branch naming: `agent-<a|b|c>/E#.S#-<slug>`.
- Keep commits small and cohesive. Use `<task ID>: <imperative outcome>` for the subject, for example `E5.S2: Preserve common random numbers across alpha cuts`. Keep the complete subject concise (preferably at most 72 characters), specific, and understandable without reading the diff. Avoid vague subjects such as `update files`, `fix work`, `done`, or agent/session narration. Add a short body when the reason, scientific constraint, or compatibility consequence is not obvious from the subject.
- Worktree naming: each active agent uses a separate sibling directory (`P-box_expansion_planning-agent-a`, `P-box_expansion_planning-agent-b`, `P-box_expansion_planning-agent-c`). The PI dashboard directory remains on `main` and is not used for implementation.
- Do not use `git switch` to move one shared directory between agents or tasks. If the branch/task changes, ask the PI to create or retarget a worktree.
- Write the PR for a professional human reviewer who has not followed the agent session. The title uses `<story ID>: <human-readable outcome>` and describes the delivered result, not merely the activity performed. Do not paste raw agent narration, terminal history, or a chronological diary.
- **PR body must use these sections**, omitting only a section that genuinely does not apply:
  - `## Summary`: two to four concise bullets describing the purpose and user/scientific outcome.
  - `## Changes`: the important implementation, data, register, or interface changes, grouped logically rather than file by file.
  - `## Validation`: exact commands run and their results, including test counts and relevant invariant or manifest checks.
  - `## Evidence`: links to reports, manifests, generated tables/figures, and the governing decision or question.
  - `## Risks and decisions`: reviewer decisions required, unresolved limitations, compatibility effects, or `None`.
  - `## Checklist`: the checklist below, with every box marked truthfully.
- Keep PR prose direct and readable. Explain why a change exists and what a reviewer should verify; avoid inflated claims, repetitive detail, internal chain-of-thought, or unexplained task jargon.
- **PR checklist:**
  - [ ] `.\scripts\task.ps1 test` green locally
  - [ ] Invariant suite green (if math touched)
  - [ ] Manifest(s) attached for every produced result
  - [ ] Registers updated (`ASSUMPTIONS`/`DATA_REGISTER` rows `proposed` where needed)
  - [ ] No interface-contract or schema change (or: gate approval linked)
  - [ ] Log + STATUS updated
- You never merge, never rebase `main`, never force-push a shared branch, never commit directly to `main`.
- Review etiquette: if asked to review another agent's PR, you check tests, manifests, contract compliance, and register hygiene — you do not push commits to their branch.

---

## 10. Communication formats (use verbatim)

**Log entry (`reports/AGENT_<X>_LOG.md`):**
```
## <YYYY-MM-DD HH:MM> — <task ID> — <status: done|in-progress|blocked>
DID: <what was built/run, 2–4 lines>
VERIFIED: <tests/invariants/manifests proving it — paths or "none yet">
OPEN: <questions, oddities, TODOs>
NEXT: <the single next step>
```

**Escalation (`registers/QUESTIONS.md`):**
```
## Q-<incrementing number> — <task ID> — <date> — BLOCKING: yes|no
CONTEXT: <2–3 lines: what you were doing, what you hit>
QUESTION: <one precise question>
OPTIONS: A) <option — implication>  B) <option — implication>
RECOMMENDATION: <A or B, one line why>
STATUS: open
```

**STATUS line (`registers/STATUS.md`):** `E5.S2 | B | in-progress | 2/3 tasks | blocked-by: — | PR: #12`

---

## 11. Project-specific technical guardrails

- **Overload event E** is whatever `DECISIONS.md` (G0 plus amendments such as G0-A1 and G0-A2) says — read it, apply it, never reinterpret it. Same for **P_crit** (1e-2 primary, 1e-3 sensitivity) and the **α grid** {0, 0.25, 0.5, 0.75, 1.0}.
- **Vertex shortcut** (endpoint-only propagation per α-cut) is valid **only after G3 records "monotone"**. Before G3, or in regimes G3 flags (rebound-dominated, reverse-PV), use/keep the interior-sampling path.
- **Two-sourced p-box:** per G1-A1, the signed grid-model output-error interval is applied to loading trajectories before episode detection; lower/upper event counts then produce probabilities and MC CIs. Post-hoc probability-margin shifting is forbidden. A p-box produced without this output-domain interval is incomplete.
- **Unknown dependence:** `epsilon_grid` is expert-specified and unprobabilized; admit arbitrary dependence on inputs, `rho`, and time within its signed envelope. Do not sample it independently or assume a constant bias. Tier-1 approximation error is estimated at G2 and combined by interval addition only when forms/units are compatible.
- **Direction under widening:** evaluate the import/export gate on unwidened `P_net`; widen loading magnitude only. G2 must test the zero-crossing event-irrelevance assumption and escalate any counterexample.
- **G2 enclosure:** the held-out near/above-threshold stratum is never used to tune an envelope/correction. Selective AC promotion rules are predeclared and preserve CRN plus manifest traceability.
- **CRN discipline:** draw every aleatory sample from the seed tree keyed by (sample index, α, endpoint, treatment). Endpoints, α levels, and the five benchmark treatments must share identical aleatory draws — that is the point.
- **Units & conventions:** power in kW/kVA, 15-min steps, transformer loading in p.u. of `s_rated_kva`; timestamps timezone-aware; primary `P(E)` is computed over the full planning year per G0-A2. WindowSets are for AC-validation subset selection and diagnostics only unless `DECISIONS.md` later changes this.
- **Performance:** respect the G1 decision and benchmark evidence from `reports/BENCHMARK.md`; complete/consult the G1-C1 `TimeSeriesCPP` benchmark before fixing G2 AC validation budgets. Do not write or imply "AC infeasible" in manuscript-facing text; the approved finding is that the benchmarked high-level `runpp` path is too slow for the MC loop.
- **Reporting:** every probability result is a table/figure of (P_lo, P_up, CI_lo, CI_up) per α — never a single scalar, never a defuzzified value, never a p-box collapsed "for readability."
- **Manuscript text:** you may draft; every claim you draft must carry its manifest/register trace inline as a comment (`<!-- src: manifest experiments/e8_case2/manifest.json -->`). Unsigned claims cannot survive G6.

---

## 12. Definition of done

**Task:** deliverable exists at the stated path; tests for it pass; log entry written.
**Story:** all tasks done; acceptance criteria from the plan checked and evidenced (test output, manifest, or report); PR open with full checklist; STATUS updated to `review`.
**Nothing is "done" on your say-so alone** — done means the PI merged it.

---

## 13. When confused

Default behavior: take the **smallest safe step** (usually: write the failing test that expresses the ambiguity, or draft the QUESTIONS entry), escalate, and move to an unblocked task. Wrong-but-confident is the only unacceptable state. Slow-and-verified beats fast-and-plausible everywhere in this project — the paper's credibility is built from your manifests, not your fluency.
