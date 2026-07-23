# B-Owned Guard Surface Audit

Status: synthetic/scaffold-only audit after PR #188. This report does not run
real trajectories, estimate real `P(E)`, choose a capacity convention, sign
A-013 or G2 values, authorize G3, or produce manuscript numbers.

## Audited B-Owned Surfaces

The audit covered the B-owned modules that can create or validate p-box,
probability, decision, or vertex-related artifacts:

- `src/pbox.py`: synthetic/pre-G3 vertex p-box estimates and probability rows.
- `src/pbox_error.py`: synthetic output-error endpoint records and endpoint
  event-count probability estimates.
- `src/pbox_result_guards.py`: final-result prerequisite guard state.
- `src/pbox_reporting.py`: guarded p-box report and runner/report boundary
  payloads.
- `src/decision.py`: synthetic alpha/rho/deferral/VoI decision scaffolds.

## Ready Guardrails

The B-owned reporting boundary now requires paper-facing p-box probability and
paper-facing decision-result payloads to carry the same final-result guard:
G2 Tier-1 envelope approval, signed A-013 grid-error value, approved capacity
convention, nonempty capacity denominator provenance, and manifested
output-error endpoint records. Vertex-shortcut payloads additionally require G3
and rows generated in `G3_APPROVED` mode.

Serialized boundary payloads are validated after conversion to plain mappings.
The validator rejects missing guard fields, result-kind mismatches, collapsed or
invalid alpha-indexed probability rows, inconsistent paper-facing allowed flags,
missing endpoint records for paper-facing payloads, endpoint-record prerequisite
claims that do not match the actual payload, and vertex rows stripped of
G3-approved mode evidence.

`src/decision.py` does not currently expose a paper-facing serializer. Its
current outputs are synthetic dataclasses for alpha-star, rho-star, procurement,
deferral-horizon, and VoI scaffolds. The guarded report boundary is therefore
the B-owned route that future reporting or runner surfaces should use when a
decision result is to be presented outside synthetic tests.

## Remaining Blockers Outside This PR

Paper-facing use still depends on upstream artifacts and PI decisions:

- Agent A/C real runner integration must call the B-owned guarded boundary from
  their owned surfaces instead of serializing p-box rows directly.
- G2 must approve Tier-1 endpoint values and adequacy over the frozen domain.
- A-013 must be signed for the grid-error value/form used in a run.
- The capacity convention and denominator provenance must be approved and
  manifested.
- Real output-error endpoint records must be generated from validated loading
  trajectories before event detection.
- G3 must approve vertex shortcut use before endpoint-only vertex outputs are
  paper-facing.

Until those items exist, B-owned guard fixtures remain synthetic readiness
checks only.