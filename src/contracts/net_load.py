"""Shared IC-1 NetLoadProvider scaffold and validators.

This module defines the Agent A-owned net-load boundary without binding it to
the unfinished E2 component implementations. It aggregates already-aligned
component trajectories and preserves the provenance needed by downstream
adequacy and physics checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence

import numpy as np

from src.contracts.loading_trajectory import LoadingTrajectoryPreRunConfig, TimeDomain
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
ExecutableInputArtifactStatus = Literal["accepted", "unsigned", "scaffold", "synthetic_fixture"]


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
DEFAULT_EXECUTABLE_BRIDGE_BLOCKER_IDS: tuple[str, ...] = (
    "A-013",
    "G2",
    "G1-A2",
    "A-016",
)

REGISTER_FILES: tuple[tuple[str, int, int, int], ...] = (
    ("registers/DECISIONS.md", 0, 6, 7),
    ("registers/ASSUMPTIONS.md", 0, 6, 7),
    ("registers/DATA_REGISTER.md", 0, 8, 9),
)
_UNSIGNED_REGISTER_STATUS_MARKERS = (
    "pending",
    "proposed",
    "superseded",
    "unsigned",
)


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
class ExecutableInputArtifact:
    """Metadata-only gate record for a future real IC-1 executable input.

    The record intentionally carries no trajectory arrays. It answers whether a
    component family is signed/versioned enough for an intended integration use
    before IC-1 is allowed to load real component outputs.
    """

    artifact_id: str
    kind: ComponentKind
    artifact_status: ExecutableInputArtifactStatus
    version_id: str
    source_id: str
    member_id: str
    calendar_id: str
    node_ids: tuple[str, ...]
    signed_register_ids: tuple[str, ...] = ()
    blocking_register_ids: tuple[str, ...] = ()
    timestep_seconds: int = 900
    shared_weather_driver_id: str | None = None
    manifest_path: str | None = None
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        artifact_id = _require_nonempty(self.artifact_id, name="artifact_id")
        if self.kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("kind must be a valid net-load component kind")
        if self.artifact_status not in _VALID_EXECUTABLE_INPUT_STATUSES:
            raise ValueError("artifact_status must be accepted, unsigned, scaffold, or synthetic_fixture")
        version_id = _require_nonempty(self.version_id, name="version_id")
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
            raise ValueError("weather-dependent executable inputs require shared_weather_driver_id")
        signed_register_ids = tuple(
            _require_nonempty(item, name="signed_register_id")
            for item in self.signed_register_ids
        )
        blocking_register_ids = tuple(
            _require_nonempty(item, name="blocking_register_id")
            for item in self.blocking_register_ids
        )
        if self.artifact_status == "accepted":
            if not signed_register_ids:
                raise ValueError("accepted executable inputs must cite signed_register_ids")
            if blocking_register_ids:
                raise ValueError("accepted executable inputs must not list blocking_register_ids")
        elif not blocking_register_ids:
            raise ValueError("non-accepted executable inputs must list blocking_register_ids")
        if self.manifest_path is None:
            if self.artifact_status == "accepted":
                raise ValueError("accepted executable inputs must cite manifest_path")
        else:
            _require_nonempty(self.manifest_path, name="manifest_path")
        _validate_nonempty_mapping_values(self.provenance, name="provenance")
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "version_id", version_id)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "member_id", member_id)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "signed_register_ids", signed_register_ids)
        object.__setattr__(self, "blocking_register_ids", blocking_register_ids)
        object.__setattr__(self, "timestep_seconds", int(self.timestep_seconds))
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    def manifest_record(self) -> dict[str, object]:
        """Return a JSON-manifestable executable-input gate record."""

        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "artifact_status": self.artifact_status,
            "version_id": self.version_id,
            "source_id": self.source_id,
            "member_id": self.member_id,
            "calendar_id": self.calendar_id,
            "node_ids": self.node_ids,
            "signed_register_ids": self.signed_register_ids,
            "blocking_register_ids": self.blocking_register_ids,
            "timestep_seconds": self.timestep_seconds,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "manifest_path": self.manifest_path,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class FutureLayerScreenPreflightConfig:
    """Metadata-only E3.S2b prerequisite screen configuration."""

    config_id: str
    scenario_ids: tuple[str, ...]
    planning_years: tuple[int, ...]
    rho_values: tuple[float, ...]
    node_ids: tuple[str, ...]
    time_domain: TimeDomain = "full_year"
    timestep_seconds: int = 900
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        config_id = _require_nonempty(self.config_id, name="config_id")
        if self.time_domain not in {"full_year", "window_set"}:
            raise ValueError("time_domain must be 'full_year' or 'window_set'")
        if (
            isinstance(self.timestep_seconds, bool)
            or not isinstance(self.timestep_seconds, int)
            or self.timestep_seconds != 900
        ):
            raise ValueError("timestep_seconds must be the 900-second IC-1 cadence")
        if not self.scenario_ids:
            raise ValueError("scenario_ids must not be empty")
        scenario_ids = tuple(_require_nonempty(item, name="scenario_id") for item in self.scenario_ids)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("scenario_ids must not contain duplicates")
        if not self.planning_years:
            raise ValueError("planning_years must not be empty")
        planning_years: list[int] = []
        for year in self.planning_years:
            if isinstance(year, bool) or not isinstance(year, int) or year <= 0:
                raise ValueError("planning_years must contain positive integers")
            planning_years.append(year)
        if len(set(planning_years)) != len(planning_years):
            raise ValueError("planning_years must not contain duplicates")
        if not self.rho_values:
            raise ValueError("rho_values must not be empty")
        rho_values: list[float] = []
        for rho in self.rho_values:
            value = float(rho)
            if not np.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("rho_values must be finite and in [0, 1]")
            rho_values.append(value)
        if len(set(rho_values)) != len(rho_values):
            raise ValueError("rho_values must not contain duplicates")
        if not self.node_ids:
            raise ValueError("node_ids must not be empty")
        node_ids = tuple(_require_nonempty(node_id, name="node_id") for node_id in self.node_ids)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node_ids must not contain duplicates")
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "config_id", config_id)
        object.__setattr__(self, "scenario_ids", scenario_ids)
        object.__setattr__(self, "planning_years", tuple(planning_years))
        object.__setattr__(self, "rho_values", tuple(rho_values))
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "timestep_seconds", int(self.timestep_seconds))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_record(self) -> dict[str, object]:
        """Return the planned screen metadata without executing the screen."""

        return {
            "config_id": self.config_id,
            "scenario_ids": self.scenario_ids,
            "planning_years": self.planning_years,
            "rho_values": self.rho_values,
            "node_ids": self.node_ids,
            "time_domain": self.time_domain,
            "timestep_seconds": self.timestep_seconds,
            "planned_case_count": len(self.scenario_ids) * len(self.planning_years) * len(self.rho_values),
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


@dataclass(frozen=True)
class NetLoadLoadingInputReadiness:
    """Validated IC-1 payload metadata for a future IC-2 loading-input call.

    The object is a readiness scaffold. It validates a net-load payload and
    records manifestable metadata, but it does not calculate transformer
    loading, thresholds, event episodes, adequacy, or probabilities.
    """

    net_load: NetLoadResult
    registry_manifest: Mapping[str, object]
    realization_context_manifest: Mapping[str, object]
    planning_year: int = 2035
    timestep_seconds: int = 900
    time_domain: TimeDomain = "full_year"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.planning_year, bool) or not isinstance(self.planning_year, int):
            raise TypeError("planning_year must be an integer")
        if self.planning_year != 2035:
            raise ValueError("loading-input readiness currently requires the G0-A4 2035 planning year")
        if (
            isinstance(self.timestep_seconds, bool)
            or not isinstance(self.timestep_seconds, int)
            or self.timestep_seconds != 900
        ):
            raise ValueError("timestep_seconds must be the 900-second IC-1 cadence")
        if self.time_domain not in {"full_year", "window_set"}:
            raise ValueError("time_domain must be 'full_year' or 'window_set'")
        validate_net_load_result(self.net_load)
        _validate_loading_input_calendar(
            self.net_load.timestamps,
            planning_year=self.planning_year,
            timestep_seconds=self.timestep_seconds,
            time_domain=self.time_domain,
        )
        _validate_nonempty_mapping_values(self.registry_manifest, name="registry_manifest")
        _validate_nonempty_mapping_values(
            self.realization_context_manifest,
            name="realization_context_manifest",
        )
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "registry_manifest", MappingProxyType(dict(self.registry_manifest)))
        object.__setattr__(
            self,
            "realization_context_manifest",
            MappingProxyType(dict(self.realization_context_manifest)),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_record(self) -> dict[str, object]:
        """Return array-free metadata for later runner manifests."""

        return {
            "planning_year": self.planning_year,
            "time_domain": self.time_domain,
            "primary_probability_domain": self.time_domain == "full_year",
            "timestep_seconds": self.timestep_seconds,
            "timestep_count": int(self.net_load.timestamps.size),
            "calendar_start": str(self.net_load.timestamps[0]),
            "calendar_end": str(self.net_load.timestamps[-1]),
            "node_ids": self.net_load.node_ids,
            "component_provenance": [
                {
                    "component_id": item.component_id,
                    "kind": item.kind,
                    "node_id": item.node_id,
                    "member_id": item.member_id,
                    "source_id": item.source_id,
                    "shared_weather_driver_id": item.shared_weather_driver_id,
                    "metadata": dict(item.metadata),
                }
                for item in self.net_load.component_provenance
            ],
            "shared_weather_driver_ids": self.net_load.shared_weather_driver_ids,
            "registry_manifest": dict(self.registry_manifest),
            "realization_context_manifest": dict(self.realization_context_manifest),
            "metadata": dict(self.metadata),
        }

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


@dataclass(frozen=True)
class GatedAdapterBackedNetLoadProvider:
    """Adapter-backed IC-1 provider guarded by executable-input metadata."""

    plan: NetLoadAssemblyPlan
    adapters: tuple[NetLoadComponentAdapter, ...]
    executable_input_artifacts: tuple[ExecutableInputArtifact, ...]
    intended_use: str = "ic1_real_component_integration"
    calendar_metadata: Mapping[str, object] = field(default_factory=dict)
    mapping_version_metadata: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapters:
            raise ValueError("adapters must not be empty")
        if not self.executable_input_artifacts:
            raise ValueError("executable_input_artifacts must not be empty")
        _require_nonempty(self.intended_use, name="intended_use")
        _validate_nonempty_mapping_values(self.calendar_metadata, name="calendar_metadata")
        _validate_nonempty_mapping_values(self.mapping_version_metadata, name="mapping_version_metadata")
        _validate_nonempty_mapping_values(self.metadata, name="metadata")
        object.__setattr__(self, "adapters", tuple(self.adapters))
        object.__setattr__(self, "executable_input_artifacts", tuple(self.executable_input_artifacts))
        object.__setattr__(self, "calendar_metadata", MappingProxyType(dict(self.calendar_metadata)))
        object.__setattr__(self, "mapping_version_metadata", MappingProxyType(dict(self.mapping_version_metadata)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def preflight(self) -> dict[str, object]:
        """Return manifestable readiness metadata before arrays are loaded."""

        return validate_executable_input_gate(
            self.executable_input_artifacts,
            required_component_kinds=self.plan.required_component_kinds,
            intended_use=self.intended_use,
        )

    def get_net_load(
        self,
        scenario: str,
        year: int,
        time_domain: TimeDomain,
        rho: float,
        seed: int,
    ) -> NetLoadResult:
        """Return IC-1 net load only after executable inputs pass preflight."""

        gate_manifest = self.preflight()
        context = build_realization_context(
            scenario=scenario,
            year=year,
            time_domain=time_domain,
            rho=rho,
            seed=seed,
            shared_weather_driver_id=gate_manifest["shared_weather_driver_id"],
            calendar_metadata=self.calendar_metadata,
            mapping_version_metadata=self.mapping_version_metadata,
        )
        outputs: list[ComponentAdapterOutput] = []
        for adapter in self.adapters:
            outputs.extend(adapter.get_component_outputs(context, self.plan.node_ids))
        # The gate is evaluated before adapter calls so unsigned real artifacts
        # cannot leak arrays into IC-1 under a synthetic-looking manifest.
        return assemble_net_load_from_adapter_outputs(
            self.plan,
            context,
            outputs,
            metadata={
                "provider": "gated_adapter_backed_ic1_preflight",
                "executable_input_gate": gate_manifest,
                "scaffold_only": True,
                **dict(self.metadata),
            },
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

    registry_output_readiness = validate_registry_adapter_output_readiness(
        registry,
        context,
        adapter_outputs,
    )
    combined_metadata = {
        "adapter_registry": registry.manifest_record(),
        "registry_output_readiness": registry_output_readiness,
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


def prepare_executable_net_load_assembly_from_artifacts(
    *,
    assembly_id: str,
    executable_input_artifacts: Sequence[ExecutableInputArtifact],
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    intended_use: str = "ic1_real_component_integration",
    planning_year: int = 2035,
    time_domain: TimeDomain = "full_year",
    metadata: Mapping[str, object] | None = None,
) -> NetLoadLoadingInputReadiness:
    """Validate accepted executable artifacts through the IC-1 assembly boundary.

    This is the dry join point for future real E2 artifacts. It builds the
    registry from artifact metadata, assembles only caller-supplied fixture or
    adapter outputs, and stops at the loading-input contract before any IC-2
    loading, threshold, event, probability, or capacity-screen step.
    """

    assembly_id = _require_nonempty(assembly_id, name="assembly_id")
    required = tuple(required_component_kinds)
    gate_manifest = validate_executable_input_gate(
        executable_input_artifacts,
        required_component_kinds=required,
        intended_use=intended_use,
    )
    artifact_by_kind = {artifact.kind: artifact for artifact in executable_input_artifacts}
    accepted_artifacts = tuple(
        AcceptedComponentAdapterArtifact(
            artifact_id=artifact_by_kind[kind].artifact_id,
            kind=kind,
            source_id=artifact_by_kind[kind].source_id,
            member_id=artifact_by_kind[kind].member_id,
            node_ids=artifact_by_kind[kind].node_ids,
            calendar_id=artifact_by_kind[kind].calendar_id,
            timestep_seconds=artifact_by_kind[kind].timestep_seconds,
            shared_weather_driver_id=artifact_by_kind[kind].shared_weather_driver_id,
            provenance={
                "executable_manifest_path": artifact_by_kind[kind].manifest_path,
                "executable_version_id": artifact_by_kind[kind].version_id,
                "signed_register_ids": artifact_by_kind[kind].signed_register_ids,
                "source_provenance": dict(artifact_by_kind[kind].provenance),
            },
        )
        for kind in required
    )
    registry = build_component_adapter_registry_from_artifacts(
        registry_id=f"{assembly_id}:adapter-registry",
        node_ids=tuple(
            dict.fromkeys(
                node_id
                for kind in required
                for node_id in artifact_by_kind[kind].node_ids
            )
        ),
        artifacts=accepted_artifacts,
        required_component_kinds=required,
        metadata={
            "assembly_id": assembly_id,
            "executable_input_gate": gate_manifest,
            "governed_event_metadata": {
                "basis": "G0-A3",
                "primary_threshold_pu": 1.0,
                "strict_import_loading_gt_threshold": True,
                "min_consecutive_15_minute_steps": 4,
                "not_evaluated_here": True,
            },
        },
    )
    readiness_metadata = {
        "source": "executable_artifact_assembly_scaffold",
        "assembly_id": assembly_id,
        "scaffold_only": True,
        "no_event_detection": True,
        "no_probability_estimate": True,
        "no_capacity_screen_result": True,
    }
    if metadata is not None:
        readiness_metadata.update(metadata)
    # Fail-closed before loading inputs: unsigned or register-mismatched
    # artifacts never reach this point, and the returned payload is still only
    # a validated loading-input scaffold for future IC-2 calls.
    return prepare_loading_input_from_registry_outputs(
        registry,
        context,
        adapter_outputs,
        planning_year=planning_year,
        time_domain=time_domain,
        metadata=readiness_metadata,
    )


def validate_registry_adapter_output_readiness(
    registry: ComponentAdapterRegistry,
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
) -> dict[str, object]:
    """Return array-free readiness metadata for registry-backed adapter outputs."""

    _validate_registry_outputs(registry, context, adapter_outputs)
    stream_by_component = _component_streams_by_name(context)
    output_records: list[dict[str, object]] = []
    for output in adapter_outputs:
        if output.kind not in stream_by_component:
            raise ValueError("adapter output kind must have a matching realization component stream")
        expected_stream = stream_by_component[output.kind]
        # Registry/source metadata can match while CRN provenance drifts; record
        # and validate stream identity before arrays are aggregated away.
        if output.stream_id != expected_stream.stream_id:
            raise ValueError("adapter output stream_id must match the realization context")
        if output.kind in {"hp", "pv"} and output.shared_weather_driver_id != context.shared_weather_driver_id:
            raise ValueError("weather-dependent adapter outputs must use the context shared_weather_driver_id")
        output_records.append(
            {
                "component_id": output.component_id,
                "kind": output.kind,
                "node_id": output.node_id,
                "source_id": output.source_id,
                "member_id": output.member_id,
                "stream_id": output.stream_id,
                "shared_weather_driver_id": output.shared_weather_driver_id,
                "artifact_status": output.metadata.get("artifact_status"),
                "calendar_id": output.metadata.get("calendar_id"),
            }
        )

    real_component_readiness = validate_real_component_adapter_readiness(
        adapter_outputs,
        required_real_component_kinds=registry.required_component_kinds,
    )
    return {
        "registry_id": registry.registry_id,
        "context_aleatory_identity": context.aleatory_identity(),
        "planning_year": context.planning_year,
        "time_domain": context.time_domain,
        "shared_weather_driver_id": context.shared_weather_driver_id,
        "node_ids": registry.node_ids,
        "component_count": len(output_records),
        "component_outputs": tuple(output_records),
        "real_component_readiness": real_component_readiness,
    }


def prepare_loading_input_from_registry_outputs(
    registry: ComponentAdapterRegistry,
    context: NetLoadRealizationContext,
    adapter_outputs: Sequence[ComponentAdapterOutput],
    *,
    planning_year: int = 2035,
    time_domain: TimeDomain = "full_year",
    metadata: Mapping[str, object] | None = None,
) -> NetLoadLoadingInputReadiness:
    """Validate accepted-artifact outputs up to the loading-input boundary."""

    if context.planning_year != planning_year:
        raise ValueError("realization context planning_year must match loading-input planning_year")
    if context.time_domain != time_domain:
        raise ValueError("realization context time_domain must match loading-input time_domain")
    net_load = assemble_net_load_from_registry_outputs(
        registry,
        context,
        adapter_outputs,
        metadata={"loading_input_readiness": True},
    )
    readiness_metadata = {
        "source": "accepted_artifact_bridge",
        "scaffold_only": True,
    }
    if metadata is not None:
        readiness_metadata.update(metadata)
    return NetLoadLoadingInputReadiness(
        net_load=net_load,
        registry_manifest=registry.manifest_record(),
        realization_context_manifest=context.manifest_metadata(),
        planning_year=planning_year,
        timestep_seconds=900,
        time_domain=time_domain,
        metadata=readiness_metadata,
    )

def validate_executable_input_gate(
    artifacts: Sequence[ExecutableInputArtifact],
    *,
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    intended_use: str = "ic1_real_component_integration",
) -> dict[str, object]:
    """Validate that real-component inputs are signed enough before execution.

    This gate is metadata-only. It does not load arrays, assemble net load, run
    IC-2, or classify events; it prevents those later steps from starting when
    a required component family is still unsigned or only scaffolded.
    """

    if not artifacts:
        raise ValueError("executable input artifacts must not be empty")
    intended_use = _require_nonempty(intended_use, name="intended_use")
    required = tuple(required_component_kinds)
    if not required:
        raise ValueError("required_component_kinds must not be empty")
    for kind in required:
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("required_component_kinds must contain valid component kinds")

    by_kind: dict[ComponentKind, ExecutableInputArtifact] = {}
    for artifact in artifacts:
        if artifact.kind in by_kind:
            raise ValueError("executable input artifact kinds must be unique")
        by_kind[artifact.kind] = artifact

    missing = [kind for kind in required if kind not in by_kind]
    if missing:
        raise ValueError(f"missing executable input artifact kind(s): {', '.join(missing)}")

    required_artifacts = tuple(by_kind[kind] for kind in required)
    calendar_ids = {artifact.calendar_id for artifact in required_artifacts}
    if len(calendar_ids) != 1:
        raise ValueError("executable input artifacts must share one calendar_id")
    cadence_values = {artifact.timestep_seconds for artifact in required_artifacts}
    if cadence_values != {900}:
        raise ValueError("executable input artifacts must use the 900-second IC-1 cadence")

    weather_ids = {
        by_kind[kind].shared_weather_driver_id
        for kind in ("hp", "pv")
        if kind in by_kind
    }
    # WEATHER-001/ALEA-001 pairing must be proven at the executable-input gate;
    # otherwise later manifests could combine HP and PV from different weather.
    if weather_ids and (None in weather_ids or len(weather_ids) != 1):
        raise ValueError("HP and PV executable input artifacts must share one weather driver")

    blockers: dict[str, tuple[str, ...]] = {}
    for artifact in required_artifacts:
        if artifact.artifact_status != "accepted":
            blockers[artifact.kind] = artifact.blocking_register_ids
    if blockers:
        details = "; ".join(
            f"{kind}: {', '.join(ids)}"
            for kind, ids in sorted(blockers.items())
        )
        raise ValueError(
            f"executable inputs are not signed enough for {intended_use}; "
            f"blocking register/decision ID(s): {details}"
        )

    _validate_artifact_register_backing(required_artifacts)

    return {
        "intended_use": intended_use,
        "ready_for_execution": True,
        "required_component_kinds": tuple(required),
        "present_component_kinds": tuple(sorted(by_kind)),
        "calendar_id": next(iter(calendar_ids)),
        "timestep_seconds": 900,
        "shared_weather_driver_id": next(iter(weather_ids)) if weather_ids else None,
        "signed_register_ids_by_kind": {
            artifact.kind: artifact.signed_register_ids
            for artifact in required_artifacts
        },
        "manifest_paths_by_kind": {
            artifact.kind: artifact.manifest_path
            for artifact in required_artifacts
            if artifact.manifest_path is not None
        },
        "artifacts": [artifact.manifest_record() for artifact in required_artifacts],
    }

def dry_run_integrated_input_preflight(
    config: FutureLayerScreenPreflightConfig,
    artifacts: Sequence[ExecutableInputArtifact],
    *,
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    missing_artifact_blockers: Mapping[str, Sequence[str]] | None = None,
    intended_use: str = "e3_s2b_integrated_input_preflight",
) -> dict[str, object]:
    """Summarize E3.S2 integrated-input readiness without executing IC-1.

    The dry run inventories accepted, missing, and blocked artifacts using the
    same register-backed acceptance rule as the executable gate. It returns a
    manifestable report even when inputs are incomplete, and it intentionally
    performs no array loading, net-load assembly, event detection, or capacity
    calculation.
    """

    required = tuple(required_component_kinds)
    if not required:
        raise ValueError("required_component_kinds must not be empty")
    for kind in required:
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("required_component_kinds must contain valid component kinds")
    blockers_by_kind = _normalized_blockers_by_kind(missing_artifact_blockers)
    by_kind: dict[ComponentKind, ExecutableInputArtifact] = {}
    for artifact in artifacts:
        if artifact.kind in by_kind:
            raise ValueError("executable input artifact kinds must be unique")
        by_kind[artifact.kind] = artifact

    component_reports: dict[str, dict[str, object]] = {}
    accepted_kinds: list[str] = []
    missing_kinds: list[str] = []
    blocked_kinds: list[str] = []
    for kind in required:
        artifact = by_kind.get(kind)
        if artifact is None:
            missing_kinds.append(kind)
            component_reports[kind] = {
                "kind": kind,
                "state": "missing",
                "accepted_for_gate": False,
                "blocking_register_ids": blockers_by_kind.get(kind, ("missing artifact metadata",)),
                "artifact": None,
            }
            continue
        report: dict[str, object] = {
            "kind": kind,
            "artifact_id": artifact.artifact_id,
            "artifact_status": artifact.artifact_status,
            "manifest_path": artifact.manifest_path,
            "signed_register_ids": artifact.signed_register_ids,
            "blocking_register_ids": artifact.blocking_register_ids,
            "artifact": artifact.manifest_record(),
        }
        if artifact.artifact_status != "accepted":
            blocked_kinds.append(kind)
            report.update(
                {
                    "state": "blocked",
                    "accepted_for_gate": False,
                    "reason": "artifact_status_not_accepted",
                }
            )
        else:
            register_failures = _register_backing_failures_for_artifact(artifact)
            if register_failures:
                blocked_kinds.append(kind)
                report.update(
                    {
                        "state": "blocked",
                        "accepted_for_gate": False,
                        "reason": "register_backing_not_accepted",
                        "register_backing_errors": tuple(register_failures),
                    }
                )
            else:
                accepted_kinds.append(kind)
                report.update({"state": "accepted", "accepted_for_gate": True})
        component_reports[kind] = report

    executable_input_gate: dict[str, object] | None = None
    gate_error: str | None = None
    if not missing_kinds and not blocked_kinds:
        try:
            executable_input_gate = validate_executable_input_gate(
                tuple(by_kind[kind] for kind in required),
                required_component_kinds=required,
                intended_use=intended_use,
            )
            if executable_input_gate["calendar_id"] != config.metadata.get("calendar_id", executable_input_gate["calendar_id"]):
                raise ValueError("screen preflight config calendar_id must match executable input artifacts")
        except ValueError as exc:
            gate_error = str(exc)

    ready_for_input_assembly = (
        executable_input_gate is not None
        and gate_error is None
        and not missing_kinds
        and not blocked_kinds
    )
    return {
        "intended_use": intended_use,
        "dry_run_only": True,
        "ready_for_input_assembly": ready_for_input_assembly,
        "screen_prerequisite_only": True,
        "no_real_net_load_arrays": True,
        "no_event_detection": True,
        "no_probability_estimate": True,
        "no_capacity_screen_result": True,
        "config_manifest": config.manifest_record(),
        "required_component_kinds": tuple(required),
        "present_component_kinds": tuple(sorted(by_kind)),
        "accepted_component_kinds": tuple(sorted(accepted_kinds)),
        "missing_component_kinds": tuple(missing_kinds),
        "blocked_component_kinds": tuple(blocked_kinds),
        "component_reports": component_reports,
        "gate_error": gate_error,
        "executable_input_gate": executable_input_gate,
    }

def build_executable_loading_bridge_preflight(
    config: FutureLayerScreenPreflightConfig,
    artifacts: Sequence[ExecutableInputArtifact],
    trajectory_config: LoadingTrajectoryPreRunConfig,
    *,
    capacity_provenance: Mapping[str, object] | None = None,
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    missing_artifact_blockers: Mapping[str, Sequence[str]] | None = None,
    downstream_blocker_ids: Sequence[str] = DEFAULT_EXECUTABLE_BRIDGE_BLOCKER_IDS,
    intended_use: str = "e3_s2_executable_loading_bridge_preflight",
) -> dict[str, object]:
    """Bridge IC-1 executable readiness to IC-2 trajectory manifest readiness.

    This is an array-free dry run. It proves the current artifact gate and the
    IC-2 pre-run metadata can be represented in one manifest-ready packet, but
    it does not assemble real net load, build loading arrays, detect events, or
    estimate probabilities.
    """

    if trajectory_config.timestep_seconds != config.timestep_seconds:
        raise ValueError("trajectory pre-run cadence must match the executable input config")
    if tuple(config.planning_years) != tuple(trajectory_config.planning_years):
        raise ValueError("trajectory pre-run planning_years must match the executable input config")

    dry_run = dry_run_integrated_input_preflight(
        config,
        artifacts,
        required_component_kinds=required_component_kinds,
        missing_artifact_blockers=missing_artifact_blockers,
        intended_use=intended_use,
    )
    capacity_record = _validate_bridge_capacity_provenance(capacity_provenance)
    downstream_blockers = tuple(
        _require_nonempty(blocker, name="downstream_blocker_id")
        for blocker in downstream_blocker_ids
    )
    component_blockers = {
        kind: tuple(report.get("blocking_register_ids", ()))
        for kind, report in dry_run["component_reports"].items()
        if report["state"] in {"missing", "blocked"}
    }
    register_backing_errors = {
        kind: tuple(report.get("register_backing_errors", ()))
        for kind, report in dry_run["component_reports"].items()
        if report.get("register_backing_errors")
    }
    ready_for_synthetic_loading_manifest = (
        dry_run["ready_for_input_assembly"] is True
        and dry_run["gate_error"] is None
        and capacity_record is not None
    )
    # A real first experiment requires signed downstream model-error, domain,
    # capacity, and scenario-consistency inputs; this bridge records that stop.
    ready_for_first_real_experiment = ready_for_synthetic_loading_manifest and not downstream_blockers

    return {
        "intended_use": intended_use,
        "dry_run_only": True,
        "metadata_preflight_only": True,
        "ready_for_ic1_input_assembly": dry_run["ready_for_input_assembly"],
        "ready_for_synthetic_loading_manifest": ready_for_synthetic_loading_manifest,
        "ready_for_first_real_experiment": ready_for_first_real_experiment,
        "no_real_net_load_arrays": True,
        "no_event_detection": True,
        "no_event_counts": True,
        "no_probability_estimate": True,
        "no_capacity_screen_result": True,
        "executable_input_preflight": dry_run,
        "trajectory_prerun_manifest": trajectory_config.manifest_record(),
        "capacity_provenance": capacity_record,
        "blockers": {
            "component_artifact_blockers_by_kind": component_blockers,
            "register_backing_errors_by_kind": register_backing_errors,
            "downstream_gate_blockers": downstream_blockers,
            "capacity_provenance_missing": capacity_record is None,
        },
        "manifest_fields": {
            "calendar_id": config.metadata.get("calendar_id"),
            "timestep_seconds": config.timestep_seconds,
            "planning_years": config.planning_years,
            "required_component_kinds": tuple(required_component_kinds),
            "governed_event_metadata": trajectory_config.manifest_record()["governed_event_metadata"],
            "capacity_provenance": capacity_record,
            "component_artifact_manifest_paths": (
                dry_run["executable_input_gate"]["manifest_paths_by_kind"]
                if dry_run["executable_input_gate"] is not None
                else {}
            ),
        },
    }


def build_real_artifact_assembly_preflight(
    config: FutureLayerScreenPreflightConfig,
    artifacts: Sequence[ExecutableInputArtifact],
    trajectory_config: LoadingTrajectoryPreRunConfig,
    *,
    capacity_provenance: Mapping[str, object] | None = None,
    artifact_sha256_by_path: Mapping[str, str] | None = None,
    repo_root: str | Path | None = None,
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    missing_artifact_blockers: Mapping[str, Sequence[str]] | None = None,
    downstream_blocker_ids: Sequence[str] = DEFAULT_EXECUTABLE_BRIDGE_BLOCKER_IDS,
    intended_use: str = "e3_s2_real_artifact_assembly_preflight",
) -> dict[str, object]:
    """Build a path/checksum-aware real-artifact assembly dossier.

    The dossier composes the existing executable-input and IC-2 bridge gates,
    then validates only metadata packet existence/checksums. It deliberately
    never opens component trajectory arrays or produces loading/event results.
    """

    bridge = build_executable_loading_bridge_preflight(
        config,
        artifacts,
        trajectory_config,
        capacity_provenance=capacity_provenance,
        required_component_kinds=required_component_kinds,
        missing_artifact_blockers=missing_artifact_blockers,
        downstream_blocker_ids=downstream_blocker_ids,
        intended_use=intended_use,
    )
    root = (Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]).resolve()
    expected_checksums = dict(artifact_sha256_by_path or {})
    manifest_paths = {
        artifact.manifest_path
        for artifact in artifacts
        if artifact.manifest_path is not None
    }
    source_records: list[dict[str, object]] = []
    missing_paths: list[str] = []
    checksum_mismatches: list[dict[str, str]] = []
    for artifact in artifacts:
        if artifact.manifest_path is None:
            continue
        relative_path = _require_nonempty(artifact.manifest_path, name="artifact manifest_path")
        full_path = _resolve_repo_metadata_path(root, relative_path)
        exists = full_path.is_file()
        record: dict[str, object] = {
            "kind": artifact.kind,
            "artifact_id": artifact.artifact_id,
            "path": relative_path,
            "exists": exists,
            "artifact_status": artifact.artifact_status,
        }
        if exists:
            observed = _sha256_file(full_path)
            record["sha256"] = observed
            expected = expected_checksums.get(relative_path)
            if expected is not None:
                checksum_match = observed == expected
                record["expected_sha256"] = expected
                record["checksum_match"] = checksum_match
                if not checksum_match:
                    checksum_mismatches.append(
                        {"path": relative_path, "expected": expected, "observed": observed}
                    )
        else:
            missing_paths.append(relative_path)
        source_records.append(record)

    unmatched_expected_paths = tuple(
        sorted(path for path in expected_checksums if path not in manifest_paths)
    )
    source_artifacts_ready = not missing_paths and not checksum_mismatches and not unmatched_expected_paths
    ready_for_real_artifact_assembly = (
        bridge["ready_for_first_real_experiment"] is True
        and source_artifacts_ready
    )
    return {
        "intended_use": intended_use,
        "dry_run_only": True,
        "metadata_preflight_only": True,
        "ready_for_real_artifact_assembly": ready_for_real_artifact_assembly,
        "source_artifacts_ready": source_artifacts_ready,
        "no_real_net_load_arrays": True,
        "no_event_detection": True,
        "no_event_counts": True,
        "no_probability_estimate": True,
        "no_capacity_screen_result": True,
        "bridge_preflight": bridge,
        "source_artifact_records": tuple(source_records),
        "blockers": {
            **bridge["blockers"],
            "source_manifest_paths_missing": tuple(missing_paths),
            "source_manifest_checksum_mismatches": tuple(checksum_mismatches),
            "unmatched_expected_checksum_paths": unmatched_expected_paths,
        },
    }


def build_accepted_artifact_loader_blocker_preflight(
    config: FutureLayerScreenPreflightConfig,
    artifacts: Sequence[ExecutableInputArtifact],
    trajectory_config: LoadingTrajectoryPreRunConfig,
    *,
    capacity_provenance: Mapping[str, object] | None = None,
    artifact_sha256_by_path: Mapping[str, str] | None = None,
    component_output_manifest_paths_by_kind: Mapping[str, str] | None = None,
    component_output_manifest_sha256_by_path: Mapping[str, str] | None = None,
    missing_component_output_manifest_blockers: Mapping[str, Sequence[str]] | None = None,
    repo_root: str | Path | None = None,
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    missing_artifact_blockers: Mapping[str, Sequence[str]] | None = None,
    downstream_blocker_ids: Sequence[str] = DEFAULT_EXECUTABLE_BRIDGE_BLOCKER_IDS,
    intended_use: str = "e3_s2_accepted_artifact_loader_blocker_preflight",
) -> dict[str, object]:
    """Build a fail-closed blocker manifest before accepted-artifact loading."""

    base = build_real_artifact_assembly_preflight(
        config,
        artifacts,
        trajectory_config,
        capacity_provenance=capacity_provenance,
        artifact_sha256_by_path=artifact_sha256_by_path,
        repo_root=repo_root,
        required_component_kinds=required_component_kinds,
        missing_artifact_blockers=missing_artifact_blockers,
        downstream_blocker_ids=downstream_blocker_ids,
        intended_use=intended_use,
    )
    root = (Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]).resolve()
    source_checksums = dict(artifact_sha256_by_path or {})
    component_manifest_paths = dict(component_output_manifest_paths_by_kind or {})
    component_manifest_checksums = dict(component_output_manifest_sha256_by_path or {})
    component_missing_blockers = _normalized_blockers_by_kind(
        missing_component_output_manifest_blockers,
    )
    required = tuple(required_component_kinds)
    artifact_by_kind = {artifact.kind: artifact for artifact in artifacts}
    blocker_items: list[dict[str, object]] = []

    for artifact in artifacts:
        if artifact.manifest_path is None:
            _append_loader_blocker(
                blocker_items,
                "source_manifest_path_missing",
                "executable input artifact does not cite a source manifest path",
                kind=artifact.kind,
                artifact_id=artifact.artifact_id,
                blocker_ids=artifact.blocking_register_ids,
            )
            continue
        # Without an expected digest, a later metadata refresh could silently change
        # which component artifact is admitted before any scientific run starts.
        if artifact.manifest_path not in source_checksums:
            _append_loader_blocker(
                blocker_items,
                "source_manifest_expected_checksum_missing",
                "source manifest must have a version-controlled expected SHA-256 before loader use",
                kind=artifact.kind,
                artifact_id=artifact.artifact_id,
                path=artifact.manifest_path,
                blocker_ids=(f"E3.S2-{artifact.kind.upper()}-SOURCE-CHECKSUM",),
            )

    _append_bridge_blockers(blocker_items, base)
    _append_cross_component_metadata_blockers(blocker_items, artifacts)

    component_records: list[dict[str, object]] = []
    for kind in required:
        artifact = artifact_by_kind.get(kind)
        manifest_path = component_manifest_paths.get(kind)
        if artifact is None:
            _append_loader_blocker(
                blocker_items,
                "required_component_artifact_missing",
                "required executable input artifact is absent",
                kind=kind,
                blocker_ids=component_missing_blockers.get(kind, (f"E3.S2-{kind.upper()}-EXECUTABLE-ARTIFACT",)),
            )
            continue
        # The loader boundary requires an accepted component-output manifest before
        # an array path becomes executable; source readiness alone is not enough.
        if manifest_path is None:
            _append_loader_blocker(
                blocker_items,
                "component_output_manifest_missing",
                "accepted component-output manifest is required before artifact-loader execution",
                kind=kind,
                artifact_id=artifact.artifact_id,
                blocker_ids=component_missing_blockers.get(kind, (f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-ARTIFACT",)),
            )
            component_records.append(
                {
                    "kind": kind,
                    "artifact_id": artifact.artifact_id,
                    "path": None,
                    "state": "missing",
                }
            )
            continue
        record, record_blockers = _component_output_manifest_preflight_record(
            root,
            kind=kind,
            path=manifest_path,
            expected_sha256=component_manifest_checksums.get(manifest_path),
            executable_artifact=artifact,
        )
        component_records.append(record)
        blocker_items.extend(record_blockers)

    blocked_kinds = tuple(
        sorted(
            {
                str(item["kind"])
                for item in blocker_items
                if item.get("kind") in _VALID_COMPONENT_KINDS
            }
        )
    )
    ready_for_artifact_loader_execution = (
        base["ready_for_real_artifact_assembly"] is True
        and not blocker_items
    )
    return {
        "intended_use": intended_use,
        "metadata_preflight_only": True,
        "ready_for_artifact_loader_execution": ready_for_artifact_loader_execution,
        "ready_for_integrated_trajectory_acceptance": ready_for_artifact_loader_execution,
        "no_component_array_loading": True,
        "no_real_net_load_arrays": True,
        "no_event_detection": True,
        "no_event_counts": True,
        "no_probability_estimate": True,
        "no_capacity_screen_result": True,
        "real_artifact_preflight": base,
        "component_output_manifest_records": tuple(component_records),
        "blocker_manifest": {
            "ready": ready_for_artifact_loader_execution,
            "blocked_component_kinds": blocked_kinds,
            "blocker_count": len(blocker_items),
            "items": tuple(blocker_items),
        },
    }


def validate_future_layer_screen_preflight(
    config: FutureLayerScreenPreflightConfig,
    artifacts: Sequence[ExecutableInputArtifact],
    *,
    required_component_kinds: Sequence[ComponentKind] = REQUIRED_INTEGRATION_COMPONENT_KINDS,
    missing_artifact_blockers: Mapping[str, Sequence[str]] | None = None,
    intended_use: str = "e3_s2b_future_layer_screen_prerequisite",
) -> dict[str, object]:
    """Validate E3.S2b input readiness before any screen can execute.

    The helper intentionally produces only prerequisite metadata. It does not
    assemble real net load, call IC-2, evaluate thresholds, or calculate any
    capacity-screen quantity.
    """

    required = tuple(required_component_kinds)
    if not required:
        raise ValueError("required_component_kinds must not be empty")
    for kind in required:
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("required_component_kinds must contain valid component kinds")
    blockers_by_kind = _normalized_blockers_by_kind(missing_artifact_blockers)
    by_kind: dict[ComponentKind, ExecutableInputArtifact] = {}
    for artifact in artifacts:
        if artifact.kind in by_kind:
            raise ValueError("executable input artifact kinds must be unique")
        by_kind[artifact.kind] = artifact

    missing = [kind for kind in required if kind not in by_kind]
    if missing:
        details = "; ".join(
            f"{kind}: {', '.join(blockers_by_kind.get(kind, ('missing artifact metadata',)))}"
            for kind in missing
        )
        raise ValueError(f"missing executable input artifact(s) for {intended_use}: {details}")

    gate_manifest = validate_executable_input_gate(
        tuple(by_kind[kind] for kind in required),
        required_component_kinds=required,
        intended_use=intended_use,
    )
    if gate_manifest["calendar_id"] != config.metadata.get("calendar_id", gate_manifest["calendar_id"]):
        raise ValueError("screen preflight config calendar_id must match executable input artifacts")
    # E3.S2b must be able to freeze a future-layer domain later, but this
    # preflight record deliberately contains no threshold or capacity result.
    return {
        "intended_use": intended_use,
        "ready_for_input_assembly": True,
        "screen_prerequisite_only": True,
        "no_event_detection": True,
        "no_capacity_screen_result": True,
        "config_manifest": config.manifest_record(),
        "executable_input_gate": gate_manifest,
        "manifest_fields": {
            "component_artifacts": gate_manifest["artifacts"],
            "planned_screen_cases": config.manifest_record(),
            "signed_register_ids_by_kind": gate_manifest["signed_register_ids_by_kind"],
            "manifest_paths_by_kind": gate_manifest["manifest_paths_by_kind"],
            "shared_weather_driver_id": gate_manifest["shared_weather_driver_id"],
        },
    }

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


def load_component_adapter_output_from_npz_artifact(
    manifest: Mapping[str, object],
    context: NetLoadRealizationContext,
    *,
    repo_root: Path | str | None = None,
    expected_calendar_id: str | None = None,
    expected_node_ids: Sequence[str] | None = None,
    allow_synthetic_fixture: bool = False,
) -> ComponentAdapterOutput:
    """Load one accepted component-output NPZ artifact into IC-1 adapter form."""

    if not isinstance(manifest, Mapping):
        raise TypeError("component output artifact manifest must be a mapping")
    artifact_status = _require_nonempty(
        _require_manifest_text(manifest, "artifact_status"),
        name="artifact_status",
    )
    if artifact_status == "synthetic_fixture":
        if not allow_synthetic_fixture:
            raise ValueError(
                "synthetic_fixture component output artifacts require allow_synthetic_fixture=True"
            )
    elif artifact_status != "accepted":
        raise ValueError("component output artifact status must be accepted before array loading")

    kind = _require_component_kind(manifest.get("kind"))
    component_id = _require_nonempty(_require_manifest_text(manifest, "component_id"), name="component_id")
    node_id = _require_nonempty(_require_manifest_text(manifest, "node_id"), name="node_id")
    member_id = _require_nonempty(_require_manifest_text(manifest, "member_id"), name="member_id")
    source_id = _require_nonempty(_require_manifest_text(manifest, "source_id"), name="source_id")
    calendar_id = _require_nonempty(_require_manifest_text(manifest, "calendar_id"), name="calendar_id")
    if expected_calendar_id is not None and calendar_id != expected_calendar_id:
        raise ValueError("component output artifact calendar_id must match the expected calendar")
    _validate_expected_node_id(node_id, expected_node_ids)
    timestep_seconds = _require_900_second_cadence(manifest.get("timestep_seconds"))
    shared_weather_driver_id = _optional_nonempty_text(
        manifest.get("shared_weather_driver_id"),
        name="shared_weather_driver_id",
    )
    if kind in {"hp", "pv"} and shared_weather_driver_id != context.shared_weather_driver_id:
        raise ValueError(
            "weather-dependent component output artifacts must use the context shared_weather_driver_id"
        )

    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise TypeError("component output artifact provenance must be a mapping")
    _validate_nonempty_mapping_values(provenance, name="component output artifact provenance")
    stream_id = _stream_id_for_context_component(context, kind)
    artifact_id = _require_nonempty(_require_manifest_text(manifest, "artifact_id"), name="artifact_id")
    array_path = _require_nonempty(_require_manifest_text(manifest, "array_path"), name="array_path")
    expected_sha256 = _require_nonempty(
        _require_manifest_text(manifest, "array_sha256"),
        name="array_sha256",
    )
    root = Path.cwd() if repo_root is None else Path(repo_root)
    resolved_array_path = _resolve_repo_artifact_path(root, array_path, field_name="array_path")
    if not resolved_array_path.is_file():
        raise ValueError("component output artifact array_path does not exist")
    # Checksum verification happens before np.load so accepted provenance cannot
    # be silently paired with a different trajectory file.
    observed_sha256 = _sha256_file(resolved_array_path)
    if observed_sha256 != expected_sha256:
        raise ValueError("component output artifact array_sha256 does not match the file bytes")

    p_kw, q_kvar, timestamps, array_metadata = _load_component_output_npz(
        resolved_array_path,
        expected={
            "artifact_id": artifact_id,
            "component_id": component_id,
            "kind": kind,
            "node_id": node_id,
            "member_id": member_id,
            "source_id": source_id,
            "calendar_id": calendar_id,
            "timestep_seconds": str(timestep_seconds),
            "shared_weather_driver_id": shared_weather_driver_id,
        },
    )
    timestep_count = manifest.get("timestep_count")
    if timestep_count is not None:
        if (
            isinstance(timestep_count, bool)
            or not isinstance(timestep_count, int)
            or timestep_count != timestamps.size
        ):
            raise ValueError("component output artifact timestep_count must match loaded arrays")
    metadata = {
        "artifact_id": artifact_id,
        "artifact_status": artifact_status,
        "array_path": array_path,
        "array_sha256": expected_sha256,
        "calendar_id": calendar_id,
        "timestep_seconds": timestep_seconds,
        "timestep_count": int(timestamps.size),
        "provenance": dict(provenance),
    }
    metadata.update(array_metadata)
    return ComponentAdapterOutput(
        component_id=component_id,
        kind=kind,
        node_id=node_id,
        p_kw=p_kw,
        q_kvar=q_kvar,
        timestamps=timestamps,
        member_id=member_id,
        source_id=source_id,
        stream_id=stream_id,
        shared_weather_driver_id=shared_weather_driver_id,
        metadata=metadata,
    )


def load_net_load_component_from_npz_artifact(
    manifest: Mapping[str, object],
    context: NetLoadRealizationContext,
    *,
    repo_root: Path | str | None = None,
    expected_calendar_id: str | None = None,
    expected_node_ids: Sequence[str] | None = None,
    allow_synthetic_fixture: bool = False,
) -> NetLoadComponent:
    """Load one accepted NPZ artifact and convert it to a validated IC-1 component."""

    adapter_output = load_component_adapter_output_from_npz_artifact(
        manifest,
        context,
        repo_root=repo_root,
        expected_calendar_id=expected_calendar_id,
        expected_node_ids=expected_node_ids,
        allow_synthetic_fixture=allow_synthetic_fixture,
    )
    return net_load_component_from_adapter_output(adapter_output, context)


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
_VALID_EXECUTABLE_INPUT_STATUSES = frozenset(ExecutableInputArtifactStatus.__args__)


def _resolve_repo_metadata_path(repo_root: Path, relative_path: str) -> Path:
    return _resolve_repo_relative_path(repo_root, relative_path, field_name="manifest_path")


def _resolve_repo_artifact_path(repo_root: Path, relative_path: str, *, field_name: str) -> Path:
    return _resolve_repo_relative_path(repo_root, relative_path, field_name=field_name)


def _resolve_repo_relative_path(repo_root: Path, relative_path: str, *, field_name: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"artifact {field_name} must be repository-relative")
    resolved_root = repo_root.resolve()
    resolved = (resolved_root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"artifact {field_name} must stay within repo_root") from exc
    return resolved

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_manifest_text(manifest: Mapping[str, object], key: str) -> str:
    value = manifest.get(key)
    if value is None:
        raise ValueError(f"{key} must not be empty")
    return _require_nonempty(str(value), name=key)


def _require_component_kind(value: object) -> ComponentKind:
    kind = _require_nonempty(str(value or ""), name="kind")
    if kind not in _VALID_COMPONENT_KINDS:
        raise ValueError("kind must be a valid net-load component kind")
    return kind  # type: ignore[return-value]


def _optional_nonempty_text(value: object, *, name: str) -> str | None:
    if value is None:
        return None
    return _require_nonempty(str(value), name=name)


def _require_900_second_cadence(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != 900:
        raise ValueError("timestep_seconds must be the 900-second IC-1 cadence")
    return value


def _validate_expected_node_id(node_id: str, expected_node_ids: Sequence[str] | None) -> None:
    if expected_node_ids is None:
        return
    expected = tuple(_require_nonempty(item, name="expected_node_id") for item in expected_node_ids)
    if node_id not in expected:
        raise ValueError("component output artifact node_id must appear in expected_node_ids")


def _stream_id_for_context_component(
    context: NetLoadRealizationContext,
    kind: ComponentKind,
) -> str:
    for stream in context.component_streams:
        if stream.component == kind:
            return stream.stream_id
    raise ValueError("component output artifact kind must have a matching realization component stream")


def _load_component_output_npz(
    path: Path,
    *,
    expected: Mapping[str, str | None],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    with np.load(path, allow_pickle=False) as data:
        p_kw = _load_npz_float_vector(data, "p_kw")
        q_kvar = _load_npz_float_vector(data, "q_kvar")
        timestamps = _load_npz_datetime_vector(data, "timestamps")
        for field_name, expected_value in expected.items():
            observed = _optional_npz_text(data, field_name)
            if observed is not None and observed != expected_value:
                raise ValueError(f"component output artifact NPZ {field_name} must match the manifest")
        if p_kw.shape != q_kvar.shape or p_kw.shape != timestamps.shape:
            raise ValueError("component output artifact arrays must have identical one-dimensional shapes")
        array_metadata = {
            f"npz_{field_name}": observed
            for field_name in expected
            if (observed := _optional_npz_text(data, field_name)) is not None
        }
    return p_kw, q_kvar, timestamps, array_metadata


def _load_npz_float_vector(data: np.lib.npyio.NpzFile, name: str) -> np.ndarray:
    if name not in data.files:
        raise ValueError(f"component output artifact NPZ missing required array {name}")
    array = np.asarray(data[name], dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"component output artifact {name} must be a non-empty one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"component output artifact {name} must contain only finite values")
    return array


def _load_npz_datetime_vector(data: np.lib.npyio.NpzFile, name: str) -> np.ndarray:
    if name not in data.files:
        raise ValueError(f"component output artifact NPZ missing required array {name}")
    try:
        array = np.asarray(data[name], dtype="datetime64[s]")
    except (TypeError, ValueError) as exc:
        raise ValueError("component output artifact timestamps must be datetime64-compatible") from exc
    if array.ndim != 1 or array.size == 0:
        raise ValueError("component output artifact timestamps must be a non-empty one-dimensional array")
    return array


def _optional_npz_text(data: np.lib.npyio.NpzFile, name: str) -> str | None:
    if name not in data.files:
        return None
    array = np.asarray(data[name])
    if array.shape != ():
        raise ValueError(f"component output artifact NPZ {name} metadata must be scalar")
    value = str(array.item())
    return _require_nonempty(value, name=f"NPZ {name}")


_UNSAFE_EXECUTABLE_TOKENS = (
    "todo",
    "tbd",
    "placeholder",
    "synthetic",
    "proposed",
    "unsigned",
    "not-approved",
)


def _append_loader_blocker(
    items: list[dict[str, object]],
    code: str,
    message: str,
    *,
    kind: str | None = None,
    artifact_id: str | None = None,
    path: str | None = None,
    blocker_ids: Sequence[str] = (),
) -> None:
    record: dict[str, object] = {
        "code": _require_nonempty(code, name="blocker code"),
        "message": _require_nonempty(message, name="blocker message"),
        "blocker_ids": tuple(_require_nonempty(item, name="blocker_id") for item in blocker_ids),
    }
    if kind is not None:
        record["kind"] = _require_nonempty(kind, name="blocker kind")
    if artifact_id is not None:
        record["artifact_id"] = _require_nonempty(artifact_id, name="blocker artifact_id")
    if path is not None:
        record["path"] = _require_nonempty(path, name="blocker path")
    items.append(record)


def _append_bridge_blockers(items: list[dict[str, object]], preflight: Mapping[str, object]) -> None:
    blockers = preflight["blockers"]
    for path in blockers.get("source_manifest_paths_missing", ()):
        _append_loader_blocker(
            items,
            "source_manifest_missing",
            "source manifest path is missing from the repository",
            path=path,
            blocker_ids=("E3.S2-SOURCE-MANIFEST-MISSING",),
        )
    for mismatch in blockers.get("source_manifest_checksum_mismatches", ()):
        _append_loader_blocker(
            items,
            "source_manifest_checksum_mismatch",
            "source manifest SHA-256 does not match the expected value",
            path=mismatch["path"],
            blocker_ids=("E3.S2-SOURCE-CHECKSUM-MISMATCH",),
        )
    for path in blockers.get("unmatched_expected_checksum_paths", ()):
        _append_loader_blocker(
            items,
            "unmatched_expected_checksum_path",
            "expected checksum was supplied for a path not cited by any executable artifact",
            path=path,
            blocker_ids=("E3.S2-UNMATCHED-SOURCE-CHECKSUM",),
        )
    for kind, blocker_ids in blockers.get("component_artifact_blockers_by_kind", {}).items():
        _append_loader_blocker(
            items,
            "component_artifact_gate_blocked",
            "component executable-input gate is not accepted",
            kind=kind,
            blocker_ids=blocker_ids,
        )
    if blockers.get("capacity_provenance_missing"):
        _append_loader_blocker(
            items,
            "capacity_provenance_missing",
            "capacity denominator provenance is required before integrated trajectory acceptance",
            blocker_ids=("G1-A2-CAPACITY-CONVENTION",),
        )
    for blocker_id in blockers.get("downstream_gate_blockers", ()):
        _append_loader_blocker(
            items,
            "downstream_gate_blocked",
            "downstream gate remains unresolved before executable integrated analysis",
            blocker_ids=(blocker_id,),
        )


def _append_cross_component_metadata_blockers(
    items: list[dict[str, object]],
    artifacts: Sequence[ExecutableInputArtifact],
) -> None:
    calendars = {artifact.calendar_id for artifact in artifacts}
    if len(calendars) != 1:
        _append_loader_blocker(
            items,
            "calendar_id_mismatch",
            "all executable component artifacts must cite one common ALEA-001 calendar before loader use",
            blocker_ids=("ALEA-001",),
        )
    weather_ids = {
        artifact.shared_weather_driver_id
        for artifact in artifacts
        if artifact.kind in {"hp", "pv"}
    }
    if weather_ids and (None in weather_ids or len(weather_ids) != 1):
        _append_loader_blocker(
            items,
            "weather_identity_mismatch",
            "HP and PV executable artifacts must share one WEATHER-001 driver identity",
            blocker_ids=("WEATHER-001",),
        )
    for artifact in artifacts:
        unsafe_fields = _unsafe_executable_token_fields(
            {
                "artifact_id": artifact.artifact_id,
                "version_id": artifact.version_id,
                "source_id": artifact.source_id,
                "member_id": artifact.member_id,
                "calendar_id": artifact.calendar_id,
                "shared_weather_driver_id": artifact.shared_weather_driver_id,
                "node_ids": artifact.node_ids,
            }
        )
        if unsafe_fields:
            _append_loader_blocker(
                items,
                "unsafe_executable_metadata_token",
                "executable artifact identity metadata contains a disallowed placeholder/status token",
                kind=artifact.kind,
                artifact_id=artifact.artifact_id,
                blocker_ids=("E3.S2-UNSAFE-EXECUTABLE-METADATA",),
            )
            items[-1]["fields"] = unsafe_fields


def _component_output_manifest_preflight_record(
    repo_root: Path,
    *,
    kind: ComponentKind,
    path: str,
    expected_sha256: str | None,
    executable_artifact: ExecutableInputArtifact,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    blockers: list[dict[str, object]] = []
    record: dict[str, object] = {
        "kind": kind,
        "artifact_id": executable_artifact.artifact_id,
        "path": path,
        "state": "blocked",
    }
    try:
        resolved = _resolve_repo_artifact_path(repo_root, path, field_name="component_output_manifest_path")
    except ValueError as exc:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_path_invalid",
            str(exc),
            kind=kind,
            artifact_id=executable_artifact.artifact_id,
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-MANIFEST-PATH",),
        )
        return record, blockers
    if not resolved.is_file():
        _append_loader_blocker(
            blockers,
            "component_output_manifest_missing",
            "component-output manifest path is missing from the repository",
            kind=kind,
            artifact_id=executable_artifact.artifact_id,
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-MANIFEST",),
        )
        return record, blockers
    observed = _sha256_file(resolved)
    record["sha256"] = observed
    if expected_sha256 is None:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_expected_checksum_missing",
            "component-output manifest requires a version-controlled expected SHA-256",
            kind=kind,
            artifact_id=executable_artifact.artifact_id,
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-MANIFEST-CHECKSUM",),
        )
    else:
        record["expected_sha256"] = expected_sha256
        record["checksum_match"] = observed == expected_sha256
        if observed != expected_sha256:
            _append_loader_blocker(
                blockers,
                "component_output_manifest_checksum_mismatch",
                "component-output manifest SHA-256 does not match the expected value",
                kind=kind,
                artifact_id=executable_artifact.artifact_id,
                path=path,
                blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-MANIFEST-CHECKSUM",),
            )
    try:
        manifest = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_json_invalid",
            f"component-output manifest is not valid JSON: {exc.msg}",
            kind=kind,
            artifact_id=executable_artifact.artifact_id,
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-MANIFEST-JSON",),
        )
        return record, blockers
    schema_blockers = _component_output_manifest_schema_blockers(
        manifest,
        kind=kind,
        path=path,
        executable_artifact=executable_artifact,
        repo_root=repo_root,
    )
    blockers.extend(schema_blockers)
    if not blockers:
        record["state"] = "accepted"
    return record, blockers


def _component_output_manifest_schema_blockers(
    manifest: Mapping[str, object],
    *,
    kind: ComponentKind,
    path: str,
    executable_artifact: ExecutableInputArtifact,
    repo_root: Path,
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    required_keys = (
        "artifact_id",
        "artifact_status",
        "kind",
        "component_id",
        "node_id",
        "member_id",
        "source_id",
        "calendar_id",
        "timestep_seconds",
        "array_path",
        "array_sha256",
        "provenance",
    )
    missing = tuple(key for key in required_keys if key not in manifest)
    if missing:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_required_keys_missing",
            "component-output manifest is not in the accepted-artifact loader schema",
            kind=kind,
            artifact_id=executable_artifact.artifact_id,
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-SCHEMA",),
        )
        blockers[-1]["missing_keys"] = missing
        return blockers
    if manifest["artifact_status"] != "accepted":
        _append_loader_blocker(
            blockers,
            "component_output_manifest_not_accepted",
            "component-output manifest status must be accepted before loader use",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-ACCEPTANCE",),
        )
    if manifest["kind"] != kind:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_kind_mismatch",
            "component-output manifest kind must match the executable artifact kind",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-COMPONENT-OUTPUT-KIND",),
        )
    if manifest["calendar_id"] != executable_artifact.calendar_id:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_calendar_mismatch",
            "component-output manifest calendar_id must match the executable artifact calendar_id",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=("ALEA-001",),
        )
    if manifest["timestep_seconds"] != executable_artifact.timestep_seconds:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_cadence_mismatch",
            "component-output manifest timestep_seconds must match the executable artifact cadence",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=("ALEA-001",),
        )
    if manifest["node_id"] not in executable_artifact.node_ids:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_node_missing",
            "component-output manifest node_id must appear in executable artifact node_ids",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-NODE-MAPPING",),
        )
    shared_weather_driver_id = manifest.get("shared_weather_driver_id")
    if kind in {"hp", "pv"} and shared_weather_driver_id != executable_artifact.shared_weather_driver_id:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_weather_mismatch",
            "weather-dependent component-output manifest must use the executable artifact weather driver",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=("WEATHER-001",),
        )
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        _append_loader_blocker(
            blockers,
            "component_output_manifest_provenance_missing",
            "component-output manifest provenance must be a mapping",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-PROVENANCE",),
        )
    unsafe_fields = _unsafe_executable_token_fields(
        {key: manifest.get(key) for key in required_keys if key != "provenance"}
    )
    if unsafe_fields:
        _append_loader_blocker(
            blockers,
            "component_output_manifest_unsafe_token",
            "component-output manifest executable fields contain disallowed placeholder/status tokens",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-UNSAFE-COMPONENT-OUTPUT-METADATA",),
        )
        blockers[-1]["fields"] = unsafe_fields
    try:
        _resolve_repo_artifact_path(repo_root, str(manifest["array_path"]), field_name="array_path")
    except ValueError:
        _append_loader_blocker(
            blockers,
            "component_output_array_path_invalid",
            "component-output array_path must be repository-relative and contained before loader use",
            kind=kind,
            artifact_id=str(manifest["artifact_id"]),
            path=path,
            blocker_ids=(f"E3.S2-{kind.upper()}-ARRAY-PATH",),
        )
    return blockers


def _unsafe_executable_token_fields(values: Mapping[str, object]) -> tuple[str, ...]:
    unsafe: list[str] = []
    for field_name, value in values.items():
        candidates: tuple[object, ...]
        if value is None:
            continue
        if isinstance(value, (tuple, list)):
            candidates = tuple(value)
        else:
            candidates = (value,)
        for candidate in candidates:
            text = str(candidate).lower()
            if any(token in text for token in _UNSAFE_EXECUTABLE_TOKENS):
                unsafe.append(str(field_name))
                break
    return tuple(sorted(set(unsafe)))


def _validate_bridge_capacity_provenance(record: Mapping[str, object] | None) -> dict[str, object] | None:
    if record is None:
        return None
    required_keys = ("s_nom_agg_kva", "convention_status", "source")
    missing = [key for key in required_keys if key not in record]
    if missing:
        raise ValueError(f"capacity_provenance missing required key(s): {', '.join(missing)}")
    s_nom_agg_kva = float(record["s_nom_agg_kva"])
    if not np.isfinite(s_nom_agg_kva) or s_nom_agg_kva <= 0.0:
        raise ValueError("capacity_provenance s_nom_agg_kva must be finite and positive")
    convention_status = _require_nonempty(str(record["convention_status"]), name="capacity_provenance convention_status")
    source = _require_nonempty(str(record["source"]), name="capacity_provenance source")
    metadata = record.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise TypeError("capacity_provenance metadata must be a mapping")
    _validate_nonempty_mapping_values(metadata, name="capacity_provenance metadata")
    return {
        "s_nom_agg_kva": s_nom_agg_kva,
        "convention_status": convention_status,
        "source": source,
        "metadata": dict(metadata),
    }

def _validate_artifact_register_backing(artifacts: Sequence[ExecutableInputArtifact]) -> None:
    failures: dict[str, list[str]] = {}
    for artifact in artifacts:
        artifact_failures = _register_backing_failures_for_artifact(artifact)
        if artifact_failures:
            failures[artifact.kind] = artifact_failures
    if failures:
        details = "; ".join(
            f"{kind}: {', '.join(values)}"
            for kind, values in sorted(failures.items())
        )
        raise ValueError(f"executable input artifact register backing is not accepted: {details}")


def _register_backing_failures_for_artifact(artifact: ExecutableInputArtifact) -> list[str]:
    rows = _load_register_rows()
    failures: list[str] = []
    for register_id in artifact.signed_register_ids:
        row = rows.get(register_id)
        if row is None:
            failures.append(f"{register_id} (not found)")
            continue
        if not _register_id_matches_component_kind(register_id, artifact.kind):
            failures.append(f"{register_id} (not valid for {artifact.kind})")
            continue
        if not _register_row_is_executable(row):
            failures.append(
                f"{register_id} (status={row['status']}; signoff={row['signoff']})"
            )
    return failures


def _load_register_rows() -> dict[str, dict[str, str]]:
    repo_root = Path(__file__).resolve().parents[2]
    rows: dict[str, dict[str, str]] = {}
    for relative_path, id_index, status_index, signoff_index in REGISTER_FILES:
        register_path = repo_root / relative_path
        if not register_path.exists():
            raise ValueError(f"required register file is missing: {relative_path}")
        for line in register_path.read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) <= max(id_index, status_index, signoff_index):
                continue
            register_id = cells[id_index]
            if not register_id or register_id == "ID" or set(register_id) == {"-"}:
                continue
            rows[register_id] = {
                "status": cells[status_index],
                "signoff": cells[signoff_index],
                "source": relative_path,
            }
    return rows


def _register_row_is_executable(row: Mapping[str, str]) -> bool:
    status = row["status"].strip().lower()
    signoff = row["signoff"].strip().lower()
    if not signoff or signoff == "--":
        return False
    # Artifact metadata cannot self-attest acceptance; executable use requires
    # the committed register row to be signed and free of unresolved caveats.
    if any(marker in status for marker in _UNSIGNED_REGISTER_STATUS_MARKERS):
        return False
    return "approved" in status or "accepted" in status


def _register_id_matches_component_kind(register_id: str, kind: ComponentKind) -> bool:
    if kind == "baseline":
        return register_id in {"D-001"} or register_id.startswith("BASELINE-")
    if kind == "ev":
        return register_id.startswith("EV-") or register_id in {"D-002", "D-010", "A-014"}
    if kind == "hp":
        return register_id.startswith("HP-") or register_id in {"D-003", "D-013", "WEATHER-001"}
    if kind == "pv":
        return register_id.startswith("PV-") or register_id.startswith("D004-") or register_id in {"D-004", "WEATHER-001"}
    if kind == "adoption":
        return register_id.startswith("EV-007") or register_id in {"D-010", "A-014"}
    if kind == "flexibility":
        return register_id.startswith("FLEX-")
    return False


def _normalized_blockers_by_kind(
    values: Mapping[str, Sequence[str]] | None,
) -> dict[str, tuple[str, ...]]:
    if values is None:
        return {}
    normalized: dict[str, tuple[str, ...]] = {}
    for kind, blockers in values.items():
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError("missing_artifact_blockers keys must be valid component kinds")
        blocker_tuple = tuple(_require_nonempty(item, name="missing_artifact_blocker") for item in blockers)
        if not blocker_tuple:
            raise ValueError("missing_artifact_blockers values must not be empty")
        normalized[kind] = blocker_tuple
    return normalized


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


def _validate_loading_input_calendar(
    timestamps: np.ndarray,
    *,
    planning_year: int,
    timestep_seconds: int,
    time_domain: TimeDomain,
) -> None:
    calendar = _as_15_minute_calendar(timestamps)
    years = calendar.astype("datetime64[Y]").astype(int) + 1970
    if not np.all(years == planning_year):
        raise ValueError("loading-input timestamps must stay within the planning year")
    if calendar.size > 1:
        cadence_s = np.diff(calendar).astype("timedelta64[s]").astype(np.int64)
        if not np.all(cadence_s == timestep_seconds):
            raise ValueError("loading-input timestamps must use the declared cadence")
    if time_domain == "full_year":
        start = np.datetime64(f"{planning_year}-01-01T00:00:00", "s")
        next_year = np.datetime64(f"{planning_year + 1}-01-01T00:00:00", "s")
        expected_steps = int((next_year - start) / np.timedelta64(timestep_seconds, "s"))
        expected_end = start + np.timedelta64((expected_steps - 1) * timestep_seconds, "s")
        # A primary-probability manifest must not be creatable from a diagnostic
        # slice; partial windows belong to window_set and are non-primary.
        if calendar.size != expected_steps or calendar[0] != start or calendar[-1] != expected_end:
            raise ValueError("full_year loading-input timestamps must cover the complete planning year")

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
