# Final-Result Guardrails For B-Owned Outputs

Status: scaffold-only guard packet. This report records checks for paper-facing p-box probabilities, decision outputs, and vertex-shortcut outputs. It does not run real E3 trajectories, estimate real `P(E)`, choose a capacity convention, sign A-013/G2 values, authorize G3, or produce manuscript numbers.

## Purpose

B-owned synthetic math code can produce valid-looking p-box and decision artifacts before the scientific prerequisites for paper-facing use are complete. The guard API in `src/pbox_result_guards.py` makes that boundary explicit: a result may be marked paper-facing only when the required model-error, capacity, and vertex prerequisites are supplied as explicit booleans/provenance rather than implied by the existence of a synthetic artifact.

## Required Prerequisites

For paper-facing p-box probabilities and decision results, the guard requires:

- G2 Tier-1 envelope/adequacy approval;
- signed numerical A-013 grid-error value;
- approved capacity convention;
- nonempty capacity denominator provenance;
- manifested output-error endpoint event records, so probabilities/CIs come from endpoint event counts rather than post-hoc probability widening.

For paper-facing vertex-shortcut outputs, the guard additionally requires G3 vertex-shortcut approval. Until G3 is signed, vertex output remains synthetic/pre-G3 or must be replaced by the approved interior-sampling path for paper-facing work.

## Reporting Shape

Paper-facing probability tables must remain alpha-indexed lower/upper p-box rows. The guard rejects collapsed fields such as `defuzzified_probability` or `p_hat`, missing lower/upper confidence fields, duplicate alpha rows, and `p_lower > p_upper`. This preserves the project rule that results are reported as alpha-indexed lower/upper bounds, never a single defuzzified probability.

## Remaining Blockers

This guard does not satisfy the blockers itself. It only makes them executable for B-owned outputs. Real paper-facing use still needs signed G2, signed A-013, the capacity convention/provenance decision, manifested output-error endpoint records from real validated trajectories, and G3 before any vertex shortcut is presented as scientific output.