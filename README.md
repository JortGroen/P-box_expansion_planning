# P-box Expansion Planning

Repository for the single-paper project:
*When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility*.

Start here:

1. Read `agent_instructions.md` completely.
2. Read `AGENTS.md` as the local entrypoint and reminder.
3. Check `registers/DECISIONS.md`, `registers/STATUS.md`, and `registers/QUESTIONS.md`.
4. Work only from the assigned role worktree and only on the role-owned paths in `agent_instructions.md`.
5. Produce tests and manifests before any result is trusted.

Worktree layout:

| Directory | Branch | Purpose |
|---|---|---|
| `P-box_expansion_planning/` | `main` | PI dashboard, reviews, gate decisions |
| `P-box_expansion_planning-agent-a/` | `agent-a/...` | Agent A simulation/grid work |
| `P-box_expansion_planning-agent-b/` | `agent-b/...` | Agent B uncertainty/decision work |
| `P-box_expansion_planning-agent-c/` | `agent-c/...` | Agent C data/experiment work |

Do not run multiple agents in the same checkout. If a branch or task changes,
create or retarget a worktree instead of switching a shared directory.

Environment:

Use the local `.venv` in each worktree; do not use Anaconda `base` for project
work.

```powershell
.\scripts\setup_venv.ps1
.\scripts\task.ps1 test
```

The task wrapper selects `.venv\Scripts\python.exe` directly, so activation is
not required for normal project tasks. For direct Python commands, call the
worktree venv explicitly:

```powershell
.venv\Scripts\python.exe -m pytest
```

The PowerShell task wrapper sets `NUMBA_CACHE_DIR` to `.tmp/numba_cache` so
pandapower/numba imports do not try to write cache files outside the worktree.
For direct Python commands that import pandapower/numba, set it in the same
shell first:

```powershell
$env:NUMBA_CACHE_DIR = Join-Path (Get-Location) ".tmp\numba_cache"
New-Item -ItemType Directory -Force -Path $env:NUMBA_CACHE_DIR | Out-Null
.venv\Scripts\python.exe -c "import pandapower"
```

Current bootstrap status:

- E0 scaffolding is present.
- Scientific choices remain unsigned until the relevant PI gate is recorded in `registers/DECISIONS.md`.
- Data sources are registered as proposed entries only; no raw data is included.

Useful commands:

```bash
python -m pytest
make test
make run
```

On Windows without `make`, use:

```powershell
.\scripts\task.ps1 test
.\scripts\task.ps1 run
```
