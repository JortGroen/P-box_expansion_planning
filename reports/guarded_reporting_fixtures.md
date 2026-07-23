# Guarded Reporting Fixtures For B-Owned P-Box Outputs

Status: scaffold-only. This packet wires the final-result guards into a future
report/runner-facing record shape using synthetic p-box fixtures only.

## Purpose

The project now has executable final-result guards for p-box probabilities,
decision results, and vertex-shortcut outputs. The next risk is a reporting or
runner surface bypassing those guards by directly serializing a valid-looking
p-box table. The `src.pbox_reporting` scaffold closes that route for B-owned
outputs: a report record carries the alpha-indexed probability rows, the guard
decision, and, for paper-facing mode, a manifested output-error endpoint record.

## Enforced Shape

The reporting scaffold preserves alpha-indexed lower/upper probability rows
with separate confidence intervals. It rejects collapsed fields such as `p_hat`
or `defuzzified_probability`. If a record is marked `paper-facing`, it must pass
the prerequisite guard and include an output-error endpoint record whose
`probability_widening` field is exactly `forbidden`.

For vertex-shortcut reports, paper-facing mode also requires rows generated in
`G3_APPROVED` vertex mode. Pre-G3 synthetic vertex rows can still be serialized
for synthetic tests, but the scaffold refuses to present them as paper-facing
even if a caller supplies complete-looking prerequisites.

## What This Does Not Decide

This scaffold does not run real E3 trajectories, estimate real `P(E)`, sign the
G2 Tier-1 envelope, sign A-013 grid-error values, choose a capacity convention
or denominator, authorize G3, or produce manuscript numbers. It only makes the
missing prerequisites visible at future report/runner boundaries.

## Synthetic Fixtures

The tests use hand-built p-box rows and a minimal synthetic endpoint-count
record. They verify blocked synthetic serialization, paper-facing rejection
when prerequisites or endpoint records are absent, acceptance when all guard
inputs are explicitly supplied, and rejection of pre-G3 vertex rows in
paper-facing mode.

## Runner/Report Boundary Payload

`build_runner_report_boundary_record` adds a named `guarded-pbox-report-v1`
payload around the guarded p-box report. Future runner or report code can emit
this stable record instead of serializing p-box rows directly. The payload keeps
whether paper-facing output was requested, whether it was allowed, the complete
guard decision, the alpha-indexed rows, and any endpoint-count record together.

The synthetic tests deliberately try to bypass the boundary by omitting G2,
A-013, capacity provenance, output-error endpoint records, or G3 for vertex
outputs. Those paper-facing attempts fail before a boundary payload can be
emitted. Synthetic-only payloads remain allowed so fixtures can document the
blocked state without becoming paper results.
## Serialized Payload Validation

`assert_runner_report_boundary_payload` validates the mapping produced by the
boundary record after serialization. This matters because future runner/report
code may handle dictionaries rather than Python dataclasses. The validator
rejects payloads that drop the guard, lie about `paper_facing_allowed`, request
paper-facing output without endpoint records, tamper with guard allowed/missing
prerequisite consistency, or strip G3-approved vertex-mode evidence from vertex
rows.

These checks are still synthetic guard fixtures. They do not create real result
manifests, run integrated trajectories, compute `P(E)`, choose capacity
conventions, or approve G2/A-013/G3.
## Fast/Full Validation Policy

After the fast/full validation policy update, these guard fixtures remain in the
fast PR suite because they are deterministic, synthetic, and do not run external
or slow adapter paths. Focused guard tests plus `scripts/task.ps1 test-fast` are
the default PR evidence. Full validation remains available for gate artifacts,
first real experiments, slow-marked checks, or explicit PI requests.

The serialized boundary validator also cross-checks endpoint-record claims: a
payload whose guard says endpoint records are manifested must actually include
an `output_error_record`, and a payload that includes endpoint records cannot
keep the guard prerequisite marked absent. This makes endpoint-record presence a
structural property of the future report boundary rather than a nearby note.