# E2.S3 HP-001 Component-Output Runner Readiness

Protocol ID: `E2-S3-HP001-COMPONENT-OUTPUT-RUNNER-READINESS`

Status: proposed runner scaffold only; real HP component outputs remain blocked.

## Why This Exists

IC-1 will eventually need an HP component-output manifest that is safe to load without re-litigating every HP source and weather gate. This runner automates the HP-side preflight before any such artifact can be consumed. It turns the existing HP readiness packet into a deterministic blocker manifest instead of relying on manual checklist reading.

## What The Runner Checks

- Signed HP-001 approval IDs for value column, denominator, GJ-to-TWh conversion, SFH/MFH split, 2035 adoption/electrification/service fraction, A-016 scenario consistency, D-004 paired-weather acceptance, and cold-spell tolerances.
- D-003, D-004, and D-013 source artifact records with concrete path, SHA-256, data ID, and provenance.
- Exact HP/PV WEATHER-001 identity equality: `shared_weather_driver_id`, `member_id`, source, content checksum, timestep count, and cadence.
- Four separate HP-001 component traces: SFH/MFH crossed with space/DHW, preserving approved When2Heat shape and COP columns.
- Unsafe/stale approval or template tokens in approvals, artifact paths, weather identity, and component scaling provenance.
- Premature accepted-artifact status claims in the scaffold.

## Current Output

The committed runner result is `data/metadata/hp_scaling/hp001_component_output_runner_readiness_blocker.json`. Current main remains blocked: no real component output is written, the committed readiness template still contains placeholder approval/artifact/weather fields, and D-003/D-004/D-013 source artifact records for this future handoff are not yet signed as executable component-output inputs.

## Synthetic Fixture Boundary

Focused tests can pass a fully signed synthetic fixture manifest and explicitly allow `synthetic_fixture` output. That path writes one tiny IC-1-compatible HP NPZ/manifest with `p_kw`, `q_kvar`, `timestamps`, and shared weather identity metadata, then loads it through the existing IC-1 NPZ loader with `allow_synthetic_fixture=True`. This is test scaffolding only and is not a real HP profile.

## Non-Claims

This packet does not approve annual HP TWh values, 2035 adoption/electrification/service fractions, final D-004 paired-weather acceptance, cold-spell tolerances, real HP profile or component-output generation, net-load/event analysis, `P(E)`, threshold/capacity-screen results, manuscript numbers, or probability results.

## Reviewer Focus

Please review whether the runner blocks the right HP-owned conditions before Agent A consumes HP component-output artifacts, and whether the synthetic fixture handoff is the right minimal IC-1 compatibility proof.
