## 2026-07-24 00:00 - E6 - done
DID: Hardened synthetic guarded decision-report rows so serialized payloads reject broader collapsed probability aliases and require deterministic alpha/metric ordering. This keeps decision-layer report rows aligned with the alpha-indexed lower/upper p-box reporting contract.
VERIFIED: Focused decision-report tests plus ownership and fast validation recorded in the PR body.
OPEN: Real decision reporting remains blocked on signed G2, A-013, capacity convention/provenance, real endpoint records, and G3 where vertex output is claimed.
NEXT: After merge, future decision report emitters should keep rows sorted by `(alpha, metric_name)` before serialization.
