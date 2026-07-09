# DECISIONS.md

Signed PI decisions live here. Agents may append proposed rows, but they never
write a PI sign-off.

| ID | Date | Gate/topic | Decision | Rationale | Evidence | Status | PI sign-off |
|---|---|---|---|---|---|---|---|
| G0 | TBD | Scope freeze | Pending: overload event, P_crit, grids, weather source | Required before gated scope-specific work | E0 registers; E1.S1 grid inventory | pending | -- |
| G1 | TBD | Foundation validated | Pending: compute budget and IC schema freeze | Required before relying on runtime budget and contracts | E1.S2 benchmark; E1.S3 profile report | pending | -- |
| G2 | TBD | Tier equivalence | Pending: summation primary vs AC primary | Determines overload evaluator strategy | E3.S3 tier comparison | pending | -- |
| G3 | TBD | Monotonicity verdict | Pending: vertex shortcut vs interior sampling | Critical compute shortcut | E4.S1 monotonicity report | pending | -- |
| G4 | TBD | Elicitation sign-off | Pending: fuzzy controllability corners | Paper hinge assumption | E7.S2 worksheet | pending | -- |
| G5 | TBD | Case selection | Pending: decision-reversal benchmark case | Money figure depends on divergent treatments | E8.S1 case sweep | pending | -- |
| G6 | TBD | Results freeze | Pending: paper numbers locked to manifests | Required before manuscript finalization | E9 robustness; E10.S1 figure dry-run | pending | -- |
| G7 | TBD | Submission | Pending: approve Applied Energy submission | Final paper gate | Manuscript, repro package, red-team report | pending | -- |
| DEP-001 | 2026-07-09 | Dependency pin update | Use `simbench==1.6.2` and `pandapower>=3.4,<4` in the `.venv` requirements. | Upstream SimBench 1.6.2 declares `pandapower>=3.4.0`; avoids the older `simbench==1.6.1` / `pandapower==3.5.3` top-level `compare_arrays` import break. | PI review of upstream `simbench` `pyproject.toml`; `.venv` metadata check; `.\scripts\task.ps1 test`; direct import check for `pandapower`, `simbench`, and `lightsim2grid`. | approved | PI approved in chat, 2026-07-09 |
