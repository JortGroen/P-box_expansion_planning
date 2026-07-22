# E3.S2 IC-1 Assembly Plan Readiness

Task: E3.S2 IC-1 integration scaffolding.

Status: scaffold/readiness only. This packet adds the next metadata layer after
the adapter skeleton checklist: an accepted-metadata registry that can build an
auditable IC-1 assembly plan and validate synthetic adapter outputs before
aggregation. It does not wire real E2 arrays, open EV held-out data, run
E3.S2a held-out adequacy, run E3.S2b/E3.S3 threshold screens, evaluate events,
compute `P(E)`, or produce manuscript numbers. Q-5 remains a hard stop before
event-based scientific analysis.

## Purpose

The merged skeleton checklist can say whether baseline, EV, HP, and PV adapter
metadata is accepted or still blocked. The new registry layer uses only
accepted skeleton metadata to produce a node-ordered `NetLoadAssemblyPlan` and
a manifestable checklist record.

This gives future real-component work a small, auditable handoff:

1. C-owned component artifacts become accepted by their own governance route.
2. Agent A records their IC-1 metadata as accepted skeletons.
3. The registry turns those skeletons into an assembly plan.
4. Adapter outputs are checked against the registry before IC-1 sums P/Q.

## Registry Checks

`ComponentAdapterRegistry` requires:

- one accepted skeleton for each required real component family;
- one explicit IC-1 node order;
- every skeleton node to appear in that node order;
- one common calendar ID and 900-second cadence inherited from the skeleton
  validator;
- one shared HP/PV weather-driver identity;
- manifestable mapping/version metadata.

`assemble_net_load_from_registry_outputs(...)` then checks that adapter outputs
match the registry before aggregation:

- output kind appears in the registry;
- output node appears in that component's skeleton;
- source ID and member ID match the accepted metadata;
- artifact status and calendar ID match the accepted metadata;
- the registry weather identity matches the realization context.

## Synthetic End-To-End Harness

The tests use synthetic accepted metadata and four synthetic adapter outputs:
baseline and EV positive demand on `node-a`, HP positive demand on `node-b`,
and PV negative generation on `node-b`. The helper combines them through the
same IC-1 net-load path used by future adapters and verifies that no threshold,
overload, or probability metadata is produced.

## Stop Conditions

Stop before real integration if any real component artifact remains scaffold or
synthetic, if the registry cannot prove one calendar and HP/PV weather member,
if output metadata drifts from accepted skeleton metadata, or if the next step
would inspect EV held-out data or produce event, threshold, probability, or
manuscript results while Q-5 is unresolved.

## No-Result Boundary

This packet creates no experimental result and therefore no runner manifest.
It adds validation logic and synthetic-only tests for future IC-1 readiness.
Any future evidence-producing run must use the project runner and manifest
mechanism.
