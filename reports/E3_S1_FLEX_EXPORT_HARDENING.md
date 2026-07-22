# E3.S1 Flex Export Hardening

Task: E3.S1 flexibility aggregator scaffold.

Status: scaffold-only hardening. This change tightens the flexibility eligibility
boundary so PV/export/generation-labeled components are never reduced, even if a
future adapter accidentally marks them as import-controllable.

## Purpose

FLEX-001 is still proposed, but the scaffold must already protect the core
boundary: demand-side controllability applies only to import-side demand loads.
The previous implementation reduced only positive kW values, which protected
negative export trajectories, but a positive-valued component labeled `pv` or
`export` and incorrectly marked controllable could still be reduced. This packet
closes that adapter-integration failure mode.

## Boundary

The aggregator remains deterministic and trajectory-preserving. Optional
`shift_to_adjacent` rebound remains a scaffold mechanism only. This report does
not approve FLEX-001, choose a flexibility model, run IC-1/IC-2, evaluate
thresholds/events, compute `P(E)`, or produce manuscript numbers.

## Verification

Synthetic tests cover PV/export-labeled components marked controllable and prove
that their original trajectories, including positive values, remain unchanged.
