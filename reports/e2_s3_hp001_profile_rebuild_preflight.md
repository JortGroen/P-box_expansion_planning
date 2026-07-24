# E2.S3 HP-001 Profile Artifact Rebuild/Checksum Preflight

Status: proposed preflight template only; no HP profile artifact is generated or approved.

## Purpose

Future HP work will need a deterministic rebuild/checksum step for the HP-001 profile artifact. This packet defines the minimum metadata that must be present before that rebuild can run, so repeated artifact generation cannot start from unsigned values, missing source checksums, or mismatched HP/PV weather identity.

## What The Preflight Checks

- Final HP approval IDs: value column, denominator, GJ-to-TWh conversion, SFH/MFH split, 2035 adoption/electrification, A-016 scenario-source consistency, D-004 paired-weather acceptance, and cold-spell tolerances. These IDs must be real approval references, not template or stale strings such as `<future ...>`, `placeholder`, `proposed`, `pending`, `unsigned`, `TODO`, `TBD`, or `not-approved`.
- Source artifacts: D-003 When2Heat source, D-004 WEATHER-001 member artifact, and D-013 value-binding record each need path, SHA-256, data ID, and provenance.
- WEATHER-001 identity: HP and PV weather records must match on `shared_weather_driver_id`, `member_id`, source, content SHA-256, timestep count, and cadence.
- Output targets: the future profile artifact path, profile manifest path, checksum manifest path, 35,040 quarter-hour timesteps, 900-second cadence, four HP-001 components, and kW electric-power units.
- Explicit blocker IDs: any unresolved blocker keeps the preflight red.

## Runner Scaffold Added 2026-07-24

`data/get_hp_scaling.py --run-profile-rebuild-preflight` now consumes either the committed preflight template packet or a future direct signed preflight manifest. It writes `data/metadata/hp_scaling/hp001_profile_rebuild_runner_blocker_manifest.json` with request ID, input manifest path, byte size, SHA-256, blocker IDs, validator names, git/code identity, and non-claims.

The committed runner output is intentionally blocked because the current template still contains future approval placeholders, missing source artifact checksums, and non-matching placeholder HP/PV weather identities. A signed synthetic fixture can pass the runner in tests only, and the accepted state exposes the intended handoff metadata without creating a real HP profile artifact.
## Non-Claims

This packet does not create or approve executable annual HP TWh values, 2035 adoption/electrification/service fractions, D-004 paired-weather final acceptance, cold-spell tolerances, HP profile artifacts, net-load/event/`P(E)`, capacity screens, threshold analysis, manuscript numbers, or probability results.

## Reviewer Decision

Please review whether this is the right minimum preflight before future HP profile artifact rebuild/checksum automation is allowed to run after the remaining PI approvals are signed.

## Suggested STATUS update

E2.S3 HP remains readiness/scaffold. A proposed HP profile artifact rebuild/checksum preflight template now lists the signed approvals, source checksums, paired-weather identity, and output targets required before future HP artifact generation can run; annual HP values and final paired/cold-spell acceptance remain unsigned.
