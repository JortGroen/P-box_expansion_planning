# E3.S2 Loading-Input Readiness

Task: E3.S2 IC-1 integration scaffolding.

Status: scaffold/readiness only. This packet validates synthetic accepted
adapter artifacts and synthetic adapter outputs up to the net-load/loading-input
handoff. It does not load real component arrays, open EV held-out data, run
E3.S2a adequacy, run E3.S2b/E3.S3 threshold screens, evaluate events, compute
`P(E)`, or produce manuscript numbers. Q-5 remains a hard stop before
event-based scientific analysis.

## Purpose

The merged adapter-artifact bridge can create an IC-1 assembly registry from
accepted metadata. The new loading-input readiness layer checks that a
registry-backed synthetic `NetLoadResult` is suitable to hand to a future IC-2
loading evaluator, without actually invoking IC-2.

## Boundary Checks

`NetLoadLoadingInputReadiness` and
`prepare_loading_input_from_registry_outputs(...)` validate:

- required baseline, EV, HP, and PV accepted artifact metadata through the
  existing artifact bridge;
- node coverage and node order through the registry;
- source/member/calendar/artifact metadata through the registry-backed output
  checks;
- HP/PV paired weather identity through the registry and realization context;
- a common 2035 timestamp axis at 900-second cadence;
- manifest-ready registry, realization-context, component-provenance, node, and
  weather metadata.

The readiness manifest deliberately excludes threshold, overload, event,
probability, capacity-screen, and manuscript-result fields.

## Synthetic Fixture

The tests use a four-step 2035 synthetic calendar and synthetic baseline, EV,
HP, and PV outputs. This is a minimal contract fixture, not a real full-year
scientific input. Full-year real component use remains blocked until the owning
C artifacts are accepted and downstream Q-5-dependent criteria are resolved.

## Stop Conditions

Stop before real integration if any required component artifact is missing or
not accepted, if metadata cannot prove one 2035 calendar and one HP/PV weather
identity, if a future step would open EV held-out data, or if the next step
would run event, threshold, probability, capacity-screen, or manuscript-number
analysis while Q-5 is unresolved.

## No-Result Boundary

This packet creates no experimental result and therefore no runner manifest.
Any future evidence-producing run must use the project runner and manifest
mechanism.