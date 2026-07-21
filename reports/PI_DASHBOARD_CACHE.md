# PI Dashboard Cache

Status: maintainer convenience cache; not an authority source.
Last protocol update: 2026-07-21.

Use this file to reduce repeated Codex context and tool-output costs during PI
coordination. If this cache conflicts with live GitHub state, `registers/*`, or
the project plans, the live authoritative source wins.

## PI Lite Default

For routine questions such as "what next?", "what gates are open?", PR triage,
or agent coordination, use PI Lite unless the PI explicitly asks for a full
audit.

1. Check the local branch and dirty state with compact output.
2. Fetch GitHub state and list open PRs with only number, title, branch,
   mergeability, review state, and check conclusions.
3. Read `registers/STATUS.md` and `registers/QUESTIONS.md` first.
4. Search `registers/DECISIONS.md`, `ASSUMPTIONS.md`,
   `DATA_REGISTER.md`, `RISKS.md`, the plans, and agent logs by exact task,
   question, decision, assumption, PR, or path ID.
5. Open whole source files only when the targeted search is insufficient,
   a conflict appears, or a scientific/gate decision depends on surrounding
   context.
6. Update this cache after major PI dashboard reconciliations, merged gate
   decisions, or repeated status patterns that future sessions need quickly.

## Output Budget Rules

- Prefer `rg -n "Q-7|D-010|E2.S6" <paths>` and `Select-String` over raw full
  file reads.
- Use `Select-Object -First`, `Select-Object -Last`, `--limit`, `--json` with
  narrow field lists, or small `max_output_tokens` for commands that may print
  logs, CI rollups, or large tables.
- Do not paste raw test logs, PR timelines, or full GitHub check objects into
  the task unless investigating a failure.
- Summarize command evidence in the response; keep URLs or exact failing lines
  only when they are needed for review.

## Validation Economy

- For local development loops, run focused tests and
  `.\scripts\task.ps1 test-fast`.
- Run `.\scripts\task.ps1 test` for merge-gate verification, risky shared
  behavior, or when the PI asks for full local validation.
- Let CI provide the full-suite gate when local full-suite output would mostly
  duplicate already-visible CI evidence.

## Full Audit Triggers

Leave PI Lite and inspect broader context when:

- The PI is about to approve or reject a scientific decision, gate, assumption,
  data source, or manuscript claim.
- A PR changes contracts, scientific semantics, dependency versions, manifests,
  or ownership boundaries.
- Live PR/check status conflicts with a register, task report, or handoff.
- An agent proposes to discard/repeat expensive work.
- A question depends on historical rationale rather than current operational
  state.

## Thread Hygiene

- Use separate tasks for large PR reviews, implementations, and PI-dashboard
  status tracking.
- Prefer short handoffs that name exact files, IDs, PRs, and required checks
  instead of pasting the full governance bundle.
- Archive or stop using completed implementation/review tasks after the PR is
  merged or closed so future context starts small.
