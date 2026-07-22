# AGENTS.md

This is the repository entrypoint for AI agents. The full standing instruction set is in `agent_instructions.md`; a session is not compliant until that file has been read completely.

Authority order:

1. `registers/DECISIONS.md`
2. `agent_instructions.md`
3. `actionable_project_plan_agentic.md`
4. `project_plan_v3_when_can_grid_reinforcement_wait.md`
5. `Literature_review_combined.md`

Bootstrap rules:

- If your role is not stated as Agent A, B, or C, stop and ask the PI before implementation.
- Work from your assigned role worktree only; the main repository directory is the PI dashboard and must stay on `main`.
- Never share one working directory across agents, and never `git switch` to another agent's branch inside a role worktree.
- Use the project `.venv` in your assigned worktree; never install or run project dependencies from Anaconda `base`.
- Use `scripts/task.ps1`; it selects `.venv` and sets `NUMBA_CACHE_DIR=.tmp/numba_cache` for pandapower/numba imports.
- In Codex shell calls, use non-login PowerShell (`login:false`) for project commands so user shell-profile hooks such as Anaconda initialization do not run. If a login shell prints an Anaconda hook traceback before a command, treat it as environment noise only when the actual project command ran through `.venv`/`scripts/task.ps1` and exited successfully; otherwise diagnose the command failure.
- Use one task ID from `actionable_project_plan_agentic.md` per PR-sized work unit; a long session may complete multiple units as separate PRs when each unit is safe and reviewable.
- Default to continuation mode: after completing a coherent PR-sized unit, open or update that PR, make the worktree clean, then keep working on another owned, unblocked unit when one is reasonably available.
- Stop only for a hard blocker: missing PI decision/sign-off, missing ownership exception, unavailable required data/dependency/API approval, required long-run approval or checkpointing gap, unsafe scientific boundary, or an unmerged dependency that cannot be sensibly stacked.
- If a follow-up depends on an unmerged PR, either choose an independent task or open a clearly labeled draft stacked PR that names the upstream PR/branch. Do not mix unrelated tasks into one PR.
- Work only in your owned paths.
- Before editing, preflight the intended paths with `scripts/task.ps1 ownership -Paths path/one.py,path/two.py`; use repository-relative paths.
- Run `scripts/task.ps1 ownership` before committing and before opening or updating a PR. The same check is enforced in CI from `configs/agent_ownership.json`.
- A cross-boundary exception is valid only when the PI has already merged an exact branch-and-path entry into `registers/OWNERSHIP_EXCEPTIONS.json` on the PR base branch. An exception added in the agent PR itself never authorizes that PR.
- Do not edit `registers/STATUS.md` or the legacy aggregate logs `reports/AGENT_A_LOG.md`, `reports/AGENT_B_LOG.md`, and `reports/AGENT_C_LOG.md` in normal feature PRs. They are PI-dashboard files. Put task progress in task-specific reports or `reports/agent_logs/<agent>/<task>.md`, and put the suggested STATUS change in the PR body.
- Before launching any process expected to take more than about 15 minutes, send the PI a long-run notice stating its purpose, estimated wall time and resource use, checkpoint location/frequency, and exact resume procedure. Posting the notice is mandatory even when no separate approval is required.
- Every process expected to exceed about 15 minutes must be durably resumable. Persist completed work units, config/code identity, seeds or member IDs, checksums, and the next unit so a restart skips verified work. If checkpointing is technically impossible, stop and obtain explicit PI approval for the restart-only plan before launch. If a run unexpectedly crosses 15 minutes, checkpoint at the next safe boundary and inform the PI before continuing.
- Scientific values, dependency changes, interface changes, gate decisions, and manuscript numbers require PI approval.
- Every experimental result must be produced through the runner and have a manifest.
- Every new logic change needs tests.
- Add a succinct why-comment for non-obvious mathematical, physical, numerical, or governance logic where removing or simplifying it could silently change results. State the invariant or failure mode; do not narrate self-explanatory code.
- Every new or changed decision, assumption, or data/protocol choice must add or update the same-ID standalone manuscript paragraph in `paper/methods_decisions_and_assumptions.md`. Preserve the register status in the prose; never write a proposed item as settled.
- Write commit messages and PR titles/descriptions for human reviewers: concise, professional, specific about the outcome, and formatted according to the Git and PR protocol in `agent_instructions.md`. Do not submit raw agent narration or vague "update/fix work" summaries.
- The PR `Summary` must be understandable without reading the diff: explain why the PR exists, what changes for the project, what it does not decide or claim, and what the reviewer should focus on.
- PI-dashboard assistance uses the lightweight protocol in `reports/PI_DASHBOARD_CACHE.md`: start from the non-authoritative cache, live PR/status summaries, and targeted register searches; open full registers, plans, logs, or CI output for gates, scientific decisions, PR conflicts, manuscript numbers, or any discrepancy. This reduces Codex usage without changing document authority.
- Per G1-A1, model-error intervals are applied to loading trajectories before event detection; never widen probabilities after estimation or sample an interval error as if it were independent randomness.
- Per G1-A2, compose relative grid error with additive Tier-1 endpoints as `(1-e_grid)*max(0,L_T1-e_minus)` and `(1+e_grid)*(L_T1+e_plus)`. A-013 numerical values remain proposed; never call 5% empirical or expert-signed.
- Per ALEA-001, construct each aleatory sample on one common calendar, keep complete temporal paths, and drive HP/PV from the same paired weather member. Treat copulas or latent factors as evidence-triggered escalations, not defaults.
- Per WEATHER-001, implement HP/PV weather pairing through the neutral shared contract in `src/weather_model.py`; do not create separate HP-local and PV-local weather schemas that are only reconciled later by convention or manifest.
- Per ALEA-002, compute congestion and profile-library adequacy only after all components are aggregated into net load; component-level percentiles and the ElaadNL UI p95 are diagnostics only.
- Per EV-003, direct bootstrap from complete frozen ElaadNL annual members is primary. Keep member IDs and seed metadata traceable; do not invent a within-realization replacement rule before the same-seed warning and cohort sizes are resolved.
- Per EV-004, the primary residential EV source is one fixed 2030 ElaadNL home charge-point distribution at 11 kW, reused across planning layers; adoption changes physical charge-point counts and nodal allocation only. Do not regenerate residential behavior by planning year or substitute the superseded home-EV profile unit.
- Per EV-005, keep finite-library uncertainty from `M` separate from conditional Monte Carlo uncertainty from `N`. Candidate and held-out API batches stay disjoint, adequacy is tested only downstream, and `M = 1000` is a candidate rather than a guaranteed sufficient size.
- Per EV-006, unrelated ElaadNL source batches use distinct seeds, but a smart-charging counterfactual deliberately reuses its uncontrolled batch seed and returned member index. Treat the two control modes as paired potential outcomes; never aggregate or resample them as independent chargers. Smart charging remains optional until its role and parameters are separately approved.
- Per G0-A3, the executable working event is strictly `L_import > 1.1 p.u.` for four consecutive 15-minute steps. This value is provisional: stop for PI review and resolution of Q-5 before any integrated event-based scientific analysis or manuscript result; never relabel historical 1.0-p.u. evidence.
- Per G0-A4, the complete primary probabilistic analysis and E8 benchmark use planning year 2035. E3.S2b still screens 2030/2033/2035, but G5 cannot choose the year after inspecting results. Do not confuse the fixed 2030 ElaadNL generator year with the 2035 planning layer; if 2035 is unusable, stop and escalate rather than switching years or tuning inputs.
- Do not assume the withdrawn 16-104 MVA applicability range. E3.S2b freezes the future operating domain and reports raw MVA under both total and firm capacity conventions before probabilistic results are inspected.
- Report alpha-indexed lower/upper bounds only; never report a defuzzified probability as the answer.

Worktree layout:

- PI dashboard: `P-box_expansion_planning/` on `main`
- Agent A: `P-box_expansion_planning-agent-a/` on `agent-a/...`
- Agent B: `P-box_expansion_planning-agent-b/` on `agent-b/...`
- Agent C: `P-box_expansion_planning-agent-c/` on `agent-c/...`

Agent progress:

- Task-specific reports under `reports/`
- Optional per-task logs under `reports/agent_logs/agent-a/`, `reports/agent_logs/agent-b/`, or `reports/agent_logs/agent-c/`
- Legacy aggregate logs are maintainer-only historical files

Control registers:

- `registers/DECISIONS.md`
- `registers/ASSUMPTIONS.md`
- `registers/DATA_REGISTER.md`
- `registers/RISKS.md`
- `registers/STATUS.md` (PI-dashboard only; agents propose updates in PR bodies)
- `registers/QUESTIONS.md`
- `registers/OWNERSHIP_EXCEPTIONS.json`
