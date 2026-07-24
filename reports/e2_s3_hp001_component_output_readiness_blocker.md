# E2.S3 HP-001 Component-Output Readiness Blocker Packet

Status: proposed blocker/preflight packet only; not executable.

## Purpose

Future IC-1 integration needs a compact HP-side manifest check that says whether a heat-pump component-output artifact is safe to consume. This packet defines that preflight surface without producing annual HP loads or approving any unsigned value.

## What The Packet Checks

- Final HP approval IDs: value column, denominator, GJ-to-TWh conversion, SFH/MFH split, 2035 adoption/electrification, A-016 scenario-source consistency, D-004 paired-weather acceptance, and cold-spell tolerances.
- HP output artifact metadata: path, SHA-256, 35,040 quarter-hour timesteps, and 900-second cadence.
- WEATHER-001 identity: HP and PV must expose identical `shared_weather_driver_id`, `member_id`, `source`, content SHA-256, timestep count, and cadence.
- Component traceability: the four HP-001 residential components remain separate as SFH/MFH crossed with space/DHW, with the approved When2Heat shape/COP column pairing.
- Explicit blocker IDs: any unresolved blocker keeps the preflight red.

## Non-Claims

This packet does not create or approve an HP profile artifact, executable annual HP TWh values, 2035 adoption/electrification/service fractions, D-004 paired-weather final acceptance, cold-spell tolerances, net-load/event/P(E), capacity screens, threshold analysis, manuscript numbers, or probability results.

## Reviewer Decision

Please review whether the listed blocker fields are the right minimum IC-1-facing HP preflight surface. All scientific/value choices remain unsigned until separate PI approval.
