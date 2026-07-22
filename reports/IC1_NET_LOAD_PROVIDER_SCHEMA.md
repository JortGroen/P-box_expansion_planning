# IC-1 NetLoadProvider Schema Packet

Task: E3.S2 IC-1 schema documentation packet.

Status: scaffold/documentation only. This packet documents the merged
`src/contracts/net_load.py` boundary for future real component adapters. It
does not wire real E2 components, open EV held-out data, run E3.S2a/E3.S2b/E3.S3,
evaluate thresholds or events, compute `P(E)`, or produce manuscript results.
Q-5 is resolved by G0-A3; this packet still does not authorize event-based work because other gates and accepted inputs remain pending.

## Governing Boundary

The public IC-1 provider call remains:

```python
get_net_load(
    scenario: str,
    year: int,
    time_domain: TimeDomain,
    rho: float,
    seed: int,
) -> NetLoadResult
```

Implementations derive an internal `NetLoadRealizationContext` from those
public arguments, call component adapters, and assemble the outputs into a
validated `NetLoadResult`. Real adapters should emit `ComponentAdapterOutput`
objects; they should not call IC-2, evaluate events, or aggregate probabilities.

Relevant governing decisions and questions:

- `ALEA-001`: one coherent realization on a common calendar; HP and PV use one
  paired weather member.
- `ALEA-002`: congestion and adequacy are downstream of aggregated net load.
- `RNG-001`: seed tree derives sample and component stream identities; CRN
  reuse is separate from physical shared drivers.
- `EV-003` through `EV-006`: EV member IDs, source-library uncertainty, and
  matched control-mode seeds remain traceable and constrained.
- `FLEX-001`: flexibility scaffold stays demand-side and proposed until PI
  approval.
- `G0-A3` / `Q-5`: resolved; primary threshold is strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps, with `1.1` and `1.2 p.u.` sensitivities. This packet does not run that criterion.
- `Q-8` / `WEATHER-001`: shared weather-member path is approved separately; this packet documents the IC-1
  hook without choosing that implementation path.

## ComponentAdapterOutput Fields

Every adapter output must populate the following fields:

| Field | Required | Meaning |
|---|---:|---|
| `component_id` | yes | Unique component-output identifier within one assembled net-load sample. |
| `kind` | yes | One of `baseline`, `ev`, `hp`, `pv`, `adoption`, `flexibility`, or `other`. Primary integration plans require the first six kinds. |
| `node_id` | yes | Target IC-1 aggregation node; must appear in `NetLoadAssemblyPlan.node_ids`. |
| `p_kw` | yes | Complete one-dimensional active-power trajectory in kW. Loads/import-side demand are positive; generation/export such as PV is negative. |
| `q_kvar` | yes | Complete one-dimensional reactive-power trajectory in kvar, same shape as `p_kw`. |
| `timestamps` | yes | Complete one-dimensional `numpy.datetime64` calendar at exactly 900-second cadence. |
| `member_id` | yes | Source-member identity selected for this realization, such as an EV profile member, weather member, or synthetic fixture ID. |
| `source_id` | yes | Provenance handle for the source/model/config that produced the member. |
| `stream_id` | yes | Component stream ID from `NetLoadRealizationContext.component_streams` for this `kind`. |
| `shared_weather_driver_id` | conditionally | Required for `hp` and `pv`, and must equal `NetLoadRealizationContext.shared_weather_driver_id`. Normally absent for non-weather components. |
| `metadata` | optional | JSON-manifestable extra provenance. Keys must be non-empty; values must not be `None` or empty strings. |

Adapters may use richer internal objects, but the IC-1 boundary receives only
the normalized `ComponentAdapterOutput` shape above.

For real-component readiness checks, each adapter output should include
`metadata["artifact_status"]` with one of:

- `accepted`: the owning E2 artifact has been accepted for integration use;
- `scaffold`: an approved scaffold or placeholder, not a scientific input;
- `synthetic_fixture`: deterministic test data only.

The helper `assemble_net_load_from_real_component_outputs(...)` requires
baseline, EV, HP, and PV outputs to be present, records the supplied
artifact-status values in `NetLoadResult.metadata["real_component_wiring"]`, and
then delegates to the same IC-1 adapter assembler. It does not call IC-2,
evaluate thresholds, inspect held-out data, or compute adequacy.

## Metadata-Only Adapter Skeletons

Future real-component adapters can be checked before any component arrays are
loaded by creating `ComponentAdapterSkeleton` records. These records are
array-free and exist only to make readiness provenance manifestable:

| Field | Meaning |
|---|---|
| `kind` | Component family, usually one of baseline, EV, HP, or PV for real-component wiring. |
| `artifact_status` | `accepted`, `scaffold`, or `synthetic_fixture`; accepted records must not list blocking items. |
| `source_id` | Readiness artifact, model, or source/config handle expected to feed the adapter. |
| `member_id` | Placeholder or accepted member identity that will later appear on emitted outputs. |
| `node_ids` | IC-1 nodes this adapter family is expected to cover. |
| `calendar_id` | Common calendar identity, such as the canonical 2035 15-minute calendar. |
| `timestep_seconds` | Must be 900 for the current IC-1 scaffold. |
| `shared_weather_driver_id` | Required for HP and PV, and the HP/PV values must match. |
| `blocking_items` | Remaining acceptance tasks for scaffold or synthetic fixtures. |
| `metadata` | Extra manifestable readiness notes, such as the owning E2 readiness report ID. |

`validate_component_adapter_skeletons(...)` requires one unique skeleton for
each requested component family, enforces the 900-second cadence, enforces the
WEATHER-001 HP/PV pairing hook, and reports whether all required real-component
families are accepted. It does not load trajectories, call adapters, assemble
net load, call IC-2, or evaluate thresholds.

## Adapter Registry And Assembly Plan

Once the required baseline, EV, HP, and PV skeletons are all accepted,
`ComponentAdapterRegistry` can turn that metadata into a node-ordered
`NetLoadAssemblyPlan`. The registry is still metadata-only: it contains no
arrays and does not certify adequacy. It records:

- `registry_id` for the wiring/checklist artifact;
- explicit IC-1 `node_ids` order;
- the accepted component skeletons and their readiness manifest;
- required component families;
- mapping/version metadata.

`build_ic1_assembly_plan_from_registry(...)` embeds the registry manifest in
the assembly plan. `assemble_net_load_from_registry_outputs(...)` then checks
future adapter outputs against the registry before delegating to the existing
IC-1 aggregation path. The pre-assembly checks require matching component kind,
node ID, source ID, member ID, artifact status, calendar ID, and shared HP/PV
weather identity. This prevents accepted metadata and emitted trajectories from
silently drifting apart in later integration work.

The registry-backed helper remains a synthetic/readiness harness. It does not
open real held-out data, call IC-2, detect events, run thresholds, or compute
`P(E)`.


## Accepted Adapter Artifact Bridge

`AcceptedComponentAdapterArtifact` is the metadata-only bridge between future
C-owned accepted component artifacts and the IC-1 adapter registry. It contains
no trajectories. Each record carries an accepted artifact ID, component kind,
source ID, member ID, covered node IDs, common calendar ID, 900-second cadence,
optional HP/PV shared weather-driver ID, and manifestable provenance.

`build_component_adapter_registry_from_artifacts(...)` validates the required
baseline, EV, HP, and PV artifact metadata before constructing a
`ComponentAdapterRegistry`. The bridge requires one unique accepted artifact per
required component kind, rejects missing registry-node coverage, preserves
source/member provenance in the registry manifest, and checks that HP and PV
share one WEATHER-001 weather-driver identity before any registry-backed
assembly can run.

This bridge is still below scientific analysis. It does not load real held-out
data, run E3.S2a adequacy, call IC-2, evaluate thresholds or events, compute
`P(E)`, or produce manuscript numbers.
## Calendar Rules

All component outputs in one `NetLoadResult` must share exactly one calendar.
Each `timestamps` vector must:

- be a one-dimensional `numpy.datetime64` array;
- be non-empty and contain no `NaT`;
- have strictly 900-second differences between adjacent steps;
- have the same length as `p_kw` and `q_kvar`;
- match every other component's timestamps exactly.

The current tests use short synthetic four-step calendars. Real full-year
adapters must preserve complete 15-minute trajectories and calendar alignment;
they must not shuffle, percentile-compress, or component-level screen before
IC-1 aggregation.

## Provenance And Member IDs

Each adapter must retain enough provenance for later manifests and diagnostics:

- `component_id` identifies the emitted trajectory inside the assembled sample.
- `member_id` identifies the selected source member for the sample.
- `source_id` identifies the source/config/model family.
- `stream_id` binds the selected member to the realization's component stream.
- `metadata` can carry extra IDs such as API request IDs, mapping versions,
  allocation rule IDs, control modes, or synthetic-fixture labels.

After conversion to `NetLoadComponent`, IC-1 stores provenance in
`ComponentProvenance` and adds:

- `realization_stream_id`;
- `realization_component_seed`.

This lets later manifests state which seed stream selected which source member
without changing the public `get_net_load(...)` signature.

## Seed And CRN Expectations

`AdapterBackedNetLoadProvider` builds one `NetLoadRealizationContext` for each
public `get_net_load(...)` call. Adapter implementations should use only the
context-derived component stream for their own `kind`.

Rules:

- same `(scenario, year, time_domain, rho, seed)` and same adapter inputs must
  produce identical `NetLoadResult` arrays and provenance;
- different root seeds must produce different aleatory identities;
- alpha, endpoint, and treatment labels must not alter the aleatory identity;
- component-stream IDs are not interchangeable between root seeds or component
  kinds;
- CRN reuse is not a physical-dependence model. Physical shared drivers, such
  as paired HP/PV weather, still need explicit shared IDs.

## Component-Specific Notes

### Baseline

Baseline adapters should emit positive demand-side `p_kw` and `q_kvar` for each
mapped node. The `member_id` should identify the selected complete baseline
trajectory or diversity member. Baseline trajectories must keep the common
calendar and should not be season/weekday shuffled after selection.

### EV

EV adapters should emit positive charging demand for each allocated node.
`member_id` must preserve the selected EV source-profile member. Future
implementations must respect EV-003 through EV-006, including finite-library
traceability and matched smart-control seeds where applicable. This packet does
not open held-out batches or choose a within-realization replacement rule.

### HP

Heat-pump adapters should emit weather-dependent demand. `shared_weather_driver_id`
is required and must equal `context.shared_weather_driver_id`. The `member_id`
should identify the HP profile/member generated from that shared weather driver.
Q-8 remains open for the neutral shared weather-member implementation path.

### PV

PV adapters should emit generation as negative `p_kw`. `shared_weather_driver_id`
is required and must equal `context.shared_weather_driver_id`, pairing the PV
trajectory with the same physical weather member used by HP. This packet does
not choose PVGIS/KNMI implementation details or run PV acceptance checks.

### Adoption

Adoption adapters may emit zero-power provenance components when adoption is
already expressed through EV/HP/PV component counts and node allocation, or may
emit adjustment trajectories if a later approved implementation requires it.
Either way, `member_id` and `metadata` should identify the scenario, local-count
source, allocation rule, and mapping version. This packet does not choose or
run real adoption counts.

### Flexibility

Flexibility adapters should emit demand-side adjustments consistent with
FLEX-001. In the current scaffold examples, flexibility appears as negative
active-power reductions on demand nodes. The adapter must not modify PV/export
components, evaluate events, or claim delivered-response behavior beyond the
scaffold.

## Validation Failures

The merged IC-1 boundary raises validation errors for:

- empty adapter lists or output lists;
- duplicate `component_id` values;
- missing required component families in `NetLoadAssemblyPlan`;
- unknown or duplicate plan `node_id` values;
- adapter `node_id` values not listed in the assembly plan;
- invalid `kind` values;
- non-empty-string failures in IDs or metadata keys;
- `None` or empty-string metadata values;
- non-finite, empty, or non-one-dimensional `p_kw` / `q_kvar`;
- non-`datetime64`, empty, `NaT`, or non-900-second timestamp vectors;
- mismatched P/Q/timestamp shapes;
- mismatched calendars between components;
- adapter `stream_id` not matching the context stream for its `kind`;
- `hp` or `pv` outputs without the context `shared_weather_driver_id`;
- HP/PV component outputs that do not share one weather ID after conversion;
- non-finite aggregate `p_net_kw` or `q_net_kvar`.

These failures are intended to stop bad samples before IC-2 loading trajectories
or downstream adequacy checks consume them.

## Synthetic Example

The following example mirrors the test fixtures and uses synthetic values only:

```python
import numpy as np

from src.contracts.net_load import (
    AdapterBackedNetLoadProvider,
    ComponentAdapterOutput,
    NetLoadAssemblyPlan,
)

calendar = np.array(
    [
        "2035-01-01T00:00:00",
        "2035-01-01T00:15:00",
        "2035-01-01T00:30:00",
        "2035-01-01T00:45:00",
    ],
    dtype="datetime64[s]",
)


class SyntheticAdapter:
    def __init__(self, kind, node_id, p_kw):
        self.kind = kind
        self.node_id = node_id
        self.p_kw = np.array(p_kw, dtype=float)

    def get_component_outputs(self, context, node_ids):
        weather_id = context.shared_weather_driver_id if self.kind in {"hp", "pv"} else None
        return [
            ComponentAdapterOutput(
                component_id=f"{self.kind}-{self.node_id}",
                kind=self.kind,
                node_id=self.node_id,
                p_kw=self.p_kw,
                q_kvar=np.zeros(calendar.size, dtype=float),
                timestamps=calendar,
                member_id=f"{self.kind}-member-{context.root_seed}",
                source_id=f"synthetic-{self.kind}",
                stream_id=next(
                    stream.stream_id
                    for stream in context.component_streams
                    if stream.component == self.kind
                ),
                shared_weather_driver_id=weather_id,
                metadata={"example": "synthetic", "artifact_status": "synthetic_fixture"},
            )
        ]


provider = AdapterBackedNetLoadProvider(
    plan=NetLoadAssemblyPlan(node_ids=("node-a", "node-b")),
    adapters=(
        SyntheticAdapter("baseline", "node-a", [10.0, 11.0, 12.0, 13.0]),
        SyntheticAdapter("ev", "node-a", [1.0, 2.0, 3.0, 4.0]),
        SyntheticAdapter("hp", "node-b", [4.0, 5.0, 6.0, 7.0]),
        SyntheticAdapter("pv", "node-b", [0.0, -2.0, -3.0, 0.0]),
        SyntheticAdapter("adoption", "node-a", [0.0, 0.0, 0.0, 0.0]),
        SyntheticAdapter("flexibility", "node-a", [-0.2, -0.2, 0.0, 0.0]),
    ),
    calendar_metadata={"calendar_id": "synthetic-2035-15min"},
    mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
    metadata={"scaffold_only": True},
)

result = provider.get_net_load("synthetic", 2035, "full_year", rho=0.25, seed=9001)
```

The resulting `NetLoadResult` has:

- `p_net_kw` and `q_net_kvar` with shape `(nodes, timesteps)`;
- `node_ids` matching the assembly plan;
- one shared timestamp vector;
- `component_provenance` entries for all six required component kinds;
- `shared_weather_driver_ids` containing the context weather ID;
- `metadata["realization_context"]` suitable for later manifest inclusion.

This example is not a scientific input, diagnostic, threshold screen, or
probability result.

## Downstream Boundary

IC-1 stops at `NetLoadResult`. Later stages may pass the aggregate trajectories
to IC-2 / `LoadingTrajectoryResult`, but this packet does not call IC-2 and does
not generate import/export loading, overload episodes, probabilities, figures,
or manuscript numbers.
