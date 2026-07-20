from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from src.rng import ComponentSelection, ComponentStream


EXPECTED_FULL_YEAR_STEPS = 35_040
STEP_HOURS = 0.25
LOCAL_TIMEZONE = "Europe/Amsterdam"
ADOPTION_SCHEMA_VERSION = 1
EV_HOME_COMPONENT = "ev_home"


@dataclass(frozen=True)
class ElaadProfileBatch:
    """Parsed ElaadNL EV profile batch.

    Parameters
    ----------
    member_ids:
        Stable local identities in the form ``profile_<batch seed>_<index>``.
    datetimes_utc:
        Timezone-aware UTC timestamps from the API response.
    datetimes_local:
        The same instants converted to Europe/Amsterdam local time.
    demands_kw:
        Matrix of charging demand in kW with shape ``(timesteps, profiles)``.
    batch_seed:
        ElaadNL request seed for the whole returned batch.
    response_config:
        Echoed API configuration block.
    """

    member_ids: tuple[str, ...]
    datetimes_utc: tuple[datetime, ...]
    datetimes_local: tuple[datetime, ...]
    demands_kw: np.ndarray
    batch_seed: int
    response_config: dict[str, Any]

    @property
    def n_timesteps(self) -> int:
        return int(self.demands_kw.shape[0])

    @property
    def n_profiles(self) -> int:
        return int(self.demands_kw.shape[1])

    def annual_energy_kwh(self) -> np.ndarray:
        return self.demands_kw.sum(axis=0) * STEP_HOURS

    def peak_kw(self) -> np.ndarray:
        return self.demands_kw.max(axis=0)


def parse_elaad_profile_response(
    payload: bytes | str | dict[str, Any],
    *,
    batch_seed: int,
    expected_n_profiles: int,
    expected_timesteps: int = EXPECTED_FULL_YEAR_STEPS,
) -> ElaadProfileBatch:
    """Parse and validate a time-major ElaadNL profile-generator response."""
    parsed = _load_response_payload(payload)
    profile = parsed.get("profile")
    if not isinstance(profile, dict):
        raise ValueError("ElaadNL response lacks a profile object")

    datetimes_raw = profile.get("datetimes")
    demands_raw = profile.get("demands_kw")
    if not isinstance(datetimes_raw, list) or not isinstance(demands_raw, list):
        raise ValueError("ElaadNL profile must contain datetimes and demands_kw lists")
    if len(datetimes_raw) != expected_timesteps:
        raise ValueError(f"Expected {expected_timesteps} timestamps, got {len(datetimes_raw)}")
    if len(demands_raw) != len(datetimes_raw):
        raise ValueError("Expected time-major demands_kw with one row per timestamp")

    demands = np.asarray(demands_raw, dtype=np.float64)
    if demands.ndim != 2:
        raise ValueError("demands_kw must be a two-dimensional time-major array")
    if demands.shape != (expected_timesteps, expected_n_profiles):
        raise ValueError(
            f"Expected demands_kw shape {(expected_timesteps, expected_n_profiles)}, got {demands.shape}"
        )
    if not np.isfinite(demands).all():
        raise ValueError("demands_kw contains missing or non-finite values")
    if (demands < 0).any():
        raise ValueError("demands_kw contains negative values")

    datetimes_utc = tuple(_parse_utc_timestamp(item) for item in datetimes_raw)
    datetimes_local = tuple(item.astimezone(_local_zone()) for item in datetimes_utc)
    _validate_time_axis(datetimes_utc, datetimes_local, expected_timesteps)

    member_ids = tuple(f"profile_{batch_seed}_{index:03d}" for index in range(expected_n_profiles))
    response_config = parsed.get("config") if isinstance(parsed.get("config"), dict) else {}
    return ElaadProfileBatch(
        member_ids=member_ids,
        datetimes_utc=datetimes_utc,
        datetimes_local=datetimes_local,
        demands_kw=demands.astype(np.float32),
        batch_seed=batch_seed,
        response_config=response_config,
    )


def distinct_member_count(batch: ElaadProfileBatch) -> int:
    """Return the number of distinct returned demand series."""
    if batch.n_profiles == 0:
        return 0
    columns = np.ascontiguousarray(batch.demands_kw.T)
    return len({column.tobytes() for column in columns})


def save_processed_batch_npz(batch: ElaadProfileBatch, path: Path) -> None:
    """Save an ignored local processed batch for deterministic sampling."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        demands_kw=batch.demands_kw,
        member_ids=np.asarray(batch.member_ids),
        datetimes_utc=np.asarray([item.isoformat() for item in batch.datetimes_utc]),
        datetimes_local=np.asarray([item.isoformat() for item in batch.datetimes_local]),
        batch_seed=np.asarray(batch.batch_seed),
    )


def load_processed_batch_npz(path: Path) -> ElaadProfileBatch:
    """Load an ignored local processed batch saved by ``save_processed_batch_npz``."""
    with np.load(path, allow_pickle=False) as data:
        demands = np.asarray(data["demands_kw"], dtype=np.float32)
        member_ids = tuple(str(item) for item in data["member_ids"].tolist())
        datetimes_utc = tuple(_parse_utc_timestamp(str(item)) for item in data["datetimes_utc"].tolist())
        datetimes_local = tuple(datetime.fromisoformat(str(item)) for item in data["datetimes_local"].tolist())
        batch_seed = int(data["batch_seed"])
    return ElaadProfileBatch(
        member_ids=member_ids,
        datetimes_utc=datetimes_utc,
        datetimes_local=datetimes_local,
        demands_kw=demands,
        batch_seed=batch_seed,
        response_config={},
    )


class EVProfileBootstrapSampler:
    """Deterministic sampler over an archived ElaadNL profile batch."""

    def __init__(self, batch: ElaadProfileBatch) -> None:
        if batch.n_profiles == 0:
            raise ValueError("Cannot sample from an empty EV profile batch")
        self.batch = batch

    @classmethod
    def from_npz(cls, path: Path) -> EVProfileBootstrapSampler:
        return cls(load_processed_batch_npz(path))

    # EV-005 deliberately has no default: replacement changes the dependence
    # structure within one realization and therefore requires an explicit choice.
    def select_members(
        self,
        n_members: int,
        *,
        component_stream: ComponentStream,
        replace: bool,
    ) -> EVBootstrapSelection:
        if component_stream.component != EV_HOME_COMPONENT:
            raise ValueError(f"Home EV profile sampling requires component stream {EV_HOME_COMPONENT!r}")
        if n_members < 0:
            raise ValueError("n_members must be non-negative")
        if not replace and n_members > self.batch.n_profiles:
            raise ValueError("Cannot sample more distinct members than are available")
        indices = tuple(
            int(index)
            for index in component_stream.rng().choice(
                self.batch.n_profiles,
                size=n_members,
                replace=replace,
            )
        )
        member_ids = tuple(self.batch.member_ids[index] for index in indices)
        return EVBootstrapSelection(
            indices=indices,
            member_ids=member_ids,
            component_stream=component_stream,
            replace=replace,
        )

    def sample_member_indices(
        self,
        n_members: int,
        *,
        component_stream: ComponentStream,
        replace: bool,
    ) -> np.ndarray:
        selection = self.select_members(
            n_members,
            component_stream=component_stream,
            replace=replace,
        )
        return selection.index_array()

    def sample_profiles_kw(
        self,
        n_members: int,
        *,
        component_stream: ComponentStream,
        replace: bool,
    ) -> np.ndarray:
        selection = self.select_members(
            n_members,
            component_stream=component_stream,
            replace=replace,
        )
        return self.batch.demands_kw[:, selection.index_array()]

    def sample_aggregate_kw(
        self,
        n_members: int,
        *,
        component_stream: ComponentStream,
        replace: bool,
    ) -> np.ndarray:
        profiles = self.sample_profiles_kw(
            n_members,
            component_stream=component_stream,
            replace=replace,
        )
        return profiles.sum(axis=1)


@dataclass(frozen=True)
class EVBootstrapSelection:
    """Traceable EV source-member selection for one component stream."""

    indices: tuple[int, ...]
    member_ids: tuple[str, ...]
    component_stream: ComponentStream
    replace: bool

    def __post_init__(self) -> None:
        if len(self.indices) != len(self.member_ids):
            raise ValueError("indices and member_ids must have the same length")

    @property
    def stream_id(self) -> str:
        return self.component_stream.stream_id

    def index_array(self) -> np.ndarray:
        return np.asarray(self.indices, dtype=np.int64)

    def component_selections(self) -> tuple[ComponentSelection, ...]:
        # Selection indices are stored so future manifests can reconstruct the
        # bootstrap draw without treating the ElaadNL member IDs as new seeds.
        return tuple(
            ComponentSelection(
                component=self.component_stream.component,
                source_member_id=member_id,
                stream_id=self.component_stream.stream_id,
                selection_index=selection_index,
            )
            for selection_index, member_id in enumerate(self.member_ids)
        )


@dataclass(frozen=True)
class EVProfileLibrary:
    """Traceable frozen ElaadNL profile library assembled from annual batches."""

    batches: tuple[ElaadProfileBatch, ...]
    partitions: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.batches) != len(self.partitions):
            raise ValueError("batches and partitions must have the same length")
        if not self.batches:
            raise ValueError("EV profile library cannot be empty")
        first_times = self.batches[0].datetimes_utc
        for batch in self.batches:
            if batch.datetimes_utc != first_times:
                raise ValueError("All EV profile batches must share one complete calendar")
        member_ids = self.member_ids
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("EV profile member IDs must be unique across batches")

    @classmethod
    def from_npz_paths(
        cls,
        paths: Sequence[Path],
        *,
        partitions: Sequence[str],
    ) -> EVProfileLibrary:
        raise PermissionError(
            "Load EV profile libraries from the committed library manifest so partitions and checksums are traceable"
        )

    @classmethod
    def from_library_manifest(
        cls,
        manifest_path: Path,
        *,
        base_dir: Path | None = None,
        include_partitions: Sequence[str] = ("candidate",),
    ) -> EVProfileLibrary:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        blocked = {"held_out", "quarantined_precriterion_diagnostic"}
        requested = set(include_partitions)
        if requested & blocked:
            raise PermissionError(
                "Held-out and quarantined EV profiles require traceable E3.S2a criterion authorization, which is not approved"
            )
        root = base_dir or Path(".")
        batches: list[ElaadProfileBatch] = []
        partitions: list[str] = []
        for item in manifest.get("batches", []):
            partition = str(item["partition"])
            if partition not in requested:
                continue
            path = root / str(item["processed_path"])
            # The manifest checksum is the source of partition truth; callers
            # cannot relabel arbitrary NPZs without changing committed metadata.
            actual = _sha256_file(path)
            if actual != item["processed_sha256_file"]:
                raise ValueError(f"Processed EV profile checksum mismatch for {path}")
            batches.append(load_processed_batch_npz(path))
            partitions.append(partition)
        return cls(batches=tuple(batches), partitions=tuple(partitions))

    @property
    def n_members(self) -> int:
        return sum(batch.n_profiles for batch in self.batches)

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(member_id for batch in self.batches for member_id in batch.member_ids)

    @property
    def demands_kw(self) -> np.ndarray:
        return np.concatenate([batch.demands_kw for batch in self.batches], axis=1)

    def member_table(self) -> tuple[dict[str, int | str], ...]:
        rows: list[dict[str, int | str]] = []
        for batch, partition in zip(self.batches, self.partitions, strict=True):
            for returned_index, member_id in enumerate(batch.member_ids):
                rows.append(
                    {
                        "member_id": member_id,
                        "partition": partition,
                        "batch_seed": batch.batch_seed,
                        "returned_profile_index": returned_index,
                    }
                )
        return tuple(rows)

    def view(self, partition: str) -> EVProfileLibrary:
        if partition in {"held_out", "quarantined_precriterion_diagnostic"}:
            raise PermissionError(
                "Held-out and quarantined EV profiles remain isolated until traceable E3.S2a criterion authorization exists"
            )
        selected = [
            (batch, item_partition)
            for batch, item_partition in zip(self.batches, self.partitions, strict=True)
            if item_partition == partition
        ]
        if not selected:
            raise ValueError(f"No EV profile batches found for partition {partition!r}")
        return EVProfileLibrary(
            batches=tuple(batch for batch, _ in selected),
            partitions=tuple(item_partition for _, item_partition in selected),
        )

    def nested_candidate_view(self, n_batches: int) -> EVProfileLibrary:
        candidate = self.view("candidate")
        if n_batches <= 0 or n_batches > len(candidate.batches):
            raise ValueError("n_batches must select at least one available candidate batch")
        return EVProfileLibrary(
            batches=candidate.batches[:n_batches],
            partitions=candidate.partitions[:n_batches],
        )

    def leave_one_batch_out_candidate_views(self) -> tuple[EVProfileLibrary, ...]:
        candidate = self.view("candidate")
        if len(candidate.batches) < 2:
            raise ValueError("At least two candidate batches are required for leave-one-batch-out views")
        views: list[EVProfileLibrary] = []
        for omitted in range(len(candidate.batches)):
            # Leave out whole API batches so finite-library diagnostics preserve
            # EV-005 seed separation instead of pretending profiles are iid rows.
            views.append(
                EVProfileLibrary(
                    batches=tuple(
                        batch for index, batch in enumerate(candidate.batches) if index != omitted
                    ),
                    partitions=tuple(
                        partition
                        for index, partition in enumerate(candidate.partitions)
                        if index != omitted
                    ),
                )
            )
        return tuple(views)

    def sampler(self) -> EVProfileBootstrapSampler:
        disallowed = {"held_out", "quarantined_precriterion_diagnostic"}
        if set(self.partitions) & disallowed:
            raise PermissionError("EVProfileLibrary.sampler requires a candidate-only library")
        first = self.batches[0]
        batch = ElaadProfileBatch(
            member_ids=self.member_ids,
            datetimes_utc=first.datetimes_utc,
            datetimes_local=first.datetimes_local,
            demands_kw=self.demands_kw,
            batch_seed=-1,
            response_config={"source": "EVProfileLibrary"},
        )
        return EVProfileBootstrapSampler(batch)

    def disjoint_candidate_batch_views(self, n_batches_per_view: int) -> tuple[EVProfileLibrary, ...]:
        candidate = self.view("candidate")
        if n_batches_per_view <= 0:
            raise ValueError("n_batches_per_view must be positive")
        if len(candidate.batches) % n_batches_per_view != 0:
            raise ValueError("Candidate batches must divide evenly into complete disjoint views")
        views: list[EVProfileLibrary] = []
        for start in range(0, len(candidate.batches), n_batches_per_view):
            stop = start + n_batches_per_view
            views.append(
                EVProfileLibrary(
                    batches=candidate.batches[start:stop],
                    partitions=candidate.partitions[start:stop],
                )
            )
        return tuple(views)


@dataclass(frozen=True)
class ChargePointScenario:
    """Local-grid EV charge-point counts for one planning year and scenario.

    Parameters
    ----------
    year:
        Planning year of the external adoption layer.
    scenario:
        Outlook scenario label, e.g. ``"low"``, ``"middle"``, or ``"high"``.
    home_charge_points:
        Number of physical home charge points.
    public_charge_points:
        Number of public charge points. Public profile behavior remains blocked
        until its separate source class is approved.
    provenance:
        Source and derivation labels for the two counts.
    """

    year: int
    scenario: str
    home_charge_points: int
    public_charge_points: int
    provenance: dict[str, str]


@dataclass(frozen=True)
class NationalOutlookProjection:
    """Read-only national Outlook projection retained as source provenance."""

    year: int
    scenario: str
    location: str
    value: float
    rounded_count: int
    source_id: str
    response_sha256: str


@dataclass(frozen=True)
class NodeChargePointAllocation:
    """Integer nodal charge-point allocation for a scenario."""

    year: int
    scenario: str
    home_by_node: dict[str, int]
    public_by_node: dict[str, int]

    @property
    def total_home_charge_points(self) -> int:
        return sum(self.home_by_node.values())

    @property
    def total_public_charge_points(self) -> int:
        return sum(self.public_by_node.values())


def load_adoption_scenarios_config(path: Path) -> dict[str, Any]:
    """Load and validate the E2.S6 adoption scenario configuration."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Adoption scenario config must be a mapping")
    validate_adoption_scenarios_config(data)
    return data


def validate_adoption_scenarios_config(config: dict[str, Any]) -> None:
    """Validate the E2.S6 scenario schema and provenance links."""

    if config.get("schema_version") != ADOPTION_SCHEMA_VERSION:
        raise ValueError(f"Expected schema_version {ADOPTION_SCHEMA_VERSION}")
    if config.get("task_id") != "E2.S6":
        raise ValueError("Adoption scenario config must declare task_id E2.S6")
    source_ids = config.get("source_ids")
    if not isinstance(source_ids, dict):
        raise ValueError("Adoption scenario config must declare source_ids")
    outlook_id = str(source_ids.get("national_outlook_projection", ""))
    allocation_id = str(source_ids.get("local_allocation_assumption", ""))
    sources = config.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Adoption scenario config must include source provenance")
    outlook = sources.get(outlook_id)
    if not isinstance(outlook, dict) or not outlook.get("url"):
        raise ValueError("ElaadNL Outlook provenance is required")
    national = config.get("national_outlook_projections")
    if not isinstance(national, list) or not national:
        raise ValueError("National Outlook projections are required as separate provenance")
    national_keys: set[tuple[int, str, str]] = set()
    for item in national:
        projection = _national_projection_from_mapping(item, outlook_id=outlook_id)
        key = (projection.year, projection.scenario, projection.location)
        if key in national_keys:
            raise ValueError("National Outlook projection keys must be unique")
        national_keys.add(key)
    allocation = config.get("allocation")
    if not isinstance(allocation, dict):
        raise ValueError("Adoption scenario config must include allocation settings")
    if allocation.get("method_id") != allocation_id:
        raise ValueError("allocation.method_id must match source_ids.local_allocation_assumption")
    if allocation.get("status") not in {"blocked", "proposed", "approved"}:
        raise ValueError("allocation status must be blocked, proposed, or approved")
    weights = allocation.get("node_weights")
    if weights is None:
        source = allocation.get("node_weight_source")
        if not isinstance(source, dict) or source.get("method_id") != allocation_id:
            raise ValueError("allocation must provide node_weights or an A-014 node_weight_source")
    else:
        _validate_node_weight_records(weights)
    local = config.get("local_grid_scenarios")
    if not isinstance(local, dict):
        raise ValueError("local_grid_scenarios must be present")
    if local.get("status") not in {"blocked", "proposed", "approved"}:
        raise ValueError("local_grid_scenarios status must be blocked, proposed, or approved")
    scenarios = local.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("local_grid_scenarios.scenarios must be a list")
    if local.get("status") in {"blocked", "proposed"} and scenarios:
        raise ValueError("Local-grid scenarios may contain counts only after their register status is approved")
    scenario_keys: set[tuple[int, str]] = set()
    for item in scenarios:
        scenario = _scenario_from_mapping(item, outlook_id=outlook_id)
        key = (scenario.year, scenario.scenario)
        if key in scenario_keys:
            raise ValueError("Local-grid scenario keys must be unique")
        scenario_keys.add(key)


def national_outlook_projections(config: dict[str, Any]) -> tuple[NationalOutlookProjection, ...]:
    """Return national Outlook projections; these are not local-grid counts."""

    validate_adoption_scenarios_config(config)
    outlook_id = str(config["source_ids"]["national_outlook_projection"])
    return tuple(
        _national_projection_from_mapping(item, outlook_id=outlook_id)
        for item in config["national_outlook_projections"]
    )


def adoption_scenarios(config: dict[str, Any]) -> tuple[ChargePointScenario, ...]:
    """Return validated local-grid charge-point scenarios from config data."""

    validate_adoption_scenarios_config(config)
    if config["local_grid_scenarios"].get("status") != "approved":
        raise ValueError("Local-grid charge-point scenarios remain blocked until Q-7 is approved")
    outlook_id = str(config["source_ids"]["national_outlook_projection"])
    return tuple(
        _scenario_from_mapping(item, outlook_id=outlook_id)
        for item in config["local_grid_scenarios"]["scenarios"]
    )


def allocate_charge_points_to_nodes(
    total_count: int,
    node_weights: Sequence[tuple[str, float]],
) -> dict[str, int]:
    """Allocate integer charge-point counts by deterministic largest remainder."""

    total_count = _require_int(total_count, "total_count")
    if total_count < 0:
        raise ValueError("total_count must be a non-negative integer")
    if not node_weights:
        raise ValueError("node_weights must be non-empty")
    normalized_weights: list[tuple[str, float]] = []
    seen_node_ids: set[str] = set()
    for node_id_raw, weight_raw in node_weights:
        node_id = str(node_id_raw)
        if not node_id or node_id in seen_node_ids:
            raise ValueError("node_weights must contain unique non-empty node IDs")
        seen_node_ids.add(node_id)
        weight = float(weight_raw)
        if not np.isfinite(weight) or weight < 0.0:
            raise ValueError("node_weights must contain finite non-negative weights")
        normalized_weights.append((node_id, weight))
    total_weight = sum(weight for _, weight in normalized_weights)
    if total_weight <= 0:
        raise ValueError("At least one node weight must be positive")
    raw = [(node_id, total_count * weight / total_weight) for node_id, weight in normalized_weights]
    floors = {node_id: int(np.floor(value)) for node_id, value in raw}
    remainder = total_count - sum(floors.values())
    # Ties are resolved by node_id so reruns do not depend on source row order
    # whenever two load nodes have equal fractional entitlement.
    ranked = sorted(raw, key=lambda item: (-(item[1] - np.floor(item[1])), item[0]))
    for node_id, _ in ranked[:remainder]:
        floors[node_id] += 1
    return floors


def adoption_node_allocations(config: dict[str, Any]) -> tuple[NodeChargePointAllocation, ...]:
    """Derive deterministic per-node home/public charge-point allocations."""

    scenarios = adoption_scenarios(config)
    if not scenarios:
        raise ValueError("Local-grid charge-point counts are blocked until Q-7 selects a scaling method")
    if config["allocation"].get("status") != "approved":
        raise ValueError("Node charge-point allocation remains blocked until A-014 is approved")
    weight_records = config["allocation"].get("node_weights")
    if weight_records is None:
        raise ValueError("adoption_node_allocations requires explicit node_weights")
    weights = tuple((str(item["node_id"]), float(item["weight"])) for item in weight_records)
    allocations = []
    for scenario in scenarios:
        allocations.append(
            NodeChargePointAllocation(
                year=scenario.year,
                scenario=scenario.scenario,
                home_by_node=allocate_charge_points_to_nodes(
                    scenario.home_charge_points,
                    weights,
                ),
                public_by_node=allocate_charge_points_to_nodes(
                    scenario.public_charge_points,
                    weights,
                ),
            )
        )
    return tuple(allocations)


def charge_point_range_by_year(
    scenarios: Sequence[ChargePointScenario],
) -> dict[int, dict[str, int]]:
    """Return low/high total count ranges by planning year."""

    ranges: dict[int, dict[str, int]] = {}
    for year in sorted({item.year for item in scenarios}):
        subset = [item for item in scenarios if item.year == year]
        ranges[year] = {
            "home_min": min(item.home_charge_points for item in subset),
            "home_max": max(item.home_charge_points for item in subset),
            "public_min": min(item.public_charge_points for item in subset),
            "public_max": max(item.public_charge_points for item in subset),
        }
    return ranges


def node_charge_point_ranges(
    allocations: Sequence[NodeChargePointAllocation],
) -> dict[str, dict[str, int]]:
    """Return per-node min/max ``K_r`` ranges across all configured scenarios."""

    node_ids = sorted({node for allocation in allocations for node in allocation.home_by_node})
    ranges: dict[str, dict[str, int]] = {}
    for node_id in node_ids:
        home_values = [allocation.home_by_node[node_id] for allocation in allocations]
        public_values = [allocation.public_by_node[node_id] for allocation in allocations]
        ranges[node_id] = {
            "home_min": min(home_values),
            "home_max": max(home_values),
            "public_min": min(public_values),
            "public_max": max(public_values),
        }
    return ranges


def batch_summary(batch: ElaadProfileBatch) -> dict[str, Any]:
    """Return commit-safe shape and aggregate statistics for a generated batch."""
    annual = batch.annual_energy_kwh()
    peak = batch.peak_kw()
    return {
        "n_timesteps": batch.n_timesteps,
        "n_profiles": batch.n_profiles,
        "member_identity": "profile_<batch seed>_<returned profile index>",
        "batch_seed": batch.batch_seed,
        "distinct_member_count": distinct_member_count(batch),
        "first_timestamp_utc": batch.datetimes_utc[0].isoformat(),
        "last_timestamp_utc": batch.datetimes_utc[-1].isoformat(),
        "first_timestamp_local": batch.datetimes_local[0].isoformat(),
        "last_timestamp_local": batch.datetimes_local[-1].isoformat(),
        "timezone_conversion": "UTC response timestamps converted to Europe/Amsterdam for local use.",
        "missing_or_nonfinite_values": int(np.size(batch.demands_kw) - np.isfinite(batch.demands_kw).sum()),
        "negative_values": int((batch.demands_kw < 0).sum()),
        "annual_energy_kwh": _series_stats(annual),
        "peak_kw": _series_stats(peak),
    }


def read_gzip_json(path: Path) -> bytes:
    with gzip.open(path, "rb") as handle:
        return handle.read()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _national_projection_from_mapping(item: Any, *, outlook_id: str) -> NationalOutlookProjection:
    if not isinstance(item, dict):
        raise ValueError("Each national Outlook projection must be a mapping")
    year = _require_int(item.get("year"), "National Outlook projection year")
    scenario = str(item.get("scenario", ""))
    location = str(item.get("location", ""))
    value = float(item.get("value", float("nan")))
    rounded_count = _require_int(item.get("rounded_count"), "National Outlook rounded_count")
    if year not in {2030, 2033, 2035}:
        raise ValueError("E2.S6 national projections must be for 2030, 2033, or 2035")
    if scenario not in {"low", "middle", "high"}:
        raise ValueError("National Outlook scenario must be low, middle, or high")
    if location not in {"home", "public"}:
        raise ValueError("National Outlook location must be home or public")
    if not np.isfinite(value) or value < 0.0:
        raise ValueError("National Outlook value must be finite and non-negative")
    if rounded_count < 0 or rounded_count != int(round(value)):
        raise ValueError("National Outlook rounded_count must be the nearest integer API value")
    provenance = item.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("source_id") != outlook_id:
        raise ValueError("National Outlook projections must trace to the Outlook source ID")
    response_sha256 = str(provenance.get("response_sha256", ""))
    if len(response_sha256) != 64:
        raise ValueError("National Outlook projections must record a response sha256")
    return NationalOutlookProjection(
        year=year,
        scenario=scenario,
        location=location,
        value=value,
        rounded_count=rounded_count,
        source_id=outlook_id,
        response_sha256=response_sha256,
    )


def _scenario_from_mapping(item: Any, *, outlook_id: str) -> ChargePointScenario:
    if not isinstance(item, dict):
        raise ValueError("Each adoption scenario must be a mapping")
    year = _require_int(item.get("year"), "Local-grid scenario year")
    scenario = str(item.get("scenario", ""))
    home = _require_int(item.get("home_charge_points"), "home_charge_points")
    public = _require_int(item.get("public_charge_points"), "public_charge_points")
    if year not in {2030, 2033, 2035}:
        raise ValueError("E2.S6 scenarios must be for 2030, 2033, or 2035")
    if scenario not in {"low", "middle", "high"}:
        raise ValueError("Scenario must be low, middle, or high")
    if home < 0 or public < 0:
        raise ValueError("Charge-point counts must be non-negative integers")
    provenance = item.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Each adoption scenario must include provenance")
    if provenance.get("source_type") != "local_grid":
        raise ValueError("Local-grid counts must declare source_type=local_grid")
    if provenance.get("home_charge_points") == outlook_id or provenance.get("public_charge_points") == outlook_id:
        raise ValueError("National Outlook projections cannot be used directly as local-grid counts")
    return ChargePointScenario(
        year=year,
        scenario=scenario,
        home_charge_points=home,
        public_charge_points=public,
        provenance={str(key): str(value) for key, value in provenance.items()},
    )


def _validate_node_weight_records(weights: Any) -> None:
    if not isinstance(weights, list) or not weights:
        raise ValueError("allocation.node_weights must be a non-empty list")
    node_ids: set[str] = set()
    for item in weights:
        if not isinstance(item, dict):
            raise ValueError("Each node weight must be a mapping")
        node_id = str(item.get("node_id", ""))
        if not node_id or node_id in node_ids:
            raise ValueError("Node IDs must be present and unique")
        node_ids.add(node_id)
        weight = float(item.get("weight", float("nan")))
        if not np.isfinite(weight) or weight < 0:
            raise ValueError("Node allocation weights must be finite and non-negative")
    total_weight = sum(float(item["weight"]) for item in weights)
    if total_weight <= 0:
        raise ValueError("At least one node allocation weight must be positive")


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a true integer")
    return value


def _load_response_payload(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, bytes):
        parsed = json.loads(payload.decode("utf-8"))
    else:
        parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("Expected ElaadNL response JSON object")
    return parsed


def _parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("ElaadNL timestamp lacks timezone information")
    return parsed.astimezone(UTC)


def _validate_time_axis(
    datetimes_utc: Sequence[datetime],
    datetimes_local: Sequence[datetime],
    expected_timesteps: int,
) -> None:
    if len(datetimes_utc) != expected_timesteps:
        raise ValueError("Unexpected UTC timestamp count")
    if datetimes_utc[0].isoformat() != "2024-12-31T23:00:00+00:00":
        raise ValueError(f"Unexpected first UTC timestamp: {datetimes_utc[0].isoformat()}")
    if datetimes_local[0].isoformat() != "2025-01-01T00:00:00+01:00":
        raise ValueError(f"Unexpected first local timestamp: {datetimes_local[0].isoformat()}")
    deltas = np.diff([item.timestamp() for item in datetimes_utc])
    if not np.all(deltas == 900):
        raise ValueError("UTC timestamps are not spaced at 15-minute intervals")


def _local_zone():
    from zoneinfo import ZoneInfo

    return ZoneInfo(LOCAL_TIMEZONE)


def _series_stats(values: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.min(values)),
        "p05": float(np.quantile(values, 0.05)),
        "median": float(np.median(values)),
        "mean": float(np.mean(values)),
        "p95": float(np.quantile(values, 0.95)),
        "max": float(np.max(values)),
    }
