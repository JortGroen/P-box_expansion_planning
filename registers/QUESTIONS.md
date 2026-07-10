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

Resolved and open questions are listed below.

## Q-1 - E1.S1 - 2026-07-08 - BLOCKING: yes
CONTEXT: Agent A prepared the E1.S1 grid loader in `src/grid_loader.py`, but the live grid-stack probe hangs inside `import simbench`. The command `python -u -c "print('start'); import simbench as sb; print('simbench imported', getattr(sb, '__version__', 'unknown'))"` printed only `start` and did not complete after several minutes.
QUESTION: How should Agent A resolve the local Python/grid-stack import hang so the SimBench and CIGRE MV inventories plus deterministic `runpp` baselines can be produced?
OPTIONS: A) PI repairs/provides the approved Python environment for the Agent A worktree - E1.S1 can then run exactly as specified.  B) PI authorizes Agent A to create or repair an isolated environment for this worktree - may require package installation/network access but keeps E1.S1 moving.
RECOMMENDATION: A, because E0 already defines the approved environment and this avoids Agent A changing dependencies or environment policy.
STATUS: resolved by DEP-001 in `registers/DECISIONS.md`; verified in Agent A `.venv` on 2026-07-09.

## Q-2 - E2.S1 - 2026-07-10 - BLOCKING: no
CONTEXT: The originally planned historical ElaadNL/EVnetNL transaction/profile dataset is not currently accessible from the public ElaadNL download page; the direct download exposed only a Charging Energy Hubs neighbourhood opportunity workbook. The PI supplied `reports/elaad_profile_generation_spec.md` for the ElaadNL Laadprofielengenerator route.
QUESTION: Should D-002 continue to target the old transaction dataset, or pivot to generated ElaadNL profile libraries?
OPTIONS: A) Keep searching for the old transaction dataset - E2.S1 remains blocked on access/licensing.  B) Use the Laadprofielengenerator route - E2.S1 can proceed with API-probe metadata, generated-profile manifests, and explicit terms-of-use notes.
RECOMMENDATION: B, because it gives accessible Dutch Outlook-based, seeded, 15-minute EV profiles now while preserving provenance and reproducibility.
STATUS: resolved by EV-001 in `registers/DECISIONS.md`; Agent C should implement a one-profile API probe before bulk generation and keep generated-profile redistribution terms as an open verification item.

## Q-3 - E2.S1 - 2026-07-10 - BLOCKING: yes
CONTEXT: EV-001 resolves the old D-002 ElaadNL transaction-data access issue, but it does not resolve the Cicenas 2025 thesis source URL/file or reuse terms for D-008. The literature review keeps Cicenas as a verified anchor, but E2.S1 still needs source/license evidence before extraction or manuscript use.
QUESTION: Should Agent C keep D-008 as a no-extraction proposed row until PI supplies/approves the thesis source terms, or replace the unit-cost source before E2.S1 can be sign-off-ready?
OPTIONS: A) PI supplies or approves the Cicenas source URL/file and reuse terms - D-008 remains proposed with no extraction until approved.  B) PI replaces the unit-cost source with an alternative source that has explicit access and reuse terms - E2.S1 continues after register revision.
RECOMMENDATION: A, because the current literature-review anchor preserves the intended Dutch/Stedin context without inventing source terms.
STATUS: open