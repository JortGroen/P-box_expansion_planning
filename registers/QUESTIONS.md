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

## Q-4 - E5.S3.T1 - 2026-07-14 - BLOCKING: yes
CONTEXT: G1-A1 supersedes PR #13's probability-margin widening. E5.S3 now needs output-domain model-error propagation: loading trajectories are interval-widened before the G0-A1/G0-A2 four-step event detector, while the import/export gate uses the unwidened `P_net` sign. This requires a small IC-2/IC-3 schema change before Agent A implements the evaluator side or Agent B implements p-box propagation.
QUESTION: Which minimal IC-2/IC-3 schema should be approved for output-domain model-error propagation?
OPTIONS: A) Minimal trajectory-result schema. IC-2 returns a structured `LoadingTrajectoryResult` with `p_net_kw[t]`, `import_loading_pu[t]`, `export_loading_pu[t]`, `screening_loading_pu[t]`, `import_mask[t]`, `export_mask[t]`, `time_index`, and diagnostic `overload` fields computed without widening. IC-3 consumes that result plus an explicit `LoadingErrorEnvelope` carrying signed envelope metadata: `basis` (`additive_pu`, `relative_fraction`, or future compatible basis), lower/upper endpoint functions or constants, symmetry/asymmetry/one-sided metadata, source labels (`epsilon_grid`, `epsilon_tier1`, `epsilon_total`), and domain tags. IC-3 applies the envelope only to loading magnitudes on the already-unwidened direction masks, then runs the four-step detector separately on lower and upper trajectories. Lower/upper probabilities and MC CIs come only from lower/upper event counts. CRN seeds and sample ordering are unchanged.  B) Evaluator-owned envelope schema. IC-2 accepts an optional approved `LoadingErrorEnvelope` and returns lower/upper event booleans/count-ready indicators directly, while IC-3 only aggregates counts. This hides less math in B's module but couples Agent A's evaluator to E5 p-box semantics and makes later asymmetric/one-sided sensitivity handling harder to audit from IC-3.
RECOMMENDATION: A, because it is the smallest cross-agent change that keeps Agent A responsible for physics-facing trajectories and direction masks, keeps Agent B responsible for p-box/event-count propagation, supports additive, relative, symmetric, asymmetric, and one-sided envelopes without another interface redesign, forbids probability-margin shifting, and gives Agent A a concrete review target before implementation.
STATUS: open; Agent A review requested for the IC-2 fields, direction-mask semantics, units, and feasibility of returning the proposed trajectory result without B editing Agent A-owned modules.
