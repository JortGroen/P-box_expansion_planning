# Per-Task Agent Logs

Use this folder for optional per-task progress notes when a task-specific report
is not already the better record.

- Agent A: `reports/agent_logs/agent-a/<task-id>.md`
- Agent B: `reports/agent_logs/agent-b/<task-id>.md`
- Agent C and C subroles: `reports/agent_logs/agent-c/<task-id>.md`

Do not append routine progress to the legacy aggregate files
`reports/AGENT_A_LOG.md`, `reports/AGENT_B_LOG.md`, or
`reports/AGENT_C_LOG.md`. Those files are retained as historical
PI-dashboard records and are maintainer-only under the ownership checker.

Feature PRs should include the proposed `registers/STATUS.md` row under the
`Suggested STATUS update` section of the PR body. The PI/dashboard assistant
reconciles STATUS after merge batches.
