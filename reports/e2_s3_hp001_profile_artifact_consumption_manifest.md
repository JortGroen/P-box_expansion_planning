# E2.S3 HP001 Profile Artifact Consumption Manifest

## Purpose

This packet defines the metadata a future HP-001 profile artifact must carry before an integrated consumer may treat it as usable. It is a consumption guard only: it does not build HP loads, approve annual TWh values, or run paired-weather/cold-spell acceptance.

## Added Readiness Surface

- `src.hp_model.require_hp001_profile_artifact_consumption_manifest(...)` validates a future manifest before integrated HP use.
- The manifest must record the HP profile artifact path and SHA-256, 15-minute cadence, kW units, WEATHER-001 member identity, four HP-001 component traces, and signed approval IDs.
- Required approval IDs remain the full HP-001 final-readiness set: value column, denominator, unit conversion, SFH/MFH split, adoption/electrification, A-016 scenario-source consistency, D-004 paired-weather acceptance, and cold-spell tolerances.
- `data/metadata/hp_scaling/hp001_profile_artifact_consumption_manifest_template.json` is a proposed template, not an accepted artifact.

## Non-Claims

- No annual HP TWh values are executable.
- No 2035 HP adoption/electrification value is signed.
- No D-004 final paired-weather acceptance or cold-spell tolerance is signed or run.
- No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability result is produced.

## Reviewer Focus

Check that the validator is metadata-only, fail-closed, and strict enough that future HP profile artifacts cannot be consumed without both signed value binding and signed weather/cold-spell approvals.
