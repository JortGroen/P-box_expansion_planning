# E3.S2 Registry-Output Readiness

Task: E3.S2 IC-1 integration scaffolding.

Status: scaffold/readiness only. This packet adds an array-free readiness record
for accepted registry-backed component adapter outputs before IC-1 aggregation.
It does not load real C-owned component arrays, open EV held-out data, run IC-2,
evaluate thresholds/events, compute `P(E)`, run E3.S2a/E3.S2b/E3.S3, or produce
manuscript numbers.

## Purpose

The accepted-artifact registry already validates that future baseline, EV, HP,
and PV artifacts share node, calendar, and HP/PV weather metadata. The added
registry-output readiness record closes the next integration gap: once adapters
emit normalized `ComponentAdapterOutput` values, their source/member/node,
calendar/status, CRN stream, and weather identity metadata are captured before
arrays are aggregated into net load.

## Boundary Checks

`validate_registry_adapter_output_readiness(...)` validates registry outputs
against the registry and `NetLoadRealizationContext`, then returns manifest-ready
metadata containing:

- registry id, node ids, planning year, time domain, and shared weather driver;
- the context aleatory identity used for CRN provenance;
- one record per component output with component id, kind, node id, source id,
  member id, stream id, weather id, artifact status, and calendar id;
- the existing real-component readiness status record.

The helper rejects stale component stream ids before aggregation, so a future
adapter cannot pass source/member checks while using outputs generated under a
different CRN stream. It also keeps HP/PV weather identity tied to the context.

## Synthetic Fixture

Tests use only synthetic baseline, EV, HP, and PV adapter outputs. The fixture
proves the manifest record is array-free and present in `NetLoadResult.metadata`
when registry-backed outputs are assembled.

## No-Result Boundary

This packet creates no experimental result and therefore no runner manifest.
Any future evidence-producing run must use the project runner and manifest
mechanism after the relevant C-owned artifacts, signed values, capacity
convention, and G2/A-013/G3 gates are in place.
