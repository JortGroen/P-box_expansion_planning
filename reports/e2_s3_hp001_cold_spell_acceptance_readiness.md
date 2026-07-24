# E2.S3 HP-001 Cold-Spell Acceptance Readiness

Status: proposed readiness scaffold only; no D-004 paired/cold-spell acceptance is signed or run.

## Practical PI Question

Before HP profiles can be accepted with D-004 weather for integrated analysis, which cold-spell tolerance set should turn diagnostics into pass/fail evidence? The packet offers three choices: keep only the fixture-runner structure, sign explicit numerical tolerances, or amend/escalate the tolerance design.

## What This Enables

The HP scaffold now separates three gates that are easy to blur: D-004 source/member identity, paired HP/PV WEATHER-001 equality, and numerical cold-spell tolerances. The runner refuses mismatched HP/PV weather identity and refuses blank `cold_spell_tolerances` approval IDs before producing pass/fail diagnostics.

Diagnostics cover coldest rolling 3-day and 7-day windows, HP peak inside/outside those windows, COP behavior, and near-freezing behavior around 0 degrees C for ASHP defrost-risk review. Unit tests use synthetic fixture data only.

## What Remains Blocked

Annual HP TWh values and 2035 adoption/electrification remain unsigned. Real D-004 paired-weather acceptance, cold-spell numerical tolerances, A-016 scenario consistency for an integrated case, net-load/event/P(E), threshold runs, capacity screens, and manuscript-result analysis remain out of scope.

## Evidence

- Metadata packet: `data/metadata/hp_scaling/hp001_d004_cold_spell_acceptance_decision_packet.json`
- Scaffold code: `src.hp_model.ColdSpellAcceptanceTolerances` and `src.hp_model.evaluate_hp001_cold_spell_acceptance`
- Same-ID methods paragraph: `E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN`

## Suggested STATUS update

E2.S3 HP-001 remains in readiness/value-binding preparation. Cold-spell and paired-weather acceptance now have a fixture-only fail-closed runner and PI tolerance decision packet; real acceptance, annual HP values, and integrated analysis remain blocked pending signed choices.
