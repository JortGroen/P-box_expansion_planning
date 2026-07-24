# E5 Alpha Report Guard Hardening

Agent: B
Task: E5 synthetic reporting guard hardening
Status: scaffold-only; no real P(E), manuscript numbers, or signed A-013/G2/G3/capacity assumptions.

## Scope

Tightened the generic alpha-indexed p-box probability-row guard so serialized report rows must be strictly increasing in alpha and must not include collapsed single-probability aliases. This supports future paper-facing report plumbing by failing closed when a table has been reordered, duplicated, or collapsed outside the lower/upper p-box contract.

## Non-Claims

- Does not compute real probabilities or inspect real E3 trajectories.
- Does not choose model-error values or capacity conventions.
- Does not approve G3 vertex shortcut use.

## Suggested STATUS Update

B-owned reporting guard readiness advanced: generic p-box probability-row validation now rejects broader collapsed probability aliases and requires strictly increasing alpha rows. Real result presentation remains blocked on signed G2, A-013, capacity provenance/convention, endpoint records, and G3 where applicable.
