"""Shared IC-1 NetLoadProvider scaffold and validators.

This module defines the Agent A-owned net-load boundary without binding it to
the unfinished E2 component implementations. It aggregates already-aligned
component trajectories and preserves the provenance needed by downstream
adequacy and physics checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence

import numpy as np

from src.contracts.loading_trajectory import TimeDomain
from src.rng import ComponentStream, SeedTree


ComponentKind = Literal[
    "baseline",
    "ev",
    "hp",
    "pv",
    "adoption",
    "flexibility",
    "other",
]
ComponentArtifactStatus = Literal["accepted", "scaffold", "synthetic_fixture"]


REQUIRED_INTEGRATION_COMPONENT_KINDS: tuple[ComponentKind, ...] = (
    "baseline",
    "ev",
    "hp",
    "pv",
    "adoption",
    "flexibility",
)
REAL_COMPONENT_WIRING_KINDS: tuple[ComponentKind, ...] = (
    "baseline",
    "ev",
    "hp",
    "pv",
)
ALLOWED_COMPONENT_ARTIFACT_STATUSES: tuple[ComponentArtifactStatus, ...] = (
    "accepted",
    "scaffold",
    "synthetic_fixture",
)

DEFAULT_REALIZATION_COMPONENTS: tuple[str, ...] = REQUIRED_INTEGRATION_COMPONENT_KINDS
DEFAULT_SAMPLE_INDEX = 0


@dataclass(frozen=True)
class ComponentProvenance:
    """Traceable source identity for one net-load component trajectory."""

    component_id: str
    kind: ComponentKind
    node_id: str
    member_id: str | None = None
    source_id: str | None = None
    shared_weather_driver_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty(self.component_id, name="component_id")
        _require_nonempty(self.node_id, name="node_id")
        if self.kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("kind must be a valid net-load component kind")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class NetLoadRealizationContext:
    """Auditable ALEA-001 sample identity derived inside IC-1.

    The public ``NetLoadProvider.get_net_load(...)`` signature remains
    unchanged; implementations can build this context internally from those
    arguments before selecting component members or assembling trajectories.
    """

    scenario: str
    planning_year: int
    time_domain: TimeDomain
    rho: float
    root_seed: int
    sample_index: int
    sample_seed: int
    component_streams: tuple[ComponentStream, ...]
    shared_weather_driver_id: str
    calendar_metadata: Mapping[str, object] = field(default_factory=dict)
    mapping_version_metadata: Mapping[str, object] = field(default_factory=dict)
    component_member_placeholders: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty(self.scenario, name="scenario")
        if isinstance(self.planning_year, bool) or not isinstance(self.planning_year, int):
            raise TypeError("planning_year must be an integer")
        if self.planning_year <= 0:
            raise ValueError("planning_year must be positive")
        if self.time_domain not in {"full_year", "window_set"}:
            raise ValueError("time_domain must be 'full_year' or 'window_set'")
        if not np.isfinite(float(self.rho)) or not 0.0 <= float(self.rho) <= 1.0:
            raise ValueError("rho must be finite and in [0, 1]")
        if self.root_seed < 0:
            raise ValueError("root_seed must be non-negative")
        if self.sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        expected_tree = SeedTree(self.root_seed)
        expected_sample_seed = expected_tree.sample_seed(self.sample_index)
        if self.sample_seed != expected_sample_seed:
            raise ValueError("sample_seed must match root_seed and sample_index")

        stream_by_component: dict[str, ComponentStream] = {}
        for stream in self.component_streams:
            if stream.component in stream_by_component:
                raise ValueError("component_streams must not contain duplicate components")
            expected_stream = expected_tree.component_stream(self.sample_index, stream.component)
            if stream.seed != expected_stream.seed or stream.stream_id != expected_stream.stream_id:
                raise ValueError("component_streams must match root_seed and sample_index")
            stream_by_component[stream.component] = stream
        if not stream_by_component:
            raise ValueError("component_streams must not be empty")

        _require_nonempty(self.shared_weather_driver_id, name="shared_weather_driver_id")
        _validate_nonempty_mapping_values(self.calendar_metadata, name="calendar_metadata")
        _validate_nonempty_mapping_values(self.mapping_version_metadata, name="mapping_version_metadata")
        _validate_nonempty_mapping_values(
            self.component_member_placeholders,
            name="component_member_placeholders",
        )
        for component in self.component_member_placeholders:
            if component not in stream_by_component:
                raise ValueError("component member placeholders require matching component streams")

        object.__setattr__(self, "rho", float(self.rho))
        object.__setattr__(self, "component_streams", tuple(sorted(stream_by_component.values(), key=lambda item: item.component)))
        object.__setattr__(self, "calendar_metadata", MappingProxyType(dict(self.calendar_metadata)))
        object.__setattr__(self, "mapping_version_metadata", MappingProxyType(dict(self.mapping_version_metadata)))
        object.__setattr__(
            self,
            "component_member_placeholders",
            MappingProxyType(dict(self.component_member_placeholders)),
        )

    def aleatory_identity(self) -> dict[str, object]:
        """Return the branch-independent physical sample identity."""

        return {
            "root_seed": self.root_seed,
            "sample_index": self.sample_index,
            "sample_seed": self.sample_seed,
            "component_streams": [stream.manifest_record() for stream in self.component_streams],
            "shared_weather_driver_id": self.shared_weather_driver_id,
        }

    def manifest_metadata(self) -> dict[str, object]:
        """Return JSON-manifestable context metadata for runner outputs."""

        return {
            "scenario": self.scenario,
            "planning_year": self.planning_year,
            "time_domain": self.time_domain,
            "rho": self.rho,
            "aleatory_identity": self.aleatory_identity(),
            "calendar_metadata": dict(self.calendar_metadata),
            "mapping_version_metadata": dict(self.mapping_version_metadata),
            "component_member_placeholders": dict(self.component_member_placeholders),
        }


@dataclass(frozen=True)
class NetLoadAssemblyPlan:
    """Synthetic IC-1 integration plan for wiring real E2 components later.

    The plan records the output node order and required component families. It
    carries no event threshold or congestion setting.
    """

    node_ids: tuple[str, ...]
    required_component_kinds: tuple[ComponentKind, ...] = REQUIRED_INTEGRATION_COMPONENT_KINDS
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_ids:
            raise ValueError("node_ids must not be empty")
        for node_id in self.node_ids:
            _require_nonempty(node_id, name="node_id")
        if len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("node_ids must not contain duplicates")
        if not self.required_component_kinds:
            raise ValueError("required_component_kinds must not be empty")
        for kind in self.required_component_kinds:
            if kind not in _VALID_COMPONENT_KINDS:
                raise ValueError("required_component_kinds must contain valid component kinds")
        object.__setattr__(self, "node_ids", tuple(self.node_ids))
        object.__setattr__(self, "required_component_kinds", tuple(self.required_component_kinds))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ComponentAdapterSkeleton:
    """Metadata-only readiness record for one future real component adapter.

    The skeleton is intentionally array-free. It documents whether a baseline,
    EV, HP, or PV adapter is still scaffold-only or can later emit
    ``ComponentAdapterOutput`` values for a given calendar and node mapping.
    """

    kind: ComponentKind
    artifact_status: ComponentArtifactStatus
    source_id: str
    member_id: str
    node_ids: tuple[str, ...]
    calendar_id: str
    timestep_seconds: int = 900
    shared_weather_driver_id: str | None = None
    blocking_items: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("kind must be a valid net-load component kind")
        if self.artifact_status not in ALLOWED_COMPONENT_ARTIFACT_STATUSES:
            raise ValueError("artifact_status must be accepted, scaffold, or synthetic_fixture")
        source_id = _require_nonempty(self.source_id, name="source_id")
        member_id = _require_nonempty(self.member_id, name="member_id")
        calendar_id = _require_nonempty(self.calendar_id, name="calendar_id")
        if not self.node_ids:
            raise ValueError("node_ids must not be empty")
        node_ids = tuple(_require_nonempty(node_id, name="node_id") for node_id in self.node_ids)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node_ids must not contain duplicates")
        if (
            isinstance(self.timestep_seconds, bool)
            or not isinstance(self.timestep_seconds, int)
            or self.timestep_seconds != 900
        ):
            raise ValueError("timestep_seconds must be the 900-second IC-1 cadence")
        if self.shared_weather_driver_id is not None:
            _require_nonempty(self.shared_weather_driver_id, name="shared_weather_driver_id")
        if self.kind in {"hp", "pv"} and self.shared_weather_driver_id is None:
            raise ValueError("weather-dependent adapter skeletons require shared_weather_driver_id")
        blocking_items = tuple(
            _require_nonempty(item, name="blocking_item")
            for item in self.blocking_items
        )
        if self.artifact_status == "accepted" and blocking_items:
            raise ValueError("accepted adapter skeletons must not list blocking_items")
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "member_id", member_id)
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "timestep_seconds", int(self.timestep_seconds))
        object.__setattr__(self, "blocking_items", blocking_items)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_record(self) -> dict[str, object]:
        """Return a JSON-manifestable metadata record for readiness reports."""

        return {
            "kind": self.kind,
            "artifact_status": self.artifact_status,
            "source_id": self.source_id,
            "member_id": self.member_id,
            "node_ids": self.node_ids,
            "calendar_id": self.calendar_id,
            "timestep_seconds": self.timestep_seconds,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "blocking_items": self.blocking_items,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AcceptedComponentAdapterArtifact:
    """Metadata-only handle for an accepted future component adapter artifact.

    This bridge record is deliberately array-free. It captures the accepted
    source/member/calendar/node metadata needed to construct an IC-1 adapter
    registry before any real component trajectories are loaded.
    """

    artifact_id: str
    kind: ComponentKind
    source_id: str
    member_id: str
    node_ids: tuple[str, ...]
    calendar_id: str
    timestep_seconds: int = 900
    shared_weather_driver_id: str | None = None
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        artifact_id = _require_nonempty(self.artifact_id, name="artifact_id")
        if self.kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("kind must be a valid net-load component kind")
        source_id = _require_nonempty(self.source_id, name="source_id")
        member_id = _require_nonempty(self.member_id, name="member_id")
        calendar_id = _require_nonempty(self.calendar_id, name="calendar_id")
        if not self.node_ids:
            raise ValueError("node_ids must not be empty")
        node_ids = tuple(_require_nonempty(node_id, name="node_id") for node_id in self.node_ids)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node_ids must not contain duplicates")
        if (
            isinstance(self.timestep_seconds, bool)
            or not isinstance(self.timestep_seconds, int)
            or self.timestep_seconds != 900
        ):
            raise ValueError("timestep_seconds must be the 900-second IC-1 cadence")
        if self.shared_weather_driver_id is not None:
            _require_nonempty(self.shared_weather_driver_id, name="shared_weather_driver_id")
        if self.kind in {"hp", "pv"} and self.shared_weather_driver_id is None:
            raise ValueError("weather-dependent adapter artifacts require shared_weather_driver_id")
        _validate_nonempty_mapping_values(self.provenance, name="provenance")
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "member_id", member_id)
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "timestep_seconds", int(self.timestep_seconds))
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    def to_skeleton(self) -> ComponentAdapterSkeleton:
        """Convert accepted artifact metadata into a registry skeleton."""

        return ComponentAdapterSkeleton(
            kind=self.kind,
            artifact_status="accepted",
            source_id=self.source_id,
            member_id=self.member_id,
            node_ids=self.node_ids,
            calendar_id=self.calendar_id,
            timestep_seconds=self.timestep_seconds,
            shared_weather_driver_id=self.shared_weather_driver_id,
            metadata={
                "artifact_id": self.artifact_id,
                "provenance": dict(self.provenance),
            },
        )

    def manifest_record(self) -> dict[str, object]:
        """Return manifestable accepted-artifact metadata for IC-1 plans."""

        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "source_id": self.source_id,
            "member_id": self.member_id,
            "node_ids": self.node_ids,
            "calendar_id": self.calendar_id,
            "timestep_seconds": self.timestep_seconds,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class ComponentAdapterRegistry:
    """Accepted metadata registry for building an auditable IC-1 plan.

    The registry is still scaffold/readiness-only: it contains no trajectories.
    It turns already-accepted component metadata into a node-ordered
    ``NetLoadAssemblyPlan`` and manifest record for later real adapter outputs.
    """

    registry_id: str
    node_ids: tuple[str, ...]
    skeletons: tuple[ComponentAdapterSkeleton, ...]
    required_component_kinds: tuple[ComponentKind, ...] = REAL_COMPONENT_WIRING_KINDS
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        registry_id = _require_nonempty(self.registry_id, name="registry_id")
        if not self.node_ids:
            raise ValueError("node_ids must not be empty")
        node_ids = tuple(_require_nonempty(node_id, name="node_id") for node_id in self.node_ids)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node_ids must not contain duplicates")
        if not self.skeletons:
            raise ValueError("skeletons must not be empty")
        readiness = validate_component_adapter_skeletons(
            self.skeletons,
            required_component_kinds=self.required_component_kinds,
        )
        if not readiness["ready_for_real_arrays"]:
            raise ValueError("adapter registry requires accepted component metadata")
        skeleton_nodes = {
            node_id
            for skeleton in self.skeletons
            for node_id in skeleton.node_ids
        }
        missing_nodes = sorted(skeleton_nodes.difference(node_ids))
        if missing_nodes:
            raise ValueError(f"skeleton node_id(s) missing from registry node_ids: {', '.join(missing_nodes)}")
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "registry_id", registry_id)
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "skeletons", tuple(self.skeletons))
        object.__setattr__(self, "required_component_kinds", tuple(self.required_component_kinds))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_record(self) -> dict[str, object]:
        """Return manifestable registry metadata for IC-1 assembly evidence."""

        readiness = validate_component_adapter_skeletons(
            self.skeletons,
            required_component_kinds=self.required_component_kinds,
        )
        return {
            "registry_id": self.registry_id,
            "node_ids": self.node_ids,
            "required_component_kinds": self.required_component_kinds,
            "readiness": readiness,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ComponentAdapterOutput:
    """Normalized output from a future E2 component adapter.

    Real baseline, EV, HP, PV, adoption, and flexibility implementations can
    emit this narrow payload before IC-1 converts it into a ``NetLoadComponent``.
    The scaffold intentionally carries trajectories and provenance only.
    """

    component_id: str
    kind: ComponentKind
    node_id: str
    p_kw: np.ndarray
    q_kvar: np.ndarray
    timestamps: np.ndarray
    member_id: str
    source_id: str
    stream_id: str
    shared_weather_driver_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        component_id = _require_nonempty(self.component_id, name="component_id")
        node_id = _require_nonempty(self.node_id, name="node_id")
        member_id = _require_nonempty(self.member_id, name="member_id")
        source_id = _require_nonempty(self.source_id, name="source_id")
        stream_id = _require_nonempty(self.stream_id, name="stream_id")
        if self.kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("kind must be a valid net-load component kind")
        p_kw = _as_power_vector(self.p_kw, name="p_kw")
        q_kvar = _as_power_vector(self.q_kvar, name="q_kvar")
        timestamps = _as_15_minute_calendar(self.timestamps)
        if p_kw.shape != timestamps.shape or q_kvar.shape != timestamps.shape:
            raise ValueError("adapter trajectories and timestamps must have identical shapes")
        if self.shared_weather_driver_id is not None:
            _require_nonempty(self.shared_weather_driver_id, name="shared_weather_driver_id")
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "component_id", component_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "member_id", member_id)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "stream_id", stream_id)
        object.__setattr__(self, "p_kw", p_kw)
        object.__setattr__(self, "q_kvar", q_kvar)
        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class NetLoadComponent:
    """One complete component trajectory before IC-1 aggregation.

    Parameters
    ----------
    provenance:
        Source/member identity retained in the aggregate result.
    p_kw, q_kvar:
        Active and reactive trajectories in kW/kvar. Generation/export
        components, such as PV, should use negative active power.
    timestamps:
        Common 15-minute calendar as ``numpy.datetime64`` values.
    """

    provenance: ComponentProvenance
    p_kw: np.ndarray
    q_kvar: np.ndarray
    timestamps: np.ndarray

    def __post_init__(self) -> None:
        p_kw = _as_power_vector(self.p_kw, name="p_kw")
        q_kvar = _as_power_vector(self.q_kvar, name="q_kvar")
        timestamps = _as_15_minute_calendar(self.timestamps)
        if p_kw.shape != timestamps.shape or q_kvar.shape != timestamps.shape:
            raise ValueError("component trajectories and timestamps must have identical shapes")
        object.__setattr__(self, "p_kw", p_kw)
        object.__setattr__(self, "q_kvar", q_kvar)
        object.__setattr__(self, "timestamps", timestamps)


@dataclass(frozen=True)
class NetLoadResult:
    """Validated IC-1 net-load payload for downstream evaluators.

    Attributes
    ----------
    p_net_kw, q_net_kvar:
        Aggregated nodal net-load arrays with shape ``(nodes, timesteps)``.
    timestamps:
        Complete common 15-minute calendar for every component and node.
    node_ids:
        Node labels corresponding to the first axis of ``p_net_kw`` and
        ``q_net_kvar``.
    component_provenance:
        Component/member metadata retained for manifests and diagnostics.
    """

    p_net_kw: np.ndarray
    q_net_kvar: np.ndarray
    timestamps: np.ndarray
    node_ids: tuple[str, ...]
    component_provenance: tuple[ComponentProvenance, ...]
    shared_weather_driver_ids: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        p_net_kw = np.asarray(self.p_net_kw, dtype=float)
        q_net_kvar = np.asarray(self.q_net_kvar, dtype=float)
        timestamps = _as_15_minute_calendar(self.timestamps)
        if p_net_kw.ndim != 2 or q_net_kvar.ndim != 2:
            raise ValueError("net-load arrays must have shape (nodes, timesteps)")
        if p_net_kw.shape != q_net_kvar.shape:
            raise ValueError("p_net_kw and q_net_kvar must have identical shapes")
        if p_net_kw.shape[0] != len(self.node_ids):
            raise ValueError("node_ids must match the net-load node dimension")
        if p_net_kw.shape[1] != timestamps.size:
            raise ValueError("timestamps must match the net-load time dimension")
        if not np.isfinite(p_net_kw).all() or not np.isfinite(q_net_kvar).all():
            raise ValueError("net-load arrays must contain only finite values")
        if not self.component_provenance:
            raise ValueError("component_provenance must not be empty")
        for node_id in self.node_ids:
            _require_nonempty(node_id, name="node_id")
        object.__setattr__(self, "p_net_kw", p_net_kw)
        object.__setattr__(self, "q_net_kvar", q_net_kvar)
        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(self, "node_ids", tuple(self.node_ids))
        object.__setattr__(self, "component_provenance", tuple(self.component_provenance))
        object.__setattr__(self, "shared_weather_driver_ids", tuple(self.shared_weather_driver_ids))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class NetLoadProvider(Protocol):
    """Structural IC-1 provider protocol for future E2/E3 implementations."""

    def get_net_load(
        self,
        scenario: str,
        year: int,
        time_domain: TimeDomain,
        rho: float,
        seed: int,
    ) -> NetLoadResult:
        """Return one deterministic, traceable net-load realization."""


class NetLoadComponentAdapter(Protocol):
    """Structural boundary for future real E2 component adapters."""

    def get_component_outputs(
        self,
        context: NetLoadRealizationContext,
        node_ids: Sequence[str],
    ) -> Sequence[ComponentAdapterOutput]:
        """Return complete component trajectories for one IC-1 realization."""


@dataclass(frozen=True)
class AdapterBackedNetLoadProvider:
    """Smoke-harness IC-1 provider backed by component adapters.

    This is a scaffold for contract/integration tests: callers keep the public
    ``get_net_load(...)`` signature while adapters receive the internal
    ALEA-001 realization context.
    """

    plan: NetLoadAssemblyPlan
    adapters: tuple[NetLoadComponentAdapter, ...]
    calendar_metadata: Mapping[str, object] = field(default_factory=dict)
    mapping_version_metadata: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapters:
            raise ValueError("adapters must not be empty")
        _validate_nonempty_mapping_values(self.calendar_metadata, name="calendar_metadata")
        _validate_nonempty_mapping_values(self.mapping_version_metadata, name="mapping_version_metadata")
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "adapters", tuple(self.adapters))
        object.__setattr__(self, "calendar_metadata", MappingProxyType(dict(self.calendar_metadata)))
        object.__setattr__(self, "mapping_version_metadata", MappingProxyType(dict(self.mapping_version_metadata)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def get_net_load(
        self,
        scenario: str,
        year: int,
        time_domain: TimeDomain,
        rho: float,
        seed: int,
    ) -> NetLoadResult:
        """Return one deterministic synthetic adapter-backed IC-1 realization."""

        context = build_realization_context(
            scenario=scenario,
            year=year,
            time_domain=time_domain,
            rho=rho,
            seed=seed,
            calendar_metadata=self.calendar_metadata,
            mapping_version_metadata=self.mapping_version_metadata,
        )
        outputs: list[ComponentAdapterOutput] = []
        for adapter in self.adapters:
            outputs.extend(adapter.get_component_outputs(context, self.plan.node_ids))
        # The provider smoke harness must not hide adapter omissions or extras:
        # every output still passes through the same boundary real E2 adapters
        # will use later.
        return assemble_net_load_from_adapter_outputs(
            self.plan,
            context,
            outputs,
            metadata={"provider": "adapter_backed_smoke_harness", **dict(self.metadata)},
        )


def build_realization_context(
    *,
    scenario: str,
    year: int,
    time_domain: TimeDomain,
    rho: float,
    seed: int,
    sample_index: int = DEFAULT_SAMPLE_INDEX,
    component_names: Sequence[str] = DEFAULT_REALIZATION_COMPONENTS,
    shared_weather_driver_id: str | None = None,
    calendar_metadata: Mapping[str, object] | None = None,
    mapping_version_metadata: Mapping[str, object] | None = None,
    component_member_placeholders: Mapping[str, str] | None = None,
) -> NetLoadRealizationContext:
    """Build the internal ALEA-001 context from IC-1 public arguments.

    The IC-1 public call has one ``seed`` argument, so this scaffold treats it
    as the RNG root and uses ``sample_index=0`` unless a future internal caller
    supplies a sample index. Branch labels are deliberately absent: alpha,
    endpoint, and treatment must replay this same physical realization.
    """

    tree = SeedTree(seed)
    components = tuple(_require_nonempty(component, name="component") for component in component_names)
    if not components:
        raise ValueError("component_names must not be empty")
    if len(set(components)) != len(components):
        raise ValueError("component_names must not contain duplicates")
    streams = tuple(tree.component_stream(sample_index, component) for component in sorted(components))
    # ALEA-001 pairs HP and PV through one shared physical weather driver; this
    # placeholder is derived from the weather stream so CRN branch labels cannot
    # accidentally create different weather identities for the same sample.
    weather_stream = tree.component_stream(sample_index, "weather")
    weather_id = shared_weather_driver_id or f"weather:{weather_stream.stream_id}"
    placeholders = (
        {component: f"pending:{component}" for component in sorted(components)}
        if component_member_placeholders is None
        else dict(component_member_placeholders)
    )
    return NetLoadRealizationContext(
        scenario=scenario,
        planning_year=year,
        time_domain=time_domain,
        rho=rho,
        root_seed=seed,
        sample_index=sample_index,
        sample_seed=tree.sample_seed(sample_index),
        component_streams=streams,
        shared_weather_driver_id=weather_id,
        calendar_metadata={} if calendar_metadata is None else calendar_metadata,
        mapping_version_metadata={} if mapping_version_metadata is None else mapping_version_metadata,
        component_member_placeholders=placeholders,
    )


def net_load_component_from_adapter_output(
    output: ComponentAdapterOutput,
    context: NetLoadRealizationContext,
) -> NetLoadComponent:
    """Convert one normalized adapter output into an IC-1 component."""

    stream_by_component = _component_streams_by_name(context)
    if output.kind not in stream_by_component:
        raise ValueError("adapter output kind must have a matching realization component stream")
    expected_stream = stream_by_component[output.kind]
    # The stream check keeps future source-member choices tied to the manifest
    # context; otherwise a component could be replayed under the wrong CRN seed.
    if output.stream_id != expected_stream.stream_id:
        raise ValueError("adapter output stream_id must match the realization context")
    # ALEA-001 makes the context's paired weather member part of the sample
    # identity; HP/PV may not substitute a different shared-but-wrong driver.
    if (
        output.kind in {"hp", "pv"}
        and output.shared_weather_driver_id != context.shared_weather_driver_id
    ):
        raise ValueError("weather-dependent adapter outputs must use the context shared_weather_driver_id")

    provenance_metadata = dict(output.metadata)
    provenance_metadata.update(
        {
            "realization_stream_id": expected_stream.stream_id,
            "realization_component_seed": expected_stream.seed,
        }
    )
    return NetLoadComponent(
        provenance=ComponentProvenance(
            component_id=output.component_id,
            kind=output.kind,
            node_id=output.node_id,
            member_id=output.member_id,
            source_id=output.source_id,
            shared_weather_driver_id=output.shared_weather_driver_id,
            metadata=provenance_metadata,
        ),
        p_kw=output.p_kw,
        q_kvar=output.q_kvar,
        timestamps=output.timestamps,
    )


def assemble_net_load_from_adapter_outputs(
    plan: NetLoadAssemblyPlan,
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
    *,
    metadata: Mapping[str, object] | None = None,
) -> NetLoadResult:
    """Assemble IC-1 net load from future component-adapter outputs.

    This scaffold defines the real-component join point while still using only
    precomputed/synthetic adapter outputs. It performs no IC-2 evaluation,
    threshold screening, adequacy check, or probability calculation.
    """

    if not adapter_outputs:
        raise ValueError("adapter_outputs must not be empty")
    component_ids = [output.component_id for output in adapter_outputs]
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("adapter output component_id values must be unique")
    components = tuple(
        net_load_component_from_adapter_output(output, context)
        for output in adapter_outputs
    )
    combined_metadata = {
        "assembly": "component_adapter_boundary_scaffold",
        "realization_context": context.manifest_metadata(),
    }
    if metadata is not None:
        combined_metadata.update(metadata)
    return assemble_net_load_from_components(plan, components, metadata=combined_metadata)


def assemble_net_load_from_real_component_outputs(
    plan: NetLoadAssemblyPlan,
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
    *,
    required_real_component_kinds: Sequence[ComponentKind] = REAL_COMPONENT_WIRING_KINDS,
    metadata: Mapping[str, object] | None = None,
) -> NetLoadResult:
    """Assemble IC-1 net load from real-component-ready adapter outputs.

    This readiness wrapper is the narrow join point future C-owned baseline,
    EV, HP, and PV adapters can target after their artifacts are accepted. It
    still accepts synthetic fixture outputs for tests, records that status in
    metadata, and performs no IC-2 loading, event, adequacy, or probability
    analysis.
    """

    readiness = validate_real_component_adapter_readiness(
        adapter_outputs,
        required_real_component_kinds=required_real_component_kinds,
    )
    combined_metadata = {
        "real_component_wiring": readiness,
    }
    if metadata is not None:
        combined_metadata.update(metadata)
    return assemble_net_load_from_adapter_outputs(
        plan,
        context,
        adapter_outputs,
        metadata=combined_metadata,
    )


def build_ic1_assembly_plan_from_registry(registry: ComponentAdapterRegistry) -> NetLoadAssemblyPlan:
    """Build a node-ordered IC-1 assembly plan from accepted metadata only."""

    return NetLoadAssemblyPlan(
        node_ids=registry.node_ids,
        required_component_kinds=registry.required_component_kinds,
        metadata={
            "assembly": "ic1_adapter_registry_readiness",
            "adapter_registry": registry.manifest_record(),
        },
    )


def build_component_adapter_registry_from_artifacts(
    *,
    registry_id: str,
    node_ids: Sequence[str],
    artifacts: Sequence[AcceptedComponentAdapterArtifact],
    required_component_kinds: Sequence[ComponentKind] = REAL_COMPONENT_WIRING_KINDS,
    metadata: Mapping[str, object] | None = None,
) -> ComponentAdapterRegistry:
    """Build an IC-1 adapter registry from accepted artifact metadata only."""

    if not artifacts:
        raise ValueError("artifacts must not be empty")
    required = tuple(required_component_kinds)
    if not required:
        raise ValueError("required_component_kinds must not be empty")
    by_kind: dict[ComponentKind, AcceptedComponentAdapterArtifact] = {}
    for artifact in artifacts:
        if artifact.kind in by_kind:
            raise ValueError("accepted component adapter artifact kinds must be unique")
        by_kind[artifact.kind] = artifact
    missing = [kind for kind in required if kind not in by_kind]
    if missing:
        raise ValueError(f"missing accepted component adapter artifact kind(s): {', '.join(missing)}")

    registry_nodes = tuple(_require_nonempty(node_id, name="node_id") for node_id in node_ids)
    if len(set(registry_nodes)) != len(registry_nodes):
        raise ValueError("node_ids must not contain duplicates")
    artifact_nodes = {
        node_id
        for artifact in artifacts
        for node_id in artifact.node_ids
    }
    missing_coverage = sorted(set(registry_nodes).difference(artifact_nodes))
    if missing_coverage:
        raise ValueError(f"registry node_id(s) lack adapter artifact coverage: {', '.join(missing_coverage)}")

    weather_ids = {
        by_kind[kind].shared_weather_driver_id
        for kind in ("hp", "pv")
        if kind in by_kind
    }
    # The artifact bridge checks HP/PV pairing before a registry exists, so
    # later real integration cannot launder mismatched weather IDs into a plan.
    if weather_ids and (None in weather_ids or len(weather_ids) != 1):
        raise ValueError("HP and PV accepted adapter artifacts must share one weather driver")

    combined_metadata = {
        "artifact_bridge": {
            "accepted_artifacts": [
                by_kind[kind].manifest_record()
                for kind in required
            ],
        },
    }
    if metadata is not None:
        combined_metadata.update(metadata)
    return ComponentAdapterRegistry(
        registry_id=registry_id,
        node_ids=registry_nodes,
        skeletons=tuple(by_kind[kind].to_skeleton() for kind in required),
        required_component_kinds=required,
        metadata=combined_metadata,
    )


def assemble_net_load_from_registry_outputs(
    registry: ComponentAdapterRegistry,
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
    *,
    metadata: Mapping[str, object] | None = None,
) -> NetLoadResult:
    """Assemble synthetic/accepted outputs after registry metadata checks.

    The helper proves the accepted-metadata-to-IC-1 route without running IC-2
    loading, event detection, held-out adequacy, or probability calculations.
    """

    _validate_registry_outputs(registry, context, adapter_outputs)
    combined_metadata = {
        "adapter_registry": registry.manifest_record(),
        "scaffold_only": True,
    }
    if metadata is not None:
        combined_metadata.update(metadata)
    return assemble_net_load_from_real_component_outputs(
        build_ic1_assembly_plan_from_registry(registry),
        context,
        adapter_outputs,
        required_real_component_kinds=registry.required_component_kinds,
        metadata=combined_metadata,
    )


def validate_real_component_adapter_readiness(
    adapter_outputs: Sequence[ComponentAdapterOutput],
    *,
    required_real_component_kinds: Sequence[ComponentKind] = REAL_COMPONENT_WIRING_KINDS,
) -> dict[str, object]:
    """Return manifestable readiness metadata for future real-component wiring."""

    if not adapter_outputs:
        raise ValueError("adapter_outputs must not be empty")
    required = tuple(required_real_component_kinds)
    if not required:
        raise ValueError("required_real_component_kinds must not be empty")
    for kind in required:
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("required_real_component_kinds must contain valid component kinds")

    by_kind: dict[ComponentKind, list[ComponentAdapterOutput]] = {}
    status_by_component_id: dict[str, str] = {}
    for output in adapter_outputs:
        by_kind.setdefault(output.kind, []).append(output)
        status = output.metadata.get("artifact_status")
        if status not in ALLOWED_COMPONENT_ARTIFACT_STATUSES:
            raise ValueError("adapter output metadata must include a valid artifact_status")
        status_by_component_id[output.component_id] = str(status)

    missing = [kind for kind in required if kind not in by_kind]
    if missing:
        raise ValueError(f"missing real-component adapter output kind(s): {', '.join(missing)}")

    # Accepted/scaffold/synthetic status is kept with each component so future
    # manifests cannot make real C-owned artifacts and synthetic placeholders
    # look interchangeable after IC-1 aggregation.
    return {
        "required_real_component_kinds": tuple(required),
        "present_component_kinds": tuple(sorted(by_kind)),
        "artifact_status_by_component_id": dict(sorted(status_by_component_id.items())),
    }


def validate_component_adapter_skeletons(
    skeletons: Sequence[ComponentAdapterSkeleton],
    *,
    required_component_kinds: Sequence[ComponentKind] = REAL_COMPONENT_WIRING_KINDS,
) -> dict[str, object]:
    """Return manifestable metadata-only readiness for future real adapters."""

    if not skeletons:
        raise ValueError("skeletons must not be empty")
    required = tuple(required_component_kinds)
    if not required:
        raise ValueError("required_component_kinds must not be empty")
    for kind in required:
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("required_component_kinds must contain valid component kinds")

    by_kind: dict[ComponentKind, ComponentAdapterSkeleton] = {}
    for skeleton in skeletons:
        if skeleton.kind in by_kind:
            raise ValueError("component adapter skeleton kinds must be unique")
        by_kind[skeleton.kind] = skeleton

    missing = [kind for kind in required if kind not in by_kind]
    if missing:
        raise ValueError(f"missing component adapter skeleton kind(s): {', '.join(missing)}")

    calendar_ids = {skeleton.calendar_id for skeleton in skeletons}
    if len(calendar_ids) != 1:
        raise ValueError("component adapter skeletons must share one calendar_id")

    weather_ids = {
        by_kind[kind].shared_weather_driver_id
        for kind in ("hp", "pv")
        if kind in by_kind
    }
    # WEATHER-001 pairing is checked at metadata-readiness time so a future real
    # adapter cannot pass review with HP/PV placeholders that later diverge.
    if weather_ids and (None in weather_ids or len(weather_ids) != 1):
        raise ValueError("HP and PV adapter skeletons must share one weather driver")

    required_skeletons = tuple(by_kind[kind] for kind in required)
    ready_for_real_arrays = all(
        skeleton.artifact_status == "accepted" and not skeleton.blocking_items
        for skeleton in required_skeletons
    )
    return {
        "required_component_kinds": tuple(required),
        "present_component_kinds": tuple(sorted(by_kind)),
        "ready_for_real_arrays": ready_for_real_arrays,
        "artifact_status_by_kind": {
            kind: by_kind[kind].artifact_status
            for kind in sorted(by_kind)
        },
        "blocking_items_by_kind": {
            kind: by_kind[kind].blocking_items
            for kind in sorted(by_kind)
            if by_kind[kind].blocking_items
        },
        "calendar_id_by_kind": {
            kind: by_kind[kind].calendar_id
            for kind in sorted(by_kind)
        },
        "node_ids_by_kind": {
            kind: by_kind[kind].node_ids
            for kind in sorted(by_kind)
        },
        "shared_weather_driver_id": next(iter(weather_ids)) if weather_ids else None,
        "skeletons": [skeleton.manifest_record() for skeleton in required_skeletons],
    }


def build_net_load_result(
    components: Sequence[NetLoadComponent],
    *,
    metadata: Mapping[str, object] | None = None,
) -> NetLoadResult:
    """Aggregate aligned components into a deterministic IC-1 result.

    The helper is intentionally small: it validates calendar/provenance
    invariants and sums active/reactive power by node, but performs no
    congestion calculation or event detection.
    """

    if not components:
        raise ValueError("components must not be empty")
    reference_calendar = components[0].timestamps
    for component in components[1:]:
        if not np.array_equal(component.timestamps, reference_calendar):
            raise ValueError("all components must use the same 15-minute calendar")

    _validate_shared_weather_identity(components)
    node_ids = tuple(dict.fromkeys(component.provenance.node_id for component in components))
    node_index = {node_id: index for index, node_id in enumerate(node_ids)}
    p_net_kw = np.zeros((len(node_ids), reference_calendar.size), dtype=float)
    q_net_kvar = np.zeros_like(p_net_kw)
    for component in components:
        row = node_index[component.provenance.node_id]
        p_net_kw[row] += component.p_kw
        q_net_kvar[row] += component.q_kvar

    weather_ids = tuple(
        sorted(
            {
                component.provenance.shared_weather_driver_id
                for component in components
                if component.provenance.shared_weather_driver_id is not None
            }
        )
    )
    return NetLoadResult(
        p_net_kw=p_net_kw,
        q_net_kvar=q_net_kvar,
        timestamps=reference_calendar,
        node_ids=node_ids,
        component_provenance=tuple(component.provenance for component in components),
        shared_weather_driver_ids=weather_ids,
        metadata={} if metadata is None else metadata,
    )


def assemble_net_load_from_components(
    plan: NetLoadAssemblyPlan,
    components: Sequence[NetLoadComponent],
    *,
    metadata: Mapping[str, object] | None = None,
) -> NetLoadResult:
    """Assemble the synthetic IC-1 integration harness output.

    This is the planned join point for baseline, EV, HP, PV, adoption, and
    flexibility components. It validates the integration invariants and sums
    P/Q by the plan's declared node order, but intentionally stops before IC-2
    loading, threshold, event, or adequacy analysis.
    """

    if not components:
        raise ValueError("components must not be empty")
    _validate_required_components(plan, components)
    node_index = {node_id: index for index, node_id in enumerate(plan.node_ids)}
    for component in components:
        if component.provenance.node_id not in node_index:
            raise ValueError("component node_id must appear in the assembly plan node_ids")

    reference_calendar = components[0].timestamps
    for component in components[1:]:
        if not np.array_equal(component.timestamps, reference_calendar):
            raise ValueError("all components must use the same 15-minute calendar")
    _validate_shared_weather_identity(components)

    p_net_kw = np.zeros((len(plan.node_ids), reference_calendar.size), dtype=float)
    q_net_kvar = np.zeros_like(p_net_kw)
    for component in components:
        row = node_index[component.provenance.node_id]
        p_net_kw[row] += component.p_kw
        q_net_kvar[row] += component.q_kvar

    combined_metadata = dict(plan.metadata)
    if metadata is not None:
        combined_metadata.update(metadata)
    combined_metadata.setdefault("assembly", "synthetic_ic1_harness")

    weather_ids = tuple(
        sorted(
            {
                component.provenance.shared_weather_driver_id
                for component in components
                if component.provenance.shared_weather_driver_id is not None
            }
        )
    )
    return NetLoadResult(
        p_net_kw=p_net_kw,
        q_net_kvar=q_net_kvar,
        timestamps=reference_calendar,
        node_ids=plan.node_ids,
        component_provenance=tuple(component.provenance for component in components),
        shared_weather_driver_ids=weather_ids,
        metadata=combined_metadata,
    )


def validate_net_load_result(result: NetLoadResult) -> None:
    """Validate an IC-1 result and raise on contract violations."""

    NetLoadResult(
        p_net_kw=result.p_net_kw,
        q_net_kvar=result.q_net_kvar,
        timestamps=result.timestamps,
        node_ids=result.node_ids,
        component_provenance=result.component_provenance,
        shared_weather_driver_ids=result.shared_weather_driver_ids,
        metadata=result.metadata,
    )


_VALID_COMPONENT_KINDS = frozenset(ComponentKind.__args__)


def _skeletons_by_kind(registry: ComponentAdapterRegistry) -> dict[ComponentKind, ComponentAdapterSkeleton]:
    return {skeleton.kind: skeleton for skeleton in registry.skeletons}


def _validate_registry_outputs(
    registry: ComponentAdapterRegistry,
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
) -> None:
    if not adapter_outputs:
        raise ValueError("adapter_outputs must not be empty")
    skeleton_by_kind = _skeletons_by_kind(registry)
    registry_weather_id = registry.manifest_record()["readiness"]["shared_weather_driver_id"]
    if registry_weather_id != context.shared_weather_driver_id:
        raise ValueError("adapter registry weather identity must match the realization context")
    for output in adapter_outputs:
        if output.kind not in skeleton_by_kind:
            raise ValueError("adapter output kind must appear in the adapter registry")
        skeleton = skeleton_by_kind[output.kind]
        if output.node_id not in skeleton.node_ids:
            raise ValueError("adapter output node_id must appear in the matching skeleton")
        if output.source_id != skeleton.source_id:
            raise ValueError("adapter output source_id must match the matching skeleton")
        if output.member_id != skeleton.member_id:
            raise ValueError("adapter output member_id must match the matching skeleton")
        if output.metadata.get("artifact_status") != skeleton.artifact_status:
            raise ValueError("adapter output artifact_status must match the matching skeleton")
        if output.metadata.get("calendar_id") != skeleton.calendar_id:
            raise ValueError("adapter output calendar_id must match the matching skeleton")


def _component_streams_by_name(context: NetLoadRealizationContext) -> dict[str, ComponentStream]:
    return {stream.component: stream for stream in context.component_streams}


def _as_power_vector(values: np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    if array.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _as_15_minute_calendar(values: np.ndarray) -> np.ndarray:
    timestamps = np.asarray(values)
    if timestamps.ndim != 1:
        raise ValueError("timestamps must be a one-dimensional array")
    if timestamps.size == 0:
        raise ValueError("timestamps must not be empty")
    if not np.issubdtype(timestamps.dtype, np.datetime64):
        raise TypeError("timestamps must use numpy.datetime64 values")
    if np.isnat(timestamps).any():
        raise ValueError("timestamps must not contain NaT")
    if timestamps.size > 1:
        cadence_s = np.diff(timestamps).astype("timedelta64[s]").astype(np.int64)
        if not np.all(cadence_s == 900):
            raise ValueError("timestamps must form a complete 15-minute calendar")
    return timestamps.astype("datetime64[s]")


def _require_nonempty(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_nonempty_mapping_values(mapping: Mapping[str, object], *, name: str) -> None:
    for key, value in mapping.items():
        _require_nonempty(key, name=f"{name} key")
        if value is None:
            raise ValueError(f"{name} values must not be None")
        if isinstance(value, str) and not value:
            raise ValueError(f"{name} string values must be non-empty")


def _validate_shared_weather_identity(components: Sequence[NetLoadComponent]) -> None:
    weather_components = [
        component
        for component in components
        if component.provenance.kind in {"hp", "pv"}
    ]
    kinds = {component.provenance.kind for component in weather_components}
    if not {"hp", "pv"}.issubset(kinds):
        return
    ids = {component.provenance.shared_weather_driver_id for component in weather_components}
    # ALEA-001 requires HP and PV to consume one paired weather member when both
    # are present; accepting missing or divergent IDs would hide a broken sample.
    if None in ids or len(ids) != 1:
        raise ValueError("HP and PV components must share one shared_weather_driver_id")


def _validate_required_components(
    plan: NetLoadAssemblyPlan,
    components: Sequence[NetLoadComponent],
) -> None:
    present = {component.provenance.kind for component in components}
    missing = [kind for kind in plan.required_component_kinds if kind not in present]
    if missing:
        raise ValueError(f"missing required component kind(s): {', '.join(missing)}")
