# E5 selective-AC report-boundary guard

DID: Added a synthetic-only report-boundary guard that accepts selective-AC promotion metadata only when the guarded p-box payload also carries validated output-error endpoint records. The validator now checks matching alpha grids, matching sample counts, candidate sample-index references, and lower/upper endpoint event consistency without executing AC or approving any G2 promotion rule.

VERIFIED: `tests/test_pbox_reporting.py` passed with 36 tests; `scripts/task.ps1 ownership` passed for 3 changed paths; `scripts/task.ps1 test-fast` passed with 597 passed, 2 skipped, 7 deselected; `git diff --check` passed.

OPEN: Real selective-AC use remains blocked on signed G2 Tier-1 endpoints, signed A-013 grid-error value/form, capacity convention/provenance, real endpoint records, and any PI-approved selective-AC promotion rule.

NEXT: Open a focused PR for review and keep downstream runner/report integration synthetic until upstream gates are signed.