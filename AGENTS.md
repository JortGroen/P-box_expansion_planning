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
- Use one task ID from `actionable_project_plan_agentic.md` per session.
- Work only in your owned paths.
- Scientific values, dependency changes, interface changes, gate decisions, and manuscript numbers require PI approval.
- Every experimental result must be produced through the runner and have a manifest.
- Every new logic change needs tests.
- Report alpha-indexed lower/upper bounds only; never report a defuzzified probability as the answer.

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

