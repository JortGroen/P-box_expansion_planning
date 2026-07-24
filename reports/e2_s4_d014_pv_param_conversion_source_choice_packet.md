# E2.S4 D-014 PV-PARAM Conversion Source Choice Packet

## Why this exists

The PI flagged the simple `PR = 0.86` / direct-GHI route as not yet satisfactory for executable PV. This packet turns that concern into a reviewable, fail-closed choice layer without approving a formula or value.

## What it proposes

- `pvlib_statistical_orientation_tilt_poa_candidate`: preferred candidate if the PI signs statistical orientation/tilt values plus transposition/decomposition/albedo/loss/temperature/clipping choices.
- `pvgis_reference_calibration_sanity_candidate`: qualitative seasonal/peak sanity and provenance context only; not a realized sampled weather path.
- `direct_ghi_pr_scalar_candidate`: disputed fallback only if explicitly signed as a first-screen simplification.

## Boundaries

D-014 capacity remains separate under PV-CAP-001. PV-ORIENT-001 remains statistical-only with no roof/building/3DBAG/PV-map extraction before the first experiment. A-016 scenario consistency, node allocation, and final paired HP/PV acceptance remain blockers.

## PI approvals still needed

The packet lists approval keys for the conversion formula, irradiance basis, signed orientation/tilt packet, transposition or direct-GHI simplification, diffuse decomposition, albedo, losses/performance ratio, temperature treatment, clipping/capacity convention, PVGIS sanity tolerance, D-014 capacity artifact, allocation, and A-016 mapping.

## Validation

Completed on this branch before PR: focused PV/data-source/methods tests passed with 123 passed; `scripts/task.ps1 ownership` passed; `git diff --check` passed; `scripts/task.ps1 test-fast` passed with 665 passed, 1 skipped, and 7 deselected.