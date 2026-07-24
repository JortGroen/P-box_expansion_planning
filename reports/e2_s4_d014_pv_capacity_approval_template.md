# E2.S4 D-014 PV Capacity Approval Template

## Why this exists

PR #230 prepares the PI-facing value-choice recommendation for the D-014 CBS Alkmaar anchor plus II3050 growth route. This follow-up keeps momentum by defining the fail-closed shape of the future signed PV capacity artifact, without approving or calculating any installed-capacity value.

## What the template requires later

The proposed `D014-PV-CAPACITY-APPROVAL-TEMPLATE` requires a later signed artifact to record:

- artifact identity: signed decision ID, approval status, and link back to `D014-PV-CAPACITY-VALUE-CHOICE-PACKET`;
- capacity value: numeric installed capacity, unit, DC/AC convention, scope, and planning year;
- CBS operand: table `85005NED`, Alkmaar `GM0361`, period, sector/category, capacity field, selected anchor value, evidence metadata checksum, and raw bundle checksum;
- II3050 operand: evidence packet, raw/source checksums, scenario column, numerator year, denominator/crosswalk, formula, and growth-factor value;
- A-016 scenario consistency: explicit mapping across EV, HP, and PV scenario labels before integrated use;
- dependencies: node allocation, signed statistical orientation/tilt distribution, and `PV-PARAM-001` or an amended signed conversion decision;
- audit outputs: content checksum, source metadata checksums, non-claims, and blockers.

## Recommendation

Use this template as the contract for the future signed capacity artifact rather than mutating retrieved evidence or the value-choice packet after PI approval. The recommended label before PV-PARAM signoff remains `installed_capacity_kwp_dc`, but this PR does not approve that convention.

## Non-claims

This packet approves no PV capacity value, CBS row, II3050 scenario, growth factor, DC/AC convention, node allocation, orientation/tilt values, PV-PARAM conversion, PV generation, net-load/event analysis, `P(E)`, threshold analysis, capacity screen, manuscript number, roof/building/3DBAG/PV-map workflow, or final paired HP/PV acceptance.

## Validation

Completed on this branch: focused PV/data-source/methods tests passed; `scripts/task.ps1 ownership` passed; `git diff --check` passed; `scripts/task.ps1 test-fast` passed with 622 passed, 1 skipped, and 7 deselected.
