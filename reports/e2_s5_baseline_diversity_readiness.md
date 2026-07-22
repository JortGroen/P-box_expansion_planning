# E2.S5 Baseline And Diversity Readiness Memo

Task: E2.S5 baseline and diversity prep  
Status: scaffold/readiness contract only  
Branch: `agent-c/E2.S5-baseline-diversity-prep`

## Purpose

This memo defines the Agent C handoff contract for aligning baseline SimBench
load, EV, heat-pump, and PV component trajectories before Agent A consumes them
through IC-1. It is a calendar/provenance readiness layer only. It does not run
net-load aggregation, event detection, congestion analysis, profile-library
adequacy, `P(E)`, capacity screening, or manuscript-number production.

## Governing Decisions

- `ALEA-001`: every aleatory realization preserves complete trajectories on one
  common 15-minute calendar; no timestep shuffling.
- `WEATHER-001`: HP and PV consume one shared weather member and must carry the
  same `shared_weather_driver_id`.
- `ALEA-002`: component-level summaries cannot certify congestion or library
  adequacy; those checks occur only after downstream aggregation.
- `G0-A3` / `Q-5`: threshold-based integrated event analysis remains blocked
  until the PI resolves Q-5.

## Common Calendar Contract

Agent C component outputs should provide, before IC-1 aggregation:

| Component | Required identity | Required timestamp basis | Handoff rule |
|---|---|---|---|
| Baseline | SimBench baseline/diversity member ID and source ID | Complete timezone-aware trajectory | Preserve the source temporal and nodal order; map to the common local season and weekday/weekend calendar without shuffling steps. |
| EV | ElaadNL source member ID, batch seed, returned index, and source ID | Complete 15-minute annual charge-point trajectory | Use candidate-only libraries for sampling until E3.S2a authorizes held-out access; keep physical adoption counts separate from source-member sampling. |
| HP | Weather member ID, HP source/config ID, and shared weather driver ID | Complete 15-minute profile derived from the shared weather member | Preserve the same UTC/local instants as PV and carry temperature/source provenance. |
| PV | Weather member ID, PV source/config ID, and shared weather driver ID | Complete 15-minute profile derived from the shared weather member | Preserve the same UTC/local instants as HP and carry irradiance/source provenance. |

The executable helper in `src/baseline_model.py` creates a
`ComponentCalendarFootprint` for each component and validates a
`ComponentCalendarReadiness` record. The validator requires:

- unique component names;
- required baseline, EV, HP, and PV footprints;
- exact equality to the canonical 15-minute UTC axis for the requested local
  year and timezone;
- HP/PV `shared_weather_driver_id` present and identical;
- manifestable member/source IDs, first/last timestamps, cadence, timestamp
  checksum, and no-event/no-adequacy flags.

The current golden test uses the complete 2035 Europe/Amsterdam calendar:
35,040 timestamps from `2034-12-31T23:00:00+00:00` through
`2035-12-31T22:45:00+00:00`.

## Diversity Prep Boundary

The merged baseline scaffold preserves complete load trajectories and records
weekday/weekend and seasonal metadata. Household-diversity calibration remains
open: no diversity factor, residual correlation model, or baseline resampling
distribution is signed by this PR. The readiness helper is deliberately limited
to detecting whether a selected baseline/diversity member can be aligned with
EV, HP, and PV without destroying temporal order.

## Agent A Handoff Readiness

Ready for Agent A:

- a manifestable component-calendar footprint shape for baseline, EV, HP, and
  PV;
- deterministic validation of exact calendar equality before IC-1 aggregation;
- explicit HP/PV shared-weather identity validation;
- no-congestion/no-adequacy flags suitable for review manifests.

Not ready or not decided:

- final household-diversity calibration;
- HP local annual scaling and D-004 weather acceptance;
- EV finite-library adequacy and within-realization replacement policy;
- integrated net-load/event analysis;
- any manuscript result or capacity-screen number.

## Verification

Focused tests added in `tests/test_baseline_model.py` cover:

- successful baseline/EV/HP/PV alignment on the complete 2035 canonical
  calendar;
- local-vs-UTC timestamp normalization;
- shifted component-calendar rejection;
- HP/PV shared-weather mismatch rejection;
- missing component and duplicate component-name rejection.

