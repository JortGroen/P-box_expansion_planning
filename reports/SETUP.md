# Bootstrap Setup Report

Date: 2026-07-08

Scope:

- Created the E0 project scaffold.
- Added control registers with unsigned proposed/pending rows.
- Added a deterministic manifest utility and tests.
- Added `AGENTS.md` as the agent entrypoint pointing to the full standing instructions.
- Added a minimal CI workflow and Makefile.

Not done:

- No dependencies were installed.
- No raw data was downloaded.
- No scientific gate was passed.
- No manuscript number was approved.

Next PI actions:

1. Assign each active agent a role: A, B, or C.
2. Review E0 deliverables.
3. Sign or revise G0 scope decisions in `registers/DECISIONS.md`.
4. Let agents start with unblocked tasks according to `registers/STATUS.md`.

Worktree cleanup:

- `P-box_expansion_planning/` is the PI dashboard and should remain on `main`.
- `P-box_expansion_planning-agent-a/` is checked out on `agent-a/E1.S1-grid-loading`.
- `P-box_expansion_planning-agent-b/` is checked out on `agent-b/E5.S1-fuzzy-number-class`.
- `P-box_expansion_planning-agent-c/` is checked out on `agent-c/E2.S1-data-acquisition`.
- Misplaced untracked Agent B files (`src/fuzzy.py`, `tests/test_fuzzy.py`) were moved from the Agent A checkout into the Agent B worktree.

Environment policy:

- Use a local `.venv` in each worktree, created with `scripts/setup_venv.ps1`.
- Do not install or run project dependencies from Anaconda `base`.
- `requirements.txt`, `requirements-dev.txt`, and `pyproject.toml` are the pinned dependency sources; SimBench is pinned to 1.6.2 with pandapower ≥3.4 and <4.
- `scripts/task.ps1` runs `.venv\Scripts\python.exe` directly and sets `NUMBA_CACHE_DIR` to `.tmp/numba_cache` inside each worktree for pandapower/numba imports.
- The abandoned conda environment `pbox-expansion-planning` may still exist locally, but it is not the project runtime.
