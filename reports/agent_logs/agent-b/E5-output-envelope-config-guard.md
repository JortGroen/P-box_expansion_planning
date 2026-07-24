# E5 output-error envelope config guard

DID: Added fail-closed envelope/config metadata for G1-A2 output-error endpoint records. Manifest metadata now records A-013 and G2 approval/provenance IDs, capacity-convention linkage, exact lower/upper G1-A2 formula strings, loading-before-event application, arbitrary unknown dependence, forbidden independent error sampling, and forbidden probability widening. The guarded p-box/report boundary now rejects endpoint records missing or contradicting those fields.

VERIFIED: Focused p-box error/reporting/decision tests passed with 69 tests; `scripts/task.ps1 ownership` passed for 5 changed paths; `scripts/task.ps1 test-fast` passed with 611 passed, 2 skipped, 7 deselected; `git diff --check` passed.

OPEN: Real paper-facing use remains blocked on signed A-013 grid-error value/form, signed G2 Tier-1 endpoints, capacity convention/provenance, real endpoint records, A-016 scenario consistency, and G3 where vertex shortcuts are claimed.

NEXT: Open a focused PR for review. Future real runner records must populate these fields from signed manifest evidence rather than synthetic placeholders.