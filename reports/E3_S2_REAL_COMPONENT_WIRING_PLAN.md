# E3.S2 Real-Component Adapter Wiring Plan

Task: E3.S2 IC-1 integration scaffolding.

Status: phase-mode wiring plan only. This packet prepares the Agent A IC-1
boundary for future accepted C-owned baseline, EV, HP, and PV artifacts. It
uses merged readiness reports and metadata-only or synthetic placeholders. It
does not wire real arrays, open EV held-out data, run E3.S2a held-out results,
run E3.S2b/E3.S3 threshold screens, evaluate events, compute `P(E)`, or produce
manuscript numbers. Q-5 remains a hard stop before event-based scientific
analysis.

## Purpose

PR #105 added the executable IC-1 readiness wrapper:
`assemble_net_load_from_real_component_outputs(...)`. This plan says how future
component adapters should populate `ComponentAdapterOutput` payloads once their
owning C artifacts become accepted. Until then, IC-1 can only use
`artifact_status="scaffold"` or `artifact_status="synthetic_fixture"` entries
for tests and dry-run wiring.

The plan is intentionally not an adequacy criterion and not a scientific input
approval. It records the current adapter boundary, readiness evidence, missing
acceptance steps, and metadata each future adapter must preserve.

## Current Readiness Snapshot

| Component | Current status on main | IC-1 artifact status before acceptance | Main blocker before real IC-1 use |
|---|---|---|---|
| Baseline | E2.S5 baseline/diversity readiness exposes component-calendar footprints and canonical 2035 calendar checks. | `scaffold` | Final household-diversity calibration/source binding remains pending. |
| EV | E2.S2 EV integration readiness exposes metadata-only candidate Set A home and Set B public libraries plus EV-007A/A-014 allocation metadata. | `scaffold` | Local ignored NPZ checksums must be verified before loading candidate profiles; held-out data remain closed until E3.S2a. |
| HP | HP-001 approves the residential source/technology boundary and code can align HP profiles to a shared weather member. | `scaffold` | Local annual HP scaling, D-004 member acceptance, and cold-spell tolerance sign-off remain pending. |
| PV/weather | WEATHER-001 is implemented; D-004 source acceptance readiness is documented; member-construction rule remains proposal-only. | `scaffold` | PI approval of D004-MC-001 or amended hourly-to-15-minute rule, accepted `WeatherMember` records, and PV sanity checks. |
| Adoption | EV-007A/A-014 allocation metadata exists for later EV allocation. | `scaffold` | Final branch selection and any unresolved within-realization replacement policy remain outside this packet. |
| Flexibility | FLEX-001 scaffold exists and remains proposed. | `scaffold` | PI approval of FLEX-001 and later response-behavior choices before scientific use. |

## Adapter Output Mapping

Every real adapter should emit one or more `ComponentAdapterOutput` records.
The following fields must be populated before IC-1 aggregation:

| Field | Baseline | EV | HP | PV |
|---|---|---|---|---|
| `component_id` | Baseline node/member ID | EV node/profile-allocation ID | HP node/end-use/building-class ID | PV node/asset-weather ID |
| `kind` | `baseline` | `ev` | `hp` | `pv` |
| `node_id` | IC-1 node from the assembly plan | IC-1 node after A-014 allocation | IC-1 node after HP adoption/allocation | IC-1 node after PV allocation |
| `p_kw` | Positive demand trajectory | Positive charging demand trajectory | Positive heat-pump electric demand trajectory | Negative generation trajectory |
| `q_kvar` | Baseline reactive trajectory or approved scaffold value | EV reactive trajectory or approved scaffold value | HP reactive trajectory or approved scaffold value | PV reactive trajectory or approved scaffold value |
| `timestamps` | Common 15-minute calendar | Same common calendar | Same common calendar | Same common calendar |
| `member_id` | Baseline/diversity member | EV profile member(s) and allocation member | HP source/weather/scaling member | PV/weather member |
| `source_id` | Baseline source/config ID | EV library partition and source ID | HP-001/D-003/scaling source ID | WEATHER-001/D-004/PV config ID |
| `stream_id` | Context `baseline` stream | Context `ev` stream | Context `hp` stream | Context `pv` stream |
| `shared_weather_driver_id` | normally absent | normally absent | Must equal context weather ID | Must equal context weather ID |
| `metadata["artifact_status"]` | `accepted`, `scaffold`, or `synthetic_fixture` | `accepted`, `scaffold`, or `synthetic_fixture` | `accepted`, `scaffold`, or `synthetic_fixture` | `accepted`, `scaffold`, or `synthetic_fixture` |

The IC-1 readiness wrapper currently requires baseline, EV, HP, and PV output
families. Adoption and flexibility outputs remain required by the broader
`NetLoadAssemblyPlan` for integrated samples, but they are not treated as
real-component blockers by the wrapper because their final scientific use is
still governed by separate decisions.

## Calendar And Weather Wiring

Before any real component arrays are consumed, A/C should run the C-owned
calendar-footprint readiness check for baseline, EV, HP, and PV. IC-1 then
receives only outputs with exactly the same 15-minute `numpy.datetime64`
calendar.

HP and PV must be produced from the same WEATHER-001 `WeatherMember` identity.
The IC-1 context's `shared_weather_driver_id` is the expected value for both
weather-dependent adapter outputs. A pair of HP/PV outputs that share a
non-context weather ID is rejected by the existing IC-1 boundary.

## CRN And Member Selection

The public `NetLoadProvider.get_net_load(...)` call remains:

```python
get_net_load(scenario, year, time_domain, rho, seed)
```

The provider derives a `NetLoadRealizationContext` internally. Future adapters
should use the context component stream for their own component kind and record
the selected member IDs in `metadata` and `member_id`. Alpha, endpoint, and
treatment labels must not alter this physical sample identity. CRN reuse does
not replace physical dependence: HP/PV still need the shared weather-member ID.

EV candidate and held-out libraries remain separate under EV-005. This plan
does not authorize held-out selection or a within-realization replacement rule.

## Minimal Synthetic Phase Harness

Until accepted artifacts exist, the integration harness should continue using
synthetic fixture outputs with:

- a small deterministic 15-minute calendar;
- `artifact_status="synthetic_fixture"`;
- baseline/EV/HP positive demand and PV negative generation;
- HP/PV `shared_weather_driver_id` equal to the context weather ID;
- node IDs that match a declared `NetLoadAssemblyPlan`;
- no threshold, overload, probability, or manuscript metadata.

Once a component has an accepted artifact, the corresponding synthetic output
can be replaced independently with `artifact_status="accepted"` while the
remaining unavailable components stay `scaffold` or `synthetic_fixture`. The
result must remain labeled as a mixed-status wiring dry run until every
component required for the intended scientific use is accepted.

## Stop Conditions Before Real Runs

Stop and escalate rather than running integrated analysis if any of the
following occur:

1. A future C-owned adapter cannot emit the existing `ComponentAdapterOutput`
   fields without changing IC-1.
2. Real component calendars cannot be made exactly common without timestep
   shuffling or unapproved interpolation.
3. HP and PV cannot prove the same WEATHER-001 member identity.
4. EV candidate profile checksums or selected member IDs cannot be verified.
5. HP local annual scaling, D-004 member construction, or PV sanity acceptance
   is still unsigned for the intended real run.
6. The run would inspect EV held-out adequacy data before E3.S2a freezes its
   downstream criterion.
7. The run would evaluate thresholds, event episodes, `P(E)`, E3.S2b/E3.S3
   threshold screens, or manuscript numbers while Q-5 is unresolved.

## Suggested Implementation Sequence

1. Keep current synthetic tests as the IC-1 boundary proof.
2. Add adapter-specific unit tests as each C-owned artifact becomes accepted,
   using metadata-only fixtures first and real arrays only after source checks
   are signed.
3. Replace synthetic baseline with accepted baseline/diversity output once E2.S5
   final calibration is ready.
4. Replace EV with candidate-only EV output after local ignored NPZ checksums,
   calendar mapping, adoption allocation, and member-selection metadata are
   verified.
5. Replace HP and PV together after D-004 member construction and HP/PV
   acceptance prove shared WEATHER-001 identity.
6. Only after all required components are accepted and Q-5 is resolved should a
   later task propose manifested downstream adequacy or threshold-based runs.

## No-Result Boundary

This packet creates no experimental result and therefore no runner manifest.
It is a planning artifact for the IC-1 adapter boundary. All future real
component or downstream runs must use the project runner and manifest mechanism
where they produce evidence.
