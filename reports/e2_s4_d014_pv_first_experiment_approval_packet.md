# E2.S4 D-014 First-Experiment PV Approval Packet

## Why this exists

PV/weather now has source/member readiness and several fail-closed D-014/PV-PARAM packets, but executable first-experiment PV still needs PI decisions across separate layers. This packet gives the PI one checklist without collapsing those decisions into a silent default.

## What it separates

- Installed capacity: D-014/PV-CAP route only; CBS row/value, II3050 growth factor, and DC/AC convention remain unsigned.
- Orientation/tilt: PV-ORIENT-001 statistical route only; source, bins, representative angles, weights, and weighting convention remain unsigned.
- Conversion/PV-PARAM: formula remains unsigned; pvlib/POA, direct-GHI, losses, temperature, clipping, and capacity convention require explicit signoff.
- Node allocation: separate future rule; no per-node shares or building/roof allocation are introduced here.

## First-experiment boundary

The packet preserves the lightweight PV-ORIENT-001 scope: typical/statistical orientation and tilt only. Building-, roof-, location-level, 3DBAG, and PV-map geometry remain deferred improvements after the first real experiment unless a later signed scope change says otherwise.

## Executable gate

Executable PV generation remains blocked until signed capacity, signed statistical distribution, signed conversion parameters, A-016 scenario consistency, signed node allocation, and final paired HP/PV acceptance exist. If invoked before then, the intended result is an abort with blocker IDs, not a PV output.

## Validation

Completed on this branch before PR: focused PV/data-source/methods tests passed with 130 passed; `scripts/task.ps1 ownership` passed; `git diff --check` passed; `scripts/task.ps1 test-fast` passed with 688 passed, 1 skipped, and 7 deselected.