# PI Dashboard Cache

Status: maintainer convenience cache; explicitly non-authoritative.
Last protocol update: 2026-07-22.

Use this file to reduce repeated Codex context and tool-output costs during PI
coordination. If this cache conflicts with live GitHub state, `registers/*`, or
the project plans, the live authoritative source wins.

Never use this cache alone to approve gates, settle scientific decisions,
resolve PR conflicts, or quote manuscript numbers. In those cases it is only an
index: inspect the current authoritative registers, plans, PR evidence, and
manifests before advising the PI.

## PI Lite Default

For routine questions such as "what next?", "what gates are open?", PR triage,
or agent coordination, use PI Lite unless the PI explicitly asks for a full
audit.

Standing PI preference: the dashboard assistant reviews open PRs for the PI and
presents only merge recommendations, blockers, and items that genuinely need PI
scientific or governance judgment.

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
  data source, manuscript claim, or manuscript number.
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

## Current Decision Notes

- `G0-A3` resolves Q-5. The primary event threshold is strict `L_import > 1.0
  p.u.` for four consecutive 15-minute import steps over the full planning
  year. Persistent-event sensitivities at `1.1` and `1.2 p.u.` are predeclared;
  no separate 1.0-1.1 cumulative-exposure rule is primary. Event analysis still
  needs all other gates, signed values, manifests, and capacity conventions.
- `EV-008` is superseded. `EV-008A` approves equal-mix capacity-stratified
  public Set B source generation only: uncontrolled ElaadNL public `cp`, fixed
  generator year 2030, native public car/van mix, 25% each for AC capacity
  classes 11/13/15/22 kW, candidate `M=1200`, held-out `H=400`, no public smart
  charging, no held-out adequacy use, and no integrated analysis.
- `HP-001` is approved. D-003 When2Heat is approved for first-pass internal
  Dutch residential HP shape/COP source use covering SFH/MFH space heat with
  ASHP radiator COP plus SFH/MFH domestic hot water with ASHP water COP.
  Commercial heat, local annual HP scaling, WEATHER-001 implementation over
  accepted D-004 members, paired-weather acceptance, cold-spell tolerances,
  event analysis, and manuscript results remain separate blockers.
- A confidential student thesis supplied privately by the PI is available only
  as a source-discovery aid for HP/local residential-demand work. Do not
  commit, quote, cite, or use thesis-specific values as provenance. C.HP may
  use `reports/e2_s3_hp_private_thesis_source_discovery_note.md` to guide
  checks of underlying public sources such as local gas demand, dwelling stock,
  BAG/CBS/DEGO-like evidence, and standard load-profile references.
- `D-013` is approved as a retrieval/checksum route for HP-001 Alkmaar local
  scaling evidence. C.HP may retrieve and checksum CBS 85035NED, PBL
  Startanalyse 2025 Alkmaar, and CBS 85523NED under `data/raw/hp_scaling/` and
  `data/metadata/hp_scaling/`. Annual HP TWh values, 2035 HP adoption, D-004
  acceptance, paired-weather acceptance, net-load/event analysis, and
  manuscript results remain unsigned.
- `WEATHER-001` resolves Q-8. HP and PV must use one neutral shared weather
  contract in `src/weather_model.py` / `tests/test_weather_model.py`, now owned
  by Agent C. This approves the interface route only; D-004 source acceptance,
  completeness checks, cold-spell tolerances, paired-weather acceptance
  results, net-load/event analysis, and manuscript results remain blocked.
- `D004-MC-001` is approved. Agent C may implement the D-004 member builder for
  the approved 2014-2023 Alkmaar/Berkhout KNMI/PVGIS bundle using UTC-year
  15-minute members, derived Europe/Amsterdam timestamps, KNMI `T/10`, and
  energy-preserving repeated KNMI `Q` as GHI. D-004 source acceptance, final
  completeness tolerances, HP/PV paired acceptance, net-load/event analysis,
  and manuscript results remain separate blockers.
- `E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN` is approved as a design, with numerical
  tolerances still pending. The future HP/PV acceptance report must check both
  coldest-window behavior and near-freezing/defrost-risk behavior around
  0 degrees C; the exact near-freezing band is not signed yet.
