# P-box Expansion Planning

Repository for the single-paper project:
*When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility*.

Start here:

1. Read `agent_instructions.md` completely.
2. Read `AGENTS.md` as the local entrypoint and reminder.
3. Check `registers/DECISIONS.md`, `registers/STATUS.md`, and `registers/QUESTIONS.md`.
4. Work only on the role-owned paths in `agent_instructions.md`.
5. Produce tests and manifests before any result is trusted.

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

