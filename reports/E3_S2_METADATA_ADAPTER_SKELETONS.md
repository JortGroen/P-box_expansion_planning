# E3.S2 Metadata-Only Adapter Skeletons

Task: E3.S2 IC-1 integration scaffolding.

Status: scaffold/readiness only. This packet adds an array-free checklist layer
for future baseline, EV, HP, and PV real-component adapters. It uses only merged
readiness metadata and synthetic fixtures. It does not wire real E2 component
arrays, open EV held-out data, run E3.S2a held-out adequacy, run E3.S2b/E3.S3
threshold screens, evaluate events, compute `P(E)`, or produce manuscript
numbers. Q-5 is resolved by G0-A3, but this scaffold still does not authorize event-based scientific analysis.

## Purpose

The merged IC-1 contract can already consume `ComponentAdapterOutput` values.
The metadata skeleton added here sits one step earlier: it records whether each
future real adapter family is still scaffold-only or has an accepted source
artifact, which calendar and nodes it expects, and which blockers remain before
arrays may be consumed.

This is not an adequacy test and not a scientific input approval. It is a
reviewable preflight checklist for future adapter wiring.

## Current Skeleton Inputs

Future checklists should use the currently merged readiness artifacts as their
source handles:

| Component | Current metadata source | Skeleton status before acceptance |
|---|---|---|
| Baseline | E2.S5 baseline/diversity readiness and canonical calendar checks | `scaffold` |
| EV | E2.S2 EV integration readiness, candidate Set A/B metadata, EV-007A/A-014 allocation metadata | `scaffold` |
| HP | HP-001 residential route plus current HP route status | `scaffold` |
| PV/weather | WEATHER-001 and D-004 source/member-construction readiness status | `scaffold` |

Adoption and flexibility remain part of the broader IC-1 assembly plan, but the
real-component skeleton validator defaults to baseline, EV, HP, and PV because
those are the C-owned component arrays that must be accepted before real IC-1
integration.

## Validation Boundary

`ComponentAdapterSkeleton` records are required to be metadata-only and
manifestable. The validator enforces:

- one unique skeleton per required component family;
- `accepted`, `scaffold`, or `synthetic_fixture` artifact status only;
- non-empty source, member, calendar, and node metadata;
- exactly 900-second cadence for the current IC-1 scaffold;
- HP and PV skeletons both carry the same shared weather-driver identity;
- accepted skeletons do not retain unresolved blocking items.

The resulting readiness dictionary states `ready_for_real_arrays=True` only
when every required skeleton is accepted and none has blocking items.

## Stop Conditions

Stop before loading real arrays if any required skeleton is missing, still
scaffold/synthetic, has unresolved blockers, cannot prove the common 15-minute
calendar, or cannot pair HP/PV through one WEATHER-001 shared weather identity.
Stop as well if the next step would inspect EV held-out data or produce any
event, threshold, probability, or manuscript result without satisfying the remaining integrated-analysis gates.

## No-Result Boundary

This packet creates no experimental result and therefore no runner manifest.
It only adds validation logic and documentation for future adapter readiness.
Any future evidence-producing run must use the project runner and manifest
mechanism.
