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
- Use one task ID from `actionable_project_plan_agentic.md` per session.
- Work only in your owned paths.
- Scientific values, dependency changes, interface changes, gate decisions, and manuscript numbers require PI approval.
- Every experimental result must be produced through the runner and have a manifest.
- Every new logic change needs tests.
- Every new or changed decision, assumption, or data/protocol choice must add or update the same-ID standalone manuscript paragraph in `paper/methods_decisions_and_assumptions.md`. Preserve the register status in the prose; never write a proposed item as settled.
- Write commit messages and PR titles/descriptions for human reviewers: concise, professional, specific about the outcome, and formatted according to the Git and PR protocol in `agent_instructions.md`. Do not submit raw agent narration or vague "update/fix work" summaries.
- Per G1-A1, model-error intervals are applied to loading trajectories before event detection; never widen probabilities after estimation or sample an interval error as if it were independent randomness.
- Per G1-A2, compose relative grid error with additive Tier-1 endpoints as `(1-e_grid)*max(0,L_T1-e_minus)` and `(1+e_grid)*(L_T1+e_plus)`. A-013 numerical values remain proposed; never call 5% empirical or expert-signed.
- Do not assume the withdrawn 16-104 MVA applicability range. E3.S2b freezes the future operating domain and reports raw MVA under both total and firm capacity conventions before probabilistic results are inspected.
- Report alpha-indexed lower/upper bounds only; never report a defuzzified probability as the answer.

Worktree layout:

- PI dashboard: `P-box_expansion_planning/` on `main`
- Agent A: `P-box_expansion_planning-agent-a/` on `agent-a/...`
- Agent B: `P-box_expansion_planning-agent-b/` on `agent-b/...`
- Agent C: `P-box_expansion_planning-agent-c/` on `agent-c/...`

Agent logs:

- Agent A: `reports/AGENT_A_LOG.md`
- Agent B: `reports/AGENT_B_LOG.md`
- Agent C: `reports/AGENT_C_LOG.md`

Control registers:

- `registers/DECISIONS.md`
- `registers/ASSUMPTIONS.md`
- `registers/DATA_REGISTER.md`
- `registers/RISKS.md`
- `registers/STATUS.md`
- `registers/QUESTIONS.md`
