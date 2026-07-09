# QUESTIONS.md

Agents append escalation questions here. The PI answers here or mirrors the
answer into `DECISIONS.md` when it becomes a decision.

Template:

```text
## Q-<incrementing number> - <task ID> - <date> - BLOCKING: yes|no
CONTEXT: <2-3 lines: what you were doing, what you hit>
QUESTION: <one precise question>
OPTIONS: A) <option - implication>  B) <option - implication>
RECOMMENDATION: <A or B, one line why>
STATUS: open
```


## Q-1 - E1.S1 - 2026-07-08 - BLOCKING: yes
CONTEXT: Agent A prepared the E1.S1 grid loader in `src/grid_loader.py`, but the live grid-stack probe hangs inside `import simbench`. The command `python -u -c "print('start'); import simbench as sb; print('simbench imported', getattr(sb, '__version__', 'unknown'))"` printed only `start` and did not complete after several minutes.
QUESTION: How should Agent A resolve the local Python/grid-stack import hang so the SimBench and CIGRE MV inventories plus deterministic `runpp` baselines can be produced?
OPTIONS: A) PI repairs/provides the approved Python environment for the Agent A worktree - E1.S1 can then run exactly as specified.  B) PI authorizes Agent A to create or repair an isolated environment for this worktree - may require package installation/network access but keeps E1.S1 moving.
RECOMMENDATION: A, because E0 already defines the approved environment and this avoids Agent A changing dependencies or environment policy.
STATUS: resolved by DEP-001 in `registers/DECISIONS.md`; verified in Agent A `.venv` on 2026-07-09.

## Q-2 - E2.S1 - 2026-07-09 - BLOCKING: yes
CONTEXT: Agent C performed E2.S1.T2 URL/license checks for the data register. SimBench, When2Heat, PVGIS/KNMI, EUR-Lex, IEC 60076-7, and the Mueller/Jansen citation now have clear provenance or citation-only/no-download rationales. ElaadNL has no explicit reuse license on the public download page, and the Cicenas thesis source URL/file plus reuse terms are not in the repo.
QUESTION: Should Agent C keep ElaadNL and Cicenas as no-download proposed rows until PI supplies/approves source terms, or replace either source before E2.S1 can be sign-off-ready?
OPTIONS: A) PI supplies or approves license/access/source details for ElaadNL and Cicenas before any download/extraction/use - E2.S1 remains blocked but preserves provenance.  B) PI replaces one or both unclear sources with alternatives that have explicit open licenses - E2.S1 T2-T3 continues after register revision.
RECOMMENDATION: A, because project rules require escalation when a data license is unclear and the current rows already preserve explicit no-download rationales.
STATUS: open
