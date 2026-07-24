# E2.S4 D-014 PV Component-Output Runner Preflight

Date: 2026-07-24
Agent: C.PV/weather
Task ID: E2.S4 / D-014 / PV component-output runner readiness

## Purpose

This packet adds the PV-owned runner/preflight boundary for future first-experiment PV component-output artifacts. It turns the existing D-014 value-approval packet and PV component-output scaffold into deterministic automation that either blocks with explicit reasons or, once all signed artifacts exist, can write an IC-1-compatible PV component-output NPZ/manifest.

## Current Main Behavior

With the committed D-014 packets on main, the runner emits `blocked_no_pv_component_output` and writes no arrays. The blocker manifest records the checksums of the D-014 value-approval packet and component-output scaffold and lists the missing signed artifacts for capacity/growth, statistical orientation/tilt, PV conversion/loss/temperature/clipping, node allocation, reactive-power policy, manifest path/checksum policy, A-016 scenario consistency, and final paired HP/PV weather acceptance.

## Synthetic Fixture Path

A tiny synthetic signed-fixture path is included for regression testing only. It requires explicit `synthetic_fixture` status, signed-fixture approval IDs, source/checksum metadata, safe repository-relative paths, WEATHER-001 identity agreement, and IC-1 loader validation. It is not a PV scientific result and does not authorize real PV output.

## Guardrails

The preflight rejects unsigned/proposed/stale/template approvals, missing source checksums, unsafe absolute or traversal paths, missing allocation, premature accepted status, WEATHER-001 identity mismatch, and any roof/building/3DBAG/PV-map geometry hook in the first-experiment path. PV-ORIENT-001 remains statistical/typical only.

## Non-Claims

This work does not approve PV capacity, II3050 growth, orientation/tilt weights, conversion formulas, losses, temperature or clipping values, reactive-power policy, node allocation, final paired HP/PV acceptance, real PV generation, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, or manuscript numbers.
