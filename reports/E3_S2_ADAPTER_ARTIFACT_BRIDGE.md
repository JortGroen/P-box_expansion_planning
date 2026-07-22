# E3.S2 Adapter Artifact Bridge

Task: E3.S2 IC-1 integration scaffolding.

Status: scaffold/readiness only. This packet adds a metadata-only bridge from
accepted component adapter artifacts into the IC-1 assembly registry. It uses
synthetic metadata and synthetic adapter outputs only. It does not load real E2
arrays, open EV held-out data, run E3.S2a held-out adequacy, run E3.S2b/E3.S3
threshold screens, evaluate events, compute `P(E)`, or produce manuscript
numbers. Q-5 is resolved by G0-A3, but this scaffold still does not authorize event-based scientific analysis.

## Purpose

The merged IC-1 registry can build an assembly plan from accepted skeletons.
The new bridge adds the step before that: future accepted baseline, EV, HP, and
PV adapter artifacts can be represented as manifestable metadata records and
converted into registry skeletons without touching their trajectory arrays.

## Bridge Checks

`AcceptedComponentAdapterArtifact` records carry:

- artifact, source, and member identity;
- component kind;
- covered IC-1 node IDs;
- common calendar ID and 900-second cadence;
- HP/PV shared weather-driver identity where required;
- manifestable provenance metadata.

`build_component_adapter_registry_from_artifacts(...)` rejects duplicate or
missing required component kinds, duplicate registry nodes, registry nodes with
no adapter-artifact coverage, unmanifestable provenance, non-900-second cadence,
and HP/PV weather-driver mismatch. It then builds a `ComponentAdapterRegistry`
whose manifest records the accepted artifacts used to create the IC-1 assembly
plan.

## Synthetic Harness

The tests build synthetic accepted artifacts for baseline, EV, HP, and PV,
construct a registry, generate synthetic adapter outputs, and route those
outputs through the existing registry-backed IC-1 aggregation helper. The result
is checked only for deterministic P/Q aggregation and metadata preservation; no
threshold, overload, event, probability, or manuscript-result metadata is
produced.

## Stop Conditions

Stop before real integration if any real component artifact is not accepted,
if source/member/calendar/node/weather metadata are missing or inconsistent, or
if the next step would open EV held-out data or produce event, threshold,
probability, capacity-screen, or manuscript results without satisfying the remaining integrated-analysis gates.

## No-Result Boundary

This packet creates no experimental result and therefore no runner manifest.
Any future evidence-producing run must use the project runner and manifest
mechanism.