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

## Q-3 - E2.S1 - 2026-07-10 - BLOCKING: no
CONTEXT: Agent C escalated D-008 because the Cicenas 2025 thesis source file and reuse terms were not visible in the Agent C worktree. The PI has already supplied the thesis as a local raw PDF in the PI worktree, and the thesis professor is involved in the project.
QUESTION: Can Agent C use the Cicenas thesis as the unit-cost source for extraction?
OPTIONS: A) Use the PI-supplied local thesis PDF under strict traceability/no-redistribution rules.  B) Replace the unit-cost source with another openly licensed source.
RECOMMENDATION: A, because the source is project-approved and preserves the Dutch/Stedin context, provided every extracted number is exactly traceable.
STATUS: resolved by COST-001 in `registers/DECISIONS.md`; source access is resolved, but extracted values remain unsigned until recorded with page/table provenance and PI sign-off.

## Q-4 - E9.S5a/A-013 - 2026-07-14 - BLOCKING: no
CONTEXT: A symmetric relative grid-error form is approved, but the candidate 5% reference and 2%/10% sensitivities are not empirically established for an uncalibrated DSO planning model. A detailed measurement-informed feeder study reports approximately 5% agreement under stronger conditions, while model-quality literature gives no universal transferable percentage.
QUESTION: Does primary evidence support a numerical A-013 envelope under a sufficiently comparable DSO model boundary, or must 5% remain an author-specified sensitivity scenario?
OPTIONS: A) Sign a sourced value only after E9.S5a documents a comparable quantity, conditioning, measurements, domain, and enclosure meaning.  B) Retain 5% with 2%/10% as explicitly author-specified scenarios and state that no empirical enclosure was available.
RECOMMENDATION: A if comparable evidence is found; otherwise B is more defensible than converting a mechanism inventory into a false empirical claim.
STATUS: open; does not block model/data integration, but blocks numerical A-013 sign-off and manuscript claims that 5% is scientifically established.

## Q-5 - E7.S1 - 2026-07-14 - BLOCKING: yes
CONTEXT: Agent B implemented the finite DFMP probability-to-possibility transform from the verified D-009 primary citation and added independent tests for normalization, event domination, ordering, ties, boundary cases, invalid input, and determinism. The workspace contains the bibliographic source but not the primary paper text or its exact worked example, so the E7.S1 acceptance test cannot honestly claim reproduction of a published example.
QUESTION: Can the PI provide the Dubois-Foulloy-Mauris-Prade (2004) primary paper pages containing a worked probability-to-possibility example, or approve a specific primary-source example to use instead?
OPTIONS: A) Provide/approve the exact primary worked example - Agent B can add the acceptance test and mark E7.S1 complete if it passes.  B) Keep E7.S1 blocked after the defensible implementation - no published-example acceptance claim is made, and downstream E7.S2 waits for verified example provenance.
RECOMMENDATION: A, because the implementation is small and testable, but E7.S1's plan-level acceptance criterion explicitly requires a published-example match.
STATUS: open
